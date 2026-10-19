import shutil
import sys
from importlib.util import find_spec
from pathlib import Path

import streamlit as st

from core.configuration import load_config, prepare_folders


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

def package_available(name):

    try:
        return find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


st.set_page_config(
    page_title="ClipForge AI",
    page_icon="ðŸŽ¬",
    layout="wide",
)

st.title("ðŸŽ¬ ClipForge AI")
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
    st.metric("Transcription Model", config["transcription"]["model"])

with col3:
    st.metric("Processing Mode", config["processing_mode"].title())

st.subheader("Environment Status")

python_version = sys.version.split()[0]
expected_version = sys.version_info[:3] == (3, 14, 7)

if expected_version:
    st.success(f"Python: {python_version} â€” expected version")
else:
    st.warning(
        f"Python: {python_version} â€” expected Python 3.14.7"
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

for tool_name in ("ffmpeg", "yt-dlp"):
    if shutil.which(tool_name):
        st.success(f"{tool_name}: Available on PATH")
    else:
        st.warning(f"{tool_name}: Not found on PATH")

st.subheader("Configured Folders")

for key, relative_path in config["paths"].items():
    folder = APP_DIR / relative_path

    if folder.is_dir():
        st.write(f"âœ… **{key}:** `{relative_path}`")
    else:
        st.warning(f"Folder not available: {relative_path}")


st.subheader("Features")

features = [
    "Video transcription and automatic subtitles",
    "Smart Clip Finder",
    "Batch processing for up to 10 videos",
    "Title, description, and hashtag suggestions",
    "Bulk downloads for authorized videos",
    "YouTube upload assistance with review before publishing",
]

for feature in features:
    st.markdown(f"- {feature}")

st.info(
    "This is the ClipForge AI foundation dashboard. "
    "Video-processing features will be added and tested in later phases."
)
