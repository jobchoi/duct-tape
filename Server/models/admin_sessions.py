"""Short-lived server-side sessions; raw credentials never enter browser storage."""
import hashlib
import secrets
import threading
import time

COOKIE = 'duct_admin_session'
HEADER = 'X-Duct-Tape-Request'


class AdminSessions:
    lifetime = 8 * 60 * 60

    def __init__(self):
        self.entries = {}
        self.lock = threading.Lock()

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self):
        value = secrets.token_urlsafe(32)
        now = time.time()
        with self.lock:
            self.entries = {key: expires for key, expires in self.entries.items() if expires > now}
            self.entries[self.digest(value)] = now + self.lifetime
        return value

    def authenticated(self, request):
        # A cross-origin HTML form cannot supply this header. No CORS is enabled.
        if request.headers.get(HEADER) != '1':
            return False
        value = request.cookies.get(COOKIE)
        if not value:
            return False
        with self.lock:
            expires = self.entries.get(self.digest(value), 0)
        return expires > time.time()

    def revoke(self, request):
        value = request.cookies.get(COOKIE)
        if value:
            with self.lock:
                self.entries.pop(self.digest(value), None)
