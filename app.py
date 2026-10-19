
import shutil
import sys
from importlib.util import find_spec
from pathlib import Path

import streamlit as st

from core.configuration import load_config, prepare_folders
from core.subtitle_burner import SubtitleBurnError, burn_subtitles
from core.transcription import transcribe_to_srt
from core.video_input import (
    VideoInputError,
    discover_videos,
    inspect_video,
)

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"


def package_available(name):
    """Check whether a Python package is available."""
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def format_duration(seconds):
    """Format a duration as minutes and seconds."""
    total_seconds = max(0, int(seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"

    return f"{minutes}:{seconds:02}"


st.set_page_config(
    page_title="ClipForge AI",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 ClipForge AI")
st.caption("Your personal YouTube video assistant")

try:
    config = load_config(CONFIG_PATH)
    prepare_folders(APP_DIR, config)
except (OSError, ValueError, TypeError) as error:
    st.error("ClipForge AI could not load or prepare its configuration.")
    st.code(str(error))
    st.stop()


st.success("Configuration validated. Required folders are ready.")

st.subheader("Project Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Maximum Batch Size", config["max_batch_size"])

with col2:
    st.metric(
        "Transcription Model",
        config["transcription"]["model"],
    )

with col3:
    st.metric(
        "Processing Mode",
        config["processing_mode"].title(),
    )


st.subheader("Environment Status")

python_version = sys.version.split()[0]

if sys.version_info[:3] == (3, 14, 7):
    st.success(f"Python: {python_version} — expected version")
else:
    st.warning(
        f"Python: {python_version} — expected Python 3.14.7"
    )

for package_name, display_name in (
    ("streamlit", "Streamlit"),
    ("faster_whisper", "faster-whisper"),
):
    if package_available(package_name):
        st.success(
            f"{display_name}: Available in this Python environment"
        )
    else:
        st.warning(
            f"{display_name}: Not found in this Python environment"
        )

for tool_name in ("ffmpeg", "ffprobe", "yt-dlp"):
    if shutil.which(tool_name):
        st.success(f"{tool_name}: Available on PATH")
    else:
        st.warning(f"{tool_name}: Not found on PATH")


st.subheader("Configured Folders")

for key, relative_path in config["paths"].items():
    folder = APP_DIR / relative_path

    if folder.is_dir():
        st.write(f"✅ **{key}:** `{relative_path}`")
    else:
        st.warning(f"Folder not available: {relative_path}")


st.divider()
st.header("🎞️ Video Subtitles")
st.write(
    "Select a video from your input folder, generate AI subtitles, "
    "customize their appearance, and permanently burn them into "
    "a new MP4 file."
)

input_dir = APP_DIR / config["paths"]["input"]
subtitle_dir = APP_DIR / config["paths"]["subtitles"]
output_dir = APP_DIR / config["paths"]["clips"]

try:
    videos = discover_videos(input_dir)
except VideoInputError as error:
    videos = []
    st.error(str(error))

if not videos:
    st.info(
        "No supported videos found. Add a video to "
        f"`{config['paths']['input']}` and refresh this page."
    )
else:
    video_options = {
        video.name: video
        for video in videos[:config["max_batch_size"]]
    }

    selected_name = st.selectbox(
        "Choose a video",
        options=list(video_options.keys()),
    )
    selected_video = video_options[selected_name]

    if st.button("Inspect selected video"):
        try:
            metadata = inspect_video(selected_video)

            st.success("Video inspection completed.")

            info_col1, info_col2, info_col3 = st.columns(3)

            with info_col1:
                st.metric(
                    "Duration",
                    format_duration(metadata["duration_seconds"]),
                )

            with info_col2:
                st.metric(
                    "Resolution",
                    f"{metadata['width']} × {metadata['height']}",
                )

            with info_col3:
                st.metric(
                    "Video Codec",
                    metadata["video_codec"],
                )

            st.write(f"Audio codec: {metadata['audio_codec']}")

        except (VideoInputError, OSError, ValueError) as error:
            st.error(f"Video inspection failed: {error}")

    st.divider()
    st.subheader("🎨 Subtitle Customization")

    st.write(
        "Choose how your subtitles should look. These settings apply "
        "when subtitles are burned into the output video."
    )

    font_col1, font_col2 = st.columns(2)

    with font_col1:
        font_name = st.selectbox(
            "Font family",
            options=[
                "Arial",
                "DejaVu Sans",
                "Liberation Sans",
                "Verdana",
                "Tahoma",
            ],
            index=0,
        )

        font_size = st.slider(
            "Font size",
            min_value=16,
            max_value=48,
            value=28,
            step=2,
        )

        font_color = st.color_picker(
            "Subtitle text color",
            value="#FFFFFF",
        )

        bold = st.checkbox(
            "Bold subtitles",
            value=True,
        )

    with font_col2:
        alignment = st.selectbox(
            "Subtitle position",
            options=[
                "Bottom Center",
                "Middle Center",
                "Top Center",
                "Bottom Left",
                "Bottom Right",
                "Top Left",
                "Top Right",
            ],
            index=0,
        )

        outline_color = st.color_picker(
            "Text outline color",
            value="#000000",
        )

        outline_thickness = st.slider(
            "Outline thickness",
            min_value=0,
            max_value=5,
            value=2,
        )

    st.markdown("**Subtitle background**")

    background_col1, background_col2 = st.columns(2)

    with background_col1:
        background_mode = st.selectbox(
            "Background style",
            options=[
                "Transparent",
                "Semi-transparent box",
                "Solid box",
            ],
            index=0,
        )

    with background_col2:
        background_color = st.color_picker(
            "Background color",
            value="#000000",
            disabled=(background_mode == "Transparent"),
        )

    margin_col1, margin_col2 = st.columns(2)

    with margin_col1:
        vertical_margin = st.slider(
            "Vertical margin",
            min_value=0,
            max_value=300,
            value=40,
            step=5,
            help=(
                "Controls the distance from the relevant video edge. "
                "The effect depends on the selected subtitle position."
            ),
        )

    with margin_col2:
        crf = st.slider(
            "Output quality",
            min_value=18,
            max_value=28,
            value=23,
            help=(
                "Lower values generally mean higher quality and larger "
                "files. Higher values generally mean smaller files."
            ),
        )

    st.markdown("**Subtitle timing**")

    timing_offset_ms = st.slider(
        "Timing adjustment (milliseconds)",
        min_value=-2000,
        max_value=2000,
        value=int(
            config["transcription"].get("timing_offset_ms", 0)
        ),
        step=25,
        help=(
            "Negative values move subtitles earlier. Positive values "
            "move them later. Start with 0 and adjust in small steps."
        ),
    )

    preview_weight = "700" if bold else "400"
    preview_outline = (
        f"2px {outline_color}"
        if outline_thickness > 0
        else "none"
    )

    preview_css = (
        f"color: {font_color};"
        f"font-family: '{font_name}', sans-serif;"
        f"font-size: {min(font_size, 36)}px;"
        f"font-weight: {preview_weight};"
        f"text-shadow: {preview_outline};"
    )

    if background_mode == "Semi-transparent box":
        preview_background = (
            f"background: {background_color}B3;"
            "padding: 6px 12px;"
            "border-radius: 4px;"
        )
    elif background_mode == "Solid box":
        preview_background = (
            f"background: {background_color};"
            "padding: 6px 12px;"
            "border-radius: 4px;"
        )
    else:
        preview_background = ""

    st.markdown("**Approximate style preview**")

    st.markdown(
        f"""
        <div style="
            background: #343434;
            min-height: 120px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
            box-sizing: border-box;
        ">
            <span style="
                {preview_css}
                {preview_background}
                text-align: center;
            ">
                Your subtitles will look like this
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "The preview is approximate. The rendered video uses FFmpeg's "
        "subtitle renderer, so font availability and exact appearance "
        "may differ."
    )

    st.divider()

    regenerate_subtitles = st.checkbox(
        "Regenerate subtitles (ignore the existing SRT file)",
        value=False,
        help=(
            "Enable this to generate fresh subtitles. If disabled and "
            "an existing subtitle file is available, it may be reused "
            "according to your configuration."
        ),
    )

    st.caption(
        "The first transcription may take longer while the AI model loads."
    )

    if st.button(
        "Generate subtitles and create subtitled video",
        type="primary",
    ):
        srt_path = subtitle_dir / f"{selected_video.stem}.srt"

        try:
            with st.status(
                "Inspecting the selected video...",
                expanded=True,
            ) as status:
                metadata = inspect_video(selected_video)

                st.write(
                    "Duration: "
                    f"{format_duration(metadata['duration_seconds'])}"
                )
                st.write(
                    f"Resolution: {metadata['width']} × "
                    f"{metadata['height']}"
                )

                st.write("Generating or loading AI subtitles...")

                transcription_result = transcribe_to_srt(
                    video_path=selected_video,
                    output_dir=subtitle_dir,
                    model_name=config["transcription"]["model"],
                    device=config["transcription"]["device"],
                    compute_type=config["transcription"]["compute_type"],
                    skip_existing=(
                        config.get("skip_existing_outputs", True)
                        and not regenerate_subtitles
                    ),
                    timing_offset_ms=timing_offset_ms,
                )

                if transcription_result["skipped"]:
                    st.write("Using existing subtitle file.")
                else:
                    st.write(
                        "Subtitle segments: "
                        f"{transcription_result['segments']}"
                    )

                st.write(f"Subtitle file: {srt_path}")
                st.write("Burning customized subtitles into the video...")

                burn_result = burn_subtitles(
                    video_path=selected_video,
                    subtitle_path=srt_path,
                    output_dir=output_dir,
                    overwrite=True,
                    crf=crf,
                    preset="veryfast",
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

                status.update(
                    label="Subtitle processing completed!",
                    state="complete",
                    expanded=False,
                )

            st.success("Your customized subtitled video is ready!")

            st.write(f"**Output video:** `{burn_result['path']}`")
            st.write(
                f"**Output size:** {burn_result['size_bytes']:,} bytes"
            )

            with Path(burn_result["path"]).open("rb") as video_file:
                st.download_button(
                    label="Download subtitled video",
                    data=video_file,
                    file_name=Path(burn_result["path"]).name,
                    mime="video/mp4",
                    key=f"download_{selected_video.name}",
                )

        except (
            VideoInputError,
            SubtitleBurnError,
            OSError,
            ValueError,
            RuntimeError,
            TypeError,
        ) as error:
            st.error(f"Video processing failed: {error}")


st.divider()
st.subheader("Features")

features = [
    "AI transcription and automatic subtitle generation",
    "Customizable subtitle font, color, outline, background, and position",
    "Burn subtitles permanently into videos",
    "Smart Clip Finder — planned",
    "Batch processing for up to 10 videos — planned",
    "Title, description, and hashtag suggestions — planned",
    "Bulk downloads for authorized videos — planned",
    "YouTube upload assistance with review before publishing — planned",
]

for feature in features:
    st.markdown(f"- {feature}")

st.caption(
    "ClipForge AI is under active development. "
    "Features marked planned are not yet implemented."
)