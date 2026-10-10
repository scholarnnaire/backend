from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.core.security import decode_access_token, get_current_school
from app.models.school import School, Team, MatchParticipant, TournamentMatch
from app.api.v1.websockets.match_manager import arena_controller

router = APIRouter()

async def get_team_from_token(token: str, db: Session) -> Team:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    school_id = payload.get("sub")
    if not school_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    # For MVP, just get the first active team for this school.
    # In a real app, the token should probably contain the team ID.
    team = db.query(Team).filter(Team.school_id == int(school_id)).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team

from pydantic import BaseModel

class AnswerRequest(BaseModel):
    answer: str

class LifelineRequest(BaseModel):
    lifeline: str

@router.get("/matches/{match_id}/state")
async def get_match_state(match_id: int, db: Session = Depends(deps.get_db), current_user: School = Depends(get_current_school)):
    team = db.query(Team).filter(Team.school_id == current_user.id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    participant = db.query(MatchParticipant).filter(
        MatchParticipant.match_id == match_id,
        MatchParticipant.team_id == team.id
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Not in this match")
        
    match_manager = arena_controller.get_match(match_id)
    if len(match_manager.questions) == 0:
        await match_manager.initialize_questions(db, match_id)
        
    state = match_manager.get_public_state()
    state["my_used_lifelines"] = match_manager.used_lifelines.get(team.id, [])
    return state

@router.post("/matches/{match_id}/answer")
async def submit_answer(match_id: int, req: AnswerRequest, db: Session = Depends(deps.get_db), current_user: School = Depends(get_current_school)):
    team = db.query(Team).filter(Team.school_id == current_user.id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    match_manager = arena_controller.get_match(match_id)
    await match_manager.process_message(team.id, {"type": "lock_answer", "answer": req.answer})
    return {"status": "success"}

@router.post("/matches/{match_id}/lifeline")
async def use_lifeline(match_id: int, req: LifelineRequest, db: Session = Depends(deps.get_db), current_user: School = Depends(get_current_school)):
    team = db.query(Team).filter(Team.school_id == current_user.id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    match_manager = arena_controller.get_match(match_id)
    await match_manager.process_message(team.id, {"type": "use_lifeline", "lifeline": req.lifeline})
    return {"status": "success"}

@router.post("/matches/{match_id}/start-arena")
async def start_arena(match_id: int, db: Session = Depends(deps.get_db)):
    # This should be protected by an admin dependency, but omitting for brevity
    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    match.status = "active"
    db.commit()
    
    match_manager = arena_controller.get_match(match_id)
    if len(match_manager.questions) == 0:
        await match_manager.initialize_questions(db, match_id)
        
    if match_manager.phase == "waiting":
        await match_manager.start_next_question()
        
    return {"message": "Arena started"}

class PauseRequest(BaseModel):
    reason: Optional[str] = "Substitution in progress"
    details: Optional[dict] = None

@router.post("/matches/{match_id}/pause")
async def pause_arena_match(match_id: int, req: PauseRequest = None):
    match_manager = arena_controller.get_match(match_id)
    reason = req.reason if req else "Substitution in progress"
    details = req.details if req else None
    await match_manager.pause_game(reason=reason, details=details)
    return {"status": "paused", "message": "Arena game paused. All timers frozen."}

@router.post("/matches/{match_id}/resume")
async def resume_arena_match(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.resume_game()
    return {"status": "resumed", "message": "Arena game resumed."}

@router.post("/matches/{match_id}/freeze-timers")
async def freeze_timers(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.freeze_timers()
    return {"status": "success", "timers_frozen": match_manager.timer_frozen}

@router.post("/matches/{match_id}/freeze-questions")
async def freeze_questions(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.freeze_questions()
    return {"status": "success", "questions_frozen": match_manager.questions_frozen}

class SubstitutionRequest(BaseModel):
    team_name: Optional[str] = "Contestant Team"
    outgoing_player: Optional[str] = "Current Contestant"
    incoming_player: Optional[str] = "Substitute Member"
    reason: Optional[str] = "Player fatigued / strategic swap"

@router.post("/matches/{match_id}/substitution/request")
async def request_substitution(match_id: int, req: SubstitutionRequest = None):
    match_manager = arena_controller.get_match(match_id)
    details = req.dict() if req else {}
    await match_manager.request_substitution(details)
    return {"status": "requested", "details": details}

@router.post("/matches/{match_id}/substitution/activate")
async def activate_substitution(match_id: int, req: SubstitutionRequest = None):
    match_manager = arena_controller.get_match(match_id)
    details = req.dict() if req else None
    await match_manager.activate_substitution(details)
    return {"status": "active", "message": "Substitution officially activated"}

@router.post("/matches/{match_id}/substitution/confirm")
async def confirm_substitution(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.confirm_substitution()
    return {"status": "confirmed", "message": "Substitution confirmed completed"}

@router.get("/matches/{match_id}/logs")
async def get_match_logs(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    return {
        "match_id": match_id,
        "logs": match_manager.game_logs
    }

@router.get("/matches/{match_id}/live-console")
async def get_live_console(match_id: int, db: Session = Depends(deps.get_db)):
    from sqlalchemy.orm import joinedload
    from app.models.school import TeamMember
    match = db.query(TournamentMatch).options(
        joinedload(TournamentMatch.stage),
        joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team).joinedload(Team.members)
    ).filter(TournamentMatch.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    match_manager = arena_controller.get_match(match_id)
    if len(match_manager.questions) == 0:
        await match_manager.initialize_questions(db, match_id)

    participants_data = []
    for p in match.participants:
        members_data = []
        if p.team and p.team.members:
            for m in p.team.members:
                members_data.append({
                    "id": m.id,
                    "name": m.name,
                    "role": m.role,
                    "is_captain": m.is_captain
                })
        participants_data.append({
            "participant_id": p.id,
            "team_id": p.team_id,
            "team_name": p.team.name if p.team else f"Team {p.team_id}",
            "score": p.score,
            "members": members_data
        })

    public_state = match_manager.get_public_state()

    return {
        "id": match.id,
        "name": match.name or f"Match #{match.id}",
        "stage_name": match.stage.name if match.stage else "Group Stage 2",
        "status": match.status,
        "participants": participants_data,
        "state": public_state
    }

