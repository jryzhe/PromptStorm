import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import promptstorm.cli as cli_module
from promptstorm.cli import (
    TURN_DIVIDER,
    format_turn_heading,
    parse_round_count,
    session_has_model_error,
    write_conclusion_safely,
)
from promptstorm.models import DebateSession, DebateTurn, PromptStormConfig


class FailingWriter:
    def __init__(self):
        self.fallback_reason = None

    def generate_conclusion(self, session, verdict, config, on_token=None):
        raise RuntimeError("RateLimitError: 429")

    def build_fallback_conclusion(self, session, verdict, reason):
        self.fallback_reason = reason
        return "fallback terminal conclusion"


class CliEntrypointTests(unittest.TestCase):
    def test_main_py_runs_without_pythonpath_or_package_install(self):
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "main.py", "--stats"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No debates recorded yet.", result.stdout)

    def test_write_conclusion_safely_returns_fallback_when_conclusion_model_fails(self):
        with tempfile.TemporaryDirectory():
            writer = FailingWriter()
            session = DebateSession(
                session_id="session-3",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="A",
                player_b="B",
                topic="Topic",
            )
            config = PromptStormConfig(
                api_key="key",
                player_a_model="model-a",
                player_b_model="model-b",
                report_model="model-report",
            )

            text, tokens, used_fallback = write_conclusion_safely(writer, session, "A", config)

            self.assertTrue(used_fallback)
            self.assertEqual(tokens, 0)
            self.assertEqual(text, "fallback terminal conclusion")
            self.assertIn("RateLimitError: 429", writer.fallback_reason)

    def test_cli_has_no_report_file_safety_path(self):
        self.assertFalse(hasattr(cli_module, "write_report_safely"))

    def test_session_has_model_error_detects_failed_turn_status(self):
        session = DebateSession(
            session_id="session-4",
            timestamp="2026-06-05T00:00:00+08:00",
            player_a="A",
            player_b="B",
            topic="Topic",
            turns=[
                DebateTurn(
                    session_id="session-4",
                    round=1,
                    speaker="B",
                    persona="B",
                    model="model-b",
                    response_text="The model did not produce a response.",
                    tokens_used=0,
                    timestamp="2026-06-05T00:00:01+08:00",
                    status="error",
                    error="RuntimeError: RateLimitError: 429",
                )
            ],
        )

        self.assertTrue(session_has_model_error(session))

    def test_parse_round_count_defaults_to_one_and_rejects_invalid_values(self):
        self.assertEqual(parse_round_count(""), 1)
        self.assertEqual(parse_round_count("3"), 3)
        with self.assertRaises(ValueError):
            parse_round_count("0")
        with self.assertRaises(ValueError):
            parse_round_count("abc")

    def test_turn_heading_includes_separator_before_each_model_response(self):
        heading = format_turn_heading(2, "B", "Point of View B")

        self.assertTrue(heading.startswith("\n"))
        self.assertIn(TURN_DIVIDER, heading)
        self.assertIn("[B: Point of View B]", heading)


if __name__ == "__main__":
    unittest.main()
