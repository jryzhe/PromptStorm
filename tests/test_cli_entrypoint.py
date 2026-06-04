import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from promptstorm.cli import parse_round_count, session_has_model_error, write_conclusion_safely
from promptstorm.models import DebateSession, DebateTurn, PromptStormConfig


class FailingWriter:
    def __init__(self, reports_dir):
        self.reports_dir = reports_dir
        self.fallback_reason = None

    def write_report(self, session, verdict, config):
        raise RuntimeError("RateLimitError: 429")

    def generate_conclusion(self, session, verdict, config, on_token=None):
        raise RuntimeError("RateLimitError: 429")

    def write_fallback_report(self, session, verdict, reason):
        self.fallback_reason = reason
        path = self.reports_dir / f"{session.session_id}.md"
        path.write_text("fallback report", encoding="utf-8")
        return path

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

    def test_write_conclusion_safely_returns_fallback_when_report_model_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = FailingWriter(Path(tmp))
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
            self.assertFalse((Path(tmp) / "session-3.md").exists())

    def test_session_has_model_error_detects_failed_turn(self):
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
                    response_text="Model call failed: RuntimeError: RateLimitError: 429",
                    tokens_used=0,
                    timestamp="2026-06-05T00:00:01+08:00",
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


if __name__ == "__main__":
    unittest.main()
