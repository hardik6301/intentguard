from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.deps import create_all
from apps.api.routers import decisions, eval as eval_router, intents, payments, proposals
from packages.intent_compiler.errors import GeminiNotConfigured


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_all()
    yield


app = FastAPI(title="IntentGuard", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intents.router)
app.include_router(proposals.router)
app.include_router(decisions.router)
app.include_router(payments.router)
app.include_router(eval_router.router)


@app.exception_handler(GeminiNotConfigured)
async def gemini_not_configured(_request: Request, exc: GeminiNotConfigured) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "intentguard"}
