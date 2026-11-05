"""Admin-only feature controls and QR utility."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from Server.models.qr import encode

class Toggle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = Field(strict=True)

class QRInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str = Field(min_length=1, max_length=1024)


def router(features, admin, root):
    routes = APIRouter()

    @routes.get('/admin/tools')
    @routes.get('/admin/tools/qr')
    def page():
        return FileResponse(root/'Server/views/tools.html')

    @routes.get('/tools.js')
    def script():
        return FileResponse(root/'Server/views/tools.js', media_type='text/javascript')

    @routes.get('/api/admin/features', dependencies=[Depends(admin)])
    def settings():
        return {'features': features.list()}

    @routes.put('/api/admin/features/{key}', dependencies=[Depends(admin)])
    def toggle(key: str, body: Toggle):
        try:
            features.set(key, body.enabled)
        except KeyError:
            raise HTTPException(404, 'Unknown feature') from None
        return {'features': features.list()}

    @routes.post('/api/admin/tools/qr', dependencies=[Depends(admin)])
    def generate(body: QRInput):
        if not features.enabled('qr'):
            raise HTTPException(409, 'QR generation is disabled')
        try:
            return {'matrix': encode(body.value)}
        except ValueError:
            raise HTTPException(422, 'Enter a nonblank value up to 1024 UTF-8 bytes') from None

    return routes
