import unittest

from promptstorm.modes import detect_output_language, get_mode_profile


class ModeProfileTests(unittest.TestCase):
    def test_get_mode_profile_returns_discussion_and_dialogue_profiles(self):
        discussion = get_mode_profile("discussion")
        dialogue = get_mode_profile("dialogue")

        self.assertEqual(discussion.name, "discussion")
        self.assertIn("collaborative", discussion.help_text)
        self.assertEqual(dialogue.name, "dialogue")
        self.assertIn("scenario", dialogue.help_text)

    def test_detect_output_language_uses_chinese_topic_over_english_personas(self):
        language = detect_output_language(
            "Steve Jobs",
            "Elon Musk",
            "兩個創業者討論是否應該裁員，最後要收斂出一個決定。",
        )

        self.assertEqual(language, "Traditional Chinese")

    def test_detect_output_language_respects_explicit_english_request(self):
        language = detect_output_language("請用英文回答：兩個人討論是否要裁員。")

        self.assertEqual(language, "English")


if __name__ == "__main__":
    unittest.main()
