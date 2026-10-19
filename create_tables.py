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
    print("Connecting to database and executing migrations...")
    try:
        # 1. Create any missing tables defined in models
        Base.metadata.create_all(bind=engine)
        
        # 2. Ensure new columns on existing tables are safely added if not present
        from sqlalchemy import text
        with engine.connect() as conn:
            columns_to_ensure = [
                ("questions", "question_type", "VARCHAR(50) NULL"),
                ("questions", "question_mode", "VARCHAR(50) NULL"),
                ("questions", "stage", "VARCHAR(50) NULL DEFAULT 'Group Stage 1'"),
                ("questions", "tournament_track_id", "INT NULL"),
                ("questions", "game_division_id", "INT NULL"),
            ]
            
            for table_name, col_name, col_def in columns_to_ensure:
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                    print(f"✓ Added column '{col_name}' to '{table_name}' table")
                except Exception:
                    # Column already exists or table structure already current
                    pass

            # 3. Seed default 4 Game Divisions if table is empty
            try:
                import json
                from app.core.database import SessionLocal
                from app.models.competition import GameDivision
                from app.api.v1.endpoints.competition import DEFAULT_GAME_DIVISIONS

                db = SessionLocal()
                count = db.query(GameDivision).count()
                if count == 0:
                    for item in DEFAULT_GAME_DIVISIONS:
                        db.add(GameDivision(
                            name=item["name"],
                            code=item["code"],
                            description=item["description"],
                            stages_json=json.dumps(item["stages"]),
                            is_active=True
                        ))
                    db.commit()
                    print("✓ Seeded 4 default Scholarnnaire game divisions")
                db.close()
            except Exception as seed_err:
                print(f"Notice during division check: {seed_err}")

        print("✓ All database tables and columns migrated successfully!")
        print(f"Total tables ({len(Base.metadata.tables)}): {', '.join(sorted(Base.metadata.tables.keys()))}")
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)

