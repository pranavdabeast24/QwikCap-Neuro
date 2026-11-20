# Run QwikCap from source

Use [Windows setup](WINDOWS.md) to run the packaged app without Python.
These steps are for developers.

Run commands from the repository root.
Use Python 3.12 with Tcl/Tk support.
The launchers use `.venv` and do not install dependencies.

## Set up macOS

Run the first three commands.
Close the Tk demonstration window.
Run the last command.
QwikCap opens with no preset fields.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tkinter
.venv/bin/python desktop.py
```

For later runs, use `./start-desktop-macos.command` or the last command above.
Text-layer PDFs need no OCR.
Scans need an existing Swift toolchain for Apple Vision or an existing Tesseract installation.

## Set up Windows

Use PowerShell.
Run the first three commands.
Close the Tk demonstration window.
Run the last command.
QwikCap opens with no preset fields.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m tkinter
.venv\Scripts\python.exe desktop.py
```

For later runs, use `start-desktop-windows.bat`.
Scans need an existing Tesseract installation with English language data.
Set `FORMBRIDGE_TESSERACT` to its executable path before launch, or add it to `PATH`.
The project does not install or bundle Tesseract.
Without OCR, read the source and enter answers manually.

## Try a form

Follow [the clinic walkthrough](SIH_CLINIC_WORKFLOW.md) for the supplied clinic PDFs.
Follow [Custom forms](CUSTOM_FORMS.md) to draw answer masks for another layout.

A saved extraction type contains reusable rules and masks.
A saved project also contains source documents and values.
Keep local types, projects, and exports outside Git.
A new clone does not restore them.
Reopened projects require fresh review and approval.

## Build on the target operating system

Use the source environment above.
On macOS, the Swift compiler and Apple developer tools must already be installed.

Run these commands on macOS:

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build_desktop.py --work-dir work/desktop-build --dist-dir dist/macos
.venv/bin/python verify_desktop_bundle.py dist/macos/QwikCap.app --output verification/bundle
.venv/bin/python tools/verify_custom_masks.py --bundle dist/macos/QwikCap.app --output verification/custom-masks-bundle
.venv/bin/python tools/verify_sih_clinic.py --bundle dist/macos/QwikCap.app --output verification/sih-clinic-bundle
```

Run these commands in Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
.venv\Scripts\python.exe verify_desktop_bundle.py dist\windows\QwikCap --output verification\bundle
.venv\Scripts\python.exe tools\verify_custom_masks.py --bundle dist\windows\QwikCap --output verification\custom-masks-bundle
.venv\Scripts\python.exe tools\verify_sih_clinic.py --bundle dist\windows\QwikCap --output verification\sih-clinic-bundle
```

Expect `dist/macos/QwikCap.app` or `dist\windows\QwikCap\QwikCap.exe`.
Keep the complete application folder, including its companion worker.
The builder preserves existing output and requests a new destination.
Mac development builds use ad hoc signing and are not notarized.

Read [Testing](TESTING.md) for check coverage and recorded platform limits.
The automated checks do not cover the complete mouse-driven workflow.
Read [the handoff](HANDOFF.md) before continuing development.

Extraction uses local PDF text, masks, and optional OCR.
LLM extraction, camera capture, and direct REDCap submission are not implemented.
