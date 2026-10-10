from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    amount = Column(Float, nullable=False)
    status = Column(String(50), default="Pending") # Pending, Approved, Rejected
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    team = relationship("Team")
