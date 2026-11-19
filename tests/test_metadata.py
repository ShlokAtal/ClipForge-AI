import json
import tempfile
import unittest
from pathlib import Path

from features.clip_finder.metadata import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    build_metadata,
    suggest_hashtags,
    suggest_title,
    write_metadata_file,
)


class TestMetadataSuggestions(unittest.TestCase):
    def test_title_uses_first_sentence_without_trailing_period(self):
        title = suggest_title("This one trick changed everything. Then more follows.")
        self.assertEqual(title, "This one trick changed everything")

    def test_long_title_is_trimmed_at_word_boundary(self):
        long_text = "word " * 40
        title = suggest_title(long_text)
        self.assertLessEqual(len(title), MAX_TITLE_LENGTH)
        self.assertTrue(title.endswith("…"))
        self.assertNotIn("  ", title)

    def test_empty_transcript_gets_fallback_title(self):
        self.assertEqual(suggest_title("   "), "Highlight")

    def test_hashtags_skip_stopwords_and_short_words(self):
        tags = suggest_hashtags(
            "The python debugger saves the python project and the debugger "
            "makes python easier to learn."
        )
        self.assertIn("#python", tags)
        self.assertIn("#debugger", tags)
        self.assertNotIn("#the", tags)
        self.assertNotIn("#and", tags)

    def test_hashtags_are_ranked_by_frequency_then_first_appearance(self):
        tags = suggest_hashtags("alpha beta alpha gamma beta alpha", max_tags=3)
        self.assertEqual(tags[0], "#alpha")

    def test_hashtags_never_contain_apostrophes_or_punctuation(self):
        tags = suggest_hashtags("You're going to love it. It's the best trick we've seen.")
        for tag in tags:
            self.assertRegex(tag, r"^#[A-Za-z]+$")

    def test_shorts_tag_is_appended_when_requested(self):
        tags = suggest_hashtags("coffee brewing secrets revealed", include_shorts=True)
        self.assertEqual(tags[-1], "#Shorts")

    def test_build_metadata_returns_all_fields_within_limits(self):
        result = build_metadata("Coffee brewing has one secret most people miss. " * 6)
        self.assertEqual(set(result), {"title", "description", "hashtags"})
        self.assertLessEqual(len(result["title"]), MAX_TITLE_LENGTH)
        self.assertLessEqual(len(result["description"].split("\n\n")[0]), MAX_DESCRIPTION_LENGTH)
        self.assertTrue(all(tag.startswith("#") for tag in result["hashtags"]))

    def test_write_metadata_file_is_utf8_json_with_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "clip.json"
            write_metadata_file(path, {"title": "Café ☕ tips"})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["title"], "Café ☕ tips")
            self.assertIn("created_at", data)


if __name__ == "__main__":
    unittest.main()
