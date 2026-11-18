# QuickCap (CV) desktop

**Property of Capitolinus Ventures**

QuickCap (CV) has a native Tk desktop interface for macOS and Windows. It runs the document and spreadsheet workers on the same computer. The desktop workflow does not require a browser, a local web server, or a cloud extraction account.

The user selected QuickCap (CV) as a working name only. The QuickCap name is already used by MedVision in healthcare software; no affiliation or trademark clearance is asserted. See [docs/COMPETITORS_AND_NAME.md](docs/COMPETITORS_AND_NAME.md) before public naming or distribution, and `OWNERSHIP.md` for the scope of the original-code notice and third-party rights.

The display name and new GUI package basename (`QuickCapCV`) have changed from Formbridge. Saved project/type formats retain their existing `formbridge-*` identifiers, and older projects remain supported. The `FORMBRIDGE_TESSERACT` setting, `FormbridgeWorker` helper name and `org.formbridge.desktop` bundle identifier also remain stable for compatibility. Renaming the app does not migrate saved data or change review requirements. The earlier browser interface and historical verification records retain their original names.

For a Windows download and setup, use [the Windows guide](docs/WINDOWS.md). Developers can start with [the handoff](docs/HANDOFF.md), follow [source setup](docs/GETTING_STARTED.md), and rerun [the portable checks](docs/TESTING.md). Source, fictional fixtures, and instructions travel through Git. Saved projects and private documents need a separate approved transfer.

For the supplied PACE study, use [the patient-bundle workflow](docs/PACE_WORKFLOW.md). The optional catalog provides all 512 exact destination fields, instrument-specific codes and date rules. Combine ordered PDFs under an operator-entered study ID, select relevant fields and masks, and review one patient row. The full destination stays intact, with explicit blank-column and mapping confirmation. Repeating-instrument REDCap upload needs a separate validated conversion; this is a patient review export.

The app starts with no fields or preset categories. Create an extraction type for your own form:

1. Import a PDF or supported image. The first upload opens the mask designer on its rendered pages.
2. Name the extraction type. Choose **Draw new**, then drag around an answer area. Give each field a unique lowercase variable name and a human label. Choose text, integer, number, ISO date (`YYYY-MM-DD`), or choice codes such as `1=Yes;0=No`. Explicitly select one text field as the required record identifier.
3. Select a field in the list or click its mask to edit it. **Redraw** replaces its mask; **Delete** removes it. **Add mask by coordinates…** provides a keyboard alternative: enter the page and left/top/width/height percentages of the full page, then press Enter. All masks on the current page remain visible. Page navigation, scrolling and zoom work while designing.
4. Choose **Apply type** to extract the queued documents using your masks. **Save type…** writes a named reusable JSON definition. Later, **Load type…** applies that definition to another matching PDF/image, including when no documents are open yet.
5. Compare each proposed value with the source pages. Correct it, confirm each field, enter a reviewer, and approve the record.
6. Open a blank XLSX or CSV destination template, or choose **Use categories as columns**. Match each source field to a destination column and inspect the populated preview before confirming the assignments and exporting approved rows.
7. Save a project explicitly to resume later. Projects contain source documents, entered values, the active extraction type and unfinished type drafts. Loading a project requires review again. Older v1 projects remain supported.

Field confirmation, record approval, and spreadsheet assignment confirmation are separate steps. Printed labels and configured page regions suggest values; they do not establish that an answer is correct. Simple blank spreadsheet templates are supported. Existing destination data, formulas, macros, embedded objects, and complex Excel behavior are rejected. Direct submission to REDCap, camera capture, repeating instruments, longitudinal events, and branching logic evaluation are outside this prototype.

An extraction-type file contains only its name, identifier selection, field rules, page shapes and normalized mask coordinates. It contains no source files, source filenames, OCR text, extracted answers or review evidence. Keep a project when you need to retain sources and drafts; keep a type when you need to reuse the extraction rules.

**Design masks** edits a draft while retaining the committed type. Apply or load reprocesses sources and clears field confirmations, approvals and spreadsheet mapping confirmation. Review, approval and spreadsheet operations stay blocked until a valid type is applied and while a type draft is open. New/open/close actions offer to save project changes, including unfinished drafts.

Types require the same page count and approximately the same page aspect ratios. A mismatch keeps the source available, clears suggested answers and blocks review/approval until the correct type is loaded or designed. Matching dimensions do not establish that documents have the same layout: inspect every mask and answer. A mask may include a printed label and answer, but drawing tightly around the answer usually avoids ambiguity. Text-only `.txt` files can be opened for legacy review but cannot define visual masks. Scanned/image sources need a working local OCR engine for suggestions; manual source review remains essential.

The **Form type** menu provides keyboard-accessible commands for drawing, entering coordinates, redrawing, deleting, applying, saving and loading, plus focusing the type-name and field-name editors. It also selects a field's value type and explicitly assigns a text field as the record identifier. **Review > Confirm current field against source and next** uses Command-K on Mac or Ctrl-K on Windows. **Expand** opens long answers. CSV templates support CSV output; import an XLSX template to retain supported layout in XLSX output. Exports include approved documents only.

## Open a packaged application

On macOS, open `QuickCapCV.app`. Keep the whole app bundle together. On Windows, open `QuickCapCV\QuickCapCV.exe` and retain the entire `QuickCapCV` folder, including its dependencies and companion worker. Copying only the `.exe` is insufficient. A packaged build includes Python and its runtime dependencies; the source launchers below are not needed.

The macOS build compiles the included `native_ocr.swift` adapter into an executable and bundles it with Apple Vision OCR. It does not need Swift on the computer running the packaged app. On Windows, Tesseract is optional and must be installed separately, with English language data. Standard Program Files and local application installations are detected automatically; `PATH` and an explicit `FORMBRIDGE_TESSERACT` executable path are also supported. The app does not bundle or download Tesseract. Without a working OCR engine, scans remain available for manual review and entry; text PDFs can still use their text layers.

These are development builds without distribution signing or notarization. The Windows x64 portable ZIP passed automated native Windows and packaged-worker checks on 2026-11-18, including all five fictional scans and independently reopened spreadsheet exports. See [the Windows evidence](docs/TESTING.md#windows-portable-build-2026-11-18). A complete person-driven workflow on a Windows laptop remains a pilot check.

On 2026-11-13, a fresh macOS arm64 environment installed the unchanged runtime and build pins and passed all 156 source tests. The final `QuickCapCV.app` built, and the source and packaged-worker custom-mask checks each passed all ten groups. Later PACE and Windows work has separate [recorded results and limits](docs/TESTING.md). Mouse drawing, a complete person-driven desktop workflow, and real-study REDCap import remain unverified.

## Run the source on macOS

Use Python 3.12 with working Tk support. From this folder, create the environment and install the pinned requirements explicitly:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python desktop.py
```

On later runs, double-click `start-desktop-macos.command`. The launcher uses this folder's `.venv` and reports setup steps if it is absent. The source OCR adapter requires an already-installed Swift toolchain, or an externally configured Tesseract installation. Packaged macOS builds use the compiled adapter.

## Run the source on Windows

Install Python 3.12 with Tcl/Tk support. In PowerShell, open this folder and run:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe desktop.py
```

On later runs, double-click `start-desktop-windows.bat`. It uses `.venv\Scripts\pythonw.exe` for the GUI. Neither launcher installs packages or downloads an OCR engine.

To configure an optional existing Tesseract installation for the current PowerShell session:

```powershell
$env:FORMBRIDGE_TESSERACT = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
.venv\Scripts\pythonw.exe desktop.py
```

## Build on the target OS

Native packaging must run on its target OS: macOS creates a Mac app, and Windows creates a Windows app. Use a Python installation with working Tk support. Install build dependencies explicitly, then invoke the builder. The builder never installs tools, downloads dependencies, removes earlier output, or rewrites source files.

macOS also requires an already-installed Swift compiler and Apple developer tools. This command keeps PyInstaller caches, generated specs, intermediate files, and the Swift module cache beneath the selected work directory:

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update(); root.destroy()'
.venv/bin/python build_desktop.py --work-dir work/desktop-build --dist-dir dist/macos
```

The result is `dist/macos/QuickCapCV.app`. PyInstaller also leaves its supporting `dist/macos/QuickCapCV` directory. Distribute the complete `.app` bundle. The console worker is built first, then included in the GUI bundle under `helpers`; the compiled OCR helper is included with both processes.

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update(); root.destroy()"
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
```

The result is `dist\windows\QuickCapCV\QuickCapCV.exe` with its adjacent dependencies. Distribute the complete `QuickCapCV` directory. Windows packages do not include Apple Vision or Tesseract.

The builder checks that the GUI, companion worker, source modules, samples, and spreadsheet directory exist before building. It requires the installed PyInstaller version pinned in `requirements-build.txt`. Each run uses a new intermediate directory. If the selected destination already contains `QuickCapCV` or `QuickCapCV.app`, choose another `--dist-dir`; the builder preserves existing output. Retained work directories can be inspected or removed manually after review.

The manually dispatched [Windows workflow](.github/workflows/windows-build.yml) builds and verifies the portable ZIP on Windows with fictional fixtures. It checks native startup, required local OCR, custom masks, patient bundles and spreadsheet cells after extraction outside the checkout. It retains notices and a component inventory. It has no push, pull-request or schedule trigger and does not publish releases. `desktop-build.yml` remains an older inactive matrix template; it does not provide the current Windows acceptance coverage.

## Local data and review limits

Documents, extracted values, and source pages are processed locally. Workers use private temporary storage; a crash can leave temporary files. Saved projects and exported spreadsheets persist where you save them, and project files include the source documents. The prototype does not provide managed access controls, encryption at rest, tamper-evident audit trails, or a compliance determination. Use fictional data until the full environment and workflow are approved for the intended research use.

LLM extraction, learning from corrections, and camera capture are not implemented. [The LLM privacy proposal](docs/LLM_PRIVACY.md) describes future requirements and does not change the current app.

See `README_BROWSER.md` for field definitions, input limits, spreadsheet restrictions, and the earlier browser workflow. This desktop build kit includes the native launchers; the earlier browser interface is a separate delivery.
