from sqlalchemy.orm import Session
from app.models.school import TeamMember, Team
from app.schemas.school import TeamMemberCreate

def get_team_members(db: Session, team_id: int):
    return db.query(TeamMember).filter(TeamMember.team_id == team_id).all()

def get_team_member(db: Session, member_id: int):
    return db.query(TeamMember).filter(TeamMember.id == member_id).first()

def create_team_member(db: Session, team_id: int, member: TeamMemberCreate):
    db_member = TeamMember(**member.model_dump(), team_id=team_id)
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

def update_team_member(db: Session, member_id: int, member_data: TeamMemberCreate):
    db_member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if not db_member:
        return None
    for key, value in member_data.model_dump().items():
        setattr(db_member, key, value)
    db.commit()
    db.refresh(db_member)
    return db_member

def delete_team_member(db: Session, member_id: int):
    db_member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if db_member:
        db.delete(db_member)
        db.commit()
        return True
    return False
