from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    id: str
    user_intent: str
    proposed_action: dict[str, Any]
    expected: Literal["APPROVE", "PAUSE", "BLOCK"]
    tags: list[str] = Field(default_factory=list)
    contract: dict[str, Any] | None = None
    semantic_stub: float | None = None
    semantic_error: bool = False
    product_text: str | None = None
    expired: bool = False
    duplicate: bool = False


class CaseResult(BaseModel):
    id: str
    expected: str
    actual: str
    tags: list[str]
    latency_ms: float
    match: bool
    hard_passed: bool
    unsafe_approval: bool


class EvalReport(BaseModel):
    mode: str
    total: int
    unsafe_approval_rate: float
    unsafe_approvals: int
    expected_blocks: int
    accuracy: float
    false_approvals: int
    false_blocks: int
    violation_precision: float
    violation_recall: float
    average_latency_ms: float
    cases: list[CaseResult]
