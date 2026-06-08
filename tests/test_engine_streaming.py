from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptstorm.engine import DebateEngine
from promptstorm.models import ModelResponse, PromptStormConfig


class ChunkingProvider:
    def complete(self, model: str, messages: Sequence[dict[str, str]]) -> ModelResponse:
        return ModelResponse(text="hello")

    def stream_complete(self, model, messages, on_delta=None):
        if on_delta:
            on_delta("hel")
            on_delta("lo")
        return ModelResponse(text="hello")


class DebateEngineStreamingTests(unittest.TestCase):
    def test_model_turns_emit_response_chunks_before_storing_cleaned_turn(self):
        config = PromptStormConfig(
            api_key="test-key",
            player_a_model="model-a",
            player_b_model="model-b",
            report_model="report-model",
        )
        engine = DebateEngine(provider=ChunkingProvider(), rounds=1)
        emitted: list[tuple[str, str]] = []

        session = engine.run(
            topic="Should tools stream output?",
            player_a_persona="",
            player_b_persona="",
            config=config,
            on_response=lambda speaker, text: emitted.append((speaker, text)),
        )

        self.assertEqual(
            emitted,
            [
                ("A", "hel"),
                ("A", "lo"),
                ("B", "hel"),
                ("B", "lo"),
            ],
        )
        self.assertEqual([turn.response_text for turn in session.turns], ["hello", "hello"])


if __name__ == "__main__":
    unittest.main()
