from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import uuid4

from .models import DebateSession, DebateTurn, PromptStormConfig
from .provider import ModelProvider


POLITE_FILLERS = [
    "好的，我明白您的意思了。",
    "好的，我明白你的意思了。",
    "我明白您的意思了。",
    "我明白你的意思了。",
    "好的，",
    "好的。",
    "Sure,",
    "Sure.",
]


class DebateEngine:
    def __init__(self, provider: ModelProvider, rounds: int = 3):
        self.provider = provider
        self.rounds = rounds

    def run(
        self,
        topic: str,
        player_a_persona: str,
        player_b_persona: str,
        config: PromptStormConfig,
        session_id: str | None = None,
        on_turn_start: Callable[[int, str, str], None] | None = None,
        on_token: Callable[[str, str], None] | None = None,
        on_turn_end: Callable[[int, str], None] | None = None,
    ) -> DebateSession:
        session = DebateSession(
            session_id=session_id or _new_session_id(),
            timestamp=_now(),
            player_a=_display_persona(player_a_persona, "A"),
            player_b=_display_persona(player_b_persona, "B"),
            topic=topic,
        )

        for round_number in range(1, self.rounds + 1):
            for speaker in ("A", "B"):
                persona = session.player_a if speaker == "A" else session.player_b
                model = config.player_a_model if speaker == "A" else config.player_b_model
                if on_turn_start:
                    on_turn_start(round_number, speaker, persona)
                response = self.provider.complete_stream(
                    model=model,
                    messages=_build_messages(
                        topic=topic,
                        round_number=round_number,
                        speaker=speaker,
                        persona=persona,
                        opponent=session.player_b if speaker == "A" else session.player_a,
                        transcript=_format_transcript(session.turns),
                    ),
                    on_token=(lambda token, active=speaker: on_token(active, token)) if on_token else None,
                )
                cleaned_text = clean_response(response.text)
                session.turns.append(
                    DebateTurn(
                        session_id=session.session_id,
                        round=round_number,
                        speaker=speaker,
                        persona=persona,
                        model=model,
                        response_text=cleaned_text,
                        tokens_used=response.tokens_used,
                        timestamp=_now(),
                    )
                )
                session.tokens_used += response.tokens_used
                if on_turn_end:
                    on_turn_end(round_number, speaker)

        return session


def clean_response(text: str) -> str:
    cleaned = text.strip()
    changed = True
    while changed:
        changed = False
        for filler in POLITE_FILLERS:
            if cleaned.startswith(filler):
                cleaned = cleaned[len(filler) :].lstrip()
                changed = True
    return cleaned


def _build_messages(
    topic: str,
    round_number: int,
    speaker: str,
    persona: str,
    opponent: str,
    transcript: str,
) -> list[dict[str, str]]:
    system = (
        f"You are Player {speaker}: {persona}. Debate the topic with a concrete, useful, "
        "high-signal argument. Avoid polite filler, disclaimers, and generic summaries. "
        "Respond in the same language as the user's topic."
    )
    if persona.startswith("Point of View"):
        system = (
            f"You are {persona}. You are not roleplaying a famous person. Debate the topic "
            "from a clear, concrete perspective. Avoid polite filler, disclaimers, and generic summaries. "
            "Respond in the same language as the user's topic."
        )

    if transcript:
        user_prompt = (
            f"Topic: {topic}\n"
            f"Round: {round_number}\n"
            f"Opponent: {opponent}\n\n"
            f"Transcript so far:\n{transcript}\n\n"
            "Now respond with your next argument. Keep it concise and directly engage the prior claims."
        )
    else:
        user_prompt = (
            f"Topic: {topic}\n"
            f"Round: {round_number}\n"
            f"Opponent: {opponent}\n\n"
            "Open the debate with a clear position and one or two strong reasons."
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _format_transcript(turns: list[DebateTurn]) -> str:
    return "\n".join(
        f"Round {turn.round} [{turn.speaker}: {turn.persona}] {turn.response_text}" for turn in turns
    )


def _display_persona(persona: str, speaker: str) -> str:
    stripped = persona.strip()
    return stripped if stripped else f"Point of View {speaker}"


def _new_session_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
