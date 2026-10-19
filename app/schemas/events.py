from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
from app.schemas.school import Team

class MatchEventBase(BaseModel):
    name: str
    subtitle: Optional[str] = None
    category: Optional[str] = "Tournament"
    event_type: Optional[str] = "tournament"
    time_str: Optional[str] = "7:00 PM (WAT)"
    status: Optional[str] = "upcoming"
    is_live: Optional[bool] = False
    is_featured: Optional[bool] = False
    venue: Optional[str] = "Online (In-App Live Arena)"
    teams_count: Optional[str] = "32 Teams"
    stage: Optional[str] = "Group Stage 2"
    round_info: Optional[str] = None
    format: Optional[str] = "100 Questions / 7 Challenges"
    duration: Optional[str] = "Approx. 2 Hours"
    prize: Optional[str] = None
    quote: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    prizes_detail: Optional[str] = None
    how_it_works: Optional[str] = None
    spec_badges: Optional[str] = None
    banner_url: Optional[str] = None

class MatchEventCreate(MatchEventBase):
    date: Optional[datetime] = None

class MatchEventUpdate(BaseModel):
    name: Optional[str] = None
    subtitle: Optional[str] = None
    category: Optional[str] = None
    event_type: Optional[str] = None
    date: Optional[datetime] = None
    time_str: Optional[str] = None
    status: Optional[str] = None
    is_live: Optional[bool] = None
    is_featured: Optional[bool] = None
    venue: Optional[str] = None
    teams_count: Optional[str] = None
    stage: Optional[str] = None
    round_info: Optional[str] = None
    format: Optional[str] = None
    duration: Optional[str] = None
    prize: Optional[str] = None
    quote: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    prizes_detail: Optional[str] = None
    how_it_works: Optional[str] = None
    spec_badges: Optional[str] = None
    banner_url: Optional[str] = None

class MatchEvent(MatchEventBase):
    id: int
    date: datetime
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LiveMatchBase(BaseModel):
    event_id: int
    team1_id: Optional[int] = None
    team2_id: Optional[int] = None
    room: Optional[str] = None
    status: Optional[str] = "Waiting"

class LiveMatchCreate(LiveMatchBase):
    pass

class LiveMatch(LiveMatchBase):
    id: int
    team1_score: int
    team2_score: int
    
    team1: Optional[Team] = None
    team2: Optional[Team] = None
    event: Optional[MatchEvent] = None

    class Config:
        from_attributes = True

class EventRegistrationCreate(BaseModel):
    event_id: int
    team_id: int

class EventRegistrationOut(BaseModel):
    id: int
    event_id: int
    team_id: int
    status: str
    registered_at: datetime
    team_name: Optional[str] = None
    school_name: Optional[str] = None
    member_count: Optional[int] = 0

    class Config:
        from_attributes = True
