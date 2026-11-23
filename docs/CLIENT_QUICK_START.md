# 클라이언트 간편 실행

Windows 클라이언트에서 `Client.bat`을 더블클릭하면 관리자 권한 요청 후 설정·보고 테스트·배포 메뉴가 열린다. Windows PowerShell 5.1을 사용하며 클라이언트에 Python은 필요 없다.

## 담당자가 준비할 항목

- 전체 소스 배포 폴더의 `Client.bat`, `Scripts/`, `Modules/`, `Config/`를 함께 복사한다. 서버에서 받은 에이전트 ZIP은 아래 서버 연동 절차를 사용한다.
- 실제 Office/한컴 설치 매체를 `Office/`, `Hancom/`에 배치하고 `Config/HancomKey.txt`를 준비한다. 자세한 매체 구조는 [배포 가이드](wiki/Deployment-Guide.md)를 따른다.
- 서버 PC에서 WSL 서버를 실행하고 Windows의 Tailscale Serve를 유지한다. 클라이언트도 해당 tailnet에 연결한다.
- 서버 주소와 보고 토큰을 준비한다. 기본 보고에는 `.env`의 `DUCT_REPORT_TOKEN`을 사용하고 학교 코드는 비운다. 학교별 보고에는 등록된 학교 코드와 학교 전용 토큰을 함께 사용한다. 대시보드용 `DUCT_READ_TOKEN`은 클라이언트 설정에 사용하지 않는다.

## 최초 설정과 실행

1. `Client.bat`을 더블클릭하고 관리자 권한 요청을 승인한다.
2. 메뉴 `1`에서 서버 HTTPS 주소, 학교 코드(기본 보고는 Enter), 학년, 보고 토큰을 입력한다. 토큰 입력은 화면에 표시하지 않는다. 주소에는 `/api/report`를 붙이지 않는다.
3. 메뉴 `2`에서 설치 없이 보고를 테스트한다. 성공하면 대시보드에 현재 PC가 `Preflight / running`으로 표시된다. 이 테스트도 실제 최신 상태를 갱신하므로 완료된 PC에서 반복 테스트할 때 주의한다.
4. 메뉴 `3`을 선택한다. 보고 테스트가 성공한 뒤 `Y`를 입력하면 `Scripts/RunSetup.bat`의 제거·설치 작업을 시작한다.
5. 배포 후 재부팅 필요 여부, Office/한컴 실행과 정품 인증을 확인한다.

설정은 `Config/Monitoring.json`에 저장된다. 담당자가 설정을 미리 준비하고 같은 학교·학년 클라이언트에 배포하면 각 PC에서 메뉴 `1`을 반복할 필요 없이 메뉴 `3`으로 시작할 수 있다. PC 식별자는 실행 중 해당 PC의 Windows MachineGuid에서 읽으므로 설정에 PC 이름을 넣을 필요가 없다. 학년·학교가 다르면 설정을 각각 준비한다.

보고 토큰과 라이선스 키가 들어 있는 배포 폴더는 승인된 담당자와 기기에만 전달한다. 실제 설정·키·설치 매체는 Git에 포함하지 않는다. Tailscale 설치·로그인, 설치 매체 다운로드, 라이선스 발급은 이 도구가 자동 처리하지 않는다.

## 접속과 장애 확인

Windows 서버 PC에서 다음 명령으로 전달 주소를 확인한다.

```powershell
tailscale serve status
```

현재 확인한 주소는 `https://desktop-9169pkb-ydhight-school.tail1a38c1.ts.net`이다. 환경이 바뀌면 실제 명령 출력 주소를 입력한다.

보고 실패 시 Tailscale 연결, WSL 서버 실행, Windows의 `http://localhost:8000` 응답, 서버 주소, 보고 토큰 및 학교 코드 조합을 확인한다. 설정에 `Enabled: true`가 필요하다. 중·고등학교 학년은 서버에서 1~3으로 제한한다.

간편 메뉴는 배포 시작 전 보고 실패를 감지하면 시작하지 않는다. 이미 시작한 셋업은 기존 정책에 따라 보고 실패 시 경고를 남기고 설치를 계속한다. 직접 실행 방법은 아래 수동 설치 절을 참고한다.

로컬 결과는 `%TEMP%\Tapbook_State.json`, 로그는 `%TEMP%\duct-tape\Deployment.log`에서 확인한다. 대시보드는 단계별 보고를 표시하며 실제 설치 백분율을 제공하지 않는다.

## 검증

```powershell
powershell -NoProfile -File tests\Test-ClientSetup.ps1
powershell -NoProfile -File tests\Test-ReportStatus.ps1
powershell -NoProfile -File tests\Test-Common.ps1
```

자동 테스트는 설치를 실행하지 않는다. 실제 Windows PowerShell 5.1의 UAC 승격, 공백·한글 경로에서 메뉴 실행, Tailscale 연결, 정식 설치 매체를 통한 배포는 Windows 테스트 PC에서 확인한다.

## 서버 연동 PC

서버의 클라이언트 페이지에서 최신 ZIP을 내려받아 압축을 풀고 `InstallAgent.bat`을 관리자 권한으로 실행한다. 관리자가 연결을 승인한 뒤 바탕화면 바로가기에서 셋업을 시작한다. 설치 매체와 제품 키는 서버에서 준비하며 에이전트가 셋업 시 가져온다. 기존 에이전트도 이 변경을 적용하려면 진행 중인 작업을 확인하고 최신 ZIP의 `InstallAgent.bat`을 한 번 다시 실행한다.

## 필요 시: 서버 없는 수동 설치

전체 배포 폴더에 Office/한컴 설치 매체와 `Config/HancomKey.txt`, `Config/OfficeKey.txt` 등 필요한 키 파일을 직접 준비한다. 구조와 키 요구 사항은 [배포 가이드](wiki/Deployment-Guide.md)를 확인한다. 관리자 권한 명령 프롬프트에서 `Scripts\RunSetup.bat`을 실행한다. 이 작업은 기존 프로그램 제거 및 설치를 수행할 수 있다. 다운로드한 에이전트 ZIP에는 매체와 키가 포함되지 않는다.
