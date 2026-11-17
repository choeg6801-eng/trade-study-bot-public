"""문서 넣기 스크립트: data/ 의 문서(.md · .txt · .pdf)를 조각내서 벡터 저장소(chroma_db/)에 저장해요.

실행: python ingest.py
- 이미 저장된 조각은 다시 임베딩하지 않아요 (OpenAI 비용 절약).
- 문서를 고치면 바뀐 조각만 새로 저장하고, 사라진 조각은 지워요.
"""
import hashlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 폴더 위치와 조각 설정
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION = "trade_notes"
SUFFIXES = (".md", ".txt", ".pdf")
LINE_CHUNK_SIZE = 200     # 노트(항목 목록)에서 한 줄이 이보다 길 때만 글자 수로 다시 잘라요
LINE_OVERLAP = 30
TEXT_CHUNK_SIZE = 500     # 줄글 문서(PDF · 긴 글)는 이 크기로 잘라요
TEXT_OVERLAP = 80         # 앞뒤 조각이 겹치는 글자 수 (문장이 끊겨도 뜻이 이어지게)


def read_file(path: Path) -> str:
    """파일 하나를 글자로 읽어요. PDF 는 쪽마다 글자를 뽑아 이어 붙이고, 글자 인코딩은 여러 가지를 시도해요."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # PDF 를 쓸 때만 불러와요
        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):  # 윈도우 한글 메모장 파일(cp949)도 읽어요
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("글자 인코딩을 알 수 없어요")


def load_documents(skipped=None):
    """data/ 폴더의 문서를 읽어서 (파일 이름이 담긴) 문서 목록으로 돌려줘요.

    읽을 수 없는 파일(깨진 PDF 등)은 앱 전체가 멈추지 않게 건너뛰고,
    skipped 목록을 넘기면 건너뛴 파일 이름을 거기에 담아 줘요.
    """
    docs = []
    for path in sorted(DATA_DIR.iterdir()):
        if path.suffix.lower() not in SUFFIXES:
            continue
        try:
            text = read_file(path).strip()
        except Exception as e:
            print("파일을 읽지 못했어요:", path.name, type(e).__name__, file=sys.stderr)
            if skipped is not None:
                skipped.append(path.name)
            continue
        if text:
            # source 에 파일 이름을 적어 두면 나중에 '출처'로 보여 줄 수 있어요
            docs.append(Document(page_content=text, metadata={"source": path.name}))
        elif skipped is not None:
            skipped.append(path.name)  # 글자가 하나도 없는 파일(스캔 PDF 등)
    return docs


def is_note_style(lines):
    """'- 용어: 설명' 처럼 한 줄이 한 항목인 노트인지 알아봐요 (줄의 절반 이상이 - 로 시작하면 노트)."""
    items = [ln for ln in lines if ln.startswith("- ")]
    return len(items) * 2 >= len(lines) - sum(ln.startswith("#") for ln in lines)


def split_documents(docs):
    """문서를 조각으로 자르고, 조각마다 고유 번호(id)와 순서를 붙여요.

    - 노트: '한 줄(항목) = 한 조각' → 용어마다 따로 찾을 수 있어요.
    - 줄글(PDF · 긴 글): 500자 단위로 자르고 앞뒤를 조금 겹쳐요.
    제목(# 줄 또는 파일 이름)은 각 조각 앞에 붙여서 '어느 문서의 내용인지' 뜻이 같이 임베딩되게 해요.
    """
    line_splitter = RecursiveCharacterTextSplitter(chunk_size=LINE_CHUNK_SIZE, chunk_overlap=LINE_OVERLAP)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=TEXT_CHUNK_SIZE, chunk_overlap=TEXT_OVERLAP)
    chunks = []
    for doc in docs:
        source = doc.metadata["source"]
        lines = [ln.strip() for ln in doc.page_content.splitlines() if ln.strip()]
        if lines[0].startswith("#"):
            title, lines = lines[0].lstrip("# ").strip(), lines[1:]
        else:
            title = Path(source).stem
        if is_note_style(lines):
            pieces = [p for ln in lines for p in line_splitter.split_text(ln.lstrip("- ").strip())]
        else:
            pieces = text_splitter.split_text("\n".join(lines))
        for piece in pieces:
            # line 에는 제목 없는 원래 내용을 남겨 둬요 (출처 미리보기용)
            chunks.append(Document(
                page_content=f"[{title}] {piece}",
                metadata={"source": source, "line": piece},
            ))
    counter, ids, seen = {}, [], {}
    for chunk in chunks:
        source = chunk.metadata["source"]
        counter[source] = counter.get(source, 0) + 1
        chunk.metadata["chunk"] = counter[source]  # 문서 안에서 몇 번째 조각인지
        # 파일 이름 + 내용이 같으면 같은 id → 이미 저장했는지 알아볼 수 있어요
        base = hashlib.sha1((source + chunk.page_content).encode("utf-8")).hexdigest()
        seen[base] = seen.get(base, 0) + 1
        # 같은 문서에 똑같은 줄이 또 나오면 번호를 붙여서 id 가 겹치지 않게 해요
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return chunks, ids


def count_chunks(skipped=None):
    """파일마다 조각이 몇 개인지 세요. (OpenAI 를 부르지 않아서 비용이 없어요) 예: {"a.md": 5}"""
    chunks, _ = split_documents(load_documents(skipped))
    counts = {}
    for c in chunks:
        counts[c.metadata["source"]] = counts.get(c.metadata["source"], 0) + 1
    return counts


def run_ingest():
    """문서를 읽고 → 자르고 → 새 조각만 임베딩해서 저장해요. 결과 {docs, chunks, new, removed} 를 돌려줘요.

    문제가 있으면 쉬운 한국어 메시지가 담긴 RuntimeError 를 내요.
    """
    load_dotenv()  # .env 에서 설정 읽기 (키와 모델 이름을 코드에 직접 쓰지 않아요)
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_EMBED_MODEL"):
        raise RuntimeError("OPENAI_API_KEY 또는 OPENAI_EMBED_MODEL 이 .env 에 없어요. 값을 채운 뒤 다시 실행해 주세요.")

    docs = load_documents()
    if not docs:
        raise RuntimeError("data/ 폴더에 문서(.md · .txt · .pdf)가 없어요. 문서를 넣고 다시 실행해 주세요.")
    chunks, ids = split_documents(docs)

    try:
        store = Chroma(
            collection_name=COLLECTION,
            embedding_function=OpenAIEmbeddings(model=os.getenv("OPENAI_EMBED_MODEL"), max_retries=0),
            persist_directory=str(DB_DIR),
        )
        saved = set(store.get()["ids"])  # 이미 저장된 조각 번호들

        # 사라진 조각(문서에서 지운 내용)은 저장소에서도 지워요
        old = list(saved - set(ids))
        if old:
            store.delete(ids=old)

        # 새 조각만 한 번에 임베딩 (이미 있는 조각은 비용이 들지 않아요)
        new = [(c, i) for c, i in zip(chunks, ids) if i not in saved]
        for start in range(0, len(new), 100):  # 큰 문서는 100조각씩 나눠 저장 (한 번에 너무 많이 보내지 않게)
            part = new[start:start + 100]
            store.add_documents([c for c, _ in part], ids=[i for _, i in part])
    except Exception as e:
        # 오류 메시지에 키가 섞일 수 있어서 종류와 상태 코드만 로그로 남겨요
        print("저장 실패:", type(e).__name__, getattr(e, "status_code", ""), file=sys.stderr)
        raise RuntimeError("문서를 저장하지 못했어요. 키 · 크레딧 · 인터넷 연결을 확인하고 다시 해 주세요.") from None

    return {"docs": len(docs), "chunks": len(chunks), "new": len(new), "removed": len(old)}


def main():
    """터미널에서 실행할 때: 결과를 한 줄로 알려줘요."""
    try:
        r = run_ingest()
    except RuntimeError as e:
        print(e)
        sys.exit(1)
    print(f"문서 {r['docs']}개 → 조각 {r['chunks']}개 저장 (새로 임베딩한 조각 {r['new']}개)")


if __name__ == "__main__":
    main()
