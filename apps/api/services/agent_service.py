from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.db import AuditEvent
from apps.api.services import audit_service, intent_service, verify_service
from packages.commerce_agent.agent import AgentFailed, run_agent
from packages.commerce_agent.tools import ToolBudget
from packages.verification_engine.forced import ForcedLowSemanticVerifier


class AgentRunResult:
    def __init__(
        self,
        *,
        intent_id: UUID,
        steps: list[dict[str, str]],
        evaluation: verify_service.ProposalRecord | None,
        would_charge: bool,
    ) -> None:
        self.intent_id = intent_id
        self.steps = steps
        self.evaluation = evaluation
        self.would_charge = would_charge


def run_intent(
    db: Session,
    intent_id: UUID,
    *,
    verifier,
    inject: str | None = None,
    force_agent_fail: bool = False,
) -> AgentRunResult:
    record = intent_service.get_intent(db, intent_id)
    if record.status.value != "active":
        raise verify_service.IntentNotActive("Intent must be active before the agent can run")
    if inject not in {None, "", "poison", "low_semantic"}:
        raise AgentFailed("Unknown injection flag.")
    tools = ToolBudget()
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="agent",
        event_type="agent_started",
        payload={"goal": record.contract.goal, "inject": inject or None},
    )
    if force_agent_fail:
        audit_service.record(
            db,
            intent_id=intent_id,
            actor="agent",
            event_type="agent_failed",
            payload={"message": "Forced agent failure for evaluation.", "steps": tools.steps},
        )
        db.commit()
        raise AgentFailed("Forced agent failure for evaluation.")
    if inject == "low_semantic":
        verifier = ForcedLowSemanticVerifier()
    suffix = "Ultra Deal" if inject == "poison" else None
    try:
        proposal, steps = run_agent(record.contract, tools=tools, query_suffix=suffix)
    except AgentFailed as exc:
        audit_service.record(
            db,
            intent_id=intent_id,
            actor="agent",
            event_type="agent_failed",
            payload={"message": exc.message, "steps": tools.steps},
        )
        db.commit()
        raise
    for step in steps:
        audit_service.record(
            db,
            intent_id=intent_id,
            actor="agent",
            event_type="agent_step",
            payload=step,
        )
    evaluation = verify_service.submit_proposal(db, intent_id, proposal, verifier=verifier)
    return AgentRunResult(
        intent_id=intent_id,
        steps=steps,
        evaluation=evaluation,
        would_charge=False,
    )


def list_activity(db: Session, intent_id: UUID) -> list[dict[str, object]]:
    intent_service.get_intent(db, intent_id)
    rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.intent_id == intent_id)
        .order_by(AuditEvent.id.asc())
    ).all()
    events: list[dict[str, object]] = []
    for row in rows:
        events.append(
            {
                "id": row.id,
                "ts": row.ts.isoformat() if row.ts else None,
                "actor": row.actor,
                "event_type": row.event_type,
                "payload": row.payload,
            }
        )
    return events
