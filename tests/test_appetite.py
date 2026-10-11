"""Every matching appetite row is returned, with that row's decision."""

from test_recommendation import _scored

from underwriting.tools.appetite import match_appetite


def test_every_matching_row_is_returned_with_its_decision():
    matched = [
        match_appetite(_scored()),
        match_appetite(
            _scored(
                case_id="APP-002",
                state="TX",
                age=22,
                territory="urban",
                score=100,
                premium="6243.12",
                violations=2,
                at_fault=1,
            )
        ),
        match_appetite(
            _scored(
                case_id="APP-003",
                state="IL",
                score=38,
                premium="874.00",
                mvr=False,
                credit=False,
            )
        ),
        match_appetite(_scored(license_status="suspended")),
        match_appetite(_scored(state="NY")),
        match_appetite(_scored(credit=False)),
        match_appetite(_scored(state="CA", credit=False)),
        match_appetite(_scored(score=None, premium=None)),
    ]

    assert [[(row.id, row.reason_code, row.decision) for row in rows] for rows in matched] == [
        [("UG-11", "within_appetite", "approve")],
        [
            ("UG-6", "youthful_high_score", "deny"),
            ("UG-7", "elevated_score", "refer"),
        ],
        [
            ("UG-4", "report_unavailable", "refer"),
            ("UG-11", "within_appetite", "approve"),
        ],
        [
            ("UG-1", "license_status", "deny"),
            ("UG-11", "within_appetite", "approve"),
        ],
        [
            ("UG-2", "state_not_written", "deny"),
            ("UG-11", "within_appetite", "approve"),
        ],
        [
            ("UG-4", "report_unavailable", "refer"),
            ("UG-11", "within_appetite", "approve"),
        ],
        [("UG-11", "within_appetite", "approve")],
        [("UG-5", "scoring_unavailable", "refer")],
    ]
