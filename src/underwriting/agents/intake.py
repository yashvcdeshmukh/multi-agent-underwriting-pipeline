"""Intake. One structured completion. This agent does not call the next agent."""

from __future__ import annotations

from underwriting.domain.models import IntakeResult
from underwriting.llm import Model, complete_as

_INTAKE_SYSTEM = """\
Extract the application into the schema you were given.
Use null when a stated count is unknown.
missing_fields lists field names the application left blank.
"""


def intake_agent(raw_application: str, model: Model) -> tuple[IntakeResult, int, int]:
    """Return the IntakeResult enrichment receives, plus the token counts."""
    return complete_as(model, _INTAKE_SYSTEM, raw_application, IntakeResult)
