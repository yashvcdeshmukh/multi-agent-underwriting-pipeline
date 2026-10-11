"""Local MVR, claims, and credit fixtures, keyed by license number.

The three lookups are independent. Enrichment reads all of them, then one model
call summarizes them.
"""

from underwriting.domain.models import ClaimsReport, CreditReport, MotorVehicleReport

_MVRS = {
    "OH-10001": MotorVehicleReport(
        license_number="OH-10001",
        violations_3yr=0,
        license_status="valid",
        dui_last_5_years=False,
    ),
    "TX-20002": MotorVehicleReport(
        license_number="TX-20002",
        violations_3yr=2,
        license_status="valid",
        dui_last_5_years=False,
    ),
}

_CLAIMS = {
    "OH-10001": ClaimsReport(
        license_number="OH-10001",
        at_fault_accidents_3yr=0,
    ),
    "TX-20002": ClaimsReport(
        license_number="TX-20002",
        at_fault_accidents_3yr=1,
    ),
    "IL-30003": ClaimsReport(
        license_number="IL-30003",
        at_fault_accidents_3yr=0,
    ),
}

_CREDIT = {
    "OH-10001": CreditReport(license_number="OH-10001", score=780),
    "TX-20002": CreditReport(license_number="TX-20002", score=710),
}


def lookup_mvr(license_number: str) -> MotorVehicleReport | None:
    """Return the motor vehicle report for this license, or None when it is not on file."""
    return _MVRS.get(license_number)


def lookup_claims(license_number: str) -> ClaimsReport | None:
    """Return the claims report for this license, or None when it is not on file."""
    return _CLAIMS.get(license_number)


def lookup_credit(license_number: str) -> CreditReport | None:
    """Return the credit report for this license, or None when it is not on file."""
    return _CREDIT.get(license_number)
