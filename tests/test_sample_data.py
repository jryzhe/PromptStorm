import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from promptstorm.audit import AuditStore
from promptstorm.config import load_config
from promptstorm.engine import clean_response
from promptstorm.models import ModelResponse
from promptstorm.modes import get_mode_profile
from promptstorm.reporter import ConclusionWriter

from tests.promptstorm_testdata import SAMPLE_ENV_TEXT, sample_config, sample_session_with_human_and_error


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def complete_stream(self, model, messages, on_token=None):
        self.calls.append({"model": model, "messages": messages})
        return ModelResponse(text="Sample conclusion", tokens_used=7)


class SampleDataTests(unittest.TestCase):
    def test_sample_env_file_loads_quotes_comments_and_model_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(SAMPLE_ENV_TEXT, encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                config = load_config(env_path)

        self.assertEqual(config.api_key, "sample-secret")
        self.assertEqual(config.player_a_model, "google/gemini-test-a")
        self.assertEqual(config.player_b_model, "anthropic/claude-test-b")
        self.assertEqual(config.report_model, "openai/report-test")

    def test_environment_variables_override_sample_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(SAMPLE_ENV_TEXT, encoding="utf-8")

            with patch.dict("os.environ", {"PLAYER_A_MODEL": "override/model-a"}, clear=True):
                config = load_config(env_path)

        self.assertEqual(config.api_key, "sample-secret")
        self.assertEqual(config.player_a_model, "override/model-a")
        self.assertEqual(config.player_b_model, "anthropic/claude-test-b")

    def test_sample_session_writes_csv_and_jsonl_without_losing_unicode_or_errors(self):
        session = sample_session_with_human_and_error()

        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp))
            store.record_session(session)

            with (Path(tmp) / "debate_history.csv").open(newline="", encoding="utf-8") as file:
                history_rows = list(csv.DictReader(file))
            turn_rows = [
                json.loads(line)
                for line in (Path(tmp) / "debate_turns.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(history_rows[0]["Topic"], session.topic)
        self.assertEqual(history_rows[0]["Winner"], "TIE")
        self.assertEqual(turn_rows[0]["response_text"], "先上線小流量，觀察真實需求。")
        self.assertEqual(turn_rows[2]["speaker"], "USER")
        self.assertEqual(turn_rows[3]["status"], "error")
        self.assertIn("RateLimitError: 429", turn_rows[3]["error"])

    def test_sample_session_conclusion_prompt_preserves_human_input_and_error_turns(self):
        provider = RecordingProvider()
        writer = ConclusionWriter(provider)

        text, tokens = writer.generate_conclusion(
            sample_session_with_human_and_error(),
            "TIE",
            sample_config(),
        )

        self.assertEqual(text, "Sample conclusion")
        self.assertEqual(tokens, 7)
        prompt = provider.calls[0]["messages"][-1]["content"]
        self.assertIn("Human input after Round 1: 請把企業客戶的 SLA 也納入考量。", prompt)
        self.assertIn("Round 2 [A: 產品經理 A] Model call failed", prompt)
        self.assertIn("RuntimeError: RateLimitError: 429", prompt)

    def test_model_output_cleanup_sample_cases(self):
        cases = [
            (
                "debate",
                "<think>hidden reasoning</think>\nRound 2 [A: Analyst] 好的，Here is the actual point.",
                "Here is the actual point.",
            ),
            (
                "dialogue",
                "老師：（看著考卷）「我們先釐清你覺得不公平的地方。」\n\n學生：我覺得範圍太廣。",
                "我們先釐清你覺得不公平的地方。",
            ),
        ]

        for mode, raw_text, expected in cases:
            with self.subTest(mode=mode):
                self.assertEqual(clean_response(raw_text, get_mode_profile(mode)), expected)


if __name__ == "__main__":
    unittest.main()
