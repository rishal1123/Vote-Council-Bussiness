from pydantic import BaseModel
from typing import Optional


class CandidateBase(BaseModel):
    name: str
    party: Optional[str] = None
    number: Optional[int] = None
    is_pledged: bool = False


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    party: Optional[str] = None
    number: Optional[int] = None
    is_pledged: Optional[bool] = None


class CandidateResponse(CandidateBase):
    id: int

    class Config:
        from_attributes = True
