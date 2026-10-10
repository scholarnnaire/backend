from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

class MatchEvent(Base):
    __tablename__ = "match_events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False) # e.g., Secondary, Primary
    date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="Scheduled") # Scheduled, Ongoing, Completed
    prize = Column(String(100), nullable=True) # e.g., ₦500,000

    matches = relationship("LiveMatch", back_populates="event")

class LiveMatch(Base):
    __tablename__ = "live_matches"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("match_events.id"))
    team1_id = Column(Integer, ForeignKey("teams.id"))
    team2_id = Column(Integer, ForeignKey("teams.id"))
    status = Column(String(50), default="Waiting") # Waiting, In Match, Completed
    room = Column(String(100), nullable=True)
    team1_score = Column(Integer, default=0)
    team2_score = Column(Integer, default=0)

    event = relationship("MatchEvent", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
