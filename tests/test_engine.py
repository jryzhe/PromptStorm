import unittest

from promptstorm.engine import DebateEngine, clean_response
from promptstorm.models import ModelResponse, PromptStormConfig, normalize_verdict


class FakeProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        speaker = "A" if model.endswith("a") else "B"
        response_text = f"{speaker} response {len(self.calls) + 1}"
        self.calls.append({"model": model, "messages": messages})
        if on_token:
            for token in response_text.split():
                on_token(token + " ")
        return ModelResponse(text=response_text, tokens_used=10)


class FailingProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        if model == "model-b":
            raise RuntimeError("RateLimitError: 429")
        return ModelResponse(text="A completed before failure", tokens_used=10)


class EngineTests(unittest.TestCase):
    def test_debate_runs_three_rounds_with_a_before_b(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)

        session = engine.run(
            topic="Should I build a CLI?",
            player_a_persona="",
            player_b_persona="Adler",
            config=config,
            session_id="session-1",
        )

        self.assertEqual([turn.round for turn in session.turns], [1, 1, 2, 2, 3, 3])
        self.assertEqual([turn.speaker for turn in session.turns], ["A", "B", "A", "B", "A", "B"])
        self.assertEqual(session.player_a, "Point of View A")
        self.assertEqual(session.player_b, "Adler")
        self.assertEqual(session.tokens_used, 60)
        self.assertEqual([call["model"] for call in provider.calls], ["model-a", "model-b"] * 3)

    def test_model_failure_records_error_turn_and_stops_debate(self):
        provider = FailingProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)

        session = engine.run(
            topic="Will this survive rate limits?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            session_id="session-rate-limit",
        )

        self.assertEqual([turn.speaker for turn in session.turns], ["A", "B"])
        self.assertEqual(session.turns[0].response_text, "A completed before failure")
        self.assertIn("Model call failed", session.turns[1].response_text)
        self.assertIn("RateLimitError: 429", session.turns[1].response_text)
        self.assertEqual(session.turns[1].tokens_used, 0)
        self.assertEqual(session.tokens_used, 10)
        self.assertEqual([call["model"] for call in provider.calls], ["model-a", "model-b"])

    def test_later_round_prompts_include_prior_transcript(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)

        engine.run(
            topic="How should we decide?",
            player_a_persona="Freud",
            player_b_persona="Adler",
            config=config,
            session_id="session-2",
        )

        round_two_a_prompt = provider.calls[2]["messages"][-1]["content"]
        self.assertIn("A response 1", round_two_a_prompt)
        self.assertIn("B response 2", round_two_a_prompt)

    def test_clean_response_removes_common_polite_fillers(self):
        cleaned = clean_response("好的，我明白您的意思了。真正的重點是行動。")

        self.assertEqual(cleaned, "真正的重點是行動。")

    def test_normalize_verdict_accepts_c_as_tie(self):
        self.assertEqual(normalize_verdict("a"), "A")
        self.assertEqual(normalize_verdict("B"), "B")
        self.assertEqual(normalize_verdict("c"), "TIE")
        self.assertEqual(normalize_verdict("tie"), "TIE")
        with self.assertRaises(ValueError):
            normalize_verdict("D")


if __name__ == "__main__":
    unittest.main()
