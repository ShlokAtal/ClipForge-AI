
"""Transcript-based highlight discovery and clip export page."""

from pathlib import Path
import re
import streamlit as st

from core.transcription import transcribe_to_srt
from core.subtitle_burner import (
    SubtitleBurnError,
    burn_subtitles,
    create_clip_srt,
)
from core.video_input import VideoInputError, inspect_video
from features.clip_finder.engine import (
    ClipFinderError,
    find_highlights,
    export_clip,
)
from ui.video_source import render_video_source_picker

def _safe_stem(value: str) -> str:
    """Create a filesystem-friendly output name."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned[:60] or "clip"

def _get_transcription_settings(config):
    """Read transcription settings, supporting current config structures."""
    settings = config.get("transcription") or config.get(
        "features", {}
    ).get("transcription", {})

    return {
        "model_name": settings.get("model", "small"),
        "device": settings.get("device", "cpu"),
        "compute_type": settings.get("compute_type", "int8"),
        "skip_existing": True,
        "timing_offset_ms": settings.get("timing_offset_ms", 0),
    }

def render_smart_clip_finder(
    *,
    app_dir,
    config,
    videos,
    inventory_error,
    subtitle_dir,
    output_dir,
):
    st.markdown(
        '<div class="cf-eyebrow">DISCOVER / HIGHLIGHTS</div>',
        unsafe_allow_html=True,
    )
    st.title("Smart Clip Finder")
    st.caption(
        "Find promising moments, choose a video format, "
        "review timestamps, and export clips with optional subtitles."
    )

    st.info(
        "Highlights are ranked using transcript wording and punctuation. "
        "Visual understanding, speaker tracking, and audience-retention "
        "analysis are not currently included."
    )

    input_dir = app_dir / config["paths"]["input"]

    video = render_video_source_picker(
        input_dir=input_dir,
        videos=videos,
        key_prefix="clip_finder",
    )

    if video is None:
        return

    video = Path(video).resolve()
    subtitle_dir = Path(subtitle_dir).resolve()
    output_dir = Path(output_dir).resolve()

    srt_path = subtitle_dir / f"{video.stem}.srt"

    if not srt_path.is_file():
        st.warning("Subtitles have not been generated for this video yet.")

        if st.button(
            "Generate subtitles automatically",
            type="primary",
            key="clip_finder_generate_subtitles",
        ):
            try:
                settings = _get_transcription_settings(config)

                with st.spinner(
                    "Transcribing video and generating subtitles. "
                    "This may take a while..."
                ):
                    result = transcribe_to_srt(
                        video_path=video,
                        output_dir=subtitle_dir,
                        **settings,
                    )

                srt_path = Path(result["path"])

                if not srt_path.is_file():
                    st.error(
                        "Transcription finished, but the subtitle file "
                        "could not be found."
                    )
                    return

                st.session_state["clip_finder_subtitle_path"] = str(srt_path)
                st.session_state["clip_finder_subtitle_video"] = str(video)

                if result.get("segments", 0) == 0 and not result.get("skipped"):
                    st.warning(
                        "No speech segments were detected. Check whether "
                        "the video contains speech."
                    )
                else:
                    st.success("Subtitles generated successfully!")

                st.rerun()

            except Exception as error:
                st.error(f"Subtitle generation failed: {error}")

        return

    st.success(f"Subtitle file found: {srt_path.name}")
    st.subheader("Clip settings")

    format_choice = st.radio(
        "Where will you publish these clips?",
        options=[
            "YouTube Shorts (Vertical 9:16)",
            "Regular YouTube (Landscape 16:9)",
            "Original video format",
        ],
        key="clip_finder_output_format",
        help=(
            "Shorts: 1080 × 1920. Regular YouTube: 1920 × 1080. "
            "Original preserves the source dimensions."
        ),
    )

    format_map = {
        "YouTube Shorts (Vertical 9:16)": "shorts",
        "Regular YouTube (Landscape 16:9)": "youtube",
        "Original video format": "original",
    }
    output_format = format_map[format_choice]

    if output_format == "shorts":
        st.caption(
            "Vertical 1080 × 1920. Center cropping may cut off content "
            "near the left and right edges."
        )
    elif output_format == "youtube":
        st.caption(
            "Landscape 1920 × 1080. Center cropping may cut off content "
            "near the top and bottom."
        )
    else:
        st.caption("Original dimensions and aspect ratio.")

    with st.expander("Detection settings", expanded=True):
        col1, col2 = st.columns(2)

        min_duration = col1.slider(
            "Minimum clip length (seconds)",
            min_value=8,
            max_value=30,
            value=12,
            key="clip_finder_min_duration",
        )

        max_duration = col2.slider(
            "Maximum clip length (seconds)",
            min_value=20,
            max_value=60,
            value=30,
            key="clip_finder_max_duration",
        )

        max_candidates = st.slider(
            "Number of clips to generate",
            min_value=1,
            max_value=10,
            value=5,
            key="clip_finder_max_candidates",
        )

    if min_duration >= max_duration:
        st.error(
            "Minimum clip length must be smaller than maximum clip length."
        )
        return

    if st.button(
        "Find highlights",
        type="primary",
        key="clip_finder_find",
    ):
        try:
            metadata = inspect_video(video)

            candidates = find_highlights(
                srt_path,
                video_duration=float(metadata["duration_seconds"]),
                min_duration=float(min_duration),
                max_duration=float(max_duration),
                max_candidates=int(max_candidates),
            )

            st.session_state["clip_candidates"] = [
                candidate.to_dict() for candidate in candidates
            ]
            st.session_state["clip_candidate_video"] = str(video)

        except (
            ClipFinderError,
            VideoInputError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            st.error(f"Highlight detection failed: {error}")
            return

    if st.session_state.get("clip_candidate_video") != str(video):
        return

    candidates = st.session_state.get("clip_candidates", [])

    if not candidates:
        st.warning(
            "No suitable highlights were found. Try a different duration "
            "range or check whether the subtitle file contains text."
        )
        return

    st.success(
        f"Found {len(candidates)} candidate clip(s). "
        "Review the timestamps before exporting."
    )

    try:
        metadata = inspect_video(video)
        video_duration = float(metadata["duration_seconds"])
    except (VideoInputError, OSError, ValueError) as error:
        st.error(f"Cannot inspect video duration: {error}")
        return
    
    st.subheader("Export options")
    quality_col, preset_col = st.columns(2)

    crf = quality_col.select_slider(
        "Video quality",
        options=[18, 20, 23, 26, 28],
        value=23,
        format_func=lambda value: {
            18: "Very high",
            20: "High",
            23: "Balanced",
            26: "Smaller file",
            28: "Smallest file",
        }[value],
        key="clip_finder_crf",
    )

    preset = preset_col.selectbox(
        "Export speed",
        options=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
        ],
        index=2,
        key="clip_finder_preset",
    )

    burn_captions = st.checkbox(
        "Burn subtitles into exported clips",
        value=True,
        key="clip_finder_burn_subtitles",
        help="Permanently adds the selected clip's captions to its video.",
    )

    with st.expander("Subtitle appearance", expanded=False):
        font_name = st.selectbox(
            "Font",
            ["Arial", "DejaVu Sans", "Liberation Sans", "Verdana", "Tahoma"],
            key="clip_finder_font",
        )

        font_size = st.slider(
            "Font size",
            min_value=16,
            max_value=48,
            value=28,
            key="clip_finder_font_size",
        )

        font_color = st.color_picker(
            "Text color",
            "#FFFFFF",
            key="clip_finder_font_color",
        )

        outline_color = st.color_picker(
            "Outline color",
            "#000000",
            key="clip_finder_outline_color",
        )

        outline_thickness = st.slider(
            "Outline thickness",
            min_value=0,
            max_value=5,
            value=2,
            key="clip_finder_outline",
        )

        background_mode = st.selectbox(
            "Subtitle background",
            [
                "Transparent",
                "Semi-transparent box",
                "Solid box",
            ],
            key="clip_finder_background_mode",
        )

        background_color = st.color_picker(
            "Background color",
            "#000000",
            key="clip_finder_background_color",
        )

        alignment = st.selectbox(
            "Subtitle position",
            [
                "Bottom Left",
                "Bottom Center",
                "Bottom Right",
                "Middle Center",
                "Top Left",
                "Top Center",
                "Top Right",
            ],
            index=1,
            key="clip_finder_alignment",
        )

        vertical_margin = st.slider(
            "Vertical margin",
            min_value=0,
            max_value=300,
            value=40,
            key="clip_finder_vertical_margin",
        )

        bold = st.checkbox(
            "Bold subtitles",
            value=True,
            key="clip_finder_bold",
        )

    st.caption(f"Output folder: `{output_dir}`")

    for index, candidate in enumerate(candidates, start=1):
        with st.container(border=True):
            st.subheader(f"{index}. {candidate['title']}")

            st.caption(
                f"Score: {candidate['score']:.1f} · "
                f"Suggested duration: "
                f"{candidate['end'] - candidate['start']:.1f}s"
            )

            st.write(candidate["transcript"])
            st.write(
                "**Why it was selected:** "
                + "; ".join(candidate["reasons"])
            )

            start_col, end_col = st.columns(2)

            suggested_start = max(
                0.0,
                min(
                    float(candidate["start"]),
                    max(0.0, video_duration - 0.1),
                ),
            )
            suggested_end = max(
                0.1,
                min(float(candidate["end"]), video_duration),
            )

            start = start_col.number_input(
                "Start (seconds)",
                min_value=0.0,
                max_value=max(0.1, video_duration - 0.1),
                value=suggested_start,
                step=0.5,
                key=f"clip_start_{index}",
            )

            end = end_col.number_input(
                "End (seconds)",
                min_value=0.1,
                max_value=max(0.1, video_duration),
                value=suggested_end,
                step=0.5,
                key=f"clip_end_{index}",
            )

            if end <= start:
                st.error("End time must be later than start time.")
                continue

            if end - start < 1:
                st.error("A clip must be at least one second long.")
                continue

            if st.button(
                "Export this clip",
                key=f"export_clip_{index}",
                type="primary",
            ):
                safe_name = (
                    f"{_safe_stem(video.stem)}_"
                    f"{output_format}_highlight_{index:02d}"
                )

                try:
                    with st.spinner(
                        f"Exporting clip {index}..."
                    ):
                        if burn_captions:
                            
                            clip_srt = create_clip_srt(
                                subtitle_path=srt_path,
                                output_path=(
                                    output_dir
                                    / f"{safe_name}_captions.srt"
                                ),
                                clip_start_seconds=float(start),
                                clip_end_seconds=float(end),
                            )
                            
                            raw_output = export_clip(
                                video_path=video,
                                output_dir=output_dir,
                                start_seconds=float(start),
                                end_seconds=float(end),
                                output_name=f"{safe_name}_raw",
                                crf=int(crf),
                                preset=preset,
                                output_format=output_format,
                            )

                            burn_result = burn_subtitles(
                                video_path=raw_output,
                                subtitle_path=clip_srt,
                                output_dir=output_dir,
                                crf=int(crf),
                                preset=preset,
                                font_name=font_name,
                                font_size=int(font_size),
                                font_color=font_color,
                                outline_color=outline_color,
                                outline_thickness=int(outline_thickness),
                                background_mode=background_mode,
                                background_color=background_color,
                                alignment=alignment,
                                vertical_margin=int(vertical_margin),
                                bold=bool(bold),
                                output_format="original",
                            )

                            final_output = Path(burn_result["path"])

                        else:
                            final_output = export_clip(
                                video_path=video,
                                output_dir=output_dir,
                                start_seconds=float(start),
                                end_seconds=float(end),
                                output_name=safe_name,
                                crf=int(crf),
                                preset=preset,
                                output_format=output_format,
                            )

                    st.session_state[
                        f"clip_export_path_{index}"
                    ] = str(final_output)

                    st.success("Clip exported successfully!")
                    st.write(f"**Format:** {format_choice}")
                    st.write(
                        f"**Subtitles burned in:** "
                        f"{'Yes' if burn_captions else 'No'}"
                    )
                    st.write(f"**Saved to:** `{final_output}`")

                except (
                    ClipFinderError,
                    SubtitleBurnError,
                    OSError,
                    ValueError,
                    RuntimeError,
                ) as error:
                    st.error(f"Clip export failed: {error}")

            saved_output = st.session_state.get(
                f"clip_export_path_{index}"
            )

            if saved_output and Path(saved_output).is_file():
                output_path = Path(saved_output)

                try:
                    with output_path.open("rb") as handle:
                        st.download_button(
                            "Download clip",
                            data=handle.read(),
                            file_name=output_path.name,
                            mime="video/mp4",
                            key=f"download_clip_{index}",
                        )
                        
                except OSError as error:
                    st.warning(
                        f"Could not prepare clip download: {error}"
                    )