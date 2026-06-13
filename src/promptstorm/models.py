from __future__ import annotations

from collections.abc import Iterable
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


def format_transcript(turns: Iterable[DebateTurn]) -> str:
    return "\n".join(format_turn(turn) for turn in turns)


def format_turn(turn: DebateTurn) -> str:
    if turn.speaker == "USER":
        if turn.round > 0:
            return f"Human input after Round {turn.round}: {turn.response_text}"
        return f"Human input before Round 1: {turn.response_text}"
    if turn.status == "error":
        detail = f" ({turn.error})" if turn.error else ""
        return f"Round {turn.round} [{turn.speaker}: {turn.persona}] Model call failed{detail}"
    return f"Round {turn.round} [{turn.speaker}: {turn.persona}] {turn.response_text}"


def human_inputs(session: DebateSession) -> list[str]:
    return [turn.response_text for turn in session.turns if turn.speaker == "USER"]
