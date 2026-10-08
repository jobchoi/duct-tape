from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from Server.database import connect


def test_concurrent_short_connections_and_failure_release(tmp_path):
    db=tmp_path/'state.db'
    with closing(connect(db)) as c,c:c.execute('CREATE TABLE values_test(value INTEGER)')
    def write(value):
        with closing(connect(db)) as c,c:c.execute('INSERT INTO values_test VALUES (?)',(value,))
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(write,i) for i in range(80)]
        for future in futures:future.result(timeout=10)
    with closing(connect(db)) as c:assert c.execute('SELECT count(*) FROM values_test').fetchone()[0]==80
    missing=tmp_path/'missing'/'db'
    with pytest.raises(sqlite3.OperationalError):connect(missing)
    missing.parent.mkdir()
    c=connect(missing);c.close();c.close()
    with closing(connect(missing)) as c:assert c.execute('SELECT 1').fetchone()[0]==1
