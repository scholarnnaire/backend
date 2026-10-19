from pydantic import BaseModel
from app.models.question import QuestionDifficulty
from app.models.school import SchoolCategory

from typing import Optional, Union

class QuestionBase(BaseModel):
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    subject: str
    difficulty: Union[QuestionDifficulty, str]
    school_category: Union[SchoolCategory, str]
    tournament_track_id: Optional[int] = None
    question_mode: Optional[str] = None
    question_type: Optional[str] = None
    stage: Optional[str] = "Group Stage 1"
    game_division_id: Optional[int] = None

class QuestionCreate(QuestionBase):
    pass

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_option: Optional[str] = None
    subject: Optional[str] = None
    difficulty: Optional[Union[QuestionDifficulty, str]] = None
    school_category: Optional[Union[SchoolCategory, str]] = None
    tournament_track_id: Optional[int] = None
    question_mode: Optional[str] = None
    question_type: Optional[str] = None
    stage: Optional[str] = None
    game_division_id: Optional[int] = None
    is_active: Optional[bool] = None

class Question(QuestionBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True
