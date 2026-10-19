from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session, joinedload
from app.api import deps
from app.core.security import decode_access_token, get_current_school
from app.models.school import School, Team, MatchParticipant, TournamentMatch, Tournament, TournamentStage, TeamMember
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

# Scholarnnaire Dual-Ladder Positive Titles & Palettes
POSITIVE_RUNG_LABELS = {
    11: "SCHOLARNAIRE",
    10: "PROFESSOR",
    9: "ASSOCIATE PROFESSOR",
    8: "Ph.D",
    7: "DON",
    6: "MASTERS",
    5: "TERTIARY",
    4: "SECONDARY",
    3: "PRIMARY",
    2: "KINDERGARTEN",
    1: "NURSERY",
    0: "GROUND LEVEL"
}

TEAM_PALETTES = [
    {
        "color": "from-emerald-500 to-teal-700",
        "border": "border-emerald-400",
        "bgLight": "bg-emerald-500/10",
        "textColor": "text-emerald-400"
    },
    {
        "color": "from-blue-600 to-indigo-800",
        "border": "border-blue-400",
        "bgLight": "bg-blue-500/10",
        "textColor": "text-blue-400"
    },
    {
        "color": "from-amber-500 to-orange-700",
        "border": "border-amber-400",
        "bgLight": "bg-amber-500/10",
        "textColor": "text-amber-400"
    },
    {
        "color": "from-purple-600 to-indigo-900",
        "border": "border-purple-400",
        "bgLight": "bg-purple-500/10",
        "textColor": "text-purple-400"
    },
    {
        "color": "from-rose-500 to-red-700",
        "border": "border-rose-400",
        "bgLight": "bg-rose-500/10",
        "textColor": "text-rose-400"
    },
    {
        "color": "from-cyan-500 to-blue-700",
        "border": "border-cyan-400",
        "bgLight": "bg-cyan-500/10",
        "textColor": "text-cyan-400"
    }
]

def format_rung_and_status(score: float):
    rung = int(score // 400)
    rung = max(-11, min(11, rung))
    if rung > 0:
        title = POSITIVE_RUNG_LABELS.get(rung, f"Rung +{rung}")
        label = f"+{int(score):,} pts"
        note = f"{title} (+{int(score):,} pts)"
        status = "up"
    elif rung < 0:
        title = f"{rung} STEP" if abs(rung) == 1 else f"{rung} STEPS"
        label = f"{int(score):,} pts"
        note = f"Penalty Step {rung} ({int(score):,} pts)"
        status = "down"
    else:
        title = "GROUND LEVEL"
        label = "0 pts"
        note = "Baseline Ground Level (0 pts)"
        status = "neutral"
    return rung, title, label, note, status

@router.get("/ladderboard/live")
async def get_live_ladderboard(
    tournament_id: Optional[int] = Query(None),
    match_id: Optional[int] = Query(None),
    db: Session = Depends(deps.get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Live Ladderboard API for School Admins, Contestants, and Scholarnnaire Admins.
    Supplies live dual-ladder standings (+/- rungs), current live show question,
    and highlights the viewer's own team.
    """
    current_school_id = None
    current_team_id = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_access_token(token)
        if payload:
            if payload.get("sub"):
                try:
                    current_school_id = int(payload["sub"])
                except Exception:
                    pass
            if payload.get("team_id"):
                try:
                    current_team_id = int(payload["team_id"])
                except Exception:
                    pass
            elif payload.get("participant_id"):
                m = db.query(TeamMember).filter(TeamMember.participant_id == str(payload["participant_id"])).first()
                if m:
                    current_team_id = m.team_id
                    if m.team and m.team.school_id:
                        current_school_id = m.team.school_id

    if current_school_id and not current_team_id:
        user_team = db.query(Team).filter(Team.school_id == current_school_id).first()
        if user_team:
            current_team_id = user_team.id

    # 1. Competitions List for Dropdown
    competitions_list = []
    tournaments = db.query(Tournament).filter(Tournament.is_active == True).all()
    for t in tournaments:
        competitions_list.append({
            "key": f"tournament_{t.id}",
            "type": "tournament",
            "id": t.id,
            "name": t.name,
            "category": "Tournament",
            "status": t.status or "active"
        })

    matches = db.query(TournamentMatch).options(
        joinedload(TournamentMatch.stage).joinedload(TournamentStage.tournament)
    ).all()
    for m in matches:
        t_name = m.stage.tournament.name if (m.stage and m.stage.tournament) else "National Tournament"
        competitions_list.append({
            "key": f"match_{m.id}",
            "type": "match",
            "id": m.id,
            "name": f"{m.name or f'Match #{m.id}'} • {t_name}",
            "category": "Live Match",
            "status": m.status
        })

    competitions_list.append({
        "key": "match_99999",
        "type": "sandbox",
        "id": 99999,
        "name": "Scholarnnaire Arena (Sandbox Simulator)",
        "category": "Simulation",
        "status": "active"
    })

    # 2. Determine target competition
    target_match_id = match_id
    target_tournament_id = tournament_id

    if target_match_id is None and target_tournament_id is None:
        if current_team_id:
            p = db.query(MatchParticipant).filter(MatchParticipant.team_id == current_team_id).first()
            if p:
                target_match_id = p.match_id
            else:
                user_t = db.query(Team).filter(Team.id == current_team_id).first()
                if user_t and user_t.tournament_id:
                    target_tournament_id = user_t.tournament_id

        if target_match_id is None and target_tournament_id is None:
            active_m = db.query(TournamentMatch).filter(TournamentMatch.status == "active").first()
            if active_m:
                target_match_id = active_m.id
            elif tournaments:
                act_t = next((t for t in tournaments if t.status == "active"), tournaments[0])
                target_tournament_id = act_t.id
            elif matches:
                target_match_id = matches[0].id
            else:
                target_match_id = 99999

    standings = []
    selected_comp = {}
    active_match_manager = None

    if target_match_id == 99999:
        selected_comp = {
            "type": "sandbox",
            "id": 99999,
            "key": "match_99999",
            "name": "Scholarnnaire Arena (Sandbox Simulator)",
            "stage_name": "Grand Finals Stage",
            "tournament_name": "Scholarnnaire National Championship (Sandbox Test)",
            "status": "active"
        }
        active_match_manager = arena_controller.get_match(99999)
        if len(active_match_manager.questions) == 0:
            active_match_manager._load_test_questions(db)

        for idx, p in enumerate(active_match_manager.custom_participants):
            t_id = p["team_id"]
            sc = active_match_manager.team_scores.get(t_id, p.get("score", 0.0))
            rung, title, label, note, status = format_rung_and_status(sc)
            palette = TEAM_PALETTES[idx % len(TEAM_PALETTES)]
            standings.append({
                "id": t_id,
                "team_id": t_id,
                "name": p["team_name"],
                "school_name": p.get("school_name", f"Academy #{t_id}"),
                "score": sc,
                "rung": rung,
                "rung_title": title,
                "rung_label": label,
                "status": status,
                "statusNote": note,
                "color": palette["color"],
                "border": palette["border"],
                "bgLight": palette["bgLight"],
                "textColor": palette["textColor"],
                "avatar": p["team_name"][0] if p["team_name"] else "T",
                "is_my_team": (current_team_id == t_id),
                "members": p.get("members", [])
            })
    elif target_match_id is not None:
        m = db.query(TournamentMatch).options(
            joinedload(TournamentMatch.stage).joinedload(TournamentStage.tournament),
            joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team).joinedload(Team.school),
            joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team).joinedload(Team.members)
        ).filter(TournamentMatch.id == target_match_id).first()

        if m:
            t_name = m.stage.tournament.name if (m.stage and m.stage.tournament) else "Scholarnnaire Tournament"
            selected_comp = {
                "type": "match",
                "id": m.id,
                "key": f"match_{m.id}",
                "name": m.name or f"Match #{m.id}",
                "stage_name": m.stage.name if m.stage else "Group Stage",
                "tournament_name": t_name,
                "status": m.status
            }
            active_match_manager = arena_controller.get_match(m.id)
            if len(active_match_manager.questions) == 0:
                await active_match_manager.initialize_questions(db, m.id)

            for idx, p in enumerate(m.participants):
                team = p.team
                if not team:
                    continue
                sc = active_match_manager.team_scores.get(team.id, p.score if p.score is not None else 0.0)
                active_match_manager.team_scores[team.id] = sc
                rung, title, label, note, status = format_rung_and_status(sc)
                active_match_manager.ladder[team.id] = rung

                palette = TEAM_PALETTES[idx % len(TEAM_PALETTES)]
                members_list = []
                if team.members:
                    members_list = [{"id": mem.id, "name": mem.name, "role": mem.role, "is_captain": mem.is_captain} for mem in team.members]

                standings.append({
                    "id": team.id,
                    "team_id": team.id,
                    "name": team.name,
                    "school_name": team.school.name if team.school else team.name,
                    "score": sc,
                    "rung": rung,
                    "rung_title": title,
                    "rung_label": label,
                    "status": status,
                    "statusNote": note,
                    "color": palette["color"],
                    "border": palette["border"],
                    "bgLight": palette["bgLight"],
                    "textColor": palette["textColor"],
                    "avatar": team.name[0] if team.name else "T",
                    "is_my_team": (current_team_id == team.id or (current_school_id and team.school_id == current_school_id)),
                    "members": members_list
                })
    else:
        t = db.query(Tournament).filter(Tournament.id == target_tournament_id).first()
        if t:
            selected_comp = {
                "type": "tournament",
                "id": t.id,
                "key": f"tournament_{t.id}",
                "name": t.name,
                "stage_name": "All Stages",
                "tournament_name": t.name,
                "status": t.status or "active"
            }
            teams_in_t = db.query(Team).options(
                joinedload(Team.school),
                joinedload(Team.members)
            ).filter(Team.tournament_id == t.id).all()

            if len(teams_in_t) < 4:
                all_teams = db.query(Team).options(
                    joinedload(Team.school),
                    joinedload(Team.members)
                ).all()
                existing_ids = {tm.id for tm in teams_in_t}
                for tm in all_teams:
                    if tm.id not in existing_ids:
                        teams_in_t.append(tm)

            active_m = db.query(TournamentMatch).join(TournamentStage).filter(
                TournamentStage.tournament_id == t.id,
                TournamentMatch.status == "active"
            ).first()
            if active_m:
                active_match_manager = arena_controller.get_match(active_m.id)
                if len(active_match_manager.questions) == 0:
                    await active_match_manager.initialize_questions(db, active_m.id)
            else:
                t_matches = db.query(TournamentMatch).join(TournamentStage).filter(
                    TournamentStage.tournament_id == t.id
                ).all()
                for tm in t_matches:
                    if tm.id in arena_controller.matches:
                        active_match_manager = arena_controller.matches[tm.id]
                        break
                if not active_match_manager and t_matches:
                    active_match_manager = arena_controller.get_match(t_matches[0].id)
                    if len(active_match_manager.questions) == 0:
                        await active_match_manager.initialize_questions(db, t_matches[0].id)
                elif not active_match_manager:
                    if 99999 in arena_controller.matches:
                        active_match_manager = arena_controller.matches[99999]

            for idx, team in enumerate(teams_in_t):
                sc = 0.0
                if active_match_manager and team.id in active_match_manager.team_scores:
                    sc = active_match_manager.team_scores[team.id]
                else:
                    parts = db.query(MatchParticipant).filter(MatchParticipant.team_id == team.id).all()
                    if parts:
                        sc = sum(p.score for p in parts if p.score)
                    elif team.members:
                        sc = float(sum(m.score for m in team.members if m.score))

                rung, title, label, note, status = format_rung_and_status(sc)
                palette = TEAM_PALETTES[idx % len(TEAM_PALETTES)]
                members_list = [{"id": mem.id, "name": mem.name, "role": mem.role, "is_captain": mem.is_captain} for mem in (team.members or [])]

                standings.append({
                    "id": team.id,
                    "team_id": team.id,
                    "name": team.name,
                    "school_name": team.school.name if team.school else team.name,
                    "score": sc,
                    "rung": rung,
                    "rung_title": title,
                    "rung_label": label,
                    "status": status,
                    "statusNote": note,
                    "color": palette["color"],
                    "border": palette["border"],
                    "bgLight": palette["bgLight"],
                    "textColor": palette["textColor"],
                    "avatar": team.name[0] if team.name else "T",
                    "is_my_team": (current_team_id == team.id or (current_school_id and team.school_id == current_school_id)),
                    "members": members_list
                })

    # Sort descending by score
    standings.sort(key=lambda x: x["score"], reverse=True)
    for idx, item in enumerate(standings):
        item["currentRank"] = idx + 1
        item["prevRank"] = idx + 1
        item["rank"] = idx + 1

    my_team = next((s for s in standings if s["is_my_team"]), None)

    # 3. Live Show Active Question
    live_show = None
    if active_match_manager and active_match_manager.questions:
        pub = active_match_manager.get_public_state()
        curr_q = pub.get("current_question")
        if curr_q:
            l_team_str = pub.get("locked_team")
            if not l_team_str and active_match_manager.locked_answers:
                first_locked_id = list(active_match_manager.locked_answers.keys())[0]
                t_match = next((s for s in standings if s["team_id"] == first_locked_id), None)
                l_team_str = t_match["name"] if t_match else f"Team {first_locked_id}"

            live_show = {
                "is_live_now": True,
                "match_id": active_match_manager.match_id,
                "phase": pub.get("phase", "question_active"),
                "game_status": pub.get("game_status", "LIVE SHOW"),
                "current_question_index": pub.get("current_question_index", 1),
                "total_questions": pub.get("total_questions", len(active_match_manager.questions)),
                "current_question": curr_q,
                "locked_team": l_team_str,
                "locked_answers": pub.get("locked_answers", []),
                "time_left": pub.get("time_left", 30),
                "show_timer_formatted": pub.get("show_timer_formatted", "00:28:45"),
                "answer_revealed": pub.get("answer_revealed", False),
                "correct_option": pub.get("correct_option") if pub.get("answer_revealed") else None,
                "buzzers_paused": pub.get("buzzers_paused", False)
            }

    return {
        "status": "success",
        "selected_competition": selected_comp,
        "competitions_list": competitions_list,
        "my_team": my_team,
        "standings": standings,
        "live_show": live_show
    }
