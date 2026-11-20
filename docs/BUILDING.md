# Build the desktop app

Build on macOS for a Mac app, or Windows for a Windows app.
Set up the [Python source environment](GETTING_STARTED.md) first.
Run commands from the repository root.
On macOS, the Swift compiler and Apple developer tools must already be installed.

## Build on macOS

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build_desktop.py --work-dir work/desktop-build --dist-dir dist/macos
.venv/bin/python verify_desktop_bundle.py dist/macos/QwikCap.app --output verification/bundle
.venv/bin/python tools/verify_custom_masks.py --bundle dist/macos/QwikCap.app --output verification/custom-masks-bundle
.venv/bin/python tools/verify_sih_clinic.py --bundle dist/macos/QwikCap.app --output verification/sih-clinic-bundle
.venv/bin/python tools/verify_pace_auto.py --bundle dist/macos/QwikCap.app --output verification/pace-auto-bundle
```

The app is `dist/macos/QwikCap.app`.
Mac development builds use ad hoc signing and are not notarized.

## Build on Windows

Run these commands in PowerShell.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
.venv\Scripts\python.exe verify_desktop_bundle.py dist\windows\QwikCap --output verification\bundle
.venv\Scripts\python.exe tools\verify_custom_masks.py --bundle dist\windows\QwikCap --output verification\custom-masks-bundle
.venv\Scripts\python.exe tools\verify_sih_clinic.py --bundle dist\windows\QwikCap --output verification\sih-clinic-bundle
.venv\Scripts\python.exe tools\verify_pace_auto.py --bundle dist\windows\QwikCap --output verification\pace-auto-bundle
```

The executable is `dist\windows\QwikCap\QwikCap.exe`.
Keep its complete application folder, including `_internal` and the companion worker.

## Check the build limits

The builder preserves existing output. Choose a new `--dist-dir` for another build.
It does not install build tools or dependencies.
Windows scans need a separate local Tesseract installation.

Read [Testing](TESTING.md) for coverage and recorded platform limits.
The automated checks do not prove the complete mouse-driven workflow.
