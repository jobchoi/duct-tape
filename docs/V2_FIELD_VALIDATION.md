# v2 서버·현장 검증 준비

2026-11-05. 후속 작업 브랜치 `feat/v2-field-validation`.
실물 PC는 아직 없으며 사용자 요청에 따라 서버·자동 검증부터 진행한다. 시험 서버 준비/실제 Windows 설치/사용자 기기 등록은 서로 다른 완료 조건이다.

## 시험 환경

목표 위치: `/home/jobchoi/web-server/duct-tape-v2`.

- repo/: 전용 Git 체크아웃. 운영 duct-tape/repo를 변경하지 않는다.
- data/db, temp, uploads: 신규 시험 데이터. 운영 DB를 복사하거나 공유하지 않는다.
- .env: 신규 시험 인증키. 서버에서 별도 생성하고 600 권한으로 보관한다.
- compose.yaml: 단일 운영 정의. [프로젝트별 Pi 예제](../deploy/compose.v2.pi.yml)를 최초 준비에만 사용한다.
- 설치 원본: `../duct-tape/data/media`를 읽기 전용으로 연결한다. 원본을 바꾸면 두 환경에 영향이 있으므로 이번 작업에서 수정하지 않는다.
- HTTP: localhost 8001. HTTPS 접속 경로는 기존 서비스 매핑을 보존한 별도 tailnet 전용 포트로 검증한다. 외부 공개 Funnel을 추가하지 않는다.

준비 결과와 실제 주소·코드 커밋·자동 시험은 아래 작업 결과에 기록한다. 명령에 인증값을 직접 넣지 않는다.

## Windows 읽기 전용 진단

새 시험 서버의 `/download/agent.zip`에는 `CollectDiagnostics.bat`과 `Scripts/diagnostics/Collect-ClientDiagnostics.ps1`이 포함된다. ZIP을 풀고 **CollectDiagnostics.bat을 관리자 권한으로 실행**하면 설치나 등록을 진행하지 않고 새 임시 폴더의 report.json을 만든다. InstallAgent.bat과 구분한다.

이미 최신 에이전트가 설치됐다면 관리자 PowerShell에서 다음을 사용할 수 있다.

```powershell
& "$env:ProgramData\DuctTapeAgent\Scripts\diagnostics\Collect-ClientDiagnostics.ps1"
```

특정 작업의 로그만 확인하려면 스크립트에 `-JobId '실제-작업-GUID'`를 지정한다. 보고서에는 PC 이름·BIOS 시리얼·모델·OS·등록 서버와 장치 ID·예약 작업 상태·Office/한컴 레지스트리 목록·상태 파일 시각·로그 존재/크기와 허용된 종료/오류 신호가 들어간다. 로그인한 사용자 TEMP와 SYSTEM TEMP 후보를 모두 확인한다. 빈 로그도 파일 크기 0으로 기록한다.

제품 키·에이전트 토큰·전체 설정·원시 로그 본문은 내보내지 않는다. 설치/제거·Win32_Product 조회·예약 작업 변경·등록/보고 POST는 수행하지 않는다. 서버 점검은 인증값 없는 /api/config GET만 사용한다. 그래도 기기 식별 정보가 포함되므로 공개 Git·블로그에 올리지 않는다. 자동 업로드는 하지 않는다.

기존 출력 폴더를 덮어쓰지 않으며 `-OutputDirectory`는 아직 존재하지 않는 경로를 지정해야 한다. 관리자 권한이 없거나 일부 정보 접근이 실패하면 issues 항목과 누락 부분을 함께 확인한다. 설치 성공 여부는 레지스트리 목록만으로 확정하지 않는다.

## 실제 PC 확보 후

1. 새 시험 HTTPS 주소와 관리자 인증키를 서버의 시험 .env에서 확인한다. 실제 키를 Git·채팅·공개 기록에 복사하지 않는다.
2. 운영 에이전트가 연결된 PC는 실행/보고 중 작업이 없는지 먼저 확인한다. 현재 한 PC에 v1/v2 예약 작업·ProgramData를 동시에 분리 설치하는 방식은 지원하지 않는다.
3. 시험 PC에서 먼저 진단 보고서를 보관하고 시험 서버의 새 ZIP으로 에이전트를 등록한다. 등록 서버가 시험 주소인지 확인한 후 관리자 승인한다.
4. PC/서버에서 같은 작업 ID를 기준으로 시작·다운로드·Office/한컴 단계·완료·앱 상태 보고를 대조한다. 앱 실행/인증·재부팅은 별도로 확인한다.
5. 실패 재시도는 복구 가능한 시험 조건에서만 수행한다. 운영 매체·키를 훼손하지 않는다. 등록 삭제 없이 새 작업이 생성되는지, ActiveJob/실제 설치 프로세스 상태가 일치하는지 확인한다.
6. 완료인데 앱 상태가 확인 전이면 진단 결과의 상태 파일 시각·설치기 종료 코드와 마지막 /api/report를 대조한다. 성공 상태를 추측으로 덮어쓰지 않는다.

## 검증 결과

- Windows PowerShell 5.1: 모의 레지스트리/CIM/예약 작업/HTTP와 임시 파일로 진단 스크립트 통과. 실제 설치기는 실행하지 않음.
- 에이전트 ZIP/앱 규약 관련 Python: 20 passed(37.08초), 기존 TestClient 사용 중단 예정 경고 1건.
- 실제 Pi 준비·자동 API 검증: 진행 후 기록.
- 실제 Windows 설치·재부팅·현장 재시도: PC 미준비로 미수행.

Tailscale HTTPS 방식은 [Serve 공식 안내](https://tailscale.com/docs/reference/tailscale-cli/serve)를 참고한다. Serve는 tailnet 내부 시험용으로 사용하고 기존 443/8443/10000 매핑은 유지한다.
