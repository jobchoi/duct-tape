# 작업 기록과 블로그 게시 원칙

기준일: 2026-10-21. 사용자 블로그 소개와 이번 대화에서 정한 기준을 재구성한 문서다. 과거 헌장 원문을 복구한 것은 아니다.

## 두 블로그의 역할

| 대상 | 목적 | 구성 |
| --- | --- | --- |
| https://lealnspire.blogspot.com/ | 개발 일지 | 배경 → 현상 → 가설/확인 → 시행착오 → 수정 → 검증 → 남은 작업 |
| https://rt-jobchoi.tistory.com/ | 작업 지시·매뉴얼 | 적용 조건 → 준비 → 실행 절차 → 확인 방법 → 오류 대응·제한 |

하나의 작업 기록에서 두 글을 작성하되 같은 본문을 그대로 중복 게시하지 않는다. 작업을 수행한 날짜와 글을 작성한 날짜를 구분한다.

## QTP와 이 문서의 경계

공통 목적과 AI 협업 원칙은 프로젝트 문서에서 분리한 [QTP 헌장](../../editorial/qtp/CHARTER.md)과 [운영 문서](../../editorial/qtp/OPERATIONS.md)를 따른다. 이 문서는 DuctTape 게시물의 적용 기준만 관리하며 헌장 본문을 중복하지 않는다.

- DuctTape 작업 기록·커밋·테스트를 근거로 작성하고 실제 코드, 모의/브라우저 테스트, 현장 설치, 운영 배포를 구분한다.
- 기관/장치 식별 정보와 비밀번호·제품 키·토큰을 글·캡처·외부 AI 입력에서 제외한다. 설정·로그·diff 전체를 무차별 전달하지 않는다.
- 개발 일지와 사용 매뉴얼의 독자를 구분하고 재현 조건·미확인 범위를 밝힌다.
- 초안 업로드와 공개를 구분하며 공개 전 작성자가 원고를 확인한다. 승인 버전과 게시 ID로 변경·중복을 관리한다.

## 자동화 범위와 현재 상태

Blogger는 OAuth 인증 후 공식 API의 posts.insert(isDraft=true)로 초안을 올릴 수 있다. 티스토리는 공식 글쓰기 Open API가 종료되었으므로 파일 작성까지 자동화하고 편집기에 직접 입력하는 흐름을 우선한다. 로그인된 브라우저 자동화는 공식 API와 별개이며 현재 구현하지 않았다.

현재 저장소에는 게시 기준, 두 종류의 초안, 최초 설정 안내를 준비했다. 2026-10-21 업로드 실행기와 설치 스크립트를 추가했다. 실제 계정 연결·시험 업로드 상태는 작업 기록을 따른다. 예약 실행과 공개 발행 기능은 구현하지 않았다.

## 근거

- 작업 근거: docs/WORK_HISTORY.md, docs/MDM_MANUAL_SETUP.md, 관련 테스트와 커밋 c2d4c30.
- Blogger API: https://developers.google.com/blogger/docs/3.0/reference/posts/insert
- OAuth: https://developers.google.com/identity/protocols/oauth2/native-app
- 티스토리 종료 안내: https://notice.tistory.com/2664
