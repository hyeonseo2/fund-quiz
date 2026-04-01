from __future__ import annotations

from datetime import date
from datetime import timedelta
from pydantic import BaseModel


class BackfillRequest(BaseModel):
    corp_code: str
    from_date: date | None = None
    to_date: date | None = None


class ReingestRequest(BaseModel):
    rcept_no: str


class RegenerateRequest(BaseModel):
    disclosure_id: int


class JobOut(BaseModel):
    id: int
    job_type: str
    target_type: str
    target_id: str
    status: str
    error_message: str | None = None
