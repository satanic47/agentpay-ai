"""
AgentPay AI Policy Guard Engine.
Evaluates agent purchase requests against user semantic guardrails,
daily spending pacing, and risk classification.
"""

from typing import Dict, List, Tuple
from core.models import (
    SpendingPolicy,
    AgentPurchaseRequest,
    PolicyEvaluationResult,
    TransactionStatus,
    RiskTier,
    AgentCapability,
)


class PolicyGuardEngine:
    def __init__(self):
        # In-memory daily spend ledger: {agent_id: cumulative_spent_today}
        self.daily_spend_ledger: Dict[str, float] = {}
        # Default policies by agent_id
        self.policies: Dict[str, SpendingPolicy] = {}

    def register_policy(self, policy: SpendingPolicy):
        self.policies[policy.agent_id] = policy

    def get_policy(self, agent_id: str) -> SpendingPolicy:
        if agent_id not in self.policies:
            # Default safe policy
            self.policies[agent_id] = SpendingPolicy(agent_id=agent_id)
        return self.policies[agent_id]

    def reset_daily_ledger(self):
        self.daily_spend_ledger.clear()

    def evaluate_request(self, request: AgentPurchaseRequest) -> PolicyEvaluationResult:
        policy = self.get_policy(request.buyer_agent_id)
        matched_rules: List[str] = []
        current_spent = self.daily_spend_ledger.get(request.buyer_agent_id, 0.0)

        # Rule 1: Capability Whitelist
        if request.capability not in policy.allowed_capabilities:
            return PolicyEvaluationResult(
                allowed=False,
                status=TransactionStatus.REJECTED,
                risk_tier=RiskTier.PROHIBITED,
                reason=f"Capability '{request.capability.value}' is not permitted by user spending policy.",
                matched_rules=["RULE_CAPABILITY_WHITELIST_FAIL"],
                suggested_action="Reject transaction. Update agent policy to grant this capability if required.",
                paypal_order_required=False,
            )
        matched_rules.append("RULE_CAPABILITY_PERMITTED")

        # Rule 2: Per-Transaction Hard Limit
        if request.amount_usd > policy.per_tx_max_usd:
            return PolicyEvaluationResult(
                allowed=False,
                status=TransactionStatus.ESCALATED_TO_HUMAN,
                risk_tier=RiskTier.HIGH_RISK,
                reason=f"Purchase amount (${request.amount_usd:.2f}) exceeds per-transaction limit (${policy.per_tx_max_usd:.2f}).",
                matched_rules=["RULE_PER_TX_LIMIT_EXCEEDED"],
                suggested_action="Escalate to human supervisor for manual multi-factor sign-off.",
                paypal_order_required=True,
            )
        matched_rules.append("RULE_PER_TX_LIMIT_PASS")

        # Rule 3: Daily Cumulative Budget
        projected_spend = current_spent + request.amount_usd
        if projected_spend > policy.daily_budget_usd:
            return PolicyEvaluationResult(
                allowed=False,
                status=TransactionStatus.ESCALATED_TO_HUMAN,
                risk_tier=RiskTier.HIGH_RISK,
                reason=f"Projected daily spend (${projected_spend:.2f}) exceeds daily cap (${policy.daily_budget_usd:.2f}). Current spent: ${current_spent:.2f}.",
                matched_rules=["RULE_DAILY_BUDGET_EXCEEDED"],
                suggested_action="Hold transaction in escrow queue until daily cap resets or human approves top-up.",
                paypal_order_required=True,
            )
        matched_rules.append("RULE_DAILY_BUDGET_PASS")

        # Rule 4: Human Confirmation Threshold
        if request.amount_usd >= policy.require_human_confirmation_over_usd:
            return PolicyEvaluationResult(
                allowed=True,
                status=TransactionStatus.ESCALATED_TO_HUMAN,
                risk_tier=RiskTier.MEDIUM_RISK,
                reason=f"Amount (${request.amount_usd:.2f}) requires human supervisor confirmation before lock.",
                matched_rules=["RULE_HUMAN_CONFIRMATION_TRIGGERED"],
                suggested_action="Present transaction card in human supervisor review queue.",
                paypal_order_required=True,
            )

        # Rule 5: Auto-Approve Tier
        if request.amount_usd <= policy.auto_approve_threshold_usd:
            # Commit to daily spend
            self.daily_spend_ledger[request.buyer_agent_id] = projected_spend
            return PolicyEvaluationResult(
                allowed=True,
                status=TransactionStatus.AUTO_APPROVED,
                risk_tier=RiskTier.LOW_RISK,
                reason=f"Within pre-authorized autonomous limits (${request.amount_usd:.2f} <= ${policy.auto_approve_threshold_usd:.2f}).",
                matched_rules=["RULE_AUTO_APPROVE_LOW_RISK"],
                suggested_action="Authorize instant PayPal Sandbox Order creation & escrow capture.",
                paypal_order_required=True,
            )

        # Default fallback
        return PolicyEvaluationResult(
            allowed=True,
            status=TransactionStatus.PENDING_POLICY,
            risk_tier=RiskTier.LOW_RISK,
            reason="Approved with standard sandbox verification.",
            matched_rules=["RULE_STANDARD_CLEARANCE"],
            suggested_action="Lock into PayPal Escrow.",
            paypal_order_required=True,
        )
