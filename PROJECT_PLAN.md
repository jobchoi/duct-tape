# duct-tape 프로젝트 계획

## 운영 원칙 및 현재 상태

- 상태 표기: `[ ]` 대기, `[/]` 진행 중, `[x]` 완료.
- 각 Phase 진입 전 구체적인 작업 계획과 영향 파일을 제시하고 사용자 승인을 받는다.
- 승인된 Phase만 구현한다. 작업 완료 시 이 문서를 갱신하고 결과, 검증 내용, 남은 항목을 보고한다.
- 브랜치 전략: `main`은 검증된 배포본, `develop`은 통합, `feature/*`는 Phase별 작업이다.
- Phase별 feature 브랜치는 `develop`에서 분기한다. 통합 및 배포는 검증과 리뷰를 거친다.
- 현재 확인: `main`, `develop` 존재, 현재 브랜치 `feature/phase-4-gas-mirroring`. 기존 코드는 `Main.bat`, `Modules/01`~`06`에 있다.
- 현재 단계: **Phase 3 커밋·원격 동기화 완료, Phase 4 설계 승인 대기**. 현재 Phase 4 준비 브랜치. Windows 현장 검증은 계속 대기.

## 반드시 보존할 동작

- 학교 Wi-Fi 및 SMB/UNC 또는 HTTP 배포 환경에서 Windows 20~50대 운영을 지원한다.
- `$PSScriptRoot`를 기준으로 동적 상위 경로 `$DeployRoot`를 계산한다. `$MyInvocation`으로 회귀하지 않는다.
- Office LTSC 2024: ODT `setup.exe /configure install.xml`, 백그라운드 사일런트 설치, 사용자 안내 로딩바를 유지한다.
- 한컴오피스 2024: `setup.ini`의 `LevelOption=1`, 잔존 `Install`/`setup`/`msiexec` 종료, 구버전 사전 제거, VC++ x86 런타임 선행 설치를 유지한다.
- 한컴 설치는 내부 `Hwp130.msi`에 `msiexec /i ... /qn AGREETOLICENSE=yes PIDKEY=...`를 전달한다. 실제 키는 코드·문서·로그·관제 데이터에 기록하지 않는다.
- 네트워크 파일 실행 보안 경고 방지를 위한 `Unblock-File` 처리를 유지한다.
- 기존 동작과 요구사항이 다르면 차이를 기록하고 해당 Phase 승인 범위에서 보완한다.

## 사전 계획

- [x] 요구사항 및 보존해야 할 기술 히스토리 정리.
- [x] 저장소 파일 구조와 Git 브랜치 상태 확인.
- [x] 전체 Phase별 작업 및 승인 절차 초안 작성.
- [x] Phase 1 계획에 대한 사용자 승인.

## Phase 1 — 거버넌스 및 보안 인프라

예정 브랜치: `feature/phase-1-governance-security`

- [x] 승인 후 `develop`에서 feature 브랜치 생성 및 체크아웃.
- [x] 기존 설정, 키 참조 위치 및 추적 파일 점검. 발견한 실제 키는 출력하지 않는다.
- [x] `.gitignore`에 `Config/HancomKey.txt` 및 실제 제품키 포함 XML/JSON 경로 추가. 템플릿은 추적 가능하게 유지한다.
- [x] 이미 추적된 민감 파일은 ignore만으로 보호되지 않으므로 별도로 확인하고 조치 범위를 보고한다. Git 이력 재작성은 별도 승인 대상으로 둔다.
- [x] `Config/HancomKey.txt.example` 생성: 실제 키 없이 입력 형식 안내.
- [x] 키 누락·공백·템플릿 값에 대한 안전한 종료 로직 설계. 프로세스 종료·제거·설치보다 먼저 검증하고 오류에 키를 노출하지 않는다. 런타임 적용은 Phase 2에서 수행한다.
- [x] `README.md`: 개요, 요구사항, 설치 매체·라이선스 준비, 빠른 시작, 브랜치 운영 안내.
- [x] `docs/ARCHITECTURE.md`: 현재 구조, 목표 구조, 배포/상태/관제 데이터 흐름, 키 검증 설계. 계획 기능과 구현 기능 구분.
- [x] `docs/TROUBLESHOOTING.md`: 한컴 GUI 노출, 1603, UNC 경로 유실, 보안 경고 대응과 검증 방법 정리. 미검증 항목은 명시.
- [x] ignore 규칙과 예제 파일 추적 가능 여부, 문서 경로 및 비밀정보 비노출 확인.
- [x] 완료 내역을 기록하고 Phase 2 계획·영향 파일을 제시하여 승인 요청.

영향 파일: 보안 점검 중 발견한 키 의심 주석 제거를 위한 `Modules/backup_1_06_InstallHancom.ps1`(실행 로직 변경 없음), `PROJECT_PLAN.md`, `.gitignore`, `Config/HancomKey.txt.example`, `README.md`, `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`.

## Phase 2 — PowerShell 공통화 및 모듈 경량화

예정 브랜치: `feature/phase-2-powershell-refactor`

- [x] Phase 진입 승인 및 브랜치 생성.
- [x] `Main.bat`, `Modules/01`~`06`의 호출 순서, 인코딩, 종료 코드, 상태 파일 계약 조사.
- [x] `Scripts/Common.ps1`: 경로 계산, 인코딩 처리, 로깅, 상태 JSON I/O 공통화 및 dot-sourcing 적용.
- [x] 현재 `%TEMP%\Tapbook_State.json` 계약과 목표 상태 파일 명칭을 정리하고 호출부와 일관되게 유지.
- [x] `Modules/04_InstallOffice.ps1`, `05_CheckHancom.ps1`, `06_InstallHancom.ps1` 경량화 및 설치 옵션 보존.
- [x] `Modules/01`~`03` 중복 코드 정리. `03_RemoveOffice.ps1`에 남은 `$MyInvocation` 기반 경로 계산 제거.
- [x] Phase 1의 키 검증 설계 적용 및 키가 없는 경우 변경 작업 전 안전 종료.
- [x] setup.ini LevelOption=1 처리, VC++/제거 종료 코드, MSI 로그 키 비노출 검증 보완.
- [x] 백업 스크립트의 유지·보관 방침 결정 및 필요 시 `Main.bat` 호출부 조정.
- [ ] Windows에서 로컬/UNC 경로, 키 누락, 상태 I/O, 설치 실패·성공과 로딩 표시 검증. 실제 설치가 필요한 검증은 테스트 기기에서 수행하고 미실행 항목을 구분.
- [x] docs/wiki/Home.md, Modules-Specification.md, Deployment-Guide.md 작성 및 문서·진행 상태 갱신.
- [x] Phase 3 진입 승인.

예상 영향 파일: `Scripts/Common.ps1`, `Modules/01`~`06`, 필요 시 `Main.bat` 및 백업 스크립트, 관련 문서.

## Phase 3 — FastAPI 중앙 관제 및 대시보드

예정 브랜치: `feature/phase-3-central-monitoring`

- [x] Phase 진입 승인 및 실제 파일 목록 확정.
- [x] 보고 스키마 정의: Hostname, Serial, Model, MAC, Office/Hancom 상태, 에러코드, 보고 시각 및 기기 식별 기준.
- [x] `Server/server.py`: `POST /api/report`, 입력 검증, SQLite 저장 및 반복 보고 갱신 처리.
- [x] `GET /`: 기기별 진행·완료·오류·최종 보고 시각을 표시하는 자동 갱신 테이블 대시보드.
- [x] `Scripts/ReportStatus.ps1`: `Invoke-RestMethod` 보고, 타임아웃 및 제한된 재시도. 관제 장애가 설치를 중단시키지 않도록 처리.
- [x] 클라이언트 진행/완료/실패 시 보고 연결, 서버 주소 및 접근 인증 설정 분리.
- [x] 의존성, 실행 방법, 방화벽/내부망 배치 및 데이터 보관 방침 문서화.
- [x] 정상·잘못된 보고, 중복 보고, 서버 장애, 20~50대 동시 보고 및 대시보드 출력 검증.
- [x] 운영/Wiki 문서 및 진행 상태 갱신.
- [ ] Windows PowerShell 5.1·기관 HTTPS/UNC 및 실제 브라우저·설치 매체 인수 검증.
- [x] Phase 3 커밋·원격 push·develop 통합 및 원격 동기화.
- [ ] 기관망 배포 및 Windows 현장 인수 승인/검증.

예상 영향 파일: `Server/server.py`, 서버 의존성·설정 예제 및 UI 파일, `Scripts/ReportStatus.ps1`, 공통/호출 모듈, `.gitignore`, 관련 문서. SQLite DB와 인증정보는 추적 제외.

## Phase 4 — GAS 단방향 웹훅 릴레이 (설계 승인 대기)

브랜치: `feature/phase-4-gas-mirroring`

- [x] Phase 3 커밋/push 및 develop 동기화 후 준비 브랜치 생성.
- [x] 이번 범위를 FastAPI BackgroundTasks → GAS → Sheets 단방향으로 확정. 역방향은 별도 승인 대상.
- [x] [설계안](docs/PHASE4_DESIGN.md)에 영향 파일·학교/학년 계약·고정 열 매핑·검증 계획 기록.
- [ ] 사용자 구현 승인.
- [ ] 학교별 보고 인증·school_code/grade 스키마·기존 SQLite 마이그레이션 구현.
- [ ] BackgroundTasks, SQLite outbox, HTTPS POST 및 제한 재시도·응답 검증 구현.
- [ ] GoogleAppsScript/Code.gs: 서명 검증·학교별 목적지·A:T 고정 RAW 쓰기·잠금·중복/역순 처리 구현.
- [ ] 클라이언트 메타데이터·대시보드 필터·비밀값 없는 설정 예제·운영 문서 작성.
- [ ] 서버/PowerShell/GAS 모의 테스트 및 20~50대 동시 이벤트 검증.
- [ ] 실제 GAS 테스트 배포·시트 쓰기 승인 및 인수 검증.
- [ ] 완료 결과 보고 및 커밋·통합 승인.

이번 턴은 계획 문서만 수정한다. 상세 영향 파일은 docs/PHASE4_DESIGN.md를 따른다.

## 작업 기록

| 날짜 | 작업 | 결과 |
| --- | --- | --- |
| 2026-09-21 | 저장소 확인 및 계획 초안 작성 | `develop` 확인. `PROJECT_PLAN.md`만 생성. Phase 1 승인 대기. |

| 2026-09-21 | Phase 1 승인 및 구현 | feature 브랜치 전환, 문서·ignore·템플릿 작성. 백업 주석의 키 의심 값 제거, 기존 이력 미변경. 정적 검증 완료. Phase 2 승인 대기. |

## Phase 1 검증 결과 및 남은 조치

- [x] 실제 키·XML/JSON·로그 제외 및 예제 추적 가능 여부: `git check-ignore --no-index` 15개 사례 통과.
- [x] 문서 내부 링크, 코드 블록 짝 및 템플릿 단일 예제 값 확인.
- [x] 추적 텍스트의 제한된 제품키 형식 검사: 현재 일치 항목 없음. 모든 비밀정보 형식을 포괄하는 검사는 아님.
- [x] Main.bat 및 01~06 파일은 HEAD와 바이트 단위 동일. 백업 파일은 주석 값만 제거하고 실행 줄 동일.
- [x] `git diff --check` 통과. 실제 키 파일 생성·설치 실행·커밋·병합은 수행하지 않음.
- [ ] 기관 담당자의 기존 키 의심 값 유효성 및 교체 필요성 확인. Git 과거 이력은 별도 승인 없이 변경하지 않음.
- [ ] Windows/UNC/실제 설치 검증은 Phase 2 테스트 기기에서 수행.

승인된 Phase 2 범위: Phase 1 변경을 검토·커밋하고 develop에 통합한 뒤 `feature/phase-2-powershell-refactor` 생성. `Scripts/Common.ps1` 신설, `Modules/01`~`06` 공통화, `Main.bat` 사전 검증·종료 처리, 백업 스크립트 정리, 관련 문서 갱신. 경로·키·상태 I/O 및 오류 흐름을 검증하며 기존 설치 옵션과 로딩 표시를 보존한다. Windows 기기를 사용할 수 없으면 실제 설치 검증은 미실행으로 보고한다.

## Phase 2 결과 (2026-09-21)

- [x] Phase 1 커밋 `42617e4`, develop에 --no-ff 병합 후 Phase 2 feature 브랜치 생성.
- [x] 공통 루트·UTF-8 상태 I/O·로그·Unblock-File, 사전 키 검증, 01~06 공통화 완료.
- [x] ODT /configure 및 로딩 표시, Hwp.exe 13.* 판별, 한컴 MSI 옵션·프로세스 종료·VC++ 선행 설치 보존.
- [x] INI LevelOption=1은 배포 전에 설정하고 클라이언트는 검증만 수행. 잘못된 설정은 구버전 제거 전에 중단.
- [x] 제거/VC++/설치 종료 코드 검증, 3010 재부팅 플래그, 키 비노출 고정 오류 및 로컬 로그 적용. 상세 MSI 로그 옵션 제거.
- [x] 백업 스크립트는 06으로 위임. Main은 모든 단계의 실패를 확인하고 exit /b 1로 종료.
- [x] Wiki 파일 3개를 같은 이름으로 복사 가능한 링크 구조로 작성. 원격 게시는 수행하지 않음.
- [x] tests/Test-Common.ps1: PowerShell 7.4.6/Linux에서 구문·루트·키·UTF-8 상태·손상 JSON·INI·종료 코드·재부팅 테스트 통과.
- [x] 06 모듈 자식 프로세스 테스트: 키 누락 조기 종료, 가짜 설치기로 종료→VC++→MSI 순서와 필수 인수, 3010 상태 저장, 잘못된 INI에서 변경 호출 0회 확인.
- [ ] Windows PowerShell 5.1, 실제 로컬/UNC/USB, 05 파일 버전 판별, ODT/MSI/VC++ 실제 설치 및 GUI 미노출 인수 검증. 실행 환경·매체 부재로 미실행.

추가 파일: Scripts/Test-DeploymentPrerequisites.ps1, tests/Test-Common.ps1, .gitattributes(Windows 배치/PowerShell 줄바꿈). 실제 설치는 실행하지 않았다. Phase 2 변경은 이후 사용자 승인에 따라 a8ed71a로 커밋하고 develop에 병합했다.

- [x] 최종 정적 검증: UTF-8 BOM/줄바꿈, 문서·Wiki 링크, Main 사전 검사 및 7개 실패 분기, 공통 모듈 참조, Git 병합 계보, `git diff --check` 통과.

## Phase 3 결과 (2026-09-21)

- [x] 사용자 지시대로 Phase 2 커밋 `a8ed71a`, develop 병합 `36a97de`, `feature/phase-3-central-monitoring` 생성.
- [x] POST /api/report, SQLite 최신 기기 상태, GET /api/devices, 5초 갱신 대시보드 구현.
- [x] 보고/조회 토큰 분리, 알 수 없는 보고 필드 거부, 원문 입력을 노출하지 않는 오류 응답, 중복·역순 보고 방지.
- [x] ReportStatus.ps1 허용 필드·UTF-8 전송, 제한 재시도·타임아웃, 비활성 기본 설정, 01~06 시작/완료/실패 및 사전 키 누락 연결.
- [x] 서버 인증·스키마·중복/역순·재시작 영속성·저장소 장애·50대 동시 요청: Python 3.13 / FastAPI 0.141.1에서 pytest 15개 통과.
- [x] PowerShell 7.4.6 → 임시 loopback Uvicorn/FastAPI → SQLite → 조회 API 실제 HTTP 통합 테스트 1개 통과. 기기 정보만 가짜 값으로 대체하고 실제 설치는 실행하지 않음.
- [x] Test-Common.ps1 기존 설치 회귀 테스트와 Test-ReportStatus.ps1 보고 허용 필드·한글·재시도·서버 장애 테스트 통과.
- [x] 대시보드 JS 구문 및 모의 DOM 테스트: 텍스트 출력, 검색, 완료 집계, 통신 장애, 인증 실패, 연결 해제 통과.
- [x] Config/Monitoring.json.example, 서버 의존성 파일, 운영·Wiki 문서 및 DB/인증정보 제외 규칙 작성.
- [ ] 실제 브라우저 화면, Windows PowerShell 5.1/학교망 HTTPS·UNC·실제 설치 인수 검증 미실행.

서버 TestClient는 샌드박스 이벤트 루프 제한 때문에 승인된 샌드박스 밖에서 검증했고, HTTP 통합 테스트의 임시 loopback 서버는 검증 후 종료했다. 운영 서버·원격 Git·Wiki는 게시하지 않았다. 테스트 의존성의 httpx/BlockingPortal 사용 중단 예고 경고 2건은 테스트 통과와 별도로 남아 있다.

Phase 3는 후속 사용자 승인으로 c70d778에 커밋하고 feature 및 develop 원격 동기화를 완료했다. 운영 배포는 수행하지 않았다. Phase 4는 이번 사용자 지시에 따라 단방향 릴레이로 제한하며 구현 승인을 기다린다.

## Phase 4 준비 기록

- [x] 사용자 지정 메시지로 Phase 3 커밋 `c70d778` 생성.
- [x] origin/feature/phase-3-central-monitoring push 및 upstream 설정.
- [x] develop fast-forward 병합, origin/develop push 완료.
- [x] develop에서 feature/phase-4-gas-mirroring 생성·체크아웃.
- [x] docs/PHASE4_DESIGN.md 설계안 작성. 구현 코드·실제 GAS 배포·시트 쓰기는 미수행.
- [ ] 설계 및 구현 파일 목록에 대한 사용자 승인.
