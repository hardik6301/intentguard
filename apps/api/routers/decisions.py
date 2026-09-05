from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_db
from apps.api.routers.proposals import ProposalEvaluation, _to_evaluation
from apps.api.services import verify_service

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


class ResolvePauseRequest(BaseModel):
    action: str


@router.post("/{decision_id}/confirm", response_model=ProposalEvaluation)
def resolve_decision(
    decision_id: UUID,
    body: ResolvePauseRequest | None = None,
    db: Session = Depends(get_db),
) -> ProposalEvaluation:
    action = (body.action if body is not None else "confirm").strip().casefold()
    if action not in {"confirm", "reject"}:
        raise HTTPException(status_code=422, detail="Action must be confirm or reject")
    try:
        record = verify_service.resolve_pause(db, decision_id, action)
    except verify_service.DecisionNotFound as exc:
        raise HTTPException(status_code=404, detail="Decision not found") from exc
    except verify_service.PauseNotResolvable as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    return _to_evaluation(record)
