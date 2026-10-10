import sys
import random
sys.path.insert(0, '/Users/rotimiolaosebikan/projects/php/quiz_cart/backend')
from app.core.database import SessionLocal
from app.models.school import TournamentTrack
from app.models.question import Question

db = SessionLocal()

try:
    # 1. Find the "Spell Quest" track
    track = db.query(TournamentTrack).filter(TournamentTrack.name.like('%Spell Quest%')).first()
    if not track:
        print("Could not find a track matching 'Spell Quest'.")
        sys.exit(1)
        
    print(f"Found Track: {track.name} (ID: {track.id})")
    
    # 2. Delete existing questions for this track
    deleted_count = db.query(Question).filter(Question.tournament_track_id == track.id).delete()
    print(f"Deleted {deleted_count} existing questions for {track.name}.")
    
    # 3. Spelling words dataset (Correct, Wrong1, Wrong2, Wrong3)
    spelling_words = [
        ("Accommodate", "Acomodate", "Accomodate", "Acommodate"),
        ("Embarrass", "Embarass", "Embaras", "Emmbarrass"),
        ("Fluorescent", "Flourescent", "Flouresant", "Fluorescant"),
        ("Maneuver", "Maneouver", "Manuver", "Manuever"),
        ("Occurrence", "Occurence", "Occurrance", "Ocurence"),
        ("Privilege", "Priviledge", "Privelige", "Privilege"),
        ("Receive", "Recieve", "Receve", "Receiv"),
        ("Rhythm", "Rythm", "Rhythym", "Rythym"),
        ("Separate", "Seperate", "Seprate", "Seperrate"),
        ("Vacuum", "Vaccum", "Vacum", "Vacume"),
        ("Acknowledge", "Acknowlege", "Aknowledge", "Acknowlegde"),
        ("Acquaintance", "Acquaintence", "Acquantance", "Aquaintance"),
        ("Apparent", "Apparant", "Aparent", "Apparrent"),
        ("Beginning", "Begining", "Beginging", "Beginning"),
        ("Believe", "Believe", "Beleive", "Beleeve"), # Need to fix this one as I duplicated Believe
        ("Colleague", "Collegue", "Coleague", "Collaegue"),
        ("Conscious", "Concious", "Consious", "Consciense"),
        ("Definitely", "Definately", "Definitly", "Defenitely"),
        ("Discipline", "Disipline", "Decipline", "Discepline"),
        ("Existence", "Existance", "Existense", "Exsistence"),
        ("Fascinate", "Fasinate", "Fascinat", "Fassinate"),
        ("Guarantee", "Gaurantee", "Garantee", "Garuntee"),
        ("Harass", "Harrass", "Harras", "Harase"),
        ("Independent", "Independant", "Indipendent", "Independent"),
        ("Judgment", "Judgement", "Jugment", "Judgmant"),
        ("Maintenance", "Maintainance", "Maintanence", "Maintenence"),
        ("Noticeable", "Noticable", "Noticible", "Noticeble"),
        ("Pronunciation", "Pronounciation", "Pronunsiation", "Prenunciation"),
        ("Questionnaire", "Questionaire", "Questionnare", "Questionnare"),
        ("Recommend", "Recomend", "Reccommend", "Reccomend"),
        ("Restaurant", "Restarant", "Restuarant", "Resaurant"),
        ("Schedule", "Shedule", "Scheduale", "Skedule"),
        ("Successfully", "Succesfully", "Successully", "Sucessfully"),
        ("Temperature", "Temparature", "Temperater", "Tempreture"),
        ("Tomorrow", "Tommorrow", "Tomorow", "Tommorow"),
        ("Unnecessary", "Unnecesary", "Unecessary", "Unneccesary"),
        ("Weird", "Wierd", "Weard", "Wierd"),
        ("Beautiful", "Beautifull", "Buetiful", "Beutiful"),
        ("Exaggerate", "Exagerate", "Exagerrate", "Exaggerat"),
        ("Immediately", "Immediatly", "Imediately", "Immedietly"),
        ("Amateur", "Amatuer", "Amature", "Ameteur"),
        ("Argument", "Arguement", "Argumant", "Arguemant"),
        ("Cemetery", "Cemetary", "Cemitery", "Cematary"),
        ("Committee", "Comittee", "Committe", "Comitee"),
        ("Entrepreneur", "Entreprenuer", "Entrapreneur", "Entrepenuer"),
        ("Foreign", "Foriegn", "Foreing", "Forien"),
        ("Intelligence", "Inteligence", "Intelligense", "Intellegence"),
        ("Knowledge", "Knowlege", "Knoledge", "Nowledge"),
        ("Leisure", "Liesure", "Lesure", "Leasure"),
        ("Library", "Libary", "Librery", "Liberary"),
        ("Misspell", "Mispell", "Mispel", "Misspel"),
        ("Necessary", "Neccessary", "Necesary", "Necessery"),
        ("Neighbor", "Nieghbor", "Neigbor", "Neighber"),
        ("Perseverance", "Perseverence", "Perserverance", "Perserverence"),
        ("Possession", "Posession", "Possesion", "Posesion"),
        ("Sergeant", "Sargeant", "Sergent", "Sargent"),
        ("Twelfth", "Twelth", "Twelft", "Twelfh"),
        ("Until", "Untill", "Entil", "Untile")
    ]
    
    # Fix the mistakes in hardcoded list
    spelling_words[14] = ("Believe", "Beleive", "Beleeve", "Baleive")
    spelling_words[23] = ("Independent", "Independant", "Indipendent", "Independance")

    # To get to 110, we'll repeat some words but change the order of options
    all_spelling_data = []
    
    # We have 58 unique words. We'll use all 58 twice with different prompt types.
    for correct, w1, w2, w3 in spelling_words:
        # Prompt Type 1
        all_spelling_data.append(("Identify the correct spelling:", correct, w1, w2, w3))
        # Prompt Type 2
        all_spelling_data.append(("Which of the following is spelled correctly?", correct, w1, w2, w3))

    categories = ["Primary", "Junior Secondary", "Senior Secondary", "Tertiary", "Corpers", "Adults / Open"]
    modes = ["Standard", "Speed", "Visual"]
    difficulties = ["Primary", "Secondary", "Tertiary"]

    questions_to_add = []
    
    # Take first 110
    for prompt, correct, w1, w2, w3 in all_spelling_data[:110]:
        opts = [correct, w1, w2, w3]
        random.shuffle(opts)
        
        correct_idx = opts.index(correct)
        correct_letter = ["A", "B", "C", "D"][correct_idx]
        
        category = random.choice(categories)
        mode = random.choice(modes)
        diff = random.choice(difficulties)
        
        q = Question(
            text=prompt,
            option_a=opts[0],
            option_b=opts[1],
            option_c=opts[2],
            option_d=opts[3],
            correct_option=correct_letter,
            subject="General", # user requested general
            difficulty=diff,
            school_category=category,
            tournament_track_id=track.id,
            question_mode=mode,
            question_type="Multiple Choice",
            is_active=True
        )
        questions_to_add.append(q)

    db.add_all(questions_to_add)
    db.commit()
    print(f"Successfully generated and seeded {len(questions_to_add)} Spelling Bee questions for {track.name}!")
    
except Exception as e:
    db.rollback()
    print("Error:", e)
finally:
    db.close()
