import sys
sys.path.insert(0, '/Users/rotimiolaosebikan/projects/php/quiz_cart/backend')
from app.core.database import engine, Base
from app.models.school import TournamentStage, TournamentMatch, MatchParticipant

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
