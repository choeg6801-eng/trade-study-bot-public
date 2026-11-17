"""임베딩 점검 스크립트.

질문 문장 1개와 비교 문장 5개를 OpenAI 임베딩으로 '한 번에' 바꾸고,
질문과 각 문장의 코사인 유사도를 큰 순서로 표로 보여 줍니다.
(키와 숫자 목록은 출력하지 않습니다.)
"""
import math
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# .env 에서 설정 읽기 (코드에 키나 모델 이름을 직접 쓰지 않아요)
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_EMBED_MODEL")
if not api_key or not model:
    print("OPENAI_API_KEY 또는 OPENAI_EMBED_MODEL 이 .env 에 없어요.")
    print(".env.example 을 .env 로 복사한 뒤, 값을 직접 채워 주세요.")
    sys.exit(1)

QUESTION = "배에 짐을 실은 증거 서류가 뭐야?"
SENTENCES = [
    "선하증권(B/L)은 화물을 선적했다는 증서다",
    "FOB 는 본선에 실으면 위험이 넘어간다",
    "오늘 점심은 김치찌개를 먹었다",
    "인보이스는 거래 금액을 적은 상업 송장이다",
    "고양이는 낮잠을 많이 잔다",
]


def cosine(a, b):
    """두 숫자 목록이 얼마나 같은 방향인지(−1~1). 1에 가까울수록 비슷해요."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


try:
    # 질문 + 5문장을 한 번의 호출로 임베딩 (여러 번 부르지 않기)
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model=model, input=[QUESTION] + SENTENCES)
except Exception as e:
    # 오류 메시지에 키 일부가 섞일 수 있어서, 종류와 상태 코드만 보여 줘요
    print("임베딩 호출 실패:", type(e).__name__, getattr(e, "status_code", ""))
    sys.exit(1)

vectors = [item.embedding for item in resp.data]
question_vec, sentence_vecs = vectors[0], vectors[1:]

rows = sorted(
    ((cosine(question_vec, v), s) for v, s in zip(sentence_vecs, SENTENCES)),
    reverse=True,
)

print(f"질문: {QUESTION}")
print(f"임베딩 모델: {model}\n")
print("| 순위 | 유사도 | 문장 |")
print("|---|---|---|")
for rank, (score, sentence) in enumerate(rows, start=1):
    print(f"| {rank} | {score:.4f} | {sentence} |")
