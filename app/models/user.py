from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    focal = "focal"
    operator = "operator"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.operator, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to focal (optional - a user may be linked to a focal)
    focal = relationship("Focal", back_populates="user", uselist=False)
