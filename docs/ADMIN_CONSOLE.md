# 관리자 콘솔 정리

## 정보 구성

- 상단: 서버/인증 연결 상태와 실행 도구 다운로드.
- 요약: 최근 응답 PC, 승인 대기, 서버 매체 준비 상태.
- 본문: 등록 PC 목록과 선택 PC의 셋업 동작을 나란히 배치.
- 준비 상태: 실제 누락 파일만 표시하며 선택 PC에 매체가 있으면 해당 상태를 우선 표시.
- 이전 상태 보고: 현재 등록과 구분해 접힌 영역에 보관. 원본 이력을 삭제하거나 모두 실제 등록 기기로 집계하지 않음.
- 하단: 복구 안내, 중단 확인 및 연결 해제. 버튼은 12px 간격과 모바일 세로 배치 사용.

목록과 선택 기기의 동작을 구분하는 [Microsoft Intune 기기 관리](https://learn.microsoft.com/en-us/intune/device-management/overview), 에이전트 보고를 기반으로 목록을 구성하는 [JumpCloud 기기 목록](https://www.jumpcloud.com/support/admin-portal-devices-list)을 참고했다. 고급 필터·새로운 설치 옵션은 추가하지 않았다.

## Office 키 전달 설명

ODT가 XML의 PowerShell 변수나 환경변수를 치환하는 방식이 아니다. OfficeConfiguration.ps1이 OfficeKey.txt를 읽어 실제 PIDKEY 문자열이 들어간 임시 XML을 만든 뒤 `setup.exe /configure 임시파일.xml`을 실행한다. 원본 XML만 직접 실행하는 경로에는 이 과정이 없다. [Microsoft LTSC 2024 배포 문서](https://learn.microsoft.com/en-us/office/ltsc/2024/deploy)의 PIDKEY 방식에 맞춘다.

## 검증

- 테스트: test_portal.py, test_agent_jobs.py, Test-AgentRegistration.ps1, Test-OfficeConfiguration.ps1.
- 실제 Chromium 수용 테스트: 선택·실제 임시 서버 작업 요청·단일 대기 상태, 과거 보고 분리, 데스크톱 버튼 간격, 모바일 가로 넘침, JS 오류 확인.
- 브라우저 테스트는 임시 DB/루프백 서버만 사용하고 실제 Windows 설치 명령은 실행하지 않는다.

```bash
DUCT_TEST_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/duct-browser .venv/bin/python -m pytest tests/test_admin_browser.py -q
```

브라우저 수용 테스트에는 선택 설치한 Playwright/Chromium이 필요하다. 실제 Windows 예약 작업·권한·설치 인수 검증은 테스트 PC에서 별도로 확인한다.
