from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import DebateSession


HISTORY_FIELDS = [
    "Session_ID",
    "Timestamp",
    "Player_A",
    "Player_B",
    "Topic",
    "Winner",
    "Tokens_Used",
]


class AuditStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.history_path = self.data_dir / "debate_history.csv"
        self.turns_path = self.data_dir / "debate_turns.jsonl"

    def record_session(self, session: DebateSession) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._append_history(session)
        self._append_turns(session)

    def format_stats(self) -> str:
        if not self.history_path.exists():
            return "No debates recorded yet."

        return self._format_stats_from_records(self._read_records())

    def _append_history(self, session: DebateSession) -> None:
        self._migrate_history_schema()
        should_write_header = not self.history_path.exists() or self.history_path.stat().st_size == 0
        with self.history_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=HISTORY_FIELDS)
            if should_write_header:
                writer.writeheader()
            writer.writerow(
                {
                    "Session_ID": session.session_id,
                    "Timestamp": session.timestamp,
                    "Player_A": session.player_a,
                    "Player_B": session.player_b,
                    "Topic": session.topic,
                    "Winner": session.winner or "",
                    "Tokens_Used": session.tokens_used,
                }
            )

    def _migrate_history_schema(self) -> None:
        if not self.history_path.exists() or self.history_path.stat().st_size == 0:
            return

        with self.history_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []
            if "Report_Path" not in fieldnames:
                return
            rows = [{field: row.get(field, "") for field in HISTORY_FIELDS} for row in reader]

        with self.history_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=HISTORY_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def _append_turns(self, session: DebateSession) -> None:
        with self.turns_path.open("a", encoding="utf-8") as file:
            for turn in session.turns:
                file.write(json.dumps(turn.to_record(), ensure_ascii=False) + "\n")

    def _read_records(self) -> list[dict[str, str]]:
        with self.history_path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def _format_stats_from_records(self, records: Iterable[dict[str, object]]) -> str:
        rows = list(records)
        if not rows:
            return "No debates recorded yet."

        total_debates = len(rows)
        total_tokens = sum(_to_int(row.get("Tokens_Used", 0)) for row in rows)
        average_tokens = total_tokens / total_debates if total_debates else 0
        ties = sum(1 for row in rows if str(row.get("Winner", "")).upper() == "TIE")
        tie_rate = ties / total_debates * 100 if total_debates else 0
        leaderboard = _build_leaderboard(rows)

        lines = [
            "PromptStorm Stats",
            f"Total debates: {total_debates}",
            f"Total tokens: {total_tokens}",
            f"Average tokens/debate: {average_tokens:.2f}",
            f"Tie rate: {tie_rate:.2f}%",
            "",
            "Leaderboard:",
        ]
        if not leaderboard:
            lines.append("No winners recorded yet.")
        else:
            for rank, row in enumerate(leaderboard, start=1):
                lines.append(
                    f"{rank}. {row['name']} - {row['wins']}/{row['appearances']} wins "
                    f"({row['win_rate']:.2f}%)"
                )
        return "\n".join(lines)


def _build_leaderboard(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    stats: dict[str, dict[str, float]] = {}
    for row in rows:
        player_a = str(row.get("Player_A", "")).strip() or "Point of View A"
        player_b = str(row.get("Player_B", "")).strip() or "Point of View B"
        winner = str(row.get("Winner", "")).upper()
        for player in (player_a, player_b):
            stats.setdefault(player, {"appearances": 0, "wins": 0})
            stats[player]["appearances"] += 1
        if winner == "A":
            stats[player_a]["wins"] += 1
        elif winner == "B":
            stats[player_b]["wins"] += 1

    leaderboard = []
    for name, values in stats.items():
        appearances = int(values["appearances"])
        wins = int(values["wins"])
        win_rate = wins / appearances * 100 if appearances else 0
        leaderboard.append(
            {
                "name": name,
                "appearances": appearances,
                "wins": wins,
                "win_rate": win_rate,
            }
        )
    leaderboard.sort(key=lambda item: (-float(item["win_rate"]), -int(item["wins"]), str(item["name"])))
    return leaderboard


def _to_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0
