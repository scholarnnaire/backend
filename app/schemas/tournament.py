from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class TournamentTrackBase(BaseModel):
    name: str
    description: Optional[str] = None
    entry_fee: Optional[str] = None
    is_active: Optional[bool] = True

class TournamentTrackCreate(TournamentTrackBase):
    pass

class TournamentTrackUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entry_fee: Optional[str] = None
    is_active: Optional[bool] = None

class TournamentTrack(TournamentTrackBase):
    id: int

    class Config:
        from_attributes = True

class TournamentBase(BaseModel):
    name: str
    description: Optional[str] = None
    tournament_track_id: int
    is_active: Optional[bool] = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    school_categories: Optional[str] = None  # comma-separated
    scope: Optional[str] = "global"  # 'global' or 'state'
    state: Optional[str] = None  # Nigerian state name, set when scope == 'state'
    entry_fee: Optional[str] = None  # overrides track entry_fee when set
    is_free: Optional[bool] = False
    max_schools: Optional[int] = 100
    team_size: Optional[int] = 5
    status: Optional[str] = "pending"

class TournamentCreate(TournamentBase):
    pass

class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tournament_track_id: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    school_categories: Optional[str] = None
    scope: Optional[str] = None
    state: Optional[str] = None
    entry_fee: Optional[str] = None
    is_free: Optional[bool] = None
    max_schools: Optional[int] = None
    team_size: Optional[int] = None
    status: Optional[str] = None

class Tournament(TournamentBase):
    id: int
    track: Optional[TournamentTrack] = None
    enrolled_count: Optional[int] = 0

    class Config:
        from_attributes = True

class MatchParticipantBase(BaseModel):
    team_id: int
    score: Optional[float] = 0
    is_qualified: Optional[bool] = False

class MatchParticipant(MatchParticipantBase):
    id: int
    match_id: int

    class Config:
        from_attributes = True

class TournamentMatchBase(BaseModel):
    name: str
    match_date: Optional[datetime] = None
    status: Optional[str] = "pending"

class TournamentMatchCreate(TournamentMatchBase):
    pass

class TournamentMatch(TournamentMatchBase):
    id: int
    tournament_stage_id: int
    participants: List[MatchParticipant] = []

    class Config:
        from_attributes = True

class TournamentStageBase(BaseModel):
    name: str
    stage_order: Optional[int] = 1
    qualifier_count: Optional[int] = 1
    match_format: Optional[str] = "knockout"
    status: Optional[str] = "pending"

class TournamentStageCreate(TournamentStageBase):
    pass

class TournamentStageUpdate(BaseModel):
    name: Optional[str] = None
    stage_order: Optional[int] = None
    qualifier_count: Optional[int] = None
    match_format: Optional[str] = None
    status: Optional[str] = None

class TournamentStage(TournamentStageBase):
    id: int
    tournament_id: int
    matches: List[TournamentMatch] = []

    class Config:
        from_attributes = True
