from __future__ import annotations

import re
from datetime import datetime
from time import sleep as default_sleep
from typing import Callable
from uuid import uuid4

from .models import (
    DebateSession,
    DebateTurn,
    PromptStormConfig,
    format_transcript,
    human_inputs,
)
from .modes import (
    ModeProfile,
    detect_output_language,
    format_language_instruction,
    get_mode_profile,
)
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


class _StreamingResponseEmitter:
    def __init__(
        self,
        speaker: str,
        persona: str,
        profile: ModeProfile,
        emit: Callable[[str, str], None],
    ):
        self.speaker = speaker
        self.persona = persona
        self.profile = profile
        self.emit = emit
        self.raw_text = ""
        self.emitted_text = ""

    def receive(self, text: str) -> None:
        self.raw_text += text
        stable_source = _stable_reasoning_source(self.raw_text)
        if _has_unstable_leading_cleanup(
            stable_source,
            profile=self.profile,
            speaker=self.speaker,
            persona=self.persona,
        ):
            return
        self._emit_cleaned(clean_response(stable_source, self.profile))

    def finish(self, cleaned_text: str) -> None:
        self._emit_cleaned(cleaned_text)

    def _emit_cleaned(self, cleaned_text: str) -> None:
        if not cleaned_text.startswith(self.emitted_text):
            return
        delta = cleaned_text[len(self.emitted_text) :]
        if not delta:
            return
        self.emit(self.speaker, delta)
        self.emitted_text = cleaned_text


class DebateEngine:
    def __init__(
        self,
        provider: ModelProvider,
        rounds: int = 3,
        mode: str = "discussion",
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
        on_response: Callable[[str, str], None] | None = None,
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
            on_response=on_response,
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
        on_response: Callable[[str, str], None] | None = None,
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
            on_response=on_response,
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
        on_response: Callable[[str, str], None] | None = None,
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
                    on_delta = None
                    stream_emitter = None
                    if on_response:
                        stream_emitter = _StreamingResponseEmitter(
                            speaker=speaker,
                            persona=persona,
                            profile=self.mode_profile,
                            emit=on_response,
                        )

                        def on_delta(text: str) -> None:
                            stream_emitter.receive(text)

                    response, streamed = self._complete_with_retries(
                        model=model,
                        messages=_build_messages(
                            topic=session.topic,
                            round_number=round_number,
                            speaker=speaker,
                            persona=persona,
                            opponent=(
                                session.player_b
                                if speaker == "A"
                                else session.player_a
                            ),
                            transcript=format_transcript(session.turns),
                            human_support=human_support,
                            profile=self.mode_profile,
                            output_language=detect_output_language(
                                session.topic,
                                *human_inputs(session),
                            ),
                        ),
                        round_number=round_number,
                        speaker=speaker,
                        on_delta=on_delta,
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
                            timestamp=_now(),
                            status="error",
                            error=error,
                        )
                    )
                    if on_turn_end:
                        on_turn_end(round_number, speaker)
                    return
                cleaned_text = clean_response(response.text, self.mode_profile)
                if stream_emitter and streamed:
                    stream_emitter.finish(cleaned_text)
                if on_response and cleaned_text and not streamed:
                    on_response(speaker, cleaned_text)
                session.turns.append(
                    DebateTurn(
                        session_id=session.session_id,
                        round=round_number,
                        speaker=speaker,
                        persona=persona,
                        model=model,
                        response_text=cleaned_text,
                        timestamp=_now(),
                    )
                )
                if on_turn_end:
                    on_turn_end(round_number, speaker)

    def _complete_with_retries(
        self,
        model: str,
        messages: list[dict[str, str]],
        round_number: int,
        speaker: str,
        on_delta: Callable[[str], None] | None,
        on_model_retry: Callable[[int, str, float, str], None] | None,
    ) -> tuple[object, bool]:
        attempts = 0
        while True:
            emitted_delta = False

            def emit_delta(text: str) -> None:
                nonlocal emitted_delta
                emitted_delta = True
                if on_delta:
                    on_delta(text)

            try:
                stream_complete = getattr(self.provider, "stream_complete", None)
                if on_delta and callable(stream_complete):
                    response = stream_complete(
                        model=model,
                        messages=messages,
                        on_delta=emit_delta,
                    )
                    return response, True
                return self.provider.complete(model=model, messages=messages), False
            except Exception as exc:
                error = _format_exception(exc)
                if (
                    emitted_delta
                    or attempts >= self.rate_limit_retries
                    or not _is_rate_limit_error(error)
                ):
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


def _stable_reasoning_source(text: str) -> str:
    candidate = _drop_partial_reasoning_tag(text)
    open_start: int | None = None
    for match in re.finditer(r"(?is)</?think>", candidate):
        if match.group(0).lower() == "<think>":
            open_start = match.start()
        elif open_start is not None:
            open_start = None
    if open_start is not None:
        return candidate[:open_start]
    return candidate


def _drop_partial_reasoning_tag(text: str) -> str:
    lowered = text.lower()
    for tag in ("<think>", "</think>"):
        for length in range(len(tag) - 1, 0, -1):
            if lowered.endswith(tag[:length]):
                return text[:-length]
    return text


def _has_unstable_leading_cleanup(
    text: str,
    profile: ModeProfile,
    speaker: str,
    persona: str,
) -> bool:
    candidate = _strip_reasoning_blocks(text).lstrip()
    if not candidate:
        return False
    if _is_partial_turn_prefix(candidate) or _is_partial_polite_filler(candidate):
        return True
    return profile.name == "dialogue" and _is_unstable_dialogue_cleanup(
        candidate,
        speaker=speaker,
        persona=persona,
    )


def _is_partial_turn_prefix(text: str) -> bool:
    if _strip_turn_prefix(text) != text:
        return False
    lowered = text.lower()
    if "round ".startswith(lowered):
        return True
    return bool(re.fullmatch(r"(?is)round\s+\d*(?:\s+\[[^\]]*)?", text))


def _is_partial_polite_filler(text: str) -> bool:
    return any(filler.startswith(text) and filler != text for filler in POLITE_FILLERS)


def _is_unstable_dialogue_cleanup(text: str, speaker: str, persona: str) -> bool:
    if _is_partial_dialogue_label(text, speaker=speaker, persona=persona):
        return True
    without_label = _strip_leading_speaker_label(text)
    if _is_unclosed_leading_stage_direction(without_label):
        return True
    without_stage_directions = _strip_leading_stage_directions(without_label)
    return _has_unclosed_chinese_quote(without_stage_directions)


def _is_partial_dialogue_label(text: str, speaker: str, persona: str) -> bool:
    labels = {speaker.strip(), persona.strip()}
    lowered = text.lower()
    for label in labels:
        if not label:
            continue
        for separator in (":", "："):
            target = f"{label}{separator}".lower()
            if target.startswith(lowered) and target != lowered:
                return True
    return False


def _is_unclosed_leading_stage_direction(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    pairs = {"(": ")", "（": "）", "[": "]", "【": "】"}
    closing = pairs.get(stripped[0])
    return bool(closing and closing not in stripped)


def _has_unclosed_chinese_quote(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("「") and "」" not in stripped


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
    stage_direction_pattern = r"^\s*(?:（[^）]*）|\([^)]*\)|\[[^\]]*\]|【[^】]*】)\s*"
    changed = True
    while changed:
        changed = False
        updated = re.sub(stage_direction_pattern, "", cleaned, count=1)
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
