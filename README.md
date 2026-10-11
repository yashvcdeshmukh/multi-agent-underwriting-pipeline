# Multi-Agent Underwriting Pipeline

Insurance application pipeline with four LLM-backed agents:

1. **Intake** — normalize applicant basics from raw application text  
2. **Enrichment** — gather supplemental context (simulated / inferred)  
3. **Risk scoring** — produce a structured risk score  
4. **Recommendation** — approve, deny, or refer to a human underwriter  

## State and memory

**Message passing.** [`docs/state-and-memory.md`](docs/state-and-memory.md) is the locked decision. `underwrite` is the only coordinator. Each agent receives one object and returns the next. There is no shared case row.

## Setup (UV)

[UV](https://docs.astral.sh/uv/) is a fast Python package and project manager from Astral (same team as Ruff). It replaces pip/venv/poetry for installs, lockfiles, and running tools.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if needed
uv sync --all-extras
cp .env.example .env
```

### Ollama + Qwen 3 8B

Live runs call local Ollama at `http://127.0.0.1:11434`. No API key. Default model: **`qwen3:8b`** (set `OLLAMA_MODEL` if your tag differs). Unit tests use a scripted reply so pytest does not start Ollama.

```bash
ollama serve          # if not already running
ollama pull qwen3:8b
```

Run tests:

```bash
uv run pytest
```

Run the full pipeline:

```bash
uv run python -m underwriting.pipeline
```

## Dev container

Open the folder in VS Code / Cursor **Dev Containers** when ready. See [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).

## Layout

| Path | Role |
|------|------|
| `docs/state-and-memory.md` | Part 1, locked |
| `docs/scale.md` | What changes when this leaves the proof of concept |
| `docs/cost-latency.md` | Part 4, after the three traces |
| `src/underwriting/domain/models.py` | Intake, enriched, scored, and decision messages |
| `src/underwriting/tools/rating.py` | Factor table `pa-table-2026.1` |
| `src/underwriting/tables/appetite.yaml` | Appetite guide. The model chooses the disposition |
| `src/underwriting/tools/appetite.py` | Every matching appetite row |
| `src/underwriting/tools/reports.py` | MVR, claims, and credit fixtures |
| `src/underwriting/llm.py` | `Model` protocol, scripted model, Ollama, `complete_as` |
| `src/underwriting/tracing.py` | Span per agent call |
| `src/underwriting/agents/` | Intake, enrichment, scoring, and recommendation |
| `src/underwriting/pipeline.py` | `underwrite`. Live runs use local Ollama |
| `src/underwriting/fixtures/applications.py` | APP-001, APP-002, APP-003, APP-TIMEOUT |
| `.github/workflows/ci.yml` | pytest |
