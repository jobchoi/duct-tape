"""Structured progress only; never accept arbitrary installer stdout or keys."""
from typing import Literal
from pathlib import PurePosixPath
from pydantic import BaseModel, ConfigDict, Field, model_validator
from Server.models.application_catalog import module_paths

PHASES = {
    'queued':'서버 요청 접수', 'starting':'실행 도구 준비', 'media_ready':'설치 원본 확인',
    'download':'설치 매체 다운로드', 'extract':'압축 해제', 'prepare':'설치 파일 배치',
    'report':'서버 통신 확인', 'module':'애플리케이션 작업', 'complete':'셋업 완료', 'error':'작업 실패',
}
MODULES = {
    '01_GetInfo.ps1':'기기 정보 수집', '02_CheckOffice.ps1':'Office 설치 상태 확인',
    '03_RemoveOffice.ps1':'기존 Office 제거', '04_InstallOffice.ps1':'Office 설치 단계',
    '05_CheckHancom.ps1':'한컴 설치 상태 확인', '06_InstallHancom.ps1':'한컴 설치 단계',
}


class ProgressEvent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sequence: int = Field(ge=1,le=1000000,strict=True)
    phase: Literal['starting','media_ready','download','extract','prepare','report','module','complete','error']
    status: Literal['started','progress','completed','failed']
    module: str | None = Field(default=None,max_length=100)
    current: int | None = Field(default=None,ge=0,le=2**63-1,strict=True)
    total: int | None = Field(default=None,ge=1,le=2**63-1,strict=True)
    unit: Literal['bytes','items','steps'] | None = None

    @model_validator(mode='after')
    def validate_progress(self):
        known={PurePosixPath(p).name for p in module_paths()}
        if self.module is not None and (self.phase!='module' or self.module not in known):
            raise ValueError('Unknown progress module')
        if self.phase=='module' and self.module is None:
            raise ValueError('Module required')
        if self.current is not None and self.total is not None and self.current>self.total:
            raise ValueError('Invalid progress counter')
        if self.unit is None and (self.current is not None or self.total is not None):
            raise ValueError('Counter unit required')
        return self


class ProgressBatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    events: list[ProgressEvent] = Field(min_length=1,max_length=32)


def label(event):
    return MODULES.get(event.get('module'), event.get('module')) if event['phase']=='module' else PHASES[event['phase']]
