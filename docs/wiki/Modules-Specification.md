# 모듈 상세 명세

[[Home]] · [[Deployment-Guide]]

## 공통 실행 계약

Windows PowerShell 5.1을 목표로 합니다. 각 01~06 모듈은 필수 문자열 `-StateFile`을 받고 Scripts/Common.ps1을 dot-source합니다. Main.bat은 `%TEMP%\Tapbook_State.json`을 전달합니다. JSON 파일명은 고정 API가 아니며 단독 실행 시 원하는 경로를 지정할 수 있습니다. 성공은 종료 코드 0, 실패는 1입니다. Main은 05를 포함한 모든 단계의 실패를 확인합니다.

배포 루트는 Common.ps1 자신의 `$PSScriptRoot` 부모입니다. 모듈의 짧은 bootstrap 경로 계산은 공통 파일을 찾기 위한 것이며 실제 배포 경로 변수는 Common에서만 정의합니다. `$MyInvocation` 경로 계산은 제거했습니다.

## Scripts/Common.ps1

| 함수 | 계약 |
| --- | --- |
| Read-DeploymentState(Path) | UTF-8 JSON 읽기, OfficeState/HancomState 존재 확인. 읽기·파싱 실패는 STATE_READ_FAILED |
| Write-DeploymentState(Path, State) | UTF-8 JSON 직렬화 후 동일 디렉터리 임시 파일을 목적지로 이동. 실패 시 STATE_WRITE_FAILED 및 임시 파일 정리. 한 기기에서 배포 1개 실행을 전제로 하며 동시 writer 잠금은 없음 |
| Write-DeploymentLog(Message, Level) | 화면과 `%TEMP%\duct-tape\Deployment.log`에 기록. 로그 쓰기 실패는 경고만 출력. 호출자는 고정 안내·코드만 전달 |
| Get-HancomKey | Config/HancomKey.txt 읽기. 누락·읽기 실패·공백·예제·여러 줄·명령행 특수문자 거부. 영숫자와 구분 하이픈만 허용하며 실제 라이선스 유효성을 검사하지 않음 |
| Assert-DeploymentFile | 파일 누락은 MEDIA_MISSING |
| Unblock-DeploymentFiles | 배포 루트 파일의 Unblock-File 수행. 일부 실패는 UNBLOCK_INCOMPLETE 경고. 기관 정책 해제를 보장하지 않음 |
| Assert-HancomSilentConfiguration | Hancom 아래 setup.ini 검색. 모든 LevelOption 값이 1이어야 함. 없거나 다르면 실패. 공유 매체를 수정하지 않음 |
| Invoke-DeploymentProcess | 숨김·동기 실행, 종료 코드 기록. 기본 허용 코드 0/3010. 인수·원문 예외는 로그에 출력하지 않음 |
| Set-RebootRequired | 3010이면 상태 RebootRequired=true 유지 |
| Write-DeploymentFailure | 허용된 고정 오류 코드만 출력. 기타 예외는 OPERATION_FAILED로 축약하여 민감값 노출 방지 |

PowerShell 소스는 Windows PowerShell의 한글 해석을 위해 UTF-8 BOM으로 저장합니다. 상태 I/O는 `-Encoding UTF8`을 명시합니다.

## 모듈별 처리

| 파일 | 처리 및 출력 | 변경 작업 전 검증 |
| --- | --- | --- |
| 01_GetInfo.ps1 | BIOS/ComputerSystem CIM 정보, 상태 초기화, 차단 해제 | 키 검증 후 차단 해제 |
| 02_CheckOffice.ps1 | 두 Uninstall 레지스트리 경로에서 Microsoft Office 및 LTSC Professional Plus 2024 표시명 판별, OfficeState 저장 | 상태 읽기 |
| 03_RemoveOffice.ps1 | 설치 필요일 때 ODT `/configure remove.xml`, 종료 코드 검증 | 키, 상태, setup.exe/remove.xml/install.xml 존재 |
| 04_InstallOffice.ps1 | ODT `/configure install.xml`, 준비 로딩바와 Write-Progress 보존, 완료 시 OfficeState=정상 | 키, 상태, 매체 |
| 05_CheckHancom.ps1 | `C:\Program Files (x86)\Hnc\HOffice2024\Bin\Hwp.exe` 존재 및 ProductVersion `13.*` 확인 | 상태 읽기 |
| 06_InstallHancom.ps1 | 아래 한컴 설치 흐름 수행, 완료 시 HancomState=정상 | 키, 상태, MSI, VC++ x86, setup.ini |
| backup_1_06_InstallHancom.ps1 | 06으로 위임하는 호환 진입점. 이전 독립 설치 로직 제거 | 06의 검증을 동일하게 적용 |
| Scripts/Test-DeploymentPrerequisites.ps1 | Main 시작 시 키 검증. 실패 시 안내 및 코드 1 | 설치·제거 실행 없음 |

03/04/06은 상태가 정상 또는 설치 필요가 아니면 STATE_INVALID로 종료합니다. 설치 상태가 정상인 경우 설치를 건너뜁니다. 키는 Main 및 설치 모듈 진입 시 항상 필요합니다.

## 06 한컴 설치 순서

1. 키·상태·Hwp130.msi·VC_redist.x86.exe·setup.ini LevelOption=1 검증.
2. Install/setup/msiexec 잔존 프로세스 강제 종료, 2초 대기.
3. 레지스트리에서 한컴오피스 구버전 검색. MSI GUID는 `/x ... /qn /norestart`; EXE는 실행 파일과 기존 인수를 분리해 `/s /v"/qn"` 추가. 잘못된 제거 명령은 안전 종료.
4. 구버전 MSI 제거는 0/1605/1614/3010 허용. 다른 제거 실패는 중단. 3초 대기.
5. VC++ x86 `/install /quiet /norestart`, 성공 코드 확인, 3초 대기.
6. `msiexec /i "...Hwp130.msi" /qn AGREETOLICENSE=yes PIDKEY=... /norestart`. 종료 코드 0/3010만 성공.
7. 재부팅 필요 및 설치 상태 저장. Office 정품 인증은 별도 확인 대상.

강제 종료는 다른 설치 작업에도 영향을 줄 수 있으므로 동시 설치를 피합니다. MSI 상세 `/l*v`는 키 노출 방지를 위해 사용하지 않습니다. OS 정책이나 설치 패키지가 자체 생성하는 로그와 프로세스 인수의 노출까지 차단하지는 못합니다.

## 상태 및 실패 기록

01이 생성하는 필드: ComputerName, SerialNumber, Model, Manufacturer, OfficeState, HancomState, Timestamp, RebootRequired. Timestamp는 수집 시각입니다. 후속 모듈은 알 수 없는 필드를 보존합니다. 오류는 로컬 로그와 프로세스 종료 코드로 보고하며 Phase 3에서 MAC 수집과 중앙 보고를 추가했습니다. [[Central-Monitoring]]에 전송 스키마가 있습니다.

## Phase 3 보고 연결

Common의 Send-DeploymentEvent는 ReportStatus.ps1을 호출하며 모든 보고 오류를 설치 흐름에서 격리합니다. 01~06의 시작·완료 및 Write-DeploymentFailure에서 호출합니다. Invoke-DeploymentProcess는 마지막 설치 종료 코드를 보고용으로 보존합니다. 01은 MAC을 상태에 추가하며 기존 미지 필드 보존 계약을 유지합니다. ReportStatus.ps1은 설정을 확인하고 허용 필드만 POST하며 설정이 없거나 비활성화이면 전송하지 않습니다. Main의 키 파일 누락 분기도 실패 보고 후 기존 종료 코드 1을 유지합니다.
