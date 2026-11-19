"""Shared, cached speech-recognition model for the Streamlit UI.

Loading a Whisper model takes seconds and a large model uses significant
memory, so the model is loaded once per settings combination and reused.
"""

import streamlit as st


@st.cache_resource(show_spinner="Loading speech model…")
def get_whisper_model(model_name: str, device: str, compute_type: str):
    """Return a cached faster-whisper model for the given settings."""
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device=device, compute_type=compute_type)
