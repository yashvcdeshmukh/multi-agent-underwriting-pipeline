"""Recommendation. Every matching appetite row is context. The model decides."""

from __future__ import annotations

import json
from typing import Any

from underwriting.domain.models import Decision, RecommendationChoice, ScoredCase
from underwriting.llm import Model, complete_turn
from underwriting.tools.appetite import AppetiteRow, match_appetite

_SYSTEM = """\
Decide this personal-auto application.
"""


def _recommendation_user(scored: ScoredCase, rows: tuple[AppetiteRow, ...]) -> str:
    """Return the scored case and every appetite row that matched."""
    return json.dumps(
        {
            "scored": scored.model_dump(mode="json"),
            "guidelines": [
                {
                    "id": row.id,
                    "reason_code": row.reason_code,
                    "decision": row.decision,
                    "guidance": row.guidance,
                }
                for row in rows
            ],
        }
    )


def _choice_schema(rows: tuple[AppetiteRow, ...]) -> dict[str, Any]:
    """Return the decision schema, limited to the row ids that matched."""
    schema = RecommendationChoice.model_json_schema()
    schema["properties"]["guideline_id"]["enum"] = [row.id for row in rows]
    return schema


def recommendation_agent(scored: ScoredCase, model: Model) -> tuple[Decision, int, int]:
    """Return the model's disposition. The cited row supplies the reason code.

    `guideline_ids` lists every row that matched. `guideline_id` is the one the
    model named, and it has to be one of those rows.
    """
    rows = match_appetite(scored)
    user = _recommendation_user(scored, rows)
    completion = complete_turn(
        model,
        _SYSTEM,
        user,
        schema=_choice_schema(rows),
    )
    choice = RecommendationChoice.model_validate_json(completion.text)
    cited = next((row for row in rows if row.id == choice.guideline_id), None)
    if cited is None:
        raise ValueError(f"guideline {choice.guideline_id} was not matched")
    decision = Decision(
        case_id=scored.enriched.intake.case_id,
        scored=scored,
        disposition=choice.disposition,
        reason_code=cited.reason_code,
        reason=choice.reason,
        guideline_id=cited.id,
        guideline_ids=[row.id for row in rows],
    )
    return decision, completion.input_tokens, completion.output_tokens
