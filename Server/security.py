"""Explicit test policy, independent of device/job business rules."""
from uuid import UUID
from fastapi import HTTPException


class SecurityPolicy:
    def __init__(self, mode='secure'):
        if mode not in ('secure', 'development'):
            raise ValueError('DUCT_AUTH_MODE must be secure or development')
        self.mode = mode

    @property
    def development(self):
        return self.mode == 'development'

    def device(self, request, store):
        if request.headers.get('X-Duct-Tape-Request') != '1':
            raise HTTPException(403, 'Same-origin request required')
        try:
            value = str(UUID(request.headers.get('X-Duct-Device-ID', '')))
            store.info(value)
        except (ValueError, LookupError):
            raise HTTPException(401, 'Connect this PC first') from None
        return value
