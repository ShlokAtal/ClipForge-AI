"""Render one highlight clip: cut, optional smart reframe, optional captions.

Both single-clip and batch exports go through ``render_clip`` so behaviour stays
identical. Intermediate files live in a temporary work folder that is always
removed, so the output folder contains only finished deliverables.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from core.subtitle_burner import SubtitleBurnError, burn_subtitles, create_clip_srt
from features.clip_finder.engine import ClipFinderError, export_clip


class ClipRenderError(RuntimeError):
    """Raised when a clip cannot be rendered."""


DEFAULT_CAPTION_STYLE = {
    "font_name": "Arial",
    "font_size": 28,
    "font_color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_thickness": 2,
    "background_mode": "Transparent",
    "background_color": "#000000",
    "alignment": "Bottom Center",
    "vertical_margin": 40,
    "bold": True,
}


def safe_clip_name(value: str) -> str:
    """Return a filesystem-safe base name for an output file."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned[:80] or "clip"


@dataclass(frozen=True)
class ClipRequest:
    """Everything needed to render one clip."""

    video_path: Path
    subtitle_path: Path
    start_seconds: float
    end_seconds: float
    name: str
    output_format: str = "original"
    reframe_mode: str | None = None
    crf: int = 23
    preset: str = "veryfast"
    burn_captions: bool = True
    caption_style: dict = field(default_factory=lambda: dict(DEFAULT_CAPTION_STYLE))


def render_clip(
    request: ClipRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = True,
) -> Path:
    """Render a clip into ``output_dir`` and return the finished file path."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    name = safe_clip_name(request.name)
    final_path = output_dir / f"{name}.mp4"

    if final_path.exists() and not overwrite:
        raise ClipRenderError(f"Clip already exists: {final_path.name}")

    work_dir = Path(tempfile.mkdtemp(prefix=".work_", dir=output_dir))

    try:
        if request.burn_captions:
            clip_srt = create_clip_srt(
                subtitle_path=request.subtitle_path,
                output_path=work_dir / f"{name}.srt",
                clip_start_seconds=float(request.start_seconds),
                clip_end_seconds=float(request.end_seconds),
            )

            raw_clip = export_clip(
                video_path=request.video_path,
                output_dir=work_dir,
                start_seconds=float(request.start_seconds),
                end_seconds=float(request.end_seconds),
                output_name=f"{name}_raw",
                crf=int(request.crf),
                preset=request.preset,
                output_format=request.output_format,
                reframe_mode=request.reframe_mode,
            )

            result = burn_subtitles(
                video_path=raw_clip,
                subtitle_path=clip_srt,
                output_dir=output_dir,
                overwrite=True,
                crf=int(request.crf),
                preset=request.preset,
                output_format="original",
                output_name=name,
                **request.caption_style,
            )
            return Path(result["path"])

        return export_clip(
            video_path=request.video_path,
            output_dir=output_dir,
            start_seconds=float(request.start_seconds),
            end_seconds=float(request.end_seconds),
            output_name=name,
            crf=int(request.crf),
            preset=request.preset,
            output_format=request.output_format,
            reframe_mode=request.reframe_mode,
            overwrite=overwrite,
        )

    except (ClipFinderError, SubtitleBurnError) as error:
        raise ClipRenderError(str(error)) from error

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
