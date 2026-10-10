from pydantic import BaseModel
from typing import List, Optional
from app.models.school import SchoolCategory
from app.schemas.tournament import TournamentTrack

class TeamMemberBase(BaseModel):
    name: str
    role: Optional[str] = "Member"
    subject: Optional[str] = "General Science"
    status: Optional[str] = "Active"
    matches: Optional[int] = 0
    participant_id: Optional[str] = None
    passport_photo_url: Optional[str] = None
    is_captain: Optional[bool] = False
    verification_status: Optional[str] = "Verified"
    current_stage: Optional[str] = "Group Stage 1"
    qualification_status: Optional[str] = "In Progress"
    highest_stage_qualified: Optional[str] = None
    score: Optional[int] = 0

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMember(TeamMemberBase):
    id: int
    team_id: int
    is_selected: Optional[bool] = False

    class Config:
        from_attributes = True

class TeamBase(BaseModel):
    name: str
    tournament_track_id: Optional[int] = None

class TeamCreate(TeamBase):
    school_id: int
    members: List[TeamMemberCreate]

class Team(TeamBase):
    id: int
    school_id: int
    members: List[TeamMember] = []
    track: Optional[TournamentTrack] = None

    class Config:
        from_attributes = True

class SchoolBase(BaseModel):
    name: str
    state: str
    lga: Optional[str] = None
    category: SchoolCategory
    type: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    tournament_track: Optional[str] = None

class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    category: Optional[SchoolCategory] = None
    type: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    tournament_track: Optional[str] = None

class SchoolCreate(SchoolBase):
    admin_username: str
    password: str

class FullRegistrationPayload(SchoolCreate):
    team_members: List[TeamMemberCreate]

class School(SchoolBase):
    id: int
    access_code: Optional[str] = None
    logo_url: Optional[str] = None
    is_approved: Optional[bool] = True
    entry_fee_paid: Optional[bool] = False
    is_flagged: Optional[bool] = False
    teams: List[Team] = []

    class Config:
        from_attributes = True

class SchoolAuthResponse(BaseModel):
    school: School
    access_token: str
    token_type: str
