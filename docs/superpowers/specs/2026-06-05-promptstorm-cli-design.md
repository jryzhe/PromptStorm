# PromptStorm CLI Design

## Product Shape

PromptStorm CLI is a terminal-only Python tool for running a three-round debate between two configured AI models. The user supplies an optional persona for each side and a topic. Player A always responds first, Player B responds second, and the debate stops after exactly three rounds.

The human user is the only judge. After the debate, the CLI asks the user to choose A, B, or tie. A separate report model may then write a Markdown report that summarizes the transcript according to the human verdict; it does not decide the verdict.

## Configuration

Model settings live in `.env`, not in the interactive debate flow.

Required:

```env
AI_GATEWAY_API_KEY=...
PLAYER_A_MODEL=google/gemini-...
PLAYER_B_MODEL=anthropic/claude-...
REPORT_MODEL=anthropic/claude-...
```

If `.env` or the API key is missing, the CLI prompts for the missing key and saves it to `.env`. Model names may use defaults, but the user can edit `.env` to change them.

## CLI Flow

`promptstorm debate` asks:

```text
Player A persona >
Player B persona >
Topic >
```

If a persona is blank, that side is labeled `Point of View A` or `Point of View B` and debates the topic without roleplay.

The debate display streams text in color-coded terminal blocks:

```text
Round 1
[A: Freud]
...

[B: Adler]
...
```

After round 3:

```text
Judge:
[A] A wins
[B] B wins
[C] Tie

Your vote >
```

## Data Model

PromptStorm records both session-level audit data and turn-level transcript data.

`data/debate_history.csv` stores one row per completed debate:

```text
Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used,Report_Path
```

`data/debate_turns.jsonl` stores one JSON object per model response:

```json
{
  "session_id": "20260605-abc123",
  "round": 1,
  "speaker": "A",
  "persona": "Freud",
  "model": "google/gemini-...",
  "response_text": "...",
  "tokens_used": 321,
  "timestamp": "2026-06-05T00:00:00+08:00"
}
```

Reports are written to `reports/<session_id>.md` and include the topic, players, models, human verdict, and a summary grounded in the recorded transcript.

## Architecture

The implementation uses focused Python modules:

- `config.py`: load and save `.env` settings.
- `models.py`: shared dataclasses for config, turns, sessions, and results.
- `provider.py`: Vercel AI Gateway streaming provider using an OpenAI-compatible client.
- `engine.py`: three-round debate orchestration.
- `reporter.py`: report prompt construction and Markdown file writing.
- `audit.py`: CSV/JSONL persistence and stats loading with pandas.
- `cli.py`: argparse-based terminal interface.

The provider is injected into the engine so tests can use deterministic fake providers without calling external APIs.

## Testing

Unit tests cover:

- `.env` parsing and saving.
- Debate turn ordering and three-round stop behavior.
- Human verdict normalization.
- Transcript persistence.
- Report prompt inputs.
- Stats aggregation from recorded history.

Runtime API calls are not made during tests.
