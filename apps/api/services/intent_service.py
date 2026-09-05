from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.models.db import Intent, IntentStatus
from apps.api.services import audit_service
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.hashing import canonical_contract_payload, contract_hash
from packages.intent_compiler.schemas import (
    ActivateRequest,
    CompileFailed,
    CompileResponse,
    IntentContract,
    IntentRecord,
    IntentStatus as ContractStatus,
)


class IntentNotFound(Exception):
    pass


class IntentImmutable(Exception):
    def __init__(self, message: str = "Intent contracts are immutable") -> None:
        super().__init__(message)
        self.message = message


def _contract_from_row(row: Intent) -> IntentContract:
    payload = dict(row.contract)
    payload["status"] = row.status
    payload["intent_id"] = str(row.id)
    return IntentContract.model_validate(payload)


def compile_draft(db: Session, compiler: IntentCompiler, raw_request: str) -> CompileResponse:
    contract = compiler.compile(raw_request)
    assert contract.intent_id is not None
    digest = contract_hash(contract)
    stored = canonical_contract_payload(contract)
    row = Intent(
        id=contract.intent_id,
        raw_request=contract.raw_request,
        contract=stored,
        contract_hash=digest,
        status=IntentStatus.DRAFT.value,
        expires_at=contract.expires_at,
        created_at=contract.created_at,
    )
    db.add(row)
    audit_service.record(
        db,
        intent_id=contract.intent_id,
        actor="compiler",
        event_type="intent_compiled",
        payload={"contract_hash": digest, "goal": contract.goal},
    )
    db.commit()
    db.refresh(row)
    return CompileResponse(intent_id=row.id, contract=_contract_from_row(row), contract_hash=digest)


def activate_intent(db: Session, request: ActivateRequest) -> IntentRecord:
    row = db.get(Intent, request.intent_id)
    if row is None:
        raise IntentNotFound()
    if row.status != IntentStatus.DRAFT.value:
        raise IntentImmutable("Only a draft intent can be confirmed")
    if request.contract is not None:
        incoming = request.contract.model_copy(update={"intent_id": row.id})
        if contract_hash(incoming) != row.contract_hash:
            raise IntentImmutable("Submitted contract does not match the compiled hash")
    row.status = IntentStatus.ACTIVE.value
    audit_service.record(
        db,
        intent_id=row.id,
        actor="user",
        event_type="intent_activated",
        payload={"contract_hash": row.contract_hash},
    )
    db.commit()
    db.refresh(row)
    return _record(row)


def get_intent(db: Session, intent_id: UUID) -> IntentRecord:
    row = db.get(Intent, intent_id)
    if row is None:
        raise IntentNotFound()
    return _record(row)


def refuse_mutation() -> None:
    raise IntentImmutable()


def _record(row: Intent) -> IntentRecord:
    contract = _contract_from_row(row)
    contract.status = ContractStatus(row.status)
    return IntentRecord(
        intent_id=row.id,
        contract=contract,
        contract_hash=row.contract_hash,
        status=ContractStatus(row.status),
    )
