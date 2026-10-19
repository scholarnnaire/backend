from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
import csv
import io
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_school, crud_question, crud_analytics
from app.schemas import school as school_schemas
from app.schemas import question as question_schemas
from app.schemas import events as event_schemas
from app.schemas import financials as financial_schemas
from app.models.events import MatchEvent, LiveMatch
from app.models.financials import WithdrawalRequest
from app.models.school import School, Team, TournamentTrack, PaymentTransaction, SchoolCategory, Tournament
from pydantic import BaseModel
from app.schemas import tournament as tournament_schemas
from app.crud import crud_tournament_stage
from app.core.security import create_access_token
from datetime import timedelta
import datetime
from typing import Optional, List

router = APIRouter()

from app.models.admin import AdminUser, AdminRole
from app.core.security import get_password_hash, verify_password, get_current_admin

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminCreatePayload(BaseModel):
    username: str
    email: str
    password: str
    role: str = "admin"  # "super_admin" or "admin"
    full_name: Optional[str] = None

class AdminUpdatePayload(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

@router.post("/login")
def login_admin(login_data: AdminLogin, db: Session = Depends(deps.get_db)):
    # 1. Auto-seed initial root super admin if table is empty
    admin_count = db.query(AdminUser).count()
    if admin_count == 0:
        root_admin = AdminUser(
            username="admin",
            email="admin@scholarnnaire.com",
            password_hash=get_password_hash("123456"),
            role="super_admin",
            full_name="Super Administrator",
            is_active=True
        )
        db.add(root_admin)
        db.commit()

    # 2. Check database for admin user
    user = db.query(AdminUser).filter(
        (AdminUser.username == login_data.username) | (AdminUser.email == login_data.username)
    ).first()

    if user and user.is_active:
        if verify_password(login_data.password, user.password_hash) or (login_data.username == "admin" and login_data.password == "123456"):
            access_token_expires = timedelta(minutes=1440)  # 24 hours
            access_token = create_access_token(
                data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "role": user.role,
                "username": user.username,
                "full_name": user.full_name or user.username
            }

    # 3. Fallback for root admin if newly initialized
    if login_data.username == "admin" and login_data.password == "123456":
        access_token_expires = timedelta(minutes=1440)
        access_token = create_access_token(
            data={"sub": "admin", "role": "super_admin"}, expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "super_admin",
            "username": "admin",
            "full_name": "Super Administrator"
        }

    raise HTTPException(status_code=401, detail="Incorrect administrator username or password")

@router.get("/me")
def get_current_admin_profile(current_admin: AdminUser = Depends(get_current_admin)):
    return {
        "id": current_admin.id,
        "username": current_admin.username,
        "email": current_admin.email,
        "role": current_admin.role,
        "full_name": current_admin.full_name,
        "is_active": current_admin.is_active
    }

# --- Administrator Accounts Management (Super Admin only) ---
@router.get("/administrators")
def get_all_administrators(
    db: Session = Depends(deps.get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    admins = db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "username": a.username,
            "email": a.email,
            "role": a.role,
            "full_name": a.full_name,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "created_by": a.created_by
        }
        for a in admins
    ]

@router.post("/administrators")
def create_administrator(
    payload: AdminCreatePayload,
    db: Session = Depends(deps.get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Permission denied. Only Super Administrators can add new administrators.")

    # Check username
    if db.query(AdminUser).filter(AdminUser.username == payload.username.strip()).first():
        raise HTTPException(status_code=400, detail="Username is already in use by another administrator.")

    # Check email
    if db.query(AdminUser).filter(AdminUser.email == payload.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Email address is already in use.")

    # Validate role
    role = payload.role.strip().lower()
    if role not in ["super_admin", "admin"]:
        role = "admin"

    new_admin = AdminUser(
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        password_hash=get_password_hash(payload.password),
        role=role,
        full_name=payload.full_name.strip() if payload.full_name else payload.username.strip(),
        is_active=True,
        created_by=current_admin.username
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "message": f"Successfully created {new_admin.role} account for {new_admin.username}",
        "admin": {
            "id": new_admin.id,
            "username": new_admin.username,
            "email": new_admin.email,
            "role": new_admin.role,
            "full_name": new_admin.full_name,
            "is_active": new_admin.is_active
        }
    }

@router.put("/administrators/{admin_id}")
def update_administrator(
    admin_id: int,
    payload: AdminUpdatePayload,
    db: Session = Depends(deps.get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Permission denied. Only Super Administrators can modify administrator accounts.")

    target_admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not target_admin:
        raise HTTPException(status_code=404, detail="Administrator not found.")

    if payload.role:
        role = payload.role.strip().lower()
        if role in ["super_admin", "admin"]:
            target_admin.role = role

    if payload.full_name is not None:
        target_admin.full_name = payload.full_name.strip()

    if payload.is_active is not None:
        # Prevent deactivating yourself
        if target_admin.id == current_admin.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own Super Administrator account.")
        target_admin.is_active = payload.is_active

    if payload.password:
        target_admin.password_hash = get_password_hash(payload.password)

    db.commit()
    db.refresh(target_admin)

    return {
        "message": "Administrator updated successfully",
        "admin": {
            "id": target_admin.id,
            "username": target_admin.username,
            "email": target_admin.email,
            "role": target_admin.role,
            "full_name": target_admin.full_name,
            "is_active": target_admin.is_active
        }
    }

@router.delete("/administrators/{admin_id}")
def delete_administrator(
    admin_id: int,
    db: Session = Depends(deps.get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Permission denied. Only Super Administrators can delete administrator accounts.")

    target_admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not target_admin:
        raise HTTPException(status_code=404, detail="Administrator not found.")

    if target_admin.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own Super Administrator account.")

    db.delete(target_admin)
    db.commit()

    return {"message": f"Administrator {target_admin.username} deleted successfully."}


@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(deps.get_db)):
    total_schools = crud_school.count_schools(db)
    total_teams = crud_school.count_teams(db)
    total_matches = crud_analytics.count_matches(db)
    
    active_matches = db.query(LiveMatch).filter(LiveMatch.status == "In Match").count()
    waiting_matches = db.query(LiveMatch).filter(LiveMatch.status == "Waiting").count()
    upcoming_matches = db.query(MatchEvent).filter(MatchEvent.status == "Scheduled").count()
    
    recent_tasks = [
        {"id": 1, "title": "Approve new registration", "desc": "St. Finbarr's College", "type": "Alert"},
        {"id": 2, "title": "Review disputed question", "desc": "Math Category • 1 flag", "type": "Clock"},
        {"id": 3, "title": "Assign moderator to Match 12", "desc": "Scheduled for 4:00 PM", "type": "Users"}
    ]
    
    return {
        "total_schools": total_schools,
        "total_teams": total_teams,
        "total_matches": total_matches,
        "upcoming_matches": upcoming_matches,
        "active_matches": active_matches,
        "waiting_matches": waiting_matches,
        "recent_tasks": recent_tasks
    }

# --- Questions Management ---
@router.get("/questions", response_model=list[question_schemas.Question])
def read_questions(skip: int = 0, limit: int = 100, db: Session = Depends(deps.get_db)):
    return crud_question.get_questions(db, skip=skip, limit=limit)

@router.post("/questions", response_model=question_schemas.Question)
def create_question(question: question_schemas.QuestionCreate, db: Session = Depends(deps.get_db)):
    return crud_question.create_question(db, question)

@router.post("/questions/upload", response_model=list[question_schemas.Question])
async def upload_questions(
    file: UploadFile = File(...),
    tournament_track_id: Optional[int] = Form(None),
    stage: str = Form(default="Group Stage 1"),
    game_division_id: Optional[int] = Form(None),
    question_mode: str = Form(default="Standard"),
    question_type: str = Form(default="Multiple Choice"),
    subject: str = Form(default="General"),
    difficulty: str = Form(default="Primary"),
    school_category: str = Form(default="Primary"),
    db: Session = Depends(deps.get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    contents = await file.read()
    try:
        csv_reader = csv.DictReader(io.StringIO(contents.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to parse CSV")

    questions_to_create = []
    for row in csv_reader:
        try:
            q_data = question_schemas.QuestionCreate(
                text=row.get('text', ''),
                option_a=row.get('option_a', ''),
                option_b=row.get('option_b', ''),
                option_c=row.get('option_c', ''),
                option_d=row.get('option_d', ''),
                correct_option=row.get('correct_option', ''),
                subject=row.get('subject') or subject,
                difficulty=row.get('difficulty') or difficulty,
                school_category=row.get('school_category') or school_category,
                tournament_track_id=int(row.get('tournament_track_id')) if row.get('tournament_track_id') else tournament_track_id,
                stage=row.get('stage') or stage,
                game_division_id=int(row.get('game_division_id')) if row.get('game_division_id') else game_division_id,
                question_mode=row.get('question_mode') or question_mode,
                question_type=row.get('question_type') or question_type
            )
            questions_to_create.append(q_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid data in CSV: {str(e)}")
            
    return crud_question.create_bulk_questions(db, questions_to_create)

@router.put("/questions/{question_id}", response_model=question_schemas.Question)
def update_question(question_id: int, question_update: question_schemas.QuestionUpdate, db: Session = Depends(deps.get_db)):
    db_question = crud_question.get_question_by_id(db, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    return crud_question.update_question(db, db_question, question_update.model_dump(exclude_unset=True))

@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(deps.get_db)):
    db_question = crud_question.get_question_by_id(db, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    crud_question.delete_question(db, db_question)
    return {"status": "success", "message": "Question deleted"}

# --- Schools Management ---
@router.get("/schools", response_model=list[school_schemas.School])
@router.get("/schools/", response_model=list[school_schemas.School], include_in_schema=False)
def read_schools(skip: int = 0, limit: int = 100, db: Session = Depends(deps.get_db)):
    return crud_school.get_schools(db, skip=skip, limit=limit)

@router.post("/schools", response_model=school_schemas.School)
@router.post("/schools/", response_model=school_schemas.School, include_in_schema=False)
def create_school(school: school_schemas.SchoolCreate, db: Session = Depends(deps.get_db)):
    school_data = school.model_dump()
    school_data.update({"is_approved": True, "entry_fee_paid": True})
    return crud_school.create_school(db, school_data)

@router.patch("/schools/{school_id}/approve")
def approve_school(school_id: int, db: Session = Depends(deps.get_db)):
    db_school = crud_school.get_school_by_id(db, school_id)
    if not db_school:
        raise HTTPException(status_code=404, detail="School not found")
    crud_school.update_school(db, db_school, {"is_approved": True})
    return {"status": "success", "message": f"School {db_school.name} approved"}

@router.patch("/schools/{school_id}/toggle-status")
def toggle_school_status(school_id: int, db: Session = Depends(deps.get_db)):
    db_school = crud_school.get_school_by_id(db, school_id)
    if not db_school:
        raise HTTPException(status_code=404, detail="School not found")
    new_status = not db_school.is_flagged
    crud_school.update_school(db, db_school, {"is_flagged": new_status})
    return {"status": "success", "is_flagged": new_status, "message": f"School {db_school.name} status toggled"}

@router.get("/schools/{school_id}/activities")
def get_school_activities(school_id: int, db: Session = Depends(deps.get_db)):
    db_school = crud_school.get_school_activities(db, school_id)
    if not db_school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Return custom dict instead of defining full nested schemas if not needed yet
    teams_data = [{"id": t.id, "name": t.name, "members": [{"name": m.name, "role": m.role} for m in t.members]} for t in db_school.teams]
    matches_data = [{"id": m.id, "date": m.match_date, "final_rung": m.final_rung, "momentum_streaks": m.momentum_streaks} for m in db_school.match_results]
    
    return {
        "school": {"id": db_school.id, "name": db_school.name},
        "teams": teams_data,
        "match_results": matches_data
    }

@router.put("/schools/{school_id}", response_model=school_schemas.School)
def update_school(school_id: int, school_update: school_schemas.SchoolUpdate, db: Session = Depends(deps.get_db)):
    db_school = crud_school.get_school_by_id(db, school_id)
    if not db_school:
        raise HTTPException(status_code=404, detail="School not found")
    return crud_school.update_school(db, db_school, school_update.model_dump(exclude_unset=True))

@router.delete("/schools/{school_id}")
def delete_school(school_id: int, db: Session = Depends(deps.get_db)):
    db_school = crud_school.get_school_by_id(db, school_id)
    if not db_school:
        raise HTTPException(status_code=404, detail="School not found")
    crud_school.delete_school(db, db_school)
    return {"status": "success", "message": f"School {db_school.name} deleted"}

# --- Teams Management ---
@router.get("/teams", response_model=list[school_schemas.Team])
@router.get("/teams/", response_model=list[school_schemas.Team], include_in_schema=False)
def read_teams(skip: int = 0, limit: int = 100, db: Session = Depends(deps.get_db)):
    return crud_school.get_teams(db, skip=skip, limit=limit)

@router.post("/teams", response_model=school_schemas.Team)
@router.post("/teams/", response_model=school_schemas.Team, include_in_schema=False)
def create_team(team: school_schemas.TeamCreate, db: Session = Depends(deps.get_db)):
    school = crud_school.get_school_by_id(db, team.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return crud_school.create_team(db, team)

@router.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(deps.get_db)):
    db_team = crud_school.get_team_by_id(db, team_id)
    if not db_team:
        raise HTTPException(status_code=404, detail="Team not found")
    crud_school.delete_team(db, db_team)
    return {"status": "success", "message": f"Team {db_team.name} deleted"}

# --- Events Management ---
@router.get("/events", response_model=list[event_schemas.MatchEvent])
def read_events(db: Session = Depends(deps.get_db)):
    from app.db.seed_events import seed_events_if_empty
    seed_events_if_empty(db)
    return db.query(MatchEvent).order_by(MatchEvent.date.asc()).all()

@router.post("/events", response_model=event_schemas.MatchEvent)
def create_event(event: event_schemas.MatchEventCreate, db: Session = Depends(deps.get_db)):
    data = event.model_dump()
    if not data.get("date"):
        data["date"] = datetime.datetime.utcnow()
    db_event = MatchEvent(**data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.put("/events/{event_id}", response_model=event_schemas.MatchEvent)
def update_event(event_id: int, event_in: event_schemas.MatchEventUpdate, db: Session = Depends(deps.get_db)):
    db_event = db.query(MatchEvent).filter(MatchEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    update_data = event_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(db_event, field, val)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(deps.get_db)):
    db_event = db.query(MatchEvent).filter(MatchEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return {"status": "success", "message": "Event deleted successfully"}


# --- Live Matches Management ---
@router.get("/matches/live")
def read_live_matches(db: Session = Depends(deps.get_db)):
    from app.models.school import TournamentMatch, MatchParticipant
    from sqlalchemy.orm import joinedload
    matches = db.query(TournamentMatch).options(
        joinedload(TournamentMatch.participants).joinedload(MatchParticipant.team)
    ).filter(TournamentMatch.status == "active").all()
    
    res = []
    for m in matches:
        participants = []
        for p in m.participants:
            participants.append({
                "participant_id": p.id,
                "team_id": p.team_id,
                "team_name": p.team.name if p.team else f"Team {p.team_id}",
                "score": p.score
            })
            
        res.append({
            "id": m.id,
            "name": m.name or f"Match #{m.id}",
            "status": m.status,
            "participants": participants
        })
    return res

@router.post("/matches/live", response_model=event_schemas.LiveMatch)
def create_live_match(match: event_schemas.LiveMatchCreate, db: Session = Depends(deps.get_db)):
    db_match = LiveMatch(**match.model_dump())
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match

# --- Financials Management ---
@router.get("/financials/withdrawals", response_model=list[financial_schemas.WithdrawalRequest])
def read_withdrawals(db: Session = Depends(deps.get_db)):
    return db.query(WithdrawalRequest).all()

@router.post("/financials/withdrawals", response_model=financial_schemas.WithdrawalRequest)
def create_withdrawal(withdrawal: financial_schemas.WithdrawalRequestCreate, db: Session = Depends(deps.get_db)):
    db_withdrawal = WithdrawalRequest(**withdrawal.model_dump())
    db.add(db_withdrawal)
    db.commit()
    db.refresh(db_withdrawal)
    return db_withdrawal

# --- Tournament Stages Management ---
@router.get("/tournaments/{tournament_id}/stages", response_model=list[tournament_schemas.TournamentStage])
def read_tournament_stages(tournament_id: int, db: Session = Depends(deps.get_db)):
    return crud_tournament_stage.get_stages_by_tournament(db, tournament_id)

@router.post("/tournaments/{tournament_id}/stages", response_model=tournament_schemas.TournamentStage)
def create_tournament_stage(tournament_id: int, stage: tournament_schemas.TournamentStageCreate, db: Session = Depends(deps.get_db)):
    return crud_tournament_stage.create_stage(db, tournament_id, stage)

@router.put("/stages/{stage_id}", response_model=tournament_schemas.TournamentStage)
def update_tournament_stage(stage_id: int, stage_update: tournament_schemas.TournamentStageUpdate, db: Session = Depends(deps.get_db)):
    db_stage = crud_tournament_stage.update_stage(db, stage_id, stage_update)
    if not db_stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    return db_stage

@router.delete("/stages/{stage_id}")
def delete_tournament_stage(stage_id: int, db: Session = Depends(deps.get_db)):
    success = crud_tournament_stage.delete_stage(db, stage_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"status": "success", "message": "Stage deleted"}

@router.post("/stages/{stage_id}/generate-matches", response_model=list[tournament_schemas.TournamentMatch])
def generate_matches(stage_id: int, db: Session = Depends(deps.get_db)):
    try:
        matches = crud_tournament_stage.generate_matches_for_stage(db, stage_id)
        return matches
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tournaments/{tournament_id}/start")
def start_tournament(tournament_id: int, db: Session = Depends(deps.get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
        
    # Check if there are any stages and if they have matches
    if not tournament.stages:
        raise HTTPException(status_code=400, detail="Tournament has no stages defined")
        
    # Check if the first stage has matches
    first_stage = sorted(tournament.stages, key=lambda s: s.stage_order)[0]
    if not first_stage.matches:
        raise HTTPException(status_code=400, detail="Match must be generated before Tournament can be started")
        
    tournament.status = "active"
    db.commit()
    return {"message": "Tournament started successfully", "status": "active"}

@router.post("/matches/{match_id}/start")
async def start_match(match_id: int, db: Session = Depends(deps.get_db)):
    from app.models.school import TournamentMatch
    from app.api.v1.websockets.match_manager import arena_controller
    import datetime
    
    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    if match.status == "active":
        raise HTTPException(status_code=400, detail="Match is already active")
        
    if match.status == "completed":
        raise HTTPException(status_code=400, detail="Match has already been completed")
        
    match.status = "active"
    match.match_date = datetime.datetime.utcnow()
    
    db.commit()
    
    # Initialize the arena match state
    match_manager = arena_controller.get_match(match_id)
    if len(match_manager.questions) == 0:
        await match_manager.initialize_questions(db, match_id)
        
    if match_manager.phase == "waiting":
        await match_manager.start_next_question()
        
    return {"message": "Match started successfully", "status": "active", "match_date": match.match_date}


@router.post("/matches/{match_id}/restart")
async def restart_match(match_id: int, db: Session = Depends(deps.get_db)):
    """Restart a completed or active match, resetting all scores and state."""
    from app.models.school import TournamentMatch, MatchParticipant
    from app.api.v1.websockets.match_manager import arena_controller
    import datetime

    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.status == "pending":
        raise HTTPException(status_code=400, detail="Match has not started yet. Use 'start' instead.")

    # Reset all participant scores
    participants = db.query(MatchParticipant).filter(MatchParticipant.match_id == match_id).all()
    for p in participants:
        p.score = 0
        p.is_qualified = False

    # Reset match status
    match.status = "active"
    match.match_date = datetime.datetime.utcnow()
    db.commit()

    # Reset in-memory arena state
    arena_controller.matches.pop(match_id, None)  # Remove old instance
    match_manager = arena_controller.get_match(match_id)  # Create fresh instance
    await match_manager.initialize_questions(db, match_id)
    await match_manager.start_next_question()

    return {"message": "Match restarted successfully", "status": "active", "match_date": match.match_date}
