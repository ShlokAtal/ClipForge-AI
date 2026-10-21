"""Application settings and environment diagnostics."""
from pathlib import Path
import streamlit as st


def render_settings(*, app_dir, config, videos, inventory_error, subtitle_dir, output_dir,
                    python_version, package_available, which):
    st.markdown('<div class="cf-eyebrow">SYSTEM / PREFERENCES</div>', unsafe_allow_html=True)
    st.title("Settings")
    st.caption("Current configuration and environment status.")
    first, second, third = st.columns(3)
    first.metric("Transcription model", config["transcription"]["model"])
    second.metric("Device", config["transcription"]["device"])
    third.metric("Batch limit", config["max_batch_size"])

    st.markdown('<div class="cf-section">Environment checks</div>', unsafe_allow_html=True)
    checks = [
        ("Python", python_version.split()[0], bool(python_version)),
        ("Streamlit", "Installed" if package_available("streamlit") else "Missing", package_available("streamlit")),
        ("faster-whisper", "Installed" if package_available("faster_whisper") else "Missing", package_available("faster_whisper")),
    ]
    checks.extend(
        (tool, "Available" if which(tool) else "Missing", bool(which(tool)))
        for tool in ("ffmpeg", "ffprobe", "yt-dlp")
    )
    for label, value, ok in checks:
        st.write(("🟢" if ok else "🟠") + f" **{label}** · {value}")

    st.markdown('<div class="cf-section">Configured folders</div>', unsafe_allow_html=True)
    for key, relative in config["paths"].items():
        st.write(("🟢" if (app_dir / relative).is_dir() else "🟠") + f" **{key.title()}** · `{relative}`")
    st.info("Batch queue management, metadata suggestions, and YouTube upload integration are still planned.")
