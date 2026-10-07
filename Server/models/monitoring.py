"""Validated monitoring payload model."""
from datetime import datetime, timezone, timedelta
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Text = Annotated[str, Field(min_length=1, max_length=160)]
InstallState = Literal['확인 전', '설치 필요', '설치 중', '정상', '오류']


class Report(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    school_code: Annotated[str, Field(pattern=r'^[A-Z0-9_-]{1,32}$')] | None = None
    grade: Annotated[int, Field(strict=True, ge=1, le=6)]
    device_id: UUID
    report_id: UUID
    hostname: Text
    serial: Annotated[str, Field(max_length=160)] = ''
    model: Annotated[str, Field(max_length=160)] = ''
    mac: Annotated[str, Field(pattern=r'^$|^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')] = ''
    office: InstallState
    hancom: InstallState
    stage: Literal['Preflight', '01', '02', '03', '04', '05', '06']
    status: Literal['running', 'completed', 'failed']
    error_code: Annotated[str, Field(pattern=r'^[A-Z0-9_]{0,64}$')] = ''
    installer_exit_code: Annotated[int, Field(ge=0, le=4294967295)] | None = None
    reboot_required: bool = False
    observed_at: AwareDatetime

    @field_validator('observed_at')
    @classmethod
    def reject_future(cls, value):
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('clock ahead')
        return value.astimezone(timezone.utc)
