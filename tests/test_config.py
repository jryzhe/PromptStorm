import tempfile
import unittest
from pathlib import Path

from promptstorm.config import (
    DEFAULT_PLAYER_A_MODEL,
    DEFAULT_PLAYER_B_MODEL,
    DEFAULT_REPORT_MODEL,
    load_config,
    save_api_key,
)


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_env_file_and_uses_model_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("AI_GATEWAY_API_KEY=secret-key\n", encoding="utf-8")

            config = load_config(env_path)

            self.assertEqual(config.api_key, "secret-key")
            self.assertEqual(config.player_a_model, DEFAULT_PLAYER_A_MODEL)
            self.assertEqual(config.player_b_model, DEFAULT_PLAYER_B_MODEL)
            self.assertEqual(config.report_model, DEFAULT_REPORT_MODEL)

    def test_save_api_key_preserves_existing_model_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "PLAYER_A_MODEL=google/custom-a\n"
                "PLAYER_B_MODEL=anthropic/custom-b\n"
                "REPORT_MODEL=anthropic/custom-report\n",
                encoding="utf-8",
            )

            save_api_key(env_path, "new-key")
            config = load_config(env_path)

            self.assertEqual(config.api_key, "new-key")
            self.assertEqual(config.player_a_model, "google/custom-a")
            self.assertEqual(config.player_b_model, "anthropic/custom-b")
            self.assertEqual(config.report_model, "anthropic/custom-report")


if __name__ == "__main__":
    unittest.main()
