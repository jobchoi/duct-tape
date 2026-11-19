# 최초 Office 설치 전 제거 단계 실패

2026-11-19. NUCBOX_M8에서 운영 서버의 전체 셋업을 실행했을 때 03_RemoveOffice.ps1이 실패했다. 11월 18일과 19일 같은 단계에서 실패했으며 최신 작업 ID는 `6a81f03c-3cef-40e8-9952-84b5f08e9a98`이다.

## 확인 근거

- 서버: 작업 failed/exit_code=1, 마지막 실패 모듈 03_RemoveOffice.ps1.
- 클라이언트: PROCESS_EXIT=-1, INSTALL_PROCESS_FAILED.
- Office 로그: `Downsell attempted without active ClickToRunSvc`, Application3 ExitCode=-1.
- 사용자의 서비스 조회: ClickToRunSvc 출력 없음. 사용자는 처음 설치하는 PC에 Office가 없었다고 설명했다.
- 서버 원본 remove.xml: Remove All=TRUE, Add 없음. Windows 포팅 여부·제조사 OS 변경·전체 레지스트리 상태는 확인하지 않았다.

## 수정

기존 OfficeState는 목표 Office 설치 필요 여부만 나타낸다. 03에서 별도 읽기 전용 탐지를 수행한다. 32/64비트 제거 레지스트리·ClickToRun 구성 흔적·ClickToRunSvc를 확인하며 Win32_Product는 사용하지 않는다.

| 상태 | 처리 |
| --- | --- |
| 목표 Office 정상 | 기존 흐름대로 제거 건너뜀 |
| Office 제품·ClickToRun 구성·서비스 모두 없음 | OFFICE_REMOVE_SKIPPED_NO_PRODUCT 로그 후 04 설치 단계로 진행 |
| 기존 MSI Office/Visio/Project 감지 | OFFICE_MSI_REMOVAL_REQUIRED로 중단, 별도 MSI 제거 절차 필요 |
| 기존 흔적이 있으나 서비스 없음 | OFFICE_C2R_SERVICE_MISSING으로 중단 |
| 서비스가 있으나 실행 중 아님 | OFFICE_C2R_SERVICE_NOT_RUNNING으로 중단 |
| 실행 중인 ClickToRun 서비스가 있고 MSI 충돌 없음 | 기존 제거 XML 실행 및 종료/재부팅 코드 처리 |

레지스트리 조회 오류는 실패로 처리한다. Office가 없는 경우를 설치 성공으로 기록하지 않는다. 실제 Office 설치·탐지는 후속 단계에서 수행한다. 03에서 무관한 한컴 키 검사는 제거했다. 고정 오류 코드는 Common 보고 및 진단 로그 허용 목록에 추가했다.

## 시험과 배포

검증·서버 반영 결과는 WORK_HISTORY에 기록한다. 운영 중인 기존 이미지에 필요한 파일만 교체한 파생 이미지를 만들어 관련 없는 v2 서버 기능을 함께 올리지 않는다. 각 환경의 Compose·인증 설정·SQLite 스냅샷·이전 이미지 ID를 보관하고 ZIP 파일 해시와 API/상태를 확인한다.

## 기존 미니 PC 재시도

서버 교체만으로 ProgramData의 기존 에이전트가 자동 갱신되지는 않는다.

1. 관리자 화면에서 해당 PC 작업이 실패로 종료됐고 다른 작업이 없는지 확인한다.
2. 기존에 사용하던 **동일한 HTTPS 서버**의 `/client`에서 최신 에이전트 ZIP을 다운로드한다. 운영 PC를 v2의9443에 임의 재등록하지 않는다.
3. 새 폴더에 압축을 풀고 InstallAgent.bat을 관리자 권한으로 실행한다. 기존 로컬 등록 정보가 유효하면 재연결을 통해 갱신한다. 설치 원본과 제품 키는 보존한다.
4. 진행 중/결과 확인 중 경고가 나오면 ActiveJob.json을 삭제하지 말고 해당 작업 상태를 확인한다.
5. 관리자에서 셋업을 재시도한다. 03의 OFFICE_REMOVE_SKIPPED_NO_PRODUCT와 04의 설치 결과를 확인한다.

수정 후 미니 PC에서 실제 Office 설치 성공 여부는 현장 재시도 전까지 미검증이다.
