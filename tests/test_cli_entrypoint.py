import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import promptstorm.cli as cli_module
from promptstorm.cli import (
    TURN_DIVIDER,
    format_turn_heading,
    run_control_loop,
    parse_round_count,
    session_has_model_error,
    write_conclusion_safely,
)
from promptstorm.modes import get_mode_profile
from promptstorm.models import DebateSession, DebateTurn, ModelResponse, PromptStormConfig


class FailingWriter:
    def __init__(self):
        self.fallback_reason = None

    def generate_conclusion(self, session, verdict, config, mode="debate", on_token=None):
        raise RuntimeError("RateLimitError: 429")

    def build_fallback_conclusion(self, session, verdict, reason, mode="debate"):
        self.fallback_reason = reason
        return "fallback terminal conclusion"


class RecordingControlEngine:
    def __init__(self, append_error_turn=False):
        self.append_error_turn = append_error_turn
        self.continue_calls = []
        self.human_inputs = []

    def continue_debate(self, **kwargs):
        self.continue_calls.append(kwargs)
        if self.append_error_turn:
            session = kwargs["session"]
            session.turns.append(
                DebateTurn(
                    session_id=session.session_id,
                    round=1,
                    speaker="A",
                    persona=session.player_a,
                    model="model-a",
                    response_text="The model did not produce a response.",
                    tokens_used=0,
                    timestamp="2026-06-05T00:00:02+08:00",
                    status="error",
                    error="RuntimeError: RateLimitError: 429",
                )
            )

    def add_human_input(self, session, text):
        self.human_inputs.append(text)
        session.turns.append(
            DebateTurn(
                session_id=session.session_id,
                round=0,
                speaker="USER",
                persona="Human",
                model="human",
                response_text=text,
                tokens_used=0,
                timestamp="2026-06-05T00:00:01+08:00",
            )
        )


class CliEntrypointTests(unittest.TestCase):
    def test_main_py_runs_without_pythonpath_or_package_install(self):
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(root / "main.py"), "--stats"],
                cwd=tmp,
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

    def test_parser_exposes_discussion_and_dialogue_commands(self):
        parser = cli_module.build_parser()

        self.assertEqual(parser.parse_args(["debate"]).command, "debate")
        self.assertEqual(parser.parse_args(["discussion"]).command, "discussion")
        self.assertEqual(parser.parse_args(["dialogue"]).command, "dialogue")

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

    def test_turn_heading_can_show_round_label_when_b_speaks_first(self):
        heading = format_turn_heading(4, "B", "老朋友", show_round_label=True)

        self.assertIn("Round 4", heading)
        self.assertIn("[B: 老朋友]", heading)

    def test_dialogue_control_loop_prints_dialogue_menu_and_exits_with_tie(self):
        result, output, engine = self.run_dialogue_control_loop(["O"])

        self.assertEqual(result, "TIE")
        self.assertIn("[A] 讓 A 更主動，讓場景繼續 N 回合", output)
        self.assertIn("[B] 讓 B 更主動，讓場景繼續 N 回合", output)
        self.assertIn("[R] 保持自然互動，讓場景繼續 N 回合", output)
        self.assertIn("[I] 我想補充一句話", output)
        self.assertIn("[O] 輸出收尾並結束", output)
        self.assertIn("請選擇 >", output)
        self.assertNotIn("Your choice >", output)
        self.assertEqual(engine.continue_calls, [])

    def test_dialogue_control_loop_continues_for_a_b_and_r_choices(self):
        cases = [
            ("A", "3", "A", 3, ("A", "B")),
            ("B", "2", "B", 2, ("B", "A")),
            ("R", "", "TIE", 1, ("A", "B")),
        ]

        for choice, round_input, expected_support, expected_rounds, expected_order in cases:
            with self.subTest(choice=choice):
                result, output, engine = self.run_dialogue_control_loop([choice, round_input, "O"])

                self.assertEqual(result, expected_support)
                self.assertEqual(len(engine.continue_calls), 1)
                call = engine.continue_calls[0]
                self.assertEqual(call["human_support"], expected_support)
                self.assertEqual(call["rounds"], expected_rounds)
                self.assertEqual(call["speaker_order"], expected_order)
                self.assertIn("Control:", output)

    def test_dialogue_control_loop_can_continue_immediately_after_human_input(self):
        result, output, engine = self.run_dialogue_control_loop(["I", "請讓 A 先道歉。", "", "O"])

        self.assertEqual(result, "TIE")
        self.assertEqual(engine.human_inputs, ["請讓 A 先道歉。"])
        self.assertEqual(len(engine.continue_calls), 1)
        self.assertEqual(engine.continue_calls[0]["human_support"], "TIE")
        self.assertEqual(engine.continue_calls[0]["rounds"], 1)
        self.assertEqual(engine.continue_calls[0]["speaker_order"], ("A", "B"))
        self.assertIn("你的補充 >", output)
        self.assertNotIn("Your input >", output)
        self.assertIn("已記錄補充。按 Enter 以目前方向繼續 1 回合，或輸入 A/B/R/O >", output)
        self.assertIn("Control:", output)

    def test_dialogue_control_loop_can_choose_b_direction_after_human_input(self):
        result, output, engine = self.run_dialogue_control_loop(["I", "請讓 B 先問問題。", "B", "", "O"])

        self.assertEqual(result, "B")
        self.assertEqual(engine.human_inputs, ["請讓 B 先問問題。"])
        self.assertEqual(len(engine.continue_calls), 1)
        self.assertEqual(engine.continue_calls[0]["human_support"], "B")
        self.assertEqual(engine.continue_calls[0]["rounds"], 1)
        self.assertEqual(engine.continue_calls[0]["speaker_order"], ("B", "A"))
        self.assertIn("要繼續幾回合？（每回合兩位各回一句）[1] >", output)

    def test_dialogue_control_loop_reprompts_until_round_count_is_positive(self):
        result, output, engine = self.run_dialogue_control_loop(["A", "0", "abc", "2", "O"])

        self.assertEqual(result, "A")
        self.assertEqual(engine.continue_calls[0]["rounds"], 2)
        self.assertIn("要繼續幾回合？（每回合兩位各回一句）[1] >", output)
        self.assertEqual(output.count("請輸入正整數。"), 2)

    def test_dialogue_control_loop_reports_model_error_after_continue(self):
        engine = RecordingControlEngine(append_error_turn=True)

        result, output, engine = self.run_dialogue_control_loop(["A", "", "O"], engine=engine)

        self.assertEqual(result, "A")
        self.assertEqual(engine.continue_calls[0]["human_support"], "A")
        self.assertIn("A model call failed during the dialogue:", output)
        self.assertIn("RateLimitError: 429", output)
        self.assertIn("You can add input or output the current transcript.", output)

    def test_dialogue_control_loop_localizes_invalid_choice_message(self):
        result, output, engine = self.run_dialogue_control_loop(["?", "O"])

        self.assertEqual(result, "TIE")
        self.assertEqual(engine.continue_calls, [])
        self.assertIn("請輸入 A、B、R、I 或 O。", output)
        self.assertNotIn("Please enter A, B, R, I, or O.", output)

    def test_dialogue_run_session_user_flow_writes_audit_after_control_choices(self):
        class FakeProvider:
            def __init__(self, api_key):
                self.api_key = api_key
                self.calls = 0

            def complete_stream(self, model, messages, on_token=None):
                self.calls += 1
                return ModelResponse(text=f"模擬角色回覆 {self.calls}。", tokens_used=3)

        class FakeConclusionWriter:
            def __init__(self, provider):
                self.provider = provider

            def generate_conclusion(self, session, verdict, config, mode="debate", on_token=None):
                return f"模擬收尾：{mode} / {verdict} / {len(session.turns)} turns", 5

            def build_fallback_conclusion(self, session, verdict, reason, mode="debate"):
                return "fallback"

        user_inputs = iter(
            [
                "焦慮的新創 CEO",
                "老朋友",
                "深夜在辦公室，A 正在猶豫明天要不要裁員，B 試著陪他想清楚。",
                "?",
                "I",
                "讓 B 不要急著給建議，先問 A 真正害怕的是什麼。",
                "B",
                "",
                "R",
                "2",
                "O",
            ]
        )

        def fake_input(prompt=""):
            value = next(user_inputs)
            print(prompt + value)
            return value

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("AI_GATEWAY_API_KEY=fake-key\n", encoding="utf-8")
            output = StringIO()

            with patch.object(cli_module, "VercelGatewayProvider", FakeProvider):
                with patch.object(cli_module, "ConclusionWriter", FakeConclusionWriter):
                    with patch("builtins.input", fake_input):
                        with redirect_stdout(output):
                            exit_code = cli_module.run_session(root, "dialogue")

            stdout = output.getvalue()
            turn_rows = [
                json.loads(line)
                for line in (root / "data" / "debate_turns.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(exit_code, 0)
        self.assertIn("請選擇 > ?", stdout)
        self.assertIn("請輸入 A、B、R、I 或 O。", stdout)
        self.assertIn("你的補充 > 讓 B 不要急著給建議", stdout)
        self.assertIn("已記錄補充。按 Enter 以目前方向繼續 1 回合，或輸入 A/B/R/O >", stdout)
        self.assertIn("要繼續幾回合？（每回合兩位各回一句）[1] >", stdout)
        self.assertIn("模擬收尾：dialogue / TIE / 9 turns", stdout)
        self.assertNotIn("Your choice >", stdout)
        self.assertNotIn("Your input >", stdout)
        self.assertEqual(len(turn_rows), 9)
        self.assertEqual(turn_rows[2]["speaker"], "USER")
        self.assertEqual(turn_rows[2]["response_text"], "讓 B 不要急著給建議，先問 A 真正害怕的是什麼。")
        self.assertEqual(turn_rows[3]["speaker"], "B")
        self.assertEqual(turn_rows[4]["speaker"], "A")

    def run_dialogue_control_loop(self, inputs, engine=None):
        engine = engine or RecordingControlEngine()
        session = DebateSession(
            session_id="session-control",
            timestamp="2026-06-05T00:00:00+08:00",
            player_a="角色 A",
            player_b="角色 B",
            topic="兩個角色在場景中對話。",
        )
        config = PromptStormConfig(
            api_key="key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="model-report",
        )
        output = StringIO()
        input_iter = iter(inputs)

        def fake_input(prompt=""):
            print(prompt, end="")
            return next(input_iter)

        with patch("builtins.input", fake_input):
            with redirect_stdout(output):
                result = run_control_loop(
                    engine=engine,
                    session=session,
                    config=config,
                    profile=get_mode_profile("dialogue"),
                    on_turn_start=lambda round_number, speaker, persona: None,
                    on_token=lambda speaker, token: None,
                    on_turn_end=lambda round_number, speaker: None,
                )

        return result, output.getvalue(), engine


if __name__ == "__main__":
    unittest.main()
