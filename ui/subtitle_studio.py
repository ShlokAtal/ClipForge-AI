"""Subtitle generation, styling, and export page."""
from pathlib import Path

import streamlit as st

from core.subtitle_burner import SubtitleBurnError, burn_subtitles
from core.transcription import transcribe_to_srt
from core.video_input import VideoInputError, inspect_video
from ui.video_source import render_video_source_picker


def render_subtitle_studio(*, app_dir, config, videos, inventory_error, subtitle_dir, output_dir):
    st.markdown('<div class="cf-eyebrow">CREATE / SUBTITLES</div>', unsafe_allow_html=True)
    st.title("Subtitle studio")
    st.caption("Generate AI subtitles, tune their appearance, and export a new MP4.")
    video = render_video_source_picker(
        input_dir=app_dir / config["paths"]["input"], videos=videos, key_prefix="subtitle"
    )
    if video is None:
        return
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="cf-section">Typography</div>', unsafe_allow_html=True)
        font_name = st.selectbox("Font", ["Arial", "DejaVu Sans", "Liberation Sans", "Verdana", "Tahoma"])
        font_size = st.slider("Font size", 16, 48, 28, 2)
        font_color = st.color_picker("Text color", "#FFFFFF")
        bold = st.checkbox("Bold subtitles", True)
        outline_color = st.color_picker("Outline color", "#000000")
        outline_thickness = st.slider("Outline thickness", 0, 5, 2)

    with right:
        st.markdown('<div class="cf-section">Placement & output</div>', unsafe_allow_html=True)
        alignment = st.selectbox("Position", ["Bottom Center", "Middle Center", "Top Center", "Bottom Left", "Bottom Right", "Top Left", "Top Right"])
        background_mode = st.selectbox("Background", ["Transparent", "Semi-transparent box", "Solid box"])
        background_color = st.color_picker("Background color", "#000000", disabled=background_mode == "Transparent")
        vertical_margin = st.slider("Vertical margin", 0, 300, 40, 5)
        crf = st.slider("Output quality · lower is higher quality", 18, 28, 23)

    timing_offset_ms = st.slider(
        "Subtitle timing adjustment (milliseconds)", -2000, 2000,
        int(config["transcription"].get("timing_offset_ms", 0)), 25,
        help="Negative values move subtitles earlier; positive values move them later.",
    )
    preview_bg = "transparent" if background_mode == "Transparent" else (
        f"{background_color}B3" if background_mode == "Semi-transparent box" else background_color
    )
    preview_weight = "700" if bold else "400"
    preview_outline = f"0 1px 3px {outline_color}" if outline_thickness else "none"
    st.markdown(
        f'<div style="background:#202b40;border:1px solid #35425e;border-radius:12px;'
        f'padding:24px;text-align:center;color:{font_color};font-family:{font_name},sans-serif;'
        f'font-size:{min(font_size,36)}px;font-weight:{preview_weight};text-shadow:{preview_outline};">'
        f'<span style="background:{preview_bg};padding:5px 10px;border-radius:5px">'
        'Your subtitles will look like this</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Approximate preview; FFmpeg rendering and installed fonts may differ.")
    regenerate = st.checkbox("Regenerate subtitles even if an SRT already exists", False)
    st.caption(
        f"Model: {config['transcription']['model']} · Device: {config['transcription']['device']} · "
        f"Compute: {config['transcription']['compute_type']}"
    )

    if not st.button("Generate subtitles & export video", type="primary"):
        return

    srt_path = subtitle_dir / f"{video.stem}.srt"
    try:
        with st.status("Processing video…", expanded=True) as status:
            metadata = inspect_video(video)
            st.write(f"Validated · {metadata['duration_seconds']:.1f}s · {metadata['width']} × {metadata['height']}")
            transcription = transcribe_to_srt(
                video_path=video,
                output_dir=subtitle_dir,
                model_name=config["transcription"]["model"],
                device=config["transcription"]["device"],
                compute_type=config["transcription"]["compute_type"],
                skip_existing=config.get("skip_existing_outputs", True) and not regenerate,
                timing_offset_ms=timing_offset_ms,
            )
            st.write(
                "Using existing SRT." if transcription["skipped"]
                else f"Transcription complete · {transcription['segments']} segments"
            )
            st.write("Burning subtitles into a new MP4…")
            result = burn_subtitles(
                video_path=video, subtitle_path=srt_path, output_dir=output_dir,
                overwrite=True, crf=crf, preset="veryfast", font_name=font_name,
                font_size=font_size, font_color=font_color, outline_color=outline_color,
                outline_thickness=outline_thickness, background_mode=background_mode,
                background_color=background_color, alignment=alignment,
                vertical_margin=vertical_margin, bold=bold,
            )
            status.update(label="Export completed", state="complete", expanded=False)

        st.success("Your subtitled video is ready.")
        st.write(f"**Output:** `{result['path']}` · {result['size_bytes']:,} bytes")
        st.write(f"**Subtitles:** `{transcription['path']}`")
        with Path(result["path"]).open("rb") as handle:
            st.download_button("Download subtitled MP4", handle, file_name=Path(result["path"]).name,
                               mime="video/mp4", key=f"mp4_{video.name}")
        with Path(transcription["path"]).open("rb") as handle:
            st.download_button("Download SRT subtitles", handle, file_name=Path(transcription["path"]).name,
                               mime="application/x-subrip", key=f"srt_{video.name}")
    except (VideoInputError, SubtitleBurnError, OSError, ValueError, RuntimeError, TypeError) as error:
        st.error(f"Processing failed: {error}")
