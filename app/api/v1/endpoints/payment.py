import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.core.config import settings
from app.core.security import get_current_school
from app.models.school import School, PaymentTransaction, Tournament
from app.services.paystack import paystack_service

router = APIRouter()

# ----------------- SCHEMAS -----------------

class InitializePaymentPayload(BaseModel):
    amount: float
    payment_type: Optional[str] = "wallet_topup" # wallet_topup, tournament_entry
    tournament_id: Optional[int] = None
    callback_url: Optional[str] = None
    description: Optional[str] = None

class WithdrawalPayload(BaseModel):
    amount: float
    bank_name: str
    account_number: str
    account_name: str

# ----------------- ENDPOINTS -----------------

@router.get("/wallet")
def get_team_wallet(
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    """Returns the authenticated school's live wallet balance and recent transactions."""
    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.school_id == school.id
    ).order_by(PaymentTransaction.created_at.desc()).limit(20).all()

    tx_list = []
    for tx in transactions:
        is_positive = tx.payment_type in ["wallet_topup", "prize_reward"]
        sign = "+" if is_positive else "-"
        color = "text-brand-green" if is_positive else ("text-red-400" if tx.payment_type in ["tournament_entry", "withdrawal"] else "text-white")
        
        tx_list.append({
            "id": tx.id,
            "reference": tx.reference,
            "type": tx.payment_type.replace("_", " ").title(),
            "amount_raw": tx.amount,
            "amount": f"{sign} ₦{tx.amount:,.2f}",
            "desc": tx.description or f"{tx.payment_type.replace('_', ' ').title()}",
            "date": tx.created_at.strftime("%b %d, %Y") if tx.created_at else "Recent",
            "status": tx.status,
            "color": color
        })

    return {
        "school_id": school.id,
        "school_name": school.name,
        "wallet_balance": float(school.wallet_balance or 0.0),
        "formatted_balance": f"₦ {float(school.wallet_balance or 0.0):,.2f}",
        "transactions": tx_list
    }

@router.post("/initialize")
async def initialize_payment(
    payload: InitializePaymentPayload,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    """
    Initializes a Paystack transaction for wallet funding or tournament entry.
    Creates a pending transaction in MySQL and returns authorization URL.
    """
    if payload.amount < 100:
        raise HTTPException(status_code=400, detail="Minimum payment amount is ₦100")

    reference = f"MOW-{school.id:04d}-{uuid.uuid4().hex[:8].upper()}"
    desc = payload.description or ("Team Wallet Top-Up" if payload.payment_type == "wallet_topup" else "Tournament Entry Fee")

    # Record pending transaction
    tx = PaymentTransaction(
        school_id=school.id,
        tournament_id=payload.tournament_id,
        amount=payload.amount,
        reference=reference,
        status="pending",
        payment_type=payload.payment_type,
        channel="paystack",
        description=desc,
        created_at=datetime.utcnow()
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # Initialize with Paystack API
    metadata = {
        "school_id": school.id,
        "school_name": school.name,
        "payment_type": payload.payment_type,
        "tournament_id": payload.tournament_id,
        "description": desc,
        "transaction_id": tx.id
    }

    try:
        paystack_data = await paystack_service.initialize_payment(
            email=school.contact_email or f"school_{school.id}@quizcart.com",
            amount_naira=payload.amount,
            reference=reference,
            callback_url=payload.callback_url,
            metadata=metadata
        )
        return {
            "success": True,
            "reference": reference,
            "authorization_url": paystack_data.get("authorization_url"),
            "access_code": paystack_data.get("access_code"),
            "public_key": settings.PAYSTACK_PUBLIC_KEY,
            "amount": payload.amount
        }
    except Exception as e:
        db.delete(tx)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify/{reference}")
async def verify_payment(
    reference: str,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    """
    Verifies transaction status directly with Paystack API and credits wallet upon confirmation.
    """
    tx = db.query(PaymentTransaction).filter(
        PaymentTransaction.reference == reference,
        PaymentTransaction.school_id == school.id
    ).first()

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction reference not found")

    try:
        paystack_data = await paystack_service.verify_payment(reference)
        ps_status = paystack_data.get("status")

        if ps_status == "success":
            if tx.status != "success":
                tx.status = "success"
                tx.paid_at = datetime.utcnow()

                if tx.payment_type == "wallet_topup":
                    school.wallet_balance = (school.wallet_balance or 0.0) + tx.amount
                elif tx.payment_type == "tournament_entry":
                    school.entry_fee_paid = True

                db.commit()
                db.refresh(school)
                db.refresh(tx)

            return {
                "success": True,
                "status": "success",
                "message": "Payment verified and credited successfully!",
                "amount": tx.amount,
                "wallet_balance": school.wallet_balance,
                "reference": tx.reference
            }
        else:
            tx.status = "failed"
            db.commit()
            return {
                "success": False,
                "status": "failed",
                "message": f"Payment status: {ps_status}"
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(None),
    db: Session = Depends(deps.get_db)
):
    """
    Official Paystack Webhook listener.
    Verifies HMAC SHA512 signature against PAYSTACK_SECRET_KEY and executes idempotent updates.
    """
    raw_body = await request.body()
    
    # Verify signature
    if not paystack_service.verify_webhook_signature(raw_body, x_paystack_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paystack signature"
        )

    try:
        event_payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON")

    event = event_payload.get("event")
    data = event_payload.get("data", {})

    if event == "charge.success":
        reference = data.get("reference")
        amount_paid = data.get("amount", 0) / 100.0 # Convert kobo to Naira
        customer = data.get("customer", {})
        customer_email = customer.get("email")
        metadata = data.get("metadata", {})
        school_id = metadata.get("school_id")

        if reference:
            tx = db.query(PaymentTransaction).filter(PaymentTransaction.reference == reference).first()
            school = None
            if tx:
                school = tx.school
            elif school_id:
                school = db.query(School).filter(School.id == school_id).first()
            elif customer_email:
                school = db.query(School).filter(School.contact_email == customer_email).first()

            if school:
                if not tx:
                    tx = PaymentTransaction(
                        school_id=school.id,
                        tournament_id=metadata.get("tournament_id"),
                        amount=amount_paid,
                        reference=reference,
                        status="success",
                        payment_type=metadata.get("payment_type", "wallet_topup"),
                        channel="paystack",
                        description=metadata.get("description", "Paystack Webhook Funding"),
                        paid_at=datetime.utcnow(),
                        created_at=datetime.utcnow()
                    )
                    db.add(tx)
                    school.wallet_balance = (school.wallet_balance or 0.0) + amount_paid
                elif tx.status != "success":
                    tx.status = "success"
                    tx.paid_at = datetime.utcnow()
                    if tx.payment_type == "wallet_topup":
                        school.wallet_balance = (school.wallet_balance or 0.0) + tx.amount
                    elif tx.payment_type == "tournament_entry":
                        school.entry_fee_paid = True

                db.commit()

    return {"status": "success"}

@router.post("/wallet/withdraw")
def withdraw_funds(
    payload: WithdrawalPayload,
    school: School = Depends(get_current_school),
    db: Session = Depends(deps.get_db)
):
    """Withdrawals are disabled for team/user accounts."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Withdrawals are not permitted for user accounts."
    )

