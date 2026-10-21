# 다음 환경에서 이어가기

기준: 2026-10-21. 작업 브랜치 `feature/v2-mdm-ui`.

## 현재 상태

- QR 이름·입학년도·S/N 라벨, 관리자 QR/MDM 기능 토글 구현·테스트 완료. 라즈베리 운영 서버 배포는 별도다.
- QTP 헌장/운영은 editorial/qtp, DuctTape 개발/운영은 docs, 게시 초안은 docs/blog로 분리했다.
- Blogger 도구 구현과 오프라인 테스트 13개 완료. 실제 OAuth 토큰은 아직 없고 시험 초안 업로드/공개는 수행하지 않았다.
- 사용자가 제공한 QR 참고 원본은 refernces/에 그대로 보존했다. 원본의 폰트/입력 파일·의존성은 통합 QR 웹 기능과 별개다. 원본은 구문만 검사했고 실행하지 않았다.

## 다른 PC에서 준비

```bash
git clone --branch feature/v2-mdm-ui git@github.com:jobchoi/duct-tape.git
cd duct-tape
./blog.sh setup
./blog.sh preview docs/blog/blogger/mdm-manual-workflow.md
```

기존 체크아웃이면 작업 변경 여부를 확인한 뒤 해당 브랜치에서 `git pull --ff-only origin feature/v2-mdm-ui` 한다. SSH 키가 없는 환경은 HTTPS 저장소 URL을 사용한다. Windows 네이티브에서는 blog.ps1을 따른다.

OAuth JSON은 Git에 포함하지 않았다. 새 PC에서도 저장소 밖 `~/.config/duct-tape-blog/client_secret.json`을 준비하고 Unix 권한 600(디렉터리 700)으로 제한한다. 계정 비밀번호·토큰을 채팅이나 Git에 넣지 않는다.

```bash
./blog.sh auth
./blog.sh check
./blog.sh upload docs/blog/blogger/mdm-manual-workflow.md --reviewed
```

새 환경에서 auth를 다시 실행한다. 이전 PC의 진행 중 OAuth 링크/localhost 콜백은 재사용하지 않는다. 실제 블로그 관리 계정 동의가 필요하다. --reviewed는 현재 원고를 검토한 후 사용한다. 시험 업로드는 한 편의 비공개 초안으로 진행하고 게시 결과를 확인한다. 이후 결과는 WORK_HISTORY.md에 기록한다.

도구 상세/WSL·Pi의 인증/오류 복구는 tools/blogger/README.md, Google 설정은 docs/blog/BLOGGER_SETUP.md를 따른다. .env, 설치 원본·제품 키, 인증 JSON·토큰, 가상환경·로컬 생성물은 별도 준비 대상이며 Git clone으로 복사되지 않는다.
