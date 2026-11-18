"""Tesseract discovery never bypasses an explicit override."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline


class OCRDiscoveryTests(unittest.TestCase):
    def test_windows_standard_installations_are_found_without_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            program = root / "Program Files/Tesseract-OCR/tesseract.exe"
            local = root / "Local AppData/Programs/Tesseract-OCR/tesseract.exe"
            for executable in (program, local):
                executable.parent.mkdir(parents=True)
                executable.write_bytes(b"fictional executable marker")
                executable.chmod(0o700)
            environment = {"ProgramFiles": str(root / "Program Files"), "LOCALAPPDATA": str(root / "Local AppData")}
            with patch.dict(os.environ, environment, clear=True), patch.object(sys, "platform", "win32"), patch.object(pipeline.shutil, "which", return_value=None):
                self.assertEqual(pipeline._tesseract_path(), str(program.resolve()))
                program.unlink()
                self.assertEqual(pipeline._tesseract_path(), str(local.resolve()))

    def test_invalid_explicit_override_is_fail_closed(self):
        for override in ("", "tesseract.exe", "/missing/tesseract.exe"):
            with self.subTest(override=override), patch.dict(os.environ, {"FORMBRIDGE_TESSERACT": override}, clear=True), patch.object(pipeline.shutil, "which") as search:
                self.assertIsNone(pipeline._tesseract_path())
                search.assert_not_called()

    def test_windows_path_candidate_must_be_absolute_expected_executable(self):
        for candidate in ("relative/tesseract.exe", "/missing/tesseract.exe", sys.executable):
            with self.subTest(candidate=candidate), patch.dict(os.environ, {}, clear=True), patch.object(sys, "platform", "win32"), patch.object(pipeline.shutil, "which", return_value=candidate):
                self.assertIsNone(pipeline._tesseract_path())


if __name__ == "__main__":
    unittest.main()
