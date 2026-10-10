import hmac
import hashlib
import json
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

PAYSTACK_BASE_URL = "https://api.paystack.co"

class PaystackService:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    async def initialize_payment(
        self,
        email: str,
        amount_naira: float,
        reference: str,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initializes a transaction with Paystack.
        Amount is converted to kobo (x100).
        """
        amount_kobo = int(round(amount_naira * 100))
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": metadata or {}
        }
        if callback_url:
            payload["callback_url"] = callback_url

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                headers=self._get_headers(),
                json=payload
            )
            response_data = response.json()
            if not response_data.get("status"):
                error_msg = response_data.get("message", "Paystack initialization failed")
                raise Exception(f"Paystack Error: {error_msg}")
            
            return response_data.get("data", {})

    async def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verifies a transaction with Paystack via reference.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                headers=self._get_headers()
            )
            response_data = response.json()
            if not response_data.get("status"):
                error_msg = response_data.get("message", "Paystack verification failed")
                raise Exception(f"Paystack Verification Error: {error_msg}")
            
            return response_data.get("data", {})

    def verify_webhook_signature(self, raw_body: bytes, signature: Optional[str]) -> bool:
        """
        Validates HMAC SHA512 signature from Paystack webhook event.
        """
        if not signature:
            return False
        
        computed_hash = hmac.new(
            self.secret_key.encode("utf-8"),
            raw_body,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_hash, signature)

paystack_service = PaystackService()
