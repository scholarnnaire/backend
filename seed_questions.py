import os
import sys
import random
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from app.core.database import SessionLocal, ensure_schema
from app.models.school import TournamentTrack
from app.models.question import Question

ensure_schema()
db = SessionLocal()
try:
    tracks = db.query(TournamentTrack).all()
    if not tracks:
        print("No tracks found to seed questions for.")
        sys.exit(1)
    
    subjects = ["General", "Mathematics", "English Language", "Basic Science", "Social Studies", "Current Affairs"]
    difficulties = ["Primary", "Secondary", "Tertiary"]
    categories = ["Primary", "Junior Secondary", "Senior Secondary", "Tertiary", "Corpers", "Adults / Open"]
    modes = ["Standard", "Speed", "Visual"]
    types = ["Multiple Choice", "True/False", "Fill in the Blank"]
    
    questions_to_add = []
    
    for track in tracks:
        for _ in range(10): # Seed 10 questions per track
            subject = random.choice(subjects)
            difficulty = random.choice(difficulties)
            category = random.choice(categories)
            mode = random.choice(modes)
            q_type = random.choice(types)
            
            q = Question(
                text=f"Sample Question for {track.name} ({subject} - {difficulty})",
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option=random.choice(["A", "B", "C", "D"]),
                subject=subject,
                difficulty=difficulty,
                school_category=category,
                tournament_track_id=track.id,
                question_mode=mode,
                question_type=q_type,
                is_active=True
            )
            questions_to_add.append(q)
            
    db.add_all(questions_to_add)
    db.commit()
    print(f"Successfully seeded {len(questions_to_add)} questions!")
except Exception as e:
    db.rollback()
    print("Error seeding questions:", e)
finally:
    db.close()
