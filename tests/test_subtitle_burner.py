import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.subtitle_burner import (
    SubtitleBurnError,
    burn_subtitles,
)

class TestBurnSubtitles(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.root = Path(self.temp_directory.name)
        self.video = self.root / "sample.mp4"
        self.subtitle = self.root / "sample.srt"
        self.output_dir = self.root / "output"

        self.video.write_bytes(b"fake video")
        self.subtitle.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello!\n",
            encoding="utf-8",
        )

    @patch("core.subtitle_burner.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_reported(self, mock_which):
        with self.assertRaisesRegex(
            SubtitleBurnError,
            "FFmpeg was not found",
        ):
            burn_subtitles(
                self.video,
                self.subtitle,
                self.output_dir,
            )

    def test_missing_video_is_rejected(self):
        with self.assertRaisesRegex(
            SubtitleBurnError,
            "Video file not found",
        ):
            burn_subtitles(
                self.root / "missing.mp4",
                self.subtitle,
                self.output_dir,
            )

    def test_missing_subtitle_is_rejected(self):
        with self.assertRaisesRegex(
            SubtitleBurnError,
            "Subtitle file not found",
        ):
            burn_subtitles(
                self.video,
                self.root / "missing.srt",
                self.output_dir,
            )

    def test_non_srt_subtitle_is_rejected(self):
        wrong_subtitle = self.root / "sample.txt"
        wrong_subtitle.write_text(
            "Hello",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            SubtitleBurnError,
            r"\.srt",
        ):
            burn_subtitles(
                self.video,
                wrong_subtitle,
                self.output_dir,
            )

    @patch("core.subtitle_burner.shutil.which", return_value="ffmpeg")
    @patch("core.subtitle_burner.subprocess.run")
    def test_successful_burn_returns_output_path(
        self,
        mock_run,
        mock_which,
    ):
        def fake_ffmpeg(*args, **kwargs):
            command = args[0]
            output_path = Path(command[-1])
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            output_path.write_bytes(b"processed video")

            return Mock(returncode=0, stderr="")

        mock_run.side_effect = fake_ffmpeg

        result = burn_subtitles(
            self.video,
            self.subtitle,
            self.output_dir,
        )

        output_path = self.output_dir / "sample_subtitled.mp4"

        self.assertTrue(output_path.is_file())
        self.assertEqual(
            result["path"],
            str(output_path.resolve()),
        )
        self.assertEqual(
            result["size_bytes"],
            len(b"processed video"),
        )
        self.assertFalse(result["skipped"])

        command = mock_run.call_args.args[0]

        self.assertIn("libx264", command)
        self.assertIn(
            "subtitles=filename=",
            command[command.index("-vf") + 1],
        )
        self.assertEqual(
            self.video.read_bytes(),
            b"fake video",
        )

    @patch("core.subtitle_burner.shutil.which", return_value="ffmpeg")
    def test_existing_output_is_not_overwritten(self, mock_which):
        self.output_dir.mkdir()

        existing_output = self.output_dir / "sample_subtitled.mp4"
        existing_output.write_bytes(b"keep me")

        with self.assertRaisesRegex(
            SubtitleBurnError,
            "already exists",
        ):
            burn_subtitles(
                self.video,
                self.subtitle,
                self.output_dir,
            )

        self.assertEqual(
            existing_output.read_bytes(),
            b"keep me",
        )

    def test_invalid_crf_is_rejected(self):
        with self.assertRaisesRegex(
            SubtitleBurnError,
            "CRF",
        ):
            burn_subtitles(
                self.video,
                self.subtitle,
                self.output_dir,
                crf=100,
            )

    def test_invalid_preset_is_rejected(self):
        with self.assertRaisesRegex(
            SubtitleBurnError,
            "preset",
        ):
            burn_subtitles(
                self.video,
                self.subtitle,
                self.output_dir,
                preset="invalid",
            )

if __name__ == "__main__":
    unittest.main()