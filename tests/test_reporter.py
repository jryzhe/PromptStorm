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


if __name__ == "__main__":
    unittest.main()
