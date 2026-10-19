
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

    red = color[0:2]
    green = color[2:4]
    blue = color[4:6]

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

    bold_value = -1 if bold else 0

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
        f"Bold={bold_value}"
    )


def _escape_filter_path(path):
    """Escape a subtitle path for FFmpeg filter syntax."""
    value = str(Path(path).resolve()).replace("\\", "/")

    # Escape special characters interpreted by FFmpeg.
    value = value.replace("\\", "\\\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    value = value.replace("[", r"\[")
    value = value.replace("]", r"\]")
    value = value.replace("%", r"\%")

    return value


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
):
    """
    Permanently burn SRT subtitles into an MP4 video.

    Returns:
        dict: Output path, skipped status, and output size.
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
        raise SubtitleBurnError(
            f"Video file not found: {video_path}"
        )

    if not subtitle_path.is_file():
        raise SubtitleBurnError(
            f"Subtitle file not found: {subtitle_path}"
        )

    if video_path.suffix.lower() not in {
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".m4v",
    }:
        raise SubtitleBurnError(
            "Unsupported input video format."
        )

    if subtitle_path.suffix.lower() != ".srt":
        raise SubtitleBurnError(
            "Subtitle file must use the .srt format."
        )

    if (
        not isinstance(crf, int)
        or isinstance(crf, bool)
        or not 18 <= crf <= 28
    ):
        raise SubtitleBurnError(
            "CRF must be an integer between 18 and 28."
        )

    if preset not in ALLOWED_PRESETS:
        raise SubtitleBurnError(
            "Unsupported FFmpeg encoding preset."
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

    output_path = output_dir / f"{video_path.stem}_subtitled.mp4"

    if output_path.resolve() == video_path:
        raise SubtitleBurnError(
            "Output path cannot be the same as the input video."
        )

    # Protect existing output unless the caller explicitly permits
    # overwriting it. This also preserves the existing unit-test contract.
    if output_path.exists() and not overwrite:
        raise SubtitleBurnError(
            f"Output file already exists: {output_path}"
        )

    # Use a separate temporary file so failed encoding does not replace
    # a previously completed output.
    temp_path = output_dir / f"{video_path.stem}_subtitled_temp.mp4"

    if temp_path.exists():
        try:
            temp_path.unlink()
        except OSError as error:
            raise SubtitleBurnError(
                f"Could not clear temporary output: {error}"
            ) from error

    escaped_subtitle_path = _escape_filter_path(subtitle_path)

    subtitle_filter = (
        f"subtitles=filename='{escaped_subtitle_path}'"
        f":force_style='{force_style}'"
    )

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
        subtitle_filter,
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
            details = (
                result.stderr or result.stdout or ""
            ).strip()

            if not details:
                details = (
                    "FFmpeg did not provide additional details."
                )

            raise SubtitleBurnError(
                "FFmpeg failed to burn subtitles:\n"
                + details[-5000:]
            )

        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            raise SubtitleBurnError(
                "FFmpeg finished without producing a valid output file."
            )

        # Replace the final output only after successful encoding.
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
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    return {
        "path": str(output_path),
        "skipped": False,
        "size_bytes": output_path.stat().st_size,
    }