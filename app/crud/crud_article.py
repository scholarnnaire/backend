from sqlalchemy.orm import Session
from app.models.article import Article
from app.schemas.article import ArticleCreate

def get_article(db: Session, article_id: int):
    return db.query(Article).filter(Article.id == article_id).first()

def get_articles_by_subject(db: Session, subject: str, skip: int = 0, limit: int = 100):
    return db.query(Article).filter(Article.subject.ilike(f"%{subject}%")).offset(skip).limit(limit).all()

def search_articles(db: Session, query: str):
    return db.query(Article).filter(
        (Article.title.ilike(f"%{query}%")) | 
        (Article.subject.ilike(f"%{query}%"))
    ).all()

def create_article(db: Session, article: ArticleCreate):
    db_article = Article(**article.model_dump())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article
