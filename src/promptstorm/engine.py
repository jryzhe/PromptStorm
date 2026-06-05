from __future__ import annotations

import re
from datetime import datetime
from time import sleep as default_sleep
from typing import Callable
from uuid import uuid4

from .models import DebateSession, DebateTurn, PromptStormConfig
from .modes import ModeProfile, detect_output_language, format_language_instruction, get_mode_profile
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

DEBATE_SPEAKERS = {"A", "B"}


class DebateEngine:
    def __init__(
        self,
        provider: ModelProvider,
        rounds: int = 3,
        mode: str = "debate",
        rate_limit_retries: int = 0,
        rate_limit_retry_delay_seconds: float = 0,
        sleep: Callable[[float], None] = default_sleep,
    ):
        self.provider = provider
        self.rounds = rounds
        self.mode_profile = get_mode_profile(mode)
        self.rate_limit_retries = max(0, rate_limit_retries)
        self.rate_limit_retry_delay_seconds = max(0, rate_limit_retry_delay_seconds)
        self._sleep = sleep

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
        on_model_retry: Callable[[int, str, float, str], None] | None = None,
    ) -> DebateSession:
        session = DebateSession(
            session_id=session_id or _new_session_id(),
            timestamp=_now(),
            player_a=_display_persona(player_a_persona, "A", self.mode_profile),
            player_b=_display_persona(player_b_persona, "B", self.mode_profile),
            topic=topic,
        )

        self._run_rounds(
            session=session,
            config=config,
            start_round=1,
            rounds=self.rounds,
            human_support=None,
            on_turn_start=on_turn_start,
            on_token=on_token,
            on_turn_end=on_turn_end,
            on_model_retry=on_model_retry,
        )
        return session

    def continue_debate(
        self,
        session: DebateSession,
        config: PromptStormConfig,
        human_support: str,
        rounds: int,
        speaker_order: tuple[str, str] = ("A", "B"),
        on_turn_start: Callable[[int, str, str], None] | None = None,
        on_token: Callable[[str, str], None] | None = None,
        on_turn_end: Callable[[int, str], None] | None = None,
        on_model_retry: Callable[[int, str, float, str], None] | None = None,
    ) -> DebateSession:
        self._run_rounds(
            session=session,
            config=config,
            start_round=_next_round_number(session),
            rounds=rounds,
            human_support=human_support,
            speaker_order=speaker_order,
            on_turn_start=on_turn_start,
            on_token=on_token,
            on_turn_end=on_turn_end,
            on_model_retry=on_model_retry,
        )
        return session

    def add_human_input(self, session: DebateSession, text: str) -> DebateSession:
        session.turns.append(
            DebateTurn(
                session_id=session.session_id,
                round=_current_debate_round(session),
                speaker="USER",
                persona="Human",
                model="human",
                response_text=text.strip(),
                tokens_used=0,
                timestamp=_now(),
            )
        )
        return session

    def _run_rounds(
        self,
        session: DebateSession,
        config: PromptStormConfig,
        start_round: int,
        rounds: int,
        human_support: str | None,
        speaker_order: tuple[str, str] = ("A", "B"),
        on_turn_start: Callable[[int, str, str], None] | None = None,
        on_token: Callable[[str, str], None] | None = None,
        on_turn_end: Callable[[int, str], None] | None = None,
        on_model_retry: Callable[[int, str, float, str], None] | None = None,
    ) -> None:
        for round_number in range(start_round, start_round + max(0, rounds)):
            for speaker in speaker_order:
                persona = session.player_a if speaker == "A" else session.player_b
                model = config.player_a_model if speaker == "A" else config.player_b_model
                if on_turn_start:
                    on_turn_start(round_number, speaker, persona)
                try:
                    response = self._complete_stream_with_retries(
                        model=model,
                        messages=_build_messages(
                            topic=session.topic,
                            round_number=round_number,
                            speaker=speaker,
                            persona=persona,
                            opponent=session.player_b if speaker == "A" else session.player_a,
                            transcript=_format_transcript(session.turns),
                            human_support=human_support,
                            profile=self.mode_profile,
                            output_language=detect_output_language(
                                session.topic,
                                *[
                                    turn.response_text
                                    for turn in session.turns
                                    if turn.speaker == "USER"
                                ],
                            ),
                        ),
                        round_number=round_number,
                        speaker=speaker,
                        on_model_retry=on_model_retry,
                    )
                except Exception as exc:
                    error = f"{exc.__class__.__name__}: {exc}"
                    session.turns.append(
                        DebateTurn(
                            session_id=session.session_id,
                            round=round_number,
                            speaker=speaker,
                            persona=persona,
                            model=model,
                            response_text="The model did not produce a response.",
                            tokens_used=0,
                            timestamp=_now(),
                            status="error",
                            error=error,
                        )
                    )
                    if on_turn_end:
                        on_turn_end(round_number, speaker)
                    return
                cleaned_text = clean_response(response.text, self.mode_profile)
                if on_token and cleaned_text:
                    on_token(speaker, cleaned_text)
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

    def _complete_stream_with_retries(
        self,
        model: str,
        messages: list[dict[str, str]],
        round_number: int,
        speaker: str,
        on_model_retry: Callable[[int, str, float, str], None] | None,
    ) -> object:
        attempts = 0
        while True:
            try:
                return self.provider.complete_stream(model=model, messages=messages, on_token=None)
            except Exception as exc:
                error = _format_exception(exc)
                if attempts >= self.rate_limit_retries or not _is_rate_limit_error(error):
                    raise
                attempts += 1
                delay = self.rate_limit_retry_delay_seconds
                if on_model_retry:
                    on_model_retry(round_number, speaker, delay, error)
                if delay > 0:
                    self._sleep(delay)


def clean_response(text: str, profile: ModeProfile | None = None) -> str:
    cleaned = _strip_reasoning_blocks(text).strip()
    cleaned = _strip_turn_prefix(cleaned).strip()
    changed = True
    while changed:
        changed = False
        for filler in POLITE_FILLERS:
            if cleaned.startswith(filler):
                cleaned = cleaned[len(filler) :].lstrip()
                changed = True
    if profile and profile.name == "dialogue":
        cleaned = _clean_dialogue_reply(cleaned)
    return cleaned


def _format_exception(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def _is_rate_limit_error(error: str) -> bool:
    lowered = error.lower()
    return "ratelimit" in lowered or "rate_limit" in lowered or "429" in lowered


def _strip_reasoning_blocks(text: str) -> str:
    return re.sub(r"(?is)<think>.*?</think>\s*", "", text)


def _strip_turn_prefix(text: str) -> str:
    return re.sub(r"(?is)^\s*Round\s+\d+\s+\[[^\]]+\]\s*", "", text)


def _clean_dialogue_reply(text: str) -> str:
    cleaned = text.strip()
    cleaned = _strip_leading_speaker_label(cleaned)
    cleaned = _strip_leading_stage_directions(cleaned)

    quoted = re.search(r"「([^」]+)」", cleaned)
    if quoted:
        return quoted.group(1).strip()

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    if paragraphs:
        cleaned = paragraphs[0]
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        cleaned = lines[0]
    cleaned = _strip_leading_speaker_label(cleaned)
    cleaned = _strip_leading_stage_directions(cleaned)
    return cleaned.strip().strip('"').strip("'").strip()


def _strip_leading_speaker_label(text: str) -> str:
    return re.sub(r"^\s*[^\n:：]{1,24}[：:]\s*", "", text, count=1)


def _strip_leading_stage_directions(text: str) -> str:
    cleaned = text
    changed = True
    while changed:
        changed = False
        updated = re.sub(r"^\s*(?:（[^）]*）|\([^)]*\)|\[[^\]]*\]|【[^】]*】)\s*", "", cleaned, count=1)
        if updated != cleaned:
            cleaned = updated
            changed = True
    return cleaned


def _build_messages(
    topic: str,
    round_number: int,
    speaker: str,
    persona: str,
    opponent: str,
    transcript: str,
    human_support: str | None = None,
    profile: ModeProfile | None = None,
    output_language: str = "English",
) -> list[dict[str, str]]:
    active_profile = profile or get_mode_profile("debate")
    default_persona = active_profile.default_persona(speaker)
    if persona == default_persona:
        identity = f"You are {persona}. You are not roleplaying a famous person."
    else:
        identity = f"You are {active_profile.identity_label} {speaker}: {persona}."
    system = (
        f"{identity} {active_profile.system_instruction} "
        f"{format_language_instruction(output_language)}"
    )

    support_context = active_profile.support_context(human_support)

    if transcript:
        user_prompt = (
            f"Topic: {topic}\n"
            f"Round: {round_number}\n"
            f"{active_profile.counterpart_label}: {opponent}\n\n"
            f"{support_context}"
            f"Transcript so far:\n{transcript}\n\n"
            f"{active_profile.continuation_instruction}"
        )
    else:
        user_prompt = (
            f"Topic: {topic}\n"
            f"Round: {round_number}\n"
            f"{active_profile.counterpart_label}: {opponent}\n\n"
            f"{active_profile.opening_instruction}"
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _format_transcript(turns: list[DebateTurn]) -> str:
    return "\n".join(_format_turn(turn) for turn in turns)


def _format_turn(turn: DebateTurn) -> str:
    if turn.speaker == "USER":
        if turn.round > 0:
            return f"Human input after Round {turn.round}: {turn.response_text}"
        return f"Human input before Round 1: {turn.response_text}"
    if turn.status == "error":
        detail = f" ({turn.error})" if turn.error else ""
        return f"Round {turn.round} [{turn.speaker}: {turn.persona}] Model call failed{detail}"
    return f"Round {turn.round} [{turn.speaker}: {turn.persona}] {turn.response_text}"


def _display_persona(persona: str, speaker: str, profile: ModeProfile) -> str:
    stripped = persona.strip()
    return stripped if stripped else profile.default_persona(speaker)


def _next_round_number(session: DebateSession) -> int:
    current_round = _current_debate_round(session)
    if current_round == 0:
        return 1
    return current_round + 1


def _current_debate_round(session: DebateSession) -> int:
    debate_rounds = [turn.round for turn in session.turns if turn.speaker in DEBATE_SPEAKERS]
    return max(debate_rounds) if debate_rounds else 0


def _new_session_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
