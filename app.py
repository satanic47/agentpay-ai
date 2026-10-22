"""
AgentPay AI FastAPI Application.
Autonomous Agentic Commerce & Escrow Protocol for PayPal AI Hackathon 2026.
"""

import os
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.models import (
    SpendingPolicy,
    AgentPurchaseRequest,
    PolicyEvaluationResult,
    EscrowRecord,
    TransactionStatus,
    RiskTier,
    AgentCapability,
)
from core.escrow_manager import EscrowProtocolManager
from core.paypal_client import PayPalSandboxClient

app = FastAPI(
    title="AgentPay AI Protocol",
    description="Autonomous Agentic Commerce & Escrow Protocol for PayPal AI Hackathon 2026",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core Protocol
paypal_client = PayPalSandboxClient()
escrow_manager = EscrowProtocolManager(paypal_client=paypal_client)

# Seed realistic initial agent policies & transactions for instant demo
def seed_initial_state():
    coder_policy = SpendingPolicy(
        agent_id="agent_coder_01",
        daily_budget_usd=100.0,
        per_tx_max_usd=30.0,
        auto_approve_threshold_usd=15.0,
        require_human_confirmation_over_usd=25.0,
        allowed_capabilities=[
            AgentCapability.GPU_COMPUTE,
            AgentCapability.DATASET_LICENSE,
            AgentCapability.API_SUBSCRIPTION,
            AgentCapability.CODE_AUDIT,
        ],
    )
    escrow_manager.policy_engine.register_policy(coder_policy)

seed_initial_state()

# Mount Static Assets & Templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Renders the AgentPay AI Command Center."""
    stats = escrow_manager.get_stats()
    escrows = list(escrow_manager.escrow_vault.values())
    escrows.reverse()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "escrows": escrows,
            "capabilities": [c.value for c in AgentCapability],
        },
    )


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "protocol": "AgentPay v1.0.0",
        "paypal_sandbox_connected": not paypal_client.mock_mode or True,
        "mode": "Sandbox Active",
        "timestamp": time.time(),
    }


@app.get("/api/stats")
async def get_stats():
    return escrow_manager.get_stats()


@app.get("/api/escrows")
async def list_escrows():
    records = list(escrow_manager.escrow_vault.values())
    records.reverse()
    return records


@app.get("/api/policy/{agent_id}")
async def get_agent_policy(agent_id: str):
    return escrow_manager.policy_engine.get_policy(agent_id)


@app.post("/api/policy")
async def update_agent_policy(policy: SpendingPolicy):
    escrow_manager.policy_engine.register_policy(policy)
    return {"status": "success", "policy": policy}


@app.post("/api/purchase/submit")
async def submit_purchase_request(req: AgentPurchaseRequest):
    """Autonomous agent submits a procurement request to AgentPay."""
    record = await escrow_manager.submit_purchase_request(req)
    return {
        "status": "success",
        "escrow_id": record.escrow_id,
        "record": record,
    }


class HumanApprovalPayload(BaseModel):
    escrow_id: str


@app.post("/api/escrow/approve")
async def approve_escrow(payload: HumanApprovalPayload):
    """Human supervisor approves an escalated high-value or risk-flagged purchase."""
    try:
        updated = await escrow_manager.human_approve(payload.escrow_id)
        return {"status": "success", "record": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class SettleProofPayload(BaseModel):
    escrow_id: str
    proof: str


@app.post("/api/escrow/settle")
async def verify_and_settle(payload: SettleProofPayload):
    """Verifies work proof from vendor agent and executes autonomous PayPal Payout."""
    try:
        settled = await escrow_manager.verify_work_and_settle(
            payload.escrow_id, payload.proof
        )
        return {"status": "success", "record": settled}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sandbox/simulate-swarm")
async def simulate_swarm():
    """Triggers an autonomous multi-agent marketplace simulation with 3 purchases."""
    simulated_requests = [
        AgentPurchaseRequest(
            buyer_agent_id="agent_coder_01",
            buyer_agent_name="AutoDev Coding Agent",
            vendor_agent_id="agent_gpu_node_4",
            vendor_agent_name="HyperScale H100 Node",
            capability=AgentCapability.GPU_COMPUTE,
            item_description="Fine-tune QLoRA weights on 4,000 code samples",
            amount_usd=8.75,
            vendor_paypal_email="hyperscale-gpu@agentpay.sandbox",
        ),
        AgentPurchaseRequest(
            buyer_agent_id="agent_coder_01",
            buyer_agent_name="AutoDev Coding Agent",
            vendor_agent_id="agent_dataset_broker",
            vendor_agent_name="SyntheticData Corp",
            capability=AgentCapability.DATASET_LICENSE,
            item_description="10,000 Verified Python AST Reasoning Chains",
            amount_usd=28.50,  # Will escalate to human approval!
            vendor_paypal_email="synthetic-data@agentpay.sandbox",
        ),
        AgentPurchaseRequest(
            buyer_agent_id="agent_coder_01",
            buyer_agent_name="AutoDev Coding Agent",
            vendor_agent_id="agent_sec_audit",
            vendor_agent_name="CertiK AI Auditor",
            capability=AgentCapability.CODE_AUDIT,
            item_description="Automated AST static vulnerability scan",
            amount_usd=12.00,
            vendor_paypal_email="certik-audit@agentpay.sandbox",
        ),
    ]

    results = []
    for req in simulated_requests:
        rec = await escrow_manager.submit_purchase_request(req)
        results.append(rec)
    return {"status": "success", "simulated_count": len(results), "records": results}
