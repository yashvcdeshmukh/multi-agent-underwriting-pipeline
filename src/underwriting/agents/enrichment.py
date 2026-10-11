"""Enrichment. Report lookups run here, in parallel. The model writes the summary."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from underwriting.domain.models import (
    ClaimsReport,
    CreditReport,
    EnrichedCase,
    IntakeResult,
    MotorVehicleReport,
)
from underwriting.llm import Model, complete_as
from underwriting.tools.reports import lookup_claims, lookup_credit, lookup_mvr

_ENRICHMENT_SYSTEM = """\
Fill the EnrichedCase schema.
Write a short summary of the driver and the reports.
Copy intake, mvr, claims, and credit from the input. Use null when a report is missing.
"""


def _enrichment_user(
    intake: IntakeResult,
    mvr: MotorVehicleReport | None,
    claims: ClaimsReport | None,
    credit: CreditReport | None,
) -> str:
    """Return the JSON the summary call sees, including the tool results."""
    return json.dumps(
        {
            "intake": intake.model_dump(mode="json"),
            "mvr": None if mvr is None else mvr.model_dump(mode="json"),
            "claims": None if claims is None else claims.model_dump(mode="json"),
            "credit": None if credit is None else credit.model_dump(mode="json"),
        }
    )


def enrichment_agent(intake: IntakeResult, model: Model) -> tuple[EnrichedCase, int, int]:
    """Return the EnrichedCase scoring receives.

    The model writes the summary. The intake object and the tool results are
    copied onto the case that is returned, so a summary cannot change them.
    """
    license_number = intake.applicant.license_number
    with ThreadPoolExecutor(max_workers=3) as pool:
        mvr_call = pool.submit(lookup_mvr, license_number)
        claims_call = pool.submit(lookup_claims, license_number)
        credit_call = pool.submit(lookup_credit, license_number)
        mvr = mvr_call.result()
        claims = claims_call.result()
        credit = credit_call.result()

    drafted, input_tokens, output_tokens = complete_as(
        model,
        _ENRICHMENT_SYSTEM,
        _enrichment_user(intake, mvr, claims, credit),
        EnrichedCase,
    )
    enriched = EnrichedCase(
        intake=intake,
        mvr=mvr,
        claims=claims,
        credit=credit,
        summary=drafted.summary,
    )
    return enriched, input_tokens, output_tokens
