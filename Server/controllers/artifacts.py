"""Administrator-only, bounded file uploads; never accept a destination path."""
import secrets
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPBearer


def router(directory, admin_token):
    routes = APIRouter()
    bearer = HTTPBearer(auto_error=False)

    def admin(credentials=Depends(bearer)):
        if not admin_token or credentials is None or not secrets.compare_digest(credentials.credentials.encode(), admin_token.encode()):
            raise HTTPException(401, 'Unauthorized')

    @routes.post('/api/upload', dependencies=[Depends(admin)])
    async def upload(file: UploadFile = File(...)):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / str(uuid4())
        try:
            size = 0
            with path.open('xb') as destination:
                while chunk := await file.read(1024*1024):
                    size += len(chunk)
                    if size > 100*1024*1024:
                        raise HTTPException(413, 'File too large')
                    destination.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return {'id': path.name, 'size': size}

    return routes
