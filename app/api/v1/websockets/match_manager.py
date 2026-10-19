import asyncio
import time
import random
from typing import Dict, List, Optional, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.models.school import TournamentMatch, MatchParticipant, Team, School
from app.models.question import Question

class ArenaMatch:
    def __init__(self, match_id: int):
        self.match_id = match_id
        # team_id -> WebSocket (only for WS connections)
        self.active_connections: Dict[int, WebSocket] = {}
        # All team IDs that have ever joined (HTTP or WS)
        self.registered_teams: Set[int] = set()
        # The 10 questions for this match
        self.questions: List[dict] = []
        # Current state
        self.current_question_index = -1
        self.phase = "waiting"  # waiting, question_active, lifeline_paused, answer_reveal, finished

        # State tracking
        self.locked_answers: Dict[int, str] = {}  # team_id -> "A", "B", "C", "D"
        # Rung positions: team_id -> int
        self.ladder: Dict[int, int] = {}

        # Lifeline tracking
        self.active_lifeline: Optional[dict] = None
        self.used_lifelines: Dict[int, List[str]] = {}  # team_id -> [lifeline names]

        # Timer tracking
        self.question_timer_start: float = 0
        self.question_timer_duration: int = 30
        self.lifeline_duration: int = 60

        self.timer_task: Optional[asyncio.Task] = None

        # Lock for exclusivity
        self._lock = asyncio.Lock()

        # Live Game Console State
        self.timer_frozen: bool = False
        self.questions_frozen: bool = False
        self.buzzers_paused: bool = False
        self.locked_team: Optional[str] = "Team Alpha"
        self.answer_revealed: bool = False
        self.show_timer_start: float = time.time() - 1725  # ~00:28:45
        self.frozen_time_remaining: int = 15
        self.substitution_status: str = "none" # none, requested, active, confirmed
        self.substitution_details: Optional[dict] = None
        self.pause_reason: Optional[str] = None
        self.ladder: Dict[int, int] = {1: 7, 2: 3, 3: -1, 4: -3}
        self.team_scores: Dict[int, float] = {1: 2800, 2: 1200, 3: -400, 4: -1200}
        self.custom_participants: List[dict] = [
            {
                "participant_id": 101, "team_id": 1, "team_name": "Team Alpha",
                "score": 2800, "rung": 7, "status": "up", "group": "Group 1",
                "members": [{"id": 1, "name": "Amina Bello", "role": "Captain", "is_captain": True}]
            },
            {
                "participant_id": 102, "team_id": 2, "team_name": "Team Beta",
                "score": 1200, "rung": 3, "status": "neutral", "group": "Group 1",
                "members": [{"id": 2, "name": "Chidi Okafor", "role": "Captain", "is_captain": True}]
            },
            {
                "participant_id": 103, "team_id": 3, "team_name": "Team Gamma",
                "score": -400, "rung": -1, "status": "down", "group": "Group 1",
                "members": [{"id": 3, "name": "David Adeleke", "role": "Member", "is_captain": False}]
            },
            {
                "participant_id": 104, "team_id": 4, "team_name": "Team Delta",
                "score": -1200, "rung": -3, "status": "down", "group": "Group 1",
                "members": [{"id": 4, "name": "Fatima Umar", "role": "Member", "is_captain": False}]
            },
        ]
        self.announcements: List[dict] = [
            {"id": 1, "message": "Welcome to Scholarnaire Live!", "timestamp": "2 mins ago"},
            {"id": 2, "message": "Next round: Semi Finals", "timestamp": "15 mins ago"},
            {"id": 3, "message": "Use your lifelines wisely!", "timestamp": "32 mins ago"},
            {"id": 4, "message": "Good luck to all teams!", "timestamp": "1 hr ago"}
        ]
        self.game_logs: List[dict] = [
            {"id": 1, "timestamp": "10:24", "event_type": "CORRECT_ANSWER", "message": "Team Alpha answered correctly (+250)"},
            {"id": 2, "timestamp": "10:22", "event_type": "LIFELINE_USED", "message": "Team Beta used 50:50 lifeline"},
            {"id": 3, "timestamp": "10:18", "event_type": "SUB_APPROVED", "message": "Substitution request approved (Team Gamma)"},
            {"id": 4, "timestamp": "10:16", "event_type": "TIMER_FROZEN", "message": "Timer frozen (Moderator)"},
            {"id": 5, "timestamp": time.strftime("%H:%M:%S"), "event_type": "MATCH_READY", "message": f"Live Arena Console Initialized for Match {match_id}"}
        ]

    def add_game_log(self, event_type: str, message: str, meta: dict = None):
        entry = {
            "id": len(self.game_logs) + 1,
            "timestamp": time.strftime("%H:%M:%S"),
            "event_type": event_type,
            "message": message,
            "meta": meta or {}
        }
        self.game_logs.append(entry)
        if len(self.game_logs) > 60:
            self.game_logs = self.game_logs[-60:]

    def ensure_team_registered(self, team_id: int):
        """Register a team for HTTP polling without requiring a WebSocket connection."""
        if team_id not in self.registered_teams:
            self.registered_teams.add(team_id)
            if team_id not in self.ladder:
                self.ladder[team_id] = 1  # Start at Nursery (rung 1)
            if team_id not in self.used_lifelines:
                self.used_lifelines[team_id] = []

    def get_lifeline_duration(self, lifeline: str) -> int:
        # All official Scholarnnaire Helplines have a designated 60-second timer
        return 60

    async def connect(self, websocket: WebSocket, team_id: int):
        self.active_connections[team_id] = websocket
        self.ensure_team_registered(team_id)
        await self.broadcast_state()

    def disconnect(self, team_id: int):
        if team_id in self.active_connections:
            del self.active_connections[team_id]

    async def broadcast(self, message: dict):
        disconnected = []
        for team_id, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(team_id)
        for team_id in disconnected:
            self.disconnect(team_id)

    def get_public_state(self):
        q = None
        correct_option = None
        display_index = max(0, self.current_question_index)
        if 0 <= display_index < len(self.questions):
            q_raw = self.questions[display_index]
            q = {
                "id": q_raw["id"],
                "text": q_raw["text"],
                "option_a": q_raw["option_a"],
                "option_b": q_raw["option_b"],
                "option_c": q_raw["option_c"],
                "option_d": q_raw["option_d"],
                "subject": q_raw["subject"],
            }
            # Only reveal correct answer during answer_reveal, finished phases or explicit admin reveal
            if self.phase in ("answer_reveal", "finished") or getattr(self, "answer_revealed", False):
                correct_option = q_raw["correct_option"].strip().upper()

        time_left = 0
        if self.timer_frozen:
            time_left = getattr(self, "frozen_time_remaining", 15)
        elif self.phase == "question_active":
            elapsed = time.time() - self.question_timer_start
            time_left = max(0, self.question_timer_duration - elapsed)
        elif self.phase == "lifeline_paused" and self.active_lifeline:
            elapsed = time.time() - self.active_lifeline["start_time"]
            time_left = max(0, self.active_lifeline.get("duration", 60) - elapsed)
        elif self.phase == "substitution_paused":
            time_left = getattr(self, "time_remaining_when_paused", 15)

        # Game status string for console badge
        game_status = "WAITING"
        if self.phase == "substitution_paused":
            game_status = "PAUSED"
        elif self.timer_frozen:
            game_status = "TIMERS FROZEN"
        elif self.questions_frozen:
            game_status = "QUESTIONS FROZEN"
        elif self.phase == "finished":
            game_status = "COMPLETED"
        elif self.phase == "question_active":
            game_status = "WAITING" if not self.locked_answers else "LOCKED"

        show_elapsed = int(time.time() - self.show_timer_start)
        show_formatted = f"{show_elapsed // 3600:02d}:{(show_elapsed % 3600) // 60:02d}:{show_elapsed % 60:02d}"

        return {
            "type": "state_update",
            "phase": self.phase,
            "game_status": game_status,
            "is_paused": self.phase == "substitution_paused",
            "timers_frozen": self.timer_frozen,
            "questions_frozen": self.questions_frozen,
            "buzzers_paused": self.buzzers_paused,
            "locked_team": self.locked_team or ("Team Alpha" if self.locked_answers else None),
            "answer_revealed": self.answer_revealed,
            "substitution_status": self.substitution_status,
            "substitution_details": self.substitution_details,
            "pause_reason": getattr(self, "pause_reason", None),
            "current_question": q,
            "current_question_index": display_index,
            "total_questions": max(len(self.questions), 50),
            "ladder": self.ladder,
            "locked_answers": list(self.locked_answers.keys()),
            "active_lifeline": self.active_lifeline,
            "time_left": int(time_left),
            "show_timer_formatted": show_formatted,
            "team_scores": self.team_scores,
            "announcements": self.announcements,
            "correct_option": correct_option,
            "game_logs": self.game_logs[-25:],
            "my_used_lifelines": [],  # Populated per-team in HTTP state endpoint
        }

    async def broadcast_state(self):
        disconnected = []
        for team_id, ws in self.active_connections.items():
            try:
                state = self.get_public_state()
                state["my_used_lifelines"] = self.used_lifelines.get(team_id, [])
                await ws.send_json(state)
            except Exception:
                disconnected.append(team_id)
        for team_id in disconnected:
            self.disconnect(team_id)

    async def initialize_questions(self, db: Session, match_id: int):
        # Match 99999 or fallback test simulation match
        if match_id == 99999:
            self._load_test_questions(db)
            return

        match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
        if not match:
            self._load_test_questions(db)
            return

        participant = db.query(MatchParticipant).filter(MatchParticipant.match_id == match_id).first()
        if not participant:
            self._load_test_questions(db)
            return

        team = db.query(Team).filter(Team.id == participant.team_id).first()
        school = db.query(School).filter(School.id == team.school_id).first() if team else None

        stage = match.stage
        tournament = stage.tournament if stage else None

        questions_query = db.query(Question).filter(Question.is_active == True)
        if tournament and tournament.tournament_track_id:
            questions_query = questions_query.filter(Question.tournament_track_id == tournament.tournament_track_id)
        if school and school.category:
            questions_query = questions_query.filter(Question.school_category == school.category)

        all_questions = questions_query.all()
        if len(all_questions) < 5:
            # Fallback to test questions if not enough
            self._load_test_questions(db)
            return

        selected = random.sample(all_questions, min(len(all_questions), 50))
        self.questions = [
            {
                "id": q.id, "text": q.text,
                "option_a": q.option_a, "option_b": q.option_b,
                "option_c": q.option_c, "option_d": q.option_d,
                "subject": q.subject, "correct_option": q.correct_option
            } for q in selected
        ]
        if self.current_question_index == -1:
            self.current_question_index = 0
            self.phase = "question_active"

    def _load_test_questions(self, db: Optional[Session] = None):
        # Always start with the official reference question from the console specification
        initial_q = {
            "id": 99901,
            "text": "Which planet is known as the Red Planet?",
            "option_a": "Earth",
            "option_b": "Mars",
            "option_c": "Jupiter",
            "option_d": "Venus",
            "subject": "Astronomy",
            "correct_option": "B"
        }
        loaded = [initial_q]

        if db:
            try:
                db_qs = db.query(Question).filter(Question.is_active == True).limit(49).all()
                for q in db_qs:
                    loaded.append({
                        "id": q.id,
                        "text": q.text,
                        "option_a": q.option_a,
                        "option_b": q.option_b,
                        "option_c": q.option_c,
                        "option_d": q.option_d,
                        "subject": q.subject or "General Knowledge",
                        "correct_option": q.correct_option or "A"
                    })
            except Exception as e:
                pass

        # Pad up to 50 if needed
        demo_pool = [
            ("What is the powerhouse of the cell?", "Ribosome", "Mitochondria", "Nucleus", "Cytoplasm", "B", "Biology"),
            ("What is the chemical symbol for Gold?", "Ag", "Au", "Pb", "Fe", "B", "Chemistry"),
            ("Which continent is known as the Dark Continent?", "Asia", "South America", "Africa", "Australia", "C", "Geography"),
            ("Who was Nigeria's first Prime Minister?", "Nnamdi Azikiwe", "Abubakar Tafawa Balewa", "Obafemi Awolowo", "Ahmadu Bello", "B", "History"),
            ("Solve for x: 3x + 15 = 45", "5", "10", "15", "20", "B", "Mathematics"),
            ("Which element has the atomic number 1?", "Helium", "Hydrogen", "Lithium", "Carbon", "B", "Chemistry"),
            ("What is the speed of light in a vacuum?", "300,000 km/s", "150,000 km/s", "30,000 km/s", "3,000 km/s", "A", "Physics"),
        ]
        idx = 2
        while len(loaded) < 50:
            item = demo_pool[(len(loaded) - 1) % len(demo_pool)]
            loaded.append({
                "id": 99900 + len(loaded),
                "text": f"{item[0]} (Q{len(loaded)+1})",
                "option_a": item[1],
                "option_b": item[2],
                "option_c": item[3],
                "option_d": item[4],
                "correct_option": item[5],
                "subject": item[6]
            })

        self.questions = loaded
        if self.current_question_index == -1:
            self.current_question_index = 0
            self.phase = "question_active"
            self.question_timer_start = time.time()

    async def start_next_question(self):
        async with self._lock:
            if self.current_question_index >= len(self.questions) - 1:
                self.phase = "finished"
                await self.broadcast_state()
                return

            self.current_question_index += 1
            self.phase = "question_active"
            self.locked_answers = {}
            self.active_lifeline = None
            self.question_timer_start = time.time()

            await self.broadcast_state()

            if self.timer_task:
                self.timer_task.cancel()
            self.timer_task = asyncio.create_task(self._question_timer())

    async def _question_timer(self):
        try:
            await asyncio.sleep(self.question_timer_duration)
            if self.phase == "question_active":
                await self.reveal_answers()
        except asyncio.CancelledError:
            pass

    async def _lifeline_timer(self, duration: int):
        try:
            await asyncio.sleep(duration)
            async with self._lock:
                if self.phase == "lifeline_paused":
                    self.phase = "question_active"
                    self.question_timer_start = time.time()  # Fresh 30s after lifeline
                    self.active_lifeline = None
                    await self.broadcast_state()

                    if self.timer_task:
                        self.timer_task.cancel()
                    self.timer_task = asyncio.create_task(self._question_timer())
        except asyncio.CancelledError:
            pass

    async def process_message(self, team_id: int, message: dict):
        # Always ensure the team is registered (supports HTTP polling teams)
        self.ensure_team_registered(team_id)

        msg_type = message.get("type")

        if msg_type == "lock_answer":
            if self.phase != "question_active":
                return
            if team_id in self.locked_answers:
                return

            answer = message.get("answer")
            if answer in ["A", "B", "C", "D"]:
                self.locked_answers[team_id] = answer
                await self.broadcast_state()

                # If ALL registered teams have locked in, reveal early
                all_teams = self.registered_teams
                if len(all_teams) > 0 and all(t in self.locked_answers for t in all_teams):
                    if self.timer_task:
                        self.timer_task.cancel()
                    await self.reveal_answers()

        elif msg_type == "use_lifeline":
            async with self._lock:
                if self.phase != "question_active":
                    return
                if self.active_lifeline is not None:
                    return  # Someone already claimed it

                lifeline = message.get("lifeline")
                valid_lifelines = ["phone_scholar", "ask_crowd", "search_net", "browse_net", "flip_scholarpedia", "flip_book"]
                if lifeline not in valid_lifelines:
                    return
                # Canonicalize alias
                if lifeline == "flip_book":
                    lifeline = "flip_scholarpedia"
                elif lifeline == "browse_net":
                    lifeline = "search_net"

                if lifeline in self.used_lifelines.get(team_id, []):
                    return  # Already used this lifeline

                # First press wins (exclusivity)
                self.used_lifelines[team_id].append(lifeline)
                duration = self.get_lifeline_duration(lifeline)
                self.active_lifeline = {
                    "team_id": team_id,
                    "lifeline": lifeline,
                    "start_time": time.time(),
                    "duration": duration
                }
                self.phase = "lifeline_paused"

                if self.timer_task:
                    self.timer_task.cancel()

                self.timer_task = asyncio.create_task(self._lifeline_timer(duration))
                await self.broadcast_state()

    def get_rung_label(self, rung: int) -> str:
        positive_titles = {
            11: "SCHOLARNAIRE (+4,400 pts)",
            10: "PROFESSOR (+4,000 pts)",
            9: "ASSOCIATE PROFESSOR (+3,600 pts)",
            8: "Ph.D (+3,200 pts)",
            7: "DON (+2,800 pts)",
            6: "MASTERS (+2,400 pts)",
            5: "TERTIARY (+2,000 pts)",
            4: "SECONDARY (+1,600 pts)",
            3: "PRIMARY (+1,200 pts)",
            2: "KINDERGARTEN (+800 pts)",
            1: "NURSERY (+400 pts)",
            0: "GROUND LEVEL (0 pts)"
        }
        if rung >= 0:
            return positive_titles.get(rung, f"Rung +{rung}")
        return f"{abs(rung)} Step{'s' if abs(rung) > 1 else ''} Penalty ({rung * 400} pts)"

    async def process_question_result(self, team_id: int, is_correct: bool, points: float = 400):
        current_rung = self.ladder.get(team_id, 0)
        team_name = next((p["team_name"] for p in self.custom_participants if p["team_id"] == team_id), f"Team {team_id}")
        if is_correct:
            new_rung = min(11, current_rung + 1)
            self.ladder[team_id] = new_rung
            self.team_scores[team_id] = self.team_scores.get(team_id, 0) + points
            self.add_game_log("CORRECT_ANSWER", f"{team_name} answered correctly (+{int(points)} pts, climbed to {self.get_rung_label(new_rung)})")
        else:
            new_rung = max(-11, current_rung - 1)
            self.ladder[team_id] = new_rung
            self.team_scores[team_id] = self.team_scores.get(team_id, 0) - points
            self.add_game_log("MISSED_QUESTION", f"{team_name} missed the question (-{int(points)} pts penalty, dropped to {self.get_rung_label(new_rung)})")

    async def reveal_answers(self):
        async with self._lock:
            self.phase = "answer_reveal"
            current_q = self.questions[self.current_question_index] if 0 <= self.current_question_index < len(self.questions) else None
            correct_opt = current_q["correct_option"].strip().upper() if current_q else "A"

            # Update ladder and scores for ALL registered teams
            for t_id in list(self.registered_teams):
                ans = self.locked_answers.get(t_id)
                is_correct = (ans == correct_opt)
                await self.process_question_result(t_id, is_correct, points=400)

            reveal_data = {
                "type": "answer_reveal",
                "correct_option": correct_opt,
                "team_answers": self.locked_answers,
                "ladder": self.ladder,
                "team_scores": self.team_scores
            }
            await self.broadcast(reveal_data)

            # Auto-transition to next question after 8 seconds
            async def auto_next():
                await asyncio.sleep(8)
                await self.start_next_question()

            asyncio.create_task(auto_next())

    async def pause_game(self, reason: str = "Admin requested game pause", details: dict = None):
        async with self._lock:
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            
            elapsed = time.time() - self.question_timer_start
            self.time_remaining_when_paused = max(1, int(self.question_timer_duration - elapsed))
            self.previous_phase = self.phase
            self.phase = "substitution_paused"
            self.pause_reason = reason
            self.active_substitution = details
            self.add_game_log("PAUSE_GAME", f"Game paused: {reason}")
            await self.broadcast_state()

    async def resume_game(self):
        async with self._lock:
            self.phase = getattr(self, "previous_phase", "question_active")
            if self.phase == "substitution_paused":
                self.phase = "question_active"
            self.question_timer_duration = getattr(self, "time_remaining_when_paused", 15)
            self.question_timer_start = time.time()
            self.active_substitution = None
            self.pause_reason = None
            self.timer_frozen = False
            self.questions_frozen = False
            self.substitution_status = "none"
            self.add_game_log("RESUME_GAME", "Game resumed by Admin")
            await self.broadcast_state()
            if self.phase == "question_active":
                self.timer_task = asyncio.create_task(self._question_timer())

    async def freeze_timers(self, freeze: Optional[bool] = None):
        async with self._lock:
            if freeze is None:
                self.timer_frozen = not self.timer_frozen
            else:
                self.timer_frozen = freeze

            if self.timer_frozen:
                elapsed = time.time() - self.question_timer_start
                self.frozen_time_remaining = max(1, int(self.question_timer_duration - elapsed))
                if self.timer_task and not self.timer_task.done():
                    self.timer_task.cancel()
                self.add_game_log("FREEZE_TIMERS", f"Timers frozen at {self.frozen_time_remaining}s remaining")
            else:
                self.question_timer_duration = self.frozen_time_remaining
                self.question_timer_start = time.time()
                if self.phase == "question_active":
                    self.timer_task = asyncio.create_task(self._question_timer())
                self.add_game_log("UNFREEZE_TIMERS", "Timers unfrozen and active")
            await self.broadcast_state()

    async def freeze_questions(self, freeze: Optional[bool] = None):
        async with self._lock:
            if freeze is None:
                self.questions_frozen = not self.questions_frozen
            else:
                self.questions_frozen = freeze
            status_text = "frozen (buzzer/locking disabled)" if self.questions_frozen else "unfrozen"
            self.add_game_log("FREEZE_QUESTIONS", f"Questions {status_text}")
            await self.broadcast_state()

    async def request_substitution(self, details: dict = None):
        async with self._lock:
            self.substitution_status = "requested"
            self.substitution_details = details or {
                "team_name": "Contestant Team",
                "reason": "Player substitution requested",
                "time": time.strftime("%H:%M:%S")
            }
            self.add_game_log("SUBSTITUTION_REQUESTED", "Team submitted substitution request", self.substitution_details)
            await self.broadcast_state()

    async def activate_substitution(self, details: dict = None):
        async with self._lock:
            self.substitution_status = "active"
            if details:
                self.substitution_details = details
            if self.phase != "substitution_paused":
                if self.timer_task and not self.timer_task.done():
                    self.timer_task.cancel()
                elapsed = time.time() - self.question_timer_start
                self.time_remaining_when_paused = max(1, int(self.question_timer_duration - elapsed))
                self.previous_phase = self.phase
                self.phase = "substitution_paused"
                self.pause_reason = "Substitution in progress"
            self.add_game_log("SUBSTITUTION_ACTIVATED", "Substitution officially activated on stage")
            await self.broadcast_state()

    async def confirm_substitution(self):
        async with self._lock:
            self.substitution_status = "confirmed"
            self.add_game_log("SUBSTITUTION_CONFIRMED", "Substitution confirmed complete. Ready to resume.")
            await self.broadcast_state()

    async def pause_buzzers(self):
        async with self._lock:
            self.buzzers_paused = True
            self.add_game_log("BUZZERS_PAUSED", "Buzzers paused by Moderator")
            await self.broadcast_state()

    async def release_buzzers(self):
        async with self._lock:
            self.buzzers_paused = False
            self.add_game_log("BUZZERS_RELEASED", "Buzzers released and live for all teams")
            await self.broadcast_state()

    async def show_answer(self):
        async with self._lock:
            self.answer_revealed = True
            if 0 <= self.current_question_index < len(self.questions):
                correct = self.questions[self.current_question_index]["correct_option"].strip().upper()
                self.add_game_log("SHOW_ANSWER", f"Correct answer revealed: Option {correct}")
            await self.broadcast_state()

    async def reset_current_question(self):
        async with self._lock:
            self.locked_answers = {}
            self.locked_team = None
            self.active_lifeline = None
            self.answer_revealed = False
            self.phase = "question_active"
            self.question_timer_start = time.time()
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            self.timer_task = asyncio.create_task(self._question_timer())
            self.add_game_log("RESET_QUESTION", f"Question {self.current_question_index + 1} reset by Moderator")
            await self.broadcast_state()

    async def adjust_team_score(self, team_id: int, delta: float, reason: str = "Score adjustment"):
        async with self._lock:
            current = self.team_scores.get(team_id, 0)
            new_score = current + delta
            self.team_scores[team_id] = new_score
            # Calculate ladder step based on 400 pts per rung (positive or negative)
            calc_rung = int(new_score // 400) if new_score >= 0 else int(new_score // 400)
            self.ladder[team_id] = max(-11, min(11, calc_rung))
            self.add_game_log("SCORE_ADJUSTED", f"Team score adjusted ({'+' if delta >= 0 else ''}{int(delta)} pts, now {self.get_rung_label(self.ladder[team_id])}): {reason}")
            await self.broadcast_state()

    async def trigger_lifeline(self, lifeline_name: str, team_id: int = 1):
        async with self._lock:
            self.active_lifeline = {
                "team_id": team_id,
                "lifeline": lifeline_name,
                "start_time": time.time(),
                "duration": 60
            }
            self.phase = "lifeline_paused"
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            self.timer_task = asyncio.create_task(self._lifeline_timer(60))
            self.add_game_log("LIFELINE_ACTIVATED", f"Lifeline '{lifeline_name.replace('_', ' ').title()}' activated for 60 seconds")
            await self.broadcast_state()

    def add_announcement(self, message: str):
        item = {
            "id": len(self.announcements) + 1,
            "message": message,
            "timestamp": "Just now"
        }
        self.announcements.insert(0, item)
        self.add_game_log("ANNOUNCEMENT", f"Announcement published: {message}")

    async def add_participant(self, team_id: Optional[int] = None, team_name: Optional[str] = None, score: float = 0, group: str = "Group 1"):
        async with self._lock:
            existing_tids = [p["team_id"] for p in self.custom_participants]
            if team_id is None:
                team_id = max(existing_tids, default=0) + 1
            if not team_name:
                greek_letters = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho", "Sigma", "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega"]
                idx = len(self.custom_participants)
                letter = greek_letters[idx] if idx < len(greek_letters) else f"Squad-{idx+1}"
                team_name = f"Team {letter}"

            for p in self.custom_participants:
                if p["team_id"] == team_id:
                    return p

            new_p = {
                "participant_id": 100 + len(self.custom_participants) + 1,
                "team_id": team_id,
                "team_name": team_name,
                "score": score,
                "status": "neutral",
                "group": group,
                "members": [{"id": 1, "name": f"{team_name} Captain", "role": "Captain", "is_captain": True}]
            }
            self.custom_participants.append(new_p)
            self.team_scores[team_id] = score
            self.ensure_team_registered(team_id)
            self.add_game_log("PARTICIPANT_ADDED", f"Participant added: {team_name} (Total: {len(self.custom_participants)})")
            await self.broadcast_state()
            return new_p

    async def remove_participant(self, team_id: Optional[int] = None, participant_id: Optional[int] = None):
        async with self._lock:
            if not self.custom_participants:
                return None

            removed_p = None
            filtered = []
            if team_id is None and participant_id is None:
                # Remove last participant (quick-decrease)
                removed_p = self.custom_participants[-1]
                filtered = self.custom_participants[:-1]
            else:
                for p in self.custom_participants:
                    if (team_id is not None and p["team_id"] == team_id) or (participant_id is not None and p["participant_id"] == participant_id):
                        removed_p = p
                    else:
                        filtered.append(p)

            if removed_p:
                self.custom_participants = filtered
                tid = removed_p["team_id"]
                self.team_scores.pop(tid, None)
                if tid in self.registered_teams:
                    self.registered_teams.discard(tid)
                self.add_game_log("PARTICIPANT_REMOVED", f"Participant removed: {removed_p['team_name']} (Total: {len(self.custom_participants)})")
                await self.broadcast_state()
                return removed_p
            return None

class ArenaController:
    def __init__(self):
        self.matches: Dict[int, ArenaMatch] = {}

    def get_match(self, match_id: int) -> ArenaMatch:
        if match_id not in self.matches:
            self.matches[match_id] = ArenaMatch(match_id)
        return self.matches[match_id]


arena_controller = ArenaController()
