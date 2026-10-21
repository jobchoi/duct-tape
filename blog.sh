#!/usr/bin/env bash
set -euo pipefail
BLOG_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BLOG_ENV="$BLOG_ROOT/.venv-blog"
run() { printf '실행 명령: '; printf '%q ' "$@"; printf '\n'; "$@"; }
if [[ "${1:-}" == setup ]]; then
  run python3 -m venv "$BLOG_ENV"
  run "$BLOG_ENV/bin/python" -m pip install -r "$BLOG_ROOT/tools/blogger/requirements.txt"
  exit 0
fi
if [[ ! -x "$BLOG_ENV/bin/python" ]]; then
  echo '먼저 ./blog.sh setup 을 실행하세요.' >&2
  exit 1
fi
run "$BLOG_ENV/bin/python" "$BLOG_ROOT/tools/blogger/cli.py" "$@"
