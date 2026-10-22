# 게시용 파일 사용 안내

초안 기준일: 2026-10-15. 실제 대화에서 전달받은 현장 결과와 저장소의 작업 이력을 바탕으로 작성했다. 공개 게시나 외부 AI 전송은 수행하지 않았다.

- pc-setup-development.md: Markdown 본문. 제목은 첫 줄, 나머지는 본문으로 사용한다.
- pc-setup-development-body.html: 블로그의 HTML 본문 편집기에 붙여넣을 조각. 별도 문서의 head/body 태그는 없다. 글 제목은 블로그 제목 칸에 별도로 입력한다.
- pc-setup-development.html: UTF-8 브라우저 미리보기용 완전한 HTML 문서. 본문 입력에는 body 파일을 권장한다.

구글 서비스는 Blogger를 가정한다. Blogger에서는 글의 HTML 보기에서 body.html 소스를 붙여넣고 미리보기한다. 티스토리는 현재 사용하는 편집기의 Markdown 또는 HTML 모드에 맞춰 본문을 붙여넣는다. 파일을 선택해 업로드하는 것과 본문 소스를 붙여넣는 것은 다르다. 스킨별 코드 블록/줄바꿈 표현은 게시 전 미리보기로 확인한다.

검토 요청은 선택 사항이다. 다른 AI에는 아래 지시와 초안만 전달하면 된다. 실제 제품 키·로그 원본·환경 설정·기관 식별 정보는 넣지 않는다.

> 이 글의 문장과 흐름을 검토해주세요. 제공된 초안 밖의 구현 사실, 성능 수치, 테스트 결과는 추가하지 마세요. 확인 완료·재현 테스트·추정·향후 계획을 구분해 유지해주세요. 설치기 종료 코드 0을 실제 앱 실행/정품 인증 성공으로 바꾸거나, 웹 접속 확인을 전체 설치 검증 완료로 확대하지 마세요. 새로운 근거가 필요한 문장은 질문으로 남기고, 수정 이유를 함께 알려주세요.

다른 AI의 표현 검토는 사실 검증을 대신하지 않는다. 작성자가 실제 현장 결과와 대조하고 최종 미리보기 후 게시한다.

## 블로그별 작성 기준 — 2026-10-21

[PUBLISHING_POLICY.md](PUBLISHING_POLICY.md)에 두 블로그의 역할과 DuctTape 게시 적용 기준을 정리했다. 공통 헌장은 [별도 QTP 영역](../../editorial/qtp/README.md)으로 분리했다. Blogger는 시행착오 일지, 티스토리는 실행 절차 중심 매뉴얼로 작성한다.

최근 MDM 변경을 같은 근거에서 각각 작성한 검토용 초안:
- [Blogger 일지](blogger/mdm-manual-workflow.md)
- [티스토리 매뉴얼](tistory/mdm-manual-setup.md)

[BLOGGER_SETUP.md](BLOGGER_SETUP.md)는 Google Cloud/OAuth 최초 설정 안내다. 2026-10-21 초안 업로드 도구와 간편 설치 스크립트를 추가했다. 실제 계정 연결·시험 업로드 상태는 작업 기록을 따른다. 티스토리는 공식 Open API 종료로 편집기 수동 입력을 우선한다.

## QR·기능 관리 구현 기록 — 2026-10-21

- [Blogger 구현 일지](blogger/qr-tools-implementation.md): 계획 문서와 구분해 실제 구현·검증·남은 확인을 기록했다.
- [티스토리 사용 절차](tistory/qr-tools.md): QR 생성과 기능 설정 방법을 정리했다.
- 두 글 모두 로컬 초안이다. Google API 계정 연결과 외부 업로드는 아직 수행하지 않았다.

## 추가 배포·전송 일지 — 2026-10-22

사용자가 블로그에서 수정한 Office 글의 구체적 용어·문장 흐름을 확인하고 참고했다. 기존 게시글은 덮어쓰지 않았다.

- [서버 실행과 설치 원본 준비](blogger/pi-office-media-readiness.md): healthy와 media.ready를 구분한 배포 기록.
- [두 PC 다운로드 지연 확인](blogger/parallel-download-investigation.md): running 상태와 실제 전송량을 구분한 조사 기록. 원인은 미확정이다.

두 글을 Blogger 비공개 초안으로 업로드했다. MDM·QR·일반 모듈 기획 초안은 앞서 정한 Office 설치·배포 중심 범위에 맞춰 이번 일괄 업로드에서 제외했다.

블로그 도구 UI는 선행 게시 작업 뒤 별도 도구/프로젝트로 검토한다. 코드 리뷰·테스트 결과를 포스팅으로 남기는 후속 계획은 [별도 로드맵](../../editorial/publishing/ROADMAP.md)을 따른다.

## Tailscale 외부 접속 일지 — 2026-10-22

- [클라이언트 Tailscale 없이 접속하기](blogger/tailscale-funnel-access.md): Pi 웹 서버와 접속 경로의 역할, Serve/Funnel, 로컬/API/공개 DNS/HTTPS 확인을 구분한다. 외부 접속 복구의 원인이나 다운로드 병목을 확정하지 않는다.
- 사용자 추가 요청으로 설치·배포 관련 Tailscale 운영 경험을 별도 초안으로 업로드했다. 공개는 하지 않았다.
