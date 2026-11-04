# 다음 환경에서 v2 작업 이어가기

갱신: 2026-11-04. 작업 브랜치: `feature/v2-mdm-ui`.
이 문서가 다음 작업의 시작점이다. 과거 기획은 날짜별 이력이며 현재 운영 배포 결과와 구분한다.

## 1. 브랜치와 프로젝트 경계

- DuctTape v2 기능과 인수인계 문서는 현재 기능 브랜치에 있다. main/develop 병합이나 운영 Pi의 v2 기능 배포를 이번 정리에서 수행하지 않는다.
- 블로그 웹서비스는 별도 저장소 [toyproject-HowToEasy](https://github.com/jobchoi/toyproject-HowToEasy)로 분리됐다. DuctTape에서 그 서비스 구현을 이어가지 않는다.
- QTP 편집 원칙은 editorial/qtp, DuctTape 구현/운영 기록은 docs에 있다.

## 2. 현재 구현 범위

| 기능 | 현재 상태·한계 | 참고 |
| --- | --- | --- |
| PC 정보 | BIOS 시리얼·제조사·모델 보고와 관리자 표시. 설치와 독립된 수집은 후속 | [관리 도구](ADMIN_TOOLS.md) |
| v2 앱 등록/선택 설치 | 관리자 앱 등록·검사·공개, 클라이언트 선택, MSI 규약·버전/해시 고정·결과 보고 | [앱 구현](V2_APPLICATIONS.md) |
| Argos MDM | 원본 다운로드·등록 URL/계정 확인·수동 설치/등록. 자동 등록은 목표에서 제외 | [수동 흐름](MDM_MANUAL_SETUP.md) |
| 관리자 기능 관리 | QR/MDM 토글 저장·서버 API 차단 | [관리 도구](ADMIN_TOOLS.md) |
| QR | 이름·입학년도·S/N 입력, 보고된 시리얼 활용, PNG 생성. A4 PDF는 미구현 | [관리 도구](ADMIN_TOOLS.md) |
| Office/한컴 | 기존 전체 셋업 유지. v2의 개별 앱 카탈로그로 전환하지 않음 | [앱 구현](V2_APPLICATIONS.md) |

새 앱은 기존 msi-v1 규약으로 처리 가능한 경우 UI 등록을 활용한다. 임의 EXE 실행이나 환경 설정 변경은 모두 지원되는 것으로 간주하지 않는다. 새 실행 방식은 탐지·실행·검증·종료 코드·재부팅·복구 계약을 먼저 정한다.

## 3. Pi 운영 현황 — 2026-11-04 확인

- 운영 루트: `/home/jobchoi/web-server`.
- DuctTape: `duct-tape/repo` 코드, `duct-tape/data/{db,media,temp,uploads}` 자료, `duct-tape/compose.yaml` 운영 정의.
- 실행 컨테이너: `duct-tape-duct-tape-1`, localhost 8000. 기존 실행 이미지를 유지한 경로 이관이며 v2 신기능을 배포한 작업이 아니다.
- Nginx/File Browser도 각 프로젝트로 이관했다. 포스팅 서비스와 Tailscale 매핑은 보존했다.
- 기존 my-server 원본·복구용 컨테이너와 프로젝트별 백업을 보존했다. 새 데이터에 운영 중 쓰기가 발생하므로 옛 데이터로 무조건 되돌리지 않는다.
- 웹/API·media.ready·DB·파일 해시·상위 status/doctor·서버 밖 백업 검증을 통과했다. Windows 실제 설치·외부 접속·서버 재부팅은 이관 검증에 포함하지 않았다.

상세: [Pi 이관/복구 기록](PI_STATUS_2026-11-04.md), [현재 배포 안내](PI_DOCKER.md). `deploy/compose.v2.yml`은 이전 부모/별도 체크아웃 레이아웃 예제다. 현재 운영 compose.yaml을 덮어쓰거나 기존 DB/포트에 v2를 연결하지 않는다. 별도 시험 DB·포트·자료·체크아웃을 준비하고 build/mount 경로부터 확인한다.

SSH 별칭 `raspberry-posting`은 현재 PC 설정이다. 다른 PC에는 SSH 키·호스트 등록·Tailscale 접속이 자동 복사되지 않는다. 비밀번호나 개인키를 Git/채팅에 넣지 않는다.

## 4. 새 환경 준비

```bash
git clone --branch feature/v2-mdm-ui git@github.com:jobchoi/duct-tape.git
cd duct-tape
python3 -m venv .venv
.venv/bin/python -m pip install -r Server/requirements.txt
.venv/bin/python -m pip install pytest
```

SSH가 없으면 clone URL을 `https://github.com/jobchoi/duct-tape.git`으로 바꾼다. 기존 체크아웃은 미커밋 변경부터 확인하고 해당 브랜치에서 `git pull --ff-only origin feature/v2-mdm-ui` 한다. Windows에서는 WSL 사용을 기준으로 한다.

`.env`, Office/한컴 원본·제품 키, 기관 설정·등록 정보, DB, 가상환경, 인증 토큰은 Git에 포함되지 않는다. 시험 환경에는 따로 준비하며 실제 값을 문서에 넣지 않는다. 서버 환경 변수는 개발용 셸에서 명시적으로 주입하거나 기존 관리 스크립트의 설정 로딩을 확인한다. `python -m uvicorn`이 .env를 자동 로드한다고 가정하지 않는다.

설치 원본 없이도 임시 DB·가짜 원본을 쓰는 테스트부터 실행할 수 있다.

```bash
.venv/bin/python -m pytest tests/test_admin_tools.py tests/test_managed_applications.py tests/test_application_catalog.py -q
```

실제 시험 서버는 운영 DB와 다른 DUCT_DB_PATH/DUCT_MEDIA_ROOT, 시험용 관리자 인증키를 설정하고 localhost의 별도 포트(예: 8001)로 실행한다. 서버 실행 예:

```bash
.venv/bin/python -m uvicorn Server.server:app --host 127.0.0.1 --port 8001
```

주소는 `/admin`, `/admin/apps`, `/admin/tools`, `/client/apps`. 실제 Windows 작업 전 최신 에이전트 규약·등록 서버·승인 대상 PC를 확인한다. 한 PC의 v1/v2 에이전트를 동시에 별도 설치해도 된다고 가정하지 않는다.

## 5. 다음 우선순위

1. **데스크톱 호환 확인:** 탭북 전용 모델 차단은 확인되지 않았다. Windows 데스크톱에서 등록·보고·설치·재부팅/결과를 검증한다. 조립 PC의 빈/기본 시리얼을 PC 식별이나 인증 근거로 사용하지 않는다.
2. **실패 후 재시도:** 관리자 버튼 → 요청/응답 → 작업 상태 → 에이전트 ActiveJob/로그를 같은 작업 ID로 대조한다. 이전 ‘버튼 무반응’이 재현되지 않았다는 이유로 해결 완료 처리하지 않는다.
3. **완료 후 앱 표시:** 셋업 완료와 Office/한컴 탐지 결과가 어긋나는 현장 보고를 실제 상태 파일·서버 보고로 확인한다. 현재 해결 완료로 간주하지 않는다.
4. **새 앱/설정 작업 논의:** 기존 MSI 등록 활용과 새 어댑터 개발을 구분한다. 실제 추가 대상의 파일 형식·무인 실행·탐지·재부팅 요구를 확인한 뒤 범위를 확정한다.
5. **후속 설계:** 다운로드 병목 측정/배포 분리, 다운로드 이어받기, 재부팅 복구·보고 재전송은 [멀티 서버 검토](MULTI_SERVER_PLAN.md)와 [v2 계획](V2_PLAN.md)을 참고한다. 분할 다운로드·자동 재개가 이미 구현됐다고 가정하지 않는다.

## 6. 검증·자동 진행 기준

과거 브라우저/API 검증 범위는 각 기능 문서에 있다. 이번 이동 준비에서 실행한 회귀 검증 결과는 WORK_HISTORY에 추가한다. 과거 성공과 새 PC/실제 Pi·Windows 시험을 구분한다.

현재 사용자 요청 범위의 읽기 전용 점검·로컬 구현·테스트·오류 수정·문서 기록은 매 단계 재승인을 기다리지 않고 진행한다. 운영 변경은 기존 사용자 승인 범위와 실행 환경 권한을 확인한다. 파괴적 작업·새 비용·외부 공개 등은 구체적 영향을 준비한 뒤 필요한 확인을 받는다. 새 기능을 임의로 운영에 배포하지 않는다.

## 새 작업 시작 요청 예시

> feature/v2-mdm-ui의 docs/NEXT_SESSION.md와 현재 Git 상태를 읽고 이어서 진행해 주세요. DuctTape만 다루고 별도 블로그 서비스는 변경하지 마세요. 우선 데스크톱 호환·실패 후 재시도·설치 완료와 앱 표시 불일치의 재현/검증부터 진행하고, 관련 테스트·오류 수정·기록까지 완료해 주세요. Pi의 현재 운영 경로와 시험 환경을 구분하고, 새로운 프로그램 실행 방식은 실제 대상과 규약을 확인한 뒤 확장해 주세요.
