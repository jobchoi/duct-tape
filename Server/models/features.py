"""Known server features; no executable plugins or arbitrary configuration keys."""
from contextlib import closing

DEFAULTS = {'qr': True, 'mdm_download': True}

class Features:
    def __init__(self, jobs):
        self.jobs = jobs

    def initialize(self):
        with closing(self.jobs.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS server_features (id TEXT PRIMARY KEY, enabled INTEGER NOT NULL)')

    def list(self):
        with closing(self.jobs.connect()) as db:
            overrides = dict(db.execute('SELECT id,enabled FROM server_features'))
        return {key: bool(overrides.get(key, value)) for key, value in DEFAULTS.items()}

    def enabled(self, key):
        return self.list().get(key, False)

    def set(self, key, enabled):
        if key not in DEFAULTS:
            raise KeyError(key)
        with closing(self.jobs.connect()) as db, db:
            db.execute('INSERT INTO server_features VALUES (?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled',
                       (key, int(enabled)))
