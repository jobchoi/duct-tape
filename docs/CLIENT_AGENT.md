# 환경 셋업 사용 방법

기본 기획은 [SETUP_PLAN.md](SETUP_PLAN.md)에 정리했다. 선택 설치·수동 코드 교환은 제외하고 다운로드 → 최초 연결 → 셋업 요청을 우선 검증한다.

## 처음 사용하는 PC

1. 서버의 `/client`에서 **실행 도구 다운로드**를 누른다. `/download/agent.zip`에서 실행 도구 ZIP을 받을 수 있다.
2. ZIP 전체를 압축 해제하고 `InstallAgent.bat`을 실행한다. 관리자 권한 요청을 승인한다. 서버 주소는 ZIP의 `Config/ServerUrl.txt`에 포함된다.
3. 설치 도구가 서버에 PC 연결을 요청하고 `%ProgramData%\DuctTapeAgent`에 실행 도구와 SYSTEM 예약 작업을 설치한다.
4. 공용 바탕화면에 `duct-tape 작업` 바로가기가 생성되며 브라우저도 열린다. 설치 전에는 이 바로가기가 없는 것이 정상이다. 브라우저 자동 열기가 실패하면 바로가기를 직접 연다.
5. 실제 셋업용 Office·한컴 매체와 라이선스 키를 준비한 뒤 환경 셋업 버튼을 사용한다.

**에이전트 설치에는 Office·한컴 매체가 없어도 된다.** 다운로드 ZIP에는 실행 스크립트만 넣고 `.env`, 실제 인증 키, 라이선스 키와 설치 매체는 포함하지 않는다.

## 실제 설치 준비

`C:\ProgramData\DuctTapeAgent`에 직접 준비하거나, 서버 배포 원본에서 자동 전달받을 수 있다. 서버 원본에는 다음 항목을 준비한다.

- `Office/setup.exe`, `Office/install.xml`, `Office/remove.xml` 및 정식 Office 매체.
- `Hancom/Install/Hwp130.msi`, `Hancom/Install/VC_redist.x86.exe` 및 나머지 정식 한컴 매체.
- `Config/HancomKey.txt`의 유효한 기관 라이선스 키.

실행 도구는 이 파일들의 준비 여부를 서버에 보고한다. 없으면 웹에서 `설치 매체 준비 필요`를 표시하고 셋업 요청을 차단한다. 준비 여부는 파일 존재 확인이며 실제 키/매체 유효성은 Main의 사전 검증에서 확인한다. 원본 폴더에 매체/키가 이미 있다면 설치 도구가 함께 복사한다. 세부 매체 조건은 [배포 가이드](wiki/Deployment-Guide.md)를 따른다.

설치 원본이 저장소 밖에 있으면 `config/app.conf`에 `DUCT_MEDIA_ROOT="/mnt/d/deployment/duct-tape"`처럼 WSL에서 접근 가능한 상위 폴더를 지정하고 서버를 재시작한다. 그 아래에 Office/, Hancom/, Config/HancomKey.txt 구조가 있어야 한다. `.gitignore`는 Git 추적에만 영향을 주며 이 읽기/전송을 차단하지 않는다.

서버 원본이 준비되면 PC에 파일이 없어도 셋업 버튼이 활성화된다. 승인된 에이전트가 `/api/agent/media`에서 비공개 ZIP을 받아 압축을 풀고 실제 설치를 시작한다. 정식 매체 전체와 키를 전달하되 서버 `.env`나 기타 설정은 전달하지 않는다. 공개 실행 도구 ZIP에는 계속 키를 넣지 않는다.

현재 확인 가능한 작업 폴더에는 실제 매체/기관 키가 없다. 실제 원본 경로가 필요하며 예제 키로 대체하거나 없는 설치 파일을 만들지 않는다.

## 테스트 모드와 운영 인증 모드

| 항목 | development | secure (기본값) |
| --- | --- | --- |
| 관리자 | 인증 키 입력 없이 상태 조회 | 관리자 키로 한 번 로그인, 최대 8시간 세션 유지 |
| 클라이언트 | MachineGuid로 식별, 토큰 없이 신청 | PC별 인증은 도구가 자동 처리, 사용자의 토큰 입력 없음 |
| 최초 연결 | 중복 확인 후 자동 승인 | 관리자 화면에서 PC 연결 한 번 승인 |
| 같은 PC 재신청 | 기존 식별값 재사용, 중복 생성 없음 | 기존 설치/연결 상태 확인 필요 |

MachineGuid는 식별값이며 인증 수단은 아니다. PC 이름은 표시용으로 사용한다. 모드별 차이는 `Server/security.py`의 `SecurityPolicy`에 분리했다. `DUCT_AUTH_MODE`의 기본값은 secure다.

로컬 무인증 테스트는 공유 서버와 다른 임시 DB·루프백 포트에서 실행한다.

```bash
DUCT_AUTH_MODE=development DUCT_DB_PATH=/tmp/duct-local-onboarding.sqlite3 .venv/bin/python -m uvicorn Server.server:app --host 127.0.0.1 --port 8001
```

Windows/WSL 호스트에서 `http://localhost:8001/admin`, `/client`로 확인한다. 이 임시 포트는 Tailscale 공유 주소에 연결하지 않았다. 현재 Tailscale 공유 서버의 8000 포트는 secure를 유지한다.

## 화면과 작업

관리자 화면은 로그인/테스트 모드와 연결 상태를 표시한다. 인증 확인 전에는 PC 관리 영역을 숨기고, 로그인 성공 시 표시한다. 연결 PC가 0대이면 다운로드 안내를 표시한다. PC 선택은 자동 갱신 후에도 유지된다. 보고만 있는 더미 기기는 작업 대상에서 제외한다.

클라이언트는 바탕화면 바로가기에서 자기 PC로 자동 연결한다. 식별값/PC 인증 정보는 URL fragment에서 지우고 현재 탭의 sessionStorage에 보관한다. 관리자 키는 이 저장소에 보관하지 않는다. 바로가기를 다른 PC에 복사하지 않는다.

셋업 요청은 PC별 대기/실행 작업을 하나만 허용한다. 실행 중 끊어진 작업은 자동 재실행하지 않는다. 실제 Office·한컴 제거/설치가 진행될 수 있으며 수동 Main 실행과 동시에 실행하지 않는다. 설치 후 앱 실행·재부팅·정품 인증은 별도로 확인한다.

## 구조와 검증

Model은 `Server/models/`, Controller는 `Server/controllers/`, View는 `Server/views/`, 인증 정책은 `Server/security.py`에 둔다. `agent_package.py`는 고정 허용 목록으로 ZIP을 생성하며 임의 경로나 비밀 파일을 포함하지 않는다. Windows 실행 도구는 고정 작업만 실행한다.

자동 테스트는 ZIP 내용과 비밀 제외, 로컬 연결 신청/중복, 매체 누락 차단, 준비 후 작업 요청/claim/완료, 운영 인증, 로그인 표시와 기본 화면을 검증한다. PowerShell 실제 HTTP 보고는 secure/development 두 모드에서 확인한다.

Windows 5.1 UAC, 바탕화면/예약 작업 생성, 정식 매체를 통한 실제 설치는 실제 Windows PC에서 확인해야 한다. 이 범위를 Linux 테스트 통과로 완료했다고 간주하지 않는다.
