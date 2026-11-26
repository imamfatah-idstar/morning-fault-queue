# Morning Fault Queue (`Open-Router-Tesla`)

Tone-blind overnight Tesla vehicle fault triage reader powered by **OpenRouter** (defaulting to the free `openrouter/free` router, or `anthropic/claude-sonnet-4.5` when configured) and **Pydantic v2** deterministic safety overrides.

## Overview

Customer fault reports often mask critical safety issues behind calm phrasing (e.g., *"no rush at all"*, *"probably nothing"*) or inflate non-safety issues with dramatic wording. This project separates tone from physical risk by combining:

1. **Tone-blind classification (`triage_reader.py`)** — Instructs the model to ignore customer tone, evaluate visible text before cutoffs on truncated notes, and classify every report into `safety_urgent`, `soon`, or `routine`.
2. **Deterministic safety overrides (`schemas.py`)** — Uses a Pydantic v2 `@model_validator(mode="after")` (`enforce_safety_overrides`) on `FaultTriageResult` to guarantee `safety_urgent` whenever:
   - `vehicle_alert_code` is one of the six critical safety codes: `BRK_a001`, `BRK_w003`, `ABS_w002`, `ESP_w003`, `EPAS_a191`, `EPAS_w202`.
   - Physical brake or steering symptoms are present (e.g., soft/spongy/sinking brake pedal, grinding when braking, steering wheel tugging/pulling, heavy steering), even when `vehicle_alert_code` is `"NONE"`.
   - A wiper stalls mid-sweep or fails to park out of the driver's forward line of sight.

## Project Structure

- `triage_reader.py` — OpenRouter client (`get_openrouter_client`) and structured triage classifier (`classify_fault_report`).
- `schemas.py` — `FaultTriageResult` Pydantic model and `enforce_safety_overrides` validator.
- `run_batch.py` — Batch runner that classifies all 300 messages in `overnight_messages.json`, writes `triage_results.csv` (`id`, `urgency`, `fix_path`), and verifies row count and non-blank fields.
- `overnight_messages.json` — 300 overnight vehicle fault reports for batch triage.
- `smoke_test.py` — Offline Pydantic validator checks and live adversarial smoke tests (`MSG-10002`, `MSG-10048`, `MSG-10068`, `MSG-10297`, `MSG-10021`).
- `requirements.txt` — Python dependencies (`openai>=1.55.0`, `pydantic>=2.9.0`, `python-dotenv>=1.0.1`).
- `.env.example` — Environment variable template (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`).
- `.gitignore` — Excludes `.env`, `.venv/`, `__pycache__/`, and `*.pyc`.
- `openrouter_integration_setup_guide.md` — Detailed setup and integration reference.

## Setup

### 1. Create a Virtual Environment & Install Dependencies

**Windows (PowerShell):**
```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and add your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
# Free OpenRouter router (no credits required); override with e.g. anthropic/claude-sonnet-4.5 if funded
OPENROUTER_MODEL=openrouter/free
```

> Never commit `.env` to Git. It is already listed in `.gitignore`.

## Batch Queue Run (300 Messages)

Run `run_batch.py` to classify all 300 messages in `overnight_messages.json` and output `triage_results.csv` (`id`, `urgency`, `fix_path`):

```powershell
# Live OpenRouter run (uses OPENROUTER_MODEL from .env, defaulting to openrouter/free)
.\.venv\Scripts\python.exe run_batch.py

# Offline deterministic test run (no API key required)
.\.venv\Scripts\python.exe run_batch.py --offline
```

`run_batch.py` automatically verifies that `triage_results.csv` contains 300 rows and no blank `id`, `urgency`, or `fix_path` values.

## Verification & Smoke Tests

Run `smoke_test.py` to execute the offline Pydantic validator checks and (when `OPENROUTER_API_KEY` is set) the 5 adversarial smoke-test cases:

```powershell
.\.venv\Scripts\python.exe smoke_test.py
```

Expected adversarial test coverage:
- `MSG-10002` — Calm-sounding soft-brake report with `vehicle_alert_code = "NONE"` → `safety_urgent`
- `MSG-10048` — Relaxed `ABS_w002` report → `safety_urgent`
- `MSG-10068` — Wiper mid-sweep stall → `safety_urgent`
- `MSG-10297` — Truncated `ABS_w002` intake note → `safety_urgent`
- `MSG-10021` — Truncated charge-port latch note → `routine` or `soon`
