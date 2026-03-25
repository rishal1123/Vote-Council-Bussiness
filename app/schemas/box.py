from pydantic import BaseModel
from typing import Optional


class BoxBase(BaseModel):
    name: str
    location: Optional[str] = None


class BoxCreate(BoxBase):
    pass


class BoxUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None


class BoxResponse(BoxBase):
    id: int
    voter_count: int = 0

    class Config:
        from_attributes = True
