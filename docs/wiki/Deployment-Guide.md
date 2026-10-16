# 배포 및 검증 가이드

[[Home]] · [[Modules-Specification]]

## 준비

- 관리자 권한 Windows 및 Windows PowerShell 5.1, 기관용 라이선스와 정식 설치 매체.
- 배포 루트에 Main.bat, Modules/, Scripts/, Config/, Office/, Hancom/ 구조를 유지합니다.
- Office/setup.exe, Office/install.xml, Office/remove.xml과 설치 원본을 준비합니다.
- Hancom/Install/Hwp130.msi, Hancom/Install/VC_redist.x86.exe와 나머지 원본 매체를 준비합니다.
- 매체의 setup.ini에 LevelOption=1을 설정합니다. 클라이언트는 읽기만 하므로 읽기 전용 공유에서도 검증 가능합니다. Hancom 아래 발견한 모든 setup.ini의 해당 값이 1이어야 합니다.
- Config/HancomKey.txt.example을 HancomKey.txt로 복사하고 실제 키 한 줄을 입력합니다. 영숫자·하이픈 형식이며 공백·여러 줄·예제 값은 허용하지 않습니다.
- 키와 매체는 Git 제외 대상입니다. 배포용 공유 폴더는 기관 계정에만 필요한 접근 권한을 부여합니다.

## 실행

1. 다른 설치가 진행 중이지 않은 테스트 기기에서 시작합니다. 한 기기에서 Main을 중복 실행하지 않습니다.
2. Main.bat을 관리자 권한으로 실행합니다. 키 파일 존재 및 내용 검증이 모든 모듈보다 먼저 수행됩니다.
3. UNC 공유는 pushd를 사용합니다. 관리자 계정의 공유 접근 권한을 확인합니다. HTTP 매체는 같은 구조로 로컬에 내려받은 후 실행합니다.
4. Office 준비 로딩바 및 설치 안내를 확인합니다. 로딩바는 실제 설치 완료율을 의미하지 않습니다.
5. `%TEMP%\Tapbook_State.json`과 `%TEMP%\duct-tape\Deployment.log`를 확인합니다. RebootRequired=true이면 재부팅하고 앱 실행·정품 인증을 별도로 확인합니다.

단독 실행 예:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Modules\05_CheckHancom.ps1 -StateFile "$env:TEMP\Tapbook_State.json"
```

## 문제 해결

| 코드·증상 | 확인 사항 |
| --- | --- |
| KEY_MISSING / KEY_UNREADABLE / KEY_INVALID | 키 파일 존재·읽기 권한·한 줄 입력·예제 제거. 실제 키를 로그나 문의에 첨부하지 않음 |
| STATE_READ_FAILED / STATE_INVALID | 01부터 정상 실행했는지 및 지정한 JSON 경로 확인 |
| STATE_WRITE_FAILED | TEMP 공간·쓰기 권한, 기기 내 중복 실행 확인 |
| MEDIA_MISSING | MSI/VC++/ODT/XML 위치 확인 |
| HANCOM_INI_MISSING / HANCOM_INI_INVALID | 원본 매체 setup.ini와 LevelOption=1 확인 |
| INSTALL_PROCESS_FAILED / 1603 | 직전 PROCESS_EXIT, 다른 설치, 구버전 제거, VC++ 및 재부팅 필요 여부 확인. 키 오류로 단정하지 않음 |
| UNBLOCK_INCOMPLETE / 보안 경고 | 공유 파일 권한·차단 표시·기관 정책 확인. 읽기 전용 매체는 배포 전에 차단 해제 |
| OPERATION_FAILED | 고정 오류만 기록하므로 현장 담당자가 권한·매체 상태를 점검. 진단 시 원문 인수/키 비노출 유지 |

Phase 1 이전의 공유 Logs/InstallLog.txt와 HancomMSIInstall.log는 더 이상 생성하지 않습니다. 과거 로그와 Git 이력의 키 의심 값은 별도 관리 대상입니다.

## 검증 범위

`tests/Test-Common.ps1`은 설치 프로그램을 실행하지 않고 구문, 루트 계산, 잘못된 키, UTF-8 상태, 손상된 상태, INI, 종료 코드와 재부팅 플래그, 키 누락 시 06 조기 종료를 검증합니다.

```powershell
powershell -NoProfile -File .\tests\Test-Common.ps1
```

개발 환경의 PowerShell 7.4.6/Linux에서 검증했습니다. Windows PowerShell 5.1, 실제 UNC·USB·한글/공백 경로, Hwp 버전 판별, 실제 ODT/MSI/VC++ 설치·구버전 제거 및 GUI 미노출은 Windows 테스트 기기의 인수 검증이 남아 있습니다. Phase 3 서버 자동 검증과 Windows 현장 검증은 구분하며 Wiki 원격 게시도 수행하지 않았습니다.

## Phase 3 중앙 보고

Config/Monitoring.json.example을 준비한 뒤 [[Central-Monitoring]]에 따라 서버 주소와 보고용 토큰을 설정합니다. 중앙 관제를 사용하지 않을 때는 설정을 만들지 않거나 Enabled=false로 둡니다. 관제 장애가 설치를 중단하지 않습니다.

## Office 2024 제품 키

`Config/OfficeKey.txt.example`을 `Config/OfficeKey.txt`로 복사하고 Office LTSC Professional Plus 2024 키만 한 줄로 입력한다. 형식은 영숫자 5자씩 5그룹을 하이픈으로 연결한 25자 키다. 예제 문구·공백·여러 줄은 거부한다. 실제 키는 Git 제외 파일에만 보관한다.

`Office/install.xml`은 제품/언어/설치 옵션만 담는 원본 설정으로 두며 PIDKEY에 실제 키를 직접 기록하지 않는다. `Scripts/OfficeConfiguration.ps1`이 설치 직전에 별도 키를 읽고 현재 실행 계정과 SYSTEM만 접근하는 임시 폴더의 XML에 PIDKEY를 주입한다. ODT 명령줄에는 임시 XML 경로만 넘긴다. 성공/실패 모두 임시 파일을 정리하고 원본 XML은 변경하지 않는다.

현재 구현은 ProPlus2024Volume 단일 제품에 적용한다. 2021/Standard/Excel 단품/Visio 등 여러 제품은 키와 판별 정책이 달라 별도 확장해야 한다. Office 키와 한컴 키는 사전 검증에서 확인해 제거 작업 전에 누락·형식 오류로 중단한다.

원본 키 파일은 평문이며 담당자/배포 계정으로 접근을 제한한다. ODT 설치 중에는 키를 포함한 임시 XML이 필요하다. 시스템 강제 종료는 finally 정리를 보장하지 못하므로 실행 계정의 임시 폴더 관리도 필요하다. 앱 실행·정품 인증 성공은 별도 확인한다.

서버의 비공개 매체 ZIP에는 Config/OfficeKey.txt와 HancomKey.txt를 포함하고, 공개 실행 도구 ZIP에는 포함하지 않는다. 실제 키를 로그·문의·Git에 남기지 않는다.

공식 참고: [ODT 구성 옵션](https://learn.microsoft.com/en-us/microsoft-365-apps/deploy/office-deployment-tool-configuration-options).
