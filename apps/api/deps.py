from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.config import get_settings
from apps.api.models.db import Base
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.heuristic_client import HeuristicJsonClient
from packages.verification_engine.heuristic_semantic import HeuristicSemanticVerifier

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_session_factory():
    get_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_compiler() -> IntentCompiler:
    settings = get_settings()
    if settings.gemini_api_key:
        from packages.intent_compiler.gemini_client import GeminiJsonClient

        llm = GeminiJsonClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
    else:
        llm = HeuristicJsonClient()
    return IntentCompiler(llm=llm, ttl_seconds=settings.intent_ttl_seconds)


def get_semantic_verifier():
    settings = get_settings()
    if settings.gemini_api_key:
        from packages.verification_engine.gemini_client import SemanticGeminiClient
        from packages.verification_engine.semantic_verifier import SemanticVerifier

        return SemanticVerifier(
            SemanticGeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
        )
    return HeuristicSemanticVerifier()
