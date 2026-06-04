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
    tokens_used: int = 0


@dataclass
class DebateTurn:
    session_id: str
    round: int
    speaker: str
    persona: str
    model: str
    response_text: str
    tokens_used: int
    timestamp: str
    status: str = "ok"
    error: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "round": self.round,
            "speaker": self.speaker,
            "persona": self.persona,
            "model": self.model,
            "response_text": self.response_text,
            "tokens_used": self.tokens_used,
            "timestamp": self.timestamp,
            "status": self.status,
            "error": self.error or "",
        }


@dataclass
class DebateSession:
    session_id: str
    timestamp: str
    player_a: str
    player_b: str
    topic: str
    winner: str | None = None
    tokens_used: int = 0
    turns: list[DebateTurn] = field(default_factory=list)


def normalize_verdict(raw_value: str) -> str:
    value = raw_value.strip().upper()
    if value in {"A", "B"}:
        return value
    if value in {"C", "TIE", "DRAW"}:
        return "TIE"
    raise ValueError("Verdict must be A, B, or C.")
