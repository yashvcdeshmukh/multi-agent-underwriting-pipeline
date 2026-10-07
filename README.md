# Multi-Agent Underwriting Pipeline

Insurance application pipeline with four LLM-backed agents:

1. **Intake** — normalize applicant basics from raw application text  
2. **Enrichment** — gather supplemental context (simulated / inferred)  
3. **Risk scoring** — produce a structured risk score  
4. **Recommendation** — approve, deny, or refer to a human underwriter  

## State & memory

Design decision and agent I/O contract: [`docs/STATE_AND_MEMORY.md`](docs/STATE_AND_MEMORY.md).

## Setup (UV)

[UV](https://docs.astral.sh/uv/) is a fast Python package and project manager from Astral (same team as Ruff). It replaces pip/venv/poetry for installs, lockfiles, and running tools.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if needed
uv sync --all-extras
cp .env.example .env   # add OPENAI_API_KEY
```

Run tests:

```bash
uv run pytest
```

Run the full pipeline (once implemented):

```bash
uv run python -m underwriting.pipeline
```

## Dev container

Open the folder in VS Code / Cursor **Dev Containers** when ready. See [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).

## Assignment parts

| Part | Location (planned) |
|------|---------------------|
| 1 Design | `docs/STATE_AND_MEMORY.md` |
| 2 Agents + unit tests | `src/underwriting/agents/`, `tests/` |
| 3 Pipeline + tracing | `src/underwriting/pipeline.py`, `src/underwriting/tracing.py` |
| 4 Cost/latency | `docs/COST_LATENCY.md`, trace JSON under `traces/` |
| 5 Failure handling | `src/underwriting/failure.py` |
| 6 CI | `.github/workflows/ci.yml` |
