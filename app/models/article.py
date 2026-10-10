from sqlalchemy import Column, Integer, String, Text, DateTime
import datetime
from app.core.database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True, nullable=False)
    subject = Column(String(255), index=True, nullable=False)
    content = Column(Text, nullable=False)
    difficulty = Column(String(255), nullable=True) # E.g., Primary, Secondary
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
