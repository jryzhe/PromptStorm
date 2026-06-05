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


class RateLimitedOnceProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        if len(self.calls) == 1:
            raise RuntimeError("RateLimitError: Error code: 429 - free tier requests are rate-limited")
        return ModelResponse(text="Recovered after retry", tokens_used=8)


class ThinkyDialogueProvider:
    def __init__(self):
        self.calls = []
        self.received_stream_callback = False

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        self.received_stream_callback = on_token is not None
        raw_text = (
            "<think>\n"
            "我需要先分析學生和老師的心理狀態，然後給出完整劇本。\n"
            "</think>\n\n"
            "老師：[眉頭微蹙]我原意是希望你們能靈活運用知識，但確實該提前說明跨章節題型的比例。你看這樣好嗎？\n\n"
            "學生：可是這樣還是不公平。"
        )
        if on_token:
            on_token(raw_text)
        return ModelResponse(text=raw_text, tokens_used=20)


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
        self.assertEqual(session.turns[1].status, "error")
        self.assertIn("RateLimitError: 429", session.turns[1].error)
        self.assertEqual(session.turns[1].tokens_used, 0)
        self.assertEqual(session.tokens_used, 10)
        self.assertEqual([call["model"] for call in provider.calls], ["model-a", "model-b"])

    def test_rate_limited_turn_retries_before_recording_error(self):
        provider = RateLimitedOnceProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        retry_events = []
        sleeps = []
        engine = DebateEngine(
            provider=provider,
            rounds=1,
            rate_limit_retries=1,
            rate_limit_retry_delay_seconds=0.5,
            sleep=sleeps.append,
        )

        session = engine.run(
            topic="Will retry recover?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            session_id="session-retry",
            on_model_retry=lambda round_number, speaker, delay, error: retry_events.append(
                (round_number, speaker, delay, error)
            ),
        )

        self.assertEqual([call["model"] for call in provider.calls], ["model-a", "model-a", "model-b"])
        self.assertEqual(session.turns[0].status, "ok")
        self.assertEqual(session.turns[0].response_text, "Recovered after retry")
        self.assertEqual(retry_events[0][0:3], (1, "A", 0.5))
        self.assertIn("429", retry_events[0][3])
        self.assertEqual(sleeps, [0.5])

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

    def test_discussion_mode_prompts_collaborative_analysis_not_default_debate(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider, mode="discussion")

        engine.run(
            topic="兩位顧問討論產品該不該漲價。",
            player_a_persona="Steve Jobs",
            player_b_persona="Elon Musk",
            config=config,
            session_id="session-discussion",
        )

        system_prompt = provider.calls[0]["messages"][0]["content"]
        user_prompt = provider.calls[0]["messages"][-1]["content"]
        self.assertIn("work together", system_prompt)
        self.assertIn("Output language: Traditional Chinese.", system_prompt)
        self.assertIn("Start the discussion", user_prompt)
        self.assertNotIn("Debate the topic", system_prompt)
        self.assertNotIn("Open the debate", user_prompt)

    def test_dialogue_mode_prompts_natural_character_conversation(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider, mode="dialogue")

        engine.run(
            topic="A 是焦慮的新創 CEO，B 是老朋友。他們深夜討論要不要裁員。",
            player_a_persona="焦慮的新創 CEO",
            player_b_persona="老朋友",
            config=config,
            session_id="session-dialogue",
        )

        system_prompt = provider.calls[0]["messages"][0]["content"]
        user_prompt = provider.calls[0]["messages"][-1]["content"]
        self.assertIn("natural dialogue", system_prompt)
        self.assertIn("Output language: Traditional Chinese.", system_prompt)
        self.assertIn("Begin the scene", user_prompt)
        self.assertIn("exactly one brief spoken reply", system_prompt)
        self.assertIn("Do not write the other character's lines", system_prompt)
        self.assertIn("your character only", user_prompt)
        self.assertNotIn("Debate the topic", system_prompt)
        self.assertNotIn("Open the debate", user_prompt)

    def test_dialogue_mode_cleans_reasoning_labels_and_stage_directions_before_display(self):
        provider = ThinkyDialogueProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-a",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider, rounds=1, mode="dialogue")
        displayed = []

        session = engine.run(
            topic="學生和老師討論考題是否公平。",
            player_a_persona="老師",
            player_b_persona="學生",
            config=config,
            session_id="session-clean-dialogue",
            on_token=lambda speaker, token: displayed.append(token),
        )

        terminal_text = "".join(displayed)
        self.assertFalse(provider.received_stream_callback)
        self.assertNotIn("<think>", terminal_text)
        self.assertNotIn("老師：", terminal_text)
        self.assertNotIn("[眉頭微蹙]", terminal_text)
        self.assertNotIn("學生：可是", terminal_text)
        self.assertEqual(
            session.turns[0].response_text,
            "我原意是希望你們能靈活運用知識，但確實該提前說明跨章節題型的比例。你看這樣好嗎？",
        )

    def test_continue_debate_adds_rounds_with_human_support_context(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)
        session = engine.run(
            topic="Should we continue?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            session_id="session-continue",
        )

        engine.continue_debate(
            session=session,
            config=config,
            human_support="A",
            rounds=2,
        )

        self.assertEqual([turn.round for turn in session.turns[-4:]], [4, 4, 5, 5])
        self.assertEqual([turn.speaker for turn in session.turns[-4:]], ["A", "B", "A", "B"])
        extension_prompt = provider.calls[6]["messages"][-1]["content"]
        self.assertIn("Human currently supports A", extension_prompt)
        self.assertIn("Round 3", extension_prompt)

    def test_discussion_continuation_uses_mode_specific_human_context(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider, mode="discussion")
        session = engine.run(
            topic="Should the product get simpler?",
            player_a_persona="Designer",
            player_b_persona="Engineer",
            config=config,
            session_id="session-discussion-continue",
        )

        engine.continue_debate(session=session, config=config, human_support="A", rounds=1)

        extension_prompt = provider.calls[6]["messages"][-1]["content"]
        self.assertIn("A's perspective is currently more useful", extension_prompt)
        self.assertNotIn("Human currently supports A", extension_prompt)

    def test_add_human_input_records_user_turn(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)
        session = engine.run(
            topic="Should we add context?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            session_id="session-human-input",
        )

        engine.add_human_input(session, "請考慮成本限制。")

        self.assertEqual(session.turns[-1].speaker, "USER")
        self.assertEqual(session.turns[-1].persona, "Human")
        self.assertEqual(session.turns[-1].model, "human")
        self.assertEqual(session.turns[-1].round, 3)
        self.assertEqual(session.turns[-1].response_text, "請考慮成本限制。")

    def test_human_input_does_not_skip_next_debate_round(self):
        provider = FakeProvider()
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        engine = DebateEngine(provider=provider)
        session = engine.run(
            topic="Should human context affect numbering?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            session_id="session-human-round",
        )

        engine.add_human_input(session, "補充一個限制。")
        engine.continue_debate(session=session, config=config, human_support="TIE", rounds=1)

        self.assertEqual([turn.speaker for turn in session.turns[-3:]], ["USER", "A", "B"])
        self.assertEqual([turn.round for turn in session.turns[-3:]], [3, 4, 4])

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
