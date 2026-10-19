import json
import shutil
import subprocess
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".wmv",
}


class VideoInputError(ValueError):
    """Raised when a video cannot be used for processing."""


def discover_videos(input_dir):
    """Return supported video files in the input directory."""
    input_dir = Path(input_dir)

    if not input_dir.is_dir():
        raise VideoInputError(
            f"Input directory does not exist: {input_dir}"
        )

    return sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )


def inspect_video(video_path):
    """Validate a video using ffprobe and return basic metadata."""
    video_path = Path(video_path)

    if not video_path.is_file():
        raise VideoInputError(
            f"Video file does not exist: {video_path}"
        )

    if video_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise VideoInputError(
            f"Unsupported video extension: {video_path.suffix}"
        )

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise VideoInputError(
            "ffprobe was not found. Install FFmpeg and add it to PATH."
        )

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise VideoInputError(
            "Video inspection timed out after 30 seconds."
        ) from error
    except OSError as error:
        raise VideoInputError(
            f"Could not run ffprobe: {error}"
        ) from error

    if result.returncode != 0:
        detail = result.stderr.strip() or "Unknown media error."
        raise VideoInputError(
            f"FFmpeg could not inspect this file: {detail}"
        )

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise VideoInputError(
            "ffprobe returned invalid metadata."
        ) from error

    streams = metadata.get("streams", [])
    video_streams = [
        stream for stream in streams
        if stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    if not video_streams:
        raise VideoInputError(
            "The selected file does not contain a video stream."
        )

    if not audio_streams:
        raise VideoInputError(
            "The video has no audio track to transcribe."
        )

    try:
        duration = float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise VideoInputError(
            "Could not determine the video's duration."
        ) from error

    if not duration > 0:
        raise VideoInputError(
            "The video duration must be greater than zero."
        )

    video = video_streams[0]
    audio = audio_streams[0]

    return {
        "path": str(video_path.resolve()),
        "name": video_path.name,
        "duration_seconds": duration,
        "video_codec": video.get("codec_name", "unknown"),
        "audio_codec": audio.get("codec_name", "unknown"),
        "width": video.get("width"),
        "height": video.get("height"),
    }