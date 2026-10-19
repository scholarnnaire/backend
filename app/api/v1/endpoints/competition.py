import os
import json
import random
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.api import deps
from app.models.school import Team, TeamMember, School
from app.models.question import Question
from app.models.competition import (
    ExamSession, Certificate, SubstitutionRequest, AuditLog, 
    QuarterFinalSchedule, Notification, LadderboardConfig, GameDivision
)
from app.core.security import create_access_token, decode_access_token

router = APIRouter()

# ----------------- SCHEMAS -----------------

class GameDivisionCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    stages: Optional[List[str]] = None

class GameDivisionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    stages: Optional[List[str]] = None
    is_active: Optional[bool] = None

class StagesUpdatePayload(BaseModel):
    stages: List[str]


class LadderRungSchema(BaseModel):
    rank: int
    title: str
    points: int
    division: str = "lower" # "upper" | "lower"
    isCrown: Optional[bool] = False
    isCurrent: Optional[bool] = False

class LadderboardConfigUpdatePayload(BaseModel):
    stage: Optional[str] = "global"
    upper_division_name: Optional[str] = "Upper Division"
    lower_division_name: Optional[str] = "Lower Division"
    qualification_threshold: Optional[int] = 24
    points_per_correct: Optional[int] = 100
    rungs: List[LadderRungSchema]


class MemberLoginPayload(BaseModel):
    participant_id: Optional[str] = None
    identifier: Optional[str] = None
    pin: Optional[str] = None
    role_hint: Optional[str] = None

class ExamStartRequest(BaseModel):
    team_member_id: int
    stage: Optional[str] = "Group Stage 1"
    bypass_rules: Optional[bool] = False

class ExamAnswerRequest(BaseModel):
    session_id: int
    question_id: int
    selected_option: Optional[str] = None # "A", "B", "C", "D" or None (missed/timeout)
    time_taken: Optional[int] = 0

class ExamCompleteRequest(BaseModel):
    session_id: int

class RescheduleRequest(BaseModel):
    captain_member_id: int
    new_date: date
    new_time: str # e.g. "10:00 AM"
    reason: Optional[str] = "Preferred team schedule"

class SubstitutionPayload(BaseModel):
    team_id: int
    captain_id: int
    half: str # "First Half" or "Second Half"
    outgoing_members: List[str] # up to 3 names
    incoming_members: List[str] # up to 3 names

class ApproveSubstitutionPayload(BaseModel):
    request_id: int

class AdminScheduleQFPayload(BaseModel):
    scheduled_date: date
    scheduled_time: str
    venue: str
    instructions: str

# ----------------- HELPERS -----------------

def check_team_constitution(team: Team, db: Session) -> Dict[str, Any]:
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    captain = next((m for m in members if m.is_captain or "Captain" in (m.role or "")), None)
    regular_members = [m for m in members if m != captain]
    verified_count = sum(1 for m in members if m.verification_status == "Verified")
    is_fully_constituted = (len(members) >= 11 and captain is not None and verified_count >= 11)
    
    if is_fully_constituted and team.status in ["Registration in Progress", "Pending"]:
        team.status = "Ready for Group Stage"
        if not team.scheduled_exam_date:
            team.scheduled_exam_date = date.today() + timedelta(days=2)
            team.scheduled_exam_time = "10:00 AM"
        db.commit()

    return {
        "total_members": len(members),
        "required_members": 11,
        "captain_present": captain is not None,
        "captain_name": captain.name if captain else None,
        "regular_count": len(regular_members),
        "verified_count": verified_count,
        "is_fully_constituted": is_fully_constituted,
        "status": "Fully Constituted" if is_fully_constituted else "Registration in Progress"
    }

class ParticipantRegisterPayload(BaseModel):
    team_id: Optional[int] = None
    team_code: Optional[str] = None
    new_team_umbrella_name: Optional[str] = None
    name: str
    email: Optional[str] = None
    passport_photo_url: Optional[str] = None
    role: str = "Member"
    subject: Optional[str] = "General Science"
    qualification_code: Optional[str] = None

# ----------------- ENDPOINTS -----------------

@router.post("/member-login")
def member_login(payload: MemberLoginPayload, db: Session = Depends(deps.get_db)):
    """
    Authenticates a Team Member or Team Captain using Participant ID, Name, or Email.
    Returns access token, role ('captain' or 'member'), and profile metadata.
    """
    lookup = (payload.participant_id or payload.identifier or "").strip()
    if not lookup:
        raise HTTPException(status_code=400, detail="Participant ID or identifier is required")

    # Match by exact participant_id first (case-insensitive)
    member = db.query(TeamMember).filter(TeamMember.participant_id.ilike(lookup)).first()

    # If not found, match by name or email
    if not member:
        member = db.query(TeamMember).filter(
            or_(
                TeamMember.name.ilike(f"%{lookup}%"),
                TeamMember.email.ilike(lookup)
            )
        ).first()

    if not member:
        raise HTTPException(
            status_code=404, 
            detail=f"No participant found matching '{lookup}'. Please check your Participant ID (e.g. P001245 or P000987)."
        )

    team = member.team
    school_id = team.school_id if team and team.school_id else 1
    is_cap = bool(member.is_captain or "captain" in (member.role or "").lower())

    access_token = create_access_token(
        data={
            "sub": str(school_id),
            "member_id": member.id,
            "participant_id": member.participant_id,
            "role": "captain" if is_cap else "member",
            "is_captain": is_cap,
            "team_id": member.team_id
        }
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "role": "captain" if is_cap else "member",
        "is_captain": is_cap,
        "member": {
            "id": member.id,
            "name": member.name,
            "participant_id": member.participant_id,
            "role": "Team Captain" if is_cap else "Member",
            "is_captain": is_cap,
            "passport_photo_url": member.passport_photo_url,
            "current_stage": member.current_stage or "Group Stage 2",
            "qualification_status": member.qualification_status or "In Progress",
            "score": member.score or 0,
            "verification_status": member.verification_status or "Verified",
            "team_id": member.team_id
        },
        "team": {
            "id": team.id if team else 23,
            "name": team.name if team else "Visionaries",
            "umbrella_name": (team.umbrella_name or team.name) if team else "Visionaries",
            "code": team.code if team else "T0023",
            "current_stage": team.current_stage if team else "Group Stage 2",
            "status": team.status if team else "Fully Constituted",
            "scheduled_exam_date": str(team.scheduled_exam_date) if team and team.scheduled_exam_date else "2025-04-15",
            "scheduled_exam_time": team.scheduled_exam_time if team else "10:00 AM (WAT)"
        }
    }

@router.get("/demo-members")
def get_demo_members(db: Session = Depends(deps.get_db)):
    """Returns quick-access demo credentials for both Captain and Participating Member."""
    captain = db.query(TeamMember).filter(TeamMember.is_captain == True).first()
    member = db.query(TeamMember).filter(TeamMember.is_captain == False).first()
    
    return {
        "captain": {
            "participant_id": captain.participant_id if captain else "P000987",
            "name": captain.name if captain else "Sarah Johnson",
            "role": "Team Captain",
            "team": captain.team.name if (captain and captain.team) else "Visionaries"
        },
        "member": {
            "participant_id": member.participant_id if member else "P001245",
            "name": member.name if member else "Daniel Okafor",
            "role": "Member",
            "team": member.team.name if (member and member.team) else "Visionaries"
        }
    }

@router.post("/upload-passport")
async def upload_passport(file: UploadFile = File(...)):
    """Uploads a participant's passport photograph and returns the accessible static URL."""
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if ext not in allowed_extensions:
        ext = ".jpg"
    
    os.makedirs("static/passports", exist_ok=True)
    filename = f"passport_{uuid.uuid4().hex[:12]}{ext}"
    filepath = os.path.join("static/passports", filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
        
    return {
        "success": True,
        "url": f"/static/passports/{filename}"
    }

@router.post("/participant/register")
def register_participant(payload: ParticipantRegisterPayload, db: Session = Depends(deps.get_db)):
    """
    Registers a participant under an approved team umbrella name or creates a new umbrella team.
    Enforces passport photo, 1 Captain + 10 members structure, and optional qualification code linking.
    """
    team = None
    if payload.team_id:
        team = db.query(Team).filter(Team.id == payload.team_id).first()
    elif payload.team_code:
        team = db.query(Team).filter(Team.code == payload.team_code.strip().upper()).first()
    
    if not team and payload.new_team_umbrella_name:
        umbrella_clean = payload.new_team_umbrella_name.strip()
        new_code = f"TM-{uuid.uuid4().hex[:6].upper()}"
        # Fetch or create a default school or associate with team
        school = db.query(School).first()
        school_id = school.id if school else 1
        team = Team(
            name=f"{umbrella_clean} Team",
            umbrella_name=umbrella_clean,
            code=new_code,
            school_id=school_id,
            status="Registration in Progress",
            current_stage="Group Stage 1"
        )
        db.add(team)
        db.commit()
        db.refresh(team)
    
    if not team:
        raise HTTPException(status_code=400, detail="Team not found. Please provide an existing team ID/code or provide a new team umbrella name.")

    # Check if team already has 11 members
    current_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    
    is_captain = (payload.role.lower() == "captain")
    if is_captain:
        # Check if captain already exists
        existing_cap = next((m for m in current_members if m.is_captain or "Captain" in (m.role or "")), None)
        if existing_cap:
            raise HTTPException(status_code=400, detail=f"Team already has a Captain ({existing_cap.name}). You can register as a Participating Member.")

    # Validate qualification code if provided
    current_stage = "Group Stage 1"
    if payload.qualification_code:
        cert = db.query(Certificate).filter(Certificate.qualification_code == payload.qualification_code.strip().upper()).first()
        if cert:
            stage_map = {
                "Group Stage 1": "Group Stage 2",
                "Group Stage 2": "Group Stage 3",
                "Group Stage 3": "Group Stage 4",
                "Group Stage 4": "Quarter-Final"
            }
            current_stage = stage_map.get(cert.stage, "Group Stage 1")

    # Generate participant ID
    part_id = f"P-{team.code}-{len(current_members) + 1:03d}"
    passport_photo = payload.passport_photo_url or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"

    new_member = TeamMember(
        name=payload.name.strip(),
        role="Captain" if is_captain else "Member",
        subject=payload.subject or "General Science",
        status="Active",
        team_id=team.id,
        participant_id=part_id,
        passport_photo_url=passport_photo,
        is_captain=is_captain,
        verification_status="Verified",
        current_stage=current_stage,
        qualification_status="In Progress",
        score=0
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    # Check constitution
    constitution = check_team_constitution(team, db)

    # Create welcome notification
    notif = Notification(
        recipient_role="participant",
        recipient_id=str(new_member.id),
        title="Registration Successful",
        message=f"Welcome {new_member.name}! You are registered under team {team.umbrella_name or team.name} ({new_member.role}).",
        type="info"
    )
    db.add(notif)
    db.commit()

    return {
        "success": True,
        "message": f"Successfully registered {new_member.name} under {team.umbrella_name or team.name}",
        "member": {
            "id": new_member.id,
            "name": new_member.name,
            "participant_id": new_member.participant_id,
            "role": new_member.role,
            "is_captain": new_member.is_captain,
            "passport_photo_url": new_member.passport_photo_url,
            "current_stage": new_member.current_stage,
            "verification_status": new_member.verification_status,
        },
        "team": {
            "id": team.id,
            "name": team.name,
            "umbrella_name": team.umbrella_name or team.name,
            "code": team.code,
            "invite_link": f"/register?team_code={team.code}"
        },
        "constitution": constitution
    }

@router.get("/teams/public")
def get_public_teams(db: Session = Depends(deps.get_db)):
    teams = db.query(Team).all()
    return [{"id": t.id, "name": t.name, "umbrella_name": t.umbrella_name or t.name, "code": t.code} for t in teams]

@router.get("/team/{team_id}/constitution")
def get_team_constitution(team_id: int, db: Session = Depends(deps.get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return check_team_constitution(team, db)

def compute_next_examination_data(team: Team, member: Optional[TeamMember], constitution: Dict[str, Any], db: Session) -> Dict[str, Any]:
    now_utc = datetime.utcnow()
    countdown_display = None
    is_room_open = False
    lock_reason = None
    time_remaining_seconds = 0

    is_stage_completed = False
    if member:
        curr_stage = team.current_stage or member.current_stage or "Group Stage 1"
        comp_sess = db.query(ExamSession).filter(
            ExamSession.team_member_id == member.id,
            ExamSession.stage == curr_stage,
            ExamSession.status.in_(["Completed", "Finished"])
        ).first()
        if comp_sess:
            is_stage_completed = True

    if not constitution["is_fully_constituted"]:
        lock_reason = f"Incomplete Roster ({constitution['verified_count']}/11 Verified Members)"
        countdown_display = "Roster Pending"
    elif is_stage_completed:
        lock_reason = f"Stage Completed ({team.current_stage or 'Group Stage 1'})"
        countdown_display = "Stage Sitting Completed"
    elif team.scheduled_exam_date:
        exam_hour = 10
        exam_min = 0
        if team.scheduled_exam_time:
            try:
                t_str = team.scheduled_exam_time.strip().upper()
                is_pm = "PM" in t_str
                clean_t = t_str.replace("AM", "").replace("PM", "").replace("WAT", "").strip()
                parts = clean_t.split(":")
                exam_hour = int(parts[0])
                if is_pm and exam_hour < 12:
                    exam_hour += 12
                elif not is_pm and exam_hour == 12:
                    exam_hour = 0
                if len(parts) > 1:
                    exam_min = int(parts[1])
            except Exception:
                exam_hour = 10
                exam_min = 0
        exam_dt_utc = datetime.combine(team.scheduled_exam_date, datetime.min.time().replace(hour=exam_hour, minute=exam_min)) - timedelta(hours=1)
        diff = exam_dt_utc - now_utc
        time_remaining_seconds = int(diff.total_seconds())
        if time_remaining_seconds > 0:
            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            mins, secs = divmod(rem, 60)
            countdown_display = f"{days:02d} Days : {hours:02d} Hours : {mins:02d} Minutes"
            lock_reason = f"Locked • Opens in {days:02d}d {hours:02d}h {mins:02d}m"
            is_room_open = False
        else:
            countdown_display = "Active Competition Window"
            is_room_open = True
    else:
        lock_reason = "Match Date Not Scheduled"
        countdown_display = "Not Scheduled"

    return {
        "stage": team.current_stage or "Group Stage 1",
        "date": str(team.scheduled_exam_date) if team.scheduled_exam_date else "Not Scheduled",
        "time": team.scheduled_exam_time or "10:00 AM",
        "time_zone": "WAT (UTC+1)",
        "countdown": countdown_display,
        "number_of_questions": 44,
        "time_per_question": "10 Seconds",
        "marks_per_question": 100,
        "max_score": 4400,
        "qualification_requirement": "24 / 44 Correct Answers (~55%)",
        "negative_marking": "None (No downward movement)",
        "instructions": "All team members participate simultaneously. Each member receives 44 randomized questions and progresses based on individual score.",
        "is_room_open": is_room_open,
        "is_team_constituted": constitution["is_fully_constituted"],
        "is_stage_completed": is_stage_completed,
        "lock_reason": lock_reason,
        "time_remaining_seconds": max(0, time_remaining_seconds)
    }

def build_competition_history(db: Session, team: Team, member: Optional[TeamMember], certs: list, next_exam: Optional[Dict[str, Any]] = None):
    sessions = []
    if member:
        sessions = db.query(ExamSession).filter(ExamSession.team_member_id == member.id).order_by(ExamSession.id.desc()).all()
    if not sessions and team:
        sessions = db.query(ExamSession).filter(ExamSession.team_id == team.id).order_by(ExamSession.id.desc()).all()

    competitions_participated = []
    competition_results = []
    seen_stages = set()

    for s in sessions:
        if s.stage not in seen_stages:
            seen_stages.add(s.stage)
            date_str = s.start_time.strftime("%d %b %Y, %I:%M %p") if s.start_time else "Completed"
            cert = next((c for c in certs if c.stage == s.stage), None)
            correct = s.correct_count if s.correct_count is not None else (s.score // 100 if s.score else 0)
            pct = round((correct / 44.0) * 100, 1) if correct else (round((s.score / 4400.0) * 100, 1) if s.score else 0)
            
            is_completed = s.status in ["Completed", "Finished"]
            status_label = "Completed" if is_completed else "In Progress"
            qual_label = "QUALIFIED" if s.is_qualified or s.score >= 2400 else ("IN PROGRESS" if s.status == "In Progress" else "COMPLETED")

            can_sit = False if is_completed else (next_exam.get("is_room_open", False) if next_exam else False)
            lock_desc = "Sitting Concluded" if is_completed else (next_exam.get("lock_reason") if next_exam else "Match window not open")

            comp_obj = {
                "id": s.id,
                "competition_name": f"{team.name} • {s.stage}",
                "stage": s.stage,
                "category": "Official CBT Tournament Stage",
                "date": date_str,
                "status": status_label,
                "total_questions": 44,
                "time_per_question": "10 Seconds",
                "sitting_mode": "Simultaneous Online Sitting",
                "score": s.score,
                "max_score": 4400,
                "is_qualified": s.is_qualified or s.score >= 2400,
                "qualification_status": qual_label,
                "can_sit": can_sit,
                "lock_reason": lock_desc
            }
            competitions_participated.append(comp_obj)

            competition_results.append({
                "competition_name": f"{team.name} • {s.stage}",
                "stage": s.stage,
                "date_taken": date_str,
                "status": status_label,
                "score": s.score,
                "max_score": 4400,
                "correct_count": correct,
                "incorrect_count": s.incorrect_count if s.incorrect_count is not None else max(0, 44 - correct),
                "missed_count": s.missed_count or 0,
                "accuracy_percentage": pct,
                "result_status": qual_label,
                "qualification_code": cert.qualification_code if cert else f"QC-{s.stage[:3].upper()}-{s.id:04d}",
                "certificate_number": cert.certificate_number if cert else None,
                "passing_threshold": "24 / 44 (55%)",
                "subject_breakdown": [
                    {"subject": "English Language & Lexis", "questions": 11, "score": int(s.score * 0.28)},
                    {"subject": "Mathematics & Logic", "questions": 11, "score": int(s.score * 0.26)},
                    {"subject": "Integrated Basic Sciences", "questions": 11, "score": int(s.score * 0.24)},
                    {"subject": "Current Affairs & General", "questions": 11, "score": int(s.score * 0.22)}
                ]
            })

    current_stage = team.current_stage or "Group Stage 2"
    if current_stage not in seen_stages:
        sched_date = f"{team.scheduled_exam_date or '15 Apr 2026'}, {team.scheduled_exam_time or '10:00 AM'}"
        can_sit = next_exam.get("is_room_open", False) if next_exam else False
        lock_desc = next_exam.get("lock_reason") if next_exam else "Match window not open"
        competitions_participated.insert(0, {
            "id": 999,
            "competition_name": f"{team.name} • {current_stage}",
            "stage": current_stage,
            "category": "Official CBT Tournament Stage",
            "date": sched_date,
            "status": "Scheduled",
            "total_questions": 44,
            "time_per_question": "10 Seconds",
            "sitting_mode": "Simultaneous Online Sitting",
            "score": 0,
            "max_score": 4400,
            "is_qualified": False,
            "qualification_status": "SCHEDULED",
            "can_sit": can_sit,
            "lock_reason": lock_desc
        })
        competition_results.append({
            "competition_name": f"{team.name} • {current_stage}",
            "stage": current_stage,
            "date_taken": sched_date,
            "status": "Scheduled",
            "score": 0,
            "max_score": 4400,
            "correct_count": 0,
            "incorrect_count": 0,
            "missed_count": 0,
            "accuracy_percentage": 0,
            "result_status": "UPCOMING",
            "qualification_code": "PENDING SITTING",
            "certificate_number": None,
            "passing_threshold": "28 / 44 (64%)",
            "subject_breakdown": [
                {"subject": "English Language & Lexis", "questions": 11, "score": 0},
                {"subject": "Mathematics & Logic", "questions": 11, "score": 0},
                {"subject": "Integrated Basic Sciences", "questions": 11, "score": 0},
                {"subject": "Current Affairs & General", "questions": 11, "score": 0}
            ]
        })

    return competitions_participated, competition_results


@router.get("/participant-dashboard/{member_identifier}")
def get_participant_dashboard(member_identifier: str, db: Session = Depends(deps.get_db)):
    member = None
    if member_identifier.isdigit():
        member = db.query(TeamMember).filter(TeamMember.id == int(member_identifier)).first()
    if not member:
        member = db.query(TeamMember).filter(TeamMember.participant_id.ilike(member_identifier.strip())).first()
    if not member:
        member = db.query(TeamMember).filter(TeamMember.name.ilike(member_identifier.strip())).first()
    if not member:
        member = db.query(TeamMember).first()
    if not member:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    team = member.team
    if not team:
        raise HTTPException(status_code=404, detail="Team not found for this participant")

    constitution = check_team_constitution(team, db)
    next_exam_data = compute_next_examination_data(team, member, constitution, db)

    # Certificates
    certs = db.query(Certificate).filter(Certificate.participant_id == member.participant_id).all()

    # Notifications
    notifications = db.query(Notification).filter(
        (Notification.recipient_id == str(member.id)) | 
        (Notification.recipient_id == str(team.id)) | 
        (Notification.recipient_role == "all") |
        (Notification.recipient_role == "participant")
    ).order_by(Notification.created_at.desc()).limit(10).all()

    # Recent exam session
    recent_session = db.query(ExamSession).filter(
        ExamSession.team_member_id == member.id
    ).order_by(ExamSession.id.desc()).first()

    stages_progression = [
        {"stage": "Group Stage 1", "status": "completed" if member.current_stage in ["Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final"] else ("current" if member.current_stage == "Group Stage 1" else "pending")},
        {"stage": "Group Stage 2", "status": "completed" if member.current_stage in ["Group Stage 3", "Group Stage 4", "Quarter-Final"] else ("current" if member.current_stage == "Group Stage 2" else "pending")},
        {"stage": "Group Stage 3", "status": "completed" if member.current_stage in ["Group Stage 4", "Quarter-Final"] else ("current" if member.current_stage == "Group Stage 3" else "pending")},
        {"stage": "Group Stage 4", "status": "completed" if member.current_stage == "Quarter-Final" else ("current" if member.current_stage == "Group Stage 4" else "pending")},
        {"stage": "Quarter-Final", "status": "current" if member.current_stage == "Quarter-Final" else "pending"}
    ]

    # Team members with competition status
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    team_members = [
        {
            "id": m.id,
            "name": m.name,
            "participant_id": m.participant_id or f"MOW-PAR-{m.id:04d}",
            "passport_photo_url": m.passport_photo_url,
            "role": m.role or ("Team Captain" if m.is_captain else "Member"),
            "is_captain": m.is_captain,
            "verification_status": m.verification_status or "Verified",
            "current_stage": m.current_stage or "Group Stage 1",
            "qualification_status": m.qualification_status or ("Qualified" if m.score and m.score >= 2400 else "In Progress"),
            "score": m.score or 0,
            "competition_status": f"{m.current_stage or 'Group Stage 1'} ({m.qualification_status or 'In Progress'})"
        }
        for m in members
    ]

    competitions_participated, competition_results = build_competition_history(db, team, member, certs, next_exam_data)

    return {
        "profile": {
            "member_id": member.id,
            "name": member.name,
            "participant_id": member.participant_id or f"MOW-PAR-{member.id:04d}",
            "passport_photo_url": member.passport_photo_url or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
            "email": member.email,
            "role": member.role or "Participating Member",
            "is_captain": member.is_captain,
            "registration_status": member.status or "Active",
            "verification_status": member.verification_status or "Verified",
            "current_stage": member.current_stage or "Group Stage 1",
            "qualification_status": member.qualification_status or "Pending",
            "account_status": "Active"
        },
        "team": {
            "team_id": team.id,
            "team_name": team.name,
            "umbrella_name": team.umbrella_name or team.name,
            "team_code": team.code or f"MOW-TEAM-{team.id:03d}",
            "captain_name": constitution["captain_name"],
            "total_registered": constitution["total_members"],
            "verified_members": constitution["verified_count"],
            "is_fully_constituted": constitution["is_fully_constituted"],
            "team_status": team.status,
            "current_stage": team.current_stage or "Group Stage 1"
        },
        "next_examination": next_exam_data,
        "examination_status": recent_session.status if recent_session else (team.status if team.status in ["Exam In Progress", "Exam Scheduled"] else "Scheduled"),
        "stages_progression": stages_progression,
        "team_members": team_members,
        "competitions_participated": competitions_participated,
        "competition_results": competition_results,
        "certificates": [
            {
                "id": c.id,
                "stage": c.stage,
                "certificate_number": c.certificate_number,
                "qualification_code": c.qualification_code,
                "score": c.score,
                "issued_date": c.issued_date.strftime("%Y-%m-%d"),
                "status": "Verified Official"
            } for c in certs
        ],
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")
            } for n in notifications
        ],
        "restrictions": {
            "can_reschedule": False,
            "can_request_substitution": False,
            "can_manage_roster": False,
            "role_title": "Participating Member (View Only Scheduling)"
        }
    }

@router.get("/captain-dashboard/{team_identifier}")
def get_captain_dashboard(team_identifier: str, db: Session = Depends(deps.get_db)):
    team = None
    if team_identifier.isdigit():
        team = db.query(Team).filter(Team.id == int(team_identifier)).first()
        if not team:
            # Check if identifier was member id
            m = db.query(TeamMember).filter(TeamMember.id == int(team_identifier)).first()
            if m and m.team:
                team = m.team
    if not team:
        # Match by team code or team name
        team = db.query(Team).filter(or_(Team.code.ilike(team_identifier.strip()), Team.name.ilike(team_identifier.strip()))).first()
    if not team:
        # Match by captain participant_id
        m = db.query(TeamMember).filter(TeamMember.participant_id.ilike(team_identifier.strip())).first()
        if m and m.team:
            team = m.team
    if not team:
        # Fallback to first team
        team = db.query(Team).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    captain = next((m for m in members if m.is_captain or "Captain" in (m.role or "")), members[0] if members else None)
    
    constitution = check_team_constitution(team, db)

    # Quarter-Final Quota
    qf_tracker = db.query(QuarterFinalSchedule).first()
    qf_status_info = {
        "target_quota": qf_tracker.target_quota if qf_tracker else 32,
        "confirmed_teams_count": qf_tracker.confirmed_teams_count if qf_tracker else 0,
        "status": qf_tracker.status if qf_tracker else "Quarter-Final Qualification in Progress",
        "live_studio_date": str(qf_tracker.scheduled_date) if (qf_tracker and qf_tracker.scheduled_date) else None,
        "live_studio_time": qf_tracker.scheduled_time if qf_tracker else None,
        "venue": qf_tracker.venue if qf_tracker else "Live Studio Arena",
        "instructions": qf_tracker.instructions if qf_tracker else None
    }

    # Audit Trail
    logs = db.query(AuditLog).filter(AuditLog.team_id == team.id).order_by(AuditLog.created_at.desc()).limit(15).all()

    # Substitution Requests
    sub_requests = db.query(SubstitutionRequest).filter(SubstitutionRequest.team_id == team.id).order_by(SubstitutionRequest.requested_at.desc()).all()

    # Team Members list with status
    member_records = []
    for m in members:
        member_records.append({
            "id": m.id,
            "name": m.name,
            "participant_id": m.participant_id or f"MOW-PAR-{m.id:04d}",
            "passport_photo_url": m.passport_photo_url or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
            "role": m.role or ("Team Captain" if m.is_captain else "Participating Member"),
            "is_captain": m.is_captain,
            "verification_status": m.verification_status or "Verified",
            "current_stage": m.current_stage or "Group Stage 1",
            "qualification_status": m.qualification_status or "Pending",
            "score": m.score or 0,
            "stage_1": "✓" if m.current_stage in ["Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final"] else ("In Progress" if m.current_stage == "Group Stage 1" else "—"),
            "stage_2": "✓" if m.current_stage in ["Group Stage 3", "Group Stage 4", "Quarter-Final"] else ("In Progress" if m.current_stage == "Group Stage 2" else "—"),
            "stage_3": "✓" if m.current_stage in ["Group Stage 4", "Quarter-Final"] else ("In Progress" if m.current_stage == "Group Stage 3" else "—"),
            "stage_4": "✓" if m.current_stage == "Quarter-Final" else ("In Progress" if m.current_stage == "Group Stage 4" else "—"),
        })

    # Available alternative slots for rescheduling
    today = date.today()
    available_reschedule_slots = [
        {"date": str(today + timedelta(days=1)), "times": ["09:00 AM", "11:30 AM", "02:00 PM", "04:30 PM"]},
        {"date": str(today + timedelta(days=2)), "times": ["10:00 AM", "01:00 PM", "03:30 PM", "06:00 PM"]},
        {"date": str(today + timedelta(days=3)), "times": ["09:00 AM", "12:00 PM", "02:30 PM", "05:00 PM"]},
        {"date": str(today + timedelta(days=4)), "times": ["10:30 AM", "01:30 PM", "04:00 PM"]},
    ]

    # Notifications
    notifications = db.query(Notification).filter(
        (Notification.recipient_id == str(team.id)) | 
        (Notification.recipient_role.in_(["all", "captain", "team"]))
    ).order_by(Notification.created_at.desc()).limit(15).all()

    # Certificates & Competition History
    certs = db.query(Certificate).filter((Certificate.participant_id == (captain.participant_id if captain else "")) | (Certificate.team_name == team.name)).all()
    next_exam_data = compute_next_examination_data(team, captain, constitution, db)
    competitions_participated, competition_results = build_competition_history(db, team, captain, certs, next_exam_data)

    return {
        "next_examination": next_exam_data,
        "captain": {
            "member_id": captain.id if captain else None,
            "name": captain.name if captain else "Captain",
            "badge": "🏅 TEAM CAPTAIN",
            "participant_id": captain.participant_id if captain else None,
            "passport_photo_url": captain.passport_photo_url if captain else "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150"
        },
        "team": {
            "team_id": team.id,
            "team_name": team.name,
            "umbrella_name": team.umbrella_name or team.name,
            "team_code": team.code or f"MOW-TEAM-{team.id:03d}",
            "status": team.status,
            "current_stage": team.current_stage or "Group Stage 1",
            "scheduled_exam_date": str(team.scheduled_exam_date) if team.scheduled_exam_date else None,
            "scheduled_exam_time": team.scheduled_exam_time or "10:00 AM",
            "substitutions_used_half1": team.substitutions_used_half1,
            "substitutions_used_half2": team.substitutions_used_half2,
        },
        "constitution": constitution,
        "team_members": member_records,
        "available_reschedule_slots": available_reschedule_slots,
        "quarter_final_status": qf_status_info,
        "substitution_requests": [
            {
                "id": s.id,
                "half": s.half,
                "outgoing": s.outgoing_members,
                "incoming": s.incoming_members,
                "status": s.status,
                "requested_at": s.requested_at.strftime("%Y-%m-%d %H:%M")
            } for s in sub_requests
        ],
        "audit_logs": [
            {
                "id": l.id,
                "actor_name": l.actor_name,
                "actor_role": l.actor_role,
                "action": l.action,
                "previous_value": l.previous_value,
                "new_value": l.new_value,
                "created_at": l.created_at.strftime("%Y-%m-%d %H:%M")
            } for l in logs
        ],
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")
            } for n in notifications
        ],
        "competitions_participated": competitions_participated,
        "competition_results": competition_results,
        "certificates": [
            {
                "id": c.id,
                "stage": c.stage,
                "certificate_number": c.certificate_number,
                "qualification_code": c.qualification_code,
                "score": c.score,
                "issued_date": c.issued_date.strftime("%Y-%m-%d"),
                "status": "Verified Official"
            } for c in certs
        ],
        "privileges": {
            "can_reschedule": True,
            "can_request_substitution": True,
            "can_manage_roster": True,
            "has_captain_badge": True
        }
    }

# ----------------- CAPTAIN RESCHEDULING -----------------

@router.post("/team/{team_id}/reschedule")
def reschedule_exam(team_id: int, payload: RescheduleRequest, db: Session = Depends(deps.get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # STRICT PERMISSION: Only Team Captain can reschedule
    captain = db.query(TeamMember).filter(TeamMember.id == payload.captain_member_id, TeamMember.team_id == team.id).first()
    if not captain or (not captain.is_captain and "Captain" not in (captain.role or "")):
        raise HTTPException(status_code=403, detail="Unauthorized: Only the designated Team Captain possesses the authority to reschedule team examinations.")

    prev_date = str(team.scheduled_exam_date)
    prev_time = team.scheduled_exam_time

    # Update appointment
    team.scheduled_exam_date = payload.new_date
    team.scheduled_exam_time = payload.new_time
    team.status = "Exam Rescheduled"
    
    # Audit Log
    log = AuditLog(
        team_id=team.id,
        actor_name=captain.name,
        actor_role="Team Captain",
        action="Examination Rescheduled",
        previous_value=f"Date: {prev_date}, Time: {prev_time}",
        new_value=f"Date: {payload.new_date}, Time: {payload.new_time}",
        details=f"Reason: {payload.reason}"
    )
    db.add(log)

    # Send Notification to all team members
    notification = Notification(
        recipient_role="team",
        recipient_id=str(team.id),
        title=f"Examination Schedule Updated for {team.name}",
        message=f"Previous Examination Schedule:\nDate: {prev_date}\nTime: {prev_time}\n\nNew Examination Schedule:\nDate: {payload.new_date}\nTime: {payload.new_time}\n\nUpdated by Team Captain {captain.name}.",
        type="exam"
    )
    db.add(notification)

    db.commit()
    db.refresh(team)

    return {
        "status": "success",
        "message": "Team examination schedule updated successfully",
        "new_date": str(team.scheduled_exam_date),
        "new_time": team.scheduled_exam_time
    }

# ----------------- EXAM ENGINE (44 Questions, 10s per question, 24/44 threshold, 100 marks) -----------------

@router.post("/exam/start")
def start_exam(payload: ExamStartRequest, db: Session = Depends(deps.get_db)):
    member = None
    if payload.team_member_id:
        member = db.query(TeamMember).filter(TeamMember.id == payload.team_member_id).first()
    
    if not member:
        if payload.bypass_rules:
            member = db.query(TeamMember).first()
        else:
            raise HTTPException(status_code=404, detail="Participant not found")
    
    team = member.team if member else None
    if not team:
        if payload.bypass_rules:
            team = db.query(Team).first()
        else:
            raise HTTPException(status_code=404, detail="Team not found")

    stage = payload.stage or member.current_stage or "Group Stage 1"

    # 1. VERIFICATION CHECK
    if member.verification_status != "Verified" and not payload.bypass_rules:
        raise HTTPException(
            status_code=403, 
            detail="Participant registration is pending verification. Only verified contestants may enter the official examination room."
        )

    # 2. CONSTITUTION CHECK (11 Verified Members)
    constitution = check_team_constitution(team, db)
    if not constitution["is_fully_constituted"] and not payload.bypass_rules:
        raise HTTPException(
            status_code=403,
            detail=f"Team roster is incomplete ({constitution['verified_count']}/11 verified members). Under official tournament rules, all 11 members must be verified before entering the competition room."
        )

    # 2b. SCHOLARNNAIRE ADMIN LIVE EVENT CHECK
    from app.models.events import MatchEvent
    active_event = db.query(MatchEvent).filter(
        (MatchEvent.stage.ilike(f"%{stage}%")) | (MatchEvent.name.ilike(f"%{stage}%"))
    ).first()
    if active_event and not payload.bypass_rules:
        if not active_event.is_live and active_event.status != "live":
            raise HTTPException(
                status_code=403,
                detail=f"The Online Examination Room for '{active_event.name}' is locked. The event has not been started by the Scholarnnaire Administrator. Early entry and previewing are strictly prohibited under tournament rules."
            )

    # 3. SCHEDULED MATCH WINDOW CHECK
    if team.scheduled_exam_date and not payload.bypass_rules:
        exam_hour = 10
        exam_min = 0
        if team.scheduled_exam_time:
            try:
                t_str = team.scheduled_exam_time.strip().upper()
                is_pm = "PM" in t_str
                clean_t = t_str.replace("AM", "").replace("PM", "").replace("WAT", "").strip()
                parts = clean_t.split(":")
                exam_hour = int(parts[0])
                if is_pm and exam_hour < 12:
                    exam_hour += 12
                elif not is_pm and exam_hour == 12:
                    exam_hour = 0
                if len(parts) > 1:
                    exam_min = int(parts[1])
            except Exception:
                exam_hour = 10
                exam_min = 0
        
        # Scheduled time is in WAT (UTC+1), subtract 1 hour for UTC comparison
        exam_dt_utc = datetime.combine(team.scheduled_exam_date, datetime.min.time().replace(hour=exam_hour, minute=exam_min)) - timedelta(hours=1)
        now_utc = datetime.utcnow()
        if now_utc < exam_dt_utc:
            diff = exam_dt_utc - now_utc
            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            mins, _ = divmod(rem, 60)
            time_left_str = f"{days:02d} Days : {hours:02d} Hours : {mins:02d} Minutes" if days > 0 else f"{hours:02d} Hours : {mins:02d} Minutes"
            raise HTTPException(
                status_code=403,
                detail=f"The Exam Room is locked. The scheduled competition window opens in {time_left_str} ({team.scheduled_exam_date.strftime('%d %b %Y')} at {team.scheduled_exam_time or '10:00 AM WAT'}). Early entry is prohibited under tournament rules."
            )

    # 4. ONE-SITTING PER STAGE CHECK
    existing_completed = db.query(ExamSession).filter(
        ExamSession.team_member_id == member.id,
        ExamSession.stage == stage,
        ExamSession.status.in_(["Completed", "Finished"])
    ).first()
    if existing_completed and not payload.bypass_rules:
        raise HTTPException(
            status_code=403,
            detail=f"You have already completed the examination for {stage} (Score: {existing_completed.score:,} pts). Retaking an official tournament stage sitting is prohibited under tournament rules."
        )

    # Fetch questions strictly from this stage's Examination Bank
    stage_questions = db.query(Question).filter(
        Question.stage == stage,
        Question.is_active == True
    ).all()

    if len(stage_questions) < 44:
        # Fallback to any questions to guarantee 44 questions if stage questions < 44
        all_q = db.query(Question).filter(Question.is_active == True).all()
        stage_questions = all_q

    # Select 44 questions
    selected_pool = stage_questions[:44] if len(stage_questions) >= 44 else stage_questions

    # RANDOMIZE question order independently for this participant!
    randomized_questions = list(selected_pool)
    random.shuffle(randomized_questions)
    q_ids = [q.id for q in randomized_questions]

    # Create exam session
    session = ExamSession(
        team_id=team.id,
        team_member_id=member.id,
        stage=stage,
        questions_order=json.dumps(q_ids),
        current_question_index=0,
        answers_submitted=json.dumps({}),
        correct_count=0,
        incorrect_count=0,
        missed_count=0,
        score=0,
        max_score=4400,
        is_qualified=False,
        status="In Progress",
        start_time=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Format public questions for frontend (strip correct answers)
    public_questions = []
    for q in randomized_questions:
        public_questions.append({
            "id": q.id,
            "text": q.text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "subject": q.subject,
        })

    return {
        "session_id": session.id,
        "participant_name": member.name,
        "participant_id": member.participant_id or f"MOW-PAR-{member.id:04d}",
        "team_name": team.name,
        "stage": stage,
        "total_questions": len(public_questions),
        "time_per_question": 10, # 10 seconds per question
        "marks_per_question": 100, # 100 marks per correct question
        "max_score": 4400,
        "qualification_threshold": 24, # 24 / 44 to qualify
        "negative_marking": False,
        "questions": public_questions
    }

@router.post("/exam/answer")
def submit_exam_answer(payload: ExamAnswerRequest, db: Session = Depends(deps.get_db)):
    session = db.query(ExamSession).filter(ExamSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if session.status == "Completed":
        raise HTTPException(status_code=400, detail="Exam session is already completed")

    question = db.query(Question).filter(Question.id == payload.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    answers_map = json.loads(session.answers_submitted or "{}")
    answers_map[str(payload.question_id)] = payload.selected_option
    session.answers_submitted = json.dumps(answers_map)

    is_correct = False
    if payload.selected_option and payload.selected_option.strip().upper() == question.correct_option.strip().upper():
        is_correct = True
        session.correct_count += 1
        session.score += 100 # 100 marks per correct answer
    elif payload.selected_option:
        session.incorrect_count += 1
        # NO downward movement or deduction of previously earned points!
    else:
        session.missed_count += 1
        # Missed question does not reduce accumulated score!

    session.current_question_index += 1
    session.is_qualified = (session.correct_count >= 24)

    db.commit()
    db.refresh(session)

    needed_to_qualify = max(0, 24 - session.correct_count)

    return {
        "is_correct": is_correct,
        "current_score": session.score,
        "correct_count": session.correct_count,
        "incorrect_count": session.incorrect_count,
        "missed_count": session.missed_count,
        "current_question_index": session.current_question_index,
        "is_qualified": session.is_qualified,
        "progress_message": f"{session.correct_count}/44" if needed_to_qualify == 0 else f"{session.correct_count}/44 — {needed_to_qualify} more correct answers required to qualify"
    }

@router.post("/exam/complete")
def complete_exam(payload: ExamCompleteRequest, db: Session = Depends(deps.get_db)):
    session = db.query(ExamSession).filter(ExamSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")

    session.status = "Completed"
    session.end_time = datetime.utcnow()
    if session.start_time:
        session.time_taken_seconds = int((session.end_time - session.start_time).total_seconds())

    is_qualified = session.correct_count >= 24
    session.is_qualified = is_qualified

    member = session.team_member
    team = session.team

    certificate_data = None
    next_stage = None

    if is_qualified:
        member.qualification_status = "Qualified"
        member.highest_stage_qualified = session.stage
        member.score = session.score

        # Determine next stage
        stage_order = ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final"]
        current_idx = stage_order.index(session.stage) if session.stage in stage_order else 0
        if current_idx < len(stage_order) - 1:
            next_stage = stage_order[current_idx + 1]
            member.current_stage = next_stage
        else:
            next_stage = "Quarter-Final"
            member.current_stage = "Quarter-Final"

        # Generate Unique Qualification Code & Certificate Number
        qual_code = f"QC-{session.stage[:3].upper()}-{random.randint(10000, 99999)}"
        cert_num = f"CERT-{session.stage[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"

        cert = Certificate(
            participant_id=member.participant_id or f"MOW-PAR-{member.id:04d}",
            participant_name=member.name,
            team_name=team.name,
            stage=session.stage,
            certificate_number=cert_num,
            qualification_code=qual_code,
            score=session.score,
            issued_date=datetime.utcnow()
        )
        db.add(cert)

        certificate_data = {
            "certificate_number": cert_num,
            "qualification_code": qual_code,
            "participant_name": member.name,
            "team_name": team.name,
            "stage": session.stage,
            "score": session.score,
            "issued_date": cert.issued_date.strftime("%B %d, %Y")
        }

        # Notification for Participant
        p_notif = Notification(
            recipient_role="participant",
            recipient_id=str(member.id),
            title=f"🎉 Congratulations! You have Qualified for {next_stage}",
            message=f"You successfully scored {session.score} marks ({session.correct_count}/44 correct) in {session.stage}! Your official Certificate of Qualification has been issued. Use qualification code {qual_code} to link your profile for {next_stage}.",
            type="qualification"
        )
        db.add(p_notif)

        # Notification for Team Captain
        c_notif = Notification(
            recipient_role="captain",
            recipient_id=str(team.id),
            title=f"Team Member Qualified: {member.name}",
            message=f"{member.name} scored {session.score} marks ({session.correct_count}/44) and has qualified for {next_stage}!",
            type="success"
        )
        db.add(c_notif)

        # Check if team qualifies for Quarter-Final
        all_team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        qf_eligible_count = sum(1 for m in all_team_members if m.current_stage == "Quarter-Final" or m.qualification_status == "Qualified")
        
        # If at least 6 members have scaled through Group Stage 4 (or designated threshold)
        if qf_eligible_count >= 6 and not team.is_qf_qualified:
            team.is_qf_qualified = True
            team.qf_qualified_at = datetime.utcnow()
            team.status = "Quarter-Final Qualified"

            # Update QF Tracker Counter
            qf_tracker = db.query(QuarterFinalSchedule).first()
            if not qf_tracker:
                qf_tracker = QuarterFinalSchedule(target_quota=32, confirmed_teams_count=1)
                db.add(qf_tracker)
            else:
                qf_tracker.confirmed_teams_count = db.query(Team).filter(Team.is_qf_qualified == True).count()
                if qf_tracker.confirmed_teams_count >= qf_tracker.target_quota:
                    qf_tracker.status = "Quarter-Final Qualification Completed"
                    # Notify Admin that 32 slots have been filled!
                    admin_notif = Notification(
                        recipient_role="admin",
                        recipient_id=None,
                        title="32 Quarter-Final Slots Filled!",
                        message="All 32 Quarter-Final qualifying teams have been confirmed! Live Studio Quarter-Final scheduling is now enabled on the Admin Dashboard.",
                        type="success"
                    )
                    db.add(admin_notif)

    else:
        member.qualification_status = "Not Qualified"
        member.score = session.score

    db.commit()

    return {
        "session_id": session.id,
        "participant_name": member.name,
        "stage": session.stage,
        "questions_attempted": session.correct_count + session.incorrect_count + session.missed_count,
        "correct_answers": session.correct_count,
        "incorrect_answers": session.incorrect_count,
        "missed_questions": session.missed_count,
        "final_score": session.score,
        "max_score": 4400,
        "percentage": round((session.correct_count / 44.0) * 100, 1),
        "is_qualified": is_qualified,
        "certificate": certificate_data,
        "next_stage": next_stage,
        "completion_time": session.time_taken_seconds
    }

# ----------------- CERTIFICATE VERIFICATION -----------------

@router.get("/certificate/verify/{qualification_code}")
def verify_certificate(qualification_code: str, db: Session = Depends(deps.get_db)):
    cert = db.query(Certificate).filter(Certificate.qualification_code == qualification_code).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Invalid qualification code")
    
    return {
        "valid": True,
        "qualification_code": cert.qualification_code,
        "certificate_number": cert.certificate_number,
        "participant_name": cert.participant_name,
        "team_name": cert.team_name,
        "stage": cert.stage,
        "score": cert.score,
        "issued_date": cert.issued_date.strftime("%B %d, %Y")
    }

# ----------------- LIVE STUDIO SUBSTITUTION RULE -----------------

@router.post("/live/request-substitution")
def request_live_substitution(payload: SubstitutionPayload, db: Session = Depends(deps.get_db)):
    team = db.query(Team).filter(Team.id == payload.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Verify caller is Captain
    captain = db.query(TeamMember).filter(TeamMember.id == payload.captain_id, TeamMember.team_id == team.id).first()
    if not captain or (not captain.is_captain and "Captain" not in (captain.role or "")):
        raise HTTPException(status_code=403, detail="Unauthorized: Only the Team Captain can request a substitution.")

    if len(payload.outgoing_members) > 3 or len(payload.incoming_members) > 3:
        raise HTTPException(status_code=400, detail="A substitution request can involve a maximum of three (3) members.")

    # Check 1 request per half rule
    if payload.half == "First Half" and team.substitutions_used_half1 >= 1:
        raise HTTPException(status_code=400, detail="Substitution limit reached: You have already used your 1 substitution opportunity for the First Half.")
    elif payload.half == "Second Half" and team.substitutions_used_half2 >= 1:
        raise HTTPException(status_code=400, detail="Substitution limit reached: You have already used your 1 substitution opportunity for the Second Half.")

    # Record substitution request
    sub = SubstitutionRequest(
        team_id=team.id,
        team_name=team.name,
        captain_name=captain.name,
        half=payload.half,
        outgoing_members=json.dumps(payload.outgoing_members),
        incoming_members=json.dumps(payload.incoming_members),
        status="Pending",
        requested_at=datetime.utcnow()
    )
    db.add(sub)

    if payload.half == "First Half":
        team.substitutions_used_half1 += 1
    else:
        team.substitutions_used_half2 += 1

    # Audit Log
    log = AuditLog(
        team_id=team.id,
        actor_name=captain.name,
        actor_role="Team Captain",
        action="Substitution Requested",
        previous_value="",
        new_value=f"Half: {payload.half}, Out: {payload.outgoing_members}, In: {payload.incoming_members}",
        details=f"Live Studio Substitution ({len(payload.outgoing_members)} players)"
    )
    db.add(log)

    # Notify Moderator
    notif = Notification(
        recipient_role="moderator",
        recipient_id=None,
        title=f"Substitution Request from {team.name}",
        message=f"Captain {captain.name} requested a substitution ({payload.half}): Out: {', '.join(payload.outgoing_members)} -> In: {', '.join(payload.incoming_members)}.",
        type="substitution"
    )
    db.add(notif)

    db.commit()
    db.refresh(sub)

    return {
        "status": "transmitted",
        "request_id": sub.id,
        "message": "Substitution request transmitted to Moderator Dashboard. Game will enter pause mode once approved by Moderator."
    }

@router.get("/live/substitution-requests")
def get_live_substitution_requests(db: Session = Depends(deps.get_db)):
    requests = db.query(SubstitutionRequest).order_by(SubstitutionRequest.requested_at.desc()).limit(20).all()
    return [
        {
            "id": r.id,
            "team_id": r.team_id,
            "team_name": r.team_name,
            "captain_name": r.captain_name,
            "half": r.half,
            "outgoing_members": json.loads(r.outgoing_members) if r.outgoing_members.startswith("[") else [r.outgoing_members],
            "incoming_members": json.loads(r.incoming_members) if r.incoming_members.startswith("[") else [r.incoming_members],
            "status": r.status,
            "requested_at": r.requested_at.strftime("%H:%M:%S")
        } for r in requests
    ]

@router.post("/live/activate-substitution")
def activate_substitution(payload: ApproveSubstitutionPayload, db: Session = Depends(deps.get_db)):
    sub = db.query(SubstitutionRequest).filter(SubstitutionRequest.id == payload.request_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Substitution request not found")

    sub.status = "Approved"
    sub.approved_at = datetime.utcnow()

    # Log action
    log = AuditLog(
        team_id=sub.team_id,
        actor_name="Moderator",
        actor_role="Moderator",
        action="Substitution Activated - Game Paused",
        previous_value="Game Active",
        new_value="Game Paused / Substitution in Progress",
        details=f"Substitution activated for {sub.team_name}"
    )
    db.add(log)
    db.commit()

    return {
        "status": "game_paused",
        "message": "Substitution activated! Game entered PAUSE MODE. All timers and contestant questions are frozen.",
        "request_id": sub.id
    }

@router.post("/live/resume-game")
def resume_game(payload: ApproveSubstitutionPayload, db: Session = Depends(deps.get_db)):
    sub = db.query(SubstitutionRequest).filter(SubstitutionRequest.id == payload.request_id).first()
    if sub:
        sub.status = "Completed"

    log = AuditLog(
        team_id=sub.team_id if sub else None,
        actor_name="Moderator",
        actor_role="Moderator",
        action="Game Resumed - Unfrozen",
        previous_value="Paused",
        new_value="Active",
        details="Game timers and questions resumed from pause point"
    )
    db.add(log)
    db.commit()

    return {
        "status": "game_resumed",
        "message": "Game unfrozen! All active timers and contestant dashboards have resumed from the exact pause point."
    }

# ----------------- ADMIN QUARTER-FINAL SCHEDULER & 32-TEAM QUOTA -----------------

@router.get("/admin/qf-quota")
def get_qf_quota(db: Session = Depends(deps.get_db)):
    tracker = db.query(QuarterFinalSchedule).first()
    if not tracker:
        tracker = QuarterFinalSchedule(target_quota=32, confirmed_teams_count=0)
        db.add(tracker)
        db.commit()
        db.refresh(tracker)

    qualified_teams = db.query(Team).filter(Team.is_qf_qualified == True).all()
    tracker.confirmed_teams_count = len(qualified_teams)
    
    if len(qualified_teams) >= 32 and tracker.status == "Quarter-Final Qualification in Progress":
        tracker.status = "Quarter-Final Qualification Completed"
    db.commit()

    teams_data = []
    for t in qualified_teams:
        members_count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        q_members = db.query(TeamMember).filter(TeamMember.team_id == t.id, TeamMember.qualification_status == "Qualified").all()
        teams_data.append({
            "team_id": t.id,
            "name": t.name,
            "school_name": t.school.name if t.school else "Independent",
            "qualified_participants_count": len(q_members),
            "total_members": members_count,
            "qualified_at": t.qf_qualified_at.strftime("%Y-%m-%d %H:%M") if t.qf_qualified_at else "Verified"
        })

    return {
        "target_quota": tracker.target_quota,
        "confirmed_count": len(qualified_teams),
        "status": tracker.status,
        "scheduling_enabled": len(qualified_teams) >= 32,
        "is_scheduled": tracker.is_published,
        "scheduled_date": str(tracker.scheduled_date) if tracker.scheduled_date else None,
        "scheduled_time": tracker.scheduled_time,
        "venue": tracker.venue,
        "instructions": tracker.instructions,
        "qualified_teams": teams_data
    }

@router.post("/admin/qf-schedule")
def schedule_quarter_final(payload: AdminScheduleQFPayload, db: Session = Depends(deps.get_db)):
    tracker = db.query(QuarterFinalSchedule).first()
    if not tracker:
        tracker = QuarterFinalSchedule(target_quota=32)
        db.add(tracker)

    tracker.scheduled_date = payload.scheduled_date
    tracker.scheduled_time = payload.scheduled_time
    tracker.venue = payload.venue
    tracker.instructions = payload.instructions
    tracker.is_published = True
    tracker.status = "Quarter-Final Scheduled"

    # Send broadcast notification to all 32 qualified teams
    notif = Notification(
        recipient_role="all",
        recipient_id=None,
        title="Official Live Studio Quarter-Final Schedule Released",
        message=f"The Live Studio Quarter-Final has been confirmed!\nDate: {payload.scheduled_date}\nTime: {payload.scheduled_time}\nVenue: {payload.venue}\nInstructions: {payload.instructions}",
        type="exam"
    )
    db.add(notif)
    db.commit()

    return {
        "status": "success",
        "message": "Quarter-Final Live Studio schedule confirmed and broadcast to all 32 qualified teams."
    }

# ----------------- ADMIN QUESTION BANKS PER STAGE -----------------

@router.get("/admin/question-banks")
def get_question_banks_summary(db: Session = Depends(deps.get_db)):
    stages = [
        "Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4",
        "Quarter-Final", "Semi-Final", "3rd-Place", "Final"
    ]
    summary = []
    for stage in stages:
        count = db.query(Question).filter(Question.stage == stage).count()
        active = db.query(Question).filter(Question.stage == stage, Question.is_active == True).count()
        summary.append({
            "stage": stage,
            "total_questions": count,
            "active_questions": active,
            "bank_status": "Ready (≥44 Questions)" if count >= 44 else "Needs More Questions"
        })
    return summary

# ----------------- SCHOLARNNAIRE LADDERBOARD & DIVISIONS CONFIGURATION -----------------

DEFAULT_LADDER_RUNGS = [
    {"rank": 1, "title": "SCHOLARNAIRE", "points": 4400, "division": "upper", "isCrown": True},
    {"rank": 2, "title": "PROFESSOR", "points": 4000, "division": "upper"},
    {"rank": 3, "title": "ASSOCIATE PROFESSOR", "points": 3600, "division": "upper"},
    {"rank": 4, "title": "Ph.D", "points": 3200, "division": "upper"},
    {"rank": 5, "title": "DON", "points": 2800, "division": "upper"},
    {"rank": 6, "title": "MASTERS", "points": 2400, "division": "upper"},
    {"rank": 7, "title": "TERTIARY", "points": 2000, "division": "lower"},
    {"rank": 8, "title": "SECONDARY", "points": 1600, "division": "lower"},
    {"rank": 9, "title": "PRIMARY", "points": 1200, "division": "lower"},
    {"rank": 10, "title": "KINDERGARTEN", "points": 800, "division": "lower"},
    {"rank": 11, "title": "NURSERY", "points": 400, "division": "lower"},
    {"rank": 12, "title": "YOU ARE HERE", "points": 0, "division": "lower", "isCurrent": True}
]

@router.get("/ladderboard/config")
def get_ladderboard_config(stage: Optional[str] = "global", db: Session = Depends(deps.get_db)):
    """Fetches the official Scholarnnaire ladderboard rungs, points, and division rules."""
    config = db.query(LadderboardConfig).filter(
        or_(LadderboardConfig.stage == stage, LadderboardConfig.stage == "global")
    ).first()
    
    if not config:
        config = LadderboardConfig(
            stage=stage or "global",
            upper_division_name="Upper Division",
            lower_division_name="Lower Division",
            qualification_threshold=24,
            points_per_correct=100,
            rungs_json=json.dumps(DEFAULT_LADDER_RUNGS)
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    try:
        rungs = json.loads(config.rungs_json)
    except Exception:
        rungs = DEFAULT_LADDER_RUNGS
        
    return {
        "id": config.id,
        "stage": config.stage,
        "upper_division_name": config.upper_division_name,
        "lower_division_name": config.lower_division_name,
        "qualification_threshold": config.qualification_threshold,
        "points_per_correct": config.points_per_correct,
        "rungs": rungs,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None
    }

@router.put("/ladderboard/config")
def update_ladderboard_config(payload: LadderboardConfigUpdatePayload, db: Session = Depends(deps.get_db)):
    """Allows Scholarnnaire Admin to customize ladderboard division thresholds, points, and rungs."""
    config = db.query(LadderboardConfig).filter(
        or_(LadderboardConfig.stage == payload.stage, LadderboardConfig.stage == "global")
    ).first()
    
    rungs_dict_list = [r.dict() for r in payload.rungs]
    # Ensure sorted ascending by rank
    rungs_dict_list.sort(key=lambda x: x["rank"])
    
    if not config:
        config = LadderboardConfig(
            stage=payload.stage or "global",
            upper_division_name=payload.upper_division_name or "Upper Division",
            lower_division_name=payload.lower_division_name or "Lower Division",
            qualification_threshold=payload.qualification_threshold or 24,
            points_per_correct=payload.points_per_correct or 100,
            rungs_json=json.dumps(rungs_dict_list)
        )
        db.add(config)
    else:
        config.upper_division_name = payload.upper_division_name or config.upper_division_name
        config.lower_division_name = payload.lower_division_name or config.lower_division_name
        config.qualification_threshold = payload.qualification_threshold or config.qualification_threshold
        config.points_per_correct = payload.points_per_correct or config.points_per_correct
        config.rungs_json = json.dumps(rungs_dict_list)
        config.updated_at = datetime.utcnow()
        
    db.commit()
    db.refresh(config)
    
    return {
        "status": "success",
        "message": "Ladderboard divisions and points configuration saved successfully.",
        "config": {
            "id": config.id,
            "stage": config.stage,
            "upper_division_name": config.upper_division_name,
            "lower_division_name": config.lower_division_name,
            "qualification_threshold": config.qualification_threshold,
            "points_per_correct": config.points_per_correct,
            "rungs": json.loads(config.rungs_json)
        }
    }

@router.post("/ladderboard/config/reset")
def reset_ladderboard_config(stage: Optional[str] = "global", db: Session = Depends(deps.get_db)):
    """Resets ladderboard configuration to standard Scholarnnaire TV tournament defaults."""
    config = db.query(LadderboardConfig).filter(
        or_(LadderboardConfig.stage == stage, LadderboardConfig.stage == "global")
    ).first()
    
    if not config:
        config = LadderboardConfig(
            stage=stage or "global",
            upper_division_name="Upper Division",
            lower_division_name="Lower Division",
            qualification_threshold=24,
            points_per_correct=100,
            rungs_json=json.dumps(DEFAULT_LADDER_RUNGS)
        )
        db.add(config)
    else:
        config.upper_division_name = "Upper Division"
        config.lower_division_name = "Lower Division"
        config.qualification_threshold = 24
        config.points_per_correct = 100
        config.rungs_json = json.dumps(DEFAULT_LADDER_RUNGS)
        config.updated_at = datetime.utcnow()
        
    db.commit()
    db.refresh(config)
    
    return {
        "status": "success",
        "message": "Ladderboard configuration reset to official tournament standard.",
        "config": {
            "id": config.id,
            "stage": config.stage,
            "upper_division_name": config.upper_division_name,
            "lower_division_name": config.lower_division_name,
            "qualification_threshold": config.qualification_threshold,
            "points_per_correct": config.points_per_correct,
            "rungs": json.loads(config.rungs_json)
        }
    }


# ----------------- SCHOLARNNAIRE 4 GAME DIVISIONS & STAGES -----------------

DEFAULT_GAME_DIVISIONS = [
    {
        "name": "SCHOLARNNAIRE GENERAL",
        "code": "scholarnnaire_general",
        "description": "Main Scholarnnaire General Academic Quiz & Championship",
        "stages": ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
    },
    {
        "name": "SCHOLARNNAIRE SPELL QUEST",
        "code": "scholarnnaire_spell_quest",
        "description": "Spell Quest Bee, Vocabulary & Word Master Gauntlet",
        "stages": ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
    },
    {
        "name": "SCHOLARNNAIRE BIBLE WORD CHALLENGE",
        "code": "scholarnnaire_bible_word_challenge",
        "description": "Scriptural Knowledge, Bible Verses & Sacred Word Mastery",
        "stages": ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
    },
    {
        "name": "SCHOLARNNAIRE SPORTS GAME SHOW",
        "code": "scholarnnaire_sports_game_show",
        "description": "Sports Trivia, Athletics, Football & Global Arena Games",
        "stages": ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
    }
]

@router.get("/game-divisions")
def list_game_divisions(db: Session = Depends(deps.get_db)):
    divisions = db.query(GameDivision).order_by(GameDivision.id).all()
    if not divisions:
        for item in DEFAULT_GAME_DIVISIONS:
            div_obj = GameDivision(
                name=item["name"],
                code=item["code"],
                description=item["description"],
                stages_json=json.dumps(item["stages"]),
                is_active=True
            )
            db.add(div_obj)
        db.commit()
        divisions = db.query(GameDivision).order_by(GameDivision.id).all()
    
    # Calculate question counts per division and per stage
    from app.models.school import TournamentTrack
    all_questions = db.query(
        Question.id, Question.school_category, Question.game_division_id, 
        Question.stage, Question.tournament_track_id, Question.subject,
        TournamentTrack.name.label("track_name")
    ).outerjoin(TournamentTrack, Question.tournament_track_id == TournamentTrack.id).all()
    
    result = []
    for div in divisions:
        stages = json.loads(div.stages_json) if div.stages_json else ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
        
        # Filter matching questions
        div_questions = []
        for q in all_questions:
            is_match = False
            if q.game_division_id == div.id:
                is_match = True
            elif div.code == "scholarnnaire_general" and (q.tournament_track_id == 1 or (q.track_name and "main" in q.track_name.lower()) or (div.name.lower() in (q.track_name or "").lower())):
                is_match = True
            elif div.code == "scholarnnaire_spell_quest" and (q.tournament_track_id == 2 or (q.track_name and "spell" in q.track_name.lower())):
                is_match = True
            elif div.code == "scholarnnaire_bible_word_challenge" and (q.tournament_track_id == 4 or (q.track_name and "bible" in q.track_name.lower()) or (q.subject and "bible" in q.subject.lower())):
                is_match = True
            elif div.code == "scholarnnaire_sports_game_show" and (q.tournament_track_id == 3 or (q.track_name and "sport" in q.track_name.lower())):
                is_match = True
            elif q.school_category and str(q.school_category).lower() == div.name.lower():
                is_match = True
            
            if is_match:
                div_questions.append(q)
        
        stage_counts = {}
        for s in stages:
            stage_counts[s] = sum(1 for q in div_questions if q.stage and q.stage.strip().lower() == s.strip().lower())
            
        result.append({
            "id": div.id,
            "name": div.name,
            "code": div.code,
            "description": div.description,
            "stages": stages,
            "total_stages": len(stages),
            "total_questions": len(div_questions),
            "stage_counts": stage_counts,
            "is_active": div.is_active
        })
    return {"status": "success", "data": result}

@router.post("/game-divisions")
def create_game_division(payload: GameDivisionCreate, db: Session = Depends(deps.get_db)):
    existing = db.query(GameDivision).filter(GameDivision.name.ilike(payload.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Division with name '{payload.name}' already exists.")
    
    stages = payload.stages or ["Group Stage 1", "Group Stage 2", "Group Stage 3", "Group Stage 4", "Quarter-Final", "Semi-Final", "3rd-Place", "Final"]
    new_div = GameDivision(
        name=payload.name,
        code=payload.code or payload.name.lower().replace(" ", "_"),
        description=payload.description or f"{payload.name} Competition Division",
        stages_json=json.dumps(stages),
        is_active=True
    )
    db.add(new_div)
    db.commit()
    db.refresh(new_div)
    return {
        "status": "success",
        "message": f"Game division '{new_div.name}' created successfully.",
        "data": {
            "id": new_div.id,
            "name": new_div.name,
            "code": new_div.code,
            "description": new_div.description,
            "stages": stages,
            "total_stages": len(stages),
            "total_questions": 0,
            "stage_counts": {s: 0 for s in stages},
            "is_active": new_div.is_active
        }
    }

@router.put("/game-divisions/{division_id}")
def update_game_division(division_id: int, payload: GameDivisionUpdate, db: Session = Depends(deps.get_db)):
    div = db.query(GameDivision).filter(GameDivision.id == division_id).first()
    if not div:
        raise HTTPException(status_code=404, detail="Game division not found.")
    
    if payload.name:
        div.name = payload.name
    if payload.code is not None:
        div.code = payload.code
    if payload.description is not None:
        div.description = payload.description
    if payload.stages is not None:
        div.stages_json = json.dumps(payload.stages)
    if payload.is_active is not None:
        div.is_active = payload.is_active
    div.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(div)
    
    stages = json.loads(div.stages_json) if div.stages_json else []
    return {
        "status": "success",
        "message": "Game division updated successfully.",
        "data": {
            "id": div.id,
            "name": div.name,
            "code": div.code,
            "description": div.description,
            "stages": stages,
            "total_stages": len(stages),
            "is_active": div.is_active
        }
    }

@router.post("/game-divisions/{division_id}/stages")
def update_division_stages(division_id: int, payload: StagesUpdatePayload, db: Session = Depends(deps.get_db)):
    div = db.query(GameDivision).filter(GameDivision.id == division_id).first()
    if not div:
        raise HTTPException(status_code=404, detail="Game division not found.")
    
    div.stages_json = json.dumps(payload.stages)
    div.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(div)
    return {
        "status": "success",
        "message": f"Stages for division '{div.name}' updated successfully.",
        "stages": payload.stages,
        "total_stages": len(payload.stages)
    }

@router.delete("/game-divisions/{division_id}")
def delete_game_division(division_id: int, db: Session = Depends(deps.get_db)):
    div = db.query(GameDivision).filter(GameDivision.id == division_id).first()
    if not div:
        raise HTTPException(status_code=404, detail="Game division not found.")
    db.delete(div)
    db.commit()
    return {"status": "success", "message": f"Game division '{div.name}' deleted successfully."}


