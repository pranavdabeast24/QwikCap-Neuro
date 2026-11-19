"""Build a native desktop bundle using already-installed tools.

Run this on the target operating system. This script never installs dependencies,
downloads tools, deletes earlier builds, or changes application source files.
"""
from __future__ import annotations

import argparse
from importlib import metadata, util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from branding import APP_BASENAME


ROOT = Path(__file__).resolve().parent
PYINSTALLER_VERSION = "6.22.3"
RUNTIME_MODULES = (
    "tkinter", "PIL", "pypdfium2", "reportlab", "pypdf", "openpyxl", "defusedxml",
)
STATIC_RESOURCES = (
    "samples/README.md", "samples/answer-key.json", "samples/blank-form.pdf",
    "samples/expected-redcap.csv", "samples/practice-01-text.pdf", "samples/practice-02-text.pdf",
    "samples/practice-03-text.pdf", "samples/practice-04-text.pdf", "samples/practice-05-text.pdf",
    "samples/practice-06-scan.pdf", "samples/practice-06-scan.png", "samples/practice-07-scan.pdf",
    "samples/practice-08-scan.pdf", "samples/practice-09-scan.pdf", "samples/practice-10-scan.pdf",
    "samples/redcap-import-template.csv", "samples/sample-data-dictionary.csv", "samples/sample-schema.json",
    "spreadsheets/friendly-template.xlsx", "spreadsheets/redcap-template.csv",
    "spreadsheets/redcap-template.xlsx", "spreadsheets/template-manifest.json",
    "spreadsheets/pace-import-template.csv", "study_profiles/pace.json",
)
REQUIRED_FILES = (
    "desktop.py", "branding.py", "desktop_model.py", "desktop_worker.py", "runtime_paths.py", "form_types.py",
    "pipeline.py", "worker.py", "templates.py", "template_worker.py", "server.py", "neurology_profile.py", "pace_profile.py", "extraction_profiles.py", "field_catalog.py", "limits.py",
    "study_profiles/pace.json", "spreadsheets/pace-import-template.csv", "source_bundle.py", "bundle_worker.py",
    "requirements.txt", "requirements-build.txt",
)


class BuildError(RuntimeError):
    pass


def preflight(dist_dir: Path) -> str | None:
    """Reject incomplete sources and missing tools before creating build output."""
    if sys.platform not in {"darwin", "win32"}:
        raise BuildError("Build on macOS for a Mac app, or Windows for a Windows app.")
    missing_files = [name for name in (*REQUIRED_FILES, *STATIC_RESOURCES)
                     if not (ROOT / name).is_file() or (ROOT / name).is_symlink()]
    if missing_files:
        raise BuildError("Application sources are incomplete: " + ", ".join(missing_files))
    missing_modules = [name for name in RUNTIME_MODULES if util.find_spec(name) is None]
    try:
        installed_version = metadata.version("pyinstaller")
    except metadata.PackageNotFoundError:
        installed_version = None
    if missing_modules or installed_version != PYINSTALLER_VERSION:
        detail = "Missing modules: " + ", ".join(missing_modules) + ". " if missing_modules else ""
        raise BuildError(
            detail + f"PyInstaller {PYINSTALLER_VERSION} is required (found {installed_version or 'none'}). "
            "Install requirements-build.txt explicitly with this Python before building."
        )
    try:
        # Importing verifies that the interpreter has its native _tkinter library.
        # Creating a GUI window is a separate test and is not needed to compile.
        __import__("tkinter")
    except ImportError as exc:
        raise BuildError("This Python needs working Tk support before it can build the GUI.") from exc
    expected_outputs = [dist_dir / APP_BASENAME]
    if sys.platform == "darwin":
        expected_outputs.append(dist_dir / f"{APP_BASENAME}.app")
    existing = [str(path) for path in expected_outputs if path.exists()]
    if existing:
        raise BuildError(
            "Earlier output exists: " + ", ".join(existing)
            + ". Choose a new --dist-dir; earlier output is never removed automatically."
        )
    if sys.platform == "darwin":
        if not (ROOT / "native_ocr.swift").is_file():
            raise BuildError("The macOS build requires native_ocr.swift.")
        swiftc = shutil.which("swiftc")
        if not swiftc:
            raise BuildError("The macOS build requires an already-installed Swift compiler (swiftc).")
        return swiftc
    return None


def run(command: list[str], environment: dict[str, str]) -> None:
    print("Running:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def build(work_dir: Path, dist_dir: Path) -> Path:
    swiftc = preflight(dist_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="build-", dir=work_dir))
    environment = os.environ.copy()
    environment["PYINSTALLER_CONFIG_DIR"] = str(run_dir / "pyinstaller-cache")
    environment["PYTHONPYCACHEPREFIX"] = str(run_dir / "python-cache")
    spec_dir = run_dir / "specs"
    spec_dir.mkdir()
    native_binary: Path | None = None
    if swiftc:
        module_cache = run_dir / "swift-module-cache"
        module_cache.mkdir()
        environment["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
        environment["SWIFT_MODULECACHE_PATH"] = str(module_cache)
        native_binary = run_dir / "native_ocr"
        run([
            swiftc, "-O", "-module-cache-path", str(module_cache),
            str(ROOT / "native_ocr.swift"), "-o", str(native_binary),
        ], environment)
        if not native_binary.is_file():
            raise BuildError("Swift completed without producing the native OCR executable.")

    common = [
        sys.executable, "-m", "PyInstaller", "--noupx",
        "--specpath", str(spec_dir), "--collect-all", "pypdfium2",
    ]
    for optional in ("numpy", "pandas", "matplotlib", "scipy", "IPython", "pytest"):
        common += ["--exclude-module", optional]
    native_options = ["--add-binary", f"{native_binary}:."] if native_binary else []
    helper_dist = run_dir / "helper-dist"
    run(common + [
        "--onefile", "--console", "--name", "FormbridgeWorker",
        "--distpath", str(helper_dist), "--workpath", str(run_dir / "helper-work"),
        "--hidden-import", "worker", "--hidden-import", "template_worker",
        "--hidden-import", "bundle_worker",
        "--add-data", f"{ROOT / 'study_profiles/pace.json'}:study_profiles",
    ] + native_options + [str(ROOT / "desktop_worker.py")], environment)
    helper = helper_dist / ("FormbridgeWorker.exe" if sys.platform == "win32" else "FormbridgeWorker")
    if not helper.is_file():
        raise BuildError("The worker build did not produce the expected companion executable.")

    gui_options = [
        "--onedir", "--windowed", "--name", APP_BASENAME,
        "--distpath", str(dist_dir), "--workpath", str(run_dir / "gui-work"),
        "--add-binary", f"{helper}:helpers",
    ]
    for name in STATIC_RESOURCES:
        gui_options += ["--add-data", f"{ROOT / name}:{Path(name).parent.as_posix()}"]
    if sys.platform == "darwin":
        gui_options += ["--osx-bundle-identifier", "com.capitolinusventures.qwikcap"]
    run(common + gui_options + native_options + [str(ROOT / "desktop.py")], environment)
    result = dist_dir / (f"{APP_BASENAME}.app" if sys.platform == "darwin" else APP_BASENAME)
    executable = result / f"Contents/MacOS/{APP_BASENAME}" if sys.platform == "darwin" else result / f"{APP_BASENAME}.exe"
    if not executable.is_file():
        raise BuildError("The GUI build did not produce the expected native application.")
    print(f"Native application: {result}")
    print(f"Build intermediates and caches retained: {run_dir}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work" / "desktop-build")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        build(args.work_dir.expanduser().resolve(), args.dist_dir.expanduser().resolve())
    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
