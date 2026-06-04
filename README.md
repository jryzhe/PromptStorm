# PromptStorm CLI

PromptStorm CLI runs a three-round terminal debate between two AI models through Vercel AI Gateway. Player A always speaks first, Player B replies second, and the human user is the judge.

## What It Does

- Asks for two optional player personas and one topic.
- Streams an initial three-round A/B debate in the terminal.
- Lets the human user steer the debate after round 3.
- Outputs the final conclusion directly in the terminal.
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

This installs the runtime package used by the CLI: `openai` for Vercel AI Gateway calls.

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

Only `AI_GATEWAY_API_KEY` is secret. `REPORT_MODEL` is used for the final terminal conclusion. The model names can be changed whenever you want to try different Gateway models.

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

After three rounds, PromptStorm opens the control panel:

```text
Control:
[A] 我目前支持 A，讓雙方再辯 N 回合
[B] 我目前支持 B，讓雙方再辯 N 回合
[R] 我目前都不支持，讓雙方再辯 N 回合
[I] 我想補充一句話
[O] 輸出結論並結束
```

`A`, `B`, and `R` ask how many additional rounds to run. Press Enter to use the default of 1 round. The speaking order stays A then B, but the prompt tells both models where the human currently stands.

`I` adds your own message to the transcript. The next model calls can use it as context.

`O` generates the final conclusion and prints it directly in the terminal.

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

Debates write session history to `data/debate_history.csv` and turn transcripts to `data/debate_turns.jsonl`.

`data/debate_history.csv` stores one row per completed debate.

`data/debate_history.csv` uses this schema:

```text
Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used
```

`data/debate_turns.jsonl` stores each transcript event with session id, debate round number, speaker, persona, model, response text, token count, timestamp, status, and error detail. Human input is kept in transcript order but does not advance the next A/B debate round.

The final conclusion is printed in the terminal. If the conclusion model is rate-limited or fails, PromptStorm prints a local fallback summary with the human position and full transcript instead of losing the completed debate.

## Testing

Run the unit tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Compile-check the Python files:

```bash
.venv/bin/python -m compileall src tests main.py
```

Smoke-test the CLI:

```bash
python3 main.py --stats
python3 -m promptstorm --help
```

## Troubleshooting

If Python says `ModuleNotFoundError: No module named 'openai'`, the dependency is not installed in your current environment. Activate `.venv` and reinstall:

```bash
source .venv/bin/activate
python3 -m pip install -e .
```

If the live debate fails with `RateLimitError: 429`, the project is reaching Vercel AI Gateway, but the selected model or free-tier credits are rate-limited. Try a cheaper or less restricted model, wait for the limit to reset, or top up Gateway credits.

If a player model is rate-limited during the debate, PromptStorm records the failed turn, stops the remaining rounds, and still lets you save the partial transcript.

If the debate finishes but the conclusion model is rate-limited, PromptStorm prints a local fallback conclusion and still records the debate in `data/debate_history.csv` and `data/debate_turns.jsonl`.

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
