"""Shared Pydantic models for case state (schema evolves with Part 1 design)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Recommendation = Literal["approve", "deny", "refer"]


class CaseRecord(BaseModel):
    """Mutable case record for shared-state orchestration (placeholder)."""

    case_id: str
    raw_application: str
    intake: dict[str, Any] | None = None
    enrichment: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    recommendation: Recommendation | None = None
    recommendation_rationale: str | None = None
    status: Literal["open", "completed", "needs_human_review"] = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)
