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

    verdict = prompt_for_verdict()
    writer = ReportWriter(provider=provider, reports_dir=root / "reports")
    print("\nWriting report...")
    report_path, report_tokens, used_fallback = write_report_safely(writer, session, verdict, config)
    if used_fallback:
        print("Report model failed; saved a local fallback transcript report instead.")
    session.winner = verdict
    session.report_path = str(report_path)
    session.tokens_used += report_tokens

    AuditStore(root / "data").record_session(session)
    print(f"Report: {report_path}")
    print("Audit: data/debate_history.csv and data/debate_turns.jsonl")
    return 0


def prompt_for_verdict() -> str:
    print("\nJudge:")
    print("[A] A wins")
    print("[B] B wins")
    print("[C] Tie")
    while True:
        try:
            return normalize_verdict(input("Your vote > "))
        except ValueError:
            print("Please enter A, B, or C.")


def write_report_safely(writer, session, verdict: str, config) -> tuple[Path, int, bool]:
    try:
        report_path, report_tokens = writer.write_report(session, verdict, config)
        return report_path, report_tokens, False
    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        report_path = writer.write_fallback_report(session, verdict, reason)
        return report_path, 0, True


def session_has_model_error(session) -> bool:
    return any(turn.response_text.startswith("Model call failed:") for turn in session.turns)
