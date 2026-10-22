"""
PayPal Sandbox Client for AgentPay AI.
Handles OAuth2 token exchange, Orders v2 creation/capture, and Payouts v1.
Gracefully supports both live sandbox credentials and resilient offline simulation.
"""

import os
import time
import httpx
from typing import Dict, Any, Optional

PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"


class PayPalSandboxClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.mock_mode = (
            mock_mode
            or not self.client_id
            or self.client_id.startswith("sandbox_mock")
            or not self.client_secret
            or self.client_secret.startswith("sandbox_mock")
        )
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str:
        """Fetches or refreshes OAuth 2.0 Bearer access token from PayPal Sandbox."""
        if self.mock_mode:
            return "mock_sandbox_access_token_agentpay_2026"

        now = time.time()
        if self._cached_token and now < (self._token_expires_at - 60):
            return self._cached_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYPAL_SANDBOX_BASE}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            self._cached_token = data["access_token"]
            self._token_expires_at = now + data.get("expires_in", 3600)
            return self._cached_token

    async def create_order(
        self,
        amount_usd: float,
        description: str,
        custom_id: str,
        return_url: str = "https://agentpay.shivysidinfo.tech/paypal/return",
        cancel_url: str = "https://agentpay.shivysidinfo.tech/paypal/cancel",
    ) -> Dict[str, Any]:
        """Creates a PayPal Orders v2 transaction for escrow locking."""
        if self.mock_mode:
            order_id = f"ORDER_SANDBOX_{int(time.time()*1000)}"
            return {
                "id": order_id,
                "status": "CREATED",
                "mock": True,
                "links": [
                    {
                        "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
                        "rel": "approve",
                        "method": "GET",
                    },
                    {
                        "href": f"{PAYPAL_SANDBOX_BASE}/v2/checkout/orders/{order_id}/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
                "gross_amount": f"{amount_usd:.2f}",
                "currency": "USD",
                "custom_id": custom_id,
                "description": description,
            }

        token = await self.get_access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": custom_id,
                    "description": description[:127],
                    "custom_id": custom_id,
                    "amount": {
                        "currency_code": "USD",
                        "value": f"{amount_usd:.2f}",
                    },
                }
            ],
            "application_context": {
                "brand_name": "AgentPay Protocol",
                "landing_page": "NO_PREFERENCE",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYPAL_SANDBOX_BASE}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Captures a pre-authorized PayPal order into escrow."""
        if self.mock_mode or order_id.startswith("ORDER_SANDBOX_"):
            capture_id = f"CAPTURE_{int(time.time()*1000)}"
            return {
                "id": capture_id,
                "status": "COMPLETED",
                "mock": True,
                "order_id": order_id,
                "final_capture": True,
            }

        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYPAL_SANDBOX_BASE}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={},
            )
            resp.raise_for_status()
            return resp.json()

    async def execute_payout(
        self,
        receiver_email: str,
        amount_usd: float,
        note: str,
        sender_item_id: str,
    ) -> Dict[str, Any]:
        """Dispatches an autonomous payout via PayPal Payouts v1."""
        if self.mock_mode:
            batch_id = f"PAYOUT_BATCH_{int(time.time()*1000)}"
            return {
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "receiver": receiver_email,
                    "amount": f"{amount_usd:.2f}",
                    "note": note,
                },
                "mock": True,
            }

        token = await self.get_access_token()
        payload = {
            "sender_batch_header": {
                "sender_batch_id": f"batch_{int(time.time()*1000)}",
                "email_subject": "AgentPay Protocol: Autonomous Work Payout",
                "email_message": note,
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": f"{amount_usd:.2f}",
                        "currency": "USD",
                    },
                    "note": note,
                    "sender_item_id": sender_item_id,
                    "receiver": receiver_email,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYPAL_SANDBOX_BASE}/v1/payments/payouts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
