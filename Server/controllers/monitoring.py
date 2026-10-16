"""Monitoring API controllers; device data is protected by role dependencies."""
from contextlib import closing
from datetime import datetime, timezone
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from Server.models.monitoring import Report
from Server.outbox import enqueue

def router(queue, connect, registry, require_writer, require_reader, reporting_device):
    routes = APIRouter()
    @routes.post('/api/report')
    def receive(report: Report, background_tasks: BackgroundTasks, school=Depends(require_writer), device_id=Depends(reporting_device)):
        if device_id is not None and str(report.device_id) != device_id:
            raise HTTPException(403, 'Device scope mismatch')
        if report.school_code != school:
            raise HTTPException(403, 'School scope mismatch')
        if school is not None and report.grade > (6 if registry[school]['school_type'] == 'elementary' else 3):
            raise HTTPException(422, 'Invalid grade for school')
        payload = report.model_dump(mode='json')
        observed = report.observed_at.isoformat(timespec='microseconds')
        received = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        payload['observed_at'] = observed
        if school is not None:
            payload.update(school_type=registry[school]['school_type'], schema_version=1, received_at=received)
        with queue.write_lock, closing(connect()) as db, db:
            # Queue event and latest state commit atomically, before network work starts.
            fresh = enqueue(db, payload) if school is not None else True
            updated = False
            if fresh:
                result = db.execute('''INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(school_code, device_id) DO UPDATE SET
                        report_id=excluded.report_id, observed_at=excluded.observed_at,
                        received_at=excluded.received_at, payload=excluded.payload
                    WHERE excluded.observed_at > devices.observed_at
                        AND excluded.report_id != devices.report_id''',
                    (school or '', str(report.device_id), str(report.report_id), observed, received,
                     json.dumps(payload, ensure_ascii=False)))
                updated = result.rowcount == 1
        background_tasks.add_task(queue.drain)
        return {'accepted': True, 'updated': updated}

    @routes.get('/api/outbox', dependencies=[Depends(require_reader)])
    def outbox_status():
        return queue.summary()

    @routes.get('/api/devices', dependencies=[Depends(require_reader)])
    def devices():
        with closing(connect()) as db:
            rows = db.execute('SELECT payload, received_at FROM devices ORDER BY received_at DESC').fetchall()
        return {'devices': [dict(json.loads(row['payload']), received_at=row['received_at']) for row in rows]}

    return routes
