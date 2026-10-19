from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_member_id = Column(Integer, ForeignKey("team_members.id"), nullable=False)
    stage = Column(String(50), default="Group Stage 1", nullable=False) # Group Stage 1, 2, 3, 4
    questions_order = Column(Text, nullable=True) # JSON list of question IDs
    current_question_index = Column(Integer, default=0)
    answers_submitted = Column(Text, nullable=True) # JSON dict of {q_id: selected_option}
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    missed_count = Column(Integer, default=0)
    score = Column(Integer, default=0) # 100 marks per correct answer
    max_score = Column(Integer, default=4400) # 44 * 100 = 4,400
    is_qualified = Column(Boolean, default=False) # True if correct_count >= 24
    status = Column(String(50), default="Scheduled") # Scheduled, In Progress, Completed
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, default=0)

    team = relationship("Team")
    team_member = relationship("TeamMember")

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(String(50), index=True, nullable=False)
    participant_name = Column(String(255), nullable=False)
    team_name = Column(String(255), nullable=False)
    stage = Column(String(50), nullable=False)
    certificate_number = Column(String(100), unique=True, index=True, nullable=False)
    qualification_code = Column(String(100), unique=True, index=True, nullable=False)
    score = Column(Integer, default=0)
    issued_date = Column(DateTime, default=datetime.datetime.utcnow)
    download_url = Column(String(500), nullable=True)

class SubstitutionRequest(Base):
    __tablename__ = "substitution_requests"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_name = Column(String(255), nullable=False)
    captain_name = Column(String(255), nullable=False)
    half = Column(String(50), default="First Half", nullable=False) # "First Half" or "Second Half"
    outgoing_members = Column(Text, nullable=False) # JSON or comma-separated names (up to 3)
    incoming_members = Column(Text, nullable=False) # JSON or comma-separated names (up to 3)
    status = Column(String(50), default="Pending", nullable=False) # "Pending", "Approved", "Completed", "Rejected"
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    team = relationship("Team")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, nullable=True)
    actor_name = Column(String(255), nullable=False)
    actor_role = Column(String(50), default="Team Captain", nullable=False)
    action = Column(String(255), nullable=False) # e.g. "Examination Rescheduled", "Substitution Requested"
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class QuarterFinalSchedule(Base):
    __tablename__ = "quarter_final_schedules"

    id = Column(Integer, primary_key=True, index=True)
    target_quota = Column(Integer, default=32)
    confirmed_teams_count = Column(Integer, default=0)
    status = Column(String(100), default="Quarter-Final Qualification in Progress") 
    # "Quarter-Final Qualification in Progress", "Quarter-Final Qualification Completed", "Quarter-Final Scheduled"
    scheduled_date = Column(Date, nullable=True)
    scheduled_time = Column(String(50), nullable=True)
    venue = Column(String(255), nullable=True)
    instructions = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class Notification(Base):
    __tablename__ = "competition_notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_role = Column(String(50), default="all") # "all", "captain", "participant", "admin", "moderator", "team"
    recipient_id = Column(String(100), nullable=True) # team_id, participant_id, or None
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info") # info, success, warning, exam, substitution, qualification
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class LadderboardConfig(Base):
    __tablename__ = "ladderboard_configs"

    id = Column(Integer, primary_key=True, index=True)
    stage = Column(String(100), default="global", nullable=False) # e.g. "global", "Group Stage 2"
    upper_division_name = Column(String(100), default="Upper Division")
    lower_division_name = Column(String(100), default="Lower Division")
    qualification_threshold = Column(Integer, default=24) # 24 correct
    points_per_correct = Column(Integer, default=100)
    rungs_json = Column(Text, nullable=False) # JSON list of rungs
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class GameDivision(Base):
    __tablename__ = "game_divisions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False) # e.g. "Primary", "Junior Secondary", "Senior Secondary", "Tertiary"
    code = Column(String(50), nullable=True) # e.g. "primary", "junior_sec", "senior_sec", "tertiary"
    description = Column(String(500), nullable=True)
    stages_json = Column(Text, nullable=True) # JSON list of stages
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

