"""Read-only readiness gate. Configure URL and admin token through the environment."""
import json
import os
import sys
from urllib.request import Request, urlopen


def main():
    url = os.environ.get('DUCT_DEPLOY_URL', 'http://127.0.0.1:8100').rstrip('/')
    token = os.environ.get('DUCT_ADMIN_TOKEN', '')
    headers = {'X-Duct-Tape-Request': '1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urlopen(Request(url + '/api/admin/deploy-readiness', headers=headers), timeout=10) as response:
            result = json.load(response)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('ready') is True else 1
    except Exception as exc:
        print('배포 점검 실패:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
