import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from core.video_input import (
    VideoInputError,
    discover_videos,
    inspect_video,
)

class TestDiscoverVideos(unittest.TestCase):

    def test_finds_supported_video_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "sample.mp4").touch()
            (folder / "sample.MKV").touch()
            (folder / "notes.txt").touch()

            videos = discover_videos(folder)

            self.assertEqual(
                {path.name for path in videos},
                {"sample.mp4", "sample.MKV"},
            )

    def test_missing_input_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"

            with self.assertRaises(VideoInputError):
                discover_videos(missing)


class TestInspectVideo(unittest.TestCase):

    def test_missing_video_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.mp4"

            with self.assertRaisesRegex(
                VideoInputError, "does not exist"
            ):
                inspect_video(missing)

    def test_unsupported_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "notes.txt"
            file_path.touch()

            with self.assertRaisesRegex(
                VideoInputError, "Unsupported"
            ):
                inspect_video(file_path)

    @patch("core.video_input.shutil.which", return_value=None)
    def test_missing_ffprobe_is_reported(self, mock_which):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "sample.mp4"
            file_path.touch()

            with self.assertRaisesRegex(
                VideoInputError, "ffprobe was not found"
            ):
                inspect_video(file_path)

    @patch("core.video_input.shutil.which", return_value="ffprobe")
    @patch("core.video_input.subprocess.run")
    def test_valid_video_metadata_is_returned(
        self, mock_run, mock_which
    ):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "sample.mp4"
            file_path.touch()

            payload = {
                "format": {"duration": "12.5"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                    },
                ],
            }

            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

            metadata = inspect_video(file_path)

            self.assertEqual(metadata["name"], "sample.mp4")
            self.assertEqual(metadata["duration_seconds"], 12.5)
            self.assertEqual(metadata["video_codec"], "h264")
            self.assertEqual(metadata["audio_codec"], "aac")
            self.assertEqual(metadata["width"], 1920)
            self.assertEqual(metadata["height"], 1080)

    @patch("core.video_input.shutil.which", return_value="ffprobe")
    @patch("core.video_input.subprocess.run")
    def test_video_without_audio_is_rejected(
        self, mock_run, mock_which
    ):
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "silent.mp4"
            file_path.touch()

            payload = {
                "format": {"duration": "10"},
                "streams": [
                    {"codec_type": "video", "codec_name": "h264"}
                ],
            }

            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

            with self.assertRaisesRegex(
                VideoInputError, "no audio track"
            ):
                inspect_video(file_path)

if __name__ == "__main__":
    unittest.main()