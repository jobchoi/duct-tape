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

개발 환경의 PowerShell 7.4.6/Linux에서 검증했습니다. Windows PowerShell 5.1, 실제 UNC·USB·한글/공백 경로, Hwp 버전 판별, 실제 ODT/MSI/VC++ 설치·구버전 제거 및 GUI 미노출은 Windows 테스트 기기의 인수 검증이 남아 있습니다. 설치되지 않은 서버·Wiki 연동 기능을 검증 완료로 취급하지 않습니다.
