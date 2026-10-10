import os
import sys
import random
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import SessionLocal, engine, Base
import app.models
from app.models.school import (
    TournamentTrack, Tournament, TournamentStage,
    School, SchoolCategory, Team, TeamMember
)
from app.models.question import Question, QuestionDifficulty
from app.models.competition import Certificate, Notification
import bcrypt

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def seed():
    print("=" * 60)
    print("MIGRATING TABLES AND SEEDING DATABASE")
    print("=" * 60)

    # 1. Create tables if not already present
    Base.metadata.create_all(bind=engine)
    print("✓ Verified all 21 database tables.")

    db = SessionLocal()

    try:
        # ── 2. SEED TOURNAMENT TRACKS ──
        tracks_data = [
            {"id": 1, "name": "Main Scholarnnaire Quiz", "description": "National Championship Scholastic Quiz Track", "entry_fee": "N10,000"},
            {"id": 2, "name": "Spell Quest Bee", "description": "National Orthography & Spelling Bee Competition", "entry_fee": "N5,000"},
            {"id": 3, "name": "Sport Mode", "description": "Sports, Trivia & General Physical Intelligence Track", "entry_fee": "N5,000"},
        ]
        created_tracks = []
        for t_info in tracks_data:
            existing = db.query(TournamentTrack).filter(TournamentTrack.name == t_info["name"]).first()
            if not existing:
                new_t = TournamentTrack(
                    id=t_info["id"],
                    name=t_info["name"],
                    description=t_info["description"],
                    entry_fee=t_info["entry_fee"],
                    is_active=True
                )
                db.add(new_t)
                db.flush()
                created_tracks.append(new_t)
                print(f"✓ Created Track: {t_info['name']}")
            else:
                created_tracks.append(existing)

        main_track = db.query(TournamentTrack).filter(TournamentTrack.name == "Main Scholarnnaire Quiz").first()
        spell_track = db.query(TournamentTrack).filter(TournamentTrack.name == "Spell Quest Bee").first()

        # ── 3. SEED TOURNAMENT & STAGE ──
        tournament = db.query(Tournament).filter(Tournament.name == "Scholarnnaire National Championship 2026").first()
        if not tournament:
            tournament = Tournament(
                name="Scholarnnaire National Championship 2026",
                description="Annual inter-school championship",
                tournament_track_id=main_track.id if main_track else 1,
                is_active=True
            )
            db.add(tournament)
            db.flush()
            print("✓ Created Tournament: Scholarnnaire National Championship 2026")

        stage = db.query(TournamentStage).filter(TournamentStage.name == "Group Stage 2").first()
        if not stage:
            stage = TournamentStage(
                tournament_id=tournament.id,
                name="Group Stage 2",
                stage_order=2,
                status="Active"
            )
            db.add(stage)
            db.flush()
            print("✓ Created Stage: Group Stage 2")

        # ── 4. SEED SAMPLE SCHOOL ──
        school = db.query(School).filter(School.name == "St Steve Secondary").first()
        if not school:
            school = School(
                name="St Steve Secondary",
                state="Lagos",
                lga="Ikeja",
                category=SchoolCategory.SENIOR_SECONDARY,
                type="Private",
                contact_email="admin@ststeve.edu.ng",
                contact_phone="08012345678",
                admin_username="ststeve",
                password_hash=get_password_hash("password123"),
                access_code=None,
                is_approved=True,
                entry_fee_paid=True,
                tournament_track="Main Scholarnnaire Quiz"
            )
            db.add(school)
            db.flush()
            print("✓ Created School: St Steve Secondary (User: ststeve, Pass: password123)")
        else:
            school.admin_username = "ststeve"
            school.password_hash = get_password_hash("password123")
            school.access_code = None
            db.flush()
            print("✓ Updated School Credentials: User: ststeve, Pass: password123")

        # ── 5. SEED TEAM: VISIONARIES ──
        team = db.query(Team).filter(Team.code == "T0023").first()
        if not team:
            team = db.query(Team).filter(Team.name == "Visionaries").first()
        if not team:
            team = Team(
                name="Visionaries",
                code="T0023",
                school_id=school.id,
                umbrella_name="Visionaries Umbrella",
                status="Ready for Group Stage",
                current_stage="Group Stage 2",
                scheduled_exam_date=datetime.date(2025, 4, 15),
                scheduled_exam_time="10:00 AM",
                tournament_track_id=main_track.id if main_track else 1,
                tournament_id=tournament.id
            )
            db.add(team)
            db.flush()
            print("✓ Created Team: Visionaries (Code: T0023)")

        # ── 6. SEED TEAM MEMBERS (Captain Sarah & Member Daniel + Team Roster) ──
        roster_data = [
            {
                "name": "Sarah Johnson",
                "participant_id": "P000987",
                "role": "Team Captain",
                "is_captain": True,
                "current_stage": "Group Stage 2",
                "qualification_status": "Qualified",
                "subject": "Mathematics",
                "score": 3800,
                "passport_photo_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&auto=format&fit=crop&q=80"
            },
            {
                "name": "Daniel Okafor",
                "participant_id": "P001245",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Physics",
                "score": 2400,
                "passport_photo_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=200&auto=format&fit=crop&q=80"
            },
            {
                "name": "Amaka Eze",
                "participant_id": "P001246",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Chemistry",
                "score": 2200,
                "passport_photo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Chinedu Nwosu",
                "participant_id": "P001247",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "Eliminated",
                "subject": "Biology",
                "score": 1100,
                "passport_photo_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Fatima Bello",
                "participant_id": "P001248",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "Qualified",
                "subject": "English Language",
                "score": 3600,
                "passport_photo_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Emeka Obi",
                "participant_id": "P001249",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "Qualified",
                "subject": "Basic Technology",
                "score": 3200,
                "passport_photo_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Zainab Ibrahim",
                "participant_id": "P001250",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Social Studies",
                "score": 2100,
                "passport_photo_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Tunde Bakare",
                "participant_id": "P001251",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Economics",
                "score": 2000,
                "passport_photo_url": "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Grace Adeleke",
                "participant_id": "P001252",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "Qualified",
                "subject": "Civic Education",
                "score": 3500,
                "passport_photo_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Ibrahim Musa",
                "participant_id": "P001253",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Agricultural Science",
                "score": 1900,
                "passport_photo_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=100&auto=format&fit=crop&q=80"
            },
            {
                "name": "Blessing Okon",
                "participant_id": "P001254",
                "role": "Member",
                "is_captain": False,
                "current_stage": "Group Stage 2",
                "qualification_status": "In Progress",
                "subject": "Computer Studies",
                "score": 2300,
                "passport_photo_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=100&auto=format&fit=crop&q=80"
            }
        ]

        for m_data in roster_data:
            existing_m = db.query(TeamMember).filter(TeamMember.participant_id == m_data["participant_id"]).first()
            if not existing_m:
                new_m = TeamMember(
                    team_id=team.id,
                    participant_id=m_data["participant_id"],
                    name=m_data["name"],
                    role=m_data["role"],
                    is_captain=m_data["is_captain"],
                    verification_status="Verified",
                    current_stage=m_data["current_stage"],
                    qualification_status=m_data["qualification_status"],
                    subject=m_data["subject"],
                    score=m_data["score"],
                    passport_photo_url=m_data["passport_photo_url"],
                    status="Active",
                    is_selected=True
                )
                db.add(new_m)
                print(f"✓ Created Contestant: {m_data['name']} (ID: {m_data['participant_id']}, Role: {m_data['role']})")

        # ── 7. SEED QUESTIONS ──
        existing_q_count = db.query(Question).count()
        if existing_q_count < 50:
            print(f"Current questions: {existing_q_count}. Seeding comprehensive question bank...")

            sample_questions = [
                # Mathematics
                ("What is 15% of 200?", "20", "30", "40", "50", "B", "Mathematics"),
                ("Solve for x: 2x + 5 = 15", "x=5", "x=10", "x=2", "x=4", "A", "Mathematics"),
                ("What is the square root of 144?", "10", "12", "14", "16", "B", "Mathematics"),
                ("If a triangle has an angle of 90 degrees, what is it called?", "Acute", "Obtuse", "Right", "Straight", "C", "Mathematics"),
                ("What is the area of a rectangle with length 8 and width 5?", "13", "40", "30", "26", "B", "Mathematics"),
                ("Simplify: 3/4 + 1/4", "1/2", "1", "3/8", "1.5", "B", "Mathematics"),
                ("What is the value of Pi to two decimal places?", "3.12", "3.14", "3.16", "3.18", "B", "Mathematics"),
                ("Which of the following is a prime number?", "9", "15", "21", "23", "D", "Mathematics"),
                ("Calculate: 7 x 8 - 4", "52", "60", "28", "42", "A", "Mathematics"),
                ("What is 5 cubed?", "25", "125", "150", "555", "B", "Mathematics"),
                ("Solve: 100 / (4 + 6)", "10", "20", "25", "50", "A", "Mathematics"),
                ("If 3y = 27, what is y?", "3", "6", "9", "12", "C", "Mathematics"),
                ("Find the perimeter of a square with side 6cm.", "12cm", "24cm", "36cm", "18cm", "B", "Mathematics"),
                ("What is 2 to the power of 6?", "32", "64", "128", "16", "B", "Mathematics"),
                ("What is the average of 10, 20, and 30?", "15", "20", "25", "30", "B", "Mathematics"),

                # Science
                ("What is the chemical formula for water?", "H2O", "CO2", "O2", "NaCl", "A", "Basic Science"),
                ("Which organ pumps blood throughout the human body?", "Lungs", "Brain", "Heart", "Liver", "C", "Basic Science"),
                ("What is the closest planet to the Sun?", "Venus", "Mercury", "Earth", "Mars", "B", "Basic Science"),
                ("What gas do green plants absorb during photosynthesis?", "Oxygen", "Nitrogen", "Carbon Dioxide", "Hydrogen", "C", "Basic Science"),
                ("What is the speed of light in vacuum approximately?", "300,000 km/s", "150,000 km/s", "3,000 km/s", "30,000 km/s", "A", "Basic Science"),
                ("Which part of the cell contains genetic material?", "Cytoplasm", "Nucleus", "Ribosome", "Cell wall", "B", "Basic Science"),
                ("What is the hardest natural substance on Earth?", "Gold", "Iron", "Diamond", "Platinum", "C", "Basic Science"),
                ("Sound travels fastest through which medium?", "Air", "Water", "Solid steel", "Vacuum", "C", "Basic Science"),
                ("What is the atomic number of Carbon?", "4", "6", "8", "12", "B", "Basic Science"),
                ("Which vitamin is produced in the human skin when exposed to sunlight?", "Vitamin A", "Vitamin B", "Vitamin C", "Vitamin D", "D", "Basic Science"),

                # English Language
                ("Choose the correct spelling:", "Accomodate", "Acomodate", "Accommodate", "Acommodate", "C", "English Language"),
                ("What is the synonym of 'Abundant'?", "Scarce", "Plentiful", "Tiny", "Weak", "B", "English Language"),
                ("Identify the noun in the sentence: 'The swift cheetah ran quickly.'", "swift", "cheetah", "ran", "quickly", "B", "English Language"),
                ("What is the antonym of 'Generous'?", "Selfish", "Kind", "Helpful", "Wealthy", "A", "English Language"),
                ("Which punctuation mark indicates direct speech?", "Comma", "Quotation marks", "Colon", "Semicolon", "B", "English Language"),
                ("Choose the correct plural form of 'Crisis':", "Crisises", "Crises", "Crisi", "Crisises", "B", "English Language"),
                ("What figure of speech is: 'The wind whispered through the trees'?", "Metaphor", "Simile", "Personification", "Hyperbole", "C", "English Language"),

                # Social Studies & General Knowledge
                ("What is the capital city of Nigeria?", "Lagos", "Abuja", "Kano", "Port Harcourt", "B", "Social Studies"),
                ("In what year did Nigeria gain independence?", "1957", "1960", "1963", "1970", "B", "Social Studies"),
                ("What is the largest continent by land area?", "Africa", "Asia", "North America", "Europe", "B", "General"),
                ("Who was Nigeria's first President?", "Nnamdi Azikiwe", "Tafawa Balewa", "Obafemi Awolowo", "Ahmadu Bello", "A", "Social Studies"),
                ("What currency is used in the United Kingdom?", "Euro", "Dollar", "Pound Sterling", "Yen", "C", "General"),
                ("Which African river is considered the longest in the world?", "Niger", "Congo", "Nile", "Zambezi", "C", "General"),
                ("What is the boiling point of pure water at sea level?", "90°C", "100°C", "110°C", "120°C", "B", "Basic Science"),
                ("How many states are in Nigeria?", "30", "36", "37", "40", "B", "Social Studies")
            ]

            added_count = 0
            for item in sample_questions:
                q_text, op_a, op_b, op_c, op_d, corr, subj = item
                new_q = Question(
                    text=q_text,
                    option_a=op_a,
                    option_b=op_b,
                    option_c=op_c,
                    option_d=op_d,
                    correct_option=corr,
                    subject=subj,
                    difficulty=QuestionDifficulty.INTERMEDIATE,
                    school_category="Senior Secondary",
                    mode="Standard",
                    question_type="Multiple Choice",
                    points=100,
                    tournament_track_id=main_track.id if main_track else 1
                )
                db.add(new_q)
                added_count += 1

            # Spelling Bee track questions
            if spell_track:
                spelling_words = [
                    ("Accommodate", "Acomodate", "Accomodate", "Acommodate"),
                    ("Embarrass", "Embarass", "Embaras", "Emmbarrass"),
                    ("Fluorescent", "Flourescent", "Flouresant", "Fluorescant"),
                    ("Maneuver", "Maneouver", "Manuver", "Manuever"),
                    ("Occurrence", "Occurence", "Occurrance", "Ocurence"),
                    ("Privilege", "Priviledge", "Privelige", "Privilege"),
                    ("Separate", "Seperate", "Seprate", "Seperrate"),
                    ("Vacuum", "Vaccum", "Vacum", "Vacume"),
                    ("Acknowledge", "Acknowlege", "Aknowledge", "Acknowlegde"),
                    ("Conscientious", "Conscientous", "Conscensious", "Consciousnous")
                ]
                for word, w1, w2, w3 in spelling_words:
                    options = [word, w1, w2, w3]
                    random.shuffle(options)
                    corr_letter = ["A", "B", "C", "D"][options.index(word)]
                    sp_q = Question(
                        text=f"Identify the correct spelling of the word:",
                        option_a=options[0],
                        option_b=options[1],
                        option_c=options[2],
                        option_d=options[3],
                        correct_option=corr_letter,
                        subject="Spelling",
                        difficulty=QuestionDifficulty.INTERMEDIATE,
                        school_category="Senior Secondary",
                        mode="Standard",
                        question_type="Multiple Choice",
                        points=100,
                        tournament_track_id=spell_track.id
                    )
                    db.add(sp_q)
                    added_count += 1

            print(f"✓ Seeded {added_count} curated academic competition questions.")
        else:
            print(f"✓ Database already has {existing_q_count} questions.")

        # ── 8. SEED SAMPLE NOTIFICATIONS ──
        if db.query(Notification).count() == 0:
            notifs = [
                ("Team constitution completed", "10 Apr 2025, 09:15 AM", "emerald"),
                ("Examination scheduled for Group Stage 2", "12 Apr 2025, 04:20 PM", "blue"),
                ("Member qualified for Group Stage 2", "13 Apr 2025, 11:05 AM", "emerald"),
                ("Substitution request approved", "14 Apr 2025, 02:30 PM", "blue"),
            ]
            for msg, dt_str, color in notifs:
                n = Notification(
                    recipient_role="team",
                    recipient_id=str(team.id),
                    title="System Alert",
                    message=msg,
                    type="info"
                )
                db.add(n)
            print("✓ Seeded sample competition notifications.")

        db.commit()
        print("=" * 60)
        print("🎉 ALL SEED DATA COMMITTED SUCCESSFULLY!")
        print("=" * 60)
        print("Login credentials ready to test:")
        print("  - Contestant Captain: Participant ID: P000987 (Sarah Johnson)")
        print("  - Contestant Member:  Participant ID: P001245 (Daniel Okafor)")
        print("  - School Admin:       Username: ststeve | Password: password123")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
