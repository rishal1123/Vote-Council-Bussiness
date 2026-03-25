from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Box(Base):
    __tablename__ = "boxes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    location = Column(String(255), nullable=True)

    # Relationship to voters
    voters = relationship("Voter", back_populates="box")
