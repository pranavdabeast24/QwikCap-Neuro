# Run QwikCap from source

To open the ready-made app, use the [download instructions](../README.md) or the [Windows guide](WINDOWS.md).
Use the steps below to run the Python source.

## Get the source

Install Git and Python 3.12 with Tcl/Tk support first.
Run these commands in Terminal on Mac or PowerShell on Windows.

```sh
git clone https://github.com/pranavdabeast24/capitolinus-form-extraction.git qwikcap
cd qwikcap
```

Run the remaining commands from this `qwikcap` folder.

## Set up macOS

Create the environment, install the requirements, and check Tk.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tkinter
```

Close the Tk demonstration window, then open QwikCap.

```sh
.venv/bin/python desktop.py
```

For later runs, use the same launch command or double-click `start-desktop-macos.command`.

## Set up Windows

In PowerShell, create the environment, install the requirements, and check Tk.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m tkinter
```

Close the Tk demonstration window, then open QwikCap.

```powershell
.venv\Scripts\python.exe desktop.py
```

For later runs, use the same launch command or double-click `start-desktop-windows.bat`.
The launchers use `.venv`. They do not install Python or dependencies.

## Try a form

QwikCap opens with PACE automatic review ready.
Follow the [one-patient walkthrough](SIH_CLINIC_WORKFLOW.md) to add the supplied PDFs, review answers, and export.

The supplied clinic PDFs have text layers and need no OCR.
For scans, macOS source runs need an existing Swift toolchain for Apple Vision or an existing Tesseract installation.
Windows scans need an existing Tesseract installation with English language data.
Set `FORMBRIDGE_TESSERACT` to its executable path before launch, or add Tesseract to `PATH`.
QwikCap does not install or bundle Tesseract.
Automatic grouping must read each patient sticker. For a scan-only sticker, configure OCR or use a searchable PDF before import.

Extraction uses local PDF text, masks, and optional OCR.
LLM extraction, camera capture, and direct REDCap submission are not implemented.

Use [Build the desktop app](BUILDING.md) for packaging commands and [the handoff](HANDOFF.md) before continuing development.
