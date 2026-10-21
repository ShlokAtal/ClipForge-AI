
"""Video source picker for uploads, existing files, and YouTube downloads."""

from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse
import streamlit as st


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
DOWNLOAD_TIMEOUT_HOURS = 3


def _is_supported_video(path: Path) -> bool:
    """Return True when path points to a supported video file."""
    try:
        return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    except OSError:
        return False


def _valid_youtube_url(url: str) -> bool:
    """Validate a YouTube URL before passing it to yt-dlp."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        return (
            parsed.scheme in {"http", "https"}
            and (
                host in {
                    "youtube.com",
                    "www.youtube.com",
                    "m.youtube.com",
                    "music.youtube.com",
                    "youtu.be",
                    "www.youtu.be",
                }
                or host.endswith(".youtube.com")
            )
        )
    except ValueError:
        return False


def _unique_upload_path(input_dir: Path, filename: str) -> Path:
    """Create a unique destination path without overwriting another file."""
    destination = input_dir / Path(filename).name

    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    counter = 1

    while True:
        candidate = input_dir / f"{stem}_uploaded_{counter}{suffix}"

        if not candidate.exists():
            return candidate

        counter += 1


def _find_downloaded_video(
    stdout: str,
    stderr: str,
    input_dir: Path,
    files_before_download: dict[str, tuple[int, int]],
) -> Path | None:
    """
    Find the downloaded video.

    Prefer paths explicitly reported by yt-dlp. If those are unavailable,
    check files created or modified during this download rather than
    selecting an unrelated older video.
    """
    reported_paths = []

    for output in (stdout, stderr):
        for line in reversed(output.splitlines()):
            candidate_text = line.strip().strip('"')

            if not candidate_text:
                continue

            candidate = Path(candidate_text)

            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate

            if _is_supported_video(candidate):
                resolved = candidate.resolve()

                if resolved not in reported_paths:
                    reported_paths.append(resolved)

    resolved_input_dir = input_dir.resolve()

    for candidate in reported_paths:
        try:
            candidate.relative_to(resolved_input_dir)
            return candidate
        except ValueError:
            continue

    changed_videos = []

    try:
        for candidate in input_dir.iterdir():
            if not _is_supported_video(candidate):
                continue

            try:
                stat = candidate.stat()
                fingerprint = (stat.st_size, stat.st_mtime_ns)
                previous = files_before_download.get(candidate.name)

                if previous != fingerprint and stat.st_size > 0:
                    changed_videos.append(candidate.resolve())

            except OSError:
                continue

    except OSError:
        return None

    if not changed_videos:
        return None

    try:
        return max(
            changed_videos,
            key=lambda path: path.stat().st_mtime_ns,
        )
    except OSError:
        return None


def render_video_source_picker(*, input_dir: Path, videos, key_prefix: str):
    """Render the video source picker and return the selected video path."""
    input_dir = Path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    selected_key = f"{key_prefix}_selected_download"
    message_key = f"{key_prefix}_download_message"

    st.markdown("#### Choose a video source")

    mode = st.radio(
        "Video source",
        ["Existing video", "Browse this PC", "YouTube URL"],
        horizontal=True,
        key=f"{key_prefix}_source_mode",
    )

    if mode == "Browse this PC":
        uploaded = st.file_uploader(
            "Browse for a video file",
            type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
            key=f"{key_prefix}_file_upload",
            help="The selected file will be copied into media/input.",
        )

        if uploaded is None:
            st.info("Choose a video file to continue.")
            return None

        try:
            data = uploaded.getvalue()
            original_path = input_dir / Path(uploaded.name).name

            if original_path.exists():
                try:
                    same_file = original_path.read_bytes() == data
                except OSError:
                    same_file = False

                destination = (
                    original_path
                    if same_file
                    else _unique_upload_path(input_dir, uploaded.name)
                )
            else:
                destination = original_path

            if not destination.exists():
                destination.write_bytes(data)

            st.session_state[selected_key] = str(destination.resolve())
            st.success(f"Video ready: {destination.name}")

            return destination

        except OSError as exc:
            st.error(f"Could not save the selected video: {exc}")
            return None

    if mode == "YouTube URL":
        url = st.text_input(
            "YouTube video URL",
            placeholder="https://www.youtube.com/watch?v=...",
            key=f"{key_prefix}_youtube_url",
        ).strip()

        if st.button(
            "Download video",
            type="primary",
            key=f"{key_prefix}_youtube_download",
        ):
            if not _valid_youtube_url(url):
                st.error(
                    "Enter a valid YouTube URL from youtube.com or youtu.be."
                )
                return None

            yt_dlp = shutil.which("yt-dlp")

            if not yt_dlp:
                st.error(
                    "yt-dlp was not found on PATH. Check the installation "
                    "and restart ClipForge AI."
                )
                return None
            
            files_before_download = {}

            try:
                for path in input_dir.iterdir():
                    if _is_supported_video(path):
                        try:
                            stat = path.stat()
                            files_before_download[path.name] = (
                                stat.st_size,
                                stat.st_mtime_ns,
                            )
                        except OSError:
                            pass
            except OSError as exc:
                st.error(f"Could not inspect the input folder: {exc}")
                return None

            command = [
                yt_dlp,
                "--no-playlist",
                "--no-warnings",
                "--no-progress",
                "--print",
                "after_move:filepath",
                "-f",
                "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                "--merge-output-format",
                "mp4",
                "-o",
                str(input_dir / "%(title).100B_%(id)s.%(ext)s"),
                url,
            ]

            try:
                with st.spinner(
                    f"Downloading video. The timeout is "
                    f"{DOWNLOAD_TIMEOUT_HOURS} hours; long videos may take a while."
                ):
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=DOWNLOAD_TIMEOUT_HOURS * 60 * 60,
                        check=False,
                    )

                if result.returncode != 0:
                    detail = (
                        result.stderr
                        or result.stdout
                        or "Unknown yt-dlp error."
                    ).strip()

                    st.error(f"YouTube download failed:\n\n{detail[-2500:]}")
                    return None

                downloaded_path = _find_downloaded_video(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    input_dir=input_dir,
                    files_before_download=files_before_download,
                )

                if downloaded_path is None:
                    st.error(
                        "yt-dlp finished, but ClipForge AI could not identify "
                        "the downloaded video. Check media/input and the "
                        "download output. Existing files have not been deleted."
                    )

                    with st.expander("Download diagnostic output"):
                        st.text("yt-dlp stdout:")
                        st.code(result.stdout[-4000:] or "(empty)")
                        st.text("yt-dlp stderr:")
                        st.code(result.stderr[-4000:] or "(empty)")

                    return None

                st.session_state[selected_key] = str(downloaded_path)
                st.session_state[message_key] = (
                    f"Download complete: {downloaded_path.name}"
                )

                st.rerun()

            except subprocess.TimeoutExpired:
                st.error(
                    f"The download exceeded the {DOWNLOAD_TIMEOUT_HOURS}-hour "
                    "timeout. Check the connection, available disk space, and "
                    "whether yt-dlp is still making progress."
                )
                return None

            except (OSError, ValueError) as exc:
                st.error(f"Could not download the video: {exc}")
                return None

        message = st.session_state.get(message_key)

        if message:
            st.success(message)

        downloaded = st.session_state.get(selected_key)

        if downloaded:
            downloaded_path = Path(downloaded)

            if _is_supported_video(downloaded_path):
                st.caption(f"Selected video: {downloaded_path.name}")
                return downloaded_path

            st.session_state.pop(selected_key, None)

        st.info("Paste a YouTube URL and click Download video.")
        return None

    options = {}

    for item in videos:
        path = Path(item)

        if _is_supported_video(path):
            options[path.name] = path

    downloaded = st.session_state.get(selected_key)

    if downloaded:
        downloaded_path = Path(downloaded)

        if _is_supported_video(downloaded_path):
            options[downloaded_path.name] = downloaded_path
        else:
            st.session_state.pop(selected_key, None)

    if not options:
        st.info(
            "No videos found yet. Choose Browse this PC or YouTube URL above."
        )
        return None

    names = list(options)
    select_key = f"{key_prefix}_existing_select"
    previous_selection = st.session_state.get(select_key)

    if previous_selection in options:
        default_index = names.index(previous_selection)
    else:
        downloaded = st.session_state.get(selected_key)
        downloaded_name = Path(downloaded).name if downloaded else None

        default_index = (
            names.index(downloaded_name)
            if downloaded_name in options
            else 0
        )

    selected = st.selectbox(
        "Source video",
        names,
        index=default_index,
        key=select_key,
    )

    return options[selected]