#!/usr/bin/env bash
# Read-only report. Never read env/key files or print raw application logs.
set -u
root=${1:-/home/jobchoi/web-server}
section() { printf '\n[%s]\n' "$1"; }
section timestamp
date -Is
section host
uname -sm
section project-root
if [[ ! -d "$root" ]]; then
  printf 'Missing directory: %s\n' "$root"
  exit 1
fi
printf '%s\n' "$root"
find "$root" -mindepth 1 -maxdepth 1 -type d -printf '%f/\n' | sort
section compose-files
find "$root" -maxdepth 2 -type f \( -name 'compose*.yml' -o -name 'docker-compose*.yml' -o -name 'compose*.yaml' -o -name 'docker-compose*.yaml' \) -printf '%P\n' | sort
section repository
repo="$root/duct-tape/repo"
if [[ ! -d "$repo/.git" ]]; then repo="$root/duct-tape"; fi
if [[ -d "$repo/.git" ]]; then
  git -C "$repo" log -1 --format='%h %cs'
  git -C "$repo" status --short --branch
fi
section disk
df -h "$root"
section containers
if command -v docker >/dev/null 2>&1; then
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'
else
  printf 'Docker unavailable\n'
fi
section duct-tape-health
# Print only known readiness fields, never an unrestricted HTTP response.
python3 - <<'PY'
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/config', timeout=10) as r:
        s = json.load(r)
    m = s.get('media', {})
    print(json.dumps({'media_ready': m.get('ready'), 'missing_file_count': len(m.get('missing', []))}, ensure_ascii=False))
except Exception as e:
    print('Health check failed:', type(e).__name__)
PY
section log-policy
printf 'Raw container logs and credential/configuration contents intentionally excluded.\n'
