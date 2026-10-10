from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.analytics import MatchResult
from app.models.school import School

def count_matches(db: Session):
    return db.query(MatchResult).count()

def get_school_match_results(db: Session, school_id: int):
    return db.query(MatchResult).filter(MatchResult.school_id == school_id).all()

def get_leaderboard(db: Session):
    return db.query(
        School.name, 
        func.max(MatchResult.final_rung).label('max_rung'),
        func.avg(MatchResult.average_response_time).label('avg_time')
    ).join(School).group_by(School.name).order_by(func.max(MatchResult.final_rung).desc(), func.avg(MatchResult.average_response_time).asc()).all()
