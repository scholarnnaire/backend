from sqlalchemy.orm import Session
from app.models.question import Question
from app.schemas.question import QuestionCreate

def get_questions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Question).offset(skip).limit(limit).all()

def create_question(db: Session, question: QuestionCreate):
    db_question = Question(**question.model_dump())
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

def create_bulk_questions(db: Session, questions: list[QuestionCreate]):
    db_questions = [Question(**q.model_dump()) for q in questions]
    db.add_all(db_questions)
    db.commit()
    for db_q in db_questions:
        db.refresh(db_q)
    return db_questions

def get_question_by_id(db: Session, question_id: int):
    return db.query(Question).filter(Question.id == question_id).first()

def update_question(db: Session, db_question: Question, update_data: dict):
    for key, value in update_data.items():
        setattr(db_question, key, value)
    db.commit()
    db.refresh(db_question)
    return db_question

def delete_question(db: Session, db_question: Question):
    db.delete(db_question)
    db.commit()
    return db_question
