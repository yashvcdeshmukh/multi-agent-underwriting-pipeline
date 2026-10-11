"""The four raw applications.

APP-001, APP-002, and APP-003 are the graded traces.
APP-TIMEOUT uses Maria's facts and is only for the scoring timeout.
"""

_APP_001 = """\
Application ID: APP-001

Applicant
Name: Maria Chen
Age: 42
License number: OH-10001
Years licensed: 20
License status: valid
Garaging state: OH
Territory: suburban
Prior insurance: continuous 12 months

Vehicle
Year: 2016
Make: Honda
Model: Civic

Coverage
Bodily injury limit: 100/300
Property damage limit: 50
Collision: yes
Comprehensive: yes

Driving record stated on the application
Moving violations in the last 3 years: 0
At-fault accidents in the last 3 years: 0
DUI in the last 5 years: no
"""

_APP_002 = """\
Application ID: APP-002

Applicant
Name: James Patel
Age: 22
License number: TX-20002
Years licensed: 4
License status: valid
Garaging state: TX
Territory: urban
Prior insurance: continuous 12 months

Vehicle
Year: 2025
Make: Honda
Model: Civic

Coverage
Bodily injury limit: 100/300
Property damage limit: 50
Collision: yes
Comprehensive: yes

Driving record stated on the application
Moving violations in the last 3 years: 2
At-fault accidents in the last 3 years: 1
DUI in the last 5 years: no
"""

_APP_003 = """\
Application ID: APP-003

Applicant
Name: Elena Rossi
Age: 34
License number: IL-30003
Years licensed: 10
License status: valid
Garaging state: IL
Territory: suburban
Prior insurance: continuous 12 months

Vehicle
Year: 2016
Make: Toyota
Model: Corolla

Coverage
Bodily injury limit: 100/300
Property damage limit: 50
Collision: yes
Comprehensive: yes

Driving record stated on the application
Moving violations in the last 3 years: 0
At-fault accidents in the last 3 years: 0
DUI in the last 5 years: no
"""

APPLICATIONS = {
    "APP-001": _APP_001,
    "APP-002": _APP_002,
    "APP-003": _APP_003,
    "APP-TIMEOUT": _APP_001.replace("Application ID: APP-001", "Application ID: APP-TIMEOUT"),
}


def raw_application(case_id: str) -> str:
    """Return the raw application text for a known case id."""
    return APPLICATIONS[case_id]
