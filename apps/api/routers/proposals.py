from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_db, get_semantic_verifier
from apps.api.services import agent_service, intent_service, verify_service
from packages.commerce_agent.agent import AgentFailed
from packages.payment_gateway.schemas import GrantView, PaymentRecord
from packages.verification_engine.schemas import (
    Decision,
    HardConstraintResult,
    ProposedAction,
    RiskAssessment,
    SemanticAssessment,
)

router = APIRouter(prefix="/v1", tags=["proposals"])


class ProposalEvaluation(BaseModel):
    proposal_id: UUID
    intent_id: UUID
    fingerprint: str
    hard: HardConstraintResult
    semantic: SemanticAssessment
    risk: RiskAssessment
    decision: Decision
    proposal: ProposedAction
    goal: str
    raw_request: str
    max_amount: float
    grant: GrantView | None = None
    payment: PaymentRecord | None = None
    decision_id: UUID | None = None
    resolution: str | None = None


def _to_evaluation(record: verify_service.ProposalRecord) -> ProposalEvaluation:
    return ProposalEvaluation(
        proposal_id=record.proposal_id,
        intent_id=record.intent_id,
        fingerprint=record.fingerprint,
        hard=record.hard,
        semantic=record.semantic,
        risk=record.risk,
        decision=record.decision,
        proposal=record.proposal,
        goal=record.goal,
        raw_request=record.raw_request,
        max_amount=record.max_amount,
        grant=record.grant,
        payment=record.payment,
        decision_id=record.decision_id,
        resolution=record.resolution,
    )


@router.post("/intents/{intent_id}/proposals", response_model=ProposalEvaluation)
def submit_proposal(
    intent_id: UUID,
    body: ProposedAction,
    db: Session = Depends(get_db),
    verifier=Depends(get_semantic_verifier),
) -> ProposalEvaluation:
    try:
        record = verify_service.submit_proposal(db, intent_id, body, verifier=verifier)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    except verify_service.IntentNotActive as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    return _to_evaluation(record)


@router.get("/intents/{intent_id}/decision", response_model=ProposalEvaluation)
def read_latest_decision(
    intent_id: UUID,
    db: Session = Depends(get_db),
) -> ProposalEvaluation:
    try:
        record = verify_service.latest_decision(db, intent_id)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    except verify_service.DecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="No decision yet") from exc
    return _to_evaluation(record)


class AgentStep(BaseModel):
    tool: str
    detail: str


class AgentRunResponse(BaseModel):
    intent_id: UUID
    steps: list[AgentStep]
    would_charge: bool = False
    evaluation: ProposalEvaluation | None = None


class ActivityEvent(BaseModel):
    id: int
    ts: str | None
    actor: str
    event_type: str
    payload: dict


class AgentRunRequest(BaseModel):
    inject: str | None = None
    force_agent_fail: bool = False


@router.post("/intents/{intent_id}/run", response_model=AgentRunResponse)
def run_commerce_agent(
    intent_id: UUID,
    body: AgentRunRequest | None = None,
    db: Session = Depends(get_db),
    verifier=Depends(get_semantic_verifier),
) -> AgentRunResponse:
    inject = body.inject if body is not None else None
    force_agent_fail = body.force_agent_fail if body is not None else False
    try:
        result = agent_service.run_intent(
            db,
            intent_id,
            verifier=verifier,
            inject=inject,
            force_agent_fail=force_agent_fail,
        )
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    except verify_service.IntentNotActive as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except AgentFailed as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    evaluation = _to_evaluation(result.evaluation) if result.evaluation else None
    return AgentRunResponse(
        intent_id=result.intent_id,
        steps=[AgentStep(tool=step["tool"], detail=step["detail"]) for step in result.steps],
        would_charge=result.would_charge,
        evaluation=evaluation,
    )


@router.get("/intents/{intent_id}/activity", response_model=list[ActivityEvent])
def read_activity(intent_id: UUID, db: Session = Depends(get_db)) -> list[ActivityEvent]:
    try:
        events = agent_service.list_activity(db, intent_id)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    return [ActivityEvent.model_validate(item) for item in events]


class AuditEventView(BaseModel):
    id: int
    ts: str | None
    actor: str
    event_type: str
    title: str
    payload: dict
    tone: str = "default"


@router.get("/intents/{intent_id}/audit", response_model=list[AuditEventView])
def read_audit(intent_id: UUID, db: Session = Depends(get_db)) -> list[AuditEventView]:
    from apps.api.services import audit_service

    try:
        intent_service.get_intent(db, intent_id)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    return [AuditEventView.model_validate(item) for item in audit_service.list_timeline(db, intent_id)]
