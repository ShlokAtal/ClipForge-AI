import unittest

from features.smart_reframe import (
    SmartReframeError,
    _crop_geometry,
    _interpolated_expression,
)


class TestSmartReframeHelpers(unittest.TestCase):
    def test_vertical_crop_geometry_for_landscape_source(self):
        width, height = _crop_geometry(1920, 1080, "shorts")
        self.assertEqual(height, 1080)
        self.assertLessEqual(width / height, 9 / 16)
        self.assertEqual(width % 2, 0)

    def test_landscape_crop_geometry_for_portrait_source(self):
        width, height = _crop_geometry(1080, 1920, "youtube")
        self.assertEqual(width, 1080)
        self.assertLessEqual(width / height, 16 / 9)
        self.assertEqual(height % 2, 0)

    def test_matching_aspect_ratio_preserves_full_frame_geometry(self):
        self.assertEqual(_crop_geometry(1080, 1920, "shorts"), (1080, 1920))

    def test_interpolated_expression_contains_time_based_segments(self):
        expression = _interpolated_expression([(0.0, 0.0), (1.0, 10.0), (2.0, 20.0)])
        self.assertIn("if(lt(t,1.000)", expression)
        self.assertIn("if(lt(t,2.000)", expression)
        self.assertIn("20.000", expression.split(",")[-1])

    def test_invalid_output_format_is_rejected(self):
        with self.assertRaisesRegex(SmartReframeError, "supports Shorts"):
            _crop_geometry(1920, 1080, "original")


if __name__ == "__main__":
    unittest.main()
