import sys
import random
sys.path.insert(0, '/Users/rotimiolaosebikan/projects/php/quiz_cart/backend')
from app.core.database import SessionLocal
from app.models.school import TournamentTrack
from app.models.question import Question

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
    
    for _ in range(150):
        track = random.choice(tracks)
        subject = random.choice(subjects)
        difficulty = random.choice(difficulties)
        category = random.choice(categories)
        mode = random.choice(modes)
        q_type = random.choice(types)
        
        q = Question(
            text=f"Sample Question #{random.randint(1000, 9999)} for {track.name}",
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
    print(f"Successfully seeded {len(questions_to_add)} additional questions!")
except Exception as e:
    db.rollback()
    print("Error seeding questions:", e)
finally:
    db.close()
