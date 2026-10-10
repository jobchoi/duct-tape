#!/usr/bin/env bash
# 통합 제어기: start(백그라운드) | run [인자...](포그라운드) | stop | restart | status | logs | rotate
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_BASE_DIR="$(cd "$BASE_DIR" && pwd -P)"
cd "$BASE_DIR" || exit 1

# 환경설정 및 보안키 로드
set -a
[ -f "$BASE_DIR/config/app.conf" ] && source "$BASE_DIR/config/app.conf"
[ -f "$BASE_DIR/.env" ] && source "$BASE_DIR/.env"
set +a
if [ -f "$BASE_DIR/scripts/load_secrets.sh" ]; then
    # shellcheck disable=SC1091
    source "$BASE_DIR/scripts/load_secrets.sh" || exit 1
elif [ -f "$BASE_DIR/config/secrets.env" ]; then
    set -a
    # shellcheck disable=SC1091
    [ -f "$BASE_DIR/config/app.conf" ] && source "$BASE_DIR/config/app.conf"
    source "$BASE_DIR/config/secrets.env"
    set +a
fi

PID_FILE="$BASE_DIR/logs/app.pid"
LOG_FILE="$BASE_DIR/logs/app.log"
LOG_MAX_BYTES="${LOG_MAX_BYTES:-10485760}"    # 10MB

# 기본값 fallback (설정 파일 누락 대비)
SERVER_HOST="${SERVER_HOST:-0.0.0.0}"
SERVER_PORT="${SERVER_PORT:-8100}"

mkdir -p "$BASE_DIR/logs"

C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_RED=$'\033[0;31m'; C_YELLOW=$'\033[1;33m'

PS_OK=0
[ -n "$(ps -p $$ -o args= 2>/dev/null)" ] && PS_OK=1

pid_matches() {
    local pid="$1" args cwd
    if [ "$PS_OK" -eq 1 ]; then
        args="$(ps -p "$pid" -o args= 2>/dev/null)"
        [ -n "$args" ] || return 1
        case "$args" in
            *python*|*uvicorn*|*run_service*) ;;
            *) return 1 ;;
        esac
    fi
    if [ -d "/proc/$pid" ]; then
        cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null)"
        if [ -n "$cwd" ] && [ "$cwd" != "$REAL_BASE_DIR" ]; then
            return 1
        fi
    fi
    return 0
}

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid; pid="$(cat "$PID_FILE" 2>/dev/null)"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_matches "$pid"
}

clean_stale_pid() {
    [ -f "$PID_FILE" ] || return 0
    is_running && return 0
    rm -f "$PID_FILE"
}

listener_pid() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -t -iTCP:"$SERVER_PORT" -sTCP:LISTEN 2>/dev/null | head -n 1
    elif command -v ss >/dev/null 2>&1; then
        ss -ltnp "sport = :$SERVER_PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | head -n 1 | cut -d= -f2
    fi
}

rotate_log() {
    [ -f "$LOG_FILE" ] || return 0
    local size
    size="$(wc -c < "$LOG_FILE" 2>/dev/null | tr -d ' ')"
    [[ "$size" =~ ^[0-9]+$ ]] || return 0
    if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
        if cp -f "$LOG_FILE" "$LOG_FILE.old" && : > "$LOG_FILE"; then
            echo "🗂  로그 회전: logs/app.log.old 로 백업 후 새로 기록합니다."
        fi
    fi
}

start_server_process() {
    source "$BASE_DIR/.venv/bin/activate"
    if [ -f "$BASE_DIR/Server/server.py" ]; then
        exec python3 -m uvicorn Server.server:app --host "$SERVER_HOST" --port "$SERVER_PORT" "$@"
    elif [ -f "$BASE_DIR/main.py" ]; then
        exec python3 -m uvicorn main:app --host "$SERVER_HOST" --port "$SERVER_PORT" "$@"
    else
        exec python3 -m http.server "$SERVER_PORT" --bind "$SERVER_HOST"
    fi
}

do_start() {
    clean_stale_pid
    if is_running; then
        echo "${C_YELLOW}ℹ️  이미 실행 중입니다 (PID: $(cat "$PID_FILE"))${C_RESET}"
        return 0
    fi

    local other; other="$(listener_pid)"
    if [ -n "$other" ]; then
        echo "${C_RED}❌ 포트 $SERVER_PORT 를 다른 프로세스(PID: $other)가 사용 중입니다.${C_RESET}" >&2
        return 1
    fi

    rotate_log
    
    if [ -f "$BASE_DIR/scripts/run_service.sh" ]; then
        nohup "$BASE_DIR/scripts/run_service.sh" >> "$LOG_FILE" 2>&1 &
    else
        nohup bash -c "source '$BASE_DIR/.venv/bin/activate' && exec python3 -m uvicorn Server.server:app --host '$SERVER_HOST' --port '$SERVER_PORT'" >> "$LOG_FILE" 2>&1 &
    fi
    echo $! > "$PID_FILE"

    for i in 1 2 3 4; do
        sleep 0.5
        if ! is_running; then
            echo "${C_RED}❌ 서버가 기동 직후 종료되었습니다. 최근 로그:${C_RESET}" >&2
            tail -n 15 "$LOG_FILE" >&2
            rm -f "$PID_FILE"
            return 1
        fi
    done
    echo "${C_GREEN}🟢 [${APP_NAME:-duct-server}] 시작됨${C_RESET} (PID: $(cat "$PID_FILE"), http://$SERVER_HOST:$SERVER_PORT)"
}

do_stop() {
    clean_stale_pid
    if ! is_running; then
        rm -f "$PID_FILE"
        echo "ℹ️  실행 중인 서버 프로세스가 없습니다."
        return 0
    fi

    local pid; pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null
    for i in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    echo "🛑 [${APP_NAME:-duct-server}] 서버(PID: $pid) 중지 완료"
}

do_status() {
    clean_stale_pid
    if is_running; then
        echo "🟢 [${APP_NAME:-duct-server}] ${C_GREEN}정상 구동 중${C_RESET} (PID: $(cat "$PID_FILE"), 포트: $SERVER_PORT)"
    else
        echo "⚪ [${APP_NAME:-duct-server}] ${C_RED}정지 상태${C_RESET}"
        return 3
    fi
}

case "${1:-}" in
    start)   do_start ;;
    run)
        shift
        clean_stale_pid
        if is_running; then
            echo "${C_RED}❌ 백그라운드 서버가 이미 실행 중입니다. 먼저 ./manage.sh stop 하세요.${C_RESET}" >&2
            exit 1
        fi
        if [ -f "$BASE_DIR/scripts/run_service.sh" ]; then
            exec "$BASE_DIR/scripts/run_service.sh" "$@"
        else
            start_server_process "$@"
        fi
        ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    logs)    touch "$LOG_FILE"; tail -n 50 -f "$LOG_FILE" ;;
    rotate)  rotate_log ;;
    *)
        echo "사용법: ./manage.sh {start|run|stop|restart|status|logs|rotate}"
        exit 1
        ;;
esac
