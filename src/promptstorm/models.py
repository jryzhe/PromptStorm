from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptStormConfig:
    api_key: str
    player_a_model: str
    player_b_model: str
    report_model: str


@dataclass
class ModelResponse:
    text: str


@dataclass
class DebateTurn:
    session_id: str
    round: int
    speaker: str
    persona: str
    model: str
    response_text: str
    timestamp: str
    status: str = "ok"
    error: str | None = None


@dataclass
class DebateSession:
    session_id: str
    timestamp: str
    player_a: str
    player_b: str
    topic: str
    turns: list[DebateTurn] = field(default_factory=list)


def normalize_verdict(raw_value: str) -> str:
    value = raw_value.strip().upper()
    if value in {"A", "B"}:
        return value
    if value in {"C", "TIE", "DRAW"}:
        return "TIE"
    raise ValueError("Verdict must be A, B, or C.")
