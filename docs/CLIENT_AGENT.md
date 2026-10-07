# 웹 버튼과 Windows 에이전트

브라우저의 버튼은 서버에 작업을 요청한다. Windows 클라이언트에 최초 한 번 설치한 에이전트가 요청을 받아 기존 설치 스크립트를 실행한다. 이후에는 작업마다 실행 파일을 내려받거나 명령을 입력하지 않는다. 정식 Office/한컴 설치 매체와 라이선스 준비는 필요하다.

## MVC 구조

- Model: `Server/models/monitoring.py`는 보고 스키마, `Server/models/agent_jobs.py`는 등록/작업 스키마와 SQLite 저장·상태 전이를 담당한다.
- Controller: `Server/controllers/monitoring.py`, `agent_jobs.py`, `artifacts.py`는 인증과 HTTP 요청/응답을 담당한다.
- View: `Server/views/admin.html`, `client.html`, `portal.js`는 관리자·클라이언트 화면과 버튼 동작을 제공한다. 기존 대시보드 JS/CSS는 `Server/static/`에서 재사용한다.
- `Server/server.py`는 앱 생성, 런타임 초기화, 인증 의존성, 공통 오류/헤더와 라우터 조립을 담당한다.
- Windows: `InstallAgent.ps1`은 최초 등록 및 시작 시 실행되는 예약 작업을 설치한다. `Agent.ps1`은 작업 수신/heartbeat/결과 전송, `AgentActions.ps1`은 고정 작업 선택, `RunAgentJob.ps1`은 보고 테스트와 기존 Main 실행을 담당한다.

## 서버 담당자의 최초 준비

1. `.env`에 다른 토큰과 구별되는 32자 이상 ASCII `DUCT_ADMIN_TOKEN`을 설정하고 서버를 재시작한다. 기존 `DUCT_READ_TOKEN`은 조회 전용, `DUCT_REPORT_TOKEN`은 보고 전용이다. 관리자 토큰이 없으면 작업 관리 API가 비활성화된다.
2. Windows Tailscale Serve의 HTTPS 주소 뒤에 `/admin`을 붙여 접속한다.
3. 화면 위의 관리자 로그인에 `DUCT_ADMIN_TOKEN`을 한 번 입력한다. 상태 조회·에이전트 관리가 함께 연결된다. 인증 키는 입력 후 지우고 서버가 발급한 HttpOnly/SameSite 쿠키로 최대 8시간 유지한다. 새로고침 시 로그인 상태를 복원하며 로그아웃·서버 재시작·만료 시 다시 로그인한다. 관리자 화면에서 별도 조회 토큰 입력은 필요 없다.
4. `1회 등록 코드 발급`을 누른다. 코드는 10분간 유효하고 한 번만 사용할 수 있다. 여러 PC는 각각 코드를 발급한다.

## 클라이언트 최초 설치

1. 클라이언트를 같은 Tailscale 네트워크에 연결한다. Windows PowerShell 5.1과 관리자 권한이 필요하다.
2. 로컬 배포 폴더에 `InstallAgent.bat`, `Main.bat`, `Scripts/`, `Modules/`, `Config/`, `Office/`, `Hancom/`을 준비한다. Office/한컴 매체와 `Config/HancomKey.txt`는 [기존 배포 가이드](wiki/Deployment-Guide.md)를 따른다.
3. `Config/Monitoring.json`을 준비한다. 없으면 설치 도구에서 서버 HTTPS 주소, 학교 코드, 학년, 보고 토큰을 묻는다. 기본 `DUCT_REPORT_TOKEN`을 사용할 때 학교 코드는 비워 둔다. 학교별 토큰은 등록된 학교 코드와 함께 사용한다.
4. `InstallAgent.bat`을 실행해 관리자 권한을 승인하고 1회 등록 코드를 입력한다.
5. 도구는 배포 스크립트·매체와 클라이언트용 Monitoring.json/HancomKey.txt만 `%ProgramData%\DuctTapeAgent`에 복사한다. 복사본은 SYSTEM·관리자 전용 새 폴더에 보관한다. 큰 설치 매체를 복사할 디스크 공간을 확보한다. 기존 폴더가 있으면 자동 덮어쓰기하지 않는다.
6. 예약 작업 `DuctTapeAgent`는 SYSTEM 권한으로 즉시 시작하고 Windows 시작 시 다시 실행한다. PC의 Tailscale 연결은 해당 권한에서 통신 가능한 상태로 유지한다.
7. 공용 바탕화면의 `duct-tape 작업` 바로가기를 연다. 이 PC 전용 클라이언트 접속 키가 URL fragment로 전달되고 페이지가 즉시 주소에서 제거한다. 서버 요청/로그에는 fragment가 전송되지 않는다. 바로가기에는 PC 전용 키가 포함되므로 다른 PC에 복사하지 않는다.
8. 첫 작업은 `보고 연결 테스트`를 선택한다. 성공하면 관리자 대시보드에서 PC 보고를 확인한 뒤 실제 배포를 시작한다.

기존 `Client.bat`/`Main.bat` 수동 실행도 가능하다. 다만 에이전트 배포와 수동 배포를 동시에 실행하지 않는다. 매체나 설정 변경은 관리자 권한으로 ProgramData의 복사본에 반영해야 한다.

## 일상 작업

- 클라이언트 `/client`: 자기 PC 접속 키로 연결, 보고 테스트 또는 배포를 선택하고 작업 시작 버튼을 누른다. 바탕화면 바로가기는 접속 키 입력을 자동화한다.
- 관리자 `/admin`: 한 번 로그인한 뒤 등록된 PC 목록에서 대상을 선택하고 작업을 요청한다. PC 목록은 5초마다 갱신된다. 등록 코드 버튼을 로그인 전에 누르면 로그인 안내가 표시된다. 코드 발급 결과와 오류는 버튼 옆에 표시한다.
- 상태: `queued` 대기 → `running` 실행 → `succeeded`/`failed` 종료. 화면은 5초 간격으로 갱신된다. 에이전트는 대기 시 5초 간격으로 작업을 확인하고 실행 중 10초 간격으로 heartbeat를 보낸다.
- Main은 `--unattended` 인자로 실행해 pause를 생략한다. 배포 시작 전 보고 연결 테스트가 실패하면 설치를 시작하지 않는다. 시작 후 보고 장애는 기존 설치 정책에 따라 경고 후 계속 진행한다.
- 기존 단계별 보고는 관리자 대시보드에서 확인한다. 설치 백분율은 제공하지 않는다. 종료 코드 0은 배포 스크립트 성공이며 정품 인증 확인은 별도다.

## 중단·재등록

작업 요청에는 요청 ID가 있어 같은 요청 재전송은 같은 작업을 반환한다. PC에 대기/실행/중단 미확인 작업이 있으면 새 작업을 거부한다. 작업 claim은 SQLite 트랜잭션으로 하나의 에이전트만 가져간다.

heartbeat가 120초 이상 끊긴 작업은 상태 조회/claim 시 `interrupted`로 바뀐다. 에이전트가 재시작했는데 완료 결과가 로컬에 없으면 중단으로 보고한다. 이미 설치를 시작했을 가능성이 있으므로 자동 재실행하지 않는다. 완료 결과가 저장돼 있으면 결과 전송만 재시도한다.

관리자는 해당 PC의 설치 프로세스와 실제 상태를 확인한 뒤 관리자 페이지에서 작업 ID를 입력해 `중단 작업 확인 완료`를 누른다. 실행 중인 설치가 남아 있으면 이 버튼을 누르지 않는다. 완료 처리는 작업을 실패 상태로 닫고 새 요청을 허용한다.

등록 해제 버튼은 해당 PC의 에이전트·클라이언트 접속 키를 폐기한다. 대기 작업은 취소하지만 실행/중단 미확인 작업이 있으면 해제를 거부한다. Windows 예약 작업은 서버에서 제거하지 않는다. 재등록하려면 해당 PC에서 기존 설치가 끝났는지 확인한 뒤 관리자 PowerShell로 다음 작업을 수행한다.

```powershell
Stop-ScheduledTask -TaskName DuctTapeAgent
Unregister-ScheduledTask -TaskName DuctTapeAgent -Confirm:$false
```

배포 매체·설정을 보존하고 기존 `%ProgramData%\DuctTapeAgent` 폴더는 담당자가 백업/정리한다. 공용 바탕화면의 기존 바로가기도 정리한다. 새 등록 코드로 최초 설치를 다시 수행한다. 설치 과정이 서버 등록 후 실패한 경우에도 같은 절차로 서버 등록과 로컬 상태를 정리한다.

## 데이터와 권한

SQLite에는 PC 인증 키의 SHA-256 해시와 작업 종류·상태·시각·종료 코드만 저장한다. 서버가 임의 명령이나 매체 경로를 내려보내지 않는다. 보고 테스트와 배포 외 작업은 서버/에이전트에서 거부한다. 클라이언트 접속 키로는 다른 PC 작업·에이전트 claim·관리자 API에 접근할 수 없다.

기존 업로드 API도 관리자 인증으로 제한하고 서버 생성 파일명으로 최대 100MiB만 저장하도록 변경했다. 업로드 파일은 자동 실행하거나 배포 매체에 반영하지 않는다. `/files`는 명시적으로 `downloads/`에 놓은 파일만 공개하므로 비밀값을 두지 않는다.

설치 실행 권한과 PC 격리를 위해 인증은 유지한다. Tailscale 연결만으로 관리자 권한을 부여하지 않는다. 로그인 쿠키는 서버의 해시 세션과 대응하며 JavaScript/localStorage에 관리자 키를 저장하지 않는다. 변경 요청은 같은 출처의 전용 헤더를 요구한다.

실제 설정, 키, 바로가기, 매체, DB와 로그는 Git에서 제외한다. 에이전트 작업 stdout/stderr는 `%ProgramData%\DuctTapeAgent\logs`에, 기존 설치 로그/상태는 SYSTEM 계정의 TEMP 경로에 기록된다.

## 검증

```bash
.venv/bin/python -m pytest tests/test_agent_jobs.py tests/test_portal.py tests/test_server.py tests/test_gas_relay.py -q
```

```powershell
powershell -NoProfile -File tests/Test-AgentActions.ps1
powershell -NoProfile -File tests/Test-ClientSetup.ps1
powershell -NoProfile -File tests/Test-ReportStatus.ps1
powershell -NoProfile -File tests/Test-Common.ps1
```

Python 테스트는 권한 분리, 1회/만료 등록, PC 격리, 고정 작업, 중복 요청, 동시 claim, 영속성, 상태 전이, 중단 처리·복구·키 폐기와 업로드 경로 보호를 검증한다. JavaScript 테스트는 QuickJS로 버튼 동작, 확인 취소, 중복 클릭, 키 제거, 인증 실패와 텍스트 렌더링을 검증한다. PowerShell 테스트는 실제 설치 없이 스크립트 구문과 허용 작업 선택을 검증한다.

PowerShell→실제 HTTP 서버 보고 통합 테스트도 통과했다. 실제 Windows 5.1 UAC, 예약 작업의 SYSTEM 통신, 파일 복사/권한, Tailscale Serve HTTPS, ODT/MSI 무인 설치는 Windows 테스트 PC에서 인수 검증이 필요하다. 작업 취소·자동 재실행·자동 매체 다운로드는 제공하지 않는다.
