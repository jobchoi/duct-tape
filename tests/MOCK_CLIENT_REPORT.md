# Python 모의 보고 클라이언트

Windows 없이 실제 HTTP로 FastAPI 보고 API를 검증한다. 서버·설치 코드 변경 없이 `tests/`에만 추가했다.

## 실행

저장소의 서버 의존성이 설치된 Python 환경에서:

```text
python tests/mock_client_report.py
```

의존성 설치가 필요하면 별도 가상환경에서 `python -m pip install -r Server/requirements.txt`를 실행한다. loopback 소켓 생성 권한이 필요하다. 성공 시 `PASS` 목록과 검사 수, 실패 시 종료 코드 1을 반환한다.

## 격리

- 임시 디렉터리의 SQLite와 127.0.0.1 임의 포트 서버를 생성하고 종료 시 정리한다.
- 학교 MOCK_E(초등)/MOCK_M(중등), 가짜 UUID·자산 정보만 사용한다.
- 테스트 토큰은 실행 시 생성하여 자식 서버의 환경변수로 전달하며 출력·저장하지 않는다.
- 자식 서버는 실제 DUCT_* 설정을 제거하고 명시적인 테스트 학교 목록과 no-network 릴레이를 주입한다.
- 운영 URL·실제 토큰·학교 설정을 받는 외부 서버 모드는 제공하지 않는다. 숨겨진 --serve/--port/--database 인수는 내부 자식 프로세스 전용이다.
- 실제 GAS/시트 요청, Windows 설치, 운영 DB 수정은 수행하지 않는다.

## 검사

| 범위 | 기대 결과 |
| --- | --- |
| 학교 보고·완료 갱신 | 200, SQLite와 GET /api/devices 최신 상태 일치 |
| 동일 보고 / 과거 보고 | updated=false, 최신 상태 유지 |
| 토큰 없음·오류·조회 토큰으로 보고 | 401 |
| 학교 토큰·학교 코드 불일치 | 403 |
| message/ip/step 추가 | 422 |
| 필수 필드 누락·잘못된 UUID/상태/단계·시간대 없는 날짜 | 422 |
| null/문자열/Boolean/실수/범위 밖 grade | 422 |
| 중등 grade=3 / 4 | 200 / 422 |
| 학교별 토큰 요청에서 school_code 누락 | 403 (모델은 학교 미지정을 허용하나 학교 토큰과 불일치) |
| 거부된 요청 | devices/outbox 행 수 불변 |
| 읽기 인증 분리 | 보고 토큰 및 인증 없는 조회는 401 |
| 모의 릴레이 | 임시 outbox 모두 sent, 외부 네트워크 호출 없음 |

대시보드는 조회 API 데이터와 HTML 응답만 확인한다. 실제 브라우저 렌더링, 학교망 HTTPS, PowerShell 및 설치 장애 격리의 현장 검증을 대체하지 않는다.

## 작업 기록

- feature/mock-client-report에서 신규 파일만 작성. 운영 코드·기존 파일 변경 없음.
- 커밋·push는 결과 검토 후 별도 승인 대상.

- 로컬 실행 결과: 실제 loopback HTTP 검사 39개 통과. 임시 서버는 종료되고 임시 DB는 정리됨.
- 기존 PROJECT_PLAN.md도 변경하지 않고 이 문서에 실행 기록을 남김(tests/ 한정 지침 준수).
