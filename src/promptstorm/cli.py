from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Sequence

from .audit import AuditStore
from .config import load_config, save_api_key
from .engine import DebateEngine
from .models import normalize_verdict
from .provider import VercelGatewayProvider
from .reporter import ReportWriter


RESET = "\033[0m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "stats_flag", False):
        return run_stats(Path.cwd())

    if args.command == "setup":
        return run_setup(Path.cwd())
    if args.command == "stats":
        return run_stats(Path.cwd())
    if args.command == "debate":
        return run_debate(Path.cwd())

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promptstorm", description="Run a terminal debate between two AI models.")
    parser.add_argument("--stats", action="store_true", dest="stats_flag", help="Show debate statistics and exit.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("setup", help="Create or update .env settings.")
    subparsers.add_parser("stats", help="Show debate statistics.")
    subparsers.add_parser("debate", help="Run a three-round debate.")
    return parser


def run_setup(root: Path) -> int:
    env_path = root / ".env"
    key = getpass.getpass("AI_GATEWAY_API_KEY: ").strip()
    if not key:
        print("No key entered; .env was not changed.")
        return 1
    save_api_key(env_path, key)
    print(f"Saved API key and default model settings to {env_path}.")
    return 0


def run_stats(root: Path) -> int:
    print(AuditStore(root / "data").format_stats())
    return 0


def run_debate(root: Path) -> int:
    env_path = root / ".env"
    config = load_config(env_path)
    if not config.api_key:
        print("Missing AI_GATEWAY_API_KEY.")
        key = getpass.getpass("Paste your Vercel AI Gateway key: ").strip()
        if not key:
            print("Cannot run debate without AI_GATEWAY_API_KEY.")
            return 1
        save_api_key(env_path, key)
        config = load_config(env_path)

    print(f"{BOLD}PromptStorm CLI{RESET}")
    player_a = input("Player A persona > ").strip()
    player_b = input("Player B persona > ").strip()
    topic = input("Topic > ").strip()
    if not topic:
        print("Topic is required.")
        return 1

    provider = VercelGatewayProvider(config.api_key)
    engine = DebateEngine(provider=provider)

    def on_turn_start(round_number: int, speaker: str, persona: str) -> None:
        color = CYAN if speaker == "A" else MAGENTA
        if speaker == "A":
            print(f"\n{BOLD}Round {round_number}{RESET}")
        print(f"{color}[{speaker}: {persona}]{RESET}")

    def on_token(speaker: str, token: str) -> None:
        color = CYAN if speaker == "A" else MAGENTA
        print(f"{color}{token}{RESET}", end="", flush=True)

    def on_turn_end(round_number: int, speaker: str) -> None:
        print()

    session = engine.run(
        topic=topic,
        player_a_persona=player_a,
        player_b_persona=player_b,
        config=config,
        on_turn_start=on_turn_start,
        on_token=on_token,
        on_turn_end=on_turn_end,
    )
    if session_has_model_error(session):
        print("\nA model call failed during the debate; saving the partial transcript.")

    final_support = run_control_loop(
        engine=engine,
        session=session,
        config=config,
        on_turn_start=on_turn_start,
        on_token=on_token,
        on_turn_end=on_turn_end,
    )
    writer = ReportWriter(provider=provider, reports_dir=root / "reports")
    print("\nOutputting conclusion...\n")
    conclusion, report_tokens, used_fallback = write_conclusion_safely(writer, session, final_support, config)
    print(conclusion)
    if used_fallback:
        print("\nReport model failed; printed a local fallback transcript summary instead.")
    session.winner = final_support
    session.report_path = ""
    session.tokens_used += report_tokens

    AuditStore(root / "data").record_session(session)
    print("Audit: data/debate_history.csv and data/debate_turns.jsonl")
    return 0


def run_control_loop(
    engine: DebateEngine,
    session,
    config,
    on_turn_start,
    on_token,
    on_turn_end,
) -> str:
    final_support = "TIE"
    while True:
        print("\nControl:")
        print("[A] 我目前支持 A，讓雙方再辯 N 回合")
        print("[B] 我目前支持 B，讓雙方再辯 N 回合")
        print("[R] 我目前都不支持，讓雙方再辯 N 回合")
        print("[I] 我想補充一句話")
        print("[O] 輸出結論並結束")
        choice = input("Your choice > ").strip().upper()
        if choice in {"A", "B", "R"}:
            final_support = "TIE" if choice == "R" else choice
            rounds = prompt_for_round_count()
            engine.continue_debate(
                session=session,
                config=config,
                human_support=final_support,
                rounds=rounds,
                on_turn_start=on_turn_start,
                on_token=on_token,
                on_turn_end=on_turn_end,
            )
            if session_has_model_error(session):
                print("\nA model call failed during the debate; you can add input or output the current transcript.")
        elif choice == "I":
            human_text = input("Your input > ").strip()
            if human_text:
                engine.add_human_input(session, human_text)
        elif choice == "O":
            return final_support
        else:
            print("Please enter A, B, R, I, or O.")


def prompt_for_round_count() -> int:
    while True:
        try:
            return parse_round_count(input("How many rounds? [1] > "))
        except ValueError:
            print("Please enter a positive integer.")


def parse_round_count(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        return 1
    rounds = int(value)
    if rounds < 1:
        raise ValueError("Round count must be positive.")
    return rounds


def write_report_safely(writer, session, verdict: str, config) -> tuple[Path, int, bool]:
    try:
        report_path, report_tokens = writer.write_report(session, verdict, config)
        return report_path, report_tokens, False
    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        report_path = writer.write_fallback_report(session, verdict, reason)
        return report_path, 0, True


def write_conclusion_safely(writer, session, verdict: str, config) -> tuple[str, int, bool]:
    try:
        conclusion, report_tokens = writer.generate_conclusion(session, verdict, config)
        return conclusion, report_tokens, False
    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        return writer.build_fallback_conclusion(session, verdict, reason), 0, True


def session_has_model_error(session) -> bool:
    return any(turn.response_text.startswith("Model call failed:") for turn in session.turns)
