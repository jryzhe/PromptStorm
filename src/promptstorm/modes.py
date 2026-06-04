from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ModeProfile:
    name: str
    help_text: str
    title: str
    identity_label: str
    counterpart_label: str
    default_persona_template: str
    system_instruction: str
    opening_instruction: str
    continuation_instruction: str
    support_contexts: Mapping[str, str]
    control_lines: tuple[str, ...]
    output_label: str
    final_state_label: str
    conclusion_system: str
    conclusion_instruction: str

    def default_persona(self, speaker: str) -> str:
        return self.default_persona_template.format(speaker=speaker)

    def support_context(self, human_support: str | None) -> str:
        if not human_support:
            return ""
        return self.support_contexts.get(human_support, "")


DEBATE = ModeProfile(
    name="debate",
    help_text="Run an adversarial A/B debate.",
    title="PromptStorm Debate",
    identity_label="Player",
    counterpart_label="Opponent",
    default_persona_template="Point of View {speaker}",
    system_instruction=(
        "Debate the topic with a concrete, useful, high-signal argument. "
        "Challenge the other side, avoid polite filler, disclaimers, and generic summaries."
    ),
    opening_instruction="Open the debate with a clear position and one or two strong reasons.",
    continuation_instruction=(
        "Now respond with your next argument. Keep it concise and directly engage the prior claims."
    ),
    support_contexts={
        "A": (
            "Human currently supports A. Player A should strengthen their case; "
            "Player B should challenge A and try to change the human's mind.\n"
        ),
        "B": (
            "Human currently supports B. Player B should strengthen their case; "
            "Player A should challenge B and try to change the human's mind.\n"
        ),
        "TIE": "Human currently supports neither side. Both players should sharpen the unresolved conflict.\n",
    },
    control_lines=(
        "[A] 我目前支持 A，讓雙方再辯 N 回合",
        "[B] 我目前支持 B，讓雙方再辯 N 回合",
        "[R] 我目前都不支持，讓雙方再辯 N 回合",
        "[I] 我想補充一句話",
        "[O] 輸出結論並結束",
    ),
    output_label="conclusion",
    final_state_label="Human Verdict",
    conclusion_system=(
        "You are PromptStorm's terminal conclusion writer. The human user controls the debate. "
        "Do not invent missing arguments. Produce a concise, useful conclusion grounded only in the transcript."
    ),
    conclusion_instruction=(
        "Write a terminal conclusion with: executive conclusion, strongest points from A, strongest points from B, "
        "why the human verdict makes sense, and concrete next steps. Keep it concise and readable in a terminal."
    ),
)


DISCUSSION = ModeProfile(
    name="discussion",
    help_text="Run a collaborative A/B discussion.",
    title="PromptStorm Discussion",
    identity_label="Participant",
    counterpart_label="Other perspective",
    default_persona_template="Perspective {speaker}",
    system_instruction=(
        "You should work together with the other persona to analyze the topic, compare tradeoffs, "
        "fill blind spots, and move toward a useful synthesis. Do not default to attacking the other side "
        "unless the user explicitly frames the topic as adversarial."
    ),
    opening_instruction=(
        "Start the discussion with a clear perspective, useful considerations, and one or two practical tradeoffs."
    ),
    continuation_instruction=(
        "Continue the discussion by integrating prior points, adding nuance, and moving toward a useful synthesis."
    ),
    support_contexts={
        "A": (
            "A's perspective is currently more useful. Both participants should deepen that angle while still "
            "adding missing context and tradeoffs.\n"
        ),
        "B": (
            "B's perspective is currently more useful. Both participants should deepen that angle while still "
            "adding missing context and tradeoffs.\n"
        ),
        "TIE": "No clear direction yet. Both participants should clarify the tradeoffs and unresolved questions.\n",
    },
    control_lines=(
        "[A] A 的角度目前比較有幫助，讓雙方再分析 N 回合",
        "[B] B 的角度目前比較有幫助，讓雙方再分析 N 回合",
        "[R] 還沒有明確方向，讓雙方再分析 N 回合",
        "[I] 我想補充一句話",
        "[O] 輸出整理並結束",
    ),
    output_label="synthesis",
    final_state_label="Human Direction",
    conclusion_system=(
        "You are PromptStorm's terminal synthesis writer. The human user controls the discussion. "
        "Do not invent missing arguments. Produce a concise synthesis grounded only in the transcript."
    ),
    conclusion_instruction=(
        "Write a terminal synthesis that should synthesize shared ground, remaining differences, tradeoffs, "
        "and practical next steps. Keep it concise and readable in a terminal."
    ),
)


DIALOGUE = ModeProfile(
    name="dialogue",
    help_text="Run a scenario-based dialogue between two personas.",
    title="PromptStorm Dialogue",
    identity_label="Character",
    counterpart_label="Scene partner",
    default_persona_template="Character {speaker}",
    system_instruction=(
        "Create natural dialogue as this character. Stay in the scenario, speak in a voice that fits the persona, "
        "and respond to the other character like a real conversation. Write exactly one brief spoken reply for your "
        "character only. Do not write the other character's lines, do not continue the whole scene, and do not default "
        "to analysis, debate, narration, or summary unless the user asks for that."
    ),
    opening_instruction=(
        "Begin the scene with exactly one brief in-character line from your character only."
    ),
    continuation_instruction=(
        "Continue the scene with exactly one brief in-character reply from your character only. "
        "Let the relationship, tension, or decision develop one turn at a time."
    ),
    support_contexts={
        "A": "Let A take more initiative in the scene while keeping the interaction natural.\n",
        "B": "Let B take more initiative in the scene while keeping the interaction natural.\n",
        "TIE": "Keep the interaction balanced and natural.\n",
    },
    control_lines=(
        "[A] 讓 A 更主動，讓場景繼續 N 回合",
        "[B] 讓 B 更主動，讓場景繼續 N 回合",
        "[R] 保持自然互動，讓場景繼續 N 回合",
        "[I] 我想補充一句話",
        "[O] 輸出收尾並結束",
    ),
    output_label="wrap-up",
    final_state_label="Human Direction",
    conclusion_system=(
        "You are PromptStorm's terminal dialogue wrap-up writer. The human user controls the scene. "
        "Do not invent events. Produce a concise wrap-up grounded only in the transcript."
    ),
    conclusion_instruction=(
        "Write a terminal wrap-up that should briefly wrap up what happened in the dialogue, how the relationship or "
        "situation shifted, and any implied decision or unresolved tension. Do not name a winner."
    ),
)


MODES = {
    DEBATE.name: DEBATE,
    DISCUSSION.name: DISCUSSION,
    DIALOGUE.name: DIALOGUE,
}
SESSION_MODE_NAMES = tuple(MODES)


def get_mode_profile(mode: str) -> ModeProfile:
    try:
        return MODES[mode]
    except KeyError as exc:
        raise ValueError(f"Unknown PromptStorm mode: {mode}") from exc


def detect_output_language(*texts: str) -> str:
    joined = "\n".join(text.strip() for text in texts if text and text.strip())
    if _asks_for_english(joined):
        return "English"
    if _asks_for_chinese(joined):
        return "Traditional Chinese"

    cjk_count = sum(1 for char in joined if "\u4e00" <= char <= "\u9fff")
    latin_count = sum(len(match) for match in re.findall(r"[A-Za-z]+", joined))
    if cjk_count and cjk_count >= max(2, latin_count // 2):
        return "Traditional Chinese"
    if latin_count:
        return "English"
    return "Traditional Chinese" if cjk_count else "English"


def format_language_instruction(output_language: str) -> str:
    return (
        f"Output language: {output_language}.\n"
        "Persona names may use another language; do not switch languages unless the user requested it."
    )


def _asks_for_english(text: str) -> bool:
    lowered = text.lower()
    english_patterns = [
        r"\banswer\s+in\s+english\b",
        r"\brespond\s+in\s+english\b",
        r"\breply\s+in\s+english\b",
        r"\bwrite\s+in\s+english\b",
        r"\buse\s+english\b",
        r"\bin\s+english\b",
    ]
    return any(re.search(pattern, lowered) for pattern in english_patterns) or any(
        phrase in text for phrase in ("用英文", "英文回答", "請用英文")
    )


def _asks_for_chinese(text: str) -> bool:
    lowered = text.lower()
    chinese_patterns = [
        r"\banswer\s+in\s+chinese\b",
        r"\brespond\s+in\s+chinese\b",
        r"\breply\s+in\s+chinese\b",
        r"\bwrite\s+in\s+chinese\b",
        r"\buse\s+chinese\b",
    ]
    return any(re.search(pattern, lowered) for pattern in chinese_patterns) or any(
        phrase in text for phrase in ("用中文", "中文回答", "繁體中文", "請用中文")
    )
