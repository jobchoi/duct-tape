"""Serialize short SQLite connection lifetimes per file across app worker threads.

Network and installer work stay outside these connections. This also avoids
concurrent connect/close stalls in the deployed Python/SQLite runtime.
"""
from pathlib import Path
import sqlite3
import threading

_guards={}
_registry_lock=threading.Lock()


class Connection(sqlite3.Connection):
    def close(self):
        guard=getattr(self,'_guard',None)
        try:
            super().close()
        finally:
            if guard is not None:
                self._guard=None
                guard.release()


def connect(database, timeout=10):
    name=str(Path(database).resolve())
    with _registry_lock:
        guard=_guards.setdefault(name,threading.RLock())
    guard.acquire()
    try:
        connection=sqlite3.connect(database,timeout=timeout,factory=Connection)
        connection._guard=guard
        return connection
    except BaseException:
        guard.release()
        raise
