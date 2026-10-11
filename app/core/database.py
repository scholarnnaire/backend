from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def ensure_schema():
    """Ensure missing columns in existing tables are safely added."""
    try:
        with engine.connect() as conn:
            columns_to_check = [
                ("questions", "tournament_track_id", "INT NULL"),
                ("questions", "question_mode", "VARCHAR(50) NULL"),
                ("questions", "question_type", "VARCHAR(50) NULL"),
                ("questions", "stage", "VARCHAR(50) DEFAULT 'Group Stage 1' NULL"),
            ]
            for table, col, col_type in columns_to_check:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
    except Exception:
        pass

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
