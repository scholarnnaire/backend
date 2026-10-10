from pydantic import BaseModel
from datetime import datetime

class MatchResultBase(BaseModel):
    school_id: int
    final_rung: int = 0
    average_response_time: float = 0.0
    fastest_answer: float = 0.0
    slowest_answer: float = 0.0
    subject_accuracy: str = "{}"
    lifelines_used: str = ""
    momentum_streaks: int = 0
    downfall_events: int = 0

class MatchResultCreate(MatchResultBase):
    pass

class MatchResult(MatchResultBase):
    id: int
    match_date: datetime

    class Config:
        from_attributes = True
