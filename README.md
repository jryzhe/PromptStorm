# PromptStorm CLI

PromptStorm lets two AI models run a terminal session through Vercel AI Gateway while you steer the conversation. It supports debates, collaborative discussions, and character dialogue.

## Features

- Run `debate`, `discussion`, or `dialogue` sessions from the terminal.
- Configure two participant models and one conclusion model.
- Add human input between model turns.
- Save session stats and turn transcripts locally.

## Requirements

- Python 3.11+
- A Vercel AI Gateway API key
- Gateway credits or billing enabled

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Create `.env`:

```bash
promptstorm setup
```

Or copy the example manually:

```bash
cp .env.example .env
```

```env
AI_GATEWAY_API_KEY=your-vercel-ai-gateway-key
PLAYER_A_MODEL=google/gemini-3-flash
PLAYER_B_MODEL=anthropic/claude-sonnet-4.6
REPORT_MODEL=anthropic/claude-sonnet-4.6
```

Environment variables override `.env`. If model values are missing, PromptStorm uses the defaults in `src/promptstorm/config.py`.

## Usage

```bash
promptstorm debate
promptstorm discussion
promptstorm dialogue
promptstorm stats
```

Compatibility entrypoints:

```bash
python3 main.py debate
python3 -m promptstorm --help
```

Each session asks for:

```text
Player A persona >
Player B persona >
Topic >
```

Personas are optional. Topic is required.

After the initial turns, the control panel lets you choose whether A, B, or neither currently has the stronger direction, add your own input, continue for more rounds, or output the final conclusion.

## Output

PromptStorm writes local history to:

- `data/debate_history.csv`
- `data/debate_turns.jsonl`

The `data/` directory is ignored by git.

## Notes

- `.env` parsing is implemented in `src/promptstorm/config.py`; `python-dotenv` is not required.
- If a live model is rate-limited, PromptStorm records the failed turn and preserves the partial transcript.
- If the conclusion model fails, PromptStorm prints a local fallback summary instead of losing the session.
