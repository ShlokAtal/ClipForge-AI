import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.configuration import load_config
from core.subtitle_burner import burn_subtitles
from core.video_input import discover_videos


config = load_config(ROOT / "config.json")

input_dir = ROOT / config["paths"]["input"]
subtitle_dir = ROOT / config["paths"]["subtitles"]
output_dir = ROOT / "output" / "clips"

videos = discover_videos(input_dir)

if not videos:
    print("No supported videos found in media/input.")
    raise SystemExit(1)

video = next(
    (
        item for item in videos
        if item.name.lower() == "test_demo.mp4"
    ),
    None,
)

if video is None:
    print("Could not find test_demo.mp4 in media/input.")
    raise SystemExit(1)

subtitle = subtitle_dir / f"{video.stem}.srt"

if not subtitle.is_file():
    print(f"Subtitle file not found: {subtitle}")
    print("Run the transcription test first.")
    raise SystemExit(1)

print(f"\nInput video: {video}")
print(f"Subtitle file: {subtitle}")
print(f"Output folder: {output_dir}")
print("\nBurning subtitles into the video...")
print("This may take a little time.")

try:
    result = burn_subtitles(
        video_path=video,
        subtitle_path=subtitle,
        output_dir=output_dir,
        crf=23,
        preset="veryfast",
    )
except Exception as error:
    print(f"\nSubtitle burning failed: {error}")
    raise SystemExit(1)

print("\nSubtitle burning completed successfully!")
print(f"Output video: {result['path']}")
print(f"Output size: {result['size_bytes']:,} bytes")