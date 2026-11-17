# 개인 챗봇 과제 — 프로젝트 안내 (Claude 가 매번 읽어요)

## 목표
data/ 문서로 답하는 RAG 챗봇 웹앱. 자세한 요구사항: @과제_안내.md
디자인 규칙: @DESIGN.md
LangChain · LangGraph 사용법 메모: @조사노트.md

## 기술
- Python 3.11 이상 · 가상환경 `.venv`
- 웹: Streamlit · RAG/부품: LangChain · 흐름: LangGraph
- 모델: OpenAI API — 대화 `OPENAI_MODEL`(기본 gpt-6-luna) · 임베딩 `OPENAI_EMBED_MODEL`(기본 text-embedding-3-small)
- 모델 이름 · 키는 .env 에서 읽기 (코드에 직접 쓰지 않기) · 사용법은 최신 공식 문서 확인

## 작업 방식
- 큰 변경 전에는 계획부터 보여 주기
- 한 번에 파일 하나씩, 바꾼 내용 3줄 요약
- 비전공자용 한국어 주석

## 내가 추가한 규칙 (이유: 시험하다 겪은 문제)
- 검색 거리 기준(`MAX_DISTANCE`)이나 조각 크기를 바꾸면, 시험 질문 3개(문서에 있는 것 2 · 없는 것 1)로 다시 확인하기
  — 조각 크기를 바꿨더니 같은 질문이 답을 찾았다가 못 찾았다 했고, 관련 있는 질문과 없는 질문의 거리 간격이 좁았어요
- `data/` 문서를 바꾸면 `python ingest.py` 를 다시 실행하기 (바뀐 조각만 임베딩돼서 비용은 거의 없어요)

## 실행
- 문서 넣기: `python ingest.py`
- 앱 실행: `streamlit run app.py`
