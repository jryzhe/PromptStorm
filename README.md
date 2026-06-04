# PromptStorm CLI

PromptStorm CLI runs a three-round terminal debate between two AI models through Vercel AI Gateway. Player A always speaks first, Player B replies second, and the human user is the judge.

## Setup

Install the package dependencies:

```bash
python3 -m pip install -e .
```

Create or edit `.env`:

```env
AI_GATEWAY_API_KEY=your-vercel-ai-gateway-key
PLAYER_A_MODEL=google/gemini-3.1-flash-lite
PLAYER_B_MODEL=alibaba/qwen-3-32b
REPORT_MODEL=openai/gpt-oss-120b
```

## Usage

```bash
promptstorm debate
promptstorm stats
promptstorm setup
```

Compatibility entrypoint:

```bash
python3 main.py --stats
python3 main.py debate
```

Debates write session history to `data/debate_history.csv`, turn transcripts to `data/debate_turns.jsonl`, and reports to `reports/<session_id>.md`.
