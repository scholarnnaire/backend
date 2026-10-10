from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PaymentTransactionBase(BaseModel):
    school_id: int
    tournament_id: int
    amount: float
    reference: str
    status: Optional[str] = "success"

class PaymentTransactionCreate(PaymentTransactionBase):
    pass

class PaymentTransaction(PaymentTransactionBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
