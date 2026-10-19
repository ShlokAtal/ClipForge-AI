import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.transcription import (
    format_srt_timestamp,
    transcribe_to_srt,
)


class TestSrtTimestamp(unittest.TestCase):

    def test_formats_timestamp(self):
        self.assertEqual(
            format_srt_timestamp(65.125),
            "00:01:05,125",
        )

    def test_formats_hours(self):
        self.assertEqual(
            format_srt_timestamp(3661.5),
            "01:01:01,500",
        )

    def test_clamps_negative_time(self):
        self.assertEqual(
            format_srt_timestamp(-2),
            "00:00:00,000",
        )

class TestTranscription(unittest.TestCase):

    @patch("core.transcription.inspect_video")
    @patch("core.transcription.WhisperModel")
    def test_generates_srt_file(self, mock_model_class, mock_inspect):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "sample.mp4"
            output_dir = root / "subtitles"
            video.touch()

            mock_inspect.return_value = {
                "duration_seconds": 20.0,
                "path": str(video),
                "name": video.name,
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 1080,
                "height": 1920,
            }

            fake_segments = [
                SimpleNamespace(
                    start=0.0,
                    end=2.4,
                    text=" Hello there. ",
                ),
                SimpleNamespace(
                    start=2.5,
                    end=4.0,
                    text="Welcome back!",
                ),
            ]

            mock_model = mock_model_class.return_value
            mock_model.transcribe.return_value = (
                iter(fake_segments),
                SimpleNamespace(language="en"),
            )

            result = transcribe_to_srt(
                video,
                output_dir,
                model_name="tiny",
                device="cpu",
                compute_type="int8",
            )

            subtitle_file = output_dir / "sample.srt"
            content = subtitle_file.read_text(encoding="utf-8")

            self.assertTrue(subtitle_file.is_file())
            self.assertEqual(result["segments"], 2)
            self.assertEqual(result["language"], "en")
            self.assertFalse(result["skipped"])
            self.assertIn(
                "00:00:00,000 --> 00:00:02,400",
                content,
            )
            self.assertIn(
                "00:00:02,500 --> 00:00:04,000",
                content,
            )
            self.assertIn("Hello there.", content)
            self.assertIn("Welcome back!", content)

            mock_inspect.assert_called_once_with(video)
            mock_model_class.assert_called_once_with(
                "tiny",
                device="cpu",
                compute_type="int8",
            )

    @patch("core.transcription.inspect_video")
    @patch("core.transcription.WhisperModel")
    def test_clamps_segment_to_video_duration(
        self,
        mock_model_class,
        mock_inspect,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "sample.mp4"
            output_dir = root / "subtitles"
            video.touch()

            mock_inspect.return_value = {
                "duration_seconds": 3.0,
                "path": str(video),
                "name": video.name,
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 1080,
                "height": 1920,
            }

            fake_segments = [
                SimpleNamespace(
                    start=2.0,
                    end=4.5,
                    text="Ending sentence.",
                ),
            ]

            mock_model = mock_model_class.return_value
            mock_model.transcribe.return_value = (
                iter(fake_segments),
                SimpleNamespace(language="en"),
            )

            result = transcribe_to_srt(
                video,
                output_dir,
                model_name="tiny",
                device="cpu",
                compute_type="int8",
            )

            content = (
                output_dir / "sample.srt"
            ).read_text(encoding="utf-8")

            self.assertEqual(result["segments"], 1)
            self.assertIn(
                "00:00:02,000 --> 00:00:03,000",
                content,
            )
            self.assertIn("Ending sentence.", content)

    @patch("core.transcription.WhisperModel")
    def test_existing_srt_is_skipped(self, mock_model_class):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "sample.mp4"
            output_dir = root / "subtitles"
            output_dir.mkdir()
            video.touch()

            existing = output_dir / "sample.srt"
            existing.write_text(
                "Existing subtitles",
                encoding="utf-8",
            )

            result = transcribe_to_srt(
                video,
                output_dir,
                skip_existing=True,
            )

            self.assertTrue(result["skipped"])
            self.assertEqual(
                existing.read_text(encoding="utf-8"),
                "Existing subtitles",
            )
            mock_model_class.assert_not_called()

    def test_missing_video_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.mp4"

            with self.assertRaisesRegex(ValueError, "not found"):
                transcribe_to_srt(missing, directory)

if __name__ == "__main__":
    unittest.main()