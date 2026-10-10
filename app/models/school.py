from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLEnum, Date, Float, DateTime
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from app.core.database import Base

class SchoolCategory(str, enum.Enum):
    PRIMARY = "Primary"
    JUNIOR_SECONDARY = "Junior Secondary"
    SENIOR_SECONDARY = "Senior Secondary"
    TERTIARY = "Tertiary"
    CORPERS = "Corpers"
    ADULTS = "Adults / Open"

class TournamentTrack(Base):
    __tablename__ = "tournament_tracks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(String(1000), nullable=True) # Rules/Description
    entry_fee = Column(String(100), nullable=True) # E.g. "N10,000"
    is_active = Column(Boolean, default=True)

    teams = relationship("Team", back_populates="track")
    tournaments = relationship("Tournament", back_populates="track", cascade="all, delete-orphan")

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    description = Column(String(1000), nullable=True)
    tournament_track_id = Column(Integer, ForeignKey("tournament_tracks.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    # Comma-separated school categories, e.g. "Primary,Junior Secondary,Senior Secondary"
    school_categories = Column(String(500), nullable=True)
    # Scope: 'global' or 'state'
    scope = Column(String(50), default="global", nullable=False)
    # State name (only relevant when scope == 'state')
    state = Column(String(255), nullable=True)
    # Override entry fee — if set, takes precedence over parent track's entry_fee
    entry_fee = Column(String(100), nullable=True)
    # When True, tournament is free regardless of entry_fee or track fee
    is_free = Column(Boolean, default=False)
    status = Column(String(50), default="pending")
    # Limits
    max_schools = Column(Integer, default=100)
    team_size = Column(Integer, default=5)

    track = relationship("TournamentTrack", back_populates="tournaments")
    teams = relationship("Team", back_populates="tournament")
    stages = relationship("TournamentStage", back_populates="tournament", cascade="all, delete-orphan", order_by="TournamentStage.stage_order")

class TournamentStage(Base):
    __tablename__ = "tournament_stages"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    name = Column(String(255), nullable=False)
    stage_order = Column(Integer, nullable=False, default=1)
    qualifier_count = Column(Integer, nullable=False, default=1)
    match_format = Column(String(100), default="knockout") # knockout, group, round_robin
    status = Column(String(50), default="pending") # pending, active, completed

    tournament = relationship("Tournament", back_populates="stages")
    matches = relationship("TournamentMatch", back_populates="stage", cascade="all, delete-orphan")

class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_stage_id = Column(Integer, ForeignKey("tournament_stages.id"), nullable=False)
    name = Column(String(255), nullable=False) # e.g., Group A, Match 1
    match_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending") # pending, active, completed

    stage = relationship("TournamentStage", back_populates="matches")
    participants = relationship("MatchParticipant", back_populates="match", cascade="all, delete-orphan")

class MatchParticipant(Base):
    __tablename__ = "match_participants"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("tournament_matches.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    score = Column(Float, default=0)
    is_qualified = Column(Boolean, default=False)

    match = relationship("TournamentMatch", back_populates="participants")
    team = relationship("Team")

class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    state = Column(String(255), nullable=False)
    lga = Column(String(255))
    category = Column(SQLEnum(SchoolCategory), nullable=False)
    type = Column(String(255)) # Public / Private
    contact_email = Column(String(255))
    contact_phone = Column(String(255))
    admin_username = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    access_code = Column(String(255), unique=True, index=True)
    reset_password_token = Column(String(255), nullable=True)
    reset_password_expires = Column(DateTime, nullable=True)
    logo_url = Column(String(255), nullable=True)
    is_approved = Column(Boolean, default=True)
    entry_fee_paid = Column(Boolean, default=False)
    tournament_track = Column(String(255), nullable=True)
    is_flagged = Column(Boolean, default=False)
    wallet_balance = Column(Float, default=0.0)
    
    teams = relationship("Team", back_populates="school")
    match_results = relationship("MatchResult", back_populates="school")

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"))
    name = Column(String(255)) # usually same as school name, but allows for Team A / Team B
    code = Column(String(50), unique=True, index=True, nullable=True) # Unique team registration code
    umbrella_name = Column(String(255), nullable=True)
    status = Column(String(100), default="Registration in Progress")
    current_stage = Column(String(50), default="Group Stage 1")
    scheduled_exam_date = Column(Date, nullable=True)
    scheduled_exam_time = Column(String(50), nullable=True)
    is_qf_qualified = Column(Boolean, default=False)
    qf_qualified_at = Column(DateTime, nullable=True)
    substitutions_used_half1 = Column(Integer, default=0)
    substitutions_used_half2 = Column(Integer, default=0)
    tournament_track_id = Column(Integer, ForeignKey("tournament_tracks.id"), nullable=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    roster_finalized = Column(Boolean, default=False)
    
    school = relationship("School", back_populates="teams")
    track = relationship("TournamentTrack", back_populates="teams")
    tournament = relationship("Tournament", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    participant_id = Column(String(50), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    passport_photo_url = Column(String(500), nullable=True)
    role = Column(String(255), default="Member") # "Team Captain" or "Member"
    is_captain = Column(Boolean, default=False)
    verification_status = Column(String(50), default="Verified") # Verified, Pending
    current_stage = Column(String(50), default="Group Stage 1")
    qualification_status = Column(String(50), default="Pending") # Qualified, Not Qualified, In Progress, Pending
    highest_stage_qualified = Column(String(50), nullable=True)
    score = Column(Integer, default=0)
    subject = Column(String(255), default="General Science")
    status = Column(String(255), default="Active")
    is_selected = Column(Boolean, default=False)
    matches = Column(Integer, default=0)

    team = relationship("Team", back_populates="members")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    amount = Column(Float, nullable=False) # In Naira (NGN)
    reference = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(50), default="pending") # pending, success, failed
    payment_type = Column(String(50), default="wallet_topup") # wallet_topup, tournament_entry, withdrawal, prize_reward
    channel = Column(String(50), default="paystack")
    description = Column(String(255), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    school = relationship("School")
    tournament = relationship("Tournament")
