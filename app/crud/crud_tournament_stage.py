from sqlalchemy.orm import Session
from app.models.school import TournamentStage, TournamentMatch, MatchParticipant, Team
from app.schemas.tournament import TournamentStageCreate, TournamentStageUpdate
import random

def create_stage(db: Session, tournament_id: int, stage: TournamentStageCreate):
    db_stage = TournamentStage(**stage.dict(), tournament_id=tournament_id)
    db.add(db_stage)
    db.commit()
    db.refresh(db_stage)
    return db_stage

def get_stages_by_tournament(db: Session, tournament_id: int):
    return db.query(TournamentStage).filter(TournamentStage.tournament_id == tournament_id).order_by(TournamentStage.stage_order).all()

def update_stage(db: Session, stage_id: int, stage_update: TournamentStageUpdate):
    db_stage = db.query(TournamentStage).filter(TournamentStage.id == stage_id).first()
    if not db_stage:
        return None
    for key, value in stage_update.dict(exclude_unset=True).items():
        setattr(db_stage, key, value)
    db.commit()
    db.refresh(db_stage)
    return db_stage

def delete_stage(db: Session, stage_id: int):
    db_stage = db.query(TournamentStage).filter(TournamentStage.id == stage_id).first()
    if db_stage:
        db.delete(db_stage)
        db.commit()
        return True
    return False

def generate_matches_for_stage(db: Session, stage_id: int):
    stage = db.query(TournamentStage).filter(TournamentStage.id == stage_id).first()
    if not stage:
        raise ValueError("Stage not found")
        
    # Find the previous stage to get qualified teams
    previous_stage = db.query(TournamentStage).filter(
        TournamentStage.tournament_id == stage.tournament_id,
        TournamentStage.stage_order < stage.stage_order
    ).order_by(TournamentStage.stage_order.desc()).first()

    qualified_teams = []
    if previous_stage:
        # Get teams that qualified from previous stage
        participants = db.query(MatchParticipant).join(TournamentMatch).filter(
            TournamentMatch.tournament_stage_id == previous_stage.id,
            MatchParticipant.is_qualified == True
        ).all()
        qualified_teams = [p.team for p in participants]
    else:
        # If this is the first stage, get all teams enrolled in the tournament
        qualified_teams = db.query(Team).filter(Team.tournament_id == stage.tournament_id).all()

    if not qualified_teams:
        raise ValueError("No qualified teams found for this stage.")
        
    # If this is the first stage, ensure the number of enrolled teams matches the tournament's max_schools
    if not previous_stage:
        expected_teams = stage.tournament.max_schools
        if len(qualified_teams) < expected_teams:
            raise ValueError(f"Cannot start competition. Expected {expected_teams} teams, but only {len(qualified_teams)} are enrolled.")

    # Auto group randomly
    random.shuffle(qualified_teams)
    
    # Delete existing matches for this stage if any
    existing_matches = db.query(TournamentMatch).filter(TournamentMatch.tournament_stage_id == stage.id).all()
    for m in existing_matches:
        db.delete(m)

    format = stage.match_format.lower()
    matches = []
    
    if format == "knockout":
        # Group into pairs
        for i in range(0, len(qualified_teams), 2):
            match = TournamentMatch(tournament_stage_id=stage.id, name=f"Match {(i//2)+1}")
            db.add(match)
            db.flush() # get match.id
            
            p1 = MatchParticipant(match_id=match.id, team_id=qualified_teams[i].id)
            db.add(p1)
            
            if i+1 < len(qualified_teams):
                p2 = MatchParticipant(match_id=match.id, team_id=qualified_teams[i+1].id)
                db.add(p2)
                
            matches.append(match)
            
    elif format == "group":
        # Group into pools of 4
        group_size = 4
        for i in range(0, len(qualified_teams), group_size):
            match = TournamentMatch(tournament_stage_id=stage.id, name=f"Group {chr(65 + (i//group_size))}")
            db.add(match)
            db.flush()
            
            for j in range(i, min(i + group_size, len(qualified_teams))):
                p = MatchParticipant(match_id=match.id, team_id=qualified_teams[j].id)
                db.add(p)
                
            matches.append(match)
    else:
        # Default fallback, one big group
        match = TournamentMatch(tournament_stage_id=stage.id, name="All Teams")
        db.add(match)
        db.flush()
        for t in qualified_teams:
            db.add(MatchParticipant(match_id=match.id, team_id=t.id))
        matches.append(match)

    stage.status = "active"
    db.commit()
    return matches
