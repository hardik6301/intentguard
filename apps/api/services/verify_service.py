from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from apps.api.config import get_settings
from apps.api.models.db import AuthorizationGrant
from apps.api.models.db import Decision as DecisionRow
from apps.api.models.db import Intent, IntentStatus, Proposal, Verification
from apps.api.services import audit_service, intent_service, payment_service
from packages.payment_gateway.grants import mint_grant, to_view
from packages.payment_gateway.schemas import GrantView, PaymentRecord
from packages.verification_engine.constraint_checker import check_constraints
from packages.verification_engine.decision_engine import decide
from packages.verification_engine.fingerprint import proposal_fingerprint
from packages.verification_engine.risk import assess_risk
from packages.verification_engine.schemas import (
    Decision,
    HardConstraintResult,
    ProposedAction,
    RiskAssessment,
    SemanticAssessment,
    Verdict,
)


class IntentNotActive(Exception):
    def __init__(self, message: str = "Intent must be active before a proposal can be submitted") -> None:
        super().__init__(message)
        self.message = message


class DecisionNotFound(Exception):
    pass


class PauseNotResolvable(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProposalRecord:
    def __init__(
        self,
        *,
        proposal_id: UUID,
        intent_id: UUID,
        fingerprint: str,
        hard: HardConstraintResult,
        semantic: SemanticAssessment,
        risk: RiskAssessment,
        decision: Decision,
        proposal: ProposedAction,
        goal: str,
        raw_request: str,
        max_amount: float,
        grant: GrantView | None = None,
        payment: PaymentRecord | None = None,
        decision_id: UUID | None = None,
        resolution: str | None = None,
    ) -> None:
        self.proposal_id = proposal_id
        self.intent_id = intent_id
        self.fingerprint = fingerprint
        self.hard = hard
        self.semantic = semantic
        self.risk = risk
        self.decision = decision
        self.proposal = proposal
        self.goal = goal
        self.raw_request = raw_request
        self.max_amount = max_amount
        self.grant = grant
        self.payment = payment
        self.decision_id = decision_id
        self.resolution = resolution


def submit_proposal(
    db: Session,
    intent_id: UUID,
    proposal: ProposedAction,
    *,
    verifier,
) -> ProposalRecord:
    record = intent_service.get_intent(db, intent_id)
    if record.status.value not in {IntentStatus.ACTIVE.value, IntentStatus.APPROVED.value, IntentStatus.PAUSED.value}:
        raise IntentNotActive()
    contract = record.contract
    existing = set(
        db.scalars(select(Proposal.fingerprint).where(Proposal.intent_id == intent_id)).all()
    )
    fingerprint = proposal_fingerprint(intent_id, proposal)
    hard = check_constraints(
        contract,
        proposal,
        existing_fingerprints=existing,
    )
    risk = assess_risk(proposal)
    semantic = verifier.verify(contract, proposal)
    proposal_id = uuid4()
    decision = decide(hard, semantic, risk, proposal_id=proposal_id)

    db.add(
        Proposal(
            id=proposal_id,
            intent_id=intent_id,
            payload=proposal.model_dump(mode="json"),
            fingerprint=fingerprint,
        )
    )
    db.add(
        Verification(
            proposal_id=proposal_id,
            hard_result=hard.model_dump(mode="json"),
            semantic_result=semantic.model_dump(mode="json"),
            risk_result=risk.model_dump(mode="json"),
        )
    )
    decision_row_id = uuid4()
    db.add(
        DecisionRow(
            id=decision_row_id,
            proposal_id=proposal_id,
            verdict=decision.verdict.value,
            reasons=decision.reasons,
            policy_version=decision.policy_version,
        )
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="agent",
        event_type="proposal_submitted",
        payload={"proposal_id": str(proposal_id), "fingerprint": fingerprint},
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="constraints",
        event_type="hard_constraints_checked",
        payload={"passed": hard.passed, "failures": [item.model_dump() for item in hard.failures]},
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="verifier",
        event_type="semantic_assessed",
        payload=semantic.model_dump(mode="json"),
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="verifier",
        event_type="risk_assessed",
        payload=risk.model_dump(mode="json"),
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="decision",
        event_type="decision_made",
        payload={
            "verdict": decision.verdict.value,
            "reasons": decision.reasons,
            "policy_version": decision.policy_version,
        },
    )
    intent_row = db.get(Intent, intent_id)
    grant_view: GrantView | None = None
    if intent_row is not None:
        if decision.verdict == Verdict.APPROVE:
            settings = get_settings()
            grant_row, token = mint_grant(
                db,
                intent_id=intent_id,
                proposal_id=proposal_id,
                amount=proposal.amount,
                currency=proposal.currency,
                ttl_seconds=settings.grant_ttl_seconds,
                secret=settings.grant_signing_secret,
            )
            intent_row.status = IntentStatus.APPROVED.value
            grant_view = to_view(grant_row, settings.grant_signing_secret, include_token=True)
            grant_view.token = token
            audit_service.record(
                db,
                intent_id=intent_id,
                actor="decision",
                event_type="grant_minted",
                payload={
                    "grant_id": str(grant_row.id),
                    "amount": float(proposal.amount),
                    "currency": proposal.currency,
                },
            )
        elif decision.verdict == Verdict.BLOCK:
            intent_row.status = IntentStatus.BLOCKED.value
            audit_service.record(
                db,
                intent_id=intent_id,
                actor="payment",
                event_type="payment_not_initiated",
                payload={"verdict": "BLOCK"},
            )
        elif decision.verdict == Verdict.PAUSE:
            intent_row.status = IntentStatus.PAUSED.value
    db.commit()
    return ProposalRecord(
        proposal_id=proposal_id,
        intent_id=intent_id,
        fingerprint=fingerprint,
        hard=hard,
        semantic=semantic,
        risk=risk,
        decision=decision,
        proposal=proposal,
        goal=contract.goal,
        raw_request=contract.raw_request,
        max_amount=float(contract.hard_constraints.max_amount),
        grant=grant_view,
        payment=None,
        decision_id=decision_row_id,
        resolution="pending" if decision.verdict == Verdict.PAUSE else None,
    )


def latest_decision(db: Session, intent_id: UUID) -> ProposalRecord:
    intent_service.get_intent(db, intent_id)
    row = db.scalars(
        select(Proposal)
        .where(Proposal.intent_id == intent_id)
        .order_by(Proposal.created_at.desc())
        .limit(1)
    ).first()
    if row is None or row.verification is None or row.decision is None:
        raise DecisionNotFound()
    proposal = ProposedAction.model_validate(row.payload)
    hard = HardConstraintResult.model_validate(row.verification.hard_result)
    semantic = SemanticAssessment.model_validate(row.verification.semantic_result)
    risk = RiskAssessment.model_validate(row.verification.risk_result)
    contract = intent_service.get_intent(db, intent_id).contract
    settings = get_settings()
    grant_row = db.scalars(
        select(AuthorizationGrant).where(AuthorizationGrant.proposal_id == row.id)
    ).first()
    grant_view = (
        to_view(grant_row, settings.grant_signing_secret, include_token=True) if grant_row else None
    )
    payment = None
    if grant_row is not None and grant_row.payment is not None:
        payment = payment_service.get_payment(db, grant_row.payment.id)
    intent = db.get(Intent, intent_id)
    return ProposalRecord(
        proposal_id=row.id,
        intent_id=intent_id,
        fingerprint=row.fingerprint,
        hard=hard,
        semantic=semantic,
        risk=risk,
        decision=Decision(
            verdict=row.decision.verdict,
            reasons=list(row.decision.reasons),
            policy_version=row.decision.policy_version,
            proposal_id=row.id,
        ),
        proposal=proposal,
        goal=contract.goal,
        raw_request=contract.raw_request,
        max_amount=float(contract.hard_constraints.max_amount),
        grant=grant_view,
        payment=payment,
        decision_id=row.decision.id,
        resolution=_resolution(intent.status if intent else None, row.decision.verdict, grant_view),
    )


def _resolution(intent_status: str | None, verdict: str, grant: GrantView | None) -> str | None:
    if verdict != Verdict.PAUSE.value:
        return None
    if grant is not None:
        return "confirmed"
    if intent_status == IntentStatus.BLOCKED.value:
        return "rejected"
    return "pending"


def resolve_pause(db: Session, decision_id: UUID, action: str) -> ProposalRecord:
    row = db.get(DecisionRow, decision_id)
    if row is None or row.proposal is None:
        raise DecisionNotFound()
    if row.verdict != Verdict.PAUSE.value:
        raise PauseNotResolvable("Only a PAUSE decision can be confirmed or rejected")
    proposal = ProposedAction.model_validate(row.proposal.payload)
    intent_id = row.proposal.intent_id
    intent = db.get(Intent, intent_id)
    if intent is None:
        raise DecisionNotFound()
    existing_grant = db.scalars(
        select(AuthorizationGrant).where(AuthorizationGrant.proposal_id == row.proposal_id)
    ).first()
    if existing_grant is not None:
        raise PauseNotResolvable("This pause has already been confirmed")
    if intent.status == IntentStatus.BLOCKED.value:
        raise PauseNotResolvable("This pause has already been rejected")
    if action == "reject":
        intent.status = IntentStatus.BLOCKED.value
        reasons = list(row.reasons) if isinstance(row.reasons, list) else []
        if "User rejected the proposed action." not in reasons:
            reasons.append("User rejected the proposed action.")
        row.reasons = reasons
        flag_modified(row, "reasons")
        audit_service.record(
            db,
            intent_id=intent_id,
            actor="user",
            event_type="pause_rejected",
            payload={"decision_id": str(row.id), "reason": "user_rejected"},
        )
        audit_service.record(
            db,
            intent_id=intent_id,
            actor="payment",
            event_type="payment_not_initiated",
            payload={"verdict": "BLOCK", "reason": "user_rejected"},
        )
        db.commit()
        return latest_decision(db, intent_id)
    if action != "confirm":
        raise PauseNotResolvable("Action must be confirm or reject")
    settings = get_settings()
    grant_row, token = mint_grant(
        db,
        intent_id=intent_id,
        proposal_id=row.proposal_id,
        amount=proposal.amount,
        currency=proposal.currency,
        ttl_seconds=settings.grant_ttl_seconds,
        secret=settings.grant_signing_secret,
    )
    intent.status = IntentStatus.APPROVED.value
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="user",
        event_type="pause_confirmed",
        payload={"decision_id": str(row.id), "grant_id": str(grant_row.id)},
    )
    audit_service.record(
        db,
        intent_id=intent_id,
        actor="decision",
        event_type="grant_minted",
        payload={
            "grant_id": str(grant_row.id),
            "amount": float(proposal.amount),
            "currency": proposal.currency,
            "source": "pause_confirm",
        },
    )
    db.commit()
    record = latest_decision(db, intent_id)
    if record.grant is not None:
        record.grant.token = token
    return record
