"""CPU-friendly subject-aware crop planning for ClipForge AI.

This first version uses OpenCV's built-in Haar face detector and HOG people
 detector. It tracks the most plausible visible subject between sampled frames
and creates a smooth, time-varying FFmpeg crop expression. It does not claim to
identify the active speaker or semantically recognize an action.
"""

from __future__ import annotations

import math
from pathlib import Path


class SmartReframeError(RuntimeError):
    """Raised when subject-aware crop planning cannot be completed."""


REFRAME_MODES = {"auto", "face", "person"}

# Upper bound on tracked keyframes. Each keyframe adds one nested if() term to
# the FFmpeg crop expression, so long clips are sampled more sparsely.
MAX_KEYFRAMES = 80
OUTPUT_RATIOS = {
    "shorts": 9 / 16,
    "youtube": 16 / 9,
}


def _even_floor(value: float) -> int:
    """Return a positive even integer no larger than the supplied value."""
    result = int(math.floor(value))
    result -= result % 2
    return max(2, result)


def _even_ceil(value: float) -> int:
    """Return a positive even integer no smaller than the supplied value."""
    result = int(math.ceil(value))
    if result % 2:
        result += 1
    return max(2, result)


def _crop_geometry(width: int, height: int, output_format: str) -> tuple[int, int]:
    if output_format not in OUTPUT_RATIOS:
        raise SmartReframeError(
            "Smart reframing supports Shorts and landscape output only."
        )

    target_ratio = OUTPUT_RATIOS[output_format]
    source_ratio = width / height
    if source_ratio > target_ratio:
        crop_width = _even_floor(height * target_ratio)
        crop_height = _even_floor(height)
    else:
        crop_width = _even_floor(width)
        crop_height = _even_ceil(width / target_ratio)

    if crop_width > width:
        crop_width = _even_floor(width)
    if crop_height > height:
        crop_height = _even_floor(height)
    return crop_width, crop_height


def _select_detection(detections, previous_center, frame_width, frame_height):
    """Choose a stable target, preferring continuity after the first sample."""
    if not detections:
        return None

    if previous_center is None:
        # The largest detection is a reasonable initial subject guess.
        x, y, width, height = max(detections, key=lambda box: box[2] * box[3])
    else:
        diagonal = max(1.0, math.hypot(frame_width, frame_height))

        def continuity_score(box):
            x, y, width, height = box
            center = (x + width / 2, y + height / 2)
            distance = math.hypot(
                center[0] - previous_center[0],
                center[1] - previous_center[1],
            ) / diagonal
            area_bonus = min(0.15, (width * height) / max(1, frame_width * frame_height))
            return distance - area_bonus

        x, y, width, height = min(detections, key=continuity_score)

    return (x + width / 2, y + height / 2)


def _effective_sample_interval(duration_seconds: float, requested: float) -> float:
    """Return the sampling interval, widened for long clips to cap keyframes."""
    return max(requested, duration_seconds / MAX_KEYFRAMES)


def _interpolated_expression(points: list[tuple[float, float]]) -> str:
    """Build a bounded, piecewise-linear FFmpeg expression from samples."""
    if not points:
        return "0"
    if len(points) == 1:
        return f"{points[0][1]:.3f}"

    expression = f"{points[-1][1]:.3f}"
    for index in range(len(points) - 2, -1, -1):
        t0, value0 = points[index]
        t1, value1 = points[index + 1]
        if t1 <= t0:
            continue
        interpolated = (
            f"({value0:.3f}+({value1 - value0:.3f})*"
            f"(t-{t0:.3f})/{t1 - t0:.3f})"
        )
        expression = f"if(lt(t,{t1:.3f}),{interpolated},{expression})"
    return expression


def build_smart_crop_filter(
    video_path: str | Path,
    start_seconds: float,
    duration_seconds: float,
    output_format: str,
    mode: str = "auto",
    *,
    sample_interval: float = 1.0,
) -> str:
    """Analyze a clip and return a dynamic FFmpeg crop-and-scale filter.

    ``auto`` prefers detected faces and falls back to full-body people;
    ``face`` tracks faces; ``person`` tracks full-body people. If no subject is
    detected, the crop remains centered. The output is still rendered by
    FFmpeg, preserving the existing export/audio/subtitle workflow.
    """
    if mode not in REFRAME_MODES:
        raise SmartReframeError(
            f"Unsupported smart-reframe mode: {mode!r}. "
            f"Choose one of: {', '.join(sorted(REFRAME_MODES))}."
        )
    if start_seconds < 0 or duration_seconds <= 0:
        raise SmartReframeError("Invalid clip range for smart reframing.")
    if sample_interval < 0.25 or sample_interval > 5:
        raise SmartReframeError("Sample interval must be between 0.25 and 5 seconds.")
    sample_interval = _effective_sample_interval(duration_seconds, sample_interval)

    try:
        import cv2
    except ImportError as error:
        raise SmartReframeError(
            "Smart reframing requires OpenCV. Install project dependencies with "
            "'python -m pip install -r requirements.txt'."
        ) from error

    path = Path(video_path).resolve()
    if not path.is_file():
        raise SmartReframeError(f"Video file not found: {path}")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise SmartReframeError(f"OpenCV could not open this video: {path.name}")

    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width < 2 or height < 2:
            raise SmartReframeError("Could not read video dimensions for reframing.")

        crop_width, crop_height = _crop_geometry(width, height, output_format)
        max_x = max(0, width - crop_width)
        max_y = max(0, height - crop_height)
        center_x = width / 2
        center_y = height / 2

        face_detector = None
        person_detector = None
        if mode in {"auto", "face"}:
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            face_detector = cv2.CascadeClassifier(str(cascade_path))
            if face_detector.empty():
                face_detector = None
                if mode == "face":
                    raise SmartReframeError(
                        "OpenCV's face detector model is missing. Reinstall "
                        "project dependencies or choose Person focus."
                    )

        if mode in {"auto", "person"}:
            person_detector = cv2.HOGDescriptor()
            person_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        times = []
        cursor = 0.0
        while cursor < duration_seconds:
            times.append(round(cursor, 3))
            cursor += sample_interval
        if not times:
            times = [0.0]

        # A maximum dimension of 640 keeps CPU work manageable on Windows.
        scale = min(1.0, 640 / max(width, height))
        analysis_width = max(1, int(width * scale))
        analysis_height = max(1, int(height * scale))

        raw_centers = []
        previous_center = None
        for relative_time in times:
            capture.set(
                cv2.CAP_PROP_POS_MSEC,
                (start_seconds + relative_time) * 1000,
            )
            ok, frame = capture.read()
            detections = []

            if ok:
                if scale != 1.0:
                    frame = cv2.resize(frame, (analysis_width, analysis_height))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                face_boxes = []
                if face_detector is not None:
                    face_boxes = face_detector.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(max(24, int(24 * scale)), max(24, int(24 * scale))),
                    )
                    face_boxes = [
                        (int(x), int(y), int(w), int(h))
                        for x, y, w, h in face_boxes
                    ]

                if mode == "face":
                    detections = face_boxes
                elif mode == "auto" and face_boxes:
                    detections = face_boxes
                elif person_detector is not None:
                    person_boxes, _weights = person_detector.detectMultiScale(
                        frame,
                        winStride=(8, 8),
                        padding=(8, 8),
                        scale=1.05,
                    )
                    detections = [
                        (int(x), int(y), int(w), int(h))
                        for x, y, w, h in person_boxes
                    ]

                # Convert detections from the analysis frame to source pixels.
                detections = [
                    (
                        int(x / scale),
                        int(y / scale),
                        max(1, int(w / scale)),
                        max(1, int(h / scale)),
                    )
                    for x, y, w, h in detections
                ]
                detected_center = _select_detection(
                    detections, previous_center, width, height
                )
                if detected_center is not None:
                    previous_center = detected_center

            # Keep the last target through short detection gaps; start centered
            # when no face/person has been found yet.
            target_x, target_y = previous_center or (center_x, center_y)
            raw_centers.append((relative_time, target_x, target_y))

        # Smooth the crop target and clamp it so the crop never leaves the frame.
        smoothed_centers = []
        smooth_x, smooth_y = center_x, center_y
        alpha = 0.38
        for relative_time, target_x, target_y in raw_centers:
            smooth_x += alpha * (target_x - smooth_x)
            smooth_y += alpha * (target_y - smooth_y)
            x = min(max(0.0, smooth_x - crop_width / 2), float(max_x))
            y = min(max(0.0, smooth_y - crop_height / 2), float(max_y))
            smoothed_centers.append((relative_time, x, y))

        # FFmpeg crop expressions use the clip-relative `t` variable. Crop
        # dimensions are fixed; x/y change smoothly as the target moves.
        x_points = [(time, x) for time, x, _y in smoothed_centers]
        y_points = [(time, y) for time, _x, y in smoothed_centers]
        x_expr = _interpolated_expression(x_points)
        y_expr = _interpolated_expression(y_points)
        output_width, output_height = (1080, 1920) if output_format == "shorts" else (1920, 1080)
        return (
            f"crop=w={crop_width}:h={crop_height}:x='{x_expr}':y='{y_expr}',"
            f"scale={output_width}:{output_height},setsar=1"
        )
    finally:
        capture.release()
