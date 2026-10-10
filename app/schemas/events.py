from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.schemas.school import Team

class MatchEventBase(BaseModel):
    name: str
    category: str
    prize: Optional[str] = None
    status: Optional[str] = "Scheduled"

class MatchEventCreate(MatchEventBase):
    pass

class MatchEvent(MatchEventBase):
    id: int
    date: datetime

    class Config:
        from_attributes = True

class LiveMatchBase(BaseModel):
    event_id: int
    team1_id: int
    team2_id: int
    room: Optional[str] = None
    status: Optional[str] = "Waiting"

class LiveMatchCreate(LiveMatchBase):
    pass

class LiveMatch(LiveMatchBase):
    id: int
    team1_score: int
    team2_score: int
    
    # We might want to include team details directly for the UI
    team1: Optional[Team] = None
    team2: Optional[Team] = None
    event: Optional[MatchEvent] = None

    class Config:
        from_attributes = True
