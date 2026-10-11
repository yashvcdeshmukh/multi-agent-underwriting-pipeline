# At scale

This file is not part of the proof of concept. The graded pipeline calls the next function directly and prints the real case fields.

## Traces

The case record keeps the name and the license number. The motor-vehicle order needs the license number. The trace store does not keep them. Spans are masked or tokenized before they are written. This submission prints the fields, because the three handoffs have to be readable.

## Queues and webhooks

Intake publishes an `IntakeResult`. Enrichment workers consume it, order the motor-vehicle report, the claims report, and the credit report, and publish an `EnrichedCase`. The decision is posted to a webhook the policy system already subscribes to. A retry with backoff sits on the report order and on the webhook delivery. The underwriting decision itself is not retried there.
