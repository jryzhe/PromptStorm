from __future__ import annotations

from pathlib import Path
from typing import Callable

from .models import DebateSession, PromptStormConfig, normalize_verdict
from .provider import ModelProvider


class ReportWriter:
    def __init__(self, provider: ModelProvider, reports_dir: Path):
        self.provider = provider
        self.reports_dir = Path(reports_dir)

    def write_report(
        self,
        session: DebateSession,
        verdict: str,
        config: PromptStormConfig,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[Path, int]:
        normalized_verdict = normalize_verdict(verdict)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        response = self.provider.complete_stream(
            model=config.report_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PromptStorm's report writer. The human user is the judge. "
                        "Do not change the verdict. Produce a useful Markdown report grounded only in the transcript."
                    ),
                },
                {"role": "user", "content": self._build_prompt(session, normalized_verdict)},
            ],
            on_token=on_token,
        )

        report_path = self.reports_dir / f"{session.session_id}.md"
        report_path.write_text(
            _metadata_header(session, normalized_verdict) + "\n\n" + response.text.strip() + "\n",
            encoding="utf-8",
        )
        return report_path, response.tokens_used

    def _build_prompt(self, session: DebateSession, verdict: str) -> str:
        return (
            f"Topic: {session.topic}\n"
            f"Player A: {session.player_a}\n"
            f"Player B: {session.player_b}\n"
            f"Human Verdict: {verdict}\n\n"
            f"Transcript:\n{_format_transcript(session)}\n\n"
            "Write a Markdown report with: executive conclusion, strongest points from A, strongest points from B, "
            "why the human verdict makes sense, and concrete next steps."
        )


def _metadata_header(session: DebateSession, verdict: str) -> str:
    return (
        "# PromptStorm Debate Report\n\n"
        f"Session ID: {session.session_id}\n"
        f"Topic: {session.topic}\n"
        f"Player A: {session.player_a}\n"
        f"Player B: {session.player_b}\n"
        f"Human Verdict: {verdict}"
    )


def _format_transcript(session: DebateSession) -> str:
    return "\n".join(
        f"Round {turn.round} [{turn.speaker}: {turn.persona}] {turn.response_text}" for turn in session.turns
    )
