from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Sequence

from .audit import AuditStore
from .config import load_config, save_api_key
from .engine import DebateEngine
from .modes import SESSION_MODE_NAMES, ModeProfile, get_mode_profile
from .provider import VercelGatewayProvider
from .reporter import ConclusionWriter


RESET = "\033[0m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"
TURN_DIVIDER = "-" * 72


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "stats_flag", False):
        return run_stats(Path.cwd())

    if args.command == "setup":
        return run_setup(Path.cwd())
    if args.command == "stats":
        return run_stats(Path.cwd())
    if args.command in SESSION_MODE_NAMES:
        return run_session(Path.cwd(), args.command)

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promptstorm", description="Run a terminal session between two AI models.")
    parser.add_argument("--stats", action="store_true", dest="stats_flag", help="Show debate statistics and exit.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("setup", help="Create or update .env settings.")
    subparsers.add_parser("stats", help="Show debate statistics.")
    for mode in SESSION_MODE_NAMES:
        profile = get_mode_profile(mode)
        subparsers.add_parser(profile.name, help=profile.help_text)
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
    return run_session(root, "debate")


def run_session(root: Path, mode: str) -> int:
    profile = get_mode_profile(mode)
    env_path = root / ".env"
    config = load_config(env_path)
    if not config.api_key:
        print("Missing AI_GATEWAY_API_KEY.")
        key = getpass.getpass("Paste your Vercel AI Gateway key: ").strip()
        if not key:
            print(f"Cannot run {profile.name} without AI_GATEWAY_API_KEY.")
            return 1
        save_api_key(env_path, key)
        config = load_config(env_path)

    print(f"{BOLD}{profile.title}{RESET}")
    player_a = input("Player A persona > ").strip()
    player_b = input("Player B persona > ").strip()
    topic = input("Topic > ").strip()
    if not topic:
        print("Topic is required.")
        return 1

    provider = VercelGatewayProvider(config.api_key)
    engine = DebateEngine(provider=provider, mode=profile.name)

    def on_turn_start(round_number: int, speaker: str, persona: str) -> None:
        print(format_turn_heading(round_number, speaker, persona))

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
        print(f"\nA model call failed during the {profile.name}; saving the partial transcript.")

    final_support = run_control_loop(
        engine=engine,
        session=session,
        config=config,
        profile=profile,
        on_turn_start=on_turn_start,
        on_token=on_token,
        on_turn_end=on_turn_end,
    )
    writer = ConclusionWriter(provider=provider)
    print(f"\nOutputting {profile.output_label}...\n")
    conclusion, conclusion_tokens, used_fallback = write_conclusion_safely(
        writer,
        session,
        final_support,
        config,
        mode=profile.name,
    )
    print(conclusion)
    if used_fallback:
        print("\nConclusion model failed; printed a local fallback transcript summary instead.")
    session.winner = final_support
    session.tokens_used += conclusion_tokens

    AuditStore(root / "data").record_session(session)
    print("Audit: data/debate_history.csv and data/debate_turns.jsonl")
    return 0


def run_control_loop(
    engine: DebateEngine,
    session,
    config,
    profile: ModeProfile,
    on_turn_start,
    on_token,
    on_turn_end,
) -> str:
    final_support = "TIE"
    while True:
        print("\nControl:")
        for line in profile.control_lines:
            print(line)
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
                print(f"\nA model call failed during the {profile.name}; you can add input or output the current transcript.")
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


def format_turn_heading(round_number: int, speaker: str, persona: str) -> str:
    color = CYAN if speaker == "A" else MAGENTA
    lines = [""]
    if speaker == "A":
        lines.append(f"{BOLD}Round {round_number}{RESET}")
    lines.extend(
        [
            f"{BOLD}{TURN_DIVIDER}{RESET}",
            f"{color}[{speaker}: {persona}]{RESET}",
        ]
    )
    return "\n".join(lines)


def write_conclusion_safely(writer, session, verdict: str, config, mode: str = "debate") -> tuple[str, int, bool]:
    try:
        conclusion, conclusion_tokens = writer.generate_conclusion(session, verdict, config, mode=mode)
        return conclusion, conclusion_tokens, False
    except Exception as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        return writer.build_fallback_conclusion(session, verdict, reason, mode=mode), 0, True


def session_has_model_error(session) -> bool:
    return any(getattr(turn, "status", "ok") == "error" for turn in session.turns)
