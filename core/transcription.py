from pathlib import Path

from faster_whisper import WhisperModel

from core.video_input import inspect_video


def format_srt_timestamp(seconds):
    """Convert seconds to an SRT timestamp."""
    milliseconds = max(0, round(float(seconds) * 1000))

    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)

    return (
        f"{hours:02}:"
        f"{minutes:02}:"
        f"{whole_seconds:02},"
        f"{milliseconds:03}"
    )


def transcribe_to_srt(
    video_path,
    output_dir,
    model_name="small",
    device="cpu",
    compute_type="int8",
    skip_existing=True,
    timing_offset_ms=0,
):
    """Transcribe a video and save its subtitles as an SRT file."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    if not video_path.is_file():
        raise ValueError(f"Video file not found: {video_path}")

    if (
        not isinstance(timing_offset_ms, int)
        or isinstance(timing_offset_ms, bool)
        or not -2000 <= timing_offset_ms <= 2000
    ):
        raise ValueError(
            "timing_offset_ms must be an integer between "
            "-2000 and 2000."
        )

    output_path = output_dir / f"{video_path.stem}.srt"

    if output_path.exists() and skip_existing:
        return {
            "path": str(output_path),
            "skipped": True,
            "segments": 0,
            "language": None,
        }

    video_metadata = inspect_video(video_path)
    video_duration = float(video_metadata["duration_seconds"])

    output_dir.mkdir(parents=True, exist_ok=True)

    offset_seconds = timing_offset_ms / 1000.0

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
    )

    segments, info = model.transcribe(
        str(video_path),
        beam_size=5,
        vad_filter=True,
    )

    temporary_path = output_path.with_name(
        output_path.name + ".tmp"
    )

    segment_count = 0

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as subtitle_file:

            for segment in segments:
                text = segment.text.strip()

                if not text:
                    continue

                # Apply the configured timing adjustment.
                start_seconds = max(
                    0.0,
                    float(segment.start) + offset_seconds,
                )

                end_seconds = min(
                    video_duration,
                    float(segment.end) + offset_seconds,
                )

                # Ignore invalid or empty subtitle intervals.
                if end_seconds <= start_seconds:
                    continue

                start_timestamp = format_srt_timestamp(
                    start_seconds
                )

                end_timestamp = format_srt_timestamp(
                    end_seconds
                )

                subtitle_file.write(
                    f"{segment_count + 1}\n"
                    f"{start_timestamp} --> {end_timestamp}\n"
                    f"{text}\n\n"
                )

                segment_count += 1

        # Replace the previous SRT only after successful completion.
        temporary_path.replace(output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "path": str(output_path),
        "skipped": False,
        "segments": segment_count,
        "language": getattr(info, "language", None),
    }
