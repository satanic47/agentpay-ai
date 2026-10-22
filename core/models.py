"""
AgentPay AI Data Models & Pydantic Schemas.
Strict v2 models covering Agent Wallets, Escrow, Invoices, and Policy Rules.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time


class RiskTier(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    PROHIBITED = "PROHIBITED"


class TransactionStatus(str, Enum):
    PENDING_POLICY = "PENDING_POLICY"
    AUTO_APPROVED = "AUTO_APPROVED"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"
    ESCROW_LOCKED = "ESCROW_LOCKED"
    SETTLED_PAYOUT = "SETTLED_PAYOUT"
    REJECTED = "REJECTED"


class AgentCapability(str, Enum):
    GPU_COMPUTE = "GPU_COMPUTE"
    DATASET_LICENSE = "DATASET_LICENSE"
    CODE_AUDIT = "CODE_AUDIT"
    API_SUBSCRIPTION = "API_SUBSCRIPTION"
    LEGAL_RESEARCH = "LEGAL_RESEARCH"
    IMAGE_SYNTHESIS = "IMAGE_SYNTHESIS"


class SpendingPolicy(BaseModel):
    policy_id: str = Field(default_factory=lambda: f"pol_{int(time.time()*1000)}")
    agent_id: str
    daily_budget_usd: float = Field(default=50.0, ge=0.0)
    per_tx_max_usd: float = Field(default=20.0, ge=0.0)
    allowed_capabilities: List[AgentCapability] = Field(
        default_factory=lambda: [
            AgentCapability.GPU_COMPUTE,
            AgentCapability.DATASET_LICENSE,
            AgentCapability.API_SUBSCRIPTION,
        ]
    )
    auto_approve_threshold_usd: float = Field(default=15.0, ge=0.0)
    require_human_confirmation_over_usd: float = Field(default=25.0, ge=0.0)
    created_at: float = Field(default_factory=time.time)


class AgentPurchaseRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{int(time.time()*1000)}")
    buyer_agent_id: str
    buyer_agent_name: str
    vendor_agent_id: str
    vendor_agent_name: str
    capability: AgentCapability
    item_description: str
    amount_usd: float = Field(gt=0.0)
    currency: str = "USD"
    work_spec_hash: Optional[str] = None
    vendor_paypal_email: str
    created_at: float = Field(default_factory=time.time)


class PolicyEvaluationResult(BaseModel):
    allowed: bool
    status: TransactionStatus
    risk_tier: RiskTier
    reason: str
    matched_rules: List[str]
    suggested_action: str
    paypal_order_required: bool = False
    evaluated_at: float = Field(default_factory=time.time)


class EscrowRecord(BaseModel):
    escrow_id: str = Field(default_factory=lambda: f"esc_{int(time.time()*1000)}")
    request: AgentPurchaseRequest
    policy_result: PolicyEvaluationResult
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    paypal_payout_batch_id: Optional[str] = None
    status: TransactionStatus
    human_approved: bool = False
    cryptographic_proof_verified: bool = False
    settled_at: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
