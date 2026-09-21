# Phase 4 GAS 미러링 설계안 — 구현 승인 대기

이번 승인은 Git 정리와 계획 수립까지이다. 이 문서는 구현 제안이며 아직 코드·GAS 배포·실제 시트 쓰기는 수행하지 않았다. 범위는 FastAPI → GAS → Sheets 단방향 릴레이이다. 시트 → 서버 역방향 동기화는 제외하고 별도 승인 대상으로 둔다.

## 승인 요청 파일 목록

| 파일 | 예정 변경 |
| --- | --- |
| Server/server.py | 학교·학년 스키마/인증 범위, SQLite 마이그레이션, BackgroundTasks 연결 |
| Server/gas_relay.py (신규) | HTTPS 전송, 요청 서명, 응답 검증, 제한 재시도 |
| Server/outbox.py (신규) | 미전송 이벤트 저장·작업 점유·성공/실패 기록·재전송 |
| Server/replay_outbox.py (신규) | 유휴 상태에서 관리자가 미전송 작업을 재실행하는 CLI |
| Server/requirements.txt, requirements-dev.txt | httpx를 서버 실행 의존성으로 추가하고 테스트 의존성 정리 |
| Config/Monitoring.json.example | SchoolCode, Grade 예제 추가 |
| Config/Schools.json.example (신규) | 학교 코드·유형·학교별 보고 토큰·GAS 경로/키 식별자의 비밀값 없는 예제 |
| Scripts/ReportStatus.ps1 | 학교·학년 허용 필드 전송, 기존 설치 장애 격리 유지 |
| Server/static/index.html, dashboard.js | 학교·학년 표시 및 필터 |
| GoogleAppsScript/Code.gs (신규) | doPost 검증, 학교별 목적지 선택, 고정 열 upsert·중복/역순 방어 |
| GoogleAppsScript/appsscript.json (신규) | 고급 Sheets 서비스 설정, 필요한 권한 선언. 비밀값 포함 금지 |
| tests/test_server.py, test_report_integration.py, Test-ReportStatus.ps1, test_dashboard.cjs | 기존 동작 및 메타데이터 계약 확장 |
| tests/test_gas_relay.py, test_gas_receiver.cjs (신규) | 장애·재시작·동시성·서명·열 매핑·RAW 쓰기 검증 |
| .gitignore | 실제 학교 설정 제외 유지, 비밀값 없는 GAS manifest의 정확한 경로만 허용 |
| PROJECT_PLAN.md, README.md, docs/ARCHITECTURE.md, docs/TROUBLESHOOTING.md | 진행 상태·운영 방법·장애 대응 갱신 |
| docs/PHASE4_DESIGN.md, docs/wiki/GAS-Mirroring.md (신규), docs/wiki/Home.md, Central-Monitoring.md, Modules-Specification.md | 확정 설계 및 Wiki 이식용 운영 문서 |

## 데이터 흐름

```mermaid
flowchart LR
    A[Windows ReportStatus: 학교·학년·기기 상태] --> B[FastAPI 인증 및 스키마 검증]
    B --> C[(SQLite: 최신 상태 + outbox 트랜잭션)]
    C --> D[클라이언트에 수신 성공 응답]
    D --> E[BackgroundTasks: pending 전송]
    E -->|서명된 HTTPS POST| F[GAS doPost]
    F --> G[학교별 목적지 검증 및 ScriptLock]
    G --> H[고정 열 RAW 쓰기: 학교별 Devices 시트]
    H --> I[report_id 포함 JSON 응답]
    I --> J[(outbox 성공 처리)]
```

BackgroundTasks는 응답 후 실행하는 방식으로 사용한다. 응답 성공은 SQLite 수신 성공을 뜻하며 Google Sheets 반영 완료를 뜻하지 않는다. GAS 실패가 기존 설치·로컬 관제를 실패로 바꾸지 않는다. [FastAPI 공식 설명](https://fastapi.tiangolo.com/tutorial/background-tasks/)

## 학교·학년 식별 및 기존 데이터 호환

- school_code: 기관이 지정하는 고정 코드, 제안 규칙 `[A-Z0-9_-]{1,32}`. 학교 이름·hostname에서 추정하지 않는다.
- school_type: 서버 학교 등록부의 elementary/middle/high 값. 클라이언트가 임의로 바꿀 수 없다.
- grade: 초등 1~6, 중·고 1~3. 공용/교직원 기기는 null로 허용하며 시트에는 빈 값으로 기록한다. 학교 등록부와 함께 검증한다.
- 클라이언트 보고 토큰을 학교 코드에 결합한다. A학교 토큰으로 B학교 코드를 보내면 거부한다. GAS 목적지 URL/스프레드시트 ID는 클라이언트 입력을 받지 않는다.
- 서버 기기 키는 `(school_code, device_id)`, 이벤트 키는 `(school_code, report_id)`로 정한다. hostname·serial·grade는 표시/분류 값이므로 동일 hostname이나 진급으로 행이 중복되지 않는다.
- 기존 Phase 3 데이터는 학교 미지정 영역으로 보존한다. 학교 메타데이터 없는 구형 보고는 기존 토큰으로 로컬 관제를 계속하되 GAS로 전송하지 않는다. 학교 등록 후 명시적 매핑만 허용하며 임의 학교로 배정하지 않는다.
- SQLite 테이블 변경은 백업·스키마 버전·트랜잭션 기반 마이그레이션으로 검증한다.
- 현재 중앙 조회 토큰은 전체 학교를 보는 관리자용이다. 학교별 시트 공유로 외부 조회 범위를 제한하며 중앙 대시보드 학교별 권한 체계는 이번 범위에 포함하지 않는다.

## BackgroundTasks와 재시도 계약

1. 검증된 새 이벤트의 outbox 기록과 최신 상태 갱신을 동일 트랜잭션으로 저장한다. 최신 상태보다 오래된 이벤트도 고유 ID 기준으로 기록할 수 있지만 시트의 최신 행을 되돌리지는 않는다.
2. 트랜잭션 성공 후 BackgroundTasks에 작업을 등록한다. 작업마다 독립 DB 연결을 사용하고 동시 전송은 기본 2개로 제한한다.
3. HTTPS 연결 제한 3초, 읽기 제한 5초, 총 3회 시도를 기본안으로 둔다. 타임아웃·429·5xx·GAS 잠금 경합은 지수 대기와 제한된 지터 후 재시도한다.
4. outbox는 pending/sending/sent/failed, 시도 횟수, next_attempt_at, 점유 만료 시각, 비밀값 없는 마지막 오류 코드를 저장한다. 중복 worker는 원자적 작업 점유로 방지한다.
5. 재시작 시 만료된 sending과 pending을 회수하고 제한된 배치로 재개한다. 후속 보고의 BackgroundTasks도 기한이 된 pending을 처리한다. 유휴 상태의 실패 작업은 replay CLI로 재개하며 별도 상시 스케줄러는 이번 범위에 추가하지 않는다.
6. 시트 반영 후 응답 유실은 동일 report_id 재전송으로 처리한다. 전달 방식은 중복 가능 재전송이며 정확히 한 번 전달을 보장한다고 표현하지 않는다.
7. sent 기록 보관 기간은 기본 30일을 제안하고 기관 설정으로 변경한다. pending/failed는 자동 폐기하지 않고 운영자에게 건수·고정 오류 코드를 제공한다.

## GAS 인증 및 응답

- doPost(e)는 e.postData.contents의 JSON 본문을 읽는다. 임의 Authorization 헤더 접근에 의존하지 않는다. [Web App 이벤트 계약](https://developers.google.com/apps-script/guides/web)
- 요청은 schema_version, key_id, sent_at, payload_json, signature의 envelope로 구성한다. 서명은 `sent_at + 개행 + payload_json` 원문 UTF-8에 대한 HMAC-SHA256이다. JSON 재직렬화 순서 차이를 피한다.
- key_id별 공유 비밀과 학교 목적지는 GAS Script Properties, 서버의 보호된 설정/환경변수에서 관리한다. 클라이언트 보고 토큰·조회 토큰과 다른 키를 쓴다.
- GAS는 크기·서명·전송 시각(±5분)·학교 허용 목록·필드 타입을 검증한 뒤 쓰기 작업을 수행한다. 재전송은 원래 report_id를 유지하고 envelope 시각·서명만 갱신한다.
- 대상 URL은 승인된 `https://script.google.com/macros/s/.../exec`만 허용한다. ContentService 응답 리다이렉트는 허용된 HTTPS Google 호스트로 GET 조회하되 서명 본문을 재전송하지 않는다. 예기치 않은 307/308, 로그인 HTML 및 임의 호스트 리다이렉트는 실패로 처리한다. [ContentService 리다이렉트](https://developers.google.com/apps-script/guides/content)
- 성공 판정은 HTTP 200만으로 하지 않는다. JSON의 ok, report_id, 결과(updated/duplicate/stale)를 검증하며 auth_failed/schema_invalid/unknown_school은 자동 반복하지 않는다.
- 실제 Web App 실행 계정·접근 정책은 기관 Workspace 정책에 맞춰 배포 때 확정한다. 서버의 무인 POST를 허용할 수 없는 기관 정책이면 공개 설정을 강행하지 않고 배포를 보류한다.

## 시트 분리와 열 매핑

기본안은 **학교별 별도 스프레드시트 + 고정 Devices 탭**이다. 학년은 C열 필터로 구분한다. 같은 파일의 탭 분리를 학교별 접근 권한 분리로 취급하지 않는다. 허용된 school_code → spreadsheet_id 매핑은 GAS 관리자 설정에서만 관리한다.

| 열 | 필드 | 저장 규칙 |
| --- | --- | --- |
| A | school_code | 문자열, 등록 코드 |
| B | school_type | elementary/middle/high |
| C | grade | 유효한 정수, 공용이면 빈 값 |
| D | hostname | 문자열 |
| E | serial | 문자열, 선행 0 유지 |
| F | status | running/completed/failed |
| G | office | 기존 Office 상태 |
| H | hancom | 기존 한컴 상태 |
| I | stage | Preflight 또는 01~06 |
| J | error_code | 고정 오류 코드 |
| K | installer_exit_code | 숫자 또는 빈 값 |
| L | model | 문자열 |
| M | mac | 문자열 |
| N | reboot_required | Boolean |
| O | observed_at | UTC ISO 문자열 |
| P | received_at | 서버 수신 UTC ISO 문자열 |
| Q | mirrored_at | GAS 반영 UTC ISO 문자열 |
| R | device_id | UUID 문자열 |
| S | report_id | UUID 문자열 |
| T | schema_version | 정수 |

- 첫 행 헤더와 열 수를 확인한다. 헤더 변경·열 이동이 발견되면 다른 열에 쓰지 않고 schema_mismatch로 중단한다.
- 쓰기 전에 ScriptLock을 획득하고 `(school_code, device_id)` 행 검색 → report_id/observed_at 비교 → A:T 쓰기를 같은 잠금 범위에서 수행한다. [LockService](https://developers.google.com/apps-script/reference/lock)
- 중복 보고는 성공 duplicate, 오래된 보고는 성공 stale로 응답한다. 동일 시각의 다른 보고는 기존 행을 유지한다.
- 고급 Sheets 서비스의 valueInputOption=RAW를 사용해 hostname·serial 등의 문자열을 수식/날짜/숫자로 해석하지 않게 한다. 요청의 객체 키 순서 대신 고정 열 배열로 변환한다. [RAW 쓰기](https://developers.google.com/workspace/sheets/api/samples/writing)
- 자동화 소유 열 A:T는 사람이 편집·정렬하는 동안 충돌할 수 있으므로 필터 보기를 사용하고 해당 범위를 보호한다. 수동 메모는 U열 이후에 둔다. 설치 라이선스·토큰·서명은 시트에 기록하지 않는다.

## 승인 후 검증 계획

- 기존 Phase 3 API/PowerShell 회귀 테스트 유지, 기존 SQLite 마이그레이션·학교 미지정 호환 검증.
- 학교 토큰 불일치, 학제별 잘못된 grade, 공용 null grade, 동일 hostname/serial의 학교 간 분리 검증.
- BackgroundTasks 등록, DB 커밋 후 응답, 실제 HTTP에서 GAS 지연과 클라이언트 응답 분리 검증.
- 실패/재시작 후 outbox 재전송, 중복 worker, 응답 유실, 역순 이벤트, 인증 실패 및 제한 재시도 검증.
- GAS 모의 서비스로 서명/시각/필드/고정 열/선행 0/수식 입력/잠금 경합·RAW 옵션 검증.
- 20~50대 동시 이벤트 시험 및 실제 GAS 테스트 시트 소규모 인수 시험을 구분한다. 실제 계정·Web App URL·테스트 시트 준비와 쓰기 승인은 구현 검증 후 요청한다.

## 이번에 승인받을 기본안

단방향 BackgroundTasks 릴레이 + SQLite outbox, 학교별 토큰과 스프레드시트, 초등 1~6/중고 1~3 및 공용 null grade, A:T 고정 RAW 열, HMAC 서명 및 제한 재시도를 승인 대상으로 제안한다. 실제 학교 코드 목록·시트 ID·키는 지금 제출하지 않아도 구현을 진행할 수 있으며 운영 설정 단계에서 별도로 준비한다.
