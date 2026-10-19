
# ClipForge AI

ClipForge AI is a free, open-source YouTube assistant designed to simplify video preparation and management.

## Phase 1 — Foundation

Phase 1 establishes the project's configuration, dashboard, setup scripts, and basic testing infrastructure.

### Current Features

- Streamlit dashboard
- Configuration loading and validation
- Configurable batch-processing limit (up to 10 videos)
- Sequential processing configuration
- Transcription settings for faster-whisper
- Checks for required tools, including FFmpeg and yt-dlp
- Configuration tests
- Windows setup, launch, and diagnostic scripts

### Planned Features

- Video transcription and subtitle generation
- Automatically burned-in subtitles
- Smart Clip Finder
- Batch video processing
- Clip export and bulk downloads
- Title, description, and hashtag suggestions
- YouTube upload assistance with review before publishing

**Note:** Planned features are not yet implemented. YouTube upload functionality will require appropriate authorization.

## Requirements

- Windows
- Python 3.14.7 (the version tested during Phase 1 verification)
- FFmpeg
- Git (optional, for development)
- Internet access when installing dependencies or downloading authorized content

## Installation

1. Clone the repository:

   ```bat
   git clone https://github.com/ShlokAtal/ClipForge-AI.git
   cd ClipForge-AI
   ```

2. Run the setup script:

   ```bat
   setup.bat
   ```

3. Launch the application:

   ```bat
   run.bat
   ```

If setup fails, run:

```bat
diagnose.bat
```

Follow any instructions printed by the scripts.

## Configuration

The application uses `config.json` for settings such as:

- Maximum batch size
- Processing mode
- Transcription model and device
- Input and output directories
- Temporary files and job data

Review the configuration before running the application. Do not store passwords, API keys, or other secrets in committed files.

## Testing

Run the configuration tests with:

```bat
python -m unittest discover -s tests -v
```

## Project Status

**Phase 1: Foundation complete.**

Video-processing features are planned for subsequent phases.

## License

ClipForge AI is licensed under the MIT License. See [LICENSE](LICENSE) for details.