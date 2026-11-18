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
    def test_macos_standard_installations_are_found_without_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            arm = root / "opt/homebrew/bin/tesseract"
            intel = root / "usr/local/bin/tesseract"
            for executable in (arm, intel):
                executable.parent.mkdir(parents=True)
                executable.write_bytes(b"fictional executable marker")
                executable.chmod(0o700)
            locations = {"/opt/homebrew/bin/tesseract": arm, "/usr/local/bin/tesseract": intel}
            path = lambda value: locations.get(str(value), Path(value))
            with patch.dict(os.environ, {}, clear=True), patch.object(sys, "platform", "darwin"), patch.object(pipeline.shutil, "which", return_value=None), patch.object(pipeline, "Path", side_effect=path):
                self.assertEqual(pipeline._tesseract_path(), str(arm.resolve()))
                arm.unlink()
                self.assertEqual(pipeline._tesseract_path(), str(intel.resolve()))
                intel.chmod(0o600)
                self.assertIsNone(pipeline._tesseract_path())
                intel.unlink()
                self.assertIsNone(pipeline._tesseract_path())

    def test_macos_path_takes_precedence_over_standard_installations(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "platform", "darwin"), patch.object(pipeline.shutil, "which", return_value="/custom/bin/tesseract"):
            self.assertEqual(pipeline._tesseract_path(), "/custom/bin/tesseract")

    def test_macos_explicit_override_takes_precedence_over_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            override = Path(folder) / "tesseract"
            override.write_bytes(b"fictional executable marker")
            override.chmod(0o700)
            with patch.dict(os.environ, {"FORMBRIDGE_TESSERACT": str(override)}, clear=True), patch.object(sys, "platform", "darwin"), patch.object(pipeline.shutil, "which", return_value="/custom/bin/tesseract"):
                self.assertEqual(pipeline._tesseract_path(), str(override.resolve()))
            locations = {"/opt/homebrew/bin/tesseract": override, "/usr/local/bin/tesseract": override}
            path = lambda value: locations.get(str(value), Path(value))
            for invalid in ("", "tesseract", "/missing/tesseract"):
                with self.subTest(override=invalid), patch.dict(os.environ, {"FORMBRIDGE_TESSERACT": invalid}, clear=True), patch.object(sys, "platform", "darwin"), patch.object(pipeline.shutil, "which", return_value=str(override)), patch.object(pipeline, "Path", side_effect=path), patch.object(pipeline, "_vision_available", return_value=True):
                    self.assertIsNone(pipeline._tesseract_path())
                    self.assertIsNone(pipeline.capabilities()["ocrEngine"])
                    self.assertEqual(pipeline._ocr(override, 100, 100), (
                        [], "unavailable", "Local OCR is unavailable. Install Tesseract locally to read scanned pages; manual entry remains available."))

    def test_macos_without_tesseract_preserves_apple_vision_fallback(self):
        lines = [pipeline._line([{"text": "0", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}])]
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "platform", "darwin"), patch.object(pipeline.shutil, "which", return_value=None), patch.object(Path, "is_file", return_value=False), patch.object(pipeline, "_vision_available", return_value=True), patch.object(pipeline, "_vision_lines", return_value=lines):
            self.assertIsNone(pipeline._tesseract_path())
            self.assertEqual(pipeline.capabilities()["ocrEngine"], "apple-vision")
            self.assertEqual(pipeline._ocr(Path("synthetic.png"), 100, 100), (lines, "apple-vision", None))

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
