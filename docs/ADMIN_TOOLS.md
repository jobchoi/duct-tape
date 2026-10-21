# 관리자 도구·기능 관리

2026-10-21 구현. v2 개발 브랜치 대상이며 운영 Raspberry Pi에 자동 반영하지 않았다.

## 사용

1. `/admin`에서 관리자 로그인한다.
2. **도구·기능 관리**(`/admin/tools`)에서 QR 생성과 MDM 다운로드·등록 정보 확인을 켜거나 끈다. 설정은 서버 DB에 저장되어 재시작해도 유지된다. 초기값은 둘 다 켜짐이다.
3. QR은 직접 값을 입력하거나 PC 관리 목록의 **QR 만들기**를 눌러 해당 PC의 보고된 시리얼을 가져온다.
4. 값을 확인하고 **QR 생성 → PNG 다운로드**를 누른다. 기본 기기 라벨 모드에서는 이름·입학년도·S/N을 입력한다. QR 데이터는 `입학년도|이름|S/N`이며 다운로드 PNG 아래에도 세 항목을 표시한다. 이름과 S/N에는 구분자 `|`나 줄바꿈을 넣을 수 없다. 입학년도는 현재 연도를 기본값으로 채우므로 실제 입학년도와 대조한다. 입력값만 QR로 생성 모드를 선택하면 이름·입학년도는 포함하지 않는다. A4 라벨 PDF는 아직 없다.

기능을 끄면 서버 API에서도 새 요청을 막는다. MDM을 끄면 클라이언트 앱 목록에서 Argos를 숨기고 ZIP 다운로드와 등록 정보 조회를 차단한다. 이미 내려받거나 열람한 내용·진행 중 작업은 회수하거나 중단하지 않는다. 다른 화면에 열어둔 MDM 안내는 다음 목록 갱신 때 숨겨진다. 임의 코드 업로드 플러그인이나 기관별/사용자별 기능 정책은 제공하지 않는다.

QR 입력은 최대 1024 UTF-8 바이트다. 값은 앞자리 0과 앞뒤 공백을 포함해 그대로 인코딩한다. URL에 접속하지 않는다. QR 값·이름·이미지를 서버 DB나 파일에 저장하지 않는다. 요청 본문을 기록하는 외부 프록시/운영 로그 설정은 별도 관리해야 한다. PNG 파일명에는 시리얼·이름을 넣지 않는다.

## 장치 정보

Windows 에이전트의 기존 BIOS 시리얼 보고를 재사용한다. 새로 등록된 PC에 아직 보고가 없거나 기본 문자열이면 직접 입력한다. 보고 시각을 보고 실제 기기와 대조한다. 시리얼을 인증 수단으로 사용하지 않으며 device_id로 PC를 연결한다. 이름·시리얼 결합 QR 형식이나 라벨 출력, 설치와 독립된 장치 정보 수집은 후속 범위다.

## 환경 준비

서버 의존성에 순수 Python `qrcode==8.2`를 추가했다. Pillow·pandas·PDF·Windows 폰트 없이 QR 행렬을 만들고 브라우저 canvas에서 PNG를 생성한다. 라이브러리는 https://pypi.org/project/qrcode/8.2/ 를 참고했다.

이미 별도 v2 Docker 환경을 구축한 경우 v2 소스 업데이트 후 해당 체크아웃에서 `./manage.sh docker-v2 build`로 이미지 재빌드, `./manage.sh docker-v2 check`로 확인한다. 실행 중 설치 작업이 있는지 먼저 확인한다. v1의 develop/main을 pull하는 것으로 이 개발 브랜치의 변경이 적용되지는 않는다. 새로운 v2 환경 생성은 기존 deploy/compose.v2.yml 안내를 따른다.

로컬 Python 서버는 기존 가상환경에서 `python -m pip install -r Server/requirements.txt`로 의존성을 갱신한다. OS Python에 강제 설치하지 않는다.

## 구조·검증

- Model: features.py의 고정 기능 목록/DB 설정, qr.py의 순수 QR 인코딩.
- Controller: tools.py의 관리자 권한·토글·입력 검증. applications.py가 MDM 기능 토글을 검사한다.
- View: tools.html/tools.js. 기존 PC 목록에서 device_id만 URL로 전달하고 장치 보고를 읽는다.
- API 테스트: 관리자/클라이언트 권한, QR 용량/공백/추가 필드, 토글 저장·재시작 보존, 비활성 API 차단, MDM 숨김 및 재활성.
- 브라우저 테스트: 모의 PC 보고 → 시리얼 자동 입력 → PNG 다운로드 → 독립 디코더로 원문 일치, 한글·특수문자, 입력 변경 시 이전 이미지 제거, 토글 유지·모바일 폭 및 기존 앱 흐름.

브라우저 테스트는 선택 실행이다. `python -m pip install -r Server/requirements-browser.txt`와 `python -m playwright install chromium`으로 테스트 환경을 준비한다. 테스트용 Pillow·zxing-cpp·Playwright는 서버 필수 의존성이 아니다. `DUCT_TEST_BROWSER=1 python -m pytest tests/test_admin_tools_browser.py`로 실행한다. 테스트 원문은 모의 데이터이며 실물 탭북·휴대폰 스캔·ARM64 Docker 빌드·인쇄 결과를 대체하지 않는다.
