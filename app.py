import shutil
import sys
from importlib.util import find_spec
from pathlib import Path

import streamlit as st

from core.configuration import load_config, prepare_folders
from core.subtitle_burner import SubtitleBurnError, burn_subtitles
from core.transcription import transcribe_to_srt
from core.video_input import VideoInputError, discover_videos, inspect_video

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


def package_available(name):
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def format_duration(seconds):
    total = max(0, int(seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


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
    st.markdown('<div class="cf-brand"><div class="cf-mark">▶</div><div><div class="cf-brand-name">ClipForge AI</div><div class="cf-brand-tag">A focused video workspace</div></div></div>', unsafe_allow_html=True)
    page = st.radio("WORKSPACE", ["Dashboard", "Video workspace", "Subtitle studio", "Settings"])
    st.divider()
    st.markdown('<span class="cf-pill">● Local workspace</span>', unsafe_allow_html=True)
    st.caption(f"Batch limit: {config['max_batch_size']} · Sequential processing")
    st.caption("Local-first · No database")

if page == "Dashboard":
    st.markdown('<div class="cf-hero"><div class="cf-eyebrow">YOUR VIDEO WORKSPACE</div><h1>Make more from<br>every video.</h1><p>Transcribe, refine subtitles, and prepare your content in one focused workspace. No clutter. Just the tools you need.</p></div>', unsafe_allow_html=True)
    subtitled = list(output_dir.glob("*_subtitled.mp4")) if output_dir.exists() else []
    srts = list(subtitle_dir.glob("*.srt")) if subtitle_dir.exists() else []
    a,b,c,d = st.columns(4)
    a.metric("Videos available", len(videos))
    b.metric("Subtitle files", len(srts))
    c.metric("Subtitled exports", len(subtitled))
    d.metric("Batch limit", config["max_batch_size"])
    st.markdown('<div class="cf-section">Workspace</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    cards = [
        ("▣","Video workspace","Inspect source media and review technical details."),
        ("CC","Subtitle studio","Generate speech subtitles and style your export."),
        ("⚙","System health","Check the tools and packages used by the backend."),
    ]
    for col,(icon,title,description) in zip(cols,cards):
        with col:
            st.markdown(f'<div class="cf-card"><div class="cf-icon">{icon}</div><h3>{title}</h3><p>{description}</p></div>',unsafe_allow_html=True)
    st.markdown('<div class="cf-section">Recent exports</div>', unsafe_allow_html=True)
    if subtitled:
        for path in sorted(subtitled,key=lambda p:p.stat().st_mtime,reverse=True)[:5]:
            st.write(f"🎞️ **{path.name}** · {path.stat().st_size/(1024*1024):.1f} MB")
            with path.open("rb") as handle:
                st.download_button("Download video",handle,file_name=path.name,mime="video/mp4",key=f"dash_{path.name}")
    else:
        st.info("Your finished exports will appear here after you create a subtitled video.")
    if inventory_error:
        st.warning(inventory_error)
    elif not videos:
        st.info(f"Add a supported video to `{config['paths']['input']}` to get started.")

elif page == "Video workspace":
    st.markdown('<div class="cf-eyebrow">WORKSPACE / MEDIA</div>',unsafe_allow_html=True)
    st.title("Video workspace")
    st.caption("Choose a source video and inspect its media properties.")
    if not videos:
        st.info(f"Copy a supported video into `{config['paths']['input']}` and refresh this page.")
    else:
        options = {p.name:p for p in videos}
        name = st.selectbox("Source video",list(options),key="workspace_video")
        video = options[name]
        left,right = st.columns([1.2,1])
        with left:
            st.markdown('<div class="cf-card"><h3>Selected media</h3><p>Preview your source before processing.</p></div>',unsafe_allow_html=True)
            st.write(f"**{video.name}** · {video.stat().st_size/(1024*1024):.2f} MB")
            st.video(str(video))
        with right:
            if st.button("Inspect video",type="primary"):
                try:
                    st.session_state["inspected_video"] = str(video)
                    st.session_state["video_metadata"] = inspect_video(video)
                except (VideoInputError,OSError,ValueError) as error:
                    st.error(f"Inspection failed: {error}")
            meta = st.session_state.get("video_metadata")
            if meta and st.session_state.get("inspected_video")==str(video):
                x,y = st.columns(2)
                x.metric("Duration",format_duration(meta["duration_seconds"]))
                y.metric("Resolution",f'{meta["width"]} × {meta["height"]}')
                st.write(f'**Video codec:** {meta["video_codec"]}')
                st.write(f'**Audio codec:** {meta["audio_codec"]}')
            else:
                st.info("Select Inspect video to load metadata from ffprobe.")

elif page == "Subtitle studio":
    st.markdown('<div class="cf-eyebrow">CREATE / SUBTITLES</div>',unsafe_allow_html=True)
    st.title("Subtitle studio")
    st.caption("Generate AI subtitles, tune their appearance, and export a new MP4.")
    if not videos:
        st.info(f"Copy a supported video into `{config['paths']['input']}` and refresh this page.")
    else:
        options = {p.name:p for p in videos}
        name = st.selectbox("Source video",list(options),key="subtitle_video")
        video = options[name]
        left,right = st.columns(2)
        with left:
            st.markdown('<div class="cf-section">Typography</div>',unsafe_allow_html=True)
            font_name = st.selectbox("Font",["Arial","DejaVu Sans","Liberation Sans","Verdana","Tahoma"])
            font_size = st.slider("Font size",16,48,28,2)
            font_color = st.color_picker("Text color","#FFFFFF")
            bold = st.checkbox("Bold subtitles",True)
            outline_color = st.color_picker("Outline color","#000000")
            outline_thickness = st.slider("Outline thickness",0,5,2)
        with right:
            st.markdown('<div class="cf-section">Placement & output</div>',unsafe_allow_html=True)
            alignment = st.selectbox("Position",["Bottom Center","Middle Center","Top Center","Bottom Left","Bottom Right","Top Left","Top Right"])
            background_mode = st.selectbox("Background",["Transparent","Semi-transparent box","Solid box"])
            background_color = st.color_picker("Background color","#000000",disabled=background_mode=="Transparent")
            vertical_margin = st.slider("Vertical margin",0,300,40,5)
            crf = st.slider("Output quality · lower is higher quality",18,28,23)
        timing_offset_ms = st.slider("Subtitle timing adjustment (milliseconds)",-2000,2000,int(config["transcription"].get("timing_offset_ms",0)),25,help="Negative values move subtitles earlier; positive values move them later.")
        preview_bg = "transparent" if background_mode=="Transparent" else (f"{background_color}B3" if background_mode=="Semi-transparent box" else background_color)
        st.markdown(f'<div style="background:#202b40;border:1px solid #35425e;border-radius:12px;padding:24px;text-align:center;color:{font_color};font-family:{font_name},sans-serif;font-size:{min(font_size,36)}px;font-weight:{"700" if bold else "400"};text-shadow:0 1px 3px {outline_color};"><span style="background:{preview_bg};padding:5px 10px;border-radius:5px">Your subtitles will look like this</span></div>',unsafe_allow_html=True)
        st.caption("Approximate preview; FFmpeg rendering and installed fonts may differ.")
        regenerate = st.checkbox("Regenerate subtitles even if an SRT already exists",False)
        st.caption(f"Model: {config['transcription']['model']} · Device: {config['transcription']['device']} · Compute: {config['transcription']['compute_type']}")
        if st.button("Generate subtitles & export video",type="primary"):
            srt_path = subtitle_dir / f"{video.stem}.srt"
            try:
                with st.status("Processing video…",expanded=True) as status:
                    meta = inspect_video(video)
                    st.write(f"Validated · {format_duration(meta['duration_seconds'])} · {meta['width']} × {meta['height']}")
                    transcription = transcribe_to_srt(video_path=video,output_dir=subtitle_dir,model_name=config["transcription"]["model"],device=config["transcription"]["device"],compute_type=config["transcription"]["compute_type"],skip_existing=config.get("skip_existing_outputs",True) and not regenerate,timing_offset_ms=timing_offset_ms)
                    st.write("Using existing SRT." if transcription["skipped"] else f"Transcription complete · {transcription['segments']} segments")
                    st.write("Burning subtitles into a new MP4…")
                    result = burn_subtitles(video_path=video,subtitle_path=srt_path,output_dir=output_dir,overwrite=True,crf=crf,preset="veryfast",font_name=font_name,font_size=font_size,font_color=font_color,outline_color=outline_color,outline_thickness=outline_thickness,background_mode=background_mode,background_color=background_color,alignment=alignment,vertical_margin=vertical_margin,bold=bold)
                    status.update(label="Export completed",state="complete",expanded=False)
                st.success("Your subtitled video is ready.")
                st.write(f"**Output:** `{result['path']}` · {result['size_bytes']:,} bytes")
                st.write(f"**Subtitles:** `{transcription['path']}`")
                with Path(result["path"]).open("rb") as handle:
                    st.download_button("Download subtitled MP4",handle,file_name=Path(result["path"]).name,mime="video/mp4",key=f"mp4_{video.name}")
                with Path(transcription["path"]).open("rb") as handle:
                    st.download_button("Download SRT subtitles",handle,file_name=Path(transcription["path"]).name,mime="application/x-subrip",key=f"srt_{video.name}")
            except (VideoInputError,SubtitleBurnError,OSError,ValueError,RuntimeError,TypeError) as error:
                st.error(f"Processing failed: {error}")

else:
    st.markdown('<div class="cf-eyebrow">SYSTEM / PREFERENCES</div>',unsafe_allow_html=True)
    st.title("Settings")
    st.caption("Current configuration and environment status.")
    a,b,c = st.columns(3)
    a.metric("Transcription model",config["transcription"]["model"])
    b.metric("Device",config["transcription"]["device"])
    c.metric("Batch limit",config["max_batch_size"])
    st.markdown('<div class="cf-section">Environment checks</div>',unsafe_allow_html=True)
    checks = [("Python",sys.version.split()[0],sys.version_info[:3]==(3,14,7)),("Streamlit","Installed" if package_available("streamlit") else "Missing",package_available("streamlit")),("faster-whisper","Installed" if package_available("faster_whisper") else "Missing",package_available("faster_whisper"))]
    checks += [(tool,"Available" if shutil.which(tool) else "Missing",bool(shutil.which(tool))) for tool in ("ffmpeg","ffprobe","yt-dlp")]
    for label,value,ok in checks:
        st.write(("🟢" if ok else "🟠")+f" **{label}** · {value}")
    st.markdown('<div class="cf-section">Configured folders</div>',unsafe_allow_html=True)
    for key,relative in config["paths"].items():
        st.write(("🟢" if (APP_DIR/relative).is_dir() else "🟠")+f" **{key.title()}** · `{relative}`")
    st.info("Smart Clip Finder, batch queue management, metadata suggestions, and YouTube upload integration remain planned and are not presented as working controls.")

st.divider()
st.caption("ClipForge AI · Local-first video tools · Planned features are clearly marked until implemented.")
