from sqlalchemy.orm import Session
from app.models.school import School, Team, TeamMember
from app.schemas.school import SchoolCreate, TeamCreate

def get_school_by_id(db: Session, school_id: int):
    return db.query(School).filter(School.id == school_id).first()

def get_school_by_name_and_category(db: Session, name: str, category: str):
    return db.query(School).filter(School.name == name, School.category == category).first()

def get_school_by_access_code(db: Session, access_code: str):
    return db.query(School).filter(School.access_code == access_code).first()

def get_school_activities(db: Session, school_id: int):
    # Eager load teams and match_results for the activities view
    from sqlalchemy.orm import joinedload
    return db.query(School)\
        .options(joinedload(School.teams), joinedload(School.match_results))\
        .filter(School.id == school_id)\
        .first()

def get_schools(db: Session, skip: int = 0, limit: int = 100):
    return db.query(School).offset(skip).limit(limit).all()

def count_schools(db: Session):
    return db.query(School).count()

def create_school(db: Session, school_data: dict):
    db_school = School(**school_data)
    db.add(db_school)
    db.commit()
    db.refresh(db_school)
    return db_school

def update_school(db: Session, db_school: School, update_data: dict):
    for key, value in update_data.items():
        setattr(db_school, key, value)
    db.commit()
    db.refresh(db_school)
    return db_school

def delete_school(db: Session, db_school: School):
    # Manually delete teams if cascade is not trusted, but we added cascade="all, delete-orphan"
    db.delete(db_school)
    db.commit()
    return db_school

# Teams
def get_team_by_id(db: Session, team_id: int):
    return db.query(Team).filter(Team.id == team_id).first()

def get_teams(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Team).offset(skip).limit(limit).all()

def count_teams(db: Session):
    return db.query(Team).count()

def create_team(db: Session, team: TeamCreate):
    db_team = Team(name=team.name, school_id=team.school_id)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    
    for member in team.members:
        db_member = TeamMember(
            name=member.name,
            is_captain=member.is_captain,
            is_lifeline_officer=member.is_lifeline_officer,
            team_id=db_team.id
        )
        db.add(db_member)
    db.commit()
    db.refresh(db_team)
    return db_team

def delete_team(db: Session, db_team: Team):
    db.delete(db_team)
    db.commit()
    return db_team
