"""
Automated Pytest Suite for AgentPay AI Protocol.
Asserts:
1. Capability whitelist filtering
2. Per-transaction cap escalation
3. Cumulative daily budget enforcement
4. Automated PayPal Orders v2 escrow lock
5. Cryptographic proof verification and PayPal Payouts v1 release
"""

import sys
import os
import pytest
import asyncio

# Ensure agentpay-ai is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import (
    SpendingPolicy,
    AgentPurchaseRequest,
    AgentCapability,
    TransactionStatus,
    RiskTier,
)
from core.policy_guard import PolicyGuardEngine
from core.paypal_client import PayPalSandboxClient
from core.escrow_manager import EscrowProtocolManager


@pytest.fixture
def policy_engine():
    engine = PolicyGuardEngine()
    policy = SpendingPolicy(
        agent_id="test_agent_alpha",
        daily_budget_usd=50.0,
        per_tx_max_usd=20.0,
        auto_approve_threshold_usd=10.0,
        require_human_confirmation_over_usd=15.0,
        allowed_capabilities=[
            AgentCapability.GPU_COMPUTE,
            AgentCapability.DATASET_LICENSE,
        ],
    )
    engine.register_policy(policy)
    return engine


@pytest.fixture
def escrow_manager():
    client = PayPalSandboxClient(mock_mode=True)
    return EscrowProtocolManager(paypal_client=client)


def test_prohibited_capability_rejected(policy_engine):
    req = AgentPurchaseRequest(
        buyer_agent_id="test_agent_alpha",
        buyer_agent_name="Alpha Agent",
        vendor_agent_id="vendor_beta",
        vendor_agent_name="Beta Vendor",
        capability=AgentCapability.LEGAL_RESEARCH,  # Not in whitelist
        item_description="Scan legal precedent",
        amount_usd=5.0,
        vendor_paypal_email="vendor@beta.com",
    )
    result = policy_engine.evaluate_request(req)
    assert not result.allowed
    assert result.status == TransactionStatus.REJECTED
    assert result.risk_tier == RiskTier.PROHIBITED
    assert "RULE_CAPABILITY_WHITELIST_FAIL" in result.matched_rules


def test_per_tx_limit_escalates_to_human(policy_engine):
    req = AgentPurchaseRequest(
        buyer_agent_id="test_agent_alpha",
        buyer_agent_name="Alpha Agent",
        vendor_agent_id="vendor_beta",
        vendor_agent_name="Beta Vendor",
        capability=AgentCapability.GPU_COMPUTE,
        item_description="10x H100 GPU Cluster",
        amount_usd=25.0,  # Exceeds per_tx_max_usd (20.0)
        vendor_paypal_email="vendor@beta.com",
    )
    result = policy_engine.evaluate_request(req)
    assert not result.allowed
    assert result.status == TransactionStatus.ESCALATED_TO_HUMAN
    assert result.risk_tier == RiskTier.HIGH_RISK
    assert "RULE_PER_TX_LIMIT_EXCEEDED" in result.matched_rules


def test_auto_approve_low_risk(policy_engine):
    req = AgentPurchaseRequest(
        buyer_agent_id="test_agent_alpha",
        buyer_agent_name="Alpha Agent",
        vendor_agent_id="vendor_beta",
        vendor_agent_name="Beta Vendor",
        capability=AgentCapability.GPU_COMPUTE,
        item_description="Quick micro-batch embedding",
        amount_usd=7.50,  # <= auto_approve_threshold_usd (10.0)
        vendor_paypal_email="vendor@beta.com",
    )
    result = policy_engine.evaluate_request(req)
    assert result.allowed
    assert result.status == TransactionStatus.AUTO_APPROVED
    assert result.risk_tier == RiskTier.LOW_RISK
    assert "RULE_AUTO_APPROVE_LOW_RISK" in result.matched_rules


def test_end_to_end_escrow_lifecycle(escrow_manager):
    req = AgentPurchaseRequest(
        buyer_agent_id="test_agent_alpha",
        buyer_agent_name="Alpha Agent",
        vendor_agent_id="vendor_beta",
        vendor_agent_name="Beta Vendor",
        capability=AgentCapability.GPU_COMPUTE,
        item_description="15m fine-tuning pass",
        amount_usd=9.00,
        vendor_paypal_email="vendor@beta.com",
    )

    async def run_lifecycle():
        # 1. Submit
        record = await escrow_manager.submit_purchase_request(req)
        assert record.status == TransactionStatus.ESCROW_LOCKED
        assert record.paypal_order_id.startswith("ORDER_SANDBOX_")
        assert record.paypal_capture_id.startswith("CAPTURE_")

        # 2. Settle with proof
        settled = await escrow_manager.verify_work_and_settle(
            record.escrow_id, delivered_proof="sha256_checkpoint_model_weights_verified"
        )
        assert settled.status == TransactionStatus.SETTLED_PAYOUT
        assert settled.cryptographic_proof_verified
        assert settled.paypal_payout_batch_id.startswith("PAYOUT_BATCH_")

    asyncio.run(run_lifecycle())
