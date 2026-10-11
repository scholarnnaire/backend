import os
import sys

# Ensure backend root is in python path dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import engine, Base

# Import all model modules so all models are registered on Base.metadata
import app.models.school
import app.models.question
import app.models.article
import app.models.analytics
import app.models.events
import app.models.financials
import app.models.competition
import app.models.admin

if __name__ == "__main__":
    print("Connecting to database and creating tables...")
    try:
        Base.metadata.create_all(bind=engine)
        
        # Ensure question_type exists on questions table if table was already created
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE questions ADD COLUMN question_type VARCHAR(50) NULL"))
                conn.commit()
                print("✓ Added missing column 'question_type' to questions table")
            except Exception:
                # Column likely already exists
                pass

        print("✓ All database tables migrated/created successfully!")
        print(f"Total tables ({len(Base.metadata.tables)}): {', '.join(sorted(Base.metadata.tables.keys()))}")
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)
