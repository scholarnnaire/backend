import os
import sys
import random
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from app.core.database import SessionLocal
from app.models.school import TournamentTrack
from app.models.question import Question

db = SessionLocal()

# Clear existing questions
db.query(Question).delete()
db.commit()

tracks = db.query(TournamentTrack).all()
if not tracks:
    print("No tracks found.")
    sys.exit(1)

math_qs = [
    ("What is 15% of 200?", "20", "30", "40", "50", "B"),
    ("Solve for x: 2x + 5 = 15", "x=5", "x=10", "x=2", "x=4", "A"),
    ("What is the square root of 144?", "10", "12", "14", "16", "B"),
    ("If a triangle has an angle of 90 degrees, what is it called?", "Acute", "Obtuse", "Right", "Straight", "C"),
    ("What is the area of a rectangle with length 8 and width 5?", "13", "40", "30", "26", "B"),
    ("Simplify: 3/4 + 1/4", "1/2", "1", "3/8", "1.5", "B"),
    ("What is the value of Pi to two decimal places?", "3.12", "3.14", "3.16", "3.18", "B"),
    ("Which of the following is a prime number?", "9", "15", "21", "23", "D"),
    ("Calculate: 7 x 8 - 4", "52", "60", "28", "42", "A"),
    ("What is the next number in the sequence: 2, 4, 8, 16, ...", "24", "30", "32", "64", "C"),
    ("How many degrees are in a full circle?", "180", "270", "360", "400", "C"),
    ("What is 5 cubed?", "25", "125", "150", "555", "B"),
    ("Solve: 100 / (4 + 6)", "10", "20", "25", "50", "A"),
    ("What is the perimeter of a square with side 6?", "12", "24", "36", "48", "B"),
    ("Write 0.75 as a fraction.", "1/2", "3/4", "1/4", "2/3", "B"),
    ("What is the absolute value of -15?", "1", "0", "-15", "15", "D"),
    ("If x=3 and y=4, what is x*y + 2?", "14", "12", "10", "8", "A"),
    ("What is the lowest common multiple of 4 and 6?", "10", "12", "24", "48", "B"),
    ("How many sides does a hexagon have?", "5", "6", "7", "8", "B"),
    ("What is 10 to the power of 3?", "100", "1000", "10000", "30", "B"),
    ("Convert 50% to a decimal.", "0.05", "0.5", "5.0", "50", "B"),
    ("What is the median of 3, 1, 4, 2, 5?", "2", "3", "4", "5", "B"),
    ("Find the missing number: 5, 10, __, 20", "12", "15", "16", "18", "B"),
    ("Which is greater: 1/3 or 1/4?", "1/3", "1/4", "Equal", "Cannot be determined", "A"),
    ("Calculate the volume of a cube with edge 3.", "9", "18", "27", "36", "C")
]

english_qs = [
    ("Which word is a noun?", "Quickly", "Beautiful", "Dog", "Run", "C"),
    ("Identify the verb: The cat slept all day.", "The", "Cat", "Slept", "Day", "C"),
    ("Choose the correct spelling:", "Accommodate", "Acomodate", "Accomodate", "Acommodate", "A"),
    ("What is the antonym of 'brave'?", "Cowardly", "Strong", "Fierce", "Heroic", "A"),
    ("What is a synonym for 'happy'?", "Sad", "Joyful", "Angry", "Tired", "B"),
    ("Which sentence is grammatically correct?", "She don't like it.", "She doesn't likes it.", "She doesn't like it.", "She don't likes it.", "C"),
    ("What punctuation ends a question?", "Period", "Comma", "Exclamation mark", "Question mark", "D"),
    ("Identify the adjective: The red ball bounced.", "The", "Red", "Ball", "Bounced", "B"),
    ("Complete the idiom: Break a ___", "Arm", "Leg", "Heart", "Bone", "B"),
    ("What is the plural of 'child'?", "Childs", "Children", "Childrens", "Childes", "B"),
    ("Choose the correct preposition: She is good ___ math.", "In", "At", "With", "On", "B"),
    ("Which word is an adverb?", "Slow", "Slowly", "Slowness", "Slower", "B"),
    ("Find the pronoun: He went to the store.", "Went", "To", "He", "Store", "C"),
    ("Identify the tense: I will go tomorrow.", "Past", "Present", "Future", "Continuous", "C"),
    ("What is the past tense of 'run'?", "Runned", "Ran", "Running", "Runs", "B"),
    ("Which is a compound word?", "Sunflower", "Beautiful", "Quickly", "Happiness", "A"),
    ("Choose the right word: Their going to the park. (Correct the sentence)", "There", "They're", "Theirs", "Them", "B"),
    ("What is a prefix in 'unhappy'?", "Un", "Happy", "Py", "Unh", "A"),
    ("Identify the conjunction: I want tea and cake.", "I", "Want", "Tea", "And", "D"),
    ("What is the opposite of 'increase'?", "Grow", "Expand", "Decrease", "Rise", "C"),
    ("Select the correct form: It is ___ beautiful day.", "A", "An", "The", "No article", "A"),
    ("What does 'bene' mean as a root?", "Bad", "Good", "Fast", "Slow", "B"),
    ("Which is a proper noun?", "city", "river", "London", "mountain", "C"),
    ("Choose the past participle of 'write'.", "Wrote", "Written", "Writing", "Writes", "B"),
    ("Identify the article: An apple fell.", "Apple", "Fell", "An", "None", "C")
]

science_qs = [
    ("What is the chemical symbol for water?", "WA", "H2O", "O2", "HO", "B"),
    ("Which planet is known as the Red Planet?", "Venus", "Jupiter", "Mars", "Saturn", "C"),
    ("What gas do plants absorb from the atmosphere?", "Oxygen", "Nitrogen", "Carbon Dioxide", "Hydrogen", "C"),
    ("What is the powerhouse of the cell?", "Nucleus", "Mitochondria", "Ribosome", "Cell Wall", "B"),
    ("Which force keeps us on the ground?", "Magnetism", "Friction", "Gravity", "Inertia", "C"),
    ("What is the boiling point of water in Celsius?", "50", "90", "100", "120", "C"),
    ("What part of the plant conducts photosynthesis?", "Root", "Stem", "Leaf", "Flower", "C"),
    ("What is the hardest natural substance on Earth?", "Gold", "Iron", "Diamond", "Quartz", "C"),
    ("Which organ pumps blood in the human body?", "Brain", "Lung", "Heart", "Liver", "C"),
    ("What are the three states of matter?", "Solid, Liquid, Gas", "Earth, Water, Fire", "Proton, Neutron, Electron", "Red, Blue, Green", "A"),
    ("What type of animal is a frog?", "Reptile", "Amphibian", "Mammal", "Bird", "B"),
    ("What is the largest organ of the human body?", "Liver", "Skin", "Heart", "Brain", "B"),
    ("How many bones are in the adult human body?", "150", "206", "300", "250", "B"),
    ("What is the center of an atom called?", "Electron", "Molecule", "Nucleus", "Proton", "C"),
    ("Which element has the symbol O?", "Osmium", "Oxygen", "Ozone", "Opal", "B"),
    ("What process turns liquid water into vapor?", "Condensation", "Freezing", "Melting", "Evaporation", "D"),
    ("What travels faster: light or sound?", "Light", "Sound", "They travel at the same speed", "Depends on the medium", "A"),
    ("What is the primary source of energy for Earth?", "The Moon", "The Sun", "Geothermal", "Wind", "B"),
    ("Which blood cells fight infection?", "Red blood cells", "White blood cells", "Platelets", "Plasma", "B"),
    ("What is a baby kangaroo called?", "Calf", "Pup", "Joey", "Cub", "C"),
    ("What part of the eye controls light entering?", "Retina", "Lens", "Cornea", "Pupil", "D"),
    ("What is the main gas in Earth's atmosphere?", "Oxygen", "Nitrogen", "Carbon Dioxide", "Argon", "B"),
    ("Which system digests food?", "Respiratory", "Nervous", "Digestive", "Circulatory", "C"),
    ("What instrument measures temperature?", "Barometer", "Thermometer", "Altimeter", "Hygrometer", "B"),
    ("What kind of energy does a moving object have?", "Potential", "Kinetic", "Thermal", "Chemical", "B")
]

social_qs = [
    ("What is the capital of Nigeria?", "Lagos", "Abuja", "Kano", "Port Harcourt", "B"),
    ("On what continent is Egypt located?", "Asia", "Europe", "Africa", "South America", "C"),
    ("Who was the first president of the United States?", "Abraham Lincoln", "George Washington", "Thomas Jefferson", "John Adams", "B"),
    ("What ocean lies on the east coast of the United States?", "Pacific", "Atlantic", "Indian", "Arctic", "B"),
    ("Which of these is a fundamental human right?", "Right to drive", "Right to education", "Right to own a pet", "Right to play games", "B"),
    ("What is a democracy?", "Rule by one person", "Rule by a few", "Government by the people", "No government", "C"),
    ("Which country has the largest population in the world?", "USA", "India", "China", "Russia", "C"),
    ("What is the longest river in the world?", "Amazon", "Nile", "Yangtze", "Mississippi", "B"),
    ("Which historical figure led the civil rights movement in the USA?", "Malcolm X", "Martin Luther King Jr.", "Rosa Parks", "W.E.B. Du Bois", "B"),
    ("What is the currency of Japan?", "Yuan", "Won", "Yen", "Ringgit", "C"),
    ("Who wrote the play Romeo and Juliet?", "Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain", "B"),
    ("What is the primary language spoken in Brazil?", "Spanish", "English", "Portuguese", "French", "C"),
    ("Which ancient civilization built the pyramids?", "Romans", "Greeks", "Mayans", "Egyptians", "D"),
    ("What is the study of maps called?", "Geology", "Cartography", "Topology", "Geography", "B"),
    ("Who is the head of state in the UK?", "Prime Minister", "President", "Monarch", "Chancellor", "C"),
    ("In which country would you find the Eiffel Tower?", "Italy", "Germany", "Spain", "France", "D"),
    ("What is a physical map?", "Shows borders", "Shows terrain features like mountains", "Shows population", "Shows climate", "B"),
    ("Who was Nelson Mandela?", "A scientist", "An anti-apartheid revolutionary", "A musician", "A sports star", "B"),
    ("What does the UN stand for?", "United Nations", "Universal Network", "United Nomads", "Union of Nations", "A"),
    ("What is the capital of Australia?", "Sydney", "Melbourne", "Canberra", "Perth", "C"),
    ("Which war was fought between the North and South regions in the USA?", "WWI", "WWII", "Civil War", "Revolutionary War", "C"),
    ("What is the largest desert in the world?", "Gobi", "Sahara", "Kalahari", "Atacama", "B"),
    ("Who discovered gravity after an apple fell on his head?", "Einstein", "Galileo", "Newton", "Tesla", "C"),
    ("Which document starts with 'We the People'?", "Declaration of Independence", "Magna Carta", "US Constitution", "Bill of Rights", "C"),
    ("What is the economic system based on private ownership?", "Socialism", "Communism", "Capitalism", "Feudalism", "C")
]

current_qs = [
    ("Who is the current President of the USA (as of 2024)?", "Donald Trump", "Joe Biden", "Barack Obama", "George Bush", "B"),
    ("Which country hosted the 2022 FIFA World Cup?", "Brazil", "Russia", "Qatar", "France", "C"),
    ("What major global event started in late 2019?", "World War III", "COVID-19 Pandemic", "Global Financial Crisis", "Y2K", "B"),
    ("Who is the CEO of Tesla?", "Jeff Bezos", "Bill Gates", "Elon Musk", "Mark Zuckerberg", "C"),
    ("Which country invaded Ukraine in 2022?", "Belarus", "Russia", "Poland", "Germany", "B"),
    ("What social media platform was formerly known as Twitter?", "Facebook", "Instagram", "X", "Threads", "C"),
    ("Which film won the Academy Award for Best Picture in 2023?", "Everything Everywhere All at Once", "Avatar", "Top Gun", "Dune", "A"),
    ("Who won the 2023 Wimbledon Men's Singles?", "Novak Djokovic", "Carlos Alcaraz", "Rafael Nadal", "Roger Federer", "B"),
    ("What is the name of the AI chatbot developed by OpenAI?", "Siri", "Alexa", "ChatGPT", "Cortana", "C"),
    ("Which country recently landed a rover on the Moon's south pole?", "USA", "Russia", "China", "India", "D"),
    ("Who is the Prime Minister of the UK (as of early 2024)?", "Boris Johnson", "Rishi Sunak", "Keir Starmer", "Theresa May", "B"),
    ("What global organization deals with international public health?", "WHO", "WTO", "IMF", "UNICEF", "A"),
    ("Which company produces the iPhone?", "Samsung", "Google", "Microsoft", "Apple", "D"),
    ("What is the abbreviation for the European currency?", "USD", "GBP", "EUR", "JPY", "C"),
    ("Which artist had a massive global 'Eras Tour' in 2023?", "Beyonce", "Taylor Swift", "Adele", "Rihanna", "B"),
    ("What year were the Tokyo Summer Olympics held?", "2016", "2020", "2021", "2024", "C"),
    ("Who is the current Pope of the Catholic Church?", "Pope John Paul II", "Pope Benedict XVI", "Pope Francis", "Pope Pius XII", "C"),
    ("Which African country is known as the 'Giant of Africa'?", "South Africa", "Nigeria", "Egypt", "Kenya", "B"),
    ("What is the name of the cryptocurrency created by Satoshi Nakamoto?", "Ethereum", "Ripple", "Bitcoin", "Dogecoin", "C"),
    ("Which social media app is known for short-form dance videos?", "Facebook", "Twitter", "TikTok", "LinkedIn", "C"),
    ("What climate agreement was signed by almost all nations in 2015?", "Kyoto Protocol", "Paris Agreement", "Geneva Convention", "Copenhagen Accord", "B"),
    ("Who is the founder of Microsoft?", "Steve Jobs", "Elon Musk", "Bill Gates", "Larry Page", "C"),
    ("Which country has the most UNESCO World Heritage sites?", "China", "Spain", "Italy", "France", "C"),
    ("What is the largest technology company by revenue?", "Apple", "Amazon", "Alphabet (Google)", "Microsoft", "A"),
    ("Which space telescope was launched by NASA in 2021?", "Hubble", "Kepler", "James Webb", "Spitzer", "C")
]

general_qs = [
    ("How many days are in a leap year?", "365", "366", "364", "367", "B"),
    ("What is the tallest mountain in the world?", "K2", "Mount Kilimanjaro", "Mount Everest", "Mount Fuji", "C"),
    ("Who painted the Mona Lisa?", "Vincent Van Gogh", "Pablo Picasso", "Leonardo da Vinci", "Claude Monet", "C"),
    ("What is the primary ingredient in guacamole?", "Tomato", "Avocado", "Onion", "Pepper", "B"),
    ("How many colors are in a rainbow?", "5", "6", "7", "8", "C"),
    ("What animal is known as the King of the Jungle?", "Tiger", "Elephant", "Lion", "Gorilla", "C"),
    ("Which planet is closest to the sun?", "Venus", "Earth", "Mars", "Mercury", "D"),
    ("What is the national flower of Japan?", "Rose", "Tulip", "Cherry Blossom", "Lotus", "C"),
    ("How many continents are there?", "5", "6", "7", "8", "C"),
    ("What is the largest ocean on Earth?", "Atlantic", "Indian", "Pacific", "Arctic", "C"),
    ("What is the capital of France?", "Rome", "Madrid", "Berlin", "Paris", "D"),
    ("Who wrote the Harry Potter series?", "J.R.R. Tolkien", "J.K. Rowling", "George R.R. Martin", "C.S. Lewis", "B"),
    ("What is the hardest rock?", "Granite", "Marble", "Diamond", "Obsidian", "C"),
    ("How many legs does a spider have?", "6", "8", "10", "12", "B"),
    ("What do bees produce?", "Milk", "Honey", "Silk", "Wax", "B"),
    ("Which month has the fewest days?", "January", "February", "March", "April", "B"),
    ("What is a baby dog called?", "Kitten", "Calf", "Foal", "Puppy", "D"),
    ("What language is spoken in Spain?", "French", "Portuguese", "Spanish", "Italian", "C"),
    ("What shape is a stop sign?", "Square", "Circle", "Hexagon", "Octagon", "D"),
    ("Who was the first man to walk on the moon?", "Buzz Aldrin", "Yuri Gagarin", "Neil Armstrong", "Michael Collins", "C"),
    ("What do you call a group of wolves?", "Herd", "Flock", "Pack", "Pride", "C"),
    ("Which string instrument is the largest?", "Violin", "Cello", "Double Bass", "Viola", "C"),
    ("What is the color of an emerald?", "Red", "Blue", "Green", "Yellow", "C"),
    ("How many players are on a soccer team on the field?", "9", "10", "11", "12", "C"),
    ("What fruit keeps the doctor away?", "Banana", "Orange", "Apple", "Grape", "C")
]

all_qs = []
for sub, q_list in [("Mathematics", math_qs), ("English Language", english_qs), ("Basic Science", science_qs), ("Social Studies", social_qs), ("Current Affairs", current_qs), ("General", general_qs)]:
    for q_data in q_list:
        all_qs.append((sub, q_data))

categories = ["Primary", "Junior Secondary", "Senior Secondary", "Tertiary", "Corpers", "Adults / Open"]
modes = ["Standard", "Speed", "Visual"]
difficulties = ["Primary", "Secondary", "Tertiary"]

questions_to_add = []
for sub, (text, a, b, c, d, correct) in all_qs:
    track = random.choice(tracks)
    category = random.choice(categories)
    mode = random.choice(modes)
    diff = random.choice(difficulties)
    
    q_type = "True/False" if ("True" in [a,b,c,d] and "False" in [a,b,c,d]) else "Multiple Choice"
    
    q = Question(
        text=text,
        option_a=a,
        option_b=b,
        option_c=c,
        option_d=d,
        correct_option=correct,
        subject=sub,
        difficulty=diff,
        school_category=category,
        tournament_track_id=track.id,
        question_mode=mode,
        question_type=q_type,
        is_active=True
    )
    questions_to_add.append(q)

try:
    db.add_all(questions_to_add)
    db.commit()
    print(f"Successfully generated and seeded {len(questions_to_add)} REAL questions!")
except Exception as e:
    db.rollback()
    print("Error:", e)
finally:
    db.close()
