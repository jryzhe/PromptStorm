from __future__ import annotations

import sys
import unittest
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptstorm.models import DebateSession, DebateTurn, ModelResponse


class NoTokenAccountingTests(unittest.TestCase):
    def test_session_models_do_not_store_token_counts(self):
        for model in (ModelResponse, DebateTurn, DebateSession):
            field_names = {field.name for field in fields(model)}
            self.assertNotIn("tokens_used", field_names)


if __name__ == "__main__":
    unittest.main()
