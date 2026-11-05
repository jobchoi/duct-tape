# Blogger 초안 도구

서버와 분리된 로컬 도구다. 대상 블로그는 https://lealnspire.blogspot.com/ 로 고정한다. 공식 API로 초안만 만들며 공개/삭제/자동 수정 기능은 없다. 초안 글은 사람이 확인한 docs/blog/blogger/*.md를 입력으로 받는다. 원고 자동 집필이나 외부 AI 호출은 포함하지 않는다.

## Linux·WSL·Raspberry Pi

```bash
./blog.sh setup
./blog.sh preview docs/blog/blogger/mdm-manual-workflow.md
./blog.sh auth
./blog.sh check
./blog.sh upload docs/blog/blogger/mdm-manual-workflow.md --reviewed
```

setup은 `.venv-blog`만 준비하며 Google API를 호출하거나 글을 올리지 않는다. Linux에서 venv 모듈이 없다면 배포판의 Python venv 패키지를 먼저 준비한다. 각 단계는 수행할 명령을 출력한다.

## Windows PowerShell

Python 3가 준비된 환경에서 같은 작업을 수행한다.

```powershell
.\blog.ps1 setup
.\blog.ps1 preview docs/blog/blogger/mdm-manual-workflow.md
.\blog.ps1 auth
.\blog.ps1 check
.\blog.ps1 upload docs/blog/blogger/mdm-manual-workflow.md --reviewed
```

PowerShell 실행 정책에 막히면 조직의 정책을 확인한다. 시스템 전체 실행 정책을 설치 도구가 바꾸지 않는다. Windows 전용 실행과 Pi ARM64 설치는 별도 현장 검증 대상이다. Windows는 파일 600 권한 대신 사용자 ACL로 인증 디렉터리를 보호해야 한다. 본 스크립트가 Windows ACL을 자동 설정하지는 않는다.

## 인증 파일

기본 위치는 `~/.config/duct-tape-blog/`이며 `client_secret.json`(데스크톱 앱), `token.json`(로그인 후 생성), `uploads.sqlite3`(게시 기록)을 보관한다. 모두 저장소 밖에 둔다. Unix에서는 디렉터리 700·파일 600으로 제한한다. 비밀번호·비밀값을 터미널 인자로 주지 않는다.

별도 경로는 명령 앞에 지정한다.

```bash
./blog.sh --config-dir /사용자전용경로 auth
```

명령 옵션에 인증 JSON 내용이나 토큰을 직접 입력하지 않는다. 계정 연결과 도구 설치는 별개이며 다른 PC로 Git clone만 해서는 인증되지 않는다. 프록시 인증서 오류는 운영체제의 신뢰 저장소 설정으로 해결하며 TLS 검증을 끄지 않는다.

## WSL·브라우저 없는 Pi

```bash
./blog.sh auth --no-browser --port 8765
```

Google 동의 URL을 출력하고 600초간 `127.0.0.1:8765`에서 콜백을 기다린다. WSL은 같은 PC Windows 브라우저에서 링크를 열고 localhost 전달이 동작하는지 확인한다. 스마트폰/다른 PC의 localhost는 해당 WSL/Pi가 아니다. 브라우저 없는 Pi는 PC에서 SSH 로컬 포워딩을 준비한다.

```bash
ssh -L 8765:127.0.0.1:8765 사용자@라즈서버
```

그 SSH 세션에서 Pi의 auth를 실행하고 PC 브라우저에서 링크를 연다. 방화벽으로 콜백 포트를 외부에 공개하지 않는다. 포트 충돌 시 터널과 auth 포트를 함께 바꾼다. 인증 완료 화면의 URL에는 일회성 코드가 있을 수 있으므로 주소 전체를 채팅에 붙이지 않는다.

## 초안 검토·중복 방지

preview는 Google 인증 없이 HTML을 만들고 SHA-256을 표시한다. 기본 출력은 Git 제외 downloads/blog-preview.html이다. HTML은 허용된 태그만 유지하며 스크립트/이미지 및 위험한 링크 스킴을 제거한다. 자동 민감 정보 탐지나 사실 검증을 보장하는 기능은 아니므로 업로드 전 내용을 확인한다.

upload의 `--reviewed`는 현재 원고를 검토했다는 명시적 표시다. 공개 승인이 아니며 API의 isDraft=true를 고정한다. 제목과 HTML은 변환된 내용을 그대로 전송한다. 대상 블로그와 원고 경로 단위로 기록해 같은 원고의 반복 업로드를 막는다. 변경된 원고는 자동으로 새 글을 만들거나 기존 글을 덮어쓰지 않는다. 필요 시 Blogger 편집기에서 기존 초안을 수정한다.

요청 직전 pending 기록을 남긴다. 오류·네트워크 타임아웃이 나면 자동으로 POST를 반복하지 않는다. 먼저 Blogger에서 확인하고 다음 읽기 전용 검색으로 기존 초안을 연결한다.

```bash
./blog.sh reconcile docs/blog/blogger/mdm-manual-workflow.md
```

원격 글의 제목·HTML 본문 해시로 찾으며(이전 기술 라벨도 호환) 대상이 정확히 하나의 초안일 때만 로컬 기록을 갱신한다. 찾지 못하거나 이미 공개된 글이면 자동 변경하지 않는다. Google이 권한 부족 등으로 명확하게 거절한 4xx 응답은 미생성으로 처리하므로 원인을 고친 뒤 직접 다시 실행할 수 있다. 네트워크 끊김·5xx·불명확한 응답은 pending을 유지한다. 로컬 기록을 임의 삭제하지 않는다. 기록 DB를 분실하거나 다른 PC에서 독립 실행하면 중복 방지 기록을 공유하지 못한다. 운영 업로드 담당 환경을 하나로 정하고 재설치 시 기록도 함께 보존한다.

해당 기록이 이미 성공 상태여도 외부에서 글을 삭제/공개했는지 업로드 명령이 매번 재확인하지는 않는다. 상태 확인이 필요하면 reconcile 또는 Blogger 편집기를 이용한다. 인증 토큰은 만료/취소될 수 있으며 재인증이 필요하면 auth를 다시 실행한다.

## 테스트

```bash
.venv-blog/bin/python -m unittest tests.test_blogger -v
```

모의 Google 응답으로 변환·자격 정보 권한·초안 전용 요청·중복 방지·응답 유실 복구를 검사한다. 실제 계정 연결·Blogger 업로드와는 구분한다.
