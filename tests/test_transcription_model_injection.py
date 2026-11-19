import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.transcription import transcribe_to_srt


class TestInjectedModel(unittest.TestCase):
    @patch("core.transcription.inspect_video", return_value={"duration_seconds": 10.0})
    @patch("core.transcription.WhisperModel")
    def test_supplied_model_is_used_without_loading_a_new_one(self, whisper_cls, inspect):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "talk.mp4"
            video.write_bytes(b"x")
            out = Path(temp) / "subs"

            model = Mock()
            model.transcribe.return_value = (
                [SimpleNamespace(start=0.0, end=2.0, text=" Hello there. ")],
                SimpleNamespace(language="en"),
            )

            result = transcribe_to_srt(video, out, model=model, skip_existing=False)

            whisper_cls.assert_not_called()
            model.transcribe.assert_called_once()
            self.assertEqual(result["segments"], 1)
            srt = (out / "talk.srt").read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:02,000", srt)
            self.assertIn("Hello there.", srt)


if __name__ == "__main__":
    unittest.main()
