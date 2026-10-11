# Cost and latency

The spans in `traces/live.json` are the local Ollama run of APP-001, APP-002, and APP-003 on `qwen3:8b`. Each span records `cost_usd` as 0 because Ollama does not bill. The dollar figures below apply Alibaba Model Studio's US (Virginia) list price for the same model, with thinking output: **$0.072 per 1M input tokens** and **$0.717 per 1M output tokens**. Source: [qwen3-8b model pricing](https://www.alibabacloud.com/help/en/model-studio/qwen3-8b). The live model used thinking, and the output-token counts include that reasoning.

## Per case

| Case | Decision | Wall clock | Input tokens | Output tokens | Hosted cost |
|------|----------|------------|--------------|---------------|-------------|
| APP-001 | approve | 287.7 s | 2,586 | 3,953 | $0.0030 |
| APP-002 | deny | 316.1 s | 2,607 | 4,495 | $0.0034 |
| APP-003 | refer | 403.2 s | 3,386 | 5,778 | $0.0044 |
| All three | | 1,007.0 s | 8,579 | 14,226 | $0.0108 |

## Per agent

| Agent | Wall clock | Input tokens | Output tokens |
|-------|------------|--------------|---------------|
| Intake | 165.7 s | 618 | 2,314 |
| Enrichment | 202.6 s | 1,008 | 2,915 |
| Risk scoring | 471.5 s | 4,645 | 6,708 |
| Recommendation | 167.1 s | 2,308 | 2,289 |

Scoring is 471.5 of the 1,007.0 seconds. APP-003 scoring alone is 251.4 seconds, because that case took more than one model turn to price and then explain.

## Real time or batch

**Batch.** A person waiting on a quote needs an answer in seconds. This pipeline takes 4.8 to 6.7 minutes per application, and the four agents run one after another, so the waits add. Hosted, the three cases cost about one cent. The limit is the clock, not the bill.

A queue can hold that. One worker on this machine finishes about ten applications an hour. That fits overnight or back-office review. It does not fit a page that has to return a premium while the applicant is still looking at it.
