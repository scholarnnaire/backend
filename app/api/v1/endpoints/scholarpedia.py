from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_article
from app.schemas import article as article_schemas

router = APIRouter()

@router.get("/search", response_model=list[article_schemas.Article])
def search_articles(q: str = Query(..., min_length=1), db: Session = Depends(deps.get_db)):
    articles = crud_article.search_articles(db, q)
    return articles

@router.get("/subject/{subject}", response_model=list[article_schemas.Article])
def get_articles_by_subject(subject: str, skip: int = 0, limit: int = 20, db: Session = Depends(deps.get_db)):
    return crud_article.get_articles_by_subject(db, subject, skip=skip, limit=limit)

@router.get("/{article_id}", response_model=article_schemas.Article)
def get_article(article_id: int, db: Session = Depends(deps.get_db)):
    article = crud_article.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("/", response_model=article_schemas.Article)
def create_article(article: article_schemas.ArticleCreate, db: Session = Depends(deps.get_db)):
    return crud_article.create_article(db, article)
