from __future__ import annotations

from .models import DebateSession, DebateTurn, PromptStormConfig, normalize_verdict
from .modes import detect_output_language, format_language_instruction, get_mode_profile
from .provider import ModelProvider


class ConclusionWriter:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    def generate_conclusion(
        self,
        session: DebateSession,
        verdict: str,
        config: PromptStormConfig,
        mode: str = "debate",
    ) -> str:
        profile = get_mode_profile(mode)
        normalized_verdict = normalize_verdict(verdict)
        output_language = detect_output_language(session.topic, *_human_inputs(session))
        response = self.provider.complete(
            model=config.report_model,
            messages=[
                {
                    "role": "system",
                    "content": profile.conclusion_system + "\n" + format_language_instruction(output_language),
                },
                {"role": "user", "content": self._build_prompt(session, normalized_verdict, mode)},
            ],
        )
        return response.text.strip()

    def build_fallback_conclusion(
        self,
        session: DebateSession,
        verdict: str,
        reason: str,
        mode: str = "debate",
    ) -> str:
        profile = get_mode_profile(mode)
        normalized_verdict = normalize_verdict(verdict)
        return (
            _conclusion_header(session, normalized_verdict, mode)
            + "\n"
            + "Conclusion Generation Status: Terminal Fallback\n\n"
            + "## Why This Conclusion Was Generated Locally\n\n"
            + f"The conclusion model failed before producing a final summary: `{reason}`\n\n"
            + f"The {profile.final_state_label.lower()} and full transcript are shown below.\n\n"
            + "## Transcript\n\n"
            + _format_transcript(session)
        )

    def _build_prompt(self, session: DebateSession, verdict: str, mode: str = "debate") -> str:
        profile = get_mode_profile(mode)
        return (
            f"Topic: {session.topic}\n"
            f"Player A: {session.player_a}\n"
            f"Player B: {session.player_b}\n"
            f"{profile.final_state_label}: {verdict}\n\n"
            f"Transcript:\n{_format_transcript(session)}\n\n"
            f"{profile.conclusion_instruction}"
        )


def _conclusion_header(session: DebateSession, verdict: str, mode: str = "debate") -> str:
    profile = get_mode_profile(mode)
    return (
        "# PromptStorm Terminal Conclusion\n\n"
        f"Session ID: {session.session_id}\n"
        f"Topic: {session.topic}\n"
        f"Player A: {session.player_a}\n"
        f"Player B: {session.player_b}\n"
        f"{profile.final_state_label}: {verdict}"
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


def _human_inputs(session: DebateSession) -> list[str]:
    return [turn.response_text for turn in session.turns if turn.speaker == "USER"]
