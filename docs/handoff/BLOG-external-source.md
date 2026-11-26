# 지시서: Blogger 초안 도구 — 외부 저장소 원고와 머리말 지원

브랜치: `feature/blog-external-source` (이미 생성됨, 이 브랜치에서만 작업). PM·QC: Claude, 구현: Codex.

## 목적
다른 저장소(예: Lealnspire의 `docs/blog/*.md`)의 연재 원고를 같은 블로그(lealnspire.blogspot.com)에 **초안으로만** 올릴 수 있게 `tools/blogger/cli.py`를 확장한다.

## 만들 것
1. **외부 원고 위치 등록**: 설정 폴더(`--config-dir`, 기본 `~/.config/duct-tape-blog/`)의 `sources.json`(`{"<이름>": "<절대 경로 폴더>"}`)에 등록된 폴더 안의 `.md`만 허용한다.
   - 기존 `docs/blog/blogger/` 원고 동작과 장부(uploads.sqlite3)의 source 키는 **그대로** 유지한다(기존 6건 기록과 호환).
   - 외부 원고의 장부 키는 `<이름>:<등록 폴더 기준 상대 경로>`. 등록 폴더 밖(`..`, 심볼릭 링크로 빠져나가는 경로)은 거부한다. sources.json 이름은 `[a-z0-9-]+`만 허용한다.
   - sources.json이 없으면 기존 동작만 한다. 파일 권한 검사는 기존 private_read 규칙을 따른다.
2. **YAML 머리말**: 파일이 `---`로 시작하면 머리말을 읽는다. 새 의존성 없이 필요한 형식만 지원: `key: "문자열"`, `key: 문자열`, `labels: [a, b, c]`. 그 밖의 형식은 명확한 오류.
   - 제목 = `title`. 본문 첫 `# ` 줄이 제목과 같으면 본문에서 뺀다(제목 중복 방지). 머리말 없으면 기존처럼 첫 줄 `# 제목`.
   - 라벨 = `labels`(문자열, 최대 20개, 각 1~50자, 중복 제거). 머리말 라벨이 없으면 기존 기본값 `['P-DuctTape','개발일지']`.
   - `status`가 있으면 `draft` 또는 `reviewed`만 업로드 허용.
   - `summary` 등 다른 키는 무시(업로드하지 않음).
3. preview·upload·reconcile 모두 새 원고를 받는다. 해시(sha256) 계산식은 기존과 동일하게 유지한다(제목+본문 HTML).
4. `tools/blogger/README.md`에 sources.json 예시(가짜 경로)와 사용법을 추가한다.

## 하지 말 것
- 공개(publish), 수정(patch/update), 삭제 API 호출 추가 금지. 초안(`isDraft=true`)만.
- 네트워크 호출, 실제 업로드, `~/.config/duct-tape-blog/` 실제 파일 읽기·수정 금지(테스트는 임시 폴더).
- 서버(Server/) 등 다른 코드 수정 금지. 새 의존성 추가 금지.
- 개인 경로, 계정, 토큰을 문서·테스트·커밋에 넣지 않는다.

## 검증
- `tests/test_blogger.py`에 오프라인 테스트 추가: 머리말 파싱(정상·오류), 라벨이 POST json에 들어감, 기본 라벨 유지, 외부 폴더 허용·폴더 밖/심볼릭 링크 거부, 장부 키 형식, 기존 원고 키 불변, status 거부, 제목 중복 제거.
- 실행: `.venv-blog/bin/python -m unittest tests.test_blogger -v` 전부 통과.

## 보고
변경 파일, 실행한 명령과 결과(통과/실패 수), 남은 문제. 커밋은 하지 않는다(Claude가 QC 후 커밋).
