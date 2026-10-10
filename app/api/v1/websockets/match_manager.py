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
        self.frozen_time_remaining: int = 15
        self.substitution_status: str = "none" # none, requested, active, confirmed
        self.substitution_details: Optional[dict] = None
        self.game_logs: List[dict] = [
            {"id": 1, "timestamp": time.strftime("%H:%M:%S"), "event_type": "MATCH_READY", "message": f"Live Arena Console Initialized for Match {match_id}"}
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
        if lifeline == "phone_scholar": return 60
        if lifeline == "flip_book": return 45
        if lifeline == "search_net": return 30
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
            # Only reveal correct answer during answer_reveal and finished phases
            if self.phase in ("answer_reveal", "finished"):
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
        game_status = "RUNNING"
        if self.phase == "substitution_paused":
            game_status = "PAUSED"
        elif self.timer_frozen:
            game_status = "TIMERS FROZEN"
        elif self.questions_frozen:
            game_status = "QUESTIONS FROZEN"
        elif self.phase == "finished":
            game_status = "COMPLETED"
        elif self.phase == "waiting":
            game_status = "WAITING"

        return {
            "type": "state_update",
            "phase": self.phase,
            "game_status": game_status,
            "is_paused": self.phase == "substitution_paused",
            "timers_frozen": self.timer_frozen,
            "questions_frozen": self.questions_frozen,
            "substitution_status": self.substitution_status,
            "substitution_details": self.substitution_details,
            "pause_reason": getattr(self, "pause_reason", None),
            "current_question": q,
            "current_question_index": display_index,
            "total_questions": len(self.questions) or 44,
            "ladder": self.ladder,
            "locked_answers": list(self.locked_answers.keys()),
            "active_lifeline": self.active_lifeline,
            "time_left": int(time_left),
            "correct_option": correct_option,
            "game_logs": self.game_logs[-20:],
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
        match = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
        if not match:
            return

        participant = db.query(MatchParticipant).filter(MatchParticipant.match_id == match_id).first()
        if not participant:
            return

        team = db.query(Team).filter(Team.id == participant.team_id).first()
        school = db.query(School).filter(School.id == team.school_id).first()

        stage = match.stage
        tournament = stage.tournament

        questions_query = db.query(Question).filter(
            Question.tournament_track_id == tournament.tournament_track_id,
            Question.school_category == school.category,
            Question.is_active == True
        )

        all_questions = questions_query.all()
        if len(all_questions) >= 10:
            selected = random.sample(all_questions, 10)
        else:
            selected = all_questions

        self.questions = [
            {
                "id": q.id, "text": q.text,
                "option_a": q.option_a, "option_b": q.option_b,
                "option_c": q.option_c, "option_d": q.option_d,
                "subject": q.subject, "correct_option": q.correct_option
            } for q in selected
        ]

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
                valid_lifelines = ["phone_scholar", "flip_book", "search_net"]
                if lifeline not in valid_lifelines:
                    return
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

    async def reveal_answers(self):
        async with self._lock:
            self.phase = "answer_reveal"
            current_q = self.questions[self.current_question_index]
            correct_opt = current_q["correct_option"].strip().upper()

            # Update ladder for ALL registered teams (not just WebSocket connections)
            for t_id in list(self.registered_teams):
                if t_id not in self.ladder:
                    self.ladder[t_id] = 1
                ans = self.locked_answers.get(t_id)
                if ans == correct_opt:
                    current_rung = self.ladder[t_id]
                    self.ladder[t_id] = min(11, current_rung + 1)  # Cap at 11
                else:
                    self.ladder[t_id] = max(1, self.ladder.get(t_id, 1) - 1)  # Floor at 1

            reveal_data = {
                "type": "answer_reveal",
                "correct_option": correct_opt,
                "team_answers": self.locked_answers,
                "ladder": self.ladder
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

class ArenaController:
    def __init__(self):
        self.matches: Dict[int, ArenaMatch] = {}

    def get_match(self, match_id: int) -> ArenaMatch:
        if match_id not in self.matches:
            self.matches[match_id] = ArenaMatch(match_id)
        return self.matches[match_id]


arena_controller = ArenaController()
