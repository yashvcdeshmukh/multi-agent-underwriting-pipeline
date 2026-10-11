# State and memory

**Message passing.** Each function receives one object and returns the next. There is no shared dictionary and no database row.

The pipeline calls intake, then enrichment, then scoring, then recommendation. A later step cannot overwrite an earlier one, because it never holds a shared record. The handoff is the return value, which is what the trace shows.

A queue in front of enrichment and a webhook after the decision are how a carrier does this at volume. They are not in this submission. Three mock applications would not show them in a trace, and they are not in the rubric.

| Step | Function | Reads | Returns |
|------|----------|-------|---------|
| 1 | `intake_agent` | Raw application text | Applicant, vehicle, coverage, missing fields |
| 2 | `enrichment_agent` | Intake result | Intake result plus MVR, claims, credit, and a short summary |
| 3 | `risk_scoring_agent` | Enriched case | Enriched case plus factors, annual premium, risk score, explanation |
| 4 | `recommendation_agent` | Scored case and every matching appetite row | The model's approve, deny, or refer, the cited row's reason code, and the reason sentence |
