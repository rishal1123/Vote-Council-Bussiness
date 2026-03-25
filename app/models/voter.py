from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class PledgeStatus(str, enum.Enum):
    yes = "yes"
    no = "no"
    undecided = "undecided"


class VoteStatus(str, enum.Enum):
    not_voted = "not_voted"
    voted_pledged = "voted_pledged"
    voted_other = "voted_other"
    undecided = "undecided"


# Many-to-many relationship between voters and focals
voter_focal = Table(
    "voter_focal",
    Base.metadata,
    Column("voter_id", Integer, ForeignKey("voters.id"), primary_key=True),
    Column("focal_id", Integer, ForeignKey("focals.id"), primary_key=True)
)


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, index=True)
    ec_number = Column(Integer, nullable=True, index=True)  # EC # - Election Commission sequence
    voter_id = Column(String(50), unique=True, index=True, nullable=True)  # # column from Excel
    national_id = Column(String(20), unique=True, index=True, nullable=True)  # ID - National ID card
    name = Column(String(100), nullable=False, index=True)
    gender = Column(String(10), nullable=True)
    age = Column(Integer, nullable=True)
    party = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    contact = Column(String(100), nullable=True)  # Increased size for multi-line contacts
    new_contact = Column(String(100), nullable=True)
    previous_island = Column(String(100), nullable=True)
    previous_address = Column(String(255), nullable=True)
    current_location = Column(String(255), nullable=True)
    box_number = Column(String(20), nullable=True)  # Box# - e.g., "B2.1"
    zone = Column(String(50), nullable=True)
    focal_comment = Column(String(500), nullable=True)
    remarks = Column(String(500), nullable=True)  # Remarks column

    photo_path = Column(String(255), nullable=True)
    box_id = Column(Integer, ForeignKey("boxes.id"), nullable=True)
    is_pledged = Column(Enum(PledgeStatus), default=PledgeStatus.no)
    vote_status = Column(Enum(VoteStatus), default=VoteStatus.not_voted)
    voted_for = Column(String(100), nullable=True)  # Store name/info of who they voted for
    voted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    box = relationship("Box", back_populates="voters")
    focals = relationship("Focal", secondary=voter_focal, back_populates="voters")
