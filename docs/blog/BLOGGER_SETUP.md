# Blogger 최초 연결 준비

대상: https://lealnspire.blogspot.com/ . 이 문서는 연결 준비 안내이며 현재 업로드 실행기는 없다.

## Google Cloud 준비

1. https://console.cloud.google.com/ 에 블로그 소유 Google 계정으로 로그인한다.
2. 별도 프로젝트를 만든다. 예: `duct-tape-blog`.
3. API 및 서비스 → 라이브러리에서 **Blogger API v3**를 찾아 사용 설정한다.
4. Google Auth Platform(또는 OAuth 동의 화면)에서 앱 이름과 지원/연락 이메일을 입력한다.
5. 개인 Google 계정이면 외부 사용자 유형을 선택하고 테스트 사용자에 블로그 관리 계정을 추가한다. 조직 계정은 조직 정책에 따라 달라질 수 있다.
6. 데이터 액세스/범위에서 `https://www.googleapis.com/auth/blogger`를 추가한다. 이 범위는 초안 전용 권한이 아니며 Blogger 관리 권한이므로 동의 화면의 실제 내용을 확인한다.
7. 클라이언트에서 **데스크톱 앱** 유형의 OAuth 클라이언트를 만들고 JSON을 내려받는다.

콘솔 메뉴명은 변경될 수 있다. Google 안내에 따라 설정하되 클라이언트 비밀값이나 토큰을 채팅으로 보내지 않는다. JSON은 저장소 밖 사용자 전용 디렉터리에 보관한다. Linux 예: `~/.config/duct-tape-blog/client_secret.json`, 디렉터리 권한 700·파일 권한 600. 이 경로는 권장 위치이며 현재 도구가 자동으로 읽는 경로는 아니다.

## 이후 연결할 기능

공식 OAuth 클라이언트 라이브러리로 로컬 브라우저 동의 및 loopback 콜백을 처리하고, 블로그 URL로 대상 ID를 확인한다. WSL에서 실행할 경우 Windows 브라우저와 WSL 콜백 연결을 별도 확인한다. 토큰은 저장소 밖에 제한 권한으로 보관하고 로그에 출력하지 않는다.

검토된 HTML 초안만 isDraft=true로 올리고 게시 ID를 기록한다. 업로드 요청의 응답을 받지 못하면 중복 생성을 막기 위해 기존 초안부터 확인한다. 초안 업로드 검증 뒤 사용자가 Blogger에서 공개한다. 장기 예약 실행 전에는 Google 테스트 모드의 토큰 유효기간 및 재인증 조건을 확인한다.

Google Cloud의 API 키만으로는 글쓰기 권한을 얻을 수 없다. 블로그 소유/작성 권한이 있는 Google 사용자의 OAuth 동의가 필요하다.

공식 안내:
- https://developers.google.com/blogger/docs/3.0/using
- https://developers.google.com/identity/protocols/oauth2/native-app

## 여러 PC·Raspberry Pi에서의 간편 설치 계획 — 2026-10-21

사용자 요청에 따라 업로드 도구는 DuctTape 웹 서버와 분리한 개발 도구로 구성한다. Linux/WSL·Raspberry Pi에서는 설치 스크립트가 전용 가상환경 및 고정된 의존성을 준비하고, 실제 수행 명령을 출력하는 방식을 목표로 한다. Windows 네이티브는 PowerShell 진입점을 별도로 제공하는 범위로 둔다. OS Python이나 DuctTape 서버의 의존성을 덮어쓰지 않는다.

설치 자동화와 Google 계정 인증은 별개다. 소스 복제/설치만으로 다른 PC에 블로그 권한이 생기지 않는다. 각 PC에서 별도 인증하거나 보호된 방식으로 인증 정보를 이전해야 한다. 브라우저 없는 Pi는 PC에서 최초 인증 후 토큰을 안전하게 이전하거나 SSH 터널을 이용한 loopback 인증 방식을 검증한다. Google 계정 비밀번호를 설치 스크립트에 넣지 않는다.

향후 명령은 설치/연결/초안 미리보기/초안 업로드로 구분하고 설치 시 자동 게시하지 않는다. 실제 명령 이름은 도구 구현 시 확정한다. 현재 설치 스크립트나 업로드 실행기는 없으므로 이 절차를 실행 가능한 명령으로 안내하지 않는다. 계정 인증 전에도 오프라인 초안 검증과 모의 업로드 테스트는 가능하도록 설계한다.
