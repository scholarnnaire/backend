from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid
from passlib.context import CryptContext
from app.core.security import create_access_token, get_current_school

from app.api import deps
from app.models.school import SchoolCategory, School, Team, TournamentTrack, Tournament, PaymentTransaction
from app.schemas import school as school_schemas
from app.crud import crud_school
from app.services.email import EmailService
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
email_service = EmailService()
import bcrypt

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8')[:72], hashed_password.encode('utf-8'))
    except Exception:
        return False

class LoginPayload(BaseModel):
    identifier: str
    password: str

class ForgotPasswordRequest(BaseModel):
    identifier: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.get("/categories")
def get_categories():
    return [category.value for category in SchoolCategory]

@router.post("/register", response_model=school_schemas.SchoolAuthResponse)
def register_school(payload: school_schemas.SchoolCreate, background_tasks: BackgroundTasks, db: Session = Depends(deps.get_db)):
    # Check if school name + category already exists
    existing_school = crud_school.get_school_by_name_and_category(db, name=payload.name, category=payload.category)
    
    # Check if admin_username is taken
    existing_username = db.query(School).filter(School.admin_username == payload.admin_username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Admin Username is already taken.")
        
    # Check if school name is taken
    existing_name = db.query(School).filter(School.name == payload.name).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="School Name is already registered.")
    
    is_flagged = False
    
    # Generate unique 6-digit alphanumeric access code
    access_code = str(uuid.uuid4()).upper()[:6]
    
    school_data = payload.model_dump()
    password = school_data.pop("password")
    school_data.update({
        "password_hash": get_password_hash(password),
        "access_code": access_code,
        "is_approved": True,
        "entry_fee_paid": False, 
        "is_flagged": is_flagged
    })
    
    db_school = crud_school.create_school(db, school_data)
    
    background_tasks.add_task(email_service.send_verification_email, payload.contact_email, access_code, payload.name)
    
    return {
        "school": db_school,
        "access_token": "",
        "token_type": "bearer"
    }

class VerifyPayload(BaseModel):
    token: str

@router.post("/verify-email", response_model=school_schemas.SchoolAuthResponse)
def verify_email(payload: VerifyPayload, background_tasks: BackgroundTasks, db: Session = Depends(deps.get_db)):
    school = db.query(School).filter(School.access_code == payload.token).first()
    if not school:
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    school.access_code = None
    db.commit()
    
    # Send post-verification onboarding email with administration instructions and credentials
    if school.contact_email:
        background_tasks.add_task(
            email_service.send_school_onboarding_email,
            school.contact_email,
            school.name,
            school.admin_username or ""
        )
    
    access_token = create_access_token(data={"sub": str(school.id)})
    return {
        "school": school,
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login")
def login(payload: LoginPayload, db: Session = Depends(deps.get_db)):
    school = db.query(School).filter(
        or_(School.admin_username == payload.identifier, School.contact_email == payload.identifier)
    ).first()
    
    if not school or not school.password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not verify_password(payload.password, school.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if school.access_code is not None:
        raise HTTPException(status_code=403, detail="Email not verified. Please check your email for the verification code.")
        
    access_token = create_access_token(data={"sub": str(school.id)})
    return {"access_token": access_token, "token_type": "bearer"}

from datetime import datetime, timedelta

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(deps.get_db)):
    school = db.query(School).filter(
        or_(School.admin_username == payload.identifier, School.contact_email == payload.identifier)
    ).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="Account not found")

    import uuid
    token = uuid.uuid4().hex[:6].upper()
    
    school.reset_password_token = token
    school.reset_password_expires = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    # Send email
    subject = "Password Reset Token - Who Wants To be A Scholarnnaire"
    body = f"""
    <html>
      <body>
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2E7D32;">Password Reset Request</h2>
            <p>Hello <strong>{school.name}</strong>,</p>
            <p>You have requested to reset your password for the Team Portal.</p>
            <p>Your password reset token is:</p>
            <div style="background-color: #f3f4f6; padding: 20px; text-align: center; border-radius: 10px; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px; font-family: monospace; color: #1f2937;">{token}</span>
            </div>
            <p>This token will expire in 15 minutes.</p>
            <p>If you did not request this, please ignore this email.</p>
            <br>
            <p>Best regards,<br>Who Wants To be A Scholarnnaire Team</p>
        </div>
      </body>
    </html>
    """
    email_service.send_email(to_email=school.contact_email, subject=subject, body=body)
    
    return {"message": "Password reset token sent to your email"}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(deps.get_db)):
    school = db.query(School).filter(School.reset_password_token == payload.token).first()
    
    if not school:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if not school.reset_password_expires or datetime.utcnow() > school.reset_password_expires:
        raise HTTPException(status_code=400, detail="Token has expired")

    school.password_hash = get_password_hash(payload.new_password)
    school.reset_password_token = None
    school.reset_password_expires = None
    db.commit()
    
    return {"message": "Password reset successfully"}

@router.get("/dashboard")
def get_dashboard_data(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
        
    from sqlalchemy import or_, and_
    from app.models.events import LiveMatch, MatchEvent
    from app.models.school import Team

    # Calculate Tournament Position dynamically
    pos = {
        "stage": "Not Enrolled",
        "next_match_countdown": "No matches scheduled",
        "opponent": "TBD",
        "record": "0W - 0L - 0D",
        "points": 0
    }

    if school.teams:
        team = school.teams[0]
        if team.tournament:
            pos["stage"] = team.tournament.name
        elif team.track:
            pos["stage"] = team.track.name
            
        completed_matches = db.query(LiveMatch).filter(
            or_(LiveMatch.team1_id == team.id, LiveMatch.team2_id == team.id),
            LiveMatch.status == "Completed"
        ).all()
        
        wins, losses, draws = 0, 0, 0
        for match in completed_matches:
            is_team1 = (match.team1_id == team.id)
            if match.team1_score == match.team2_score:
                draws += 1
            elif (match.team1_score > match.team2_score and is_team1) or (match.team2_score > match.team1_score and not is_team1):
                wins += 1
            else:
                losses += 1
                
        pos["record"] = f"{wins}W - {losses}L - {draws}D"
        pos["points"] = (wins * 3) + (draws * 1)
        
        now = datetime.utcnow()
        next_match = db.query(LiveMatch).join(MatchEvent).filter(
            or_(LiveMatch.team1_id == team.id, LiveMatch.team2_id == team.id),
            LiveMatch.status.in_(["Waiting", "Scheduled"]),
            MatchEvent.date > now
        ).order_by(MatchEvent.date.asc()).first()
        
        if next_match:
            time_diff = next_match.event.date - now
            days = time_diff.days
            hours, remainder = divmod(time_diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            pos["next_match_countdown"] = f"{days} Days {hours:02d}:{minutes:02d}"
            
            opponent_team_id = next_match.team2_id if next_match.team1_id == team.id else next_match.team1_id
            if opponent_team_id:
                opponent_team = db.query(Team).filter(Team.id == opponent_team_id).first()
                if opponent_team and opponent_team.school:
                    pos["opponent"] = opponent_team.school.name
                else:
                    pos["opponent"] = "Unknown Team"
            else:
                pos["opponent"] = "TBD"

    # Build list of all enrolled tournaments for this school
    enrolled_positions = []
    for team in school.teams:
        t = team.tournament
        if not t:
            continue
        t_pos = {
            "stage": t.name,
            "tournament_id": t.id,
            "status": t.status,
            "next_match_countdown": "No matches scheduled",
            "opponent": "TBD",
            "record": "0W - 0L - 0D",
            "points": 0
        }
        completed_m = db.query(LiveMatch).filter(
            or_(LiveMatch.team1_id == team.id, LiveMatch.team2_id == team.id),
            LiveMatch.status == "Completed"
        ).all()
        w, l, d = 0, 0, 0
        for m in completed_m:
            is_t1 = (m.team1_id == team.id)
            if m.team1_score == m.team2_score:
                d += 1
            elif (m.team1_score > m.team2_score and is_t1) or (m.team2_score > m.team1_score and not is_t1):
                w += 1
            else:
                l += 1
        t_pos["record"] = f"{w}W - {l}L - {d}D"
        t_pos["points"] = (w * 3) + (d * 1)
        enrolled_positions.append(t_pos)

    return {
        "school": school,
        "teams": school.teams,
        "performance_stats": {
            "subject_accuracy": {
                "Maths": 85,
                "Science": 92,
                "English": 78,
                "History": 60,
                "General Knowledge": 88
            },
            "average_response_time": 4.2,
            "momentum_streaks": 5,
            "head_to_head": pos["record"]
        },
        "ladder_status": {
            "current_rung": 8,
            "cash_equivalent": "₦40,000",
            "correct_answers": 8,
            "total_questions": 15,
            "direction": "climbing" 
        },
        "tournament_position": pos,
        "enrolled_positions": enrolled_positions,
        "lifelines": {
            "phone_a_scholar": {"available": True, "description": "Call a registered scholar for 30 seconds of help."},
            "flip_a_book": {"available": False, "description": "Consult a reference book for 45 seconds."},
            "search_the_net": {"available": True, "description": "Perform one supervised web search."}
        }
    }

@router.get("/tournaments")
def get_available_tournaments(school: School = Depends(get_current_school), db: Session = Depends(deps.get_db)):
    """Return all active tournaments visible to this school (state-scoped + global)."""
    from sqlalchemy import or_
    school_state = school.state

    tournaments = db.query(Tournament).filter(
        Tournament.is_active == True,
        or_(
            Tournament.scope == "global",
            (Tournament.scope == "state") & (Tournament.state == school_state)
        )
    ).all()

    # Also note which ones the school is already enrolled in
    enrolled_ids = set()
    for team in school.teams:
        if team.tournament_id:
            enrolled_ids.add(team.tournament_id)

    result = []
    for t in tournaments:
        enrolled_count = len(t.teams) if hasattr(t, 'teams') else 0
        result.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "scope": t.scope,
            "state": t.state,
            "entry_fee": t.entry_fee,
            "is_free": t.is_free,
            "team_size": t.team_size,
            "max_schools": t.max_schools,
            "start_date": str(t.start_date) if t.start_date else None,
            "end_date": str(t.end_date) if t.end_date else None,
            "track_name": t.track.name if t.track else None,
            "enrolled_schools": enrolled_count,
            "is_enrolled": t.id in enrolled_ids,
        })

    return result

def check_event_stage_and_qualification(ev, team):
    """
    Enforces tournament progression rules:
    - Only start or group stage of the competition can be registered for directly.
    - Advanced stages (Quarter Final, Semi Final, 3rd Place, Final) cannot be registered for directly.
    - Only teams that have qualified from the start stage or preceding stage can advance.
    """
    name_lower = (ev.name or "").lower()
    stage_lower = (ev.stage or "").lower()

    if "quarter" in name_lower or "quarter" in stage_lower:
        stage_type = "knockout"
        required_stage = "Group Stage 2"
        is_qualified = bool(
            team and (
                team.is_qf_qualified or 
                (team.current_stage and any(s in team.current_stage.lower() for s in ["quarter", "semi", "final"]))
            )
        )
        lock_message = f"Direct registration is closed for {ev.name}. This is an advanced knockout stage; only teams finishing in the qualifying positions of {required_stage} can advance to this round."
    elif "semi" in name_lower or "semi" in stage_lower:
        stage_type = "knockout"
        required_stage = "Quarter-Final"
        is_qualified = bool(
            team and team.current_stage and any(s in team.current_stage.lower() for s in ["semi", "final"])
        )
        lock_message = f"Direct registration is closed for {ev.name}. Only Quarter-Final winners advance to the Semi-Finals."
    elif "3rd" in name_lower or "third" in name_lower:
        stage_type = "knockout"
        required_stage = "Semi-Final"
        is_qualified = bool(
            team and team.current_stage and any(s in team.current_stage.lower() for s in ["3rd", "third", "semi", "final"])
        )
        lock_message = f"Direct registration is closed for {ev.name}. Only Semi-Final runners-up advance to the 3rd Place Match."
    elif "final" in name_lower or "final" in stage_lower or "championship" in name_lower:
        stage_type = "knockout"
        required_stage = "Semi-Final"
        is_qualified = bool(
            team and team.current_stage and any(s in team.current_stage.lower() for s in ["final", "grand final"])
        )
        lock_message = f"Direct registration is closed for {ev.name}. Only Semi-Final winners advance to the Championship Final."
    else:
        stage_type = "group_stage"
        required_stage = None
        is_qualified = True
        lock_message = None

    return {
        "is_knockout_stage": stage_type == "knockout",
        "stage_type": stage_type,
        "required_stage": required_stage,
        "is_qualified": is_qualified,
        "lock_message": lock_message
    }

@router.get("/events")
def get_available_events(
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    school: School = Depends(get_current_school), 
    db: Session = Depends(deps.get_db)
):
    """Return full Match & Events data for School Admin with live, upcoming, and registered teams."""
    from app.models.events import MatchEvent, EventRegistration, LiveMatch
    from app.db.seed_events import seed_events_if_empty, DEFAULT_RULES, DEFAULT_PRIZES, DEFAULT_HOW_IT_WORKS, DEFAULT_SPEC_BADGES
    import json
    
    # Auto-seed if empty
    seed_events_if_empty(db)

    # Base query
    query = db.query(MatchEvent)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                MatchEvent.name.ilike(search_fmt),
                MatchEvent.subtitle.ilike(search_fmt),
                MatchEvent.stage.ilike(search_fmt),
                MatchEvent.category.ilike(search_fmt)
            )
        )

    all_events = query.order_by(MatchEvent.date.asc()).all()

    # Find current school's most active team
    school_team = None
    for tm in school.teams:
        if tm.members and len(tm.members) > 0:
            school_team = tm
            break
    if not school_team and school.teams:
        school_team = school.teams[0]

    # Format events
    formatted_events = []
    featured_event = None
    upcoming_events = []

    for ev in all_events:
        month_str = ev.date.strftime("%b").upper() if ev.date else "OCT"
        day_str = ev.date.strftime("%d") if ev.date else "25"
        formatted_date = ev.date.strftime("%B %d, %Y") if ev.date else "October 25, 2026"

        # Check stage progression and qualification gate
        q_info = check_event_stage_and_qualification(ev, school_team)

        # Registered teams for this event
        regs = db.query(EventRegistration).filter(EventRegistration.event_id == ev.id).all()
        registered_teams = []
        is_school_registered = False

        for r in regs:
            t = r.team
            if t:
                is_mine = (t.school_id == school.id)
                if is_mine:
                    is_school_registered = True
                registered_teams.append({
                    "id": t.id,
                    "name": t.name or (t.school.name if t.school else f"Team {t.id}"),
                    "school_name": t.school.name if t.school else "Independent",
                    "members_count": len(t.members) if t.members else 11,
                    "status": r.status,
                    "stage": t.current_stage or ev.stage,
                    "is_my_team": is_mine
                })

        # Ensure full group roster displays top contender names
        default_names = ['Team Faith', 'Team Truth', 'Team Hope', 'Team Glory', 'Kings Academy', 'Grace High', 'Dominion Stars', 'St. Gregory Elite']
        existing_names = {rt['name'] for rt in registered_teams}
        for name in default_names:
            if name not in existing_names and len(registered_teams) < 32:
                registered_teams.append({
                    "id": f"contender-{name.lower().replace(' ', '-')}",
                    "name": name,
                    "school_name": f"{name} Collegiate",
                    "members_count": 11,
                    "status": "Confirmed",
                    "stage": ev.stage,
                    "is_my_team": False
                })

        # Safely parse JSON fields
        try:
            rules_list = json.loads(ev.rules) if ev.rules else json.loads(DEFAULT_RULES)
        except Exception:
            rules_list = []

        try:
            prizes_list = json.loads(ev.prizes_detail) if ev.prizes_detail else json.loads(DEFAULT_PRIZES)
        except Exception:
            prizes_list = []

        try:
            how_it_works_list = json.loads(ev.how_it_works) if ev.how_it_works else json.loads(DEFAULT_HOW_IT_WORKS)
        except Exception:
            how_it_works_list = []

        try:
            spec_badges_list = json.loads(ev.spec_badges) if ev.spec_badges else json.loads(DEFAULT_SPEC_BADGES)
        except Exception:
            spec_badges_list = []

        tag = ev.category or "Tournament"
        tag_color = "bg-purple-900/50 text-purple-300 border-purple-500/40"
        if "semi" in ev.name.lower():
            tag_color = "bg-blue-900/50 text-blue-300 border-blue-500/40"
        elif "3rd" in ev.name.lower():
            tag_color = "bg-teal-900/50 text-teal-300 border-teal-500/40"
        elif "final" in ev.name.lower():
            tag_color = "bg-amber-900/50 text-amber-300 border-amber-500/40"
        elif ev.event_type == "special":
            tag_color = "bg-rose-900/50 text-rose-300 border-rose-500/40"

        now_utc = datetime.utcnow()
        has_started = False
        is_live = False
        countdown_info = None

        if ev.date:
            if now_utc >= ev.date:
                has_started = True
                if now_utc <= ev.date + timedelta(hours=2, minutes=30) or ev.status == 'live':
                    is_live = True
                    actual_status = "live"
                else:
                    is_live = False
                    actual_status = "completed"
            else:
                has_started = False
                is_live = False
                actual_status = "upcoming"
                diff = ev.date - now_utc
                days = diff.days
                hours, rem = divmod(diff.seconds, 3600)
                mins, _ = divmod(rem, 60)
                if days > 0:
                    countdown_info = f"{days}d {hours}h {mins}m"
                else:
                    countdown_info = f"{hours}h {mins}m"
        else:
            actual_status = ev.status or "upcoming"
            has_started = actual_status in ["live", "completed"]
            is_live = actual_status == "live"

        ev_dict = {
            "id": ev.id,
            "name": ev.name,
            "subtitle": ev.subtitle or "",
            "category": ev.category or "Tournament",
            "event_type": ev.event_type or "tournament",
            "date": ev.date.isoformat() if ev.date else None,
            "month": month_str,
            "day": day_str,
            "formatted_date": formatted_date,
            "time_str": ev.time_str or "7:00 PM (WAT)",
            "status": actual_status,
            "has_started": has_started,
            "is_live": is_live,
            "countdown_info": countdown_info,
            "user_role": "school_admin",
            "can_enter_exam_room": False,
            "ladder_url": "/ladder",
            "is_featured": ev.is_featured,
            "venue": ev.venue or "Online (In-App Live Arena)",
            "teams_count": ev.teams_count or "32 Teams",
            "stage": ev.stage or "Group Stage 2",
            "round_info": ev.round_info or "",
            "format": ev.format or "100 Questions / 7 Challenges",
            "duration": ev.duration or "Approx. 2 Hours",
            "prize": ev.prize or "₦5,000,000 Grand Prize",
            "quote": ev.quote or "Same Scripture. Same Clock. Rebuild It. Solve It. Lock It. Wait for the Reveal.",
            "description": ev.description or "",
            "rules": rules_list,
            "prizes_detail": prizes_list,
            "how_it_works": how_it_works_list,
            "spec_badges": spec_badges_list,
            "banner_url": ev.banner_url,
            "registered_teams": registered_teams,
            "is_enrolled": is_school_registered,
            "tag": tag,
            "tag_color": tag_color,
            # Stage progression and qualification metadata
            "is_knockout_stage": q_info["is_knockout_stage"],
            "stage_type": q_info["stage_type"],
            "required_stage": q_info["required_stage"],
            "team_is_qualified": q_info["is_qualified"],
            "lock_reason": q_info["lock_message"],
            "can_register": (not is_school_registered) and (not q_info["is_knockout_stage"] or q_info["is_qualified"])
        }

        formatted_events.append(ev_dict)

        if ev.is_featured or (is_live and not featured_event):
            featured_event = ev_dict

        if actual_status in ["upcoming", "live"] and not ev.is_featured:
            upcoming_events.append({
                "id": ev.id,
                "month": month_str,
                "day": day_str,
                "title": ev.name,
                "teams": ev.subtitle or ev.teams_count,
                "time": ev.time_str,
                "tag": tag,
                "tagColor": tag_color,
                "stage": ev.stage,
                "status": actual_status,
                "has_started": has_started,
                "is_live": is_live,
                "is_knockout_stage": q_info["is_knockout_stage"],
                "team_is_qualified": q_info["is_qualified"]
            })

    if not featured_event and formatted_events:
        featured_event = formatted_events[0]

    school_team_dict = None
    if school_team:
        school_team_dict = {
            "id": school_team.id,
            "name": school_team.name,
            "stage": school_team.current_stage,
            "status": school_team.status,
            "members_count": len(school_team.members) if school_team.members else 0,
            "is_qf_qualified": school_team.is_qf_qualified,
            "scheduled_exam_date": str(school_team.scheduled_exam_date) if school_team.scheduled_exam_date else None,
            "scheduled_exam_time": school_team.scheduled_exam_time
        }

    return {
        "status": "success",
        "featured_event": featured_event,
        "events": formatted_events,
        "upcoming_events": upcoming_events,
        "school_team": school_team_dict,
        "total_events": len(formatted_events)
    }

@router.get("/events/{event_id}")
def get_event_detail(
    event_id: int,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    from app.models.events import MatchEvent, EventRegistration
    from app.db.seed_events import DEFAULT_RULES, DEFAULT_PRIZES, DEFAULT_HOW_IT_WORKS, DEFAULT_SPEC_BADGES
    import json

    ev = db.query(MatchEvent).filter(MatchEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    # Find school's team
    school_team = None
    for tm in school.teams:
        if tm.members and len(tm.members) > 0:
            school_team = tm
            break
    if not school_team and school.teams:
        school_team = school.teams[0]

    month_str = ev.date.strftime("%b").upper() if ev.date else "OCT"
    day_str = ev.date.strftime("%d") if ev.date else "25"
    formatted_date = ev.date.strftime("%B %d, %Y") if ev.date else "October 25, 2026"

    q_info = check_event_stage_and_qualification(ev, school_team)

    regs = db.query(EventRegistration).filter(EventRegistration.event_id == ev.id).all()
    registered_teams = []
    is_school_registered = False

    for r in regs:
        t = r.team
        if t:
            is_mine = (t.school_id == school.id)
            if is_mine:
                is_school_registered = True
            registered_teams.append({
                "id": t.id,
                "name": t.name or (t.school.name if t.school else f"Team {t.id}"),
                "school_name": t.school.name if t.school else "Independent",
                "members_count": len(t.members) if t.members else 11,
                "status": r.status,
                "stage": t.current_stage or ev.stage,
                "is_my_team": is_mine
            })

    try:
        rules_list = json.loads(ev.rules) if ev.rules else json.loads(DEFAULT_RULES)
    except Exception:
        rules_list = []

    try:
        prizes_list = json.loads(ev.prizes_detail) if ev.prizes_detail else json.loads(DEFAULT_PRIZES)
    except Exception:
        prizes_list = []

    try:
        how_it_works_list = json.loads(ev.how_it_works) if ev.how_it_works else json.loads(DEFAULT_HOW_IT_WORKS)
    except Exception:
        how_it_works_list = []

    try:
        spec_badges_list = json.loads(ev.spec_badges) if ev.spec_badges else json.loads(DEFAULT_SPEC_BADGES)
    except Exception:
        spec_badges_list = []

    tag = ev.category or "Tournament"
    tag_color = "bg-purple-900/50 text-purple-300 border-purple-500/40"
    if "semi" in ev.name.lower():
        tag_color = "bg-blue-900/50 text-blue-300 border-blue-500/40"
    elif "3rd" in ev.name.lower():
        tag_color = "bg-teal-900/50 text-teal-300 border-teal-500/40"
    elif "final" in ev.name.lower():
        tag_color = "bg-amber-900/50 text-amber-300 border-amber-500/40"
    elif ev.event_type == "special":
        tag_color = "bg-rose-900/50 text-rose-300 border-rose-500/40"

    now_utc = datetime.utcnow()
    has_started = False
    is_live = False
    countdown_info = None

    if ev.date:
        if now_utc >= ev.date:
            has_started = True
            if now_utc <= ev.date + timedelta(hours=2, minutes=30) or ev.status == 'live':
                is_live = True
                actual_status = "live"
            else:
                is_live = False
                actual_status = "completed"
        else:
            has_started = False
            is_live = False
            actual_status = "upcoming"
            diff = ev.date - now_utc
            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            mins, _ = divmod(rem, 60)
            if days > 0:
                countdown_info = f"{days}d {hours}h {mins}m"
            else:
                countdown_info = f"{hours}h {mins}m"
    else:
        actual_status = ev.status or "upcoming"
        has_started = actual_status in ["live", "completed"]
        is_live = actual_status == "live"

    return {
        "id": ev.id,
        "name": ev.name,
        "subtitle": ev.subtitle or "",
        "category": ev.category or "Tournament",
        "event_type": ev.event_type or "tournament",
        "date": ev.date.isoformat() if ev.date else None,
        "month": month_str,
        "day": day_str,
        "formatted_date": formatted_date,
        "time_str": ev.time_str or "7:00 PM (WAT)",
        "status": actual_status,
        "has_started": has_started,
        "is_live": is_live,
        "countdown_info": countdown_info,
        "user_role": "school_admin",
        "can_enter_exam_room": False,
        "ladder_url": "/ladder",
        "is_featured": ev.is_featured,
        "venue": ev.venue or "Online (In-App Live Arena)",
        "teams_count": ev.teams_count or "32 Teams",
        "stage": ev.stage or "Group Stage 2",
        "round_info": ev.round_info or "",
        "format": ev.format or "100 Questions / 7 Challenges",
        "duration": ev.duration or "Approx. 2 Hours",
        "prize": ev.prize or "₦5,000,000 Grand Prize",
        "quote": ev.quote or "Same Scripture. Same Clock. Rebuild It. Solve It. Lock It. Wait for the Reveal.",
        "description": ev.description or "",
        "rules": rules_list,
        "prizes_detail": prizes_list,
        "how_it_works": how_it_works_list,
        "spec_badges": spec_badges_list,
        "banner_url": ev.banner_url,
        "registered_teams": registered_teams,
        "is_enrolled": is_school_registered,
        "tag": tag,
        "tag_color": tag_color,
        "is_knockout_stage": q_info["is_knockout_stage"],
        "stage_type": q_info["stage_type"],
        "required_stage": q_info["required_stage"],
        "team_is_qualified": q_info["is_qualified"],
        "lock_reason": q_info["lock_message"],
        "can_register": (not is_school_registered) and (not q_info["is_knockout_stage"] or q_info["is_qualified"])
    }

@router.post("/events/{event_id}/register")
def register_for_event(
    event_id: int,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    from app.models.events import MatchEvent, EventRegistration

    ev = db.query(MatchEvent).filter(MatchEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    
    team = None
    for tm in school.teams:
        if tm.members and len(tm.members) >= 1:
            team = tm
            break
    if not team and school.teams:
        team = school.teams[0]
    
    if not team:
        raise HTTPException(status_code=400, detail="School does not have a team. Please register a team in My Team first.")

    # ENFORCE RULE: Only start or group stage of the competition can be registered for.
    # Advanced stages cannot be registered for directly; only qualified teams can participate.
    q_info = check_event_stage_and_qualification(ev, team)
    if q_info["is_knockout_stage"] and not q_info["is_qualified"]:
        raise HTTPException(
            status_code=403,
            detail=q_info["lock_message"] or f"Direct registration is closed for {ev.name}. Only teams that qualify from {q_info['required_stage']} can advance to this stage."
        )

    existing = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.team_id == team.id
    ).first()
    if existing:
        return {"status": "success", "message": f"Team {team.name} is already registered/confirmed for {ev.name}"}

    reg = EventRegistration(
        event_id=ev.id,
        team_id=team.id,
        status="Confirmed"
    )
    db.add(reg)
    db.commit()
    return {"status": "success", "message": f"Team {team.name} successfully registered/confirmed for {ev.name}!"}


@router.patch("/profile", response_model=school_schemas.School)
def update_profile(
    payload: school_schemas.SchoolUpdate, 
    school: School = Depends(get_current_school), 
    db: Session = Depends(deps.get_db)
):
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(school, key, value)
    
    db.add(school)
    db.commit()
    db.refresh(school)
    return school

class EnrollPayload(BaseModel):
    tournament_id: int
    payment_reference: Optional[str] = None

@router.post("/enroll")
def enroll_tournament(
    payload: EnrollPayload,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Verify tournament exists and is active
    tournament = db.query(Tournament).filter(Tournament.id == payload.tournament_id, Tournament.is_active == True).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found or inactive.")
        
    # Check max_schools limit
    enrolled_count = db.query(Team).filter(Team.tournament_id == tournament.id).count()
    if enrolled_count >= tournament.max_schools:
        raise HTTPException(status_code=400, detail="Tournament is already full.")

    # Check payment if not free
    if not tournament.is_free:
        fee_str = tournament.entry_fee or (tournament.track.entry_fee if tournament.track else None)
        if fee_str and str(fee_str).lower() != 'free':
            if not payload.payment_reference:
                raise HTTPException(status_code=400, detail="Payment reference is required for this tournament")
            
            # Check if reference already used
            existing_tx = db.query(PaymentTransaction).filter(PaymentTransaction.reference == payload.payment_reference).first()
            if existing_tx:
                raise HTTPException(status_code=400, detail="Payment reference has already been used.")

            import re
            # Extract numeric value from string (e.g., '₦50,000' -> 50000.0)
            numeric_fee = 0.0
            try:
                numeric_fee = float(re.sub(r'[^\d.]', '', fee_str))
            except:
                pass
                
            tx = PaymentTransaction(
                school_id=school.id,
                tournament_id=tournament.id,
                amount=numeric_fee,
                reference=payload.payment_reference,
                status='success'
            )
            db.add(tx)
            # Commit happens below with team
        
    # Get or create school's team
    if school.teams:
        team = school.teams[0]
    else:
        team = Team(name=f"{school.name} Team", school_id=school.id)
        db.add(team)
        db.commit()
        db.refresh(team)
        
    team.tournament_id = payload.tournament_id
    team.tournament_track_id = tournament.tournament_track_id # Keep backwards compatible
    db.commit()
    db.refresh(team)
    
    # Send email detailing necessary steps
    if school.contact_email:
        email_body = f"""
        <html>
            <body>
                <h2>Welcome to {tournament.name}!</h2>
                <p>Hello {school.name},</p>
                <p>Your school has successfully enrolled in the tournament.</p>
                <h3>Next Steps:</h3>
                <ol>
                    <li><strong>Build your Team:</strong> Navigate to the Team Management page to add your students and assign their specialties.</li>
                    <li><strong>Wait for Scheduling:</strong> The tournament administrators will schedule your matches.</li>
                    <li><strong>Check your Dashboard:</strong> Watch the countdown timer on your dashboard to see when your next match is.</li>
                    <li><strong>Join the Match:</strong> When it's time, click "Join Match Now" to enter the live arena!</li>
                </ol>
                <p>Good luck!</p>
            </body>
        </html>
        """
        background_tasks.add_task(
            email_service.send_email,
            to_email=school.contact_email,
            subject=f"Enrollment Confirmed: {tournament.name}",
            body=email_body
        )
    
    return {"status": "success", "message": f"Successfully enrolled in {tournament.name}"}

from fastapi import UploadFile, File
import os
import shutil
import time

@router.post("/logo", response_model=school_schemas.School)
def upload_logo(
    file: UploadFile = File(...),
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    # Ensure static directory exists
    os.makedirs("static/logos", exist_ok=True)
    
    # Generate unique filename to prevent caching issues
    extension = file.filename.split(".")[-1]
    filename = f"school_{school.id}_{int(time.time())}.{extension}"
    file_location = f"static/logos/{filename}"
    
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    # Public URL
    public_url = f"http://localhost:8000/static/logos/{filename}"
    school.logo_url = public_url
    
    db.add(school)
    db.commit()
    db.refresh(school)
    return school

from app.models.school import TournamentMatch, Team, MatchParticipant

@router.get("/tournaments/{tournament_id}/matches")
def get_team_matches(
    tournament_id: int, 
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    team = db.query(Team).filter(Team.school_id == school.id, Team.tournament_id == tournament_id).first()
    if not team:
        raise HTTPException(status_code=403, detail="Your school is not enrolled in this tournament.")
        
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
        
    if tournament.status != "active":
        return {"status": "pending", "message": "The tournament has not started yet. Pairings will be visible once the admin starts the tournament."}
        
    # Find all matches that involve this team across all stages

    
    matches = db.query(TournamentMatch).join(MatchParticipant).filter(
        TournamentMatch.tournament_stage_id.in_([s.id for s in tournament.stages]),
        MatchParticipant.team_id == team.id
    ).all()
    
    match_list = []
    for m in matches:
        participants = []
        for p in m.participants:
            participants.append({
                "team_id": p.team_id,
                "team_name": p.team.name if p.team else "Unknown",
                "score": p.score
            })
            
        match_list.append({
            "id": m.id,
            "stage_id": m.tournament_stage_id,
            "status": m.status,
            "scheduled_time": m.match_date,
            "participants": participants
        })
        
    return {
        "status": "active",
        "team_id": team.id,
        "matches": match_list
    }

class QuizAnswer(BaseModel):
    question_id: int
    selected_option: str # A, B, C, or D

class QuizSubmission(BaseModel):
    answers: list[QuizAnswer]

@router.get("/matches/{match_id}/questions")
def get_match_questions(
    match_id: int, 
    db: Session = Depends(deps.get_db),
    current_user: School = Depends(get_current_school)
):
    from app.models.question import Question
    import random
    
    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    if match.status != "active":
        raise HTTPException(status_code=400, detail="Match is not active")
        
    stage = match.stage
    tournament = stage.tournament
    
    # Verify team belongs to school and match
    participant = db.query(MatchParticipant).join(Team).filter(
        MatchParticipant.match_id == match_id,
        Team.school_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=403, detail="Your team is not in this match")
        
    # Get random questions for the tournament track and school category
    questions_query = db.query(Question).filter(
        Question.tournament_track_id == tournament.tournament_track_id,
        Question.school_category == current_user.category,
        Question.is_active == True
    )
    
    all_questions = questions_query.all()
    if len(all_questions) < 10:
        raise HTTPException(status_code=400, detail="Not enough questions available for this track and category.")
        
    # Randomly select 10 questions.
    # Note: Using python's random for simplicity, for true stateless we should perhaps hash the team_id. 
    # Since the user asked to randomize for each team, we just random sample here.
    # A robust app would save the assigned questions in DB, but this works for MVP.
    selected_questions = random.sample(all_questions, 10)
    
    # Strip correct option
    public_questions = []
    for q in selected_questions:
        public_questions.append({
            "id": q.id,
            "text": q.text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "subject": q.subject,
        })
        
    return public_questions

@router.post("/matches/{match_id}/submit")
def submit_match_answers(
    match_id: int, 
    submission: QuizSubmission,
    db: Session = Depends(deps.get_db),
    current_user: School = Depends(get_current_school)
):
    from app.models.question import Question
    
    participant = db.query(MatchParticipant).join(Team).filter(
        MatchParticipant.match_id == match_id,
        Team.school_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=403, detail="Your team is not in this match")
        
    match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if match.status != "active":
        raise HTTPException(status_code=400, detail="Match is no longer active")
        
    # Calculate score
    score = 0
    question_ids = [ans.question_id for ans in submission.answers]
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    q_map = {q.id: q for q in questions}
    
    for ans in submission.answers:
        q = q_map.get(ans.question_id)
        if q and q.correct_option.strip().upper() == ans.selected_option.strip().upper():
            score += 1 # 1 point per correct answer
            
    participant.score = score
    db.commit()
    
    return {"message": "Answers submitted successfully", "score": score}

@router.get("/practice/summary")
def get_practice_summary(db: Session = Depends(deps.get_db)):
    from app.models.question import Question
    subjects_map = {
        "general": ["General", "General Knowledge", "Current Affairs", "Science", "Social Studies"],
        "spelling": ["Spelling", "English Language", "English", "Grammar", "Word"],
        "bible": ["Bible", "Scripture", "Word Wars", "Religion", "Christian Religious Studies", "CRS"],
        "sports": ["Sports", "Physical", "Athletics", "Football", "Olympics"],
        # Legacy aliases
        "math": ["Mathematics", "Maths", "Math"],
        "eng": ["English Language", "English"],
        "sci": ["General Science", "Basic Science", "Science", "Biology", "Physics", "Chemistry"],
        "soc": ["Current Affairs", "Social Studies", "General"]
    }
    counts = {}
    for key, aliases in subjects_map.items():
        conditions = [Question.subject.ilike(f"%{a}%") for a in aliases]
        count = db.query(Question).filter(Question.is_active == True, or_(*conditions)).count()
        counts[key] = count
    return counts

@router.get("/practice/questions")
def get_practice_questions(
    subject: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(deps.get_db)
):
    import random
    from app.models.question import Question
    query = db.query(Question).filter(Question.is_active == True)
    
    if subject and subject.lower() != 'all':
        query = query.filter(Question.subject.ilike(f"%{subject}%"))
    
    questions = query.all()
    if not questions:
        questions = db.query(Question).filter(Question.is_active == True).all()
        
    if len(questions) > limit:
        questions = random.sample(questions, limit)
    elif questions:
        random.shuffle(questions)
        
    return [
        {
            "id": q.id,
            "text": q.text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option.strip().upper(),
            "subject": q.subject,
            "difficulty": q.difficulty.value if hasattr(q.difficulty, 'value') else str(q.difficulty),
            "school_category": q.school_category.value if hasattr(q.school_category, 'value') else str(q.school_category),
        }
        for q in questions
    ]


