---
name: Study Buddy
description: 개인 챗봇 과제용 디자인 규칙 (자유롭게 바꿔도 돼요)
colors:
  primary: "#2B59C3"
  surface: "#F5F7FB"
  text: "#1B1F24"
  card: "#FFFFFF"
  primary-deep: "#1F44A0"
  primary-soft: "#E8EEFB"
  muted: "#6B7480"
  border: "#E1E6EF"
  chip: "#EEF1F6"
  accent: "#F2B33D"
typography:
  body-md:
    fontFamily: Pretendard
    fontSize: 1rem
    lineHeight: 1.7
  source-sm:
    fontFamily: Pretendard
    fontSize: 0.8rem
    lineHeight: 1.55
rounded:
  md: 12px
components:
  chat-bubble-user:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
  answer-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  source-text:
    textColor: "{colors.muted}"
    typography: "{typography.source-sm}"
  example-chip:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
---

## Overview
공부 친구 같은 편안한 챗봇. 답변은 읽기 쉽게, 출처는 작고 차분하게.
화면은 맨 위 파란 머리말 카드(컨테이너선 그림), 가운데 한 줄 대화(폭 760px), 왼쪽 "내 자료" 사이드바로 구성해요.
배경은 공책 같은 연한 점무늬예요. 포인트색은 파랑(primary)이고, 나머지는 흰색과 회색 계열로 차분하게 둬요.
노란색(accent)은 "오늘의 용어" 표시 점 하나에만 아주 조금 써요.

## Do's and Don'ts
- Do: 출처는 답변 아래 작은 회색 글씨 (파일 이름은 굵게, 미리보기는 보통)
- Do: 사용자 말풍선은 오른쪽 파란색, 도우미 답변은 왼쪽 흰 카드(왼쪽에 파란 띠)
- Do: 캐릭터(선하)는 토큰 색만 써서 직접 그린 SVG 로, 평소엔 느긋하게 · 찾을 땐 돋보기 · 찾았을 땐 폴짝 · 못 찾았을 땐 물음표로 움직이기 (사진 · GIF 는 쓰지 않기)
- Do: 외우기 카드는 용어를 크게(파랑), 뜻은 눌러서 보여 주기
- Do: 문서에서 못 찾았을 땐 회색 글씨로 담담하게 알리고 다음에 해 볼 일을 한 줄 안내
- Don't: 화면 가득 장식, 글꼴 3개 이상 (글꼴은 Pretendard 하나)
- Don't: 토큰에 없는 색 (그라데이션 · 보라색 · 형광색 포함), 이모지로 화면 꾸미기 (아이콘은 선 모양 하나로 통일)
