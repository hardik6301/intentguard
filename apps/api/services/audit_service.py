from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.db import AuditEvent

_TITLES = {
    "intent_compiled": "Intent compiled",
    "intent_activated": "Contract confirmed",
    "agent_started": "Agent started",
    "agent_step": "Agent tool",
    "agent_failed": "Agent failed",
    "proposal_submitted": "Proposal submitted",
    "hard_constraints_checked": "Hard constraints checked",
    "semantic_assessed": "Semantic verification",
    "risk_assessed": "Risk assessed",
    "decision_made": "Decision recorded",
    "grant_minted": "Grant minted",
    "payment_created": "Payment created",
    "payment_succeeded": "Payment succeeded",
    "payment_timeout": "Payment status unknown",
    "razorpay_order_created": "Razorpay order created",
    "pause_confirmed": "User confirmed pause",
    "pause_rejected": "User rejected pause",
    "payment_not_initiated": "Payment was not initiated",
}

_BLOCK_TYPES = {
    "payment_not_initiated",
    "pause_rejected",
    "agent_failed",
}


def record(
    db: Session,
    *,
    intent_id: UUID,
    actor: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        intent_id=intent_id,
        actor=actor,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)
    return event


def list_timeline(db: Session, intent_id: UUID) -> list[dict[str, object]]:
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.intent_id == intent_id).order_by(AuditEvent.id.asc())
    ).all()
    events: list[dict[str, object]] = []
    for row in rows:
        event_type = row.event_type
        payload = row.payload or {}
        tone = "default"
        if event_type in _BLOCK_TYPES or payload.get("verdict") == "BLOCK":
            tone = "block"
        elif payload.get("verdict") == "APPROVE" or event_type in {"grant_minted", "payment_succeeded", "pause_confirmed"}:
            tone = "approve"
        elif payload.get("verdict") == "PAUSE":
            tone = "pause"
        events.append(
            {
                "id": row.id,
                "ts": row.ts.isoformat() if row.ts else None,
                "actor": row.actor,
                "event_type": event_type,
                "title": _TITLES.get(event_type, event_type.replace("_", " ")),
                "payload": payload,
                "tone": tone,
            }
        )
    return events
