from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.deps import get_compiler, get_db
from apps.api.services import intent_service
from packages.intent_compiler.broken_client import BrokenJsonClient
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.errors import GeminiNotConfigured
from packages.intent_compiler.schemas import (
    ActivateRequest,
    CompileFailed,
    CompileRequest,
    CompileResponse,
    IntentRecord,
)

router = APIRouter(prefix="/v1/intents", tags=["intents"])


def _http_for_compile(exc: CompileFailed) -> HTTPException:
    return HTTPException(status_code=422, detail=exc.to_model().model_dump())


@router.post("/compile", response_model=CompileResponse)
def compile_intent(
    body: CompileRequest,
    db: Session = Depends(get_db),
    compiler: IntentCompiler = Depends(get_compiler),
) -> CompileResponse:
    if body.force_invalid_json:
        compiler = IntentCompiler(llm=BrokenJsonClient(), ttl_seconds=compiler.ttl_seconds)
    try:
        return intent_service.compile_draft(db, compiler, body.raw_request)
    except CompileFailed as exc:
        raise _http_for_compile(exc) from exc
    except GeminiNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/", response_model=IntentRecord)
def confirm_intent(
    body: ActivateRequest,
    db: Session = Depends(get_db),
) -> IntentRecord:
    try:
        return intent_service.activate_intent(db, body)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc
    except intent_service.IntentImmutable as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc


@router.get("/{intent_id}", response_model=IntentRecord)
def read_intent(intent_id: UUID, db: Session = Depends(get_db)) -> IntentRecord:
    try:
        return intent_service.get_intent(db, intent_id)
    except intent_service.IntentNotFound as exc:
        raise HTTPException(status_code=404, detail="Intent not found") from exc


@router.patch("/{intent_id}")
def patch_intent(intent_id: UUID) -> None:
    raise HTTPException(
        status_code=409,
        detail="Intent contracts are immutable",
        headers={"X-Intent-Id": str(intent_id)},
    )


@router.put("/{intent_id}")
def put_intent(intent_id: UUID) -> None:
    raise HTTPException(
        status_code=409,
        detail="Intent contracts are immutable",
        headers={"X-Intent-Id": str(intent_id)},
    )
