import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from features.clip_finder.engine import (
    ClipFinderError,
    export_clip,
    find_highlights,
    parse_srt,
)


SRT = """1
00:00:00,000 --> 00:00:04,000
Today I will show you an amazing trick!

2
00:00:04,500 --> 00:00:09,000
This is the secret that changed everything.

3
00:00:10,000 --> 00:00:15,000
Why does this work? Let me explain the solution.

4
00:00:16,000 --> 00:00:20,000
And that is the most important result!
"""


class TestClipFinder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.srt = self.root / "sample.srt"
        self.srt.write_text(SRT, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_parse_srt_segments(self):
        segments = parse_srt(self.srt)
        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[0].start, 0)
        self.assertIn("amazing trick", segments[0].text)

    def test_missing_srt_is_rejected(self):
        with self.assertRaisesRegex(ClipFinderError, "not found"):
            parse_srt(self.root / "missing.srt")

    def test_finds_ranked_candidates_with_reasons(self):
        candidates = find_highlights(
            self.srt, video_duration=25, min_duration=8,
            max_duration=18, max_candidates=5, padding_seconds=0.5,
        )
        self.assertTrue(candidates)
        self.assertTrue(all(c.start < c.end for c in candidates))
        self.assertTrue(all(c.reasons for c in candidates))
        self.assertTrue(all(c.duration <= 18 for c in candidates))

    def test_invalid_duration_range_rejected(self):
        with self.assertRaisesRegex(ClipFinderError, "duration range"):
            find_highlights(self.srt, min_duration=20, max_duration=10)

    def test_export_rejects_missing_video(self):
        with self.assertRaisesRegex(ClipFinderError, "not found"):
            export_clip(self.root / "missing.mp4", self.root / "out", 0, 5)

    def test_export_rejects_invalid_boundaries(self):
        video = self.root / "sample.mp4"
        video.touch()
        with self.assertRaisesRegex(ClipFinderError, "boundaries"):
            export_clip(video, self.root / "out", 5, 4)

    @patch("features.clip_finder.engine.shutil.which", return_value="ffmpeg")
    @patch("features.clip_finder.engine.subprocess.run")
    def test_export_creates_output_safely(self, run, which):
        video = self.root / "sample.mp4"
        video.touch()

        def fake_run(command, **kwargs):
            Path(command[-1]).write_bytes(b"fake video")
            return Mock(returncode=0, stderr="")
        run.side_effect = fake_run

        output = export_clip(video, self.root / "out", 2, 8, output_name="highlight_01")
        self.assertTrue(output.is_file())
        self.assertEqual(output.name, "highlight_01.mp4")
        self.assertNotEqual(output, video)


    @patch("features.clip_finder.engine.build_smart_crop_filter", return_value="scale=1080:1920")
    @patch("features.clip_finder.engine.shutil.which", return_value="ffmpeg")
    @patch("features.clip_finder.engine.subprocess.run")
    def test_smart_reframe_filter_is_used_when_requested(self, run, which, build_filter):
        video = self.root / "sample.mp4"
        video.touch()

        def fake_run(command, **kwargs):
            Path(command[-1]).write_bytes(b"fake video")
            return Mock(returncode=0, stderr="")

        run.side_effect = fake_run
        output = export_clip(
            video,
            self.root / "out",
            2,
            8,
            output_name="smart_highlight",
            output_format="shorts",
            reframe_mode="auto",
        )

        self.assertTrue(output.is_file())
        build_filter.assert_called_once_with(
            video.resolve(), 2, 6, "shorts", mode="auto"
        )
        command = run.call_args.args[0]
        self.assertIn("scale=1080:1920", command)

    @patch("features.clip_finder.engine.shutil.which", return_value="ffmpeg")
    @patch("features.clip_finder.engine.subprocess.run")
    def test_export_does_not_overwrite_existing_clip(self, run, which):
        video = self.root / "sample.mp4"
        video.touch()
        output_dir = self.root / "out"
        output_dir.mkdir()
        existing = output_dir / "sample_clip.mp4"
        existing.write_bytes(b"preserve")
        with self.assertRaisesRegex(ClipFinderError, "refusing to overwrite"):
            export_clip(video, output_dir, 2, 8)
        self.assertEqual(existing.read_bytes(), b"preserve")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
