from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.schemas.school import Team

class WithdrawalRequestBase(BaseModel):
    team_id: int
    amount: float
    status: Optional[str] = "Pending"

class WithdrawalRequestCreate(WithdrawalRequestBase):
    pass

class WithdrawalRequest(WithdrawalRequestBase):
    id: int
    created_at: datetime
    team: Optional[Team] = None

    class Config:
        from_attributes = True
