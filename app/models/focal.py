from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Focal(Base):
    __tablename__ = "focals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="focal")
    voters = relationship("Voter", secondary="voter_focal", back_populates="focals")
