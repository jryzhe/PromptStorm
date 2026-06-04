import tempfile
import unittest
from pathlib import Path

from promptstorm.models import DebateSession, DebateTurn, ModelResponse, PromptStormConfig
from promptstorm.reporter import ReportWriter


class FakeReportProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        text = "## Final Report\nThis report follows the human verdict."
        if on_token:
            for token in text.split():
                on_token(token + " ")
        return ModelResponse(text=text, tokens_used=15)


class ReporterTests(unittest.TestCase):
    def test_reporter_uses_transcript_and_human_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeReportProvider()
            writer = ReportWriter(provider=provider, reports_dir=Path(tmp))
            config = PromptStormConfig(
                api_key="key",
                player_a_model="model-a",
                player_b_model="model-b",
                report_model="model-report",
            )
            session = DebateSession(
                session_id="session-1",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="Freud",
                player_b="Adler",
                topic="A hard choice",
                winner=None,
                tokens_used=20,
                report_path=None,
                turns=[
                    DebateTurn(
                        session_id="session-1",
                        round=1,
                        speaker="A",
                        persona="Freud",
                        model="model-a",
                        response_text="A argues from the past.",
                        tokens_used=10,
                        timestamp="2026-06-05T00:00:01+08:00",
                    ),
                    DebateTurn(
                        session_id="session-1",
                        round=1,
                        speaker="B",
                        persona="Adler",
                        model="model-b",
                        response_text="B argues from action.",
                        tokens_used=10,
                        timestamp="2026-06-05T00:00:02+08:00",
                    ),
                ],
            )

            report_path, tokens = writer.write_report(session, "TIE", config)

            self.assertEqual(tokens, 15)
            self.assertTrue(report_path.exists())
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("Session ID: session-1", report)
            self.assertIn("Human Verdict: TIE", report)
            prompt = provider.calls[0]["messages"][-1]["content"]
            self.assertIn("A argues from the past.", prompt)
            self.assertIn("B argues from action.", prompt)
            self.assertEqual(provider.calls[0]["model"], "model-report")

    def test_generate_conclusion_returns_text_without_writing_report_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeReportProvider()
            writer = ReportWriter(provider=provider, reports_dir=Path(tmp))
            config = PromptStormConfig(
                api_key="key",
                player_a_model="model-a",
                player_b_model="model-b",
                report_model="model-report",
            )
            session = DebateSession(
                session_id="session-terminal",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="A",
                player_b="B",
                topic="Terminal output",
                winner=None,
                tokens_used=0,
                report_path=None,
                turns=[],
            )

            text, tokens = writer.generate_conclusion(session, "B", config)

            self.assertIn("Final Report", text)
            self.assertEqual(tokens, 15)
            self.assertFalse((Path(tmp) / "session-terminal.md").exists())

    def test_fallback_report_writes_verdict_and_transcript_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeReportProvider()
            writer = ReportWriter(provider=provider, reports_dir=Path(tmp))
            session = DebateSession(
                session_id="session-2",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="Point of View A",
                player_b="Point of View B",
                topic="A rate-limited report",
                winner=None,
                tokens_used=20,
                report_path=None,
                turns=[
                    DebateTurn(
                        session_id="session-2",
                        round=1,
                        speaker="A",
                        persona="Point of View A",
                        model="model-a",
                        response_text="A completed the debate.",
                        tokens_used=10,
                        timestamp="2026-06-05T00:00:01+08:00",
                    ),
                    DebateTurn(
                        session_id="session-2",
                        round=1,
                        speaker="B",
                        persona="Point of View B",
                        model="model-b",
                        response_text="B completed the debate.",
                        tokens_used=10,
                        timestamp="2026-06-05T00:00:02+08:00",
                    ),
                ],
            )

            report_path = writer.write_fallback_report(session, "C", "RateLimitError: 429")

            report = report_path.read_text(encoding="utf-8")
            self.assertIn("Session ID: session-2", report)
            self.assertIn("Human Verdict: TIE", report)
            self.assertIn("Report Generation Status: Fallback", report)
            self.assertIn("RateLimitError: 429", report)
            self.assertIn("A completed the debate.", report)
            self.assertIn("B completed the debate.", report)


if __name__ == "__main__":
    unittest.main()
