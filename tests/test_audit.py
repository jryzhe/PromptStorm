import json
import tempfile
import unittest
from pathlib import Path

from promptstorm.audit import AuditStore
from promptstorm.models import DebateSession, DebateTurn


class AuditTests(unittest.TestCase):
    def test_record_session_writes_history_and_each_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp))
            session = DebateSession(
                session_id="session-1",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="Freud",
                player_b="Adler",
                topic="A topic",
                winner="TIE",
                tokens_used=22,
                turns=[
                    DebateTurn(
                        session_id="session-1",
                        round=1,
                        speaker="A",
                        persona="Freud",
                        model="model-a",
                        response_text="A said something",
                        tokens_used=11,
                        timestamp="2026-06-05T00:00:01+08:00",
                    ),
                    DebateTurn(
                        session_id="session-1",
                        round=1,
                        speaker="B",
                        persona="Adler",
                        model="model-b",
                        response_text="B replied",
                        tokens_used=11,
                        timestamp="2026-06-05T00:00:02+08:00",
                        status="error",
                        error="RuntimeError: RateLimitError: 429",
                    ),
                ],
            )

            store.record_session(session)

            history = (Path(tmp) / "debate_history.csv").read_text(encoding="utf-8")
            self.assertIn("Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used", history)
            self.assertNotIn("Report_Path", history)
            self.assertIn("session-1", history)
            turns = (Path(tmp) / "debate_turns.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(turns), 2)
            self.assertEqual(json.loads(turns[0])["response_text"], "A said something")
            self.assertEqual(json.loads(turns[0])["status"], "ok")
            self.assertEqual(json.loads(turns[1])["status"], "error")
            self.assertIn("RateLimitError: 429", json.loads(turns[1])["error"])

    def test_format_stats_reports_leaderboard_and_token_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp))
            history_path = Path(tmp) / "debate_history.csv"
            history_path.write_text(
                "Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used\n"
                "s1,t,Freud,Adler,x,A,10\n"
                "s2,t,Freud,Adler,y,B,20\n"
                "s3,t,Freud,Adler,z,TIE,30\n",
                encoding="utf-8",
            )

            output = store.format_stats()

            self.assertIn("Total debates: 3", output)
            self.assertIn("Total tokens: 60", output)
            self.assertIn("Tie rate: 33.33%", output)
            self.assertIn("Freud", output)
            self.assertIn("Adler", output)

    def test_record_session_removes_legacy_report_path_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp))
            history_path = Path(tmp) / "debate_history.csv"
            history_path.write_text(
                "Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used,Report_Path\n"
                "old,t,A,B,old topic,A,10,reports/old.md\n",
                encoding="utf-8",
            )
            session = DebateSession(
                session_id="new",
                timestamp="2026-06-05T00:00:00+08:00",
                player_a="A",
                player_b="B",
                topic="new topic",
                winner="B",
                tokens_used=12,
            )

            store.record_session(session)

            history = history_path.read_text(encoding="utf-8")
            self.assertIn("Session_ID,Timestamp,Player_A,Player_B,Topic,Winner,Tokens_Used\n", history)
            self.assertNotIn("Report_Path", history)
            self.assertIn("old,t,A,B,old topic,A,10", history)
            self.assertIn("new,2026-06-05T00:00:00+08:00,A,B,new topic,B,12", history)


if __name__ == "__main__":
    unittest.main()
