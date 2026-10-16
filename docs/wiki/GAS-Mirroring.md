# GAS 배포 설정 및 현장 테스트 체크리스트

[[Home]] · [[Central-Monitoring]]

기준 커밋: `2067162`. 문서 작성만 완료했으며 실제 배포·시트 쓰기·Windows 설치는 별도 승인 후 수행한다. 아래 `<...>`는 치환 자리표시자이며 실제 비밀값이 아니다.

## 1. 테스트 스프레드시트

- [ ] 학교별 테스트용 스프레드시트를 만들고 탭 이름을 정확히 `Devices`로 설정한다.
- [ ] 아래 탭 구분 한 줄을 A1에 붙여 넣는다. A1:T1의 순서·철자·열 수를 유지한다.

```text
school_code	school_type	grade	hostname	serial	status	office	hancom	stage	error_code	installer_exit_code	model	mac	reboot_required	observed_at	received_at	mirrored_at	device_id	report_id	schema_version
```

| 열 | 필드 | 열 | 필드 |
| --- | --- | --- | --- |
| A | school_code | K | installer_exit_code |
| B | school_type | L | model |
| C | grade | M | mac |
| D | hostname | N | reboot_required |
| E | serial | O | observed_at |
| F | status | P | received_at |
| G | office | Q | mirrored_at |
| H | hancom | R | device_id |
| I | stage | S | report_id |
| J | error_code | T | schema_version |

- [ ] GAS 배포 계정에 테스트 파일 편집 권한을 부여한다. 시트 자체는 공개하지 않는다.
- [ ] A:T는 자동화 소유 영역으로 보호하고, 수동 메모는 U열 이후에 둔다. 행 순서 변경 대신 필터 보기를 사용한다.
- [ ] 학년은 필수 정수: elementary 1~6, middle/high 1~3. null·문자열·Boolean은 거부한다.
- [ ] 문자열은 코드의 RAW 쓰기를 유지한다. `serial=000123`과 `hostname==1+1`이 숫자/수식으로 변환되지 않는지 시험한다.

## 2. GAS 프로젝트·Script Properties

- [ ] 테스트용 Apps Script 프로젝트에 `GoogleAppsScript/Code.gs`와 `appsscript.json`을 반영한다.
- [ ] 프로젝트 설정에서 manifest 표시를 켜고, 서비스의 Google Sheets API v4(`Sheets`)를 확인한다. 표준 Cloud 프로젝트를 연결했다면 해당 프로젝트에서도 Sheets API를 활성화한다. [공식 안내](https://developers.google.com/apps-script/guides/services/advanced)
- [ ] 프로젝트 설정 → 스크립트 속성에 다음 **두 JSON 문자열**을 등록한다. OS 환경변수와는 별개 저장소이다.

| 속성 이름 | 값의 구조 |
| --- | --- |
| RELAY_KEYS | `{"school-e01-v1":"<HMAC_SECRET_FROM_SECRET_STORE>"}` |
| SCHOOLS | `{"SCHOOL_E01":{"school_type":"elementary","spreadsheet_id":"<TEST_SPREADSHEET_ID>","key_id":"school-e01-v1"}}` |

- [ ] HMAC 비밀은 무작위 32자 이상으로 생성·보관하고 서버 `DUCT_GAS_E01_SECRET`과 같은 값을 등록한다. 보고/조회 토큰과 공유하지 않는다.
- [ ] school_code와 key_id는 서버 설정과 일치시킨다. 다른 학교는 별도 키와 스프레드시트로 추가한다.
- [ ] 실제 속성·토큰·시트 ID는 문서/소스/스크린샷/실행 로그에 붙여 넣지 않는다. 프로젝트 편집자는 속성을 볼 수 있으므로 담당자만 허용한다.

## 3. 웹앱 배포와 서버 설정

- [ ] 배포 승인 후 배포 → 새 배포 → 웹 앱, 실행 주체는 배포 계정으로 선택한다.
- [ ] 현재 서버는 Google 로그인 없이 HMAC으로 인증한다. 기관 정책이 허용할 때만 비로그인 호출 가능한 접근 설정을 선택한다. 정책상 불가하면 배포를 멈추고 인증 방식을 재설계한다. [Web App 공식 안내](https://developers.google.com/apps-script/guides/web)
- [ ] 배포 계정의 Sheets 권한 승인을 완료하고 `/exec` URL을 서버 학교 설정에 등록한다. `/dev`는 운영 릴레이 URL로 사용하지 않는다.
- [ ] 코드 변경 시 배포 관리에서 새 버전을 반영한다. 브라우저 GET만으로 성공 판정하지 않는다(현재 doPost 수신부).

| 위치 | 설정 | 의미 |
| --- | --- | --- |
| 서버 환경 | DUCT_SCHOOLS_PATH | 실제 `Config/schools.json` 경로 |
| 학교 설정 | school_type, gas_url, key_id | 학제, 승인된 `/exec` URL, GAS 키 식별자 |
| 학교 설정 | report_token_env | `DUCT_SCHOOL_E01_TOKEN` 등 실제 환경변수 **이름** |
| 학교 설정 | secret_env | `DUCT_GAS_E01_SECRET` 등 실제 환경변수 **이름** |
| 서버 환경 | DUCT_SCHOOL_E01_TOKEN | 해당 학교 클라이언트 Bearer 토큰 |
| 서버 환경 | DUCT_GAS_E01_SECRET | RELAY_KEYS의 해당 HMAC 비밀과 동일한 값 |
| 서버 환경 | DUCT_REPORT_TOKEN / DUCT_READ_TOKEN | 기존 학교 미지정 보고용 / 중앙 조회용, 각각 다른 32자 이상 토큰 |
| 서버 환경 | DUCT_DB_PATH | 테스트 전용 SQLite 경로; 운영 DB와 분리 |

실제 학교 설정은 `Config/Schools.json.example`에서 로컬로 준비한다. 환경변수 이름은 임의 지정 가능하지만 설정의 참조명과 실제 주입명이 반드시 같아야 한다. `.env` 자동 로딩은 없으며 서버 프로세스에 환경변수를 주입한 뒤 시작한다. GAS JSON의 `ok`와 `report_id`까지 확인해야 성공이며 HTTP 200만으로 판단하지 않는다.

## 4. 가짜 이벤트 검증

사전 조건: 테스트 DB·학교·시트만 사용, 모든 시계 UTC 동기화, 라이선스/실제 자산 정보 대신 가짜 값 사용. API 입력은 새 UUID device_id/report_id, school_code, 정수 grade, hostname, serial, model, mac, office, hancom, stage, status, observed_at으로 구성한다. stage는 Preflight 또는 01~06, status는 running/completed/failed, observed_at은 시간대 포함 ISO-8601이다. 원문 토큰·서명은 시험 결과에 남기지 않는다.

| 확인 | 절차 | 합격 기준 |
| --- | --- | --- |
| [ ] 정상 경로 | 학교 Bearer 토큰으로 가짜 기기 1건을 POST /api/report | accepted=true → outbox sent → 지정 학교 Devices에 1행, A:T 값 일치 |
| [ ] API 중복 | 동일 report_id·본문을 다시 POST | updated=false, outbox/시트 행 증가 없음 |
| [ ] GAS 중복 | 최초 서명된 릴레이 이벤트를 같은 report_id로 GAS에 직접 재전송 | JSON result=duplicate, 같은 행 유지 |
| [ ] 서명 위조 | 서명 완료 후 signature 1글자를 변경하거나 payload_json만 변경해 GAS에 직접 POST | auth_failed, 시트 변경 없음 |
| [ ] 역순 | 같은 device_id, 새 report_id와 과거 observed_at으로 전송 | 최신 상태 유지; GAS 직접 검증 시 result=stale |
| [ ] 학교 격리 | A학교 토큰으로 B학교 school_code를 API에 전송 | HTTP 403, 큐·시트 변경 없음 |
| [ ] 학년 | 누락/null/문자열/범위 밖 값을 전송 | API 422; 직접 GAS 서명 시험 시 schema_invalid |
| [ ] RAW | 새 시험 기기에 serial `000123`, hostname `=1+1` 지정 | 문자 그대로 유지, 수식 실행 없음 |
| [ ] 실패 복구 | 테스트 GAS 목적지 실패 후 원인 복구·실패 큐 재실행 | 설치/API 수신은 유지, 복구 후 sent, 중복 행 없음 |

GAS 직접 시험은 로컬 시험 도구에서 설정의 비밀을 읽어 서명한다. envelope는 schema_version=1, key_id, sent_at, payload_json, signature이며 `HMAC-SHA256(secret, sent_at + 개행 + payload_json UTF-8)`의 소문자 hex를 사용한다. 시각은 UTC 마이크로초 6자리 `+00:00` 형식이며 sent_at은 ±5분 이내여야 한다. 재전송은 payload/report_id를 유지하고 sent_at·서명만 갱신한다. 서버 outbox가 API 중복을 먼저 제거하므로 API 재전송만으로 GAS 중복 방어를 검증했다고 기록하지 않는다.

로컬 모의 검증: `node tests/test_gas_receiver.cjs`. 실제 클라우드 결과와 구분한다. 실패 큐 재실행은 같은 **테스트 DB·환경변수**로 다음 명령을 사용한다.

```text
python -m Server.replay_outbox --retry-failed --limit 50
```

이 명령은 해당 DB의 모든 failed 작업을 재대기 상태로 바꾼다. 종료 코드 0만 보지 말고 출력의 groups/worker_error 및 조회 토큰으로 GET /api/outbox를 확인한다.

## 5. Windows 단일 기기 보고·장애 격리

- [ ] 실제 설치 없이 테스트 기기 1대, 서버 테스트 인스턴스와 테스트 시트만 사용한다.
- [ ] Config/Monitoring.json을 예제로 준비한다: Enabled=true, SchoolCode=테스트 학교, Grade=정수, ServerUrl=테스트 HTTPS 원점, ReportToken=해당 학교 토큰. 기본 TimeoutSeconds=3, MaxAttempts=2, AllowHttp=false 유지.
- [ ] 실제 값은 로컬 설정에만 입력한다. Windows 보고 모듈은 실제 hostname·MachineGuid·MAC을 수집하므로 가짜 UUID만 쓰는 앞 단계와 구분한다.
- [ ] 다음과 같이 임시 상태 파일을 준비하고 **ReportStatus.ps1만** 실행한다. Main.bat/설치 모듈은 실행하지 않는다.

```powershell
$testState = Join-Path $env:TEMP 'duct-tape-field-test.json'
@{ OfficeState='정상'; HancomState='정상'; SerialNumber='TEST-SERIAL'; Model='TEST-MODEL'; RebootRequired=$false } |
    ConvertTo-Json | Set-Content -LiteralPath $testState -Encoding UTF8
powershell -NoProfile -File .\Scripts\ReportStatus.ps1 -StateFile $testState -Stage 06 -Status completed
Write-Host 'REPORT_CALL_RETURNED'
```

- [ ] 정상 시 대시보드·GET /api/outbox·테스트 시트에서 동일 기기를 확인한다. 보고 스크립트는 실패도 격리하므로 종료 코드만으로 전송 성공을 판정하지 않는다.
- [ ] 테스트 서버를 중지하고 같은 보고 명령을 실행한다. REPORT_UNAVAILABLE 경고 후 REPORT_CALL_RETURNED까지 도달하는지 확인한다. 기본 HTTP 대기 예산 약 7초 외에 DNS·기기 조회 시간이 추가될 수 있으므로 소요 시간을 기록한다.
- [ ] 서버 복구 후 보고를 다시 실행해 최신 상태가 갱신되는지 확인한다. 클라이언트에는 영속 재전송 큐가 없으므로 서버 다운 중 유실된 보고의 자동 복구를 기대하지 않는다.
- [ ] 별도 시험으로 서버는 유지하고 GAS 경로만 실패시키면, 서버 DB/outbox에는 남아야 한다. 서버 다운과 GAS 다운을 서로 다른 장애로 기록한다.
- [ ] 실제 Main.bat 설치 중 장애 격리 검증은 설치 매체·관리자 승인 확보 후 별도 수행한다. 이번 보고 전용 시험으로 실제 설치 인수 완료를 선언하지 않는다.

## 6. 기록·종료

- [ ] 기록: 시험일, 코드 커밋, Windows/PowerShell 버전, 시나리오, 합격/실패, 소요 시간, 고정 오류코드. 비밀값·원문 인증 요청은 기록하지 않는다.
- [ ] 실패가 있으면 다중 기기 배포를 보류한다. 성공 후 5대 → 20~50대 확대 계획을 별도 승인받는다.
- [ ] 시험 종료 후 테스트 보고 설정을 비활성화하고 운영자 승인에 따라 테스트 행/DB를 정리한다.
