# Changelog

## 1.1.0

### Added
- Batch clip export: select several highlights, export them with a progress bar,
  and respect the `max_batch_size` limit from `config.json`.
- Per-clip review: editable start and end times, title, description, and hashtags.
- Offline draft titles, descriptions, and hashtags generated from each transcript.
- JSON metadata sidecar for every exported clip in `output/metadata/`.
- Dashboard lists all exported videos.
- `.streamlit/config.toml` with a dark theme and a 4096 MB upload limit.
- `.gitattributes` to keep line endings consistent across Windows and Git.

### Fixed
- Re-exporting a clip after changing its caption style failed with
  "Output already exists". Re-exports now replace the previous file.
- Editing highlights left stale start and end values from a previous search.
- Changing the subtitle timing adjustment had no effect when existing subtitles
  were reused. A non-zero adjustment now regenerates subtitles.
- Intermediate raw and caption files are removed after each export.
- Hashtags could contain apostrophes (for example `#you're`).
- Long smart-reframe clips produced very large FFmpeg expressions. Keyframes are
  now capped.
- Face focus silently fell back to center crop when the face model was missing.
  It now reports the problem.

### Changed
- The Whisper model is loaded once and reused instead of reloaded for each run.
- Clear, professional wording throughout the interface.
- Python sources use LF line endings. Batch scripts keep CRLF.

## 1.0.0

- Initial release: dashboard, video workspace, subtitle studio, Smart Clip Finder,
  Smart Reframing (initial version), settings, and Windows setup scripts.
