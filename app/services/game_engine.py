import random
import time
from app.services.mock_data import MOCK_QUESTIONS

class GameSession:
    def __init__(self):
        # We start with teams at rung 0. 11 rungs total (0 to 11).
        self.players = {
            "player1": {
                "rung": 0,
                "current_question_idx": 0, 
                "streak": 0, # positive for correct, negative for incorrect
                "in_momentum": False,
                "in_downfall": False,
                "lifelines": {"phone_a_scholar": True, "flip_a_book": True, "search_the_net": True},
                "last_question_start": 0
            },
            "player2": {
                "rung": 0,
                "current_question_idx": 0,
                "streak": 0,
                "in_momentum": False,
                "in_downfall": False,
                "lifelines": {"phone_a_scholar": True, "flip_a_book": True, "search_the_net": True},
                "last_question_start": 0
            }
        }
        self.status = "waiting" # waiting, active, finished
        self.crowd_votes = {0: 0, 1: 0, 2: 0, 3: 0}
        
        # Lifeline exclusivity locks. Which team claimed it first?
        self.lifeline_locks = {
            "phone_a_scholar": None,
            "flip_a_book": None,
            "search_the_net": None
        }

    def reset_crowd_votes(self):
        self.crowd_votes = {0: 0, 1: 0, 2: 0, 3: 0}

    def record_crowd_vote(self, answer_index: int):
        if answer_index in self.crowd_votes:
            self.crowd_votes[answer_index] += 1

    def get_crowd_results(self):
        total = sum(self.crowd_votes.values())
        if total == 0:
            return {0: 25, 1: 25, 2: 25, 3: 25}
        return {k: round((v / total) * 100) for k, v in self.crowd_votes.items()}

    def start_game(self):
        self.status = "active"
        self.lifeline_locks = {"phone_a_scholar": None, "flip_a_book": None, "search_the_net": None}
        for p in self.players.values():
            p["rung"] = 0
            p["current_question_idx"] = 0
            p["streak"] = 0
            p["in_momentum"] = False
            p["in_downfall"] = False
            p["lifelines"] = {"phone_a_scholar": True, "flip_a_book": True, "search_the_net": True}
            p["last_question_start"] = time.time()
            
    def get_question(self, player_id: str):
        player = self.players.get(player_id)
        if not player or self.status != "active":
            return None
            
        idx = player["current_question_idx"]
        if idx >= len(MOCK_QUESTIONS):
            return {"status": "finished", "rung": player["rung"]}
            
        q = MOCK_QUESTIONS[idx]
        player["last_question_start"] = time.time()
        
        return {
            "status": "active",
            "question_data": {
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
            },
            "rung": player["rung"],
            "in_momentum": player["in_momentum"],
            "in_downfall": player["in_downfall"],
            "lifelines": player["lifelines"],
            "lifeline_locks": self.lifeline_locks,
            "question_index": idx
        }

    def answer_question(self, player_id: str, answer_index: int):
        player = self.players.get(player_id)
        if not player or self.status != "active":
            return {"error": "Invalid player or game not active"}
            
        idx = player["current_question_idx"]
        if idx >= len(MOCK_QUESTIONS):
            return {"error": "Game already finished for this player"}
            
        # Check timer (30 seconds + 2 seconds grace for latency as per PRD)
        time_elapsed = time.time() - player["last_question_start"]
        is_timeout = time_elapsed > 32
        
        q = MOCK_QUESTIONS[idx]
        is_correct = (answer_index == q["answer_index"]) and not is_timeout
        
        # Momentum / Downfall Logic
        if is_correct:
            if player["streak"] < 0:
                player["streak"] = 0 # reset negative streak
            player["streak"] += 1
            
            # Climb ladder
            rungs_to_climb = 1
            
            # Momentum trigger (3 in a row)
            if player["streak"] >= 3:
                player["in_momentum"] = True
                rungs_to_climb = 2 # Bonus rung in momentum mode
                
            # If they just broke downfall (Comeback Bonus - not fully spec'd but let's climb normally)
            player["in_downfall"] = False
            
            player["rung"] = min(11, player["rung"] + rungs_to_climb)
            
        else:
            if player["streak"] > 0:
                player["streak"] = 0 # reset positive streak
            player["streak"] -= 1
            
            player["in_momentum"] = False
            
            rungs_to_fall = 0
            if player["streak"] <= -2:
                player["in_downfall"] = True
                rungs_to_fall = 1 # Fall a rung in downfall mode
                
            player["rung"] = max(0, player["rung"] - rungs_to_fall)
            
        player["current_question_idx"] += 1
        
        return {
            "correct": is_correct, 
            "reason": "timeout" if is_timeout else "answered",
            "rung": player["rung"],
            "in_momentum": player["in_momentum"],
            "in_downfall": player["in_downfall"]
        }

    def use_lifeline(self, player_id: str, lifeline_id: str):
        player = self.players.get(player_id)
        if not player:
            return {"success": False, "error": "Invalid player"}
            
        if lifeline_id not in player["lifelines"]:
            return {"success": False, "error": "Invalid lifeline"}
            
        if not player["lifelines"][lifeline_id]:
            return {"success": False, "error": "Lifeline already used by you"}
            
        # First-press wins exclusivity check
        if self.lifeline_locks[lifeline_id] is not None and self.lifeline_locks[lifeline_id] != player_id:
            return {"success": False, "error": "Lifeline already claimed by opponent"}
            
        # Claim it
        self.lifeline_locks[lifeline_id] = player_id
        player["lifelines"][lifeline_id] = False
        
        return {"success": True, "lifelines_state": player["lifelines"], "locks": self.lifeline_locks}

# Global instance for prototype
global_game = GameSession()
