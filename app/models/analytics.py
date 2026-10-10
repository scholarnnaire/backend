from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"))
    match_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Analytics Data
    final_rung = Column(Integer, default=0)
    average_response_time = Column(Float, default=0.0) # In seconds
    fastest_answer = Column(Float, default=0.0)
    slowest_answer = Column(Float, default=0.0)
    
    # Subject breakdown JSON string for simplicity, or could be related table
    subject_accuracy = Column(String(255), default="{}") 
    topics_struggled = Column(String(255), default="[]") 
    topics_excelled = Column(String(255), default="[]")
    lifelines_used = Column(String(255), default="")
    
    momentum_streaks = Column(Integer, default=0)
    downfall_events = Column(Integer, default=0)
    
    school = relationship("School", back_populates="match_results")
