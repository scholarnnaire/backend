import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.api import deps
from app.schemas import school as schemas
from app.crud import crud_team, crud_school
from app.models.school import Team, School, TeamMember
from app.core.security import get_current_school
from app.api.v1.endpoints.competition import check_team_constitution

router = APIRouter()

def get_or_create_school_team(school: School, db: Session) -> Team:
    if school.teams:
        team = school.teams[0]
        updated = False
        if not team.umbrella_name:
            team.umbrella_name = school.name
            updated = True
        if not team.code:
            team.code = f"TM-{school.id:04d}-{str(uuid.uuid4())[:4].upper()}"
            updated = True
        if updated:
            db.commit()
            db.refresh(team)
        return team
    
    new_team = Team(
        name=f"{school.name} Team",
        umbrella_name=school.name,
        code=f"TM-{school.id:04d}-{str(uuid.uuid4())[:4].upper()}",
        school_id=school.id,
        status="Registration in Progress",
        current_stage="Group Stage 1"
    )
    db.add(new_team)
    db.commit()
    db.refresh(new_team)
    return new_team

@router.get("/my-team")
def get_my_team(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    """Return the authenticated school's official team and umbrella information."""
    team = get_or_create_school_team(school, db)
    constitution = check_team_constitution(team, db)
    return {
        "team_id": team.id,
        "school_id": school.id,
        "school_name": school.name,
        "team_name": team.name,
        "umbrella_name": team.umbrella_name or school.name,
        "team_code": team.code,
        "status": team.status,
        "current_stage": team.current_stage or "Group Stage 1",
        "constitution": constitution,
        "scheduled_exam_date": str(team.scheduled_exam_date) if team.scheduled_exam_date else None,
        "scheduled_exam_time": team.scheduled_exam_time or "10:00 AM"
    }

@router.get("/tournament-info")
def get_tournament_info(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    """Return the enrolled tournament details for the school's team."""
    team = get_or_create_school_team(school, db)
    tournament = team.tournament
    
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    selected_count = db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.is_selected == True).count()
    
    return {
        "enrolled": tournament is not None,
        "tournament_id": tournament.id if tournament else None,
        "tournament_name": tournament.name if tournament else (team.umbrella_name or school.name),
        "team_size": tournament.team_size if tournament else 11,
        "max_schools": tournament.max_schools if tournament else None,
        "member_count": member_count,
        "selected_count": selected_count,
        "slots_remaining": max(0, (tournament.team_size if tournament else 11) - selected_count),
        "team_id": team.id,
        "team_name": team.name,
        "umbrella_name": team.umbrella_name or school.name,
        "team_code": team.code,
        "school_name": school.name,
        "roster_finalized": team.roster_finalized
    }

@router.get("/school/members", response_model=List[schemas.TeamMember])
def get_school_team_members(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    team = get_or_create_school_team(school, db)
    members = crud_team.get_team_members(db, team_id=team.id)
    return members

@router.post("/school/members", response_model=schemas.TeamMember)
def create_team_member(member: schemas.TeamMemberCreate, school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
        
    # Ensure team exists
    if not school.teams:
        new_team = Team(name=f"{school.name} Team", school_id=school.id)
        db.add(new_team)
        db.commit()
        db.refresh(new_team)
        team_id = new_team.id
    else:
        team_id = school.teams[0].id
        
    team = db.query(Team).filter(Team.id == team_id).first()
    if team and team.tournament and team.roster_finalized:
        raise HTTPException(status_code=400, detail="Roster is already finalized for this tournament. Cannot add more members.")
            
    return crud_team.create_team_member(db=db, team_id=team_id, member=member)

@router.put("/members/{member_id}", response_model=schemas.TeamMember)
def update_team_member(member_id: int, member: schemas.TeamMemberCreate, school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    updated_member = crud_team.update_team_member(db, member_id, member)
    if not updated_member:
        raise HTTPException(status_code=404, detail="Team member not found")
    return updated_member

@router.delete("/members/{member_id}")
def delete_team_member(member_id: int, school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    success = crud_team.delete_team_member(db, member_id)
    if not success:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"status": "success"}

class FinalizeRosterPayload(BaseModel):
    member_ids: List[int]

@router.post("/finalize-roster")
def finalize_roster(payload: FinalizeRosterPayload, school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    if not school.teams:
        raise HTTPException(status_code=404, detail="No team found.")
    
    team = school.teams[0]
    if team.roster_finalized:
        raise HTTPException(status_code=400, detail="Roster already finalized.")
        
    tournament = team.tournament
    if not tournament:
        raise HTTPException(status_code=400, detail="Not enrolled in a tournament.")
        
    if len(payload.member_ids) > tournament.team_size:
        raise HTTPException(status_code=400, detail=f"Cannot select more than {tournament.team_size} members.")
        
    # Mark selected members as True, others as False
    db.query(TeamMember).filter(TeamMember.team_id == team.id).update({"is_selected": False})
    
    if payload.member_ids:
        db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.id.in_(payload.member_ids)).update(
            {"is_selected": True}, synchronize_session=False
        )
        
    team.roster_finalized = True
    db.commit()
    
    return {"status": "success", "roster_finalized": True}

@router.post("/reset-roster")
def reset_roster(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    """Allow a school to unlock and redo their roster selection before the tournament starts."""
    if not school.teams:
        raise HTTPException(status_code=404, detail="No team found.")
    
    team = school.teams[0]
    if not team.roster_finalized:
        raise HTTPException(status_code=400, detail="Roster is not finalized yet.")
    
    # Reset all selections and unlock
    db.query(TeamMember).filter(TeamMember.team_id == team.id).update({"is_selected": False})
    team.roster_finalized = False
    db.commit()
    
    return {"status": "success", "roster_finalized": False}

