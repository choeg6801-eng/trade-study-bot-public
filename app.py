"""무역 공부 도우미 — Streamlit 채팅 화면.

실행: streamlit run app.py
- 질문하기: graph.py(LangGraph)가 data/ 문서에서 근거를 찾아 답하고, 답 아래에 출처를 보여 줘요.
- 카드로 외우기: 용어 노트의 "용어: 뜻" 줄을 카드로 만들어 외워요 (OpenAI 를 부르지 않아서 무료예요).
"""
import datetime
import html
import random
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import graph
import ingest

NOT_FOUND = graph.NOT_FOUND
INTERRUPTED = "답을 만들다가 멈췄어요. 한 번 더 물어봐 주세요."
DATA_DIR = ingest.DATA_DIR
STARTER_FILES = {"01_가상_회사소개.md", "02_무역용어_노트.md", "03_내_학습메모.md"}  # 처음부터 있던 연습 문서
MAX_UPLOAD_MB = 2
MODES = ["질문하기", "카드로 외우기"]
EXAMPLES = [  # (아이콘, 질문)
    (":material/compare_arrows:", "FOB 와 CIF 는 뭐가 달라?"),
    (":material/description:", "선하증권(B/L)이 뭐야?"),
    (":material/schedule:", "ETD 랑 ETA 차이가 뭐예요?"),
    (":material/storefront:", "한빛무역은 샘플을 몇 개까지 무료로 줘?"),
]

st.set_page_config(
    page_title="무역 공부 도우미", page_icon="📘", layout="centered", initial_sidebar_state="auto"  # auto: 컴퓨터에선 열리고 휴대폰에선 접혀서 본문을 가리지 않아요
)

# DESIGN.md 의 색 · 글꼴 · 둥근 모서리 규칙 (글꼴은 Pretendard 하나, 없으면 기본 한글 글꼴)
st.markdown(
    """
<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");
:root {
    --primary: #2B59C3; --primary-deep: #1F44A0; --primary-soft: #E8EEFB; --surface: #F5F7FB; --card: #FFFFFF;
    --text: #1B1F24; --muted: #6B7480; --border: #E1E6EF; --chip: #EEF1F6; --accent: #F2B33D; --radius: 12px;
}
html, body, .stApp, .stApp :not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {
    font-family: "Pretendard", "Malgun Gothic", sans-serif !important;
}
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: "Material Symbols Rounded" !important; }

/* 불필요한 기본 화면 요소는 숨기되, 사이드바 여닫기 버튼은 꼭 남겨요 */
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
[data-testid="stHeaderActionElements"], h1 a { display: none !important; }
[data-testid="stHeader"] { background: rgba(245,247,251,0.88); backdrop-filter: blur(6px); }  /* 스크롤할 때 글자가 위 버튼과 겹치지 않게 */
.block-container { max-width: 760px; padding-top: 3.4rem; padding-bottom: 0; min-height: 100vh; display: flex; flex-direction: column; }
.block-container > [data-testid="stVerticalBlock"] { flex: 1; }
/* 입력창: 가운데 열 안에서 화면 아래에 붙어 있어요 */
[data-testid="stLayoutWrapper"]:has(> .st-key-chatbar) { position: sticky; bottom: 0; z-index: 50; margin-top: auto; padding: 0.8rem 0 1.1rem; background: linear-gradient(to top, #F5F7FB 78%, rgba(245,247,251,0)); }
/* 방안지(공책) 같은 점무늬 배경 */
.stApp { background-color: var(--surface); background-image: radial-gradient(#D5DDEC 1px, transparent 1px); background-size: 22px 22px; color: var(--text); }
.stApp p, .stApp li { font-size: 1rem; line-height: 1.7; }

/* 머리말(히어로) */
.hero { position: relative; overflow: hidden; background: var(--primary); color: #fff; border-radius: 16px; padding: 1.7rem 1.8rem 1.5rem; margin-bottom: 1.1rem; }
.hero .eyebrow { font-size: 0.72rem; letter-spacing: 0.14em; font-weight: 600; opacity: 0.75; }
.hero h1 { font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; margin: 0.35rem 0 0.4rem; color: #fff; padding: 0; line-height: 1.2; }
.hero p { margin: 0; color: rgba(255,255,255,0.86); font-size: 0.95rem; max-width: 26rem; line-height: 1.6; }
.hero .stats { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1.1rem; }
.hero .stat { background: rgba(255,255,255,0.14); border-radius: 999px; padding: 0.22rem 0.75rem; font-size: 0.78rem; font-weight: 500; }
.hero svg.hero-art { position: absolute; right: -6px; bottom: -4px; width: 350px; max-width: 50%; }
@media (max-width: 640px) { .hero svg.hero-art { display: none; } .hero h1 { font-size: 1.65rem; } }

/* 모드 전환(질문하기 / 카드로 외우기) */
[data-testid="stSegmentedControl"] { margin-bottom: 0.6rem; }
[data-testid="stSegmentedControl"] button { font-weight: 600; font-size: 0.92rem; }

/* 첫 화면 */
.sec-label { font-size: 0.8rem; font-weight: 600; color: var(--muted); letter-spacing: 0.04em; margin: 1.1rem 0 0.5rem; }
.today { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem 1.2rem; }
.today .tag { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; font-weight: 600; color: var(--muted); }
.today .tag::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.today .term { font-size: 1.15rem; font-weight: 700; margin: 0.35rem 0 0.15rem; }
.today .mean { color: #3B424C; font-size: 0.95rem; line-height: 1.6; }

/* 버튼 */
.stElementContainer:has(.stButton), .stButton, [data-testid="stColumn"] .stButton { width: 100% !important; }
.st-key-today_ask, .st-key-ask_more { max-width: 16rem; margin-top: 0.5rem; }
.stElementContainer:has(.stDownloadButton), .stDownloadButton { width: 100% !important; }
.stDownloadButton > button { width: 100%; justify-content: flex-start; background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); }
[data-testid="stProgressBarTrack"] { background: var(--border); height: 6px; border-radius: 999px; overflow: hidden; }
[data-testid="stProgressBarTrack"] > div { background: var(--primary); border-radius: 999px; }
[data-testid="stProgress"] p { font-size: 0.82rem; color: var(--muted); }
.stButton > button, [data-testid="stBaseButton-secondary"] {
    width: 100%; text-align: left; justify-content: flex-start; background: var(--card);
    border: 1px solid var(--border); border-radius: var(--radius); color: var(--text);
    padding: 0.75rem 1rem; font-size: 0.95rem; font-weight: 500; transition: border-color .15s, background .15s, transform .1s;
}
.stButton > button:hover { border-color: var(--primary); background: var(--primary-soft); color: var(--text); transform: translateY(-1px); }
.stButton > button:focus:not(:active) { border-color: var(--primary); color: var(--text); }
.stButton > button [data-testid="stIconMaterial"] { color: var(--primary); }
[data-testid="stFormSubmitButton"] > button, .stButton > button[kind="primary"] { background: var(--primary); color: #fff; border-color: var(--primary); justify-content: center; text-align: center; }
[data-testid="stFormSubmitButton"] > button:hover, .stButton > button[kind="primary"]:hover { background: var(--primary-deep); color: #fff; }

/* 대화 */
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none; }
[data-testid="stChatMessage"] { background: transparent; padding: 0.35rem 0; gap: 0; }
[data-testid="stChatMessage"]:has(.user-bubble) [data-testid="stChatMessageContent"] { display: flex; justify-content: flex-end; }
.user-bubble {
    background: var(--primary); color: #FFFFFF; border-radius: var(--radius) var(--radius) 4px var(--radius);
    padding: 0.65rem 1rem; max-width: 85%; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
    width: fit-content; margin-left: auto; box-shadow: 0 1px 2px rgba(31,68,160,0.18);
}
[data-testid="stChatMessage"]:not(:has(.user-bubble)) [data-testid="stChatMessageContent"] {
    background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--primary);
    border-radius: 4px var(--radius) var(--radius) 4px; padding: 1rem 3.6rem 1.5rem 1.2rem; width: 100%;  /* 오른쪽 여백 = 선하 자리 */
    box-shadow: 0 1px 3px rgba(27,31,36,0.04);
}
[data-testid="stChatMessageContent"] p { margin: 0 0 0.4rem; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0; }
.notfound { color: var(--muted); }
.hint { color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem; }

/* 출처: 답변 아래 작은 회색 글씨 */
.sources { color: var(--muted); font-size: 0.8rem; line-height: 1.5; margin-top: 0.9rem; padding-top: 0.7rem; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 0.35rem; }
.src { display: flex; align-items: baseline; gap: 0.45rem; }
.src svg { flex: none; width: 12px; height: 12px; transform: translateY(1px); stroke: var(--muted); }
.src b { font-weight: 600; color: #4B5563; background: var(--chip); border-radius: 6px; padding: 0.05rem 0.4rem; }
.sources .rewritten { margin-top: 0.1rem; }

/* 생각 중 표시 */
.thinking { color: var(--muted); font-size: 0.92rem; display: flex; align-items: center; gap: 0.7rem; }
.thinking .mascot { width: 52px; height: 57px; flex: none; margin: -0.3rem 0 -0.4rem; }

/* 답이 나왔을 때 카드 모서리에 잠깐 나타나는 선하 (기뻐서 폴짝 / 못 찾아서 갸웃) */
[data-testid="stChatMessageContent"] { position: relative; }
.stElementContainer:has(.react) { height: 0; margin-bottom: -1rem; }
.react { position: absolute; top: -6px; right: -3.2rem; width: 40px; height: 44px; pointer-events: none; }  /* 카드 오른쪽 여백(padding) 안쪽에 앉아요 */
.react .mascot { width: 100%; height: 100%; overflow: visible; }
.mascot .m-open { opacity: 0; }
.mascot .m-q { display: none; }  /* 물음표 글자는 갸웃할 때만 — 답변을 복사할 때 섞이지 않게 평소엔 아예 없애요 */
.mascot.puzzled .m-q { display: inline; }
.mascot { user-select: none; }
.mascot.happy .m-smile, .mascot.puzzled .m-smile { opacity: 0; }
.mascot.happy .m-open { opacity: 1; }
.mascot.happy .m-body { animation: jump .8s ease-out 1; }
.mascot.puzzled .m-body { animation: shake .9s ease-in-out 1; }
.mascot.puzzled .m-q { animation: pop .5s ease-out 1; transform-box: fill-box; transform-origin: center; }
.mascot.happy .m-eye { animation: none; transform: scaleY(.55); }
@keyframes jump { 0% { transform: translateY(0); } 30% { transform: translateY(-14px); } 60% { transform: translateY(0); } 80% { transform: translateY(-5px); } 100% { transform: translateY(0); } }
@keyframes shake { 0%, 100% { transform: rotate(0); } 20% { transform: rotate(-9deg); } 45% { transform: rotate(8deg); } 70% { transform: rotate(-5deg); } }
@keyframes pop { from { transform: scale(0); } to { transform: scale(1); } }

/* 마스코트 움직임 — 평소엔 가만히 숨 쉬듯 · 생각할 땐 돋보기를 들고 갸웃 */
.mascot .m-body { transform-box: fill-box; transform-origin: 50% 100%; }
.mascot .m-eye { transform-box: fill-box; transform-origin: center; animation: blink 4.4s infinite; }
.mascot .m-arm { transform-box: fill-box; transform-origin: 0% 50%; }
.mascot .m-lens { opacity: 0; transform-box: fill-box; transform-origin: 90% 90%; }
.mascot.idle .m-body { animation: bob 2.8s ease-in-out infinite; }
.mascot.idle .m-arm { animation: wave 2.2s ease-in-out infinite; }
.mascot.thinking .m-body { animation: tilt 1.3s ease-in-out infinite; }
.mascot.thinking .m-lens { opacity: 1; animation: scan 1.3s ease-in-out infinite; }
.mascot.thinking .m-eye { animation: look 1.3s ease-in-out infinite; }
.hero-art .sea-back { animation: drift 5s ease-in-out infinite alternate; }
.hero-art .sea-front { animation: drift 3.6s ease-in-out infinite alternate-reverse; }
@keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
@keyframes wave { 0%, 100% { transform: rotate(-8deg); } 50% { transform: rotate(-38deg); } }
@keyframes blink { 0%, 93%, 100% { transform: scaleY(1); } 96% { transform: scaleY(.1); } }
@keyframes tilt { 0%, 100% { transform: rotate(-5deg); } 50% { transform: rotate(5deg); } }
@keyframes scan { 0%, 100% { transform: rotate(-14deg) translateX(-2px); } 50% { transform: rotate(14deg) translateX(2px); } }
@keyframes look { 0%, 100% { transform: translateX(-2px); } 50% { transform: translateX(2px); } }
@keyframes drift { from { transform: translateX(0); } to { transform: translateX(-24px); } }
@media (prefers-reduced-motion: reduce) { .mascot *, .hero-art * { animation: none !important; } }
.thinking .dots::after { content: ""; animation: dots 1.2s steps(4, end) infinite; }
@keyframes dots { 0% { content: ""; } 25% { content: "."; } 50% { content: ".."; } 75% { content: "..."; } }

/* 외우기 카드 */
.flash { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 2.2rem 1.6rem; text-align: center; min-height: 11rem; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 2px 10px rgba(27,31,36,0.05); }
.flash .no { font-size: 0.78rem; color: var(--muted); font-weight: 600; letter-spacing: 0.04em; }
.flash .term { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; color: var(--primary); margin: 0.5rem 0; }
.flash .mean { font-size: 1.05rem; line-height: 1.7; color: var(--text); margin-top: 0.4rem; border-top: 1px dashed var(--border); padding-top: 0.9rem; }
.flash .ask { color: var(--muted); font-size: 0.9rem; }
.done { text-align: center; padding: 1.8rem 1rem; background: var(--card); border: 1px solid var(--border); border-radius: 16px; margin-bottom: 0.4rem; }
.done .big { font-size: 1.6rem; font-weight: 800; color: var(--primary); }

/* 사이드바 안내 글씨 · 업로드 상자 (기본 영어 안내는 숨기고 우리 안내만 보여요) */
[data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] { font-size: 0.8rem !important; line-height: 1.55; color: var(--muted); }
[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }
[data-testid="stFileUploaderDropzone"] { padding: 0.6rem; border-radius: var(--radius); }

/* 스크롤 보정용 보이지 않는 조각은 자리를 차지하지 않게 해요 */
.stElementContainer:has(iframe) { height: 0; margin-bottom: -1rem; overflow: hidden; }

/* 입력창 */
[data-testid="stChatInput"] { border-radius: var(--radius); }
[data-testid="stChatInput"] textarea { font-size: 0.97rem; }

/* 사이드바 */
[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--border); }
.side-title { font-size: 0.78rem; font-weight: 600; color: var(--muted); letter-spacing: 0.04em; margin: 0.2rem 0 0.5rem; }
.file-row { display: flex; justify-content: space-between; gap: 0.6rem; font-size: 0.88rem; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }
.file-row span:last-child { color: var(--muted); white-space: nowrap; }
.side-note { color: var(--muted); font-size: 0.8rem; line-height: 1.55; margin: 0.7rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

# 마스코트 "선하": 컨테이너를 닮은 선장 캐릭터 (SVG 도형 + CSS 움직임이라 가볍고 확대해도 선명해요)
# 이름은 선하증권(B/L)의 '선하(船荷, 배에 실은 짐)'에서 따왔어요. 상태: idle · thinking · happy · puzzled
MASCOT_PARTS = """
<g class="m-body">
  <ellipse cx="50" cy="104" rx="26" ry="4" fill="#1F44A0" opacity=".16"/>
  <rect x="33" y="88" width="12" height="13" rx="5" fill="#17357F"/>
  <rect x="55" y="88" width="12" height="13" rx="5" fill="#17357F"/>
  <rect x="22" y="34" width="56" height="55" rx="15" fill="#fff" stroke="#C9D6F3" stroke-width="1.5"/>
  <path d="M30 46V78M70 46V78" stroke="#E3EBFB" stroke-width="3" stroke-linecap="round"/>
  <rect x="11" y="60" width="13" height="9" rx="4.5" fill="#fff" stroke="#C9D6F3" stroke-width="1.5"/>
  <g class="m-arm"><rect x="76" y="55" width="15" height="9" rx="4.5" fill="#fff" stroke="#C9D6F3" stroke-width="1.5"/></g>
  <g class="m-lens"><circle cx="90" cy="44" r="8" fill="#E8EEFB" fill-opacity=".8" stroke="#2B59C3" stroke-width="3"/><path d="M84 51L77 60" stroke="#2B59C3" stroke-width="3.5" stroke-linecap="round"/></g>
  <ellipse class="m-eye" cx="40" cy="58" rx="3.6" ry="4.8" fill="#1B1F24"/>
  <ellipse class="m-eye" cx="60" cy="58" rx="3.6" ry="4.8" fill="#1B1F24"/>
  <circle cx="41.3" cy="56.4" r="1.2" fill="#fff"/><circle cx="61.3" cy="56.4" r="1.2" fill="#fff"/>
  <circle cx="31" cy="67" r="4.2" fill="#F2B33D" opacity=".5"/><circle cx="69" cy="67" r="4.2" fill="#F2B33D" opacity=".5"/>
  <path class="m-smile" d="M44 68Q50 74.5 56 68" stroke="#1B1F24" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path class="m-open" d="M43.5 66.5Q50 80 56.5 66.5Z" fill="#1B1F24"/>
  <text class="m-q" x="76" y="30" font-size="26" font-weight="800" fill="#2B59C3">?</text>
  <path d="M28 40Q50 12 72 40Z" fill="#1F44A0"/>
  <rect x="24" y="37" width="52" height="7" rx="3.5" fill="#17357F"/>
  <circle cx="50" cy="28" r="3.6" fill="#F2B33D"/>
</g>
"""


def mascot_small(state="thinking"):
    """작은 마스코트 그림 한 장(state: idle · thinking). 답을 찾는 동안 돋보기를 들고 갸웃거려요."""
    return f'<svg class="mascot {state}" viewBox="0 0 100 110" aria-hidden="true">{MASCOT_PARTS}</svg>'


HERO_SHIP = f"""
<svg class="hero-art" viewBox="0 0 300 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <g class="sea-back"><path d="M-40 104 Q -15 94 10 104 T 60 104 T 110 104 T 160 104 T 210 104 T 260 104 T 310 104 T 360 104 V120 H-40Z" fill="#fff" opacity=".14"/></g>
  <rect x="58" y="58" width="26" height="22" rx="2" fill="#fff" opacity=".92"/>
  <rect x="86" y="58" width="26" height="22" rx="2" fill="#BFD0F5"/>
  <rect x="114" y="58" width="26" height="22" rx="2" fill="#8FAEEE"/>
  <rect x="72" y="35" width="26" height="22" rx="2" fill="#8FAEEE"/>
  <rect x="100" y="35" width="26" height="22" rx="2" fill="#fff" opacity=".92"/>
  <path d="M40 80 H262 L242 102 H62 Z" fill="#fff"/>
  <g transform="translate(150 0) scale(.8)" class="mascot idle">{MASCOT_PARTS}</g>
  <g class="sea-front"><path d="M-40 110 Q -10 100 20 110 T 80 110 T 140 110 T 200 110 T 260 110 T 320 110 T 380 110 V120 H-40Z" fill="#fff" opacity=".22"/></g>
</svg>
"""
DOC_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>'
)


SCROLL_BOTTOM_JS = """
<script>
  // 질문을 보낸 뒤 답이 나오는 동안(최대 약 12초) 새 내용이 보이게 아래로 따라가요.
  // 사용자가 직접 위로 스크롤하면(휠 · 터치) 바로 멈춰요.
  const doc = window.parent.document;
  const box = doc.querySelector('[data-testid="stMain"]');
  let follow = true, tries = 0;
  const stop = () => { follow = false; };
  doc.addEventListener('wheel', stop, { passive: true });
  doc.addEventListener('touchmove', stop, { passive: true });
  const timer = setInterval(() => {
    if (follow && box) box.scrollTop = box.scrollHeight;
    if (!follow || ++tries > 60) {
      clearInterval(timer);
      doc.removeEventListener('wheel', stop);
      doc.removeEventListener('touchmove', stop);
    }
  }, 200);
</script>
"""


def esc(text):
    """화면에 넣을 글자에서 HTML 기호를 안전하게 바꿔요."""
    return html.escape(str(text))


@st.cache_data(show_spinner=False)
def scan_data(signature):
    """자료 폴더를 한 번 훑어서 파일별 항목 수와 외울 용어 카드를 만들어요. (파일이 바뀔 때만 다시 계산)

    signature 는 파일 이름 · 크기 · 수정 시각 묶음이라, 문서가 바뀌면 자동으로 새로 읽어요.
    """
    skipped = []  # 읽지 못한 파일 (깨진 PDF 등) — 앱이 멈추지 않고 건너뛰어요
    docs = ingest.load_documents(skipped)
    chunks, _ = ingest.split_documents(docs)
    counts = {}
    for c in chunks:
        counts[c.metadata["source"]] = counts.get(c.metadata["source"], 0) + 1

    terms = []  # [(용어, 뜻, 파일 이름)] — 제목이나 파일 이름에 '용어'가 든 노트의 "- 용어: 뜻" 줄
    for doc in docs:
        first = doc.page_content.strip().splitlines()[0]
        if "용어" not in doc.metadata["source"] and "용어" not in first:
            continue
        for line in doc.page_content.splitlines():
            m = re.match(r"^-\s*(.+?):\s*(.+)$", line.strip())
            if m:
                terms.append((m.group(1).strip(), m.group(2).strip(), doc.metadata["source"]))
    return counts, terms, skipped


def data_signature():
    """data/ 폴더의 파일 상태를 한 줄로 요약해요 (scan_data 가 다시 읽을지 정하는 열쇠)."""
    if not DATA_DIR.exists():
        return ()
    return tuple(
        (p.name, p.stat().st_size, int(p.stat().st_mtime))
        for p in sorted(DATA_DIR.iterdir())
        if p.suffix.lower() in ingest.SUFFIXES
    )


def render_sources(sources, rewritten=""):
    """답변 아래에 작은 회색 글씨로 출처(파일 이름 + 미리보기)를 보여 줘요."""
    if not sources:
        return
    rows = "".join(
        f'<div class="src">{DOC_ICON}<span><b>{esc(s["file"])}</b> {esc(s["preview"])}</span></div>' for s in sources
    )
    note = f'<div class="rewritten">처음엔 못 찾아서 질문을 바꿔 다시 찾았어요 → {esc(rewritten)}</div>' if rewritten else ""
    st.markdown(f'<div class="sources">{rows}{note}</div>', unsafe_allow_html=True)


def render_answer(result, fresh=False):
    """도우미 답변 하나를 그려요. 못 찾았을 땐 다음에 해 볼 일을 같이 알려 줘요.

    fresh=True(방금 나온 답)이면 카드 모서리에 선하가 나타나요: 찾았으면 폴짝, 못 찾았으면 갸웃.
    """
    answer = result["answer"]
    if fresh and not result.get("error"):
        state = "puzzled" if answer == NOT_FOUND else "happy"
        st.markdown(f'<div class="react">{mascot_small(state)}</div>', unsafe_allow_html=True)
    if answer == NOT_FOUND:
        st.markdown(f'<div class="notfound">{NOT_FOUND}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="hint">다른 표현으로 물어보거나, 왼쪽 "자료 추가하기"로 노트를 더해 보세요.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(answer)
    render_sources(result.get("sources"), result.get("rewritten", ""))


def show_message(msg):
    """저장된 대화 한 줄을 그려요 (사용자는 오른쪽 파란 말풍선, 도우미는 왼쪽 카드)."""
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(f'<div class="user-bubble">{esc(msg["content"])}</div>', unsafe_allow_html=True)
        else:
            render_answer(msg)


def conversation_markdown(messages):
    """대화를 .md 파일로 저장할 글로 만들어요 (질문 · 답 · 출처)."""
    out = ["# 무역 공부 도우미 대화", ""]
    for m in messages:
        if m["role"] == "user":
            out += [f"## Q. {m['content']}", ""]
        else:
            out += [m["answer"], ""]
            for s in m.get("sources", []):
                out.append(f"- 출처: {s['file']} — {s['preview']}")
            out.append("")
    return "\n".join(out)


def safe_name(name):
    """올린 파일 이름에서 폴더 경로를 떼고, 같은 이름이 있으면 (2) 를 붙여요."""
    base = Path(name).name
    path = DATA_DIR / base
    n = 2
    while path.exists():
        path = DATA_DIR / f"{Path(base).stem} ({n}){Path(base).suffix}"
        n += 1
    return path


def prepare_documents():
    """문서를 저장소에 넣고(필요한 조각만 임베딩) 결과를 돌려줘요. 문제가 있으면 화면에 알려요."""
    try:
        with st.spinner("문서를 읽고 정리하는 중이에요..."):
            result = ingest.run_ingest()
        graph.get_store.cache_clear()  # 새 문서가 바로 검색되게 저장소를 다시 열어요
        return result
    except RuntimeError as e:
        st.error(str(e))
        return None


# 버튼 눌렀을 때 먼저 실행되는 함수들 (화면이 다시 그려지기 전에 상태를 바꿔요)
def ask_this(question):
    """예시 질문이나 '더 물어보기'를 눌렀을 때: 질문하기 화면으로 가서 그 질문을 보내요."""
    st.session_state.mode = MODES[0]
    st.session_state.pending = question


def card_action(kind):
    """카드 버튼 동작: show(뜻 보기) · known(알았어요) · again(헷갈려요) · restart(처음부터) · retry(헷갈린 것만)."""
    s = st.session_state
    if kind == "show":
        s.card_show = True
    elif kind in ("known", "again"):
        (s.card_known if kind == "known" else s.card_again).append(s.card_deck[s.card_pos])
        s.card_pos += 1
        s.card_show = False
    elif kind == "restart":
        s.card_deck = None
    elif kind == "retry":
        s.card_deck, s.card_pos, s.card_show = list(s.card_again), 0, False
        s.card_known, s.card_again = [], []


# ---------- 자료 읽기 ----------
counts, terms, unreadable = scan_data(data_signature())
today_term = terms[datetime.date.today().toordinal() % len(terms)] if terms else None

# ---------- 사이드바: 내 자료 ----------
with st.sidebar:
    st.markdown('<div class="side-title">내 자료</div>', unsafe_allow_html=True)
    if counts:
        rows = "".join(
            f'<div class="file-row"><span>{esc(name)}</span><span>{n}개 항목</span></div>'
            for name, n in counts.items()
        )
        st.markdown(rows, unsafe_allow_html=True)
    else:
        st.caption("data/ 폴더에 문서가 없어요.")
    if unreadable:
        st.warning("읽지 못해서 건너뛴 파일: " + ", ".join(unreadable) + " (글자가 없거나 깨진 파일이에요. 아래에서 지울 수 있어요)")
    st.markdown(
        '<div class="side-note">답변은 위 자료에서만 찾아요. 자료에 없으면 없다고 말해요.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("자료 추가하기"):
        with st.form("upload", clear_on_submit=True):
            upload = st.file_uploader("파일 선택", type=["md", "txt", "pdf"], label_visibility="collapsed")
            st.caption(f".md · .txt · .pdf · {MAX_UPLOAD_MB}MB 까지. 개인정보나 회사 문서는 넣지 마세요. 내용이 OpenAI 로 전송돼요.")
            if st.form_submit_button("추가"):
                if upload is None:
                    st.warning("파일을 먼저 골라 주세요.")
                elif upload.size > MAX_UPLOAD_MB * 1024 * 1024:
                    st.warning(f"{MAX_UPLOAD_MB}MB 보다 작은 파일만 올릴 수 있어요.")
                else:
                    path = safe_name(upload.name)
                    path.write_bytes(upload.getvalue())
                    try:  # 저장하기 전에 먼저 읽을 수 있는 파일인지 확인해요 (깨진 파일이 자료에 섞이지 않게)
                        readable = bool(ingest.read_file(path).strip())
                    except Exception:
                        readable = False
                    result = prepare_documents() if readable else None
                    if result and path.name in ingest.count_chunks():
                        st.session_state.flash = f"'{path.name}' 을(를) 추가했어요."
                        st.rerun()
                    else:
                        path.unlink(missing_ok=True)  # 글자를 읽지 못했거나 저장에 실패했으면 되돌려요
                        if result:
                            prepare_documents()
                        if not readable:
                            st.warning("파일에서 글자를 읽지 못했어요. 글자가 들어 있는(스캔 이미지가 아닌) 파일인지 확인해 주세요.")
        extra = [n for n in list(counts) + unreadable if n not in STARTER_FILES]
        if extra:
            target = st.selectbox("추가한 자료 지우기", ["선택 안 함"] + extra)
            if target != "선택 안 함" and st.button("삭제"):
                (DATA_DIR / target).unlink(missing_ok=True)
                prepare_documents()
                st.session_state.flash = f"'{target}' 을(를) 지웠어요."
                st.rerun()

    st.write("")
    if st.button("새 대화 시작"):
        st.session_state.messages = []
        st.rerun()
    if st.session_state.get("messages"):
        st.download_button(
            "대화 저장하기 (.md)", conversation_markdown(st.session_state.messages),
            file_name="무역공부_대화.md", mime="text/markdown",
        )

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))

# ---------- 본문: 머리말 ----------
total_items = sum(counts.values())
st.markdown(
    f"""<div class="hero">
  <div class="eyebrow">TRADE STUDY NOTE</div>
  <h1>무역 공부 도우미</h1>
  <p>안녕하세요, 선하예요. 수업 노트와 무역 용어 정리에서 답을 찾고, 어느 문서에서 찾았는지 함께 알려 드려요.</p>
  <div class="stats"><span class="stat">자료 {len(counts)}개</span><span class="stat">항목 {total_items}개</span><span class="stat">용어 카드 {len(terms)}장</span></div>
  {HERO_SHIP}
</div>""",
    unsafe_allow_html=True,
)

# 문서를 아직 저장하지 않았다면 버튼 하나로 준비해요
if not graph.DB_DIR.exists():
    st.info("처음 한 번, 자료를 읽어 검색할 수 있게 준비해야 해요.")
    if st.button("자료 준비하기"):
        if prepare_documents():
            st.rerun()
    st.stop()

if "messages" not in st.session_state:  # 대화 기록은 session_state 에 담아 두면 화면이 다시 그려져도 남아요
    st.session_state.messages = []
st.session_state.setdefault("mode", MODES[0])

mode = st.segmented_control("화면", MODES, key="mode", label_visibility="collapsed") or MODES[0]

# ---------- 카드로 외우기 ----------
if mode == MODES[1]:
    if not terms:
        st.info("외울 용어가 없어요. 제목에 '용어'가 들어간 노트(예: '- FOB: 뜻')를 자료에 추가해 보세요.")
        st.stop()
    s = st.session_state
    if s.get("card_deck") is None or max(s.card_deck, default=-1) >= len(terms) or s.get("card_n") != len(terms):
        # 처음이거나 '처음부터'를 눌렀거나, 자료가 바뀌어 카드 수가 달라졌을 때 카드를 새로 섞어요
        s.card_n = len(terms)
        s.card_deck = random.sample(range(len(terms)), len(terms))
        s.card_pos, s.card_show, s.card_known, s.card_again = 0, False, [], []

    total = len(s.card_deck)
    if s.card_pos >= total:  # 한 바퀴 끝
        st.markdown(
            f'<div class="done"><div class="big">{len(s.card_known)} / {total}</div>'
            f'<div>카드를 다 봤어요. 헷갈린 카드는 {len(s.card_again)}장이에요.</div></div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        if s.card_again:
            c1.button("헷갈린 카드만 다시", on_click=card_action, args=("retry",), type="primary")
        c2.button("처음부터 다시", on_click=card_action, args=("restart",))
    else:
        term, meaning, source = terms[s.card_deck[s.card_pos]]
        st.progress(s.card_pos / total, text=f"{s.card_pos + 1} / {total}")
        body = f'<div class="mean">{esc(meaning)}</div>' if s.card_show else '<div class="ask">이 용어의 뜻을 떠올려 보세요</div>'
        st.markdown(
            f'<div class="flash"><div class="no">{esc(source)}</div><div class="term">{esc(term)}</div>{body}</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        if not s.card_show:
            st.button("뜻 보기", on_click=card_action, args=("show",), type="primary")
        else:
            c1, c2 = st.columns(2)
            c1.button("알았어요", on_click=card_action, args=("known",), icon=":material/check:")
            c2.button("헷갈려요", on_click=card_action, args=("again",), icon=":material/refresh:")
            st.button("이 용어 더 물어보기", key="ask_more", on_click=ask_this, icon=":material/chat:",
                      args=(f"{term} 에 대해 더 자세히 알려 줘",))
    st.stop()

# ---------- 질문하기 ----------
# 대화가 그려지는 칸을 먼저 만들고, 입력창을 그 아래(문서의 맨 끝)에 둬요.
# Streamlit 기본 입력창을 쓰면 열자마자 맨 아래로 자동 스크롤되어 머리말이 잘려 보여서,
# 입력창을 컨테이너 안에 넣고 CSS(.st-key-chatbar)로 화면 아래에 붙였어요.
chat_area = st.container()
with st.container(key="chatbar"):
    typed = st.chat_input("선하에게 용어나 노트 내용을 물어보세요")
question = (st.session_state.pop("pending", None) or typed or "").strip()

with chat_area:
    # 첫 화면 안내는 한 칸(placeholder)에 담아 두고, 질문이 들어오면 바로 비워요 (흐릿한 잔상 방지)
    intro = st.empty()
    if not st.session_state.messages and not question:
        with intro.container():
            if today_term:
                st.markdown(
                    f'<div class="today"><span class="tag">오늘의 용어</span>'
                    f'<div class="term">{esc(today_term[0])}</div><div class="mean">{esc(today_term[1])}</div></div>',
                    unsafe_allow_html=True,
                )
                st.button("이 용어 더 물어보기", key="today_ask", on_click=ask_this, icon=":material/chat:",
                          args=(f"{today_term[0]} 에 대해 더 자세히 알려 줘",))
            st.markdown('<div class="sec-label">이렇게 물어볼 수 있어요</div>', unsafe_allow_html=True)
            cols = st.columns(2)
            for i, (icon, example) in enumerate(EXAMPLES):
                cols[i % 2].button(example, key=f"ex{i}", icon=icon, on_click=ask_this, args=(example,))

    for m in st.session_state.messages:
        show_message(m)

    if question:
        past = st.session_state.messages
        if past and past[-1]["role"] == "user":
            # 앞 질문의 답이 끝나기 전에 새 질문을 보내면 답이 비어요 → 자리를 채워 대화 짝이 어긋나지 않게 해요
            past.append({"role": "assistant", "content": INTERRUPTED, "answer": INTERRUPTED, "sources": []})
            show_message(past[-1])
        # 직전 대화 2번까지만 넘겨서 "그건 뭐야?" 같은 질문도 이해하게 해요 (질문 → 답 짝이 맞는 것만)
        history = [
            {"q": past[i]["content"], "a": past[i + 1]["content"]}
            for i in range(len(past) - 1)
            if past[i]["role"] == "user" and past[i + 1]["role"] == "assistant" and past[i + 1]["answer"] != INTERRUPTED
        ][-2:]

        st.session_state.messages.append({"role": "user", "content": question})
        show_message(st.session_state.messages[-1])
        components.html(SCROLL_BOTTOM_JS, height=0)  # 답이 나오는 동안 화면이 아래로 따라가게 해요

        with st.chat_message("assistant"):
            box = st.empty()  # 진행 상황 → 글자가 흘러나오는 답 → 완성된 답 순서로 바뀌는 자리
            result, text = {}, ""
            for kind, value in graph.ask_stream(question, history):  # 질문 1번에 OpenAI 호출은 필요할 때만
                if kind == "step" and not text:
                    box.markdown(
                        f'<div class="thinking">{mascot_small("thinking")}<span>{esc(value)}<span class="dots"></span></span></div>',
                        unsafe_allow_html=True,
                    )
                elif kind == "token":
                    text += value
                    box.markdown(text + " ▍")
                elif kind == "done":
                    result = value
            with box.container():  # 같은 자리에 완성된 답 + 출처를 그려요
                render_answer(result, fresh=True)

        # content 에는 답 글자를, 나머지(answer · sources · rewritten)는 다시 그릴 때 써요
        st.session_state.messages.append({"role": "assistant", "content": result["answer"], **result})
