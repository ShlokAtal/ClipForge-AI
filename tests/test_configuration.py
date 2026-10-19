import json
import tempfile
import unittest
from pathlib import Path

from core.configuration import (
    load_config,
    prepare_folders,
    validate_config,
)


def valid_config():

    return {
        "app_name": "ClipForge AI",
        "max_batch_size": 10,
        "processing_mode": "sequential",
        "transcription": {
            "model": "small",
            "device": "auto",
            "compute_type": "int8",
        },
        "paths": {
            "input": "media/input",
            "clips": "output/clips",
            "subtitles": "output/subtitles",
            "metadata": "output/metadata",
            "jobs": "data/jobs",
            "temp": "temp",
            "logs": "logs",
        },
        "skip_existing_outputs": True,
        "automatic_upload": False,
        "telemetry": False,
    }

class TestConfiguration(unittest.TestCase):

    def test_valid_configuration(self):
        config = valid_config()
        self.assertEqual(validate_config(config), config)

    def test_non_object_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_config([])

    def test_invalid_batch_size_is_rejected(self):
        config = valid_config()
        config["max_batch_size"] = 11

        with self.assertRaisesRegex(ValueError, "max_batch_size"):
            validate_config(config)

    def test_boolean_batch_size_is_rejected(self):
        config = valid_config()
        config["max_batch_size"] = True

        with self.assertRaisesRegex(ValueError, "max_batch_size"):
            validate_config(config)

    def test_invalid_processing_mode_is_rejected(self):
        config = valid_config()
        config["processing_mode"] = "parallel"

        with self.assertRaisesRegex(ValueError, "processing_mode"):
            validate_config(config)

    def test_path_traversal_is_rejected(self):
        config = valid_config()
        config["paths"]["input"] = "../outside"

        with self.assertRaisesRegex(ValueError, "paths.input"):
            validate_config(config)

    def test_missing_config_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_file = Path(directory) / "missing.json"

            with self.assertRaises(FileNotFoundError):
                load_config(missing_file)

    def test_invalid_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.json"
            config_file.write_text("{invalid json", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                load_config(config_file)

    def test_load_config_reads_and_validates_file(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.json"
            config_file.write_text(
                json.dumps(valid_config()),
                encoding="utf-8",
            )

            loaded = load_config(config_file)
            self.assertEqual(loaded["app_name"], "ClipForge AI")

    def test_prepare_folders_creates_missing_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            config = valid_config()

            prepare_folders(base_dir, config)

            for relative_path in config["paths"].values():
                self.assertTrue((base_dir / relative_path).is_dir())

    def test_prepare_folders_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            input_folder = base_dir / "media" / "input"
            input_folder.mkdir(parents=True)
            existing_file = input_folder / "keep.txt"
            existing_file.write_text("keep me", encoding="utf-8")

            prepare_folders(base_dir, valid_config())

            self.assertEqual(
                existing_file.read_text(encoding="utf-8"),
                "keep me",
            )

if __name__ == "__main__":
    unittest.main()
