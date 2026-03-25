from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.voter import VoteStatus


class VoterBase(BaseModel):
    name: str
    voter_id: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    party: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None
    new_contact: Optional[str] = None
    previous_island: Optional[str] = None
    previous_address: Optional[str] = None
    current_location: Optional[str] = None
    zone: Optional[str] = None
    focal_comment: Optional[str] = None
    is_pledged: bool = False


class VoterCreate(VoterBase):
    box_id: Optional[int] = None
    focal_ids: Optional[List[int]] = None


class VoterUpdate(BaseModel):
    name: Optional[str] = None
    voter_id: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    party: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None
    new_contact: Optional[str] = None
    previous_island: Optional[str] = None
    previous_address: Optional[str] = None
    current_location: Optional[str] = None
    zone: Optional[str] = None
    focal_comment: Optional[str] = None
    is_pledged: Optional[bool] = None
    box_id: Optional[int] = None
    focal_ids: Optional[List[int]] = None


class VoterStatusUpdate(BaseModel):
    vote_status: VoteStatus
    voted_for: Optional[str] = None


class FocalBrief(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class BoxBrief(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class VoterResponse(VoterBase):
    id: int
    photo_path: Optional[str] = None
    box_id: Optional[int] = None
    box: Optional[BoxBrief] = None
    vote_status: VoteStatus
    voted_for: Optional[str] = None
    focals: List[FocalBrief] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VoterListResponse(BaseModel):
    id: int
    name: str
    voter_id: Optional[str] = None
    box: Optional[BoxBrief] = None
    is_pledged: bool
    vote_status: VoteStatus
    contact: Optional[str] = None
    focals: List[FocalBrief] = []

    class Config:
        from_attributes = True
