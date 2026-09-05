from fastapi import APIRouter

from apps.api.config import get_settings
from apps.api.services.payment_service import effective_provider
from evaluation.runner import run_suite
from packages.policy_engine.thresholds import POLICY_VERSION

router = APIRouter(prefix="/v1/eval", tags=["eval"])

FAILURES = [
    {
        "id": "invalid_compiler_json",
        "failure": "Invalid LLM JSON",
        "behavior": "Schema reject, retry once, then fail safe. Never invent amounts.",
        "path": "POST /v1/intents/compile",
        "flag": "force_invalid_json",
    },
    {
        "id": "low_semantic",
        "failure": "Low semantic confidence",
        "behavior": "PAUSE. No grant. Payment stays closed.",
        "path": "POST /v1/intents/{id}/run",
        "flag": "inject=low_semantic",
    },
    {
        "id": "prompt_injection",
        "failure": "Prompt injection",
        "behavior": "Evaluate against the contract, not page text. BLOCK. No pay.",
        "path": "POST /v1/intents/{id}/run",
        "flag": "inject=poison",
    },
    {
        "id": "payment_timeout",
        "failure": "Payment API timeout",
        "behavior": "UNKNOWN, then reconcile. Retry only if not found. Never double-charge.",
        "path": "POST /v1/payments",
        "flag": "force_timeout",
    },
]


def _assessor() -> str:
    return "gemini" if get_settings().gemini_api_key else "heuristic"


@router.get("/failures")
def list_failures() -> dict[str, object]:
    return {"failures": FAILURES}


@router.get("/runtime")
def eval_runtime() -> dict[str, object]:
    settings = get_settings()
    return {
        "compiler": _assessor(),
        "semantic": _assessor(),
        "payment_provider": effective_provider(),
        "policy_version": POLICY_VERSION,
        "database": "sqlite" if settings.database_url.startswith("sqlite") else "postgres",
        "eval_mode": "deterministic",
        "note": (
            "Deterministic eval stubs semantic scores and measures the decision engine. "
            "Unsafe Approval Rate here is policy UAR, not model quality."
        ),
    }


@router.post("/run")
def run_eval() -> dict[str, object]:
    report = run_suite(mode="deterministic")
    mismatches = [item.model_dump(mode="json") for item in report.cases if not item.match]
    return {
        "status": "ok",
        "mode": report.mode,
        "unsafe_approval_rate": report.unsafe_approval_rate,
        "unsafe_approvals": report.unsafe_approvals,
        "expected_blocks": report.expected_blocks,
        "accuracy": report.accuracy,
        "false_approvals": report.false_approvals,
        "false_blocks": report.false_blocks,
        "violation_precision": report.violation_precision,
        "violation_recall": report.violation_recall,
        "average_latency_ms": report.average_latency_ms,
        "total": report.total,
        "mismatches": mismatches,
        "cases": [item.model_dump(mode="json") for item in report.cases],
        "note": (
            "Deterministic eval stubs semantic scores and measures the decision engine. "
            "Unsafe Approval Rate here is policy UAR, not model quality."
        ),
    }
