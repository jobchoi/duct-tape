#!/usr/bin/env bash
# Explicit Docker mode: do not source .env or start the local Python server.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
case "${DUCT_DOCKER_PROFILE:-v1}" in
    v1) profile_file=compose.duct-tape.yml; service=duct-tape; port=8000 ;;
    v2) profile_file=compose.duct-tape-v2.yml; service=duct-tape-v2; port=8001 ;;
    *) echo '알 수 없는 Docker 프로필입니다.' >&2; exit 2 ;;
esac
compose_file="${DUCT_COMPOSE_FILE:-$(dirname "$project_dir")/$profile_file}"
action="${1:-help}"
case "$action" in
    help|-h|--help)
        echo '사용법: ./manage.sh {docker|docker-v2} {start|stop|restart|status|logs|build|check}'
        echo 'start: 시작, stop: 중지, restart: 재시작, status: 상태, logs: 실시간 로그'
        echo 'build: 코드 변경 후 재빌드·시작, check: 로컬 API 확인'
        echo 'logs 종료는 Ctrl+C이며 서버는 계속 실행됩니다.'
        exit 0 ;;
    start|stop|restart|status|logs|build|check) ;;
    *) echo "알 수 없는 Docker 관리 명령: $action" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo '추가 인자는 지원하지 않습니다. help를 확인하세요.' >&2; exit 2
fi
if [ ! -f "$compose_file" ]; then
    echo "Compose 파일이 없습니다: $compose_file" >&2
    echo 'Pi 배포 안내: docs/PI_DOCKER.md' >&2
    exit 1
fi
command -v docker >/dev/null || { echo 'Docker 명령을 찾을 수 없습니다.' >&2; exit 127; }
case "$action" in
    start)   args=(up -d "$service") ;;
    stop)    args=(stop "$service") ;;
    restart) args=(restart "$service") ;;
    status)  args=(ps -a "$service") ;;
    logs)    args=(logs --tail=80 --follow "$service") ;;
    build)   args=(up -d --build "$service") ;;
    check)
        command=(curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$port/api/config") ;;
esac
if [ "$action" != check ]; then
    command=(docker compose -f "$compose_file" "${args[@]}")
fi
echo '실행 명령:'
printf '  %q' "${command[@]}"
printf '\n'
exec "${command[@]}"
