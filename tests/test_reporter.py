import unittest

from promptstorm.models import DebateSession, DebateTurn, ModelResponse, PromptStormConfig
from promptstorm.reporter import ConclusionWriter


class FakeConclusionProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        text = "## Final Conclusion\nThis conclusion follows the human verdict."
        if on_token:
            for token in text.split():
                on_token(token + " ")
        return ModelResponse(text=text, tokens_used=15)


class ReporterTests(unittest.TestCase):
    def test_generate_conclusion_uses_terminal_prompt_and_human_verdict(self):
        provider = FakeConclusionProvider()
        writer = ConclusionWriter(provider=provider)
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        session = DebateSession(
            session_id="session-terminal",
            timestamp="2026-06-05T00:00:00+08:00",
            player_a="Freud",
            player_b="Adler",
            topic="A hard choice",
            winner=None,
            tokens_used=20,
            turns=[
                DebateTurn(
                    session_id="session-terminal",
                    round=1,
                    speaker="A",
                    persona="Freud",
                    model="model-a",
                    response_text="A argues from the past.",
                    tokens_used=10,
                    timestamp="2026-06-05T00:00:01+08:00",
                ),
                DebateTurn(
                    session_id="session-terminal",
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

        text, tokens = writer.generate_conclusion(session, "TIE", config)

        self.assertIn("Final Conclusion", text)
        self.assertEqual(tokens, 15)
        self.assertEqual(provider.calls[0]["model"], "model-report")
        prompt = provider.calls[0]["messages"][-1]["content"]
        self.assertIn("Human Verdict: TIE", prompt)
        self.assertIn("A argues from the past.", prompt)
        self.assertIn("B argues from action.", prompt)
        self.assertIn("Write a terminal conclusion", prompt)
        self.assertNotIn("Write a Markdown report", prompt)
        self.assertFalse(hasattr(writer, "write_report"))

    def test_fallback_conclusion_is_terminal_text_with_transcript(self):
        provider = FakeConclusionProvider()
        writer = ConclusionWriter(provider=provider)
        session = DebateSession(
            session_id="session-2",
            timestamp="2026-06-05T00:00:00+08:00",
            player_a="Point of View A",
            player_b="Point of View B",
            topic="A rate-limited conclusion",
            winner=None,
            tokens_used=20,
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

        conclusion = writer.build_fallback_conclusion(session, "C", "RateLimitError: 429")

        self.assertIn("Session ID: session-2", conclusion)
        self.assertIn("Human Verdict: TIE", conclusion)
        self.assertIn("Conclusion Generation Status: Terminal Fallback", conclusion)
        self.assertIn("RateLimitError: 429", conclusion)
        self.assertIn("A completed the debate.", conclusion)
        self.assertIn("B completed the debate.", conclusion)


if __name__ == "__main__":
    unittest.main()
