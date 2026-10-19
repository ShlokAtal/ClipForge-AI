import json
from pathlib import Path

REQUIRED_PATHS = (
    "input",
    "clips",
    "subtitles",
    "metadata",
    "jobs",
    "temp",
    "logs",
)

VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3"}
VALID_DEVICES = {"auto", "cpu", "cuda"}
VALID_COMPUTE_TYPES = {
    "int8",
    "float16",
    "float32",
    "int8_float16",
}

def validate_config(config):

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

    errors = []

    app_name = config.get("app_name")
    if not isinstance(app_name, str) or not app_name.strip():
        errors.append("'app_name' must be a non-empty string.")

    batch_size = config.get("max_batch_size")
    if type(batch_size) is not int or not 1 <= batch_size <= 10:
        errors.append("'max_batch_size' must be an integer from 1 to 10.")

    if config.get("processing_mode") != "sequential":
        errors.append("'processing_mode' must be 'sequential'.")

    transcription = config.get("transcription")
    if not isinstance(transcription, dict):
        errors.append("'transcription' must be a JSON object.")
        transcription = {}

    if transcription.get("model") not in VALID_MODELS:
        errors.append("Invalid transcription model.")

    if transcription.get("device") not in VALID_DEVICES:
        errors.append("Invalid transcription device.")

    if transcription.get("compute_type") not in VALID_COMPUTE_TYPES:
        errors.append("Invalid transcription compute type.")

    paths = config.get("paths")
    if not isinstance(paths, dict):
        errors.append("'paths' must be a JSON object.")
        paths = {}

    for key in REQUIRED_PATHS:
        value = paths.get(key)

        if not isinstance(value, str) or not value.strip():
            errors.append(f"'paths.{key}' must be a non-empty relative path.")
            continue

        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"'paths.{key}' must stay inside the project folder.")

    for key in (
        "skip_existing_outputs",
        "automatic_upload",
        "telemetry",
    ):
        if type(config.get(key)) is not bool:
            errors.append(f"'{key}' must be true or false.")

    if errors:
        raise ValueError("\n".join(errors))

    return config

def load_config(config_path):

    config_path = Path(config_path)

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    return validate_config(config)


def prepare_folders(base_dir, config):

    base_dir = Path(base_dir)

    for relative_path in config["paths"].values():
        folder = base_dir / relative_path
        folder.mkdir(parents=True, exist_ok=True)
