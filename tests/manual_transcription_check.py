
import sys
from pathlib import Path

# Add the project root so Python can import the core package.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.configuration import load_config
from core.transcription import transcribe_to_srt
from core.video_input import discover_videos, inspect_video


config = load_config(ROOT / "config.json")

input_dir = ROOT / config["paths"]["input"]
output_dir = ROOT / config["paths"]["subtitles"]

videos = discover_videos(input_dir)

if not videos:
    print("No supported videos found in media/input.")
    raise SystemExit(1)

video = videos[0]

print(f"\nSelected video: {video.name}")
print("Inspecting video...")

metadata = inspect_video(video)
print(f"Duration: {metadata['duration_seconds']:.1f} seconds")
print(f"Resolution: {metadata['width']}x{metadata['height']}")

print("\nStarting real AI transcription...")
print("The first run may download the Whisper model.")

result = transcribe_to_srt(
    video_path=video,
    output_dir=output_dir,
    model_name=config["transcription"]["model"],
    device=config["transcription"]["device"],
    compute_type=config["transcription"]["compute_type"],
    skip_existing=False,
)

print("\nTranscription finished!")
print(f"Subtitle file: {result['path']}")
print(f"Language detected: {result['language']}")
print(f"Subtitle segments: {result['segments']}")
