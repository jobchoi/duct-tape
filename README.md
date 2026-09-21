# duct-tape

학교·교육기관의 Windows 기기 20~50대에 Office LTSC 2024와 한컴오피스 2024를 배포하는 자동화 프로젝트입니다. 현재 `Main.bat`이 PowerShell 모듈을 순차 실행하고 로컬 상태 JSON을 전달합니다.

Phase 1은 문서·라이선스 파일 보호 규칙을 정비한 단계입니다. 공통 모듈은 Phase 2, FastAPI/SQLite 관제는 Phase 3, Google Sheets 미러링은 Phase 4 예정이며 아직 구현되지 않았습니다.

## 요구사항

- 관리자 권한으로 실행할 Windows 기기와 Windows PowerShell. Phase 2 검증 기준은 Windows PowerShell 5.1이며 현재 환경별 호환성 검증은 미완료입니다.
- 기관에서 구매한 유효한 라이선스와 정식 설치 매체. 실제 키와 설치 파일은 저장소에 포함하지 않습니다.
- USB/로컬 폴더 또는 접근 가능한 SMB 공유 폴더. HTTP 배포는 같은 디렉터리 구조로 내려받은 후 실행하며 현재 자동 다운로드 기능은 없습니다.
- `%TEMP%` 상태 파일 쓰기 권한과 배포 루트의 `Logs` 쓰기 권한. 관리자 실행 계정에서도 공유 폴더에 접근할 수 있어야 합니다.
- 설치 전 작업 내용을 저장하고 다른 설치 작업이 없는지 확인합니다. 현재 한컴 모듈은 설치 프로세스를 강제 종료하고 구버전을 제거합니다.

## 빠른 시작

1. 저장소와 정식 매체를 아래 구조로 준비합니다. 설치 매체의 나머지 부속 파일도 보존합니다.

   ```text
   duct-tape/
   ├── Main.bat
   ├── Modules/                    # 01~06 모듈
   ├── Config/
   │   ├── HancomKey.txt.example    # 저장소용 예제
   │   └── HancomKey.txt            # 현장 준비: 실제 키 한 줄
   ├── Office/
   │   ├── setup.exe               # ODT
   │   ├── install.xml             # 기관용 설치 설정
   │   └── remove.xml              # 기관용 제거 설정
   ├── Hancom/
   │   └── Install/
   │       ├── Hwp130.msi
   │       └── VC_redist.x86.exe
   └── Logs/
   ```

2. 배포 루트의 PowerShell에서 예제를 복사하고 실제 키 한 줄을 입력합니다. 기존 키 파일은 덮어쓰지 않습니다.

   ```powershell
   if (-not (Test-Path .\Config\HancomKey.txt)) {
       Copy-Item .\Config\HancomKey.txt.example .\Config\HancomKey.txt
   }
   notepad .\Config\HancomKey.txt
   New-Item -ItemType Directory -Path .\Logs -Force | Out-Null
   ```

   `REPLACE_WITH_YOUR_LICENSE_KEY`는 유효한 키가 아닙니다. **현재 코드는 키 확인 전에 구버전을 제거하며 공백·예제 값도 거르지 않습니다.** 실행 전 운영자가 키와 매체를 확인해야 합니다. 사전 검증은 Phase 2에서 구현합니다.

3. 기관에서 검증한 `install.xml`, `remove.xml`을 준비합니다. 한컴 매체의 `setup.ini`에서 `LevelOption=1`을 확인합니다. 해당 설정의 자동 처리는 Phase 2 보완 대상입니다.
4. 테스트 기기에서 `Main.bat`을 우클릭하여 **관리자 권한으로 실행**합니다. Office 로딩바와 단계별 메시지를 확인합니다.
5. `%TEMP%\Tapbook_State.json`에서 상태를 확인하고 실제 앱 실행과 라이선스 상태를 별도로 점검합니다. 현재 Office 성공 메시지는 프로세스 종료 코드에 근거하며 정품 인증을 별도로 검증하지 않습니다.

로그는 `Logs\InstallLog.txt`와 `C:\Windows\Temp\HancomMSIInstall.log`입니다. MSI 상세 로그에 키가 포함될 가능성이 있으므로 원문을 저장소나 관제로 전송하지 않습니다. 공유 로그 동시 쓰기와 실패 상태 기록은 향후 개선 대상입니다.

## 라이선스 파일 관리

`.gitignore`는 Config 실제 설정, TXT/JSON/XML, Office/Hancom 매체와 로그를 제외합니다. 키 없는 템플릿은 `.example` 접미사를 사용합니다. `Office/`와 `Hancom/`은 전체 제외하므로 저장소용 예제는 `Config/`에 둡니다. 일반 JSON/XML도 기본 제외되므로 비밀정보 없는 설정은 리뷰 후 정확한 경로로 예외를 추가합니다.

ignore는 파일 내용 검사나 이미 추적된 파일·과거 이력 정리를 대신하지 않습니다. 백업 스크립트 주석의 키 의심 값은 Phase 1에서 제거했으나 과거 이력은 그대로입니다. 기관 담당자가 실제 사용 키인지 확인하고 유효한 키였다면 교체·재발급을 협의해야 합니다.

## 개발 및 문서

- `main`: 검증된 배포본, `develop`: 통합 브랜치, `feature/*`: Phase별 작업.
- 현재 브랜치: `feature/phase-1-governance-security`.
- 각 Phase는 계획과 영향 파일을 제시하고 승인 후 시작합니다. 검증·리뷰 후 develop에 통합하고 배포본을 main에 반영합니다.
- [전체 계획](PROJECT_PLAN.md) · [아키텍처](docs/ARCHITECTURE.md) · [문제 해결 기록](docs/TROUBLESHOOTING.md)
