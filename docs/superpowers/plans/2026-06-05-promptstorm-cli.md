# PromptStorm CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable PromptStorm CLI with official API streaming, human judging, transcript audit logs, Markdown reports, and stats.

**Architecture:** The CLI is a small Python package with injected providers. Core orchestration is testable without network calls, while `VercelGatewayProvider` performs the real streaming calls at runtime.

**Tech Stack:** Python 3.11+, argparse, dataclasses, csv/jsonl, OpenAI-compatible Vercel AI Gateway client, pandas for stats.

---

## File Structure

- `pyproject.toml`: package metadata, console script, runtime dependencies.
- `README.md`: setup and usage.
- `.gitignore`: generated files and local configuration.
- `src/promptstorm/__init__.py`: package marker.
- `src/promptstorm/__main__.py`: `python -m promptstorm` entrypoint.
- `src/promptstorm/models.py`: dataclasses and verdict normalization.
- `src/promptstorm/config.py`: `.env` load/save logic.
- `src/promptstorm/provider.py`: streaming model provider protocol and Vercel implementation.
- `src/promptstorm/engine.py`: three-round debate loop.
- `src/promptstorm/reporter.py`: report generation flow.
- `src/promptstorm/audit.py`: history CSV, turn JSONL, and pandas stats.
- `src/promptstorm/cli.py`: argparse commands.
- `tests/test_config.py`: config behavior.
- `tests/test_engine.py`: debate ordering and transcript behavior.
- `tests/test_audit.py`: persistence and stats behavior.
- `tests/test_reporter.py`: report generation inputs and output.

## Tasks

### Task 1: Write Failing Tests

- [ ] Add standard-library `unittest` tests for config, engine, audit, and reporter modules.
- [ ] Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- [ ] Confirm imports fail because production modules do not exist yet.

### Task 2: Implement Core Models And Config

- [ ] Add dataclasses for settings, debate turns, debate sessions, and model responses.
- [ ] Implement verdict normalization for `A`, `B`, and `TIE`.
- [ ] Implement `.env` parsing and key saving without external dependencies.
- [ ] Run the config tests until green.

### Task 3: Implement Debate Engine

- [ ] Add provider protocol and fake-provider-friendly orchestration.
- [ ] Run exactly three rounds with A first and B second.
- [ ] Preserve all turn responses for audit and reporting.
- [ ] Run engine tests until green.

### Task 4: Implement Audit Store

- [ ] Append completed sessions to `data/debate_history.csv`.
- [ ] Append each turn to `data/debate_turns.jsonl`.
- [ ] Implement pandas-backed stats with a CSV fallback when pandas is unavailable.
- [ ] Run audit tests until green.

### Task 5: Implement Reporter

- [ ] Build a transcript-grounded report prompt.
- [ ] Stream or collect report model output.
- [ ] Write `reports/<session_id>.md`.
- [ ] Run reporter tests until green.

### Task 6: Implement CLI And Runtime Provider

- [ ] Add `promptstorm debate`, `promptstorm stats`, and `promptstorm setup`.
- [ ] Add Vercel AI Gateway provider using the OpenAI-compatible Python client.
- [ ] Keep model names in `.env`, not in interactive prompts.
- [ ] Run the full test suite.

### Task 7: Verify Package Smoke Tests

- [ ] Run `PYTHONPATH=src python3 -m promptstorm --help`.
- [ ] Run `PYTHONPATH=src python3 -m promptstorm stats` against an empty data directory.
- [ ] Confirm the CLI exits cleanly and prints useful guidance.

## Self-Review

- The plan covers model configuration, human judging, report generation, transcript audit logs, and stats.
- No implementation task requires live API calls in tests.
- The report model is named `REPORT_MODEL` and does not decide the human verdict.
