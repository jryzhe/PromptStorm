from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .models import PromptStormConfig


DEFAULT_PLAYER_A_MODEL = "google/gemini-3-flash"
DEFAULT_PLAYER_B_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_REPORT_MODEL = "anthropic/claude-sonnet-4.6"

CONFIG_KEYS = [
    "AI_GATEWAY_API_KEY",
    "PLAYER_A_MODEL",
    "PLAYER_B_MODEL",
    "REPORT_MODEL",
]


def load_config_from_paths(env_paths: Iterable[Path]) -> PromptStormConfig:
    values: dict[str, str] = {}
    for env_path in env_paths:
        for key, value in _read_env_file(env_path).items():
            if value:
                values[key] = value
    return _config_from_values(values)


def _config_from_values(values: dict[str, str]) -> PromptStormConfig:
    for key in CONFIG_KEYS:
        if os.environ.get(key):
            values[key] = os.environ[key]

    return PromptStormConfig(
        api_key=values.get("AI_GATEWAY_API_KEY", ""),
        player_a_model=values.get("PLAYER_A_MODEL", DEFAULT_PLAYER_A_MODEL),
        player_b_model=values.get("PLAYER_B_MODEL", DEFAULT_PLAYER_B_MODEL),
        report_model=values.get("REPORT_MODEL", DEFAULT_REPORT_MODEL),
    )


def save_api_key(
    env_path: Path,
    api_key: str,
    player_a_model: str | None = None,
    player_b_model: str | None = None,
    report_model: str | None = None,
) -> None:
    values = _read_env_file(env_path)
    values["AI_GATEWAY_API_KEY"] = api_key
    if player_a_model is None:
        values.setdefault("PLAYER_A_MODEL", DEFAULT_PLAYER_A_MODEL)
    else:
        values["PLAYER_A_MODEL"] = player_a_model
    if player_b_model is None:
        values.setdefault("PLAYER_B_MODEL", DEFAULT_PLAYER_B_MODEL)
    else:
        values["PLAYER_B_MODEL"] = player_b_model
    if report_model is None:
        values.setdefault("REPORT_MODEL", DEFAULT_REPORT_MODEL)
    else:
        values["REPORT_MODEL"] = report_model
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(_format_env(values), encoding="utf-8")


def _read_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _unquote(value.strip())
    return values


def _format_env(values: dict[str, str]) -> str:
    ordered_keys = [key for key in CONFIG_KEYS if key in values]
    extra_keys = sorted(key for key in values if key not in CONFIG_KEYS)
    lines = [f"{key}={values[key]}" for key in ordered_keys + extra_keys]
    return "\n".join(lines) + "\n"


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
