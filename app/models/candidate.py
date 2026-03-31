from sqlalchemy import Column, Integer, String, Boolean

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    party = Column(String(100), nullable=True)
    number = Column(Integer, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color e.g. "#FF5733"
    is_pledged = Column(Boolean, default=False)  # Is this our pledged candidate
