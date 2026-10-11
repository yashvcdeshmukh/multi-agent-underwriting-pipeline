"""Scoring. The model calls price, then returns the scored case."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from underwriting.domain.models import EnrichedCase, Rate, RateRequest, ScoredCase
from underwriting.llm import Completion, Model, ToolCall, complete_turn
from underwriting.tools.rating import price

_SYSTEM = """\
Price this enriched personal-auto application and explain the rating.
"""

_MAX_TURNS = 4

PRICE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "price",
        "description": "Price a personal-auto application from the factor table.",
        "parameters": RateRequest.model_json_schema(),
    },
}


class ScoringUnavailable(Exception):
    """The scoring model did not return a scored case."""


def _invoke(call: ToolCall) -> tuple[Rate | None, str]:
    """Validate the model's arguments and run price. An error string is not a rate."""
    if call.name != "price":
        return None, json.dumps({"error": f"unknown tool {call.name}"})
    try:
        request = RateRequest.model_validate(call.arguments)
    except ValidationError as exc:
        return None, json.dumps({"error": exc.errors()})
    quote = price(request)
    return quote, quote.model_dump_json()


def _assistant_turn(turn: Completion) -> dict[str, Any]:
    """Build the assistant message, including any tool calls, for the next request."""
    tool_calls = []
    for index, call in enumerate(turn.tool_calls):
        tool_calls.append(
            {
                "id": call.id or f"call-{index}",
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
        )
    return {"role": "assistant", "content": turn.text or None, "tool_calls": tool_calls}


def _scored_case(enriched: EnrichedCase, quote: Rate, explanation: str) -> ScoredCase:
    """Build the object recommendation reads. The quote supplies the rating."""
    return ScoredCase(
        enriched=enriched,
        factors=quote.factors,
        combined_factor=quote.combined_factor,
        annual_premium=quote.annual_premium,
        risk_score=quote.risk_score,
        explanation=explanation,
        table_version=quote.table_version,
    )


def risk_scoring_agent(enriched: EnrichedCase, model: Model) -> tuple[ScoredCase, int, int]:
    """Return the scored case for recommendation.

    The model calls price. That result is the rating. The model then fills the
    scored-case schema, and its explanation is the summary recommendation reads.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": enriched.model_dump_json()},
    ]
    schema = ScoredCase.model_json_schema()
    quote: Rate | None = None
    input_tokens = 0
    output_tokens = 0
    for _ in range(_MAX_TURNS):
        turn = complete_turn(
            model,
            _SYSTEM,
            enriched.model_dump_json(),
            messages=messages,
            schema=schema if quote is not None else None,
            tools=None if quote is not None else [PRICE_TOOL],
        )
        input_tokens += turn.input_tokens
        output_tokens += turn.output_tokens
        if quote is not None:
            try:
                drafted = ScoredCase.model_validate_json(turn.text)
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": turn.text})
                messages.append({"role": "user", "content": json.dumps({"error": exc.errors()})})
                continue
            scored = _scored_case(enriched, quote, drafted.explanation)
            return scored, input_tokens, output_tokens
        if not turn.tool_calls:
            messages.append({"role": "assistant", "content": turn.text})
            messages.append(
                {"role": "user", "content": json.dumps({"error": "a scored case was not returned"})}
            )
            continue
        messages.append(_assistant_turn(turn))
        for index, call in enumerate(turn.tool_calls):
            rated, body = _invoke(call)
            if rated is not None:
                quote = rated
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id or f"call-{index}",
                    "content": body,
                }
            )
    raise ScoringUnavailable("scoring did not return a scored case")
