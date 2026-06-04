from __future__ import annotations

from typing import Callable

from .models import DebateSession, DebateTurn, PromptStormConfig, normalize_verdict
from .provider import ModelProvider


class ConclusionWriter:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    def generate_conclusion(
        self,
        session: DebateSession,
        verdict: str,
        config: PromptStormConfig,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[str, int]:
        normalized_verdict = normalize_verdict(verdict)
        response = self.provider.complete_stream(
            model=config.report_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PromptStorm's terminal conclusion writer. The human user controls the debate. "
                        "Do not invent missing arguments. Produce a concise, useful conclusion grounded only in the transcript."
                    ),
                },
                {"role": "user", "content": self._build_prompt(session, normalized_verdict)},
            ],
            on_token=on_token,
        )
        return response.text.strip(), response.tokens_used

    def build_fallback_conclusion(self, session: DebateSession, verdict: str, reason: str) -> str:
        normalized_verdict = normalize_verdict(verdict)
        return (
            _conclusion_header(session, normalized_verdict)
            + "\n"
            + "Conclusion Generation Status: Terminal Fallback\n\n"
            + "## Why This Conclusion Was Generated Locally\n\n"
            + f"The conclusion model failed before producing a final summary: `{reason}`\n\n"
            + "The human position and full debate transcript are shown below.\n\n"
            + "## Transcript\n\n"
            + _format_transcript(session)
        )

    def _build_prompt(self, session: DebateSession, verdict: str) -> str:
        return (
            f"Topic: {session.topic}\n"
            f"Player A: {session.player_a}\n"
            f"Player B: {session.player_b}\n"
            f"Human Verdict: {verdict}\n\n"
            f"Transcript:\n{_format_transcript(session)}\n\n"
            "Write a terminal conclusion with: executive conclusion, strongest points from A, strongest points from B, "
            "why the human verdict makes sense, and concrete next steps. Keep it concise and readable in a terminal."
        )


def _conclusion_header(session: DebateSession, verdict: str) -> str:
    return (
        "# PromptStorm Terminal Conclusion\n\n"
        f"Session ID: {session.session_id}\n"
        f"Topic: {session.topic}\n"
        f"Player A: {session.player_a}\n"
        f"Player B: {session.player_b}\n"
        f"Human Verdict: {verdict}"
    )


def _format_transcript(session: DebateSession) -> str:
    return "\n".join(_format_turn(turn) for turn in session.turns)


def _format_turn(turn: DebateTurn) -> str:
    if turn.speaker == "USER":
        if turn.round > 0:
            return f"Human input after Round {turn.round}: {turn.response_text}"
        return f"Human input before Round 1: {turn.response_text}"
    if turn.status == "error":
        detail = f" ({turn.error})" if turn.error else ""
        return f"Round {turn.round} [{turn.speaker}: {turn.persona}] Model call failed{detail}"
    return f"Round {turn.round} [{turn.speaker}: {turn.persona}] {turn.response_text}"
