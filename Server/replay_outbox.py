"""Run from repository root: python -m Server.replay_outbox [--retry-failed]."""
import argparse
import json
import os
from pathlib import Path

from Server.gas_relay import GasRelay, load_schools
from Server.outbox import Outbox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-failed', action='store_true', help='Explicitly reset failed jobs after correcting their cause')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error('--limit must be 1..1000')
    database = Path(os.environ.get('DUCT_DB_PATH', Path(__file__).parent / 'data/monitoring.sqlite3'))
    try:
        queue = Outbox(database, GasRelay(load_schools()), int(os.environ.get('DUCT_SENT_RETENTION_DAYS', '30')))
        if args.retry_failed:
            queue.replay_failed()
        queue.drain(args.limit)
        print(json.dumps(queue.summary()))
        return 1 if queue.last_error else 0
    except Exception:
        print('{"error":"replay_unavailable"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
