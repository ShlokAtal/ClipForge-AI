"""Dashboard page."""
import streamlit as st


def render_dashboard(*, config, videos, inventory_error, subtitle_dir, output_dir, **_):
    st.markdown(
        '<div class="cf-hero"><div class="cf-eyebrow">YOUR VIDEO WORKSPACE</div>'
        '<h1>Make more from<br>every video.</h1><p>Transcribe, refine subtitles, and prepare your content '
        'in one focused workspace. No clutter. Just the tools you need.</p></div>',
        unsafe_allow_html=True,
    )
    exports = (
        sorted(output_dir.glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
        if output_dir.exists() else []
    )
    srts = list(subtitle_dir.glob("*.srt")) if subtitle_dir.exists() else []
    a, b, c, d = st.columns(4)
    a.metric("Source videos", len(videos))
    b.metric("Subtitle files", len(srts))
    c.metric("Exported videos", len(exports))
    d.metric("Batch limit", config["max_batch_size"])
    st.markdown('<div class="cf-section">Workspace</div>', unsafe_allow_html=True)
    columns = st.columns(3)
    cards = [
        ("▣", "Video workspace", "Inspect source media and review technical details."),
        ("CC", "Subtitle studio", "Generate speech subtitles and style your export."),
        ("✂", "Smart Clip Finder", "Find highlights, edit drafts, and batch-export clips."),
    ]
    for column, (icon, title, description) in zip(columns, cards):
        with column:
            st.markdown(
                f'<div class="cf-card"><div class="cf-icon">{icon}</div><h3>{title}</h3><p>{description}</p></div>',
                unsafe_allow_html=True,
            )
    st.markdown('<div class="cf-section">Recent exports</div>', unsafe_allow_html=True)
    if exports:
        for path in exports[:5]:
            st.write(f"🎞️ **{path.name}** · {path.stat().st_size / (1024 * 1024):.1f} MB")
            with path.open("rb") as handle:
                st.download_button(
                    "Download video", handle, file_name=path.name,
                    mime="video/mp4", key=f"dash_{path.name}",
                )
    else:
        st.info("Finished clips and subtitled videos will appear here.")
    if inventory_error:
        st.warning(inventory_error)
    elif not videos:
        st.info(f"Add a supported video to `{config['paths']['input']}` to get started.")
