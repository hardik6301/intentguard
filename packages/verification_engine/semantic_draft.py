from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.verification_engine.schemas import SubstitutionSeverity


class SemanticDraft(BaseModel):
    """LLM-facing assessment. Must never include a verdict or payment decision."""

    model_config = ConfigDict(extra="forbid")

    semantic_match: float = Field(..., ge=0.0, le=1.0)
    violated_preferences: list[str] = Field(default_factory=list)
    substitution_severity: SubstitutionSeverity = SubstitutionSeverity.NONE
    reason: str = ""
