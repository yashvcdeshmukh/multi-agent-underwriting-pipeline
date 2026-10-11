"""Personal auto factor table. Ordinary Python: same input, same output.

Rating year is fixed at 2026 so vehicle age does not drift with the clock.
"""

from decimal import ROUND_HALF_UP, Decimal

from underwriting.domain.models import (
    ClaimsReport,
    CreditReport,
    Factor,
    IntakeResult,
    MotorVehicleReport,
    Rate,
    RateRequest,
)

TABLE_VERSION = "pa-table-2026.1"
RATING_YEAR = 2026
BASE_PREMIUM = Decimal("800")
_CENT = Decimal("0.01")


def _band(value: int, cuts: list[tuple[int, str, str]]) -> tuple[str, Decimal]:
    """Return the level and multiplier for the first band whose upper bound covers value."""
    for upper, level, multiplier in cuts:
        if value <= upper:
            return level, Decimal(multiplier)
    raise ValueError(value)


def _age_band(age: int) -> tuple[str, Decimal]:
    """Return the age band. Ages under 16 are outside the table."""
    if age < 16:
        raise ValueError(f"age {age} is outside the table")
    return _band(
        age,
        [
            (24, "16-24", "1.80"),
            (35, "25-35", "1.15"),
            (55, "36-55", "1.00"),
            (70, "56-70", "1.05"),
            (200, "71+", "1.40"),
        ],
    )


def _violation_band(count: int) -> tuple[str, Decimal]:
    """Return the moving-violation band for a three-year count."""
    return _band(
        count,
        [
            (0, "0", "1.00"),
            (1, "1", "1.25"),
            (2, "2", "1.60"),
            (100, "3+", "2.20"),
        ],
    )


def _accident_band(count: int) -> tuple[str, Decimal]:
    """Return the at-fault accident band for a three-year count."""
    return _band(
        count,
        [
            (0, "0", "1.00"),
            (1, "1", "1.45"),
            (100, "2+", "2.10"),
        ],
    )


def _licensed_band(years: int) -> tuple[str, Decimal]:
    """Return the years-licensed band."""
    return _band(
        years,
        [
            (0, "0", "1.50"),
            (2, "1-2", "1.30"),
            (5, "3-5", "1.15"),
            (100, "6+", "1.00"),
        ],
    )


def _credit_band(score: int) -> tuple[str, Decimal]:
    """Return the credit band. Scores outside 300-850 are outside the table."""
    if score < 300 or score > 850:
        raise ValueError(f"credit score {score} is outside 300-850")
    return _band(
        score,
        [
            (579, "300-579", "1.70"),
            (639, "580-639", "1.45"),
            (699, "640-699", "1.20"),
            (759, "700-759", "1.00"),
            (850, "760-850", "0.85"),
        ],
    )


def _credit_factor(state: str, credit: CreditReport | None) -> tuple[str, Decimal]:
    """California does not allow credit-based insurance scoring."""
    if state == "CA":
        return "CA", Decimal("1.00")
    if credit is None:
        return "missing", Decimal("1.00")
    return _credit_band(credit.score)


def _vehicle_age_band(years: int) -> tuple[str, Decimal]:
    """Return the vehicle-age band. Age is the rating year minus the model year."""
    return _band(
        years,
        [
            (2, "0-2", "1.25"),
            (7, "3-7", "1.10"),
            (100, "8+", "0.95"),
        ],
    )


_TERRITORY = {
    "urban": ("urban", Decimal("1.30")),
    "suburban": ("suburban", Decimal("1.00")),
    "rural": ("rural", Decimal("0.85")),
}
_PRIOR = {
    "continuous_12_months": ("continuous_12_months", Decimal("1.00")),
    "lapse": ("lapse", Decimal("1.25")),
    "none": ("none", Decimal("1.40")),
}


def _count(report_value: int | None, stated: int | None, label: str) -> int:
    """Prefer the report count. Fall back to the application. Raise when both are missing."""
    if report_value is not None:
        return report_value
    if stated is None:
        raise ValueError(f"{label} is missing")
    return stated


def _quote(
    *,
    age: int,
    violations: int,
    accidents: int,
    years_licensed: int,
    territory: str,
    vehicle_year: int,
    prior_insurance: str,
    state: str,
    credit: CreditReport | None,
) -> Rate:
    """Annual premium = 800 × the product of the factor-table multipliers."""
    vehicle_age = RATING_YEAR - vehicle_year
    bands = [
        ("age", *_age_band(age)),
        ("moving_violations_3yr", *_violation_band(violations)),
        ("at_fault_accidents_3yr", *_accident_band(accidents)),
        ("years_licensed", *_licensed_band(years_licensed)),
        ("territory", *_TERRITORY[territory]),
        ("vehicle_age", *_vehicle_age_band(vehicle_age)),
        ("prior_insurance", *_PRIOR[prior_insurance]),
        ("credit", *_credit_factor(state, credit)),
    ]
    factors = [
        Factor(name=name, level=level, multiplier=multiplier) for name, level, multiplier in bands
    ]
    combined = Decimal("1")
    for factor in factors:
        combined *= factor.multiplier
    premium = (BASE_PREMIUM * combined).quantize(_CENT, rounding=ROUND_HALF_UP)
    score = min(100, int(round(Decimal(35) * combined)))
    return Rate(
        table_version=TABLE_VERSION,
        factors=factors,
        combined_factor=combined,
        annual_premium=premium,
        risk_score=score,
    )


def rate(
    intake: IntakeResult,
    mvr: MotorVehicleReport | None,
    claims: ClaimsReport | None,
    credit: CreditReport | None,
) -> Rate:
    """Price an enriched case. Report counts win. A missing count with no fallback raises."""
    applicant = intake.applicant
    return _quote(
        age=applicant.age,
        violations=_count(
            None if mvr is None else mvr.violations_3yr,
            intake.stated_moving_violations_3yr,
            "moving violations",
        ),
        accidents=_count(
            None if claims is None else claims.at_fault_accidents_3yr,
            intake.stated_at_fault_accidents_3yr,
            "at-fault accidents",
        ),
        years_licensed=applicant.years_licensed,
        territory=applicant.territory,
        vehicle_year=intake.vehicle.year,
        prior_insurance=applicant.prior_insurance,
        state=applicant.garaging_state,
        credit=credit,
    )


def price(request: RateRequest) -> Rate:
    """Price the validated arguments the model sent."""
    credit = None
    if request.credit_score is not None:
        credit = CreditReport(license_number="", score=request.credit_score)
    return _quote(
        age=request.age,
        violations=request.moving_violations_3yr,
        accidents=request.at_fault_accidents_3yr,
        years_licensed=request.years_licensed,
        territory=request.territory,
        vehicle_year=request.vehicle_year,
        prior_insurance=request.prior_insurance,
        state=request.garaging_state,
        credit=credit,
    )
