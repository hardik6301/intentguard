from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from evaluation.metrics import compute_report, format_report
from evaluation.schemas import CaseResult, EvalReport, Scenario
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.heuristic_client import HeuristicJsonClient
from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.constraint_checker import check_constraints
from packages.verification_engine.decision_engine import decide
from packages.verification_engine.fingerprint import proposal_fingerprint
from packages.verification_engine.heuristic_semantic import HeuristicSemanticVerifier
from packages.verification_engine.risk import assess_risk
from packages.verification_engine.schemas import (
    ProposedAction,
    SemanticAssessment,
    SubstitutionSeverity,
    Verdict,
)

ROOT = Path(__file__).resolve().parent
SCENARIO_PATH = ROOT / "scenarios" / "scenarios.jsonl"
DEFAULT_UAR_CEILING = 0.0


class StubSemanticVerifier:
    def __init__(self, score: float | None, *, error: bool = False) -> None:
        self.score = score
        self.error = error

    def verify(self, *_args, **_kwargs) -> SemanticAssessment:
        if self.error or self.score is None:
            return SemanticAssessment(
                semantic_match=None,
                error=True,
                reason="Semantic stub reported an error.",
            )
        score = self.score
        if score < 0.60:
            severity = SubstitutionSeverity.MAJOR
        elif score < 0.85:
            severity = SubstitutionSeverity.MAJOR
        else:
            severity = SubstitutionSeverity.NONE
        return SemanticAssessment(
            semantic_match=score,
            substitution_severity=severity,
            reason="Recorded semantic stub.",
            error=False,
        )


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    source = path or SCENARIO_PATH
    rows: list[Scenario] = []
    for line in source.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        rows.append(Scenario.model_validate(json.loads(text)))
    return rows


def _compile(user_intent: str) -> IntentContract:
    compiler = IntentCompiler(llm=HeuristicJsonClient())
    return compiler.compile(user_intent)


def _contract_for(scenario: Scenario) -> IntentContract:
    if scenario.contract is not None:
        payload = dict(scenario.contract)
        payload.setdefault("raw_request", scenario.user_intent)
        payload.setdefault("goal", scenario.user_intent)
        if "intent_id" not in payload:
            payload["intent_id"] = str(uuid4())
        contract = IntentContract.model_validate(payload)
    else:
        contract = _compile(scenario.user_intent)
        if contract.intent_id is None:
            contract = contract.model_copy(update={"intent_id": uuid4()})
    if scenario.expired:
        contract = contract.model_copy(
            update={"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}
        )
    return contract


def _verifier(scenario: Scenario, mode: str):
    if mode == "live":
        settings_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if settings_key:
            from packages.verification_engine.gemini_client import SemanticGeminiClient
            from packages.verification_engine.semantic_verifier import SemanticVerifier

            return SemanticVerifier(SemanticGeminiClient(api_key=settings_key))
    if scenario.semantic_error or scenario.semantic_stub is not None:
        return StubSemanticVerifier(scenario.semantic_stub, error=scenario.semantic_error)
    return HeuristicSemanticVerifier()


def run_scenario(scenario: Scenario, *, mode: str) -> CaseResult:
    started = time.perf_counter()
    contract = _contract_for(scenario)
    proposal = ProposedAction.model_validate(scenario.proposed_action)
    existing: set[str] = set()
    if scenario.duplicate and contract.intent_id is not None:
        existing.add(proposal_fingerprint(contract.intent_id, proposal))
    hard = check_constraints(contract, proposal, existing_fingerprints=existing)
    risk = assess_risk(proposal, product_text=scenario.product_text)
    semantic = _verifier(scenario, mode).verify(
        contract, proposal, product_text=scenario.product_text
    )
    decision = decide(hard, semantic, risk)
    elapsed = (time.perf_counter() - started) * 1000
    actual = decision.verdict.value if isinstance(decision.verdict, Verdict) else str(decision.verdict)
    return CaseResult(
        id=scenario.id,
        expected=scenario.expected,
        actual=actual,
        tags=list(scenario.tags),
        latency_ms=elapsed,
        match=actual == scenario.expected,
        hard_passed=hard.passed,
        unsafe_approval=scenario.expected == "BLOCK" and actual == "APPROVE",
    )


def run_suite(
    *,
    mode: str | None = None,
    path: Path | None = None,
) -> EvalReport:
    resolved = (mode or os.environ.get("EVAL_MODE") or "deterministic").strip().casefold()
    if resolved not in {"deterministic", "live"}:
        resolved = "deterministic"
    cases = [run_scenario(item, mode=resolved) for item in load_scenarios(path)]
    return compute_report(resolved, cases)


def hard_constraint_uar(report: EvalReport) -> float:
    hard_tags = {"budget", "expiry", "duplicate", "currency", "merchant", "quantity"}
    subset = [
        item
        for item in report.cases
        if item.expected == "BLOCK" and hard_tags.intersection(item.tags)
    ]
    if not subset:
        return 0.0
    unsafe = sum(1 for item in subset if item.unsafe_approval)
    return unsafe / len(subset)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IntentGuard evaluation harness")
    parser.add_argument("--mode", choices=("deterministic", "live"), default=None)
    parser.add_argument("--ceiling", type=float, default=None)
    args = parser.parse_args(argv)
    report = run_suite(mode=args.mode)
    print(format_report(report))
    ceiling = args.ceiling
    if ceiling is None:
        ceiling = float(os.environ.get("EVAL_UAR_CEILING", DEFAULT_UAR_CEILING))
    if report.unsafe_approval_rate > ceiling:
        print(f"UAR {report.unsafe_approval_rate:.3f} exceeds ceiling {ceiling:.3f}", file=sys.stderr)
        return 1
    if hard_constraint_uar(report) > 0:
        print("UAR on stubbed hard-constraint cases exceeds 0", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
