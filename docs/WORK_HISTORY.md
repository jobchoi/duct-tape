# 작업 이력

## 2026-10-07 서버 복구

- 브랜치: `fix/server-startup` → `develop` (`--no-ff` 병합).
- 복구 커밋: `01a250b` (`fix: restore server dependencies and load runtime configuration`).
- 가상환경에서 서버 패키지가 누락되어 uvicorn 실행이 실패한 로그를 확인하고 의존성을 재설치했다.
- 업로드용 `python-multipart` 의존성을 추가하고 `manage.sh`에서 `config/app.conf`와 `.env`를 로딩하도록 변경했다.
- 검증: 대시보드·인증 조회 API HTTP 200, Python 테스트 41개 통과 / 1개 생략(PowerShell 통합 테스트 런타임 미지정).

## 2026-10-07 클라이언트 간편 실행

- 브랜치: `feature/client-quick-start` → `develop` (`--no-ff` 병합).
- `Client.bat`과 `Scripts/ClientSetup.ps1`을 추가했다. 더블클릭으로 관리자 승격 후 최초 설정, 설치 없는 보고 테스트, 기존 Main 배포 실행을 선택한다.
- HTTPS 원점, ASCII 보고 토큰, 학년·학교 코드를 검증한다. 토큰은 숨겨 입력하고 실제 설정은 Git 제외 파일에 저장한다.
- 배포 전에 보고가 성공하는지 확인한다. 기존 Main의 설치 중 보고 장애 격리 정책은 유지한다.
- 사용 절차: [클라이언트 간편 실행](CLIENT_QUICK_START.md).
- 실제 설정·라이선스 키·설치 매체는 커밋하지 않는다. 원격 push와 main 반영은 수행하지 않는다.
- 검증: 임시 PowerShell 7.4.6/Linux 런타임에서 `Test-ClientSetup.ps1`, `Test-ReportStatus.ps1`, `Test-Common.ps1` 모두 통과. `git diff --check` 통과. 실제 Windows 5.1 UAC·메뉴·설치 인수 검증은 별도 확인이 필요하다.
