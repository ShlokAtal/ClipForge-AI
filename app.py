"""ClipForge AI application entry point.

Keep this file small: shared setup and navigation only.
Individual pages live in the ui/ package.
"""
import shutil
import sys
from importlib.util import find_spec
from pathlib import Path

import streamlit as st

from core.configuration import load_config, prepare_folders
from core.video_input import VideoInputError, discover_videos

from ui.dashboard import render_dashboard
from ui.video_workspace import render_video_workspace
from ui.subtitle_studio import render_subtitle_studio
from ui.smart_clip_finder import render_smart_clip_finder
from ui.settings import render_settings

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

st.set_page_config(page_title="ClipForge AI", page_icon="🎬", layout="wide")

st.markdown("""
<style>
:root { --bg:#0b1020; --panel:#111a2b; --border:#26334b; --text:#edf2ff; --muted:#9ba9c3; --accent:#7185ff; }
.stApp { background:var(--bg); color:var(--text); }
[data-testid="stHeader"] { background:rgba(11,16,32,.94); }
[data-testid="stSidebar"] { background:#0d1526; border-right:1px solid var(--border); }
.cf-brand {display:flex;gap:12px;align-items:center;padding:5px 3px 24px}
.cf-mark {width:42px;height:42px;border-radius:13px;background:linear-gradient(145deg,#7185ff,#8d6cf4);display:flex;align-items:center;justify-content:center;color:white;font-size:22px;font-weight:800}
.cf-brand-name {font-size:20px;font-weight:750;letter-spacing:-.5px;color:#f3f5ff}
.cf-brand-tag,.cf-muted {font-size:12px;color:var(--muted)}
.cf-hero {background:radial-gradient(ellipse at 80% 20%,rgba(101,115,255,.2),transparent 38%),linear-gradient(125deg,#17243b,#10192b 65%,#171d39);border:1px solid var(--border);border-radius:18px;padding:28px 30px;margin-bottom:18px}
.cf-eyebrow {color:#aebcff;text-transform:uppercase;letter-spacing:1.6px;font-size:11px;font-weight:700;margin-bottom:8px}
.cf-hero h1 {font-size:34px;line-height:1.15;letter-spacing:-1.2px;color:#f5f7ff;margin:0 0 12px}
.cf-hero p {color:#b3bfd6;font-size:14px;margin:0;max-width:650px}
.cf-card {background:var(--panel);border:1px solid var(--border);border-radius:15px;padding:18px;height:100%;min-height:130px}
.cf-card h3 {font-size:16px;color:#eef2ff;margin:0 0 8px}
.cf-card p {font-size:13px;color:var(--muted);line-height:1.55;margin:0}
.cf-icon {width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:#222d4a;color:#aab5ff;font-size:17px;margin-bottom:13px}
.cf-section {font-size:20px;font-weight:700;color:#f0f3ff;margin:24px 0 12px}
.cf-pill {display:inline-block;background:#102b2a;border:1px solid #1f5147;color:#7ce4bf;border-radius:999px;padding:5px 10px;font-size:12px}
div.stButton>button,div.stDownloadButton>button {border-radius:10px;border:1px solid #33415f;min-height:42px;font-weight:650}
div.stButton>button[kind="primary"] {background:linear-gradient(110deg,#6679f7,#7768ec);border:0;color:white}
[data-testid="stMetric"] {background:var(--panel);border:1px solid var(--border);border-radius:13px;padding:14px 16px}
[data-testid="stMetricLabel"] {color:var(--muted)} [data-testid="stMetricValue"] {color:#f3f5ff}
hr {border-color:var(--border)} footer {visibility:hidden}
</style>
""", unsafe_allow_html=True)

def package_available(name: str) -> bool:
    """Return whether an importable package is installed."""
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def main() -> None:
    """Load configuration, prepare shared paths, and show the selected page."""
    try:
        config = load_config(CONFIG_PATH)
        prepare_folders(APP_DIR, config)
    except (OSError, ValueError, TypeError) as error:
        st.error("ClipForge AI could not load or prepare its configuration.")
        st.code(str(error))
        st.stop()

    input_dir = APP_DIR / config["paths"]["input"]
    subtitle_dir = APP_DIR / config["paths"]["subtitles"]
    output_dir = APP_DIR / config["paths"]["clips"]

    try:
        videos = discover_videos(input_dir)
        inventory_error = None
    except VideoInputError as error:
        videos, inventory_error = [], str(error)

    with st.sidebar:
        st.markdown(
            '<div class="cf-brand"><div class="cf-mark">▶</div>'
            '<div><div class="cf-brand-name">ClipForge AI</div>'
            '<div class="cf-brand-tag">A focused video workspace</div></div></div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "WORKSPACE",
            ["Dashboard", "Video workspace", "Subtitle studio", "Smart Clip Finder", "Settings"],
        )
        st.divider()
        st.markdown('<span class="cf-pill">● Local workspace</span>', unsafe_allow_html=True)
        st.caption(f"Batch limit: {config['max_batch_size']} · Sequential processing")
        st.caption("Local-first · No database")

    common = {
        "app_dir": APP_DIR,
        "config": config,
        "videos": videos,
        "inventory_error": inventory_error,
        "subtitle_dir": subtitle_dir,
        "output_dir": output_dir,
    }

    if page == "Dashboard":
        render_dashboard(**common)
    elif page == "Video workspace":
        render_video_workspace(**common)
    elif page == "Subtitle studio":
        render_subtitle_studio(**common)
    elif page == "Smart Clip Finder":
        render_smart_clip_finder(**common)
    else:
        render_settings(
            **common,
            python_version=sys.version,
            package_available=package_available,
            which=shutil.which,
        )

    st.divider()
    st.caption("ClipForge AI · Local-first video tools · Features are clearly marked until implemented.")


if __name__ == "__main__":
    main()
