"""Signed, bounded GAS transport. Never log credentials, envelopes or raw errors."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit

import httpx


class RelayError(Exception):
    def __init__(self, code, retryable=False):
        super().__init__(code)
        self.code, self.retryable = code, retryable


def valid_endpoint(url):
    return isinstance(url, str) and re.fullmatch(
        r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url) is not None


def load_schools(path=None):
    path = path or os.environ.get('DUCT_SCHOOLS_PATH')
    if not path:
        return {}
    try:
        with open(path, encoding='utf-8') as source:
            data = json.load(source)
        if not isinstance(data, dict):
            raise ValueError()
        for code, school in data.items():
            if (not re.fullmatch(r'[A-Z0-9_-]{1,32}', code)
                    or school['school_type'] not in ('elementary', 'middle', 'high')):
                raise ValueError()
            # Secrets are resolved locally; only environment variable names live in examples.
            school['report_token'] = os.environ[school['report_token_env']]
        return data
    except Exception:
        raise RuntimeError('Invalid school registry or missing report token environment.') from None


class GasRelay:
    def __init__(self, schools, transport=None):
        self.schools, self.transport = schools, transport

    def send(self, payload):
        school = self.schools.get(payload['school_code'], {})
        endpoint, key_id = school.get('gas_url'), school.get('key_id')
        secret = os.environ.get(school.get('secret_env', ''), '')
        if (not valid_endpoint(endpoint) or not isinstance(key_id, str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key_id)
                or len(secret) < 32 or secret == school.get('report_token')):
            raise RelayError('relay_config')
        sent_at = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        signature = hmac.new(secret.encode(), (sent_at + '\n' + payload_json).encode(), hashlib.sha256).hexdigest()
        envelope = dict(schema_version=1, key_id=key_id, sent_at=sent_at,
                        payload_json=payload_json, signature=signature)
        try:
            with httpx.Client(timeout=httpx.Timeout(5, connect=3), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                response = client.post(endpoint, json=envelope)
                # GAS ContentService uses a one-time Google URL. Never forward POST body.
                if response.status_code in (301, 302, 303):
                    location = response.headers.get('location', '')
                    target = urlsplit(location)
                    if (target.scheme != 'https' or target.hostname != 'script.googleusercontent.com'
                            or target.port not in (None, 443) or target.username or target.password
                            or target.fragment or target.path != '/macros/echo'):
                        raise RelayError('redirect_invalid')
                    response = client.get(location)
                if response.status_code == 429 or response.status_code >= 500:
                    raise RelayError('http_unavailable', True)
                if response.status_code != 200:
                    raise RelayError('http_rejected')
                if len(response.content) > 16384:
                    raise RelayError('response_invalid')
                result = response.json()
                if not isinstance(result, dict):
                    raise RelayError('response_invalid')
                if result.get('ok') is True and result.get('report_id') == payload['report_id'] and result.get('result') in ('updated', 'duplicate', 'stale'):
                    return
                code = result.get('error')
                if code in ('lock_busy', 'sheet_unavailable'):
                    raise RelayError(code, True)
                if code in ('auth_failed', 'schema_invalid', 'unknown_school', 'schema_mismatch'):
                    raise RelayError(code)
                raise RelayError('response_invalid')
        except httpx.TransportError:
            raise RelayError('network_unavailable', True) from None
        except (ValueError, TypeError):
            raise RelayError('response_invalid') from None
