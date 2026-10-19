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

@router.get("/matches/ongoing")
def get_ongoing_matches(db: Session = Depends(deps.get_db)):
    from app.models.school import TournamentMatch, MatchParticipant, Team, TournamentStage
    from sqlalchemy.orm import joinedload
    matches = db.query(TournamentMatch).options(
        joinedload(TournamentMatch.stage).joinedload(TournamentStage.tournament),
        joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team)
    ).all()
    
    active_list = []
    scheduled_list = []
    
    for m in matches:
        participants = []
        for p in m.participants:
            participants.append({
                "participant_id": p.id,
                "team_id": p.team_id,
                "team_name": p.team.name if p.team else f"Team {p.team_id}",
                "score": p.score
            })
        
        item = {
            "id": m.id,
            "name": m.name or f"Match #{m.id}",
            "status": m.status,
            "stage_name": m.stage.name if m.stage else "Group Stage",
            "tournament_name": m.stage.tournament.name if (m.stage and m.stage.tournament) else "Scholarnnaire Tournament",
            "match_date": m.match_date.isoformat() if m.match_date else None,
            "participants": participants
        }
        if m.status == "active":
            active_list.append(item)
        else:
            scheduled_list.append(item)
            
    return {
        "active_matches": active_list,
        "scheduled_matches": scheduled_list,
        "has_ongoing": len(active_list) > 0
    }

@router.get("/matches/{match_id}/live-console")
async def get_live_console(match_id: int, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    if len(match_manager.questions) == 0:
        await match_manager.initialize_questions(db, match_id)

    # Check if this is the Test Simulator Mode (match_id == 99999 or non-existent match)
    if match_id == 99999:
        participants_data = []
        for p in match_manager.custom_participants:
            t_id = p["team_id"]
            participants_data.append({
                **p,
                "score": match_manager.team_scores.get(t_id, p.get("score", 0)),
                "rung": match_manager.ladder.get(t_id, 0)
            })
        return {
            "id": 99999,
            "name": "SCHOLARNNAIRE LIVE ARENA - TEST SIMULATOR",
            "stage_name": "Grand Finals Stage",
            "tournament_name": "Scholarnnaire National Championship (Sandbox Test)",
            "status": "active",
            "is_test_mode": True,
            "participants": participants_data,
            "state": match_manager.get_public_state()
        }

    from sqlalchemy.orm import joinedload
    from app.models.school import TeamMember
    match = db.query(TournamentMatch).options(
        joinedload(TournamentMatch.stage),
        joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team).joinedload(Team.members)
    ).filter(TournamentMatch.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    participants_data = []
    for idx, p in enumerate(match.participants):
        members_data = []
        if p.team and p.team.members:
            for m in p.team.members:
                members_data.append({
                    "id": m.id,
                    "name": m.name,
                    "role": m.role,
                    "is_captain": m.is_captain
                })
        
        # Determine live score (override from match_manager if exists, else db score)
        current_score = match_manager.team_scores.get(p.team_id, p.score if p.score else 0)
        current_rung = match_manager.ladder.get(p.team_id, 0)
        
        participants_data.append({
            "participant_id": p.id,
            "team_id": p.team_id,
            "team_name": p.team.name if p.team else f"Team {p.team_id}",
            "score": current_score,
            "rung": current_rung,
            "status": "up" if current_rung > 0 else ("down" if current_rung < 0 else "neutral"),
            "group": f"Group {(idx % 4) + 1}",
            "members": members_data
        })

    public_state = match_manager.get_public_state()

    return {
        "id": match.id,
        "name": match.name or f"Match #{match.id}",
        "stage_name": match.stage.name if match.stage else "Group Stage 2",
        "tournament_name": match.stage.tournament.name if (match.stage and match.stage.tournament) else "Scholarnnaire Tournament",
        "status": match.status,
        "is_test_mode": False,
        "participants": participants_data,
        "state": public_state
    }

@router.post("/matches/{match_id}/buzzers/pause")
async def pause_buzzers(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.pause_buzzers()
    return {"status": "success", "buzzers_paused": True}

@router.post("/matches/{match_id}/buzzers/release")
async def release_buzzers(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.release_buzzers()
    return {"status": "success", "buzzers_paused": False}

@router.post("/matches/{match_id}/questions/reveal")
async def reveal_answer(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.show_answer()
    return {"status": "success", "answer_revealed": True}

@router.post("/matches/{match_id}/questions/next")
async def next_question(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.start_next_question()
    return {"status": "success", "current_index": match_manager.current_question_index}

@router.post("/matches/{match_id}/questions/reset")
async def reset_question(match_id: int):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.reset_current_question()
    return {"status": "success", "message": "Question reset"}

class ScoreAdjustBody(BaseModel):
    team_id: int
    delta: float
    reason: Optional[str] = "Moderator adjustment"

@router.post("/matches/{match_id}/scores/adjust")
async def adjust_score(match_id: int, req: ScoreAdjustBody, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.adjust_team_score(req.team_id, req.delta, req.reason)
    
    # If not test match, persist to MatchParticipant
    if match_id != 99999:
        participant = db.query(MatchParticipant).filter(
            MatchParticipant.match_id == match_id,
            MatchParticipant.team_id == req.team_id
        ).first()
        if participant:
            participant.score = (participant.score or 0) + req.delta
            db.commit()
            
    return {"status": "success", "new_score": match_manager.team_scores.get(req.team_id)}

class AnnouncementBody(BaseModel):
    message: str

@router.post("/matches/{match_id}/announcements")
async def post_announcement(match_id: int, req: AnnouncementBody):
    match_manager = arena_controller.get_match(match_id)
    match_manager.add_announcement(req.message)
    await match_manager.broadcast_state()
    return {"status": "success", "announcements": match_manager.announcements}

class LifelineTriggerBody(BaseModel):
    lifeline: str
    team_id: Optional[int] = 1

@router.post("/matches/{match_id}/lifelines/trigger")
async def trigger_lifeline_moderator(match_id: int, req: LifelineTriggerBody):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.trigger_lifeline(req.lifeline, req.team_id or 1)
    return {"status": "success", "active_lifeline": match_manager.active_lifeline}

@router.post("/matches/{match_id}/end-stage")
async def end_stage(match_id: int, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    match_manager.phase = "finished"
    match_manager.add_game_log("END_STAGE", "Stage officially concluded by Moderator")
    await match_manager.broadcast_state()
    
    if match_id != 99999:
        match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
        if match:
            match.status = "completed"
            db.commit()
    return {"status": "success", "message": "Stage concluded"}

@router.post("/matches/{match_id}/end-show")
async def end_show(match_id: int, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    match_manager.phase = "finished"
    match_manager.add_game_log("END_SHOW", "Live Show Ended and Broadcast Finalized")
    await match_manager.broadcast_state()
    
    if match_id != 99999:
        match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
        if match:
            match.status = "completed"
            db.commit()
    return {"status": "success", "message": "Live Show broadcast ended"}

class AddParticipantRequest(BaseModel):
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    score: Optional[float] = 0.0
    group: Optional[str] = "Group 1"

class RemoveParticipantRequest(BaseModel):
    team_id: Optional[int] = None
    participant_id: Optional[int] = None

@router.get("/matches/{match_id}/available-teams")
def get_available_teams(match_id: int, db: Session = Depends(deps.get_db)):
    existing_team_ids = set()
    if match_id != 99999:
        participants = db.query(MatchParticipant).filter(MatchParticipant.match_id == match_id).all()
        existing_team_ids = {p.team_id for p in participants}
    else:
        match_manager = arena_controller.get_match(match_id)
        existing_team_ids = {p["team_id"] for p in match_manager.custom_participants}

    teams = db.query(Team).all()
    available = []
    for t in teams:
        if t.id not in existing_team_ids:
            school_name = t.school.name if t.school else "Independent School"
            available.append({
                "id": t.id,
                "name": t.name,
                "school_name": school_name
            })
    return {"available_teams": available}

@router.post("/matches/{match_id}/participants/add")
async def add_participant_endpoint(match_id: int, req: AddParticipantRequest, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    
    if match_id == 99999:
        new_p = await match_manager.add_participant(
            team_id=req.team_id,
            team_name=req.team_name,
            score=req.score or 0.0,
            group=req.group or "Group 1"
        )
        return {"status": "success", "message": "Participant added successfully", "participant": new_p}

    # Real match
    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Tournament match not found")

    team = None
    if req.team_id:
        team = db.query(Team).filter(Team.id == req.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
    elif req.team_name:
        team = db.query(Team).filter(Team.name == req.team_name).first()
        if not team:
            first_school = db.query(School).first()
            if not first_school:
                raise HTTPException(status_code=400, detail="No school found to register team with")
            team = Team(name=req.team_name, school_id=first_school.id, is_active=True)
            db.add(team)
            db.commit()
            db.refresh(team)
    else:
        existing_tids = {p.team_id for p in match.participants}
        available_team = db.query(Team).filter(~Team.id.in_(existing_tids) if existing_tids else True).first()
        if available_team:
            team = available_team
        else:
            first_school = db.query(School).first()
            team = Team(name=f"Team {len(match.participants) + 1}", school_id=first_school.id if first_school else 1, is_active=True)
            db.add(team)
            db.commit()
            db.refresh(team)

    existing_participant = db.query(MatchParticipant).filter(
        MatchParticipant.match_id == match_id,
        MatchParticipant.team_id == team.id
    ).first()
    if existing_participant:
        raise HTTPException(status_code=400, detail="Team is already participating in this match")

    new_participant = MatchParticipant(
        match_id=match_id,
        team_id=team.id,
        score=req.score or 0.0,
        is_qualified=False
    )
    db.add(new_participant)
    db.commit()
    db.refresh(new_participant)

    match_manager.team_scores[team.id] = req.score or 0.0
    match_manager.ensure_team_registered(team.id)
    match_manager.add_game_log("PARTICIPANT_ADDED", f"Participant added: {team.name}")
    await match_manager.broadcast_state()

    return {
        "status": "success",
        "message": f"Participant {team.name} added to match",
        "participant": {
            "participant_id": new_participant.id,
            "team_id": team.id,
            "team_name": team.name,
            "score": new_participant.score,
            "group": req.group or "Group 1"
        }
    }

@router.post("/matches/{match_id}/participants/remove")
async def remove_participant_endpoint(match_id: int, req: Optional[RemoveParticipantRequest] = None, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    tid = req.team_id if req else None
    pid = req.participant_id if req else None

    if match_id == 99999:
        removed = await match_manager.remove_participant(team_id=tid, participant_id=pid)
        return {"status": "success", "message": "Participant removed", "removed": removed}

    query = db.query(MatchParticipant).filter(MatchParticipant.match_id == match_id)
    if pid is not None:
        query = query.filter(MatchParticipant.id == pid)
    elif tid is not None:
        query = query.filter(MatchParticipant.team_id == tid)
    else:
        query = query.order_by(MatchParticipant.id.desc())

    participant = query.first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    team_id = participant.team_id
    team_name = participant.team.name if participant.team else f"Team {team_id}"

    db.delete(participant)
    db.commit()

    match_manager.team_scores.pop(team_id, None)
    match_manager.registered_teams.discard(team_id)
    match_manager.add_game_log("PARTICIPANT_REMOVED", f"Participant removed: {team_name}")
    await match_manager.broadcast_state()

    return {"status": "success", "message": f"Participant {team_name} removed"}

@router.post("/matches/{match_id}/participants/quick-increase")
async def quick_increase_participant(match_id: int, db: Session = Depends(deps.get_db)):
    return await add_participant_endpoint(match_id, AddParticipantRequest(), db=db)

@router.post("/matches/{match_id}/participants/quick-decrease")
async def quick_decrease_participant(match_id: int, db: Session = Depends(deps.get_db)):
    return await remove_participant_endpoint(match_id, None, db=db)

class QuestionResultBody(BaseModel):
    team_id: int
    is_correct: bool
    points: Optional[float] = 400.0

@router.post("/matches/{match_id}/simulate-question-result")
async def simulate_question_result(match_id: int, req: QuestionResultBody, db: Session = Depends(deps.get_db)):
    match_manager = arena_controller.get_match(match_id)
    await match_manager.process_question_result(req.team_id, req.is_correct, req.points or 400.0)
    
    if match_id != 99999:
        p = db.query(MatchParticipant).filter(
            MatchParticipant.match_id == match_id,
            MatchParticipant.team_id == req.team_id
        ).first()
        if p:
            delta = req.points if req.is_correct else -req.points
            p.score = (p.score or 0) + delta
            db.commit()
            
    return {
        "status": "success",
        "team_id": req.team_id,
        "is_correct": req.is_correct,
        "new_score": match_manager.team_scores.get(req.team_id),
        "new_rung": match_manager.ladder.get(req.team_id)
    }




