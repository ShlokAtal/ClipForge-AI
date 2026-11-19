# ClipForge AI

ClipForge AI is a local-first video preparation assistant for Windows. It is
built with Python and Streamlit and helps you turn long videos into short,
ready-to-publish clips with subtitles, draft metadata, and subject-aware framing.

Your media stays on your computer. Speech recognition, highlight discovery,
metadata drafts, and rendering all run locally.

## Features

**Source and transcription**

- Select a video from the input folder, upload one, or download a YouTube video
  through `yt-dlp` (only download content you are authorized to access).
- Inspect media details with FFprobe.
- Generate timestamped SRT subtitles with faster-whisper. The model is loaded
  once and reused for the session.

**Smart Clip Finder**

- Ranks transcript windows as highlight candidates. You choose the clip length
  range and how many candidates to generate.
- Review each clip: adjust the start and end times, and edit the title,
  description, and hashtags before exporting.
- Draft titles, descriptions, and hashtags are generated offline from the
  transcript. Nothing is sent to an external service.
- Export one clip, or select several and export them as a batch with a progress
  bar. The batch size is limited by `max_batch_size` in `config.json`.
- Choose a format: vertical YouTube Shorts (1080 × 1920), landscape (1920 × 1080),
  or the original format.
- Smart camera framing follows a detected face or person (see below), or uses a
  fixed center crop.
- Optionally burn styled subtitles into each clip.
- Each exported clip gets a JSON sidecar in `output/metadata/` with its timing,
  title, description, hashtags, transcript, and source video.

**Subtitle studio**

- Style subtitles (font, size, colors, outline, background box, position, margin)
  and export a subtitled MP4. A timing adjustment regenerates subtitles so the
  change is applied.

**Smart reframing**

Smart reframing samples video frames and uses OpenCV's built-in face detector
and HOG people detector to follow the most plausible subject when cropping.
It runs on the CPU and needs no separately downloaded model.

- **Auto subject tracking (faces first):** tracks a face when one is visible and
  falls back to a full-body person detector.
- **Face focus:** best for close-up and talking-head footage.
- **Person focus:** best when the subject moves around the scene.
- **Center crop:** a fixed center crop.

Reframing applies to Shorts and 16:9 output. It does not identify the active
speaker or understand actions, and it does not guarantee that hands or equipment
stay in frame. When no subject is detected, it falls back to a centered crop.
Review each exported clip before publishing.

## Requirements

- Windows (primary target)
- Python 3.14.7, as checked by `setup.bat`
- FFmpeg and FFprobe available on `PATH`
- `yt-dlp` available on `PATH` (for YouTube downloads)
- Python packages in `requirements.txt`

## Installation

1. Install Python 3.14.7 and FFmpeg. Make sure `ffmpeg`, `ffprobe`, and `yt-dlp`
   are available on `PATH`.
2. From the project folder, install the Python dependencies:

   ```bat
   python -m pip install -r requirements.txt
   ```

3. Run the environment checks:

   ```bat
   setup.bat
   ```

4. Start the application:

   ```bat
   run.bat
   ```

If setup fails, run `diagnose.bat` and review its output.

## Configuration

`config.json` controls the transcription model and device, the batch-size limit,
and the input, output, metadata, and temporary folders. Paths must stay inside
the project folder.

`.streamlit/config.toml` controls the Streamlit server and theme. The upload
limit is 4096 MB.

Do not store passwords, API keys, or other secrets in committed files.

## Project layout

```
app.py                     Entry point and navigation
core/                      Config, video inspection, transcription, subtitle burning
features/clip_finder/      Highlight ranking, clip render pipeline, metadata drafts
features/smart_reframe.py  Subject-aware crop planning
ui/                        Streamlit pages
tests/                     Automated tests
```

## Tests

Run the automated test suite from the project folder:

```bat
python -m unittest discover -s tests -v
```

Some tests render real clips with FFmpeg against `media/input/test_demo.mp4`.
They are skipped automatically if FFmpeg or the sample media is missing.
Automated tests do not replace testing exports with your own media.

## Planned work

- Active-speaker estimation that combines audio activity with visual mouth movement.
- Action-aware subject selection that keeps hands or equipment in frame.
- Bulk download and queue management for multiple source videos.
- YouTube upload assistance, with explicit user review and authorization.

## License

ClipForge AI is licensed under the MIT License. See [LICENSE](LICENSE) for details.
