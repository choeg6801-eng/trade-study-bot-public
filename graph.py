"""LangGraph 흐름: 질문 → retrieve(문서 조각 찾기) → generate(조각만 근거로 답하기).
도전: 관련 조각이 없으면 rewrite 로 질문을 바꿔 retrieve 를 딱 한 번 더 해요.

사용:
  from graph import ask, ask_stream
  result = ask("FOB 가 뭐야?")   # result["answer"], result["sources"]
터미널 시험: python graph.py "FOB 가 뭐야?"   (질문이 없으면 흐름 그림(mermaid) 출력)
"""
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterator, TypedDict

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph

load_dotenv()  # .env 에서 키 · 모델 이름 읽기 (코드에 직접 쓰지 않아요)

DB_DIR = Path(__file__).parent / "chroma_db"
COLLECTION = "trade_notes"      # ingest.py 와 같은 이름이어야 해요
TOP_K = 4                       # 질문과 비슷한 조각을 몇 개 찾을지
MAX_DISTANCE = 1.40             # 이보다 멀면(덜 비슷하면) 관련 없는 조각 (시험 질문으로 정한 값)
SOURCE_MARGIN = 0.4             # 출처로 보여 줄 조각은 가장 가까운 조각보다 이만큼 이내로 가까운 것만
NOT_FOUND = "문서에서 찾지 못했어요"
ERROR_MESSAGE = "지금은 답을 만들지 못했어요. 인터넷 연결, .env 의 API 키, OpenAI 크레딧을 확인하고 다시 물어봐 주세요."

PROMPT = """너는 무역 공부를 돕는 도우미야. 아래 [문서 조각]에 적힌 내용만 근거로 한국어로 쉽게 답해.
- 비전공자가 이해할 수 있게 짧고 쉽게 설명해.
- [문서 조각]에서 답을 찾을 수 없으면 다른 말 없이 정확히 "{not_found}" 라고만 답해.
- 조각에 없는 내용을 지어내거나 네가 아는 지식으로 보태지 마. 영어 풀네임·번역·숫자·예시도 조각에 그대로 적혀 있을 때만 말해.
- 질문의 일부만 조각에 있으면 있는 부분만 답하고, 없는 부분은 "{not_found}" 라고 덧붙여.
- [이전 대화]는 질문이 가리키는 대상("그건", "아까 그거")을 이해하는 데만 쓰고, 근거는 반드시 [문서 조각]에서만 찾아.

[이전 대화]
{history}

[문서 조각]
{context}

[질문]
{question}"""

REWRITE_PROMPT = """아래 질문으로 무역 용어 노트와 회사 소개 문서에서 내용을 찾지 못했어.
문서 검색에 더 잘 걸리도록, 질문에 담긴 핵심 무역 용어나 키워드로 바꿔서 한 줄로만 써줘.
(예: '짐 실었다는 증거 서류' → '선하증권 B/L 화물 선적 증명 서류')
질문이 "그건", "아까 그거"처럼 이전 대화를 가리키면 [이전 대화]를 보고 대상을 풀어서 써줘.
설명 없이 바꾼 검색어만 출력해.

[이전 대화]
{history}

[질문]
{question}"""


class State(TypedDict):
    """그래프가 노드 사이에 주고받는 값들."""
    question: str       # 사용자의 질문 (답변할 때는 항상 이 원래 질문을 써요)
    history: list       # 직전 대화 [{"q": 질문, "a": 답}] (최대 2번 · 대명사 질문을 이해하는 용도)
    search_query: str   # 검색에 쓰는 문장 (처음엔 질문 그대로, 다시 찾을 땐 바꾼 문장)
    retries: int        # 질문을 바꿔 다시 찾은 횟수 (최대 1번)
    docs: list          # 찾아 온 문서 조각들
    answer: str         # 최종 답변
    sources: list       # 출처 목록 [{"file": 파일 이름, "preview": 미리보기}]


def format_history(history: list) -> str:
    """직전 대화를 프롬프트에 넣을 짧은 글로 바꿔요. 없으면 '(없음)'."""
    if not history:
        return "(없음)"
    return "\n".join(f"- 질문: {h['q'][:120]}\n  답: {h['a'][:200]}" for h in history[-2:])


@lru_cache(maxsize=1)
def get_store():
    """저장해 둔 벡터 저장소(chroma_db/)를 한 번만 열어요. (문서를 새로 넣으면 get_store.cache_clear())"""
    embeddings = OpenAIEmbeddings(model=os.getenv("OPENAI_EMBED_MODEL"), max_retries=0)
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
    )


@lru_cache(maxsize=1)
def get_llm():
    """대화 모델(OPENAI_MODEL)을 한 번만 만들어요. 자동 재시도는 끄고 비용을 아껴요.

    OPENAI_REASONING_EFFORT(기본 low)로 모델의 '생각 시간'을 줄여 답이 빨라지고 토큰도 아껴요.
    이 옵션을 지원하지 않는 모델이면 .env 에 OPENAI_REASONING_EFFORT=none 을 적어 끄세요.
    """
    effort = os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower()
    extra = {} if effort in ("", "none") else {"reasoning_effort": effort}
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL"), max_retries=0, **extra)


def retrieve(state: State) -> dict:
    """검색 문장과 비슷한 문서 조각 4개를 찾고, 너무 먼 조각은 버려요."""
    query = state.get("search_query") or state["question"]
    found = get_store().similarity_search_with_score(query, k=TOP_K)
    docs = []
    for doc, distance in found:
        if distance <= MAX_DISTANCE:
            doc.metadata["distance"] = float(distance)  # 출처를 고를 때 '얼마나 가까운지' 쓰려고 적어 둬요
            docs.append(doc)
    return {"docs": docs}


def rewrite(state: State) -> dict:
    """찾은 게 없을 때 질문을 검색하기 좋은 키워드로 바꿔요. (모델 1번 호출, 딱 한 번만 거쳐요)"""
    reply = get_llm().invoke(
        REWRITE_PROMPT.format(question=state["question"], history=format_history(state["history"]))
    )
    lines = reply.content.strip().splitlines()
    new_query = lines[0].strip()[:100] if lines else ""
    return {"search_query": new_query or state["question"], "retries": state["retries"] + 1}


def route_after_retrieve(state: State) -> str:
    """조건 분기: 관련 조각이 없고 아직 다시 찾지 않았다면 rewrite, 아니면 generate 로 가요."""
    if not state["docs"] and state["retries"] < 1:
        return "rewrite"
    return "generate"


def generate(state: State) -> dict:
    """찾은 조각만 근거로 답하고, 근거가 없으면 모델을 부르지 않고 바로 '못 찾았어요'로 답해요."""
    docs = state["docs"]
    if not docs:  # 관련 조각이 하나도 없으면 OpenAI 호출 없이 끝 (비용 절약)
        return {"answer": NOT_FOUND, "sources": []}

    context = "\n\n".join(f"({d.metadata['source']}) {d.page_content}" for d in docs)
    reply = get_llm().invoke(
        PROMPT.format(
            not_found=NOT_FOUND,
            history=format_history(state["history"]),
            context=context,
            question=state["question"],
        )
    )
    answer = reply.content.strip()

    # 모델도 못 찾았다고 답했다면 출처는 보여 주지 않아요
    if NOT_FOUND in answer:
        return {"answer": NOT_FOUND, "sources": []}

    # 출처는 가장 가까운 조각과 비슷하게 가까운 것만 (엉뚱한 파일이 따라 붙지 않게)
    best = min(d.metadata.get("distance", 0) for d in docs)
    close = [d for d in docs if d.metadata.get("distance", 0) <= best + SOURCE_MARGIN]

    # 같은 파일은 한 번만, 미리보기는 그 파일에서 가장 가까운 조각의 앞부분
    sources, seen = [], set()
    for d in close:
        name = d.metadata["source"]
        if name not in seen:
            seen.add(name)
            preview = d.metadata.get("line", d.page_content)
            sources.append({"file": name, "preview": " ".join(preview.split())[:70]})
    return {"answer": answer, "sources": sources}


def build_graph():
    """순서도: START → retrieve →(관련 없음 & 첫 시도) rewrite → retrieve (다시, 1번만) … → generate → END."""
    builder = StateGraph(State)
    builder.add_node("retrieve", retrieve)
    builder.add_node("rewrite", rewrite)
    builder.add_node("generate", generate)
    builder.add_edge(START, "retrieve")
    builder.add_conditional_edges(
        "retrieve", route_after_retrieve, {"rewrite": "rewrite", "generate": "generate"}
    )
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("generate", END)
    return builder.compile()


graph = build_graph()


def ask_stream(question: str, history: list | None = None) -> Iterator[tuple]:
    """질문 하나를 그래프에 넣고 진행 상황을 알려 줘요.

    ("step", "지금 하는 일") 을 여러 번, 마지막에 ("done", {answer, sources, rewritten}) 를 돌려줘요.
    오류가 나면 키가 새지 않게 종류만 로그로 남기고, 쉬운 한국어 답을 돌려줘요.
    """
    state = {
        "question": question, "history": history or [], "search_query": "", "retries": 0,
        "docs": [], "answer": "", "sources": [],
    }
    yield ("step", "문서에서 관련 내용을 찾는 중")
    try:
        for mode, data in graph.stream(state, stream_mode=["updates", "messages"]):
            if mode == "messages":
                # 답을 쓰는 노드(generate)가 만드는 글자를 바로바로 화면에 넘겨요
                chunk, meta = data
                if meta.get("langgraph_node") == "generate" and chunk.content:
                    yield ("token", chunk.content)
                continue
            for node, update in data.items():
                state.update(update)
                if node == "retrieve":
                    if route_after_retrieve(state) == "rewrite":
                        yield ("step", "찾은 내용이 부족해서 질문을 바꾸는 중")
                    else:
                        yield ("step", "답을 정리하는 중")
                elif node == "rewrite":
                    yield ("step", "바꾼 질문으로 다시 찾는 중")
        yield ("done", {
            "answer": state["answer"],
            "sources": state["sources"],
            "rewritten": state["search_query"] if state["retries"] else "",
        })
    except Exception as e:
        # 오류 메시지에 키가 섞일 수 있어서 종류와 상태 코드만 로그로 남겨요
        print("답변 실패:", type(e).__name__, getattr(e, "status_code", ""), file=sys.stderr)
        yield ("done", {"answer": ERROR_MESSAGE, "sources": [], "rewritten": "", "error": True})


def ask(question: str, history: list | None = None) -> dict:
    """진행 상황 없이 결과({answer, sources, rewritten})만 필요할 때 써요."""
    result = {}
    for kind, value in ask_stream(question, history):
        if kind == "done":
            result = value
    return result


if __name__ == "__main__":
    # 터미널에서 시험: python graph.py "질문"
    if len(sys.argv) > 1:
        out = ask(" ".join(sys.argv[1:]))
        print(out["answer"])
        for s in out["sources"]:
            print(f"  출처: {s['file']} — {s['preview']}")
        if out.get("rewritten"):
            print(f"  (질문을 바꿔 다시 찾았어요: {out['rewritten']})")
    else:
        print(build_graph().get_graph().draw_mermaid())  # 질문이 없으면 흐름 그림(mermaid)만 출력
