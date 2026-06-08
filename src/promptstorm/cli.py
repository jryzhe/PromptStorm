from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
from typing import Sequence

from .config import load_config_from_paths, save_api_key
from .engine import DebateEngine
from .modes import SESSION_MODE_NAMES, ModeProfile, get_mode_profile
from .provider import VercelGatewayProvider
from .reporter import ConclusionWriter


RESET = "\033[0m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"
TURN_DIVIDER = "-" * 72
DEFAULT_INITIAL_ROUNDS = 3
DIALOGUE_INITIAL_ROUNDS = 1
APP_DIR_NAME = "promptstorm"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return run_setup()
    if args.command in SESSION_MODE_NAMES:
        return run_session(Path.cwd(), args.command)

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptstorm",
        description="Run a terminal session between two AI participants.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("setup", help="Create or update .env settings.")
    for mode in SESSION_MODE_NAMES:
        profile = get_mode_profile(mode)
        subparsers.add_parser(profile.name, help=profile.help_text)
    return parser


def run_setup() -> int:
    env_path = default_env_path()
    current_config = load_config_from_paths([env_path])
    key = getpass.getpass("AI_GATEWAY_API_KEY: ").strip()
    if not key:
        print("No key entered; .env was not changed.")
        return 1
    print("Choose models available to your Vercel AI Gateway account.")
    print("Go to https://vercel.com/ -> ai-gateway -> models")
    player_a_model = prompt_model("Player A model", current_config.player_a_model)
    player_b_model = prompt_model("Player B model", current_config.player_b_model)
    report_model = prompt_model("Report model", current_config.report_model)
    save_api_key(
        env_path,
        key,
        player_a_model=player_a_model,
        player_b_model=player_b_model,
        report_model=report_model,
    )
    print(f"Saved API key and model settings to {env_path}.")
    print("A .env file in the current directory can override these settings.")
    return 0


def prompt_model(label: str, default: str) -> str:
    model = input(f"{label} [{default}]: ").strip()
    return model or default


def run_session(root: Path, mode: str) -> int:
    profile = get_mode_profile(mode)
    env_path = default_env_path()
    config = load_config_from_paths(config_paths(root))
    if not config.api_key:
        print("Missing AI_GATEWAY_API_KEY.")
        key = getpass.getpass("Paste your Vercel AI Gateway key: ").strip()
        if not key:
            print(f"Cannot run {profile.name} without AI_GATEWAY_API_KEY.")
            return 1
        save_api_key(env_path, key)
        config = load_config_from_paths(config_paths(root))

    print(f"{BOLD}{profile.title}{RESET}")
    player_a = input("Player A persona > ").strip()
    player_b = input("Player B persona > ").strip()
    topic = input("Topic > ").strip()
    if not topic:
        print("Topic is required.")
        return 1

    provider = VercelGatewayProvider(config.api_key)
    engine = DebateEngine(
        provider=provider,
        rounds=initial_rounds_for_mode(profile.name),
        mode=profile.name,
        rate_limit_retries=2,
        rate_limit_retry_delay_seconds=30,
    )
    last_heading_round: int | None = None

    def on_turn_start(round_number: int, speaker: str, persona: str) -> None:
        nonlocal last_heading_round
        show_round_label = round_number != last_heading_round
        last_heading_round = round_number
        print(format_turn_heading(round_number, speaker, persona, show_round_label=show_round_label))

    def on_response(speaker: str, text: str) -> None:
        color = CYAN if speaker == "A" else MAGENTA
        print(f"{color}{text}{RESET}", end="", flush=True)

    def on_turn_end(round_number: int, speaker: str) -> None:
        print()

    def on_model_retry(round_number: int, speaker: str, delay: float, error: str) -> None:
        print(
            f"\n模型暫時限流，{delay:g} 秒後重試 "
            f"(Round {round_number} {speaker}: {summarize_model_error(error)})"
        )

    session = engine.run(
        topic=topic,
        player_a_persona=player_a,
        player_b_persona=player_b,
        config=config,
        on_turn_start=on_turn_start,
        on_response=on_response,
        on_turn_end=on_turn_end,
        on_model_retry=on_model_retry,
    )
    if session_has_model_error(session):
        print(f"\nA model call failed during the {profile.name}: {latest_model_error_summary(session)}")
        print("Continuing with the partial transcript.")

    final_support = run_control_loop(
        engine=engine,
        session=session,
        config=config,
        profile=profile,
        on_turn_start=on_turn_start,
        on_response=on_response,
        on_turn_end=on_turn_end,
        on_model_retry=on_model_retry,
    )
    writer = ConclusionWriter(provider=provider)
    print(f"\nOutputting {profile.output_label}...\n")
    conclusion, _conclusion_tokens, used_fallback = write_conclusion_safely(
        writer,
        session,
        final_support,
        config,
        mode=profile.name,
    )
    print(conclusion)
    if used_fallback:
        print("\nConclusion model failed; printed a local fallback transcript summary instead.")
    return 0


def config_paths(root: Path) -> list[Path]:
    paths = [default_env_path()]
    local_env_path = root / ".env"
    if local_env_path.exists():
        paths.append(local_env_path)
    return paths


def default_env_path() -> Path:
    return default_config_dir() / ".env"


def default_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR_NAME


def run_control_loop(
    engine: DebateEngine,
    session,
    config,
    profile: ModeProfile,
    on_turn_start,
    on_response,
    on_turn_end,
    on_model_retry=None,
) -> str:
    final_support = "TIE"
    while True:
        print("\nControl:")
        for line in profile.control_lines:
            print(line)
        choice = input("請選擇 > ").strip().upper()
        if choice in {"A", "B", "R"}:
            final_support = _support_from_control_choice(choice)
            rounds = prompt_for_round_count()
            continue_from_control_choice(
                engine=engine,
                session=session,
                config=config,
                profile=profile,
                control_choice=choice,
                human_support=final_support,
                rounds=rounds,
                on_turn_start=on_turn_start,
                on_response=on_response,
                on_turn_end=on_turn_end,
                on_model_retry=on_model_retry,
            )
        elif choice == "I":
            human_text = input("你的補充 > ").strip()
            if human_text:
                engine.add_human_input(session, human_text)
                next_choice = input("已記錄補充。按 Enter 以目前方向繼續 1 回合，或輸入 A/B/R/O > ").strip().upper()
                if not next_choice:
                    continue_from_control_choice(
                        engine=engine,
                        session=session,
                        config=config,
                        profile=profile,
                        control_choice=_control_choice_from_support(final_support),
                        human_support=final_support,
                        rounds=1,
                        on_turn_start=on_turn_start,
                        on_response=on_response,
                        on_turn_end=on_turn_end,
                        on_model_retry=on_model_retry,
                    )
                elif next_choice in {"A", "B", "R"}:
                    final_support = _support_from_control_choice(next_choice)
                    rounds = prompt_for_round_count()
                    continue_from_control_choice(
                        engine=engine,
                        session=session,
                        config=config,
                        profile=profile,
                        control_choice=next_choice,
                        human_support=final_support,
                        rounds=rounds,
                        on_turn_start=on_turn_start,
                        on_response=on_response,
                        on_turn_end=on_turn_end,
                        on_model_retry=on_model_retry,
                    )
                elif next_choice == "O":
                    return final_support
                else:
                    print("請輸入 A、B、R、I 或 O。")
        elif choice == "O":
            return final_support
        else:
            print("請輸入 A、B、R、I 或 O。")


def continue_from_control_choice(
    engine: DebateEngine,
    session,
    config,
    profile: ModeProfile,
    control_choice: str,
    human_support: str,
    rounds: int,
    on_turn_start,
    on_response,
    on_turn_end,
    on_model_retry=None,
) -> None:
    engine.continue_debate(
        session=session,
        config=config,
        human_support=human_support,
        rounds=rounds,
        speaker_order=_speaker_order_for_control_choice(profile, control_choice),
        on_turn_start=on_turn_start,
        on_response=on_response,
        on_turn_end=on_turn_end,
        on_model_retry=on_model_retry,
    )
    if session_has_model_error(session):
        print(f"\nA model call failed during the {profile.name}: {latest_model_error_summary(session)}")
        print("You can add input or output the current transcript.")


def _support_from_control_choice(choice: str) -> str:
    return "TIE" if choice == "R" else choice


def _control_choice_from_support(human_support: str) -> str:
    return "R" if human_support == "TIE" else human_support


def _speaker_order_for_control_choice(profile: ModeProfile, control_choice: str) -> tuple[str, str]:
    if profile.name == "dialogue" and control_choice == "B":
        return ("B", "A")
    return ("A", "B")


def initial_rounds_for_mode(mode: str) -> int:
    if mode == "dialogue":
        return DIALOGUE_INITIAL_ROUNDS
    return DEFAULT_INITIAL_ROUNDS


def latest_model_error_summary(session) -> str:
    for turn in reversed(getattr(session, "turns", [])):
        if getattr(turn, "status", "ok") == "error":
            return summarize_model_error(getattr(turn, "error", "") or "Unknown error")
    return "Unknown error"


def summarize_model_error(error: str) -> str:
    compact = " ".join(str(error).split())
    if "429" in compact and ("RateLimitError" in compact or "rate_limit" in compact):
        if "Free tier requests" in compact:
            return "RateLimitError: 429 - Free tier requests on this model are rate-limited."
        return "RateLimitError: 429"
    if len(compact) > 240:
        return compact[:237] + "..."
    return compact


def prompt_for_round_count() -> int:
    while True:
        try:
            return parse_round_count(input("要繼續幾回合？（每回合兩位各回一句）[1] > "))
        except ValueError:
            print("請輸入正整數。")


def parse_round_count(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        return 1
    rounds = int(value)
    if rounds < 1:
        raise ValueError("Round count must be positive.")
    return rounds


def format_turn_heading(
    round_number: int,
    speaker: str,
    persona: str,
    show_round_label: bool | None = None,
) -> str:
    color = CYAN if speaker == "A" else MAGENTA
    lines = [""]
    if show_round_label is None:
        show_round_label = speaker == "A"
    if show_round_label:
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
