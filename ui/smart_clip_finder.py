"""Smart Clip Finder: discover highlights, review them, and export clips.

Workflow: pick a video, generate or reuse subtitles, find ranked highlights,
review and edit each clip's timing and draft metadata, then export one clip or
a batch. Every export goes through the same render pipeline.
"""

from pathlib import Path

import streamlit as st

from core.transcription import transcribe_to_srt
from core.video_input import VideoInputError, inspect_video
from features.clip_finder import (
    ClipFinderError,
    ClipRenderError,
    ClipRequest,
    build_metadata,
    find_highlights,
    render_clip,
    safe_clip_name,
    write_metadata_file,
)
from ui.model_cache import get_whisper_model
from ui.video_source import render_video_source_picker

FORMAT_OPTIONS = {
    "YouTube Shorts (vertical 9:16)": "shorts",
    "Regular YouTube (landscape 16:9)": "youtube",
    "Original video format": "original",
}

FRAMING_OPTIONS = {
    "Auto subject tracking (faces first)": "auto",
    "Face focus (talking-head videos)": "face",
    "Person focus (full-body / activity videos)": "person",
    "Center crop (no subject tracking)": None,
}

FONT_OPTIONS = ["Arial", "DejaVu Sans", "Liberation Sans", "Verdana", "Tahoma"]
ALIGNMENT_OPTIONS = [
    "Bottom Left",
    "Bottom Center",
    "Bottom Right",
    "Middle Center",
    "Top Left",
    "Top Center",
    "Top Right",
]
BACKGROUND_OPTIONS = ["Transparent", "Semi-transparent box", "Solid box"]
CRF_LABELS = {
    18: "Very high",
    20: "High",
    23: "Balanced",
    26: "Smaller file",
    28: "Smallest file",
}
PRESET_OPTIONS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"]

RESULTS_KEY = "clip_results"
CANDIDATES_KEY = "clip_candidates"
RUN_COUNTER_KEY = "clip_run_counter"
FLASH_KEY = "clip_flash"


@st.cache_data(show_spinner=False)
def _probe_duration(path: str, modified: float) -> float:
    """Return a video's duration; cached per file and modification time."""
    return float(inspect_video(path)["duration_seconds"])


def _transcription_settings(config) -> dict:
    settings = config["transcription"]
    return {
        "model_name": settings["model"],
        "device": settings["device"],
        "compute_type": settings["compute_type"],
        "skip_existing": True,
        "timing_offset_ms": int(settings.get("timing_offset_ms", 0)),
    }


def _render_header() -> None:
    st.markdown('<div class="cf-eyebrow">DISCOVER / HIGHLIGHTS</div>', unsafe_allow_html=True)
    st.title("Smart Clip Finder")
    st.caption(
        "Find promising moments, review timing and draft metadata, then export "
        "one clip or a batch with optional burned-in captions."
    )
    st.info(
        "Highlights are ranked from transcript wording and punctuation. Smart "
        "reframing follows visible faces or people, but it does not identify "
        "the active speaker or understand actions. Review each clip before publishing."
    )


def _render_subtitle_generation(video: Path, srt_path: Path, subtitle_dir: Path, config) -> None:
    st.warning("Subtitles have not been generated for this video yet.")
    st.caption("Speech recognition runs locally. The model stays in memory after its first use.")

    if not st.button(
        "Generate subtitles",
        type="primary",
        key="clip_finder_generate_subtitles",
    ):
        return

    settings = _transcription_settings(config)

    try:
        with st.spinner("Transcribing speech. This can take several minutes for long videos…"):
            model = get_whisper_model(
                settings["model_name"],
                settings["device"],
                settings["compute_type"],
            )
            result = transcribe_to_srt(
                video_path=video,
                output_dir=subtitle_dir,
                model=model,
                **settings,
            )
    except (VideoInputError, OSError, RuntimeError, ValueError) as error:
        st.error(f"Subtitle generation failed: {error}")
        return

    if result["segments"] == 0:
        # Discard the empty file so the page keeps offering to generate subtitles.
        srt_path.unlink(missing_ok=True)
        st.warning("No speech was detected in this video. Check that it contains spoken audio.")
        return

    st.rerun()


def _render_detection_settings() -> tuple[int, int, int]:
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
    return min_duration, max_duration, max_candidates


def _run_discovery(video: Path, srt_path: Path, duration: float, min_d, max_d, count) -> None:
    try:
        with st.spinner("Ranking transcript windows…"):
            candidates = find_highlights(
                srt_path,
                video_duration=duration,
                min_duration=float(min_d),
                max_duration=float(max_d),
                max_candidates=int(count),
            )
    except (ClipFinderError, ValueError, OSError) as error:
        st.error(f"Highlight detection failed: {error}")
        return

    # Each run gets a new id, so per-clip widgets reset to the fresh suggestions.
    run = st.session_state.get(RUN_COUNTER_KEY, 0) + 1
    st.session_state[RUN_COUNTER_KEY] = run
    st.session_state[CANDIDATES_KEY] = {
        "video": str(video),
        "run": run,
        "items": [candidate.to_dict() for candidate in candidates],
    }


def _render_export_options() -> dict:
    st.subheader("Export options")
    quality_col, preset_col = st.columns(2)

    crf = quality_col.select_slider(
        "Video quality",
        options=list(CRF_LABELS),
        value=23,
        format_func=lambda value: CRF_LABELS[value],
        key="clip_finder_crf",
    )
    preset = preset_col.selectbox(
        "Export speed",
        options=PRESET_OPTIONS,
        index=2,
        key="clip_finder_preset",
        help="Faster presets render sooner but produce slightly larger files.",
    )
    burn_captions = st.checkbox(
        "Burn subtitles into exported clips",
        value=True,
        key="clip_finder_burn_subtitles",
        help="Permanently adds the clip's captions to the video.",
    )

    with st.expander("Subtitle appearance", expanded=False):
        font_name = st.selectbox("Font", FONT_OPTIONS, key="clip_finder_font")
        font_size = st.slider("Font size", 16, 48, 28, key="clip_finder_font_size")
        font_color = st.color_picker("Text color", "#FFFFFF", key="clip_finder_font_color")
        outline_color = st.color_picker("Outline color", "#000000", key="clip_finder_outline_color")
        outline_thickness = st.slider("Outline thickness", 0, 5, 2, key="clip_finder_outline")
        background_mode = st.selectbox(
            "Subtitle background", BACKGROUND_OPTIONS, key="clip_finder_background_mode"
        )
        background_color = st.color_picker(
            "Background color", "#000000", key="clip_finder_background_color"
        )
        alignment = st.selectbox(
            "Subtitle position", ALIGNMENT_OPTIONS, index=1, key="clip_finder_alignment"
        )
        vertical_margin = st.slider("Vertical margin", 0, 300, 40, key="clip_finder_vertical_margin")
        bold = st.checkbox("Bold subtitles", value=True, key="clip_finder_bold")

    return {
        "crf": int(crf),
        "preset": preset,
        "burn_captions": bool(burn_captions),
        "caption_style": {
            "font_name": font_name,
            "font_size": int(font_size),
            "font_color": font_color,
            "outline_color": outline_color,
            "outline_thickness": int(outline_thickness),
            "background_mode": background_mode,
            "background_color": background_color,
            "alignment": alignment,
            "vertical_margin": int(vertical_margin),
            "bold": bool(bold),
        },
    }


def _range_error(start: float, end: float) -> str | None:
    if end <= start:
        return "End time must be later than start time."
    if end - start < 1:
        return "A clip must be at least one second long."
    return None


def _build_job(video, srt_path, output_format, reframe_mode, options, candidate, values):
    """Return (ClipRequest, metadata payload) for one clip."""
    start, end = float(values["start"]), float(values["end"])
    name = f"{safe_clip_name(video.stem)[:40]}_{output_format}_{round(start)}-{round(end)}s"

    hashtags = [
        tag if tag.startswith("#") else f"#{tag}"
        for tag in values["hashtags"].split()
        if tag.strip("#")
    ]

    request = ClipRequest(
        video_path=video,
        subtitle_path=srt_path,
        start_seconds=start,
        end_seconds=end,
        name=name,
        output_format=output_format,
        reframe_mode=reframe_mode,
        crf=options["crf"],
        preset=options["preset"],
        burn_captions=options["burn_captions"],
        caption_style=options["caption_style"],
    )

    payload = {
        "source_video": video.name,
        "format": output_format,
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "duration_seconds": round(end - start, 3),
        "score": candidate["score"],
        "burned_subtitles": options["burn_captions"],
        "title": values["title"].strip(),
        "description": values["description"].strip(),
        "hashtags": hashtags,
        "transcript": candidate["transcript"],
    }
    return request, payload


def _export_job(job, output_dir: Path, metadata_dir: Path) -> dict:
    """Render one clip and write its metadata sidecar."""
    request, payload = job
    final_path = render_clip(request, output_dir, overwrite=True)

    payload["clip_file"] = final_path.name
    metadata_path = write_metadata_file(metadata_dir / f"{final_path.stem}.json", payload)
    return {"path": str(final_path), "metadata": str(metadata_path)}


def _render_result(result_key: str) -> None:
    """Show the outcome of an export, with a download when the file exists."""
    result = st.session_state[RESULTS_KEY].get(result_key)
    if not result:
        return

    if "error" in result:
        st.error(f"Clip export failed: {result['error']}")
        return

    path = Path(result["ok"]["path"])
    if not path.is_file():
        st.warning("This exported clip is no longer on disk.")
        return

    st.success(f"Exported: {path.name}")
    with path.open("rb") as handle:
        st.download_button(
            "Download clip",
            data=handle,
            file_name=path.name,
            mime="video/mp4",
            key=f"download_{result_key}",
        )


def _render_batch(pending, ctx, results) -> None:
    st.subheader("Batch export")
    limit = int(ctx["config"]["max_batch_size"])
    count = len(pending)

    if count > limit:
        st.error(
            f"Batch export is limited to {limit} clips per run. "
            f"Deselect {count - limit} clip(s) to continue."
        )
    elif count == 0:
        st.caption("Select at least one valid clip to enable batch export.")

    if not st.button(
        f"Export {count} selected clip(s)",
        type="primary",
        disabled=count == 0 or count > limit,
        key="clip_finder_batch_export",
    ):
        return

    progress = st.progress(0.0, text="Starting batch export…")
    succeeded, failed = 0, 0

    for position, (result_key, job) in enumerate(pending, start=1):
        progress.progress((position - 1) / count, text=f"Exporting clip {position} of {count}…")
        try:
            results[result_key] = {"ok": _export_job(job, ctx["output_dir"], ctx["metadata_dir"])}
            succeeded += 1
        except (ClipRenderError, OSError, ValueError) as exc:
            results[result_key] = {"error": str(exc)}
            failed += 1

    progress.progress(1.0, text="Batch complete")

    if failed:
        flash = ("warning", f"Batch finished: {succeeded} exported, {failed} failed. See each clip for details.")
    else:
        flash = ("success", f"Batch finished: {succeeded} clip(s) exported.")

    st.session_state[FLASH_KEY] = flash
    st.rerun()


def _render_candidates(ctx: dict, output_format: str, reframe_mode, options: dict) -> None:
    state = st.session_state[CANDIDATES_KEY]
    run = state["run"]
    candidates = state["items"]
    results = st.session_state.setdefault(RESULTS_KEY, {})

    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        kind, message = flash
        (st.success if kind == "success" else st.warning)(message)

    if not candidates:
        st.warning(
            "No suitable highlights were found. Try a wider duration range or "
            "check whether the subtitle file contains enough speech."
        )
        return

    st.success(
        f"Found {len(candidates)} candidate clip(s). Edit any draft, then export "
        "one clip or select several for batch export."
    )

    pending = []  # (result_key, job) for every included, valid clip
    duration = ctx["duration"]

    for index, candidate in enumerate(candidates, start=1):

        def key(name, _index=index):
            return f"clip_{run}_{_index}_{name}"

        result_key = f"{run}:{index}"
        defaults = build_metadata(candidate["transcript"], include_shorts=output_format == "shorts")

        with st.container(border=True):
            st.subheader(f"{index}. {candidate['title']}")
            st.caption(
                f"Score {candidate['score']:.1f} · "
                f"{candidate['end'] - candidate['start']:.1f}s suggested"
            )

            include = st.checkbox("Include in batch export", value=True, key=key("include"))

            title = st.text_input("Title", value=defaults["title"], max_chars=100, key=key("title"))
            description = st.text_area(
                "Description", value=defaults["description"], height=110, key=key("description")
            )
            hashtags = st.text_input(
                "Hashtags", value=" ".join(defaults["hashtags"]), key=key("hashtags")
            )

            start_col, end_col = st.columns(2)
            suggested_start = max(0.0, min(float(candidate["start"]), max(0.0, duration - 0.1)))
            suggested_end = max(0.1, min(float(candidate["end"]), duration))

            start = start_col.number_input(
                "Start (seconds)",
                min_value=0.0,
                max_value=max(0.1, duration - 0.1),
                value=suggested_start,
                step=0.5,
                key=key("start"),
            )
            end = end_col.number_input(
                "End (seconds)",
                min_value=0.1,
                max_value=max(0.1, duration),
                value=suggested_end,
                step=0.5,
                key=key("end"),
            )

            with st.expander("Transcript and selection reasons"):
                st.write(candidate["transcript"])
                st.write("**Why it was selected:** " + "; ".join(candidate["reasons"]))

            error = _range_error(start, end)
            if error:
                st.error(error)
            else:
                job = _build_job(
                    ctx["video"],
                    ctx["srt_path"],
                    output_format,
                    reframe_mode,
                    options,
                    candidate,
                    {
                        "start": start,
                        "end": end,
                        "title": title,
                        "description": description,
                        "hashtags": hashtags,
                    },
                )
                if include:
                    pending.append((result_key, job))

                if st.button("Export this clip", key=key("export"), type="primary"):
                    try:
                        with st.spinner(f"Exporting clip {index}…"):
                            results[result_key] = {
                                "ok": _export_job(job, ctx["output_dir"], ctx["metadata_dir"])
                            }
                    except (ClipRenderError, OSError, ValueError) as exc:
                        results[result_key] = {"error": str(exc)}

            _render_result(result_key)

    _render_batch(pending, ctx, results)


def _render_caption_hint(output_format: str) -> None:
    if output_format == "original":
        st.caption("Original dimensions and aspect ratio. Smart framing applies only to Shorts and 16:9.")
    elif output_format == "shorts":
        st.caption("Vertical 1080 × 1920. Smart framing can follow a detected face or person.")
    else:
        st.caption("Landscape 1920 × 1080. Smart framing can adjust the crop vertically.")


def render_smart_clip_finder(*, app_dir, config, videos, subtitle_dir, output_dir, **_):
    _render_header()

    video = render_video_source_picker(
        input_dir=app_dir / config["paths"]["input"],
        videos=videos,
        key_prefix="clip_finder",
    )
    if video is None:
        return

    video = Path(video).resolve()
    subtitle_dir = Path(subtitle_dir).resolve()
    output_dir = Path(output_dir).resolve()
    metadata_dir = (app_dir / config["paths"]["metadata"]).resolve()
    srt_path = subtitle_dir / f"{video.stem}.srt"

    try:
        duration = _probe_duration(str(video), video.stat().st_mtime)
    except (VideoInputError, OSError, ValueError) as error:
        st.error(f"Cannot read this video: {error}")
        return

    if not srt_path.is_file():
        _render_subtitle_generation(video, srt_path, subtitle_dir, config)
        return

    st.success(f"Subtitles ready · {srt_path.name}")

    st.subheader("Clip settings")
    format_choice = st.radio(
        "Where will you publish these clips?",
        options=list(FORMAT_OPTIONS),
        key="clip_finder_output_format",
        help="Shorts: 1080 × 1920. Regular YouTube: 1920 × 1080. Original keeps the source size.",
    )
    output_format = FORMAT_OPTIONS[format_choice]

    framing_choice = st.selectbox(
        "Smart camera framing",
        options=list(FRAMING_OPTIONS),
        index=0,
        key="clip_finder_framing_mode",
        help=(
            "Smart modes sample frames and move the crop smoothly. Auto prefers "
            "faces and falls back to full-body people. Center crop keeps a fixed center crop."
        ),
    )
    reframe_mode = FRAMING_OPTIONS[framing_choice]
    _render_caption_hint(output_format)

    min_duration, max_duration, max_candidates = _render_detection_settings()

    if min_duration >= max_duration:
        st.error("Minimum clip length must be smaller than maximum clip length.")
        return

    if st.button("Find highlights", type="primary", key="clip_finder_find"):
        _run_discovery(video, srt_path, duration, min_duration, max_duration, max_candidates)

    state = st.session_state.get(CANDIDATES_KEY)
    if not state or state["video"] != str(video):
        st.info("Choose your settings and click Find highlights to begin.")
        return

    options = _render_export_options()
    ctx = {
        "config": config,
        "video": video,
        "srt_path": srt_path,
        "output_dir": output_dir,
        "metadata_dir": metadata_dir,
        "duration": duration,
    }
    st.caption(f"Output folder: `{output_dir}`")
    _render_candidates(ctx, output_format, reframe_mode, options)
