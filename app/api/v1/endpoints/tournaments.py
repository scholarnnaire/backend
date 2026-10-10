from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.school import TournamentTrack, Tournament
from app.schemas.tournament import (
    TournamentTrack as TournamentTrackSchema, TournamentTrackCreate, TournamentTrackUpdate,
    Tournament as TournamentSchema, TournamentCreate, TournamentUpdate
)

router = APIRouter()

@router.get("/tracks", response_model=List[TournamentTrackSchema])
def get_tournament_tracks(db: Session = Depends(get_db)):
    """
    Retrieve all tournament tracks.
    """
    tracks = db.query(TournamentTrack).all()
    return tracks

@router.post("/tracks", response_model=TournamentTrackSchema)
def create_tournament_track(track_in: TournamentTrackCreate, db: Session = Depends(get_db)):
    """
    Create a new tournament track.
    """
    db_track = db.query(TournamentTrack).filter(TournamentTrack.name == track_in.name).first()
    if db_track:
        raise HTTPException(status_code=400, detail="Track with this name already exists")
    
    new_track = TournamentTrack(**track_in.dict())
    db.add(new_track)
    db.commit()
    db.refresh(new_track)
    return new_track

@router.put("/tracks/{track_id}", response_model=TournamentTrackSchema)
def update_tournament_track(track_id: int, track_in: TournamentTrackUpdate, db: Session = Depends(get_db)):
    """
    Update a tournament track.
    """
    db_track = db.query(TournamentTrack).filter(TournamentTrack.id == track_id).first()
    if not db_track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    update_data = track_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_track, key, value)
        
    db.commit()
    db.refresh(db_track)
    return db_track

@router.delete("/tracks/{track_id}")
def delete_tournament_track(track_id: int, db: Session = Depends(get_db)):
    """
    Delete a tournament track.
    """
    db_track = db.query(TournamentTrack).filter(TournamentTrack.id == track_id).first()
    if not db_track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    if len(db_track.teams) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete track because it has assigned teams")

    db.delete(db_track)
    db.commit()
    return {"message": "Track deleted successfully"}

@router.get("/", response_model=List[TournamentSchema])
def get_tournaments(db: Session = Depends(get_db)):
    """
    Retrieve all tournaments.
    """
    tournaments = db.query(Tournament).all()
    # Attach enrolled school count (teams relationship is already loaded)
    result = []
    for t in tournaments:
        obj = TournamentSchema.model_validate(t)
        obj.enrolled_count = len(t.teams)
        result.append(obj)
    return result

@router.post("/", response_model=TournamentSchema)
def create_tournament(tournament_in: TournamentCreate, db: Session = Depends(get_db)):
    """
    Create a new tournament.
    """
    db_tournament = db.query(Tournament).filter(Tournament.name == tournament_in.name).first()
    if db_tournament:
        raise HTTPException(status_code=400, detail="Tournament with this name already exists")
    
    new_tournament = Tournament(**tournament_in.dict())
    db.add(new_tournament)
    db.commit()
    db.refresh(new_tournament)
    return new_tournament

@router.put("/{tournament_id}", response_model=TournamentSchema)
def update_tournament(tournament_id: int, tournament_in: TournamentUpdate, db: Session = Depends(get_db)):
    """
    Update a tournament.
    """
    db_tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not db_tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    update_data = tournament_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tournament, key, value)
        
    db.commit()
    db.refresh(db_tournament)
    return db_tournament

@router.delete("/{tournament_id}")
def delete_tournament(tournament_id: int, db: Session = Depends(get_db)):
    """
    Delete a tournament.
    """
    db_tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not db_tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    if len(db_tournament.teams) > 0:
        raise HTTPException(status_code=400, detail="Cannot delete tournament because it has assigned teams")

    db.delete(db_tournament)
    db.commit()
    return {"message": "Tournament deleted successfully"}

@router.get("/{tournament_id}/teams")
def get_tournament_teams(tournament_id: int, db: Session = Depends(get_db)):
    """
    Get all teams enrolled in a specific tournament, along with their selected members.
    """
    db_tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not db_tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
        
    teams_data = []
    for team in db_tournament.teams:
        school = team.school
        selected_members = [m for m in team.members if m.is_selected]
        teams_data.append({
            "team_id": team.id,
            "team_name": team.name,
            "school_id": school.id if school else None,
            "school_name": school.name if school else "Unknown School",
            "state": school.state if school else "Unknown",
            "roster_finalized": team.roster_finalized,
            "selected_members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "role": m.role,
                    "subject": m.subject,
                    "status": m.status
                }
                for m in selected_members
            ]
        })
        
    return teams_data

@router.get("/bracket/active")
def get_active_tournament_bracket(db: Session = Depends(get_db)):
    """
    Returns bracket data for the first active tournament or most relevant tournament.
    """
    active_t = db.query(Tournament).filter(Tournament.status == "active").first()
    if not active_t:
        active_t = db.query(Tournament).order_by(Tournament.id.desc()).first()
    if not active_t:
        raise HTTPException(status_code=404, detail="No tournaments found")
    return format_tournament_bracket(active_t, db)

@router.get("/{tournament_id}/bracket")
def get_tournament_bracket(tournament_id: int, db: Session = Depends(get_db)):
    """
    Returns full tournament stages, matches, and participant bracket tree.
    """
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return format_tournament_bracket(tournament, db)

def format_tournament_bracket(tournament: Tournament, db: Session):
    stages_data = []
    sorted_stages = sorted(tournament.stages, key=lambda s: s.stage_order)
    
    for stage in sorted_stages:
        matches_data = []
        for match in stage.matches:
            participants_data = []
            for p in match.participants:
                team = p.team
                school = team.school if team else None
                participants_data.append({
                    "id": p.id,
                    "team_id": p.team_id,
                    "team_name": team.name if team else "TBD",
                    "school_id": school.id if school else None,
                    "school_name": school.name if school else "TBD",
                    "school_state": school.state if school else "",
                    "logo_url": school.logo_url if school else None,
                    "score": float(p.score or 0.0),
                    "is_qualified": p.is_qualified
                })
            
            matches_data.append({
                "id": match.id,
                "name": match.name,
                "status": match.status,
                "match_date": match.match_date.strftime("%b %d, %Y - %I:%M %p") if match.match_date else None,
                "participants": participants_data
            })
            
        stages_data.append({
            "id": stage.id,
            "name": stage.name,
            "order": stage.stage_order,
            "format": stage.match_format,
            "status": stage.status,
            "matches": matches_data
        })
        
    enrolled_teams = [
        {
            "id": team.id,
            "name": team.name,
            "school_id": team.school_id,
            "school_name": team.school.name if team.school else "TBD",
            "state": team.school.state if team.school else "",
            "logo_url": team.school.logo_url if team.school else None
        }
        for team in tournament.teams
    ]
    
    return {
        "tournament_id": tournament.id,
        "name": tournament.name,
        "description": tournament.description,
        "status": tournament.status,
        "track_name": tournament.track.name if tournament.track else "National",
        "entry_fee": tournament.entry_fee or ("Free" if tournament.is_free else "₦1,000,000"),
        "max_schools": tournament.max_schools,
        "season": "Season 2026/2027",
        "stages": stages_data,
        "teams": enrolled_teams
    }
