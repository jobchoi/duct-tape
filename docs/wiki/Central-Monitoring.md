# 중앙 관제 운영 가이드

[[Home]] · [[Modules-Specification]] · [[Deployment-Guide]]

학교 무인 배포 duct-tape의 Phase 3입니다. 서버 실행·기관망 배포·다음 Phase는 운영자의 수동 승인 아래 진행합니다. 이 문서는 실행 방법을 제공하며 자동 배포를 수행하지 않습니다.

## 서버 준비

Python 3.11 이상과 서버 로컬 디스크를 사용합니다. 저장소 루트에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r Server\requirements.txt
$env:DUCT_REPORT_TOKEN = (.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:DUCT_READ_TOKEN = (.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python -m uvicorn Server.server:app --host 127.0.0.1 --port 8000
```

Linux에서는 `.venv/bin/python`과 셸 환경변수를 사용합니다. 두 토큰은 서로 다른 32자 이상 ASCII 문자열이어야 합니다. 예시 명령은 서버 세션마다 새 토큰을 만드므로 기관 운영 시 비밀 저장소에서 기존 값을 주입합니다. `.env` 자동 로딩 기능은 없습니다. 토큰 원문을 Git·Wiki·로그에 저장하지 않습니다.

기본 DB는 `Server/data/monitoring.sqlite3`이며 `DUCT_DB_PATH`로 변경할 수 있습니다. 실행 계정에 DB 디렉터리 쓰기 권한을 부여합니다. SQLite WAL 파일까지 같은 로컬 디스크에 두며 SMB 공유 DB는 사용하지 않습니다. 기본 실행은 loopback 전용입니다. 기관망 배포 승인 후 HTTPS 역방향 프록시를 구성하고 방화벽을 관리 대상 서브넷으로 제한합니다. 대시보드 브라우저는 최신 Edge/Chrome을 사용합니다.

## 클라이언트 설정

`Config/Monitoring.json.example`을 `Config/Monitoring.json`으로 복사합니다.

| 설정 | 의미 |
| --- | --- |
| Enabled | true이면 보고. 예제는 false이며 설정 파일이 없어도 설치는 계속됨 |
| ServerUrl | HTTPS 서버 원점. 경로·쿼리·사용자정보 없이 입력 |
| ReportToken | 서버 DUCT_REPORT_TOKEN 값. 조회 토큰은 클라이언트에 배포하지 않음 |
| AllowHttp | 기본 false. 격리된 로컬 검증에서만 HTTP 사용을 명시적으로 허용 |
| TimeoutSeconds | 요청 제한 1~10초, 기본 3초 |
| MaxAttempts | 총 시도 1~3회, 기본 2회, 재시도 사이 1초 대기 |

실패 시 REPORT_UNAVAILABLE 경고 후 설치를 계속합니다. 400/401/403/404/422는 재시도하지 않습니다. 그 외 통신·서버 실패는 제한 횟수만 재시도합니다. 기본 네트워크 요청 대기 예산은 이벤트당 약 7초이며 PowerShell 5.1의 DNS 조회나 기기 정보 조회 시간은 별도로 더 걸릴 수 있습니다. 영속 오프라인 큐는 없으므로 재시도 소진 시 해당 이벤트는 유실될 수 있고 다음 단계 보고에서 최신 상태를 회복합니다.

01~06의 시작·완료, 공통 오류 처리에서 보고합니다. 키 누락에 의한 Main 사전 종료도 실패 보고를 시도합니다. ODT/MSI 실행 도중 주기적인 heartbeat나 실제 설치 백분율 보고는 없습니다. 설치 옵션은 Phase 2를 유지합니다.

## API 및 저장 계약

- `POST /api/report`: 보고 토큰의 Bearer 인증. 검증 후 기기별 최신 상태를 SQLite에 upsert합니다.
- `GET /api/devices`: 조회 토큰의 Bearer 인증. 최신 기기 목록과 서버 수신 시각을 반환합니다.
- `GET /`: 공개 대시보드 틀만 반환합니다. 자산 데이터는 조회 토큰 입력 후 표시합니다.

보고 필드: device_id/report_id(UUID), hostname, serial, model, mac, office, hancom, stage(Preflight 또는 01~06), status(running/completed/failed), error_code, installer_exit_code, reboot_required, observed_at(시간대 포함 UTC).

기기 키는 Windows MachineGuid입니다. 이름 변경에는 유지되지만 OS 재설치 시 바뀔 수 있으며 복제 이미지의 중복 GUID는 배포 전에 Sysprep 등 기관 절차로 해결해야 합니다. MAC은 IP가 활성화된 어댑터 중 정렬된 첫 주소입니다. Serial/Model은 01의 수집 결과이며 사전 검증 실패 보고에는 없을 수 있습니다.

키·설치 인수·원문 예외·전체 State/Config를 보내지 않고 명시된 필드만 구성합니다. 스키마에 없는 필드는 서버가 거부하며 검증 오류 응답에도 입력값을 반사하지 않습니다.

동일 기기의 observed_at이 더 최신일 때만 갱신합니다. 같은 요청 재시도나 늦게 도착한 과거 보고는 accepted=true, updated=false입니다. 동일 시각 충돌은 먼저 저장된 보고가 유지됩니다. 클라이언트 시계를 동기화해야 하며 서버보다 5분 넘게 미래인 보고는 거부합니다. 시계가 뒤로 변경되면 기존 시각을 따라잡을 때까지 보고가 갱신되지 않을 수 있습니다. 수신 시각은 서버가 별도로 기록합니다.

## 대시보드 및 데이터 보관

조회 토큰을 입력하면 5초 간격으로 조회합니다. 토큰은 페이지 메모리에만 두며 저장소·URL에 보관하지 않습니다. 연결 해제 시 화면 자산과 토큰을 지웁니다. 화면은 호스트/일련번호/모델 검색, Office/한컴 상태, 단계·오류코드, 재부팅 여부, 최종 수신 시각을 표시합니다.

5분 이상 지난 보고에는 경과 표시를 붙입니다. 장시간 설치 중 보고가 없을 수도 있으므로 이를 오프라인 판정으로 해석하지 않습니다. 갱신 실패 시 기존 데이터를 유지하고 실패 상태를 표시합니다. 06 completed만 배포 완료로 집계하며 라이선스 인증 성공을 뜻하지 않습니다.

DB에는 기기별 최신 행만 저장하며 이벤트 이력·자동 삭제 기능은 없습니다. 기기 퇴역/보관 기간은 기관 정책으로 정하고 운영자가 정리합니다. DB는 암호화되지 않으므로 실행 계정·백업 접근 권한을 제한합니다. 서버 중지 후 DB와 WAL/SHM을 일관되게 백업하거나 SQLite 백업 기능을 사용합니다.

## 검증 및 제한

```powershell
.\.venv\Scripts\python -m pip install -r Server\requirements-dev.txt
.\.venv\Scripts\python -m pytest tests/test_server.py -q
powershell -NoProfile -File tests/Test-Common.ps1
powershell -NoProfile -File tests/Test-ReportStatus.ps1
```

서버 테스트는 인증 분리, 입력 거부, 반복·역순 보고, 영속성, 저장소 장애, 50대 동시 요청을 검증합니다. PowerShell 보고 테스트는 허용 필드, UTF-8, 재시도 동일 ID, 장애 격리를 검증합니다. Windows PowerShell 5.1/실제 SMB·HTTPS·설치 매체 인수 검증은 별도입니다. Google Sheets 전송은 Phase 4 승인 전까지 구현하지 않습니다.

구현 참고: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [FastAPI TestClient](https://fastapi.tiangolo.com/reference/testclient/), [Python sqlite3](https://docs.python.org/3/library/sqlite3.html).

추가 검증: `node tests/test_dashboard.cjs`로 모의 DOM 동작을 확인합니다. `DUCT_TEST_PWSH`에 PowerShell 실행 경로를 지정하고 `python -m pytest tests/test_report_integration.py -q`를 실행하면 가짜 기기 정보로 임시 loopback 서버까지 실제 HTTP 전송을 검증합니다. 이 테스트는 소켓 생성 권한이 필요하며 완료 후 서버를 종료합니다. Node/브라우저는 서버 실행 의존성이 아니라 UI 검증 도구입니다.
