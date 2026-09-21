# duct-tape

학교 Windows 기기 20~50대의 Office LTSC 2024·한컴오피스 2024 배포 자동화입니다. Main.bat과 PowerShell 01~06 모듈을 Scripts/Common.ps1 기반으로 공통화했습니다. FastAPI/SQLite 중앙 관제와 자동 상태 보고를 구현했습니다. Google Sheets 미러링은 Phase 4 예정입니다.

## 요구사항과 빠른 시작

1. 관리자 권한 Windows/Windows PowerShell 5.1, 기관 구매 라이선스와 정식 설치 매체를 준비합니다. 현재 런타임 테스트는 PowerShell 7.4.6/Linux에서 수행했으며 Windows 설치 인수 검증은 남아 있습니다.
2. Office/에 ODT setup.exe, install.xml, remove.xml 및 원본 매체를 배치합니다.
3. Hancom/에 전체 원본 매체를 배치합니다. Install/Hwp130.msi, Install/VC_redist.x86.exe 및 LevelOption=1로 준비한 setup.ini가 필요합니다.
4. Config/HancomKey.txt.example을 Config/HancomKey.txt로 복사하고 실제 키 한 줄을 입력합니다. 키는 영숫자·하이픈 형식이며 예제·공백·여러 줄은 거부합니다.
5. 다른 설치가 없는 테스트 기기에서 Main.bat을 관리자 권한으로 실행합니다. 키 누락·검증 실패 시 설치 전에 종료합니다. UNC/로컬 구조를 유지하고 HTTP 배포는 매체를 로컬로 내려받아 실행합니다.
6. `%TEMP%\Tapbook_State.json` 및 `%TEMP%\duct-tape\Deployment.log`를 확인합니다. RebootRequired=true이면 재부팅하고 앱 실행과 정품 인증을 점검합니다.

한컴 설치는 잔존 Install/setup/msiexec를 강제 종료하고 구버전을 제거합니다. 기기별 배포는 한 번에 하나만 실행합니다. 설치 안내 로딩바는 실제 설치 완료율이 아닙니다.

## 라이선스 및 Git 운영

실제 키·XML/JSON·매체·로그는 .gitignore로 제외하고 키 없는 예제만 추적합니다. 일반 XML/JSON도 기본 제외되므로 비밀정보 없는 설정은 리뷰 후 정확한 경로를 허용합니다. 예제는 Config/에 두며 Office/Hancom 전체 제외 규칙은 유지합니다.

백업 코드 주석의 키 의심 값은 Phase 1에서 제거했지만 Git 과거 이력은 그대로입니다. 기관 담당자의 유효성·교체 필요성 확인이 남아 있습니다. MSI 상세 로그 생성을 중단했으며 설치 인수와 키를 공통 로그에 기록하지 않습니다. OS 정책·패키지 자체 로그는 별도 확인합니다.

main은 배포본, develop은 통합, feature/*는 Phase별 작업입니다. Phase 2까지 develop에 병합했고 현재 작업은 feature/phase-3-central-monitoring입니다. 다음 Phase는 승인 후 시작합니다.

## 문서 및 검증

- [전체 계획](PROJECT_PLAN.md)
- [아키텍처](docs/ARCHITECTURE.md) · [문제 해결 이력](docs/TROUBLESHOOTING.md)
- [Wiki 홈](docs/wiki/Home.md) · [모듈 상세 명세](docs/wiki/Modules-Specification.md) · [배포 가이드](docs/wiki/Deployment-Guide.md)
- 테스트: `powershell -NoProfile -File tests/Test-Common.ps1` (설치 실행 없이 검증)

Wiki Markdown 파일을 Wiki 저장소 루트에 그대로 복사할 수 있습니다. 원격 Wiki 게시 작업은 수행하지 않았습니다.

## 중앙 관제 (Phase 3)

[중앙 관제 운영 가이드](docs/wiki/Central-Monitoring.md)에 서버 실행, 두 인증 토큰, 클라이언트 Monitoring.json 설정, DB 보관·네트워크 배치 방법을 정리했습니다. 기본적으로 보고는 비활성화되어 있으며 활성화해도 서버 장애가 설치를 중단하지 않습니다. 보고 API와 5초 갱신 대시보드를 제공합니다. 서버 배포와 Phase 4 진입은 수동 승인 후 진행합니다.
