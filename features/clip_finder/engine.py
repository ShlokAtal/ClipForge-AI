
"""Transcript-based highlight discovery and safe FFmpeg clip export.

Uses lightweight transcript heuristics and the existing FFmpeg installation.
No database or additional AI model is required.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from features.smart_reframe import SmartReframeError, build_smart_crop_filter


class ClipFinderError(ValueError):
    """Raised when subtitles or clip export settings are invalid."""


@dataclass(frozen=True)
class SubtitleSegment:
    index: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ClipCandidate:
    start: float
    end: float
    score: float
    title: str
    transcript: str
    reasons: tuple[str, ...]

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        result = asdict(self)
        result["duration"] = round(self.duration, 3)
        result["reasons"] = list(self.reasons)
        return result


TIMESTAMP_RE = re.compile(
    r"(?P<sh>\d{2,}):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<ms>\d{3})"
)

HIGHLIGHT_TERMS = {
    "amazing": 2.0,
    "awesome": 1.8,
    "best": 1.2,
    "secret": 1.8,
    "surprising": 2.0,
    "surprise": 1.8,
    "finally": 1.2,
    "important": 1.2,
    "mistake": 1.8,
    "never": 0.9,
    "always": 0.7,
    "why": 0.9,
    "how": 0.5,
    "what": 0.5,
    "imagine": 1.3,
    "incredible": 1.8,
    "actually": 0.7,
    "revealed": 1.6,
    "tip": 0.8,
    "trick": 1.0,
    "learned": 0.8,
    "remember": 0.6,
    "love": 0.5,
    "hate": 0.5,
    "fail": 1.1,
    "failed": 1.1,
    "win": 1.0,
    "won": 1.0,
    "problem": 0.7,
    "solution": 0.9,
    "result": 0.7,
    "instead": 0.5,
}

FILLER_ONLY = {
    "",
    "♪",
    "[music]",
    "(music)",
    "[applause]",
    "(applause)",
}

OUTPUT_FORMATS = {
    "shorts": (1080, 1920),
    "youtube": (1920, 1080),
}


def _timestamp_seconds(value: str) -> float:
    match = TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise ClipFinderError(f"Invalid SRT timestamp: {value!r}")

    parts = match.groupdict()
    return (
        int(parts["sh"]) * 3600
        + int(parts["sm"]) * 60
        + int(parts["ss"])
        + int(parts["ms"]) / 1000
    )


def parse_srt(srt_path: str | Path) -> list[SubtitleSegment]:
    """Parse a standard SRT file into ordered, validated segments."""
    path = Path(srt_path)

    if not path.is_file():
        raise ClipFinderError(f"Subtitle file not found: {path}")

    content = path.read_text(encoding="utf-8-sig", errors="replace")
    blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
    segments: list[SubtitleSegment] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        if len(lines) < 2:
            continue

        timing_index = next(
            (i for i, line in enumerate(lines[:3]) if "-->" in line),
            None,
        )

        if timing_index is None:
            continue

        timing = lines[timing_index].split("-->")
        if len(timing) != 2:
            raise ClipFinderError(
                f"Invalid SRT timing line: {lines[timing_index]}"
            )

        start, end = map(_timestamp_seconds, timing)
        text = " ".join(lines[timing_index + 1:]).strip()
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\{\\[^}]*\}", "", text).strip()

        if end <= start:
            continue

        if not text or text.casefold() in FILLER_ONLY:
            continue

        segments.append(
            SubtitleSegment(len(segments) + 1, start, end, text)
        )

    if not segments:
        raise ClipFinderError(
            "No usable subtitle segments were found in this SRT file."
        )

    return segments


def _score_window(
    segments: Iterable[SubtitleSegment],
) -> tuple[float, tuple[str, ...]]:
    items = list(segments)
    text = " ".join(item.text for item in items)
    words = re.findall(r"\b[\w']+\b", text.casefold())
    reasons: list[str] = []
    score = 0.0

    matched = sorted(
        (
            (term, weight)
            for term, weight in HIGHLIGHT_TERMS.items()
            if term in words
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    if matched:
        score += min(4.0, sum(weight for _, weight in matched[:3]))
        reasons.append(
            "Engaging wording: "
            + ", ".join(term for term, _ in matched[:3])
        )

    if "?" in text:
        score += 1.0
        reasons.append("Contains a question")

    if "!" in text:
        score += 0.8
        reasons.append("Emphatic delivery in transcript punctuation")

    if re.search(r"\b[A-Z]{3,}\b", text):
        score += 0.6
        reasons.append("Emphasized word")

    if len(words) >= 12:
        score += 0.7
        reasons.append("Enough context to stand alone")
    elif len(words) < 5:
        score -= 0.8

    unique_ratio = len(set(words)) / max(1, len(words))
    if unique_ratio < 0.35 and len(words) >= 8:
        score -= 0.8
        reasons.append("Repetitive wording")

    if not reasons:
        reasons.append("Speech segment selected for context")

    return round(max(0.0, score), 2), tuple(reasons)


def find_highlights(
    srt_path: str | Path,
    *,
    video_duration: float | None = None,
    min_duration: float = 12.0,
    max_duration: float = 45.0,
    max_candidates: int = 10,
    padding_seconds: float = 1.0,
) -> list[ClipCandidate]:
    """Rank transcript windows that fit the requested duration range."""
    if not (0 < min_duration <= max_duration):
        raise ClipFinderError(
            "Clip duration range must satisfy 0 < minimum <= maximum."
        )

    if not 1 <= max_candidates <= 50:
        raise ClipFinderError("max_candidates must be between 1 and 50.")

    if not 0 <= padding_seconds <= 5:
        raise ClipFinderError("padding_seconds must be between 0 and 5 seconds.")

    segments = parse_srt(srt_path)

    if video_duration is None:
        video_duration = max(item.end for item in segments)

    if video_duration <= 0:
        raise ClipFinderError("Video duration must be greater than zero.")

    candidates: list[ClipCandidate] = []

    for start_index, first in enumerate(segments):
        start = max(0.0, first.start - padding_seconds)
        collected: list[SubtitleSegment] = []

        for segment in segments[start_index:]:
            if segment.start - start > max_duration:
                break

            collected.append(segment)
            end = min(video_duration, segment.end + padding_seconds)
            duration = end - start

            if duration < min_duration or duration > max_duration:
                continue

            score, reasons = _score_window(collected)

            if score <= 0:
                continue

            transcript = " ".join(item.text for item in collected)
            title = re.sub(r"\s+", " ", transcript).strip()

            if len(title) > 76:
                title = title[:73].rsplit(" ", 1)[0] + "…"

            candidates.append(
                ClipCandidate(
                    start=round(start, 3),
                    end=round(end, 3),
                    score=score,
                    title=title or "Suggested highlight",
                    transcript=transcript,
                    reasons=reasons,
                )
            )

            break

    candidates.sort(
        key=lambda item: (item.score, len(item.transcript)),
        reverse=True,
    )

    selected: list[ClipCandidate] = []

    for candidate in candidates:
        overlaps = any(
            min(candidate.end, other.end) - max(candidate.start, other.start)
            > 0.65 * min(candidate.duration, other.duration)
            for other in selected
        )

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= max_candidates:
            break

    return sorted(selected, key=lambda item: item.start)


def _get_video_filter(output_format: str) -> str | None:
    """Return an FFmpeg filter for the requested aspect ratio."""
    if output_format == "original":
        return None

    if output_format not in OUTPUT_FORMATS:
        allowed = ", ".join((*OUTPUT_FORMATS.keys(), "original"))
        raise ClipFinderError(
            f"Unsupported output format: {output_format!r}. "
            f"Choose one of: {allowed}."
        )

    width, height = OUTPUT_FORMATS[output_format]

    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        "setsar=1"
    )


def export_clip(
    video_path: str | Path,
    output_dir: str | Path,
    start_seconds: float,
    end_seconds: float,
    *,
    output_name: str | None = None,
    crf: int = 23,
    preset: str = "veryfast",
    output_format: str = "original",
    reframe_mode: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Export a clip in original, vertical Shorts, or landscape format.

    output_format:
        "original" - preserve the source dimensions and aspect ratio.
        "shorts"   - crop to vertical 1080x1920.
        "youtube"  - crop to landscape 1920x1080.
    """
    video = Path(video_path).resolve()
    destination = Path(output_dir).resolve()

    if not video.is_file():
        raise ClipFinderError(f"Video file not found: {video}")

    if not (0 <= start_seconds < end_seconds):
        raise ClipFinderError("Clip boundaries must satisfy 0 <= start < end.")

    if end_seconds - start_seconds < 1:
        raise ClipFinderError("Clip must be at least one second long.")

    if not isinstance(crf, int) or isinstance(crf, bool) or not 18 <= crf <= 28:
        raise ClipFinderError("CRF must be an integer between 18 and 28.")

    if preset not in {
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
    }:
        raise ClipFinderError("Unsupported FFmpeg preset.")

    if reframe_mode is not None and output_format != "original":
        try:
            video_filter = build_smart_crop_filter(
                video,
                start_seconds,
                end_seconds - start_seconds,
                output_format,
                mode=reframe_mode,
            )
        except SmartReframeError as error:
            raise ClipFinderError(str(error)) from error
    else:
        video_filter = _get_video_filter(output_format)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ClipFinderError("FFmpeg was not found on PATH.")

    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ClipFinderError(
            f"Could not create output directory: {error}"
        ) from error

    safe_stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        output_name or f"{video.stem}_clip",
    )
    safe_stem = safe_stem.strip("._") or "clip"
    output = destination / f"{safe_stem}.mp4"

    if output.exists() and not overwrite:
        raise ClipFinderError(
            f"Output already exists; refusing to overwrite: {output}"
        )

    temp = destination / f".{safe_stem}.tmp.mp4"

    try:
        temp.unlink(missing_ok=True)

        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(video),
            "-t",
            f"{end_seconds - start_seconds:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
        ]

        if video_filter:
            command.extend(["-vf", video_filter])

        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(temp),
            ]
        )

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=7200,
            check=False,
        )

        if (
            result.returncode != 0
            or not temp.is_file()
            or temp.stat().st_size == 0
        ):
            detail = (result.stderr or "").strip()[-1500:]
            raise ClipFinderError(
                f"FFmpeg could not export this clip. {detail}".strip()
            )

        temp.replace(output)

    except ClipFinderError:
        temp.unlink(missing_ok=True)
        raise

    except (OSError, subprocess.TimeoutExpired) as error:
        temp.unlink(missing_ok=True)
        raise ClipFinderError(f"Clip export failed: {error}") from error

    except Exception:
        temp.unlink(missing_ok=True)
        raise

    return output