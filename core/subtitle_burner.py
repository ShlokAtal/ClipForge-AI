
"""Burn SRT subtitles into video files using FFmpeg."""

import re
import shutil
import subprocess
from pathlib import Path

class SubtitleBurnError(RuntimeError):
    """Raised when subtitles cannot be burned into a video."""

ALLOWED_FONTS = {
    "Arial",
    "DejaVu Sans",
    "Liberation Sans",
    "Verdana",
    "Tahoma",
}

ALIGNMENT_MAP = {
    "Bottom Left": 1,
    "Bottom Center": 2,
    "Bottom Right": 3,
    "Middle Center": 5,
    "Top Left": 7,
    "Top Center": 8,
    "Top Right": 9,
}

BACKGROUND_MODES = {
    "Transparent",
    "Semi-transparent box",
    "Solid box",
}

ALLOWED_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
}

OUTPUT_DIMENSIONS = {
    "shorts": (1080, 1920),
    "youtube": (1920, 1080),
}


def _validate_color(color):
    """Validate a hexadecimal RGB color."""
    if not isinstance(color, str) or not re.fullmatch(
        r"#[0-9A-Fa-f]{6}", color
    ):
        raise SubtitleBurnError(
            "Invalid color. Choose a color in #RRGGBB format."
        )
    return color.upper()


def _ass_color(color, alpha="00"):
    """Convert #RRGGBB into ASS AABBGGRR notation."""
    color = _validate_color(color).lstrip("#")
    red, green, blue = color[0:2], color[2:4], color[4:6]
    return f"&H{alpha}{blue}{green}{red}"


def _build_force_style(
    font_name="Arial",
    font_size=28,
    font_color="#FFFFFF",
    outline_color="#000000",
    outline_thickness=2,
    background_mode="Transparent",
    background_color="#000000",
    alignment="Bottom Center",
    vertical_margin=40,
    bold=True,
):
    """Build and validate the FFmpeg ASS subtitle style."""
    if font_name not in ALLOWED_FONTS:
        raise SubtitleBurnError("Unsupported subtitle font.")

    if (
        not isinstance(font_size, int)
        or isinstance(font_size, bool)
        or not 16 <= font_size <= 48
    ):
        raise SubtitleBurnError(
            "Font size must be an integer between 16 and 48."
        )

    if (
        not isinstance(outline_thickness, int)
        or isinstance(outline_thickness, bool)
        or not 0 <= outline_thickness <= 5
    ):
        raise SubtitleBurnError(
            "Outline thickness must be between 0 and 5."
        )

    if (
        not isinstance(vertical_margin, int)
        or isinstance(vertical_margin, bool)
        or not 0 <= vertical_margin <= 300
    ):
        raise SubtitleBurnError(
            "Vertical margin must be between 0 and 300."
        )

    if alignment not in ALIGNMENT_MAP:
        raise SubtitleBurnError(
            f"Unsupported subtitle position: {alignment!r}"
        )

    if background_mode not in BACKGROUND_MODES:
        raise SubtitleBurnError(
            "Unsupported subtitle background mode."
        )

    if not isinstance(bold, bool):
        raise SubtitleBurnError("Bold must be True or False.")

    primary_color = _ass_color(font_color)
    outline_ass_color = _ass_color(outline_color)

    if background_mode == "Transparent":
        border_style = 1
        back_color = _ass_color("#000000", alpha="FF")
    elif background_mode == "Semi-transparent box":
        border_style = 3
        back_color = _ass_color(background_color, alpha="80")
    else:
        border_style = 3
        back_color = _ass_color(background_color)

    return (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour={primary_color},"
        f"OutlineColour={outline_ass_color},"
        f"BackColour={back_color},"
        f"BorderStyle={border_style},"
        f"Outline={outline_thickness},"
        f"Shadow=0,"
        f"Alignment={ALIGNMENT_MAP[alignment]},"
        f"MarginV={vertical_margin},"
        f"Bold={-1 if bold else 0}"
    )


def _escape_filter_path(path):
    """Escape a subtitle path for FFmpeg filter syntax."""
    value = str(Path(path).resolve()).replace("\\", "/")

    for old, new in (
        ("\\", "\\\\"),
        (":", r"\:"),
        ("'", r"\'"),
        (",", r"\,"),
        ("[", r"\["),
        ("]", r"\]"),
        ("%", r"\%"),
    ):
        value = value.replace(old, new)

    return value

def _escape_filter_value(value):
    """Escape commas and quotes in an FFmpeg filter option value."""
    return value.replace("\\", "\\\\").replace("'", r"\'").replace(",", r"\,")

def _parse_srt_timestamp(value):
    """Convert HH:MM:SS,mmm or HH:MM:SS.mmm to seconds."""
    match = re.fullmatch(
        r"(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})",
        value.strip(),
    )
    if not match:
        raise SubtitleBurnError(
            f"Invalid SRT timestamp: {value!r}"
        )

    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def _format_srt_timestamp(seconds):
    """Convert nonnegative seconds to an SRT timestamp."""
    milliseconds_total = round(seconds * 1000)
    hours, remainder = divmod(milliseconds_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)

    return (
        f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"
    )


def create_clip_srt(
    subtitle_path,
    output_path,
    clip_start_seconds,
    clip_end_seconds,
):
    """Create an SRT containing only subtitles overlapping a clip.

    Subtitle times are shifted so the clip begins at time zero.
    """
    subtitle_path = Path(subtitle_path).resolve()
    output_path = Path(output_path).resolve()

    if not subtitle_path.is_file():
        raise SubtitleBurnError(
            f"Subtitle file not found: {subtitle_path}"
        )

    if subtitle_path.suffix.lower() != ".srt":
        raise SubtitleBurnError("Subtitle file must use the .srt format.")

    if (
        not isinstance(clip_start_seconds, (int, float))
        or isinstance(clip_start_seconds, bool)
        or not isinstance(clip_end_seconds, (int, float))
        or isinstance(clip_end_seconds, bool)
        or clip_start_seconds < 0
        or clip_end_seconds <= clip_start_seconds
    ):
        raise SubtitleBurnError("Invalid clip subtitle time range.")

    content = subtitle_path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
    output_blocks = []

    for block in blocks:
        lines = block.splitlines()
        timing_index = next(
            (i for i, line in enumerate(lines) if "-->" in line),
            None,
        )

        if timing_index is None:
            continue

        timing_parts = lines[timing_index].split("-->")
        if len(timing_parts) != 2:
            continue

        try:
            original_start = _parse_srt_timestamp(timing_parts[0])
            original_end = _parse_srt_timestamp(timing_parts[1])
        except SubtitleBurnError:
            continue

        start = max(original_start, float(clip_start_seconds))
        end = min(original_end, float(clip_end_seconds))

        if end <= start:
            continue

       
        relative_start = max(0.0, start - float(clip_start_seconds))
        relative_end = max(0.0, end - float(clip_start_seconds))

        text_lines = lines[timing_index + 1:]
        if not any(line.strip() for line in text_lines):
            continue

        output_blocks.append(
            "\n".join(
                [
                    str(len(output_blocks) + 1),
                    (
                        f"{_format_srt_timestamp(relative_start)} --> "
                        f"{_format_srt_timestamp(relative_end)}"
                    ),
                    *text_lines,
                ]
            )
        )

    if not output_blocks:
        raise SubtitleBurnError(
            "No subtitles overlap the selected clip. "
            "Check the subtitle file and clip timestamps."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n\n".join(output_blocks) + "\n",
        encoding="utf-8",
    )

    return output_path

def burn_subtitles(
    video_path,
    subtitle_path,
    output_dir,
    overwrite=False,
    crf=23,
    preset="veryfast",
    font_name="Arial",
    font_size=28,
    font_color="#FFFFFF",
    outline_color="#000000",
    outline_thickness=2,
    background_mode="Transparent",
    background_color="#000000",
    alignment="Bottom Center",
    vertical_margin=40,
    bold=True,
    output_format="original",
    output_name=None,
):
    """Permanently burn SRT subtitles into an MP4 video.

    output_format:
        "original" - preserve input dimensions.
        "shorts"   - center-crop and resize to 1080x1920.
        "youtube"  - center-crop and resize to 1920x1080.

    Returns a dictionary containing the output path and file size.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SubtitleBurnError(
            "FFmpeg was not found on PATH. Install FFmpeg and restart "
            "the terminal."
        )

    video_path = Path(video_path).resolve()
    subtitle_path = Path(subtitle_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not video_path.is_file():
        raise SubtitleBurnError(f"Video file not found: {video_path}")

    if not subtitle_path.is_file():
        raise SubtitleBurnError(f"Subtitle file not found: {subtitle_path}")

    if video_path.suffix.lower() not in {
        ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"
    }:
        raise SubtitleBurnError("Unsupported input video format.")

    if subtitle_path.suffix.lower() != ".srt":
        raise SubtitleBurnError("Subtitle file must use the .srt format.")

    if (
        not isinstance(crf, int)
        or isinstance(crf, bool)
        or not 18 <= crf <= 28
    ):
        raise SubtitleBurnError("CRF must be an integer between 18 and 28.")

    if preset not in ALLOWED_PRESETS:
        raise SubtitleBurnError("Unsupported FFmpeg encoding preset.")

    if output_format not in {"original", *OUTPUT_DIMENSIONS.keys()}:
        raise SubtitleBurnError(
            "output_format must be 'original', 'shorts', or 'youtube'."
        )

    force_style = _build_force_style(
        font_name=font_name,
        font_size=font_size,
        font_color=font_color,
        outline_color=outline_color,
        outline_thickness=outline_thickness,
        background_mode=background_mode,
        background_color=background_color,
        alignment=alignment,
        vertical_margin=vertical_margin,
        bold=bold,
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SubtitleBurnError(
            f"Could not create output directory: {error}"
        ) from error

    stem = output_name or f"{video_path.stem}_subtitled"
    output_path = output_dir / f"{stem}.mp4"

    if output_path.resolve() == video_path:
        raise SubtitleBurnError(
            "Output path cannot be the same as the input video."
        )

    if output_path.exists() and not overwrite:
        raise SubtitleBurnError(
            f"Output file already exists: {output_path}"
        )

    temp_path = output_dir / f".{video_path.stem}_subtitled_temp.mp4"
    temp_path.unlink(missing_ok=True)

    escaped_subtitle_path = _escape_filter_path(subtitle_path)
    escaped_force_style = _escape_filter_value(force_style)

    video_filters = []

    if output_format in OUTPUT_DIMENSIONS:
        width, height = OUTPUT_DIMENSIONS[output_format]
        video_filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )

    video_filters.append(
        f"subtitles=filename='{escaped_subtitle_path}'"
        f":force_style='{escaped_force_style}'"
    )

    video_filter = ",".join(video_filters)

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        video_filter,
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
        str(temp_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=7200,
            check=False,
        )

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            if not details:
                details = "FFmpeg did not provide additional details."

            raise SubtitleBurnError(
                "FFmpeg failed to burn subtitles:\n" + details[-5000:]
            )

        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            raise SubtitleBurnError(
                "FFmpeg finished without producing a valid output file."
            )

        if output_path.exists() and overwrite:
            output_path.unlink()

        temp_path.replace(output_path)

    except subprocess.TimeoutExpired as error:
        raise SubtitleBurnError(
            "Video processing exceeded the two-hour time limit."
        ) from error

    except FileNotFoundError as error:
        raise SubtitleBurnError(
            "FFmpeg could not be started. Check your FFmpeg installation."
        ) from error

    except OSError as error:
        raise SubtitleBurnError(
            f"Could not process or save the video: {error}"
        ) from error

    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "path": str(output_path),
        "skipped": False,
        "size_bytes": output_path.stat().st_size,
    }