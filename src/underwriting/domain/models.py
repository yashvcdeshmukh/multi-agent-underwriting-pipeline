"""Messages passed between agents. A later object nests the earlier one and does not rewrite it."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Disposition = Literal["approve", "deny", "refer"]
ReasonCode = Literal[
    "license_status",
    "state_not_written",
    "knockout",
    "intake_unavailable",
    "enrichment_unavailable",
    "scoring_unavailable",
    "recommendation_unavailable",
    "report_unavailable",
    "youthful_high_score",
    "elevated_score",
    "stacked_mid_score",
    "mid_score",
    "youthful_low_score",
    "within_appetite",
]
Territory = Literal["urban", "suburban", "rural"]
PriorInsurance = Literal["continuous_12_months", "lapse", "none"]
LicenseStatus = Literal["valid", "suspended", "revoked"]
AgentName = Literal["intake", "enrichment", "risk_scoring", "recommendation"]


class _Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Applicant(_Message):
    """The driver named on the application."""

    full_name: str
    age: int
    license_number: str
    years_licensed: int
    license_status: LicenseStatus
    garaging_state: str
    territory: Territory
    prior_insurance: PriorInsurance


class Vehicle(_Message):
    """The vehicle named on the application."""

    year: int
    make: str
    model: str


class Coverage(_Message):
    """The coverage the applicant asked for."""

    bodily_injury_limit: str
    property_damage_limit: str
    collision: bool
    comprehensive: bool


class IntakeResult(_Message):
    """Applicant, vehicle, coverage, and fields the application left blank."""

    case_id: str
    applicant: Applicant
    vehicle: Vehicle
    coverage: Coverage
    missing_fields: list[str] = Field(default_factory=list)
    stated_moving_violations_3yr: int | None = None
    stated_at_fault_accidents_3yr: int | None = None
    stated_dui_last_5_years: bool | None = None


class MotorVehicleReport(_Message):
    """Driving record ordered for a license number."""

    license_number: str
    violations_3yr: int
    license_status: LicenseStatus
    dui_last_5_years: bool


class ClaimsReport(_Message):
    """At-fault claim count ordered for a license number."""

    license_number: str
    at_fault_accidents_3yr: int


class CreditReport(_Message):
    """Credit score ordered for a license number."""

    license_number: str
    score: int


class EnrichedCase(_Message):
    """Intake result plus the reports and a short summary. A report is null when absent."""

    intake: IntakeResult
    mvr: MotorVehicleReport | None
    claims: ClaimsReport | None
    credit: CreditReport | None
    summary: str


class Factor(_Message):
    """One rating-table band and its multiplier."""

    name: str
    level: str
    multiplier: Decimal


class RateRequest(_Message):
    """Arguments the scoring model sends to the rating tool."""

    age: int
    years_licensed: int
    territory: Territory
    prior_insurance: PriorInsurance
    garaging_state: str
    vehicle_year: int
    moving_violations_3yr: int
    at_fault_accidents_3yr: int
    credit_score: int | None = None


class Rate(_Message):
    """Output of the personal-auto factor table."""

    table_version: str
    factors: list[Factor]
    combined_factor: Decimal
    annual_premium: Decimal
    risk_score: int


class ScoredCase(_Message):
    """Enriched case plus the rating and explanation the model returns."""

    enriched: EnrichedCase
    factors: list[Factor] = Field(default_factory=list)
    combined_factor: Decimal | None = None
    annual_premium: Decimal | None = None
    risk_score: int | None = None
    explanation: str = ""
    table_version: str | None = None


class RecommendationChoice(_Message):
    """The disposition, the reason sentence, and the appetite row the model is acting on."""

    disposition: Disposition
    reason: str
    guideline_id: str


class Decision(_Message):
    """Final message. `scored` is null when scoring never returned a case."""

    case_id: str
    scored: ScoredCase | None
    disposition: Disposition
    reason_code: ReasonCode
    reason: str
    guideline_id: str | None = None
    guideline_ids: list[str] = Field(default_factory=list)
