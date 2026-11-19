# Run from a new clone

To run the packaged Windows app without installing Python, use [WINDOWS.md](WINDOWS.md).
The instructions below are for source development.

The repository contains the desktop and earlier browser source, build scripts,
tests, explicitly fictional practice files, and the [original supplied synthetic train/test packet](../datasets/sih-synthetic/README.md). Run the commands below from the
repository root. Python 3.12 with Tcl/Tk support is required for the desktop UI.
The launchers use the clone's `.venv`; they do not install dependencies.
For the scope of this transfer and the remaining work, read [HANDOFF.md](HANDOFF.md).

The user-selected desktop working name is **QwikCap**, with `QwikCap`
as the GUI package basename. This is a working name only, with no affiliation or
trademark clearance asserted; see [COMPETITORS_AND_NAME.md](COMPETITORS_AND_NAME.md)
for the historical QuickCap name collision and limits of the rename. Existing Formbridge project/type identifiers,
worker name and environment variables remain compatible. The Mac bundle identifier
is now `com.capitolinusventures.qwikcap` to distinguish older Formbridge builds;
see [the current README](../README.md).

## macOS source setup

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tkinter
.venv/bin/python desktop.py
```

Close the small Tk demonstration window before starting the app. Later, run
`./start-desktop-macos.command` or use the final command above. Text-layer PDFs
work without OCR. Source OCR on macOS requires an already installed Swift
toolchain for the Apple Vision adapter, or an existing Tesseract installation.

## Windows source setup

In PowerShell, with Python 3.12 and Tcl/Tk installed:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m tkinter
.venv\Scripts\python.exe desktop.py
```

Close the Tk demonstration window first. On later runs, use
`start-desktop-windows.bat`. Scans can use an existing Tesseract installation
with English language data. Set `FORMBRIDGE_TESSERACT` to its executable path or
put it on `PATH` before launch. The project does not install or bundle Tesseract.
Without OCR, inspect scans and enter answers manually.

On 2026-11-13, a fresh macOS arm64 environment installed the unchanged runtime
and build pins. All 156 source tests passed with Python 3.12.14 and Tk 9.0.
See [the environment record](testing/ENVIRONMENT_MACOS.json),
[test output](testing/UNIT_TEST_RESULTS_MACOS.txt), and
[BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) for the current evidence and the
historical `cfd0762` snapshot. Rerun [TESTING.md](TESTING.md) on each new machine.
The current QwikCap build passes 283 source tests on Mac with seven Windows-only
skips. Its Windows build uses Python 3.12.10 and passes 283 tests with one
POSIX-only skip and all 11 acceptance stages. See [the current Windows evidence](testing/QWIKCAP_WINDOWS_2026-11-19.md).

## First fictional workflow

For the PACE study references, follow [the patient-bundle workflow](PACE_WORKFLOW.md). It loads the optional expected-field catalog and combines ordered patient PDFs into one review row. The general custom-field route below remains available.

1. Start with a practice PDF from `samples/`. The initial workspace has no
   fields. Name a form type, create answer masks, give each field a unique
   lowercase variable name, choose value types, and select one text identifier.
2. Apply the type. Compare each extracted answer with the source, correct it,
   confirm every field, enter a reviewer, and approve the record.
3. Load a blank destination template from `spreadsheets/`, or use the categories
   as columns. Inspect the populated preview, confirm the column assignments,
   and export CSV or XLSX.
4. Save a type to reuse only the field rules and normalized masks. Save a
   project to retain documents, values, and drafts. Reopening a project clears
   approvals and spreadsheet confirmation so it must be reviewed again.

Custom form layouts, saved type files, projects, and outputs are local working
data and are excluded from Git. A new clone does not restore the previous
computer's workspace. Transfer a wanted type or project separately through an
approved channel; projects include their source documents. The independent
mask verifier can generate a complete fictional workflow instead of copying
old workspace outputs; see [TESTING.md](TESTING.md).

## Build on the target operating system

Use the source environment above. Building requires an explicit installation of
`requirements-build.txt`. On macOS, the Swift compiler and Apple developer tools
must already be installed.

macOS:

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build_desktop.py --work-dir work/desktop-build --dist-dir dist/macos
.venv/bin/python verify_desktop_bundle.py dist/macos/QwikCap.app --output verification/bundle
.venv/bin/python tools/verify_custom_masks.py --bundle dist/macos/QwikCap.app --output verification/custom-masks-bundle
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
.venv\Scripts\python.exe verify_desktop_bundle.py dist\windows\QwikCap --output verification\bundle
.venv\Scripts\python.exe tools\verify_custom_masks.py --bundle dist\windows\QwikCap --output verification\custom-masks-bundle
```

The recorded Mac build produced `QuickCapCV.app`, and both the source and bundled
worker passed the ten custom-mask acceptance groups. See [TESTING.md](TESTING.md)
for the reports and limits. These checks do not exercise native mouse drawing
or a complete native end-to-end workflow.

The builder preserves earlier output and asks for a new destination when one
already exists. Keep the complete macOS `.app` or Windows application directory,
including its companion worker. macOS development builds use ad hoc signing;
they are not distribution signed or notarized. Windows packaging and native
automated acceptance are recorded in [TESTING.md](TESTING.md). A person-driven
Windows walkthrough of the supplied packet remains outstanding.

Extraction currently uses local text layers, configured regions, and optional
OCR. LLM extraction and learning from corrections are not implemented. The
future model requirements are described in [LLM_PRIVACY.md](LLM_PRIVACY.md).
Camera capture is also not implemented. The exports are files for review;
this prototype has no live REDCap connection or
verified live REDCap import. Continue with the detailed workflow in
[README_DESKTOP.md](../README_DESKTOP.md).
