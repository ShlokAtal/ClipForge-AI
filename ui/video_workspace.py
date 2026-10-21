"""Video inspection page."""
import streamlit as st
from core.video_input import VideoInputError, inspect_video
from ui.video_source import render_video_source_picker


def _format_duration(seconds):
    total = max(0, int(seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def render_video_workspace(*, app_dir, config, videos, **_):
    st.markdown('<div class="cf-eyebrow">WORKSPACE / MEDIA</div>', unsafe_allow_html=True)
    st.title("Video workspace")
    st.caption("Choose a source video and inspect its media properties.")
    video = render_video_source_picker(
        input_dir=app_dir / config["paths"]["input"], videos=videos, key_prefix="workspace"
    )
    if video is None:
        return
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown('<div class="cf-card"><h3>Selected media</h3><p>Preview your source before processing.</p></div>', unsafe_allow_html=True)
        st.write(f"**{video.name}** · {video.stat().st_size / (1024 * 1024):.2f} MB")
        st.video(str(video))
    with right:
        if st.button("Inspect video", type="primary"):
            try:
                st.session_state["inspected_video"] = str(video)
                st.session_state["video_metadata"] = inspect_video(video)
            except (VideoInputError, OSError, ValueError) as error:
                st.error(f"Inspection failed: {error}")
        metadata = st.session_state.get("video_metadata")
        if metadata and st.session_state.get("inspected_video") == str(video):
            x, y = st.columns(2)
            x.metric("Duration", _format_duration(metadata["duration_seconds"]))
            y.metric("Resolution", f'{metadata["width"]} × {metadata["height"]}')
            st.write(f'**Video codec:** {metadata["video_codec"]}')
            st.write(f'**Audio codec:** {metadata["audio_codec"]}')
        else:
            st.info("Select Inspect video to load metadata from ffprobe.")
