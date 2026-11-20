# Open QwikCap on Windows

Use a 64-bit Intel or AMD Windows computer.

1. Download `QwikCap-Windows-x64.zip` from the [updated prototype release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/v1.1.1-prototype).
2. Right-click the ZIP in File Explorer.
3. Choose **Extract All**.
4. Open the extracted `QwikCap` folder.
5. Double-click `QwikCap.exe`.

Keep the whole folder together.
Do not move the executable away from `_internal`.
You do not need Python, Excel, or a web browser to run the packaged app.
The build is unsigned, so an institution may require IT approval.

## Try the sample forms

Follow the [one-patient walkthrough](SIH_CLINIC_WORKFLOW.md).
PACE automatic review is ready when the app opens.
Add PDFs, check the proposed patient groups, then review their suggested answers.

The PDFs in the current clinic packet have text layers.
They do not need an OCR installation.
Scanned documents need a separate local OCR engine for suggested answers.
Without OCR, automatic grouping cannot read a scan-only sticker. Use a searchable PDF or configure local OCR first.
See [Tesseract's installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html) if you need scan support.
QwikCap does not install or bundle Tesseract.

## If the app does not open

Check that the ZIP is fully extracted and `_internal` is beside the executable.
If device policy blocks the app, ask your IT team.
If Excel has an export open, close it before replacing that file.

Read [developer setup](GETTING_STARTED.md) to run the source and [Build the app](BUILDING.md) to package it.
Read [test results](TESTING.md) for the platform checks and limits.
