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

## Install

### macOS

```bash
brew install pipx
pipx ensurepath
pipx install git+https://github.com/jryzhe/PromptStorm.git
```

### Linux

Install `pipx` with your package manager, then install PromptStorm:

```bash
python3 -m pipx ensurepath
python3 -m pipx install git+https://github.com/jryzhe/PromptStorm.git
```

### Windows PowerShell

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install git+https://github.com/jryzhe/PromptStorm.git
```

Restart your terminal if `promptstorm` is not found after installation.

## Setup

```bash
promptstorm setup
```

`setup` stores your API key and default models in the user config directory:

- macOS / Linux: `~/.config/promptstorm/.env`
- Windows: `%APPDATA%\promptstorm\.env`

Environment variables override config values. A `.env` file in the current directory can also override the global config for that folder.

## Usage

```bash
promptstorm debate
promptstorm discussion
promptstorm dialogue
promptstorm stats
```

For local development from a cloned repo:

```bash
python3 -m pip install -e .
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

PromptStorm writes history to the user data directory:

- macOS / Linux: `~/.local/share/promptstorm/data/`
- Windows: `%LOCALAPPDATA%\promptstorm\data\`

The files are `debate_history.csv` and `debate_turns.jsonl`.

## Notes

- `.env` parsing is implemented in `src/promptstorm/config.py`; `python-dotenv` is not required.
- If a live model is rate-limited, PromptStorm records the failed turn and preserves the partial transcript.
- If the conclusion model fails, PromptStorm prints a local fallback summary instead of losing the session.
