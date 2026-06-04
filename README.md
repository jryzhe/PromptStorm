# PromptStorm CLI

PromptStorm CLI runs a three-round terminal debate between two AI models through Vercel AI Gateway. Player A always speaks first, Player B replies second, and the human user is the judge.

## What It Does

- Asks for two optional player personas and one topic.
- Streams a three-round A/B debate in the terminal.
- Lets the human user vote for A, B, or a tie.
- Generates a Markdown report after the vote.
- Records debate history and turn-by-turn transcripts for stats.

## Requirements

- Python 3.11 or newer
- A Vercel AI Gateway API key
- Vercel AI Gateway credits or billing enabled

## First-Time Setup

Create a local virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the project and its dependencies:

```bash
python3 -m pip install -e .
```

This installs the runtime packages used by the CLI, including `openai` for Vercel AI Gateway calls and `pandas` for stats.

## Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
AI_GATEWAY_API_KEY=your-vercel-ai-gateway-key
PLAYER_A_MODEL=google/gemini-3.1-flash-lite
PLAYER_B_MODEL=alibaba/qwen-3-32b
REPORT_MODEL=openai/gpt-oss-120b
```

Only `AI_GATEWAY_API_KEY` is secret. The model names can be changed whenever you want to try different Gateway models.

The `.env` file is ignored by git, so do not commit your real key.

## Usage

Run a debate:

```bash
promptstorm debate
```

The CLI will ask:

```text
Player A persona >
Player B persona >
Topic >
```

You can leave the personas blank. In that case the CLI uses `Point of View A` and `Point of View B`.

After three rounds, vote:

```text
Judge:
[A] A wins
[B] B wins
[C] Tie
```

Show saved stats:

```bash
promptstorm stats
```

You can also use the compatibility entrypoint without installing the console script:

```bash
python3 main.py --stats
python3 main.py debate
```

## Output Files

Debates write session history to `data/debate_history.csv`, turn transcripts to `data/debate_turns.jsonl`, and reports to `reports/<session_id>.md`.

`data/debate_history.csv` stores one row per completed debate.

`data/debate_turns.jsonl` stores each model response with session id, round number, speaker, persona, model, response text, token count, and timestamp.

`reports/<session_id>.md` stores the final Markdown report generated after the human vote. If the report model is rate-limited or fails, PromptStorm saves a local fallback report with the human verdict and full transcript instead of losing the completed debate.

## Testing

Run the unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Compile-check the Python files:

```bash
python3 -m compileall src tests main.py
```

Smoke-test the CLI:

```bash
python3 main.py --stats
python3 -m promptstorm --help
```

## Troubleshooting

If Python says `ModuleNotFoundError: No module named 'openai'` or `No module named 'pandas'`, the dependencies are not installed in your current environment. Activate `.venv` and reinstall:

```bash
source .venv/bin/activate
python3 -m pip install -e .
```

If the live debate fails with `RateLimitError: 429`, the project is reaching Vercel AI Gateway, but the selected model or free-tier credits are rate-limited. Try a cheaper or less restricted model, wait for the limit to reset, or top up Gateway credits.

If the debate finishes but the report model is rate-limited, PromptStorm writes a local fallback report to `reports/<session_id>.md` and still records the debate in `data/debate_history.csv` and `data/debate_turns.jsonl`.

If the CLI says the API key is missing, check that `.env` exists in the project root and contains:

```env
AI_GATEWAY_API_KEY=...
```

## Suggested Demo Flow

```bash
source .venv/bin/activate
python3 main.py debate
python3 main.py --stats
```
