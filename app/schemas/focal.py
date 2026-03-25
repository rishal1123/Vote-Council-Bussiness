from pydantic import BaseModel
from typing import Optional


class FocalBase(BaseModel):
    name: str
    phone: Optional[str] = None


class FocalCreate(FocalBase):
    user_id: Optional[int] = None


class FocalUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    user_id: Optional[int] = None


class FocalResponse(FocalBase):
    id: int
    user_id: Optional[int] = None
    voter_count: int = 0

    class Config:
        from_attributes = True
