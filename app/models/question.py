from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLEnum, ForeignKey
import enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.school import SchoolCategory

class QuestionDifficulty(str, enum.Enum):
    NURSERY = "Nursery"
    KINDERGARTEN = "Kindergarten"
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    TERTIARY = "Tertiary"
    MASTERS = "Masters"
    DON = "Don"
    PHD = "Ph.D."
    ASSOCIATE_PROFESSOR = "Associate Professor"
    PROFESSOR = "Professor"
    SCHOLARNNAIRE = "Scholarnnaire"

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255), nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_option = Column(String(255), nullable=False) # A, B, C, or D
    subject = Column(String(255), nullable=False)
    difficulty = Column(SQLEnum(QuestionDifficulty), nullable=False)
    school_category = Column(SQLEnum(SchoolCategory), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # New fields for tournament association
    tournament_track_id = Column(Integer, ForeignKey("tournament_tracks.id"), nullable=True)
    question_mode = Column(String(50), nullable=True)
    question_type = Column(String(50), nullable=True)
    stage = Column(String(50), default="Group Stage 1", index=True, nullable=True)
    
    tournament_track = relationship("TournamentTrack")
