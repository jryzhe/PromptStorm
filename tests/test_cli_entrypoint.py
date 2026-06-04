import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from promptstorm.cli import session_has_model_error, write_report_safely
from promptstorm.models import DebateSession, DebateTurn, PromptStormConfig


class FailingWriter:
    def __init__(self, reports_dir):
        self.reports_dir = reports_dir
        self.fallback_reason = None

    def write_report(self, session, verdict, config):
        raise RuntimeError("RateLimitError: 429")

    def write_fallback_report(self, session, verdict, reason):
        self.fallback_reason = reason
        path = self.reports_dir / f"{session.session_id}.md"
        path.write_text("fallback report", encoding="utf-8")
        return path


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

    def test_write_report_safely_returns_fallback_when_report_model_fails(self):
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

            report_path, tokens, used_fallback = write_report_safely(writer, session, "A", config)

            self.assertTrue(used_fallback)
            self.assertEqual(tokens, 0)
            self.assertEqual(report_path.read_text(encoding="utf-8"), "fallback report")
            self.assertIn("RateLimitError: 429", writer.fallback_reason)

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


if __name__ == "__main__":
    unittest.main()
