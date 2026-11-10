# Meridian

Autonomous news intelligence and verification platform. See `MASTER_SYSTEM_BLUEPRINT.md` (kept
separately in `docs/blueprint/`) for the full design.

## Status

Step 1 of the build: **pure-logic foundations** (no database, no LLM, no network yet).

| Package | Purpose |
|---|---|
| `meridian.core` | UUIDv7 ids, clock abstraction, error types |
| `meridian.schemas` | Pydantic contracts: claims, evidence, verification, agents, events, articles |
| `meridian.verification` | Policy loader, evidence-strength maths, **verdict decision table (R1-R8)**, compound-claim aggregation |
| `meridian.evidence` | Verbatim quote verification and location |

## Setup

Requires Python 3.11 or newer.

```bash
# from the project root (the folder containing pyproject.toml)
python -m venv .venv

# activate the environment
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   Windows (cmd):         .venv\Scripts\activate.bat
#   macOS / Linux:         source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Run the checks

```bash
pytest                 # all tests (expected: 117 passed)
pytest --cov=meridian --cov-report=term-missing
ruff check .           # lint
ruff format --check .  # formatting
mypy                   # strict type check of src/
```

## Design rules enforced by tests

- The verdict label is chosen by `meridian.verification.decide` (pure code). No LLM picks labels.
- Evidence strength counts **origin groups**, never URLs (ten copies of one story = one group).
- Evidence is only valid when its excerpt matches the stored snapshot text verbatim.
- `schemas`, `core`, `verification`, `evidence` obey the layering rules (`tests/unit/test_architecture.py`).
