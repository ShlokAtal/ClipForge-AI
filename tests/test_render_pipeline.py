import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from features.clip_finder.engine import ClipFinderError, export_clip
from features.clip_finder.pipeline import ClipRenderError, ClipRequest, render_clip, safe_clip_name
from features.smart_reframe import _effective_sample_interval, MAX_KEYFRAMES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_VIDEO = PROJECT_ROOT / "media" / "input" / "test_demo.mp4"
SAMPLE_SRT = PROJECT_ROOT / "output" / "subtitles" / "test_demo.srt"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
HAS_SAMPLE = SAMPLE_VIDEO.is_file() and SAMPLE_SRT.is_file()


class TestSafeClipName(unittest.TestCase):
    def test_unsafe_characters_are_replaced(self):
        self.assertEqual(safe_clip_name("My Video: part #1!"), "My_Video_part_1")

    def test_empty_name_falls_back(self):
        self.assertEqual(safe_clip_name("!!!"), "clip")


class TestSmartReframeSampling(unittest.TestCase):
    def test_short_clip_keeps_requested_interval(self):
        self.assertEqual(_effective_sample_interval(30, 1.0), 1.0)

    def test_long_clip_is_capped_to_max_keyframes(self):
        interval = _effective_sample_interval(600, 1.0)
        self.assertLessEqual(600 / interval, MAX_KEYFRAMES + 1e-9)


class TestExportOverwrite(unittest.TestCase):
    @patch("features.clip_finder.engine.shutil.which", return_value="ffmpeg")
    @patch("features.clip_finder.engine.subprocess.run")
    def test_existing_output_is_refused_by_default(self, run, which):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.mp4"
            source.write_bytes(b"not really a video")
            out = Path(temp) / "out"
            out.mkdir()
            (out / "clip.mp4").write_bytes(b"old")

            with self.assertRaisesRegex(ClipFinderError, "refusing to overwrite"):
                export_clip(source, out, 0, 5, output_name="clip")

            run.assert_not_called()


@unittest.skipUnless(HAS_FFMPEG and HAS_SAMPLE, "requires FFmpeg and the sample media")
class TestRenderClipEndToEnd(unittest.TestCase):
    """Real FFmpeg renders against the bundled sample video."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / "clips"

    def tearDown(self):
        self.temp.cleanup()

    def _request(self, **overrides):
        base = dict(
            video_path=SAMPLE_VIDEO,
            subtitle_path=SAMPLE_SRT,
            start_seconds=2.0,
            end_seconds=8.0,
            name="demo_clip",
            output_format="youtube",
            reframe_mode="auto",
            preset="ultrafast",
            crf=28,
        )
        base.update(overrides)
        return ClipRequest(**base)

    def test_render_with_captions_produces_landscape_mp4(self):
        final = render_clip(self._request(), self.out)
        self.assertTrue(final.is_file())
        self.assertEqual(final.name, "demo_clip.mp4")
        self.assertGreater(final.stat().st_size, 0)

    def test_re_export_replaces_clip_instead_of_failing(self):
        """Regression: re-exporting the same clip used to raise 'already exists'."""
        render_clip(self._request(), self.out)
        final = render_clip(self._request(caption_style={
            "font_name": "Arial", "font_size": 40, "font_color": "#FFFF00",
            "outline_color": "#000000", "outline_thickness": 2,
            "background_mode": "Transparent", "background_color": "#000000",
            "alignment": "Bottom Center", "vertical_margin": 40, "bold": True,
        }), self.out)
        self.assertTrue(final.is_file())

    def test_no_intermediate_files_are_left_behind(self):
        render_clip(self._request(), self.out)
        leftovers = [p.name for p in self.out.iterdir() if p.name.startswith(".work_")]
        self.assertEqual(leftovers, [])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["demo_clip.mp4"])

    def test_render_without_captions_skips_burn_step(self):
        final = render_clip(self._request(burn_captions=False, reframe_mode=None), self.out)
        self.assertTrue(final.is_file())

    def test_invalid_range_raises_render_error(self):
        with self.assertRaises(ClipRenderError):
            render_clip(self._request(start_seconds=5.0, end_seconds=5.0), self.out)


if __name__ == "__main__":
    unittest.main()
