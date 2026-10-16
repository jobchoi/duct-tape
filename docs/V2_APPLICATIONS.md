# v2 앱 등록·선택 설치 구현

> 2026-10-16 방향 변경: Argos MDM은 **원본 ZIP 다운로드 + 등록 URL·계정 확인 + 수동 설치·등록**으로 변경했다. 아래 최초 구현 기록의 Argos 자동 MSI 설치/계정 비공개 전제는 이 결정으로 대체한다. 일반 앱 MSI 설치 기능은 유지한다. 상세 사용법은 [MDM_MANUAL_SETUP.md](MDM_MANUAL_SETUP.md)를 따른다.


기준: 2026-10-16. 개발 브랜치: feature/v2-mdm-ui. v1 main/v1.0.0-rc.1은 변경하지 않는다. 운영 Pi에 자동 배포하거나 실제 MDM 설치/계정 등록을 실행한 작업이 아니다.

## 구현한 사용자 흐름

관리자는 기존 /admin에서 로그인한 뒤 **v2 앱 관리**(/admin/apps)로 이동한다. 앱 정보와 설치 ZIP을 UI에 입력해 검사 후 초안으로 등록한다. MSI 선행 구성요소와 무인 설치를 검증한 뒤 **검토 후 공개**로 전환한다. 공개 해제는 새 요청을 막으며 이미 생성된 작업의 패키지는 유지한다.

클라이언트는 기존 바탕화면 바로가기로 연결한 탭에서 **v2 선택 앱 설치**(/client/apps)로 이동한다. 공개 앱과 버전을 선택해 설치한다. 관리자가 승인된 PC를 선택해 같은 선택 설치를 요청할 수도 있다. 한 PC에서는 기존 전체 셋업과 새 앱 작업을 동시에 실행하지 않는다.

최초 v2 사용 때는 서버를 v2로 올린 뒤 시험 PC에 최신 전체 ZIP으로 InstallAgent.bat을 다시 실행해야 한다. 에이전트는 protocol_version=2를 보고한다. v1 에이전트에는 v2 작업을 전달하지 않으며 UI 요청은 업데이트 필요 오류를 보여준다. 이후 같은 msi-v1 규약의 앱 추가는 에이전트 재설치 없이 패키지로 전달된다.

PC별 최근 선택 설치 작업과 앱 결과를 함께 표시한다. 설치 확인/기존 설치 확인, 고정 오류 코드, 재부팅 필요 및 MDM 사용자 등록 필요를 구분한다. 비어 있는 계정이나 설치기 종료 0만으로 MDM 등록 성공을 표시하지 않는다. 설치 확인은 MSI ProductCode/등록 버전 확인이며 실제 앱 실행·관리 서버 접속 검증과 다르다.

## 이번 단계의 모듈 규약

임의 PowerShell/명령줄 업로드가 아니라 서버와 에이전트가 검토된 **msi-v1 어댑터**를 공유한다. schema_version=2와 앱 ID·버전·표시명·ZIP 내부 MSI 경로·ProductCode·설치 후 사용자 등록 필요 여부를 앱 정의로 사용한다. UI는 manifest JSON을 직접 편집하지 않아도 이 정의를 등록할 수 있다.

ZIP에는 MSI/EXE/CAB/DLL 설치 원본만 허용한다. 업로드 상한 512 MB, 해제 상한 2 GiB, 항목 상한 10,000개다. 절대 경로·상위 경로·심볼릭 링크·대소문자 충돌·계정 설정/스크립트 파일을 거부한다. 서버는 MSI 파일 헤더를 검사하고 Windows 에이전트는 실행 전에 Windows Installer COM 읽기 전용으로 실제 ProductCode와 버전을 확인한다.

서버 DB와 같은 데이터 디렉터리의 application-packages에 SHA-256 기반 ZIP을 보관한다. 같은 앱/버전 덮어쓰기는 막고 변경 시 새 버전을 등록한다. 작업에는 선택 앱의 정의·버전·해시를 고정한다. 서버 등록/공개 변경은 application_audit에 기록한다. 현재 단일 관리자 키 기반이므로 작업자 개인별 식별까지 제공하지는 않는다.

에이전트는 AppData가 아니라 기존 보호된 ProgramData/DuctTapeAgent 아래 packages에 다운로드 ZIP을 캐시하고 SHA-256 확인 후 재사용한다. 같은 해시라도 손상됐으면 다시 받는다. 패키지 안의 EXE는 동봉 원본으로 보관할 수 있지만 이 어댑터는 실행하지 않는다. MSI만 `/i ... /qn /norestart`로 실행하고 HKLM 32/64비트 제품 등록에서 버전을 확인한다. per-user 전용 설치나 EXE 선행 구성요소 자동 설치는 이 규약으로 보장하지 않는다.

기존 Office·한컴은 기존 전체 셋업 흐름을 유지한다. 아직 v2 카탈로그의 개별 앱으로 변환하지 않았으며, 제품키 속성·특수 선행 조건·제거 정책은 해당 어댑터를 추가할 때 별도 검증한다.

네트워크 결과 보고는 앱별로 로컬 application-results/<job>.<app>.json을 기록한 뒤 제한 재시도한다. 보고 실패 시 설치를 자동 반복하거나 서버 작업을 성공으로 바꾸지 않는다. 기록된 보고의 자동 복구 큐, 다운로드 이어받기·분할 전송, 재부팅 후 설치 재개는 아직 미구현이다. 기존 v1 전체 원본 ZIP 생성 방식도 이번 캐시로 바뀌지 않는다.

## Argos 원본 초안 등록

실제 원본의 읽기 전용 분석 결과:

- MSI: ArgosMDMAgent, 제조사 DKI, ProductVersion 1.1.7.
- ProductCode: {A23A2428-0549-4AF0-8C9B-85F60CBE9AE7}.
- ALLUSERS=2, LaunchCondition 0개, CustomAction 14개. 이 정보가 선행 구성요소 불필요를 뜻하지 않는다.
- setup.exe 제품 버전은 17.0.35410.144이다. 기존 수동 설치는 setup.exe였으므로 MSI 단독 설치와 같다고 주장하지 않는다. setup.exe에 추정한 무인 옵션을 넣어 실행하지 않았다.

서버 배포 원본의 ArgosMDM/ 또는 Tools/ArgosMDM/ 아래에 ArgosMDMSetup.msi와 setup.exe를 구조 그대로 둔다. 로컬 개발 원본은 Tools/ArgosMDM이다. 관리자 화면의 **서버의 Argos 1.1.7 원본을 초안으로 등록** 버튼으로 ZIP을 한 번 생성·보관한다. 자동 공개/설치하지 않으며 다른 버전의 원본을 이 1.1.7 버튼으로 등록하지 않는다. 다른 버전은 실제 MSI 정보를 확인해 일반 폼으로 등록한다.

실제 원본 두 파일로 임시 DB에 초안 등록 및 중복 버전 거부를 시험했고, 새 에이전트의 MSI 식별 검증 함수가 실제 원본의 버전 불일치를 거부하는 것도 확인했다. 설치기는 실행하지 않았다. Argos MSI 단독 경로의 실제 설치·선행 조건과 Windows MDM 등록은 전용 시험 PC에서 검증해야 한다.

## 공통 계정·비밀 설정 분리

실제 URL/전자메일/사용자명/비밀번호를 앱 정의, 소스, ZIP, 진행 이벤트에 넣지 않는다. Config/ArgosEnrollment.json.example은 값이 빈 로컬 파일 템플릿이다. 필요하면 서버 배포 원본 Config/ArgosEnrollment.json에 분리 보관할 수 있으며 Linux에서는 소유자만 읽도록 chmod 600을 적용한다. 이 실제 파일은 Git 제외다.

현재 구현은 **관리자에게 설정 준비 여부만 표시**하며 계정 값을 API/클라이언트로 보내거나 자동 등록에 사용하지 않는다. 수동 등록만 시험한다면 이 파일을 만들 필요도 없다. 불필요하게 비밀번호를 미리 저장하지 않는 것이 낫다. 파일 자체는 암호화 저장소가 아니므로 운영 자동 등록을 설계할 때 OS 자격 증명 저장소/전용 비밀 관리 도구를 연동하고 접근·회전 정책을 정한다. 임의 자체 암호화나 공개 코드에 암호화 키를 함께 넣는 방식을 사용하지 않는다.

사용자가 확인한 등록 절차는 Windows 설정 → 계정 → 회사 또는 학교 액세스 → 장치 관리에만 등록 → 전자메일/공통 계정 인증이다. MDM 공급사의 공식 무인 등록 방식은 아직 확인하지 못했다. UI 클릭 자동화, Intune/Entra라고 가정한 등록, 공통 비밀번호의 설치 인자 전달은 구현하지 않았다.

## 검증 환경과 적용 순서

임시 DB·루프백 서버·가짜 MSI/설치 함수로 서버/API/PowerShell을 검증하고, 실제 Chromium에서 관리자 업로드→공개→클라이언트 선택→모의 결과 반영 및 모바일 화면을 검증했다. 테스트 중 모바일 폼 넘침과 ZIP 테스트 데이터의 시각 차이를 수정했다. 실제 Argos 원본은 읽기/패키징 검증만 수행했다.

검증 결과: Python 관련 회귀 66개 통과/선택 환경 테스트 2개 제외, Docker 관리 명령 2개 통과, 실제 Chromium 기존 관리자/새 앱 흐름 2개 통과, Windows PowerShell 5.1 테스트 6종 통과. 실제 Argos 초안 패키징 및 MSI 읽기 전용 식별/버전 불일치 차단도 확인했다. 추가 최종 새 API/브라우저 검증에서 요청 처리 중 클릭 유실을 발견해 버튼 잠금과 백그라운드 조회 분리로 수정했다. JavaScript/Python/Bash 구문, Compose YAML 문법, git diff --check를 확인했다. Docker 이미지 빌드/ARM64/Pi 현장 설치는 이 작업에서 검증하지 않았다.

v2는 별도 체크아웃/포트/DB로 시험한다. 예시 구성은 deploy/compose.v2.yml이며 상위 디렉터리에 compose.duct-tape-v2.yml로 복사한다. v1 Pi의 Compose·DB·Funnel을 변경하지 않는다. 같은 Windows PC의 에이전트는 서버 한 곳에만 등록하므로 전용 시험 PC를 사용한다.

예제는 상위에 별도 duct-tape-v2 체크아웃과 전용 .env, duct-v2-data/duct-v2-temp/duct-v2-uploads/deployment-v2 디렉터리가 필요하다. v2 관리 명령은 `./manage.sh docker-v2 start/status/logs/build/check`다. docker-v2는 전용 Compose·서비스·8001 포트만 사용한다. 기존 `docker` 명령은 v1을 가리키므로 혼용하지 않는다. v2도 클라이언트용 HTTPS 주소를 별도 준비해야 하며 예제는 loopback에만 노출한다. 브라우저 관리자 쿠키는 포트로 분리되지 않으므로 v1/v2를 같은 호스트의 다른 포트로 사용하면 재로그인이 필요할 수 있다.

순서: 별도 v2 서버 기동 → 관리자 UI 접속 → 원본 초안 등록 → Windows 시험용 선행 구성요소/무인 MSI 검증 → 공개 → v2 에이전트 등록/승인 → 선택 설치 → 앱 설치 확인과 사용자 등록을 별도로 확인. 새 서버 주소를 넣은 공개 ZIP을 사용한다. v2 서버는 v1 클라이언트의 기존 API를 유지하지만 v2 에이전트를 v1 서버로 되돌릴 때는 v1 도구를 다시 설치해야 한다. v2 DB를 구형 서버와 공유하거나 미완료 v2 작업을 구형 서버에 전달하지 않는다.

후속은 V2_PLAN.md의 재부팅·전송·보고 복구 및 설치 후 실제 제품 동작 검증과 연결한다.

## 공식 기술 근거

- [Windows Installer 명령줄](https://learn.microsoft.com/windows-server/administration/windows-commands/msiexec): MSI 무인 설치/재부팅 옵션. Argos의 실제 동작 성공을 보장하는 자료는 아니다.
- [Visual Studio 배포 선행 구성요소](https://learn.microsoft.com/en-us/visualstudio/deployment/application-deployment-prerequisites): bootstrapper와 MSI 실행 경로를 구분할 필요가 있다.
