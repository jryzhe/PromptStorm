# PromptStorm Session Modes Design

## Goal

PromptStorm should support three explicit terminal modes:

- `promptstorm debate`: adversarial A/B argument.
- `promptstorm discussion`: collaborative A/B analysis.
- `promptstorm dialogue`: scenario-based dialogue between two personas.

All three modes keep the existing terminal-first flow, model configuration, streaming output, transcript audit, human input loop, and terminal conclusion. The change is mainly about making mode-specific prompts and labels explicit instead of hard-coding debate behavior into the engine.

## User Experience

Each mode asks for the same basic inputs:

```text
Player A persona >
Player B persona >
Topic >
```

`persona` remains the right word for all modes. A and B can be people, roles, styles, or perspectives. The mode determines how those personas interact.

### Debate

`debate` treats A and B as opposing sides. They should challenge each other, respond to prior claims, and try to persuade the human user.

Control labels keep the current meaning:

```text
[A] I currently support A; continue the debate for N rounds
[B] I currently support B; continue the debate for N rounds
[R] I currently support neither side; continue the debate for N rounds
[I] Add my input
[O] Output conclusion and exit
```

The conclusion should summarize the strongest points on both sides and why the human verdict makes sense.

### Discussion

`discussion` treats A and B as two personas or perspectives working together. They may disagree when the topic or personas clearly call for it, but they should not default to attacking each other just because they are labeled A and B.

Discussion should only become adversarial when the user explicitly frames the topic that way, for example with wording such as "debate", "argue", "A supports / B opposes", "pro/con", "versus", "vs", "attack", "defend", or equivalent Chinese phrasing such as "辯論", "攻防", "正方/反方", "反駁".

Control labels should be collaborative:

```text
[A] A's perspective is currently more useful; analyze N more rounds
[B] B's perspective is currently more useful; analyze N more rounds
[R] No clear direction yet; analyze N more rounds
[I] Add my input
[O] Output synthesis and exit
```

The conclusion should synthesize shared ground, remaining differences, tradeoffs, and practical next steps.

### Dialogue

`dialogue` treats A and B as characters in a scenario. The output should read like natural back-and-forth conversation that fits the personas and situation. It should not default to analysis, debate, or summary unless the user asks for that.

Example topic:

```text
A is an anxious startup CEO. B is an old friend. They talk late at night in the office about whether to do layoffs.
```

Control labels should steer the scene without making it analytical:

```text
[A] Let A take more initiative for N rounds
[B] Let B take more initiative for N rounds
[R] Keep the interaction balanced for N rounds
[I] Add my input
[O] Output wrap-up and exit
```

The conclusion should briefly wrap up what happened in the dialogue, how the relationship or situation shifted, and any implied decision or unresolved tension. It should not name a winner.

## Shared Language Rule

All modes should answer in the user's output language.

Rules:

- If the topic and human input are mostly Traditional Chinese, model turns and conclusions should be in Traditional Chinese.
- If the topic and human input are mostly English, model turns and conclusions should be in English.
- If the input is mixed, use the dominant language of the topic and recent human input.
- Persona names or role labels may be in another language; they do not determine output language.
- If the user explicitly asks for a response language, that instruction wins.

Implementation should use a small deterministic language detector for the topic and human input, then pass an explicit prompt line such as:

```text
Output language: Traditional Chinese.
Persona names may use another language; do not switch languages unless the user requested it.
```

The same output language must be passed to both turn generation and terminal conclusion generation.

## Architecture

Introduce a small `ModeProfile` concept rather than adding scattered conditionals.

Each profile should provide:

- command name: `debate`, `discussion`, or `dialogue`
- parser help text
- default persona labels
- turn prompt instructions
- continuation prompt instructions for A/B/R choices
- control menu labels
- conclusion prompt instructions
- neutral label for the saved final state

The existing engine can remain mostly intact. It should receive a mode profile or mode name and call prompt-building helpers that use the selected profile. The provider remains unchanged.

`ConclusionWriter` should also receive the selected mode or profile so it can write a conclusion prompt that matches the session type.

## Data Model

Keep the current audit schema for the first implementation. The existing `winner` field can continue to store the final human preference:

- debate: actual supported side or tie
- discussion: currently more useful perspective or no clear direction
- dialogue: currently more active character or balanced

Renaming this field to something like `outcome` would be cleaner, but it can be a later cleanup because changing audit columns increases the blast radius.

## Testing

Tests should cover:

- `build_parser()` exposes `debate`, `discussion`, and `dialogue`.
- `discussion` prompts do not contain default adversarial language.
- `dialogue` prompts ask for natural character conversation, not analysis or debate.
- `debate` preserves existing adversarial prompt behavior.
- language detection selects Traditional Chinese for Chinese topics even when personas are English names.
- `ConclusionWriter` uses mode-specific conclusion instructions.
- existing debate tests remain green.

## Non-Goals

- No automatic mode selection. The user chooses the command explicitly.
- No GUI or browser UI.
- No schema migration for existing audit files in this pass.
- No new provider or model configuration.
