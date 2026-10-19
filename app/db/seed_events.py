import json
import datetime
from sqlalchemy.orm import Session
from app.models.events import MatchEvent, EventRegistration, LiveMatch
from app.models.school import Team, School

DEFAULT_RULES = json.dumps([
    {
        "title": "1. Seven Sequential Challenges (100 Questions)",
        "desc": "Challenges 1–6 consist of 10 targeted questions each (60 questions total). Challenge 7 is a rapid 40-question MCQ gauntlet."
    },
    {
        "title": "2. Strict Per-Question Timer",
        "desc": "Standard questions allow exactly 10 seconds. Unanswered items automatically register as missed with zero downward marking."
    },
    {
        "title": "3. Four Permitted Live Helplines",
        "desc": "Phone a Scholar (60s), Ask the Crowd (60s), Browse the Net (60s), and Flip Scholarpedia (60s) available during designated phases."
    },
    {
        "title": "4. Qualification Criteria",
        "desc": "The top 2 teams in each group advance to the 32-team Quarter-Finals stage based on cumulative correct answers and match points."
    }
])

DEFAULT_PRIZES = json.dumps([
    {
        "place": "1st Place Champion",
        "award": "Grand Championship Trophy",
        "bonus": "+ Continental Scholarship Grants",
        "color": "amber"
    },
    {
        "place": "2nd Place Finalist",
        "award": "Silver Cup & Medals",
        "bonus": "+ Tournament Bursary",
        "color": "slate"
    },
    {
        "place": "3rd Place Podium",
        "award": "Bronze Distinction",
        "bonus": "+ Certified Scholar Accolade",
        "color": "bronze"
    }
])

DEFAULT_HOW_IT_WORKS = json.dumps([
    {
        "step": 1,
        "text": "Log in with your verified Team Participant ID or Captain credentials at least 15 minutes before the match slot."
    },
    {
        "step": 2,
        "text": "Enter the live arena. All 11 members sit simultaneously under server synchronized countdown clocks."
    },
    {
        "step": 3,
        "text": "Lock your answers within the 10-second timer. The Scholarnnaire Ladderboard updates team positions in real time."
    }
])

DEFAULT_SPEC_BADGES = json.dumps([
    {
        "icon": "BookOpen",
        "label": "7 Challenges",
        "sub": "(100 Questions)",
        "color": "purple"
    },
    {
        "icon": "Users",
        "label": "10 Members",
        "sub": "+ 1 Captain",
        "color": "emerald"
    },
    {
        "icon": "Clock",
        "label": "Shared Clock",
        "sub": "(Private Entry)",
        "color": "blue"
    }
])

def seed_events_if_empty(db: Session):
    count = db.query(MatchEvent).count()
    if count > 0:
        return

    events_data = [
        {
            "name": "Group Stage 2",
            "subtitle": "Round 1 of 4 • Group A & B",
            "category": "Tournament",
            "event_type": "tournament",
            "date": datetime.datetime(2026, 10, 25, 19, 0, 0),
            "time_str": "7:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": True,
            "venue": "Online (In-App Live Arena)",
            "teams_count": "32 Teams",
            "stage": "Group Stage 2 (A & B)",
            "round_info": "Round 1 of 4",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2 Hours",
            "prize": "₦5,000,000 Grand Prize & Scholarship Grants",
            "quote": "Same Scripture. Same Clock. Rebuild It. Solve It. Lock It. Wait for the Reveal.",
            "description": "The battle for qualification continues! 32 teams compete in 4 group stages. The top 2 teams from each group advance to the Quarter Finals.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "Quarter Final (QF)",
            "subtitle": "32 teams → 16 teams",
            "category": "Tournament",
            "event_type": "upcoming",
            "date": datetime.datetime(2026, 10, 28, 19, 0, 0),
            "time_str": "7:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": False,
            "venue": "Online (In-App Live Arena)",
            "teams_count": "32 teams → 16 teams",
            "stage": "Quarter Final",
            "round_info": "Knockout Round 1",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2 Hours",
            "prize": "QF Qualification Accolade & Semi-Final Ticket",
            "quote": "The Elite 32 go head-to-head. High stakes, zero margin for error.",
            "description": "32 qualified teams battle in single-elimination knockout brackets. Only 16 teams punch their ticket to the National Semi-Finals.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "Semi Final (SF)",
            "subtitle": "16 teams → 8 teams",
            "category": "Tournament",
            "event_type": "upcoming",
            "date": datetime.datetime(2026, 11, 2, 19, 0, 0),
            "time_str": "7:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": False,
            "venue": "Online (In-App Live Arena)",
            "teams_count": "16 teams → 8 teams",
            "stage": "Semi Final",
            "round_info": "Knockout Round 2",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2 Hours",
            "prize": "Finalist Distinction & Educational Grant",
            "quote": "16 Schools. 8 Final spots. The pressure reaches boiling point.",
            "description": "High-intensity head-to-head matches between regional champions. Winners advance to the National Championship Grand Final.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "3rd Place Match",
            "subtitle": "4 teams",
            "category": "Tournament",
            "event_type": "upcoming",
            "date": datetime.datetime(2026, 11, 9, 18, 0, 0),
            "time_str": "6:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": False,
            "venue": "Online (In-App Live Arena)",
            "teams_count": "4 teams",
            "stage": "3rd Place",
            "round_info": "Bronze Battle",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2 Hours",
            "prize": "Bronze Distinction & Certified Scholar Accolade",
            "quote": "Honor and glory on the line for the bronze podium finish.",
            "description": "Consolation final deciding the 3rd and 4th place national tournament standing.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "Final (Championship)",
            "subtitle": "2 teams",
            "category": "Tournament",
            "event_type": "upcoming",
            "date": datetime.datetime(2026, 11, 16, 18, 0, 0),
            "time_str": "6:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": False,
            "venue": "Main Broadcast Studio & Online Arena",
            "teams_count": "2 teams",
            "stage": "Grand Final",
            "round_info": "Championship Decider",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2.5 Hours",
            "prize": "Grand Championship Trophy + Continental Scholarship Grants",
            "quote": "Two finest schools in the nation. One ultimate champion.",
            "description": "The grand showdown of the Scholarnnaire Bible Word Wars season. Witness the crowning of the 2026 National Champion.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "All-Stars Exhibition Challenge",
            "subtitle": "Captains & Mentors Special",
            "category": "Special Events",
            "event_type": "special",
            "date": datetime.datetime(2026, 11, 20, 17, 0, 0),
            "time_str": "5:00 PM (WAT)",
            "status": "upcoming",
            "is_live": False,
            "is_featured": False,
            "venue": "Exhibition Arena",
            "teams_count": "8 Special Teams",
            "stage": "Special Exhibition",
            "round_info": "Special Showcase",
            "format": "Fastest Finger & Word Grid Gauntlet",
            "duration": "Approx. 1.5 Hours",
            "prize": "Exhibition Shield & Tech Gifts",
            "quote": "Top team captains face special challenges in a friendly showcase.",
            "description": "A celebratory exhibition clash featuring standout performers and team captains.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        },
        {
            "name": "Group Stage 1 (Qualifiers)",
            "subtitle": "Round 1 of 4 • All Divisions",
            "category": "Tournament",
            "event_type": "completed",
            "date": datetime.datetime(2026, 10, 15, 19, 0, 0),
            "time_str": "7:00 PM (WAT)",
            "status": "completed",
            "is_live": False,
            "is_featured": False,
            "venue": "Online (In-App Live Arena)",
            "teams_count": "64 Teams",
            "stage": "Group Stage 1",
            "round_info": "Completed Qualifiers",
            "format": "100 Questions / 7 Challenges",
            "duration": "Approx. 2 Hours",
            "prize": "Qualification to Group Stage 2",
            "quote": "The initial gauntlet where 64 teams were narrowed down to 32.",
            "description": "Group Stage 1 qualifiers successfully concluded with 32 teams earning spots in Group Stage 2.",
            "rules": DEFAULT_RULES,
            "prizes_detail": DEFAULT_PRIZES,
            "how_it_works": DEFAULT_HOW_IT_WORKS,
            "spec_badges": DEFAULT_SPEC_BADGES,
            "banner_url": None,
        }
    ]

    created_events = []
    for item in events_data:
        ev = MatchEvent(**item)
        db.add(ev)
        created_events.append(ev)

    db.commit()

    # Link existing registered teams to Group Stage 2
    live_event = created_events[0]
    existing_teams = db.query(Team).all()
    for t in existing_teams:
        reg = EventRegistration(
            event_id=live_event.id,
            team_id=t.id,
            status="Confirmed"
        )
        db.add(reg)

    db.commit()
    print(f"Successfully seeded {len(created_events)} match events and registered teams.")
