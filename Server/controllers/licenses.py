"""Authenticated product-key revisions, without plaintext retrieval endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID
from Server.models.license_history import KEYS

class NewKey(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=80, pattern=r'.*\S.*')
    note: str = Field(default='', max_length=240)

class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['apply', 'restore', 'verify', 'fail']
    confirmed: bool = Field(strict=True)


def router(vault, admin, agent, store, root):
    routes = APIRouter()

    def mutation(request: Request):
        if request.headers.get('X-Duct-Tape-Request') != '1':
            raise HTTPException(403, 'Same-origin request required')

    @routes.get('/admin/licenses')
    def page():
        return FileResponse(root/'Server/views/licenses.html')

    @routes.get('/licenses.js')
    def script():
        return FileResponse(root/'Server/views/licenses.js', media_type='text/javascript')

    @routes.get('/api/admin/licenses', dependencies=[Depends(admin)])
    def listing():
        return vault.listing()

    @routes.post('/api/admin/licenses/{app}', dependencies=[Depends(admin), Depends(mutation)])
    def save(app: Literal['office', 'hancom'], body: NewKey):
        try:
            return {'id': vault.save(app, body.key, body.label.strip(), body.note.strip())}
        except ValueError:
            raise HTTPException(422, 'Invalid product key format') from None

    @routes.post('/api/admin/licenses/{app}/{revision}', dependencies=[Depends(admin), Depends(mutation)])
    def change(app: Literal['office', 'hancom'], revision: UUID, body: Change):
        if not body.confirmed:
            raise HTTPException(422, 'Explicit confirmation required')
        try:
            vault.change(app, str(revision), body.action)
        except LookupError:
            raise HTTPException(404, 'Unknown revision') from None
        except FileExistsError:
            raise HTTPException(409, '셋업 작업 종료 후 적용·복구·상태 변경을 진행하세요.') from None
        except ValueError:
            raise HTTPException(409, '문제 이력은 적용할 수 없으며 복구에는 정상 확인 이력이 필요합니다.') from None
        return vault.listing()

    @routes.get('/api/agent/licenses')
    def keys(device_id=Depends(agent)):
        if not store.info(device_id)['approved']:
            raise HTTPException(403, 'Administrator approval required')
        snapshot = vault.snapshot()
        if any(value is None for value in snapshot.values()):
            raise HTTPException(409, 'Restore a working product key before setup')
        vault.record_usage(device_id)
        return {'keys': [{'app': app, 'key': value.decode()} for app, value in snapshot.items() if app in KEYS]}

    return routes
