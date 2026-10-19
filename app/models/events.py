from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

class MatchEvent(Base):
    __tablename__ = "match_events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True) # e.g., "Round 1 of 4 • Group A & B"
    category = Column(String(255), default="Tournament") # Tournament, Special Event, Live Match
    event_type = Column(String(50), default="tournament") # all, live, upcoming, completed, tournament, special
    date = Column(DateTime, default=datetime.datetime.utcnow)
    time_str = Column(String(100), default="7:00 PM (WAT)")
    status = Column(String(50), default="upcoming") # live, upcoming, completed, Scheduled
    is_live = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    venue = Column(String(255), default="Online (In-App Live Arena)")
    teams_count = Column(String(100), default="32 Teams")
    stage = Column(String(100), default="Group Stage 2")
    round_info = Column(String(100), nullable=True)
    format = Column(String(255), default="100 Questions / 7 Challenges")
    duration = Column(String(100), default="Approx. 2 Hours")
    prize = Column(String(255), nullable=True)
    quote = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    rules = Column(Text, nullable=True) # JSON string
    prizes_detail = Column(Text, nullable=True) # JSON string
    how_it_works = Column(Text, nullable=True) # JSON string
    spec_badges = Column(Text, nullable=True) # JSON string
    banner_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    matches = relationship("LiveMatch", back_populates="event", cascade="all, delete-orphan")
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")

class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("match_events.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    registered_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="Confirmed") # Confirmed, Waitlist, Disqualified

    event = relationship("MatchEvent", back_populates="registrations")
    team = relationship("Team")

class LiveMatch(Base):
    __tablename__ = "live_matches"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("match_events.id"))
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    status = Column(String(50), default="Waiting") # Waiting, In Match, Completed, Live
    room = Column(String(100), nullable=True)
    team1_score = Column(Integer, default=0)
    team2_score = Column(Integer, default=0)

    event = relationship("MatchEvent", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
