# Part 1: State and memory (draft — fill before orchestration)

## Decision

**Pattern:** _TBD — shared state store **or** explicit message passing_

## Rationale

_Why this fits underwriting (audit trail, human handoff, refer cases, etc.)_

## Case record schema

| Field | Written by | Read by | Description |
|-------|------------|---------|-------------|
| `raw_application` | pipeline input | intake | Original applicant text |
| … | | | |

## Agent contracts

### `intake_agent`

- **Reads:** …
- **Produces:** …

### `enrichment_agent`

- **Reads:** …
- **Produces:** …

### `risk_scoring_agent`

- **Reads:** …
- **Produces:** …

### `recommendation_agent`

- **Reads:** …
- **Produces:** …
