# QuickCap (CV) desktop

**Property of Capitolinus Ventures**

QuickCap (CV) has a native Tk desktop interface for macOS and Windows. It runs the document and spreadsheet workers on the same computer. The desktop workflow does not require a browser, a local web server, or a cloud extraction account.

The user selected QuickCap (CV) as a working name only. The QuickCap name is already used by MedVision in healthcare software; no affiliation or trademark clearance is asserted. See [docs/COMPETITORS_AND_NAME.md](docs/COMPETITORS_AND_NAME.md) before public naming or distribution, and `OWNERSHIP.md` for the scope of the original-code notice and third-party rights.

The display name and GUI package basename (`QuickCapCV`) have changed from Formbridge. The Mac bundle identifier is `com.capitolinusventures.quickcapcv`, so macOS can distinguish QuickCap from older Formbridge builds. Saved project/type formats retain their existing `formbridge-*` identifiers, and older projects remain supported. The `FORMBRIDGE_TESSERACT` setting and `FormbridgeWorker` helper name remain stable for compatibility. Renaming the app does not migrate saved data or change review requirements. The earlier browser interface and historical verification records retain their original names.

For a Windows download and setup, use [the Windows guide](docs/WINDOWS.md). Developers can start with [the handoff](docs/HANDOFF.md), follow [source setup](docs/GETTING_STARTED.md), and rerun [the portable checks](docs/TESTING.md). Source, fictional fixtures, and instructions travel through Git. Saved projects and private documents need a separate approved transfer.

The app starts without preset fields. You can draw custom answer masks and save a reusable extraction type. For the supplied PACE forms, an optional printed-form reader recognizes questions, marked choices, and matrix columns from native PDF text and control geometry. You still confirm the source group, review its answers, and approve one patient row before export. The destination keeps the supplied template's exact 512 headers. Repeating-instrument REDCap upload needs a separate validated conversion.

## Review supplied PACE forms

The primary interface has **File**, **Advanced**, and **Help** menus, an **Add documents…** action, and two tabs. Field setup appears when it applies. Advanced controls stay hidden until you enable them.

1. Choose **Advanced > Form type > Read PACE printed forms**. The shortcut is Command-Shift-U on Mac or Ctrl-Shift-U on Windows.
2. Choose **Add documents… > Combine PDFs for one patient…**. Select that patient's original PDFs, enter the study record ID, and confirm the group and source order.
3. Review the suggested answers beside their source pages. **Confirm & next** saves the current confirmation and advances. Correct any value that differs from the source, enter your reviewer name, and approve the patient row.
4. Open **Map & export**. Choose **Use fields as columns** to create the complete 512-column XLSX destination, or select a supported blank spreadsheet.
5. Inspect the field assignments and populated preview. Confirm the column mapping, then export the approved rows through the app.
6. Save a project if you need to continue later. Reopening a project reprocesses the original sources and requires fresh confirmations and approval.

The reader checks printed record IDs and demographics against the confirmed patient bundle. Unknown instruments, conflicting source identities, repeated assessments of one instrument, and conflicting source values block the one-row merge. A visibly unchecked checkbox can produce `0`. An absent question stays blank, and a visible unanswered radio stays blank and remains part of the review. Editing an answer cannot hide an observed field.

## Actual train validation, 2026-11-18

The supplied synthetic train set contains 28 PDFs, 45 pages, nine instruments, and five patient groups. Independent answer-key checks cover 609 explicit values. Of these, 600 have destination columns in the supplied template. The final local extraction diagnostics match all 600 values and all 483 expected unchecked-checkbox zeroes. Two visibly unmarked source rows remain blank. Nine total-score entries have no destination column and are reported separately, rather than added to the export.

The Mac source suite ran 283 tests with seven Windows-specific skips and no failures. The reader retains all 14 catalog-required flags plus the required record ID. Source-confirmed missing answers require immutable unmarked-row evidence and explicit field confirmation, which must be repeated after reopening. The packaged-reader check passes 16 invented fields with all 512 destinations. Independent audit of the [new Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229) at `b139c46` confirms 283 source tests with one POSIX-only skip and all 11 acceptance checks passing. The older Windows prerelease below does not contain the new reader or UI changes.

The native desktop imported all 28 PDFs into five confirmed patient bundles, confirmed 1,085 applicable fields, approved all five patient rows, confirmed the 512-column mapping, and wrote [the train readout](examples/quickcap-actual-train-readout.xlsx). Independent checks of both the saved raw project and app-written workbook match all 2,560 expected destination cells, with zero issues and zero manual value corrections. The reader was frozen at `26fb90e` before any held-out access. See [the train report](docs/testing/actual-pace-dataset-2026-11-18.md) for the workbook hash and measured scope.

## Held-out evaluation and current limit

**The frozen reader makes one raw extraction error in the supplied held-out set.** Across 27 PDFs, 40 pages, and five patient groups, it matches 550 of 551 mapped key values and all 390 additional unchecked-checkbox zeroes. For `personal_ctdisorder_v2`, it suggests `hypermobility` where the fictional source reads `Joint hypermobility`. Eight key-only totals have no destination column and remain outside the export. No extraction rule or engine change was made from these test answers.

The native Mac desktop workflow corrected that one suggestion from the visible source, confirmed all 941 applicable fields, approved five patient rows, confirmed the 512-column mapping, and exported XLSX. Independent checks match all 2,560 reviewed workbook cells with zero issues. Before correction, the app-saved raw project matched 2,559 of 2,560 cells. Every other value and all original source data remained unchanged. All 37 frozen runtime file hashes still match after evaluation; no engine or rule tuning was made. See [the held-out report](docs/testing/heldout-pace-2026-11-18.md) for hashes and independent evidence. Actual-dataset desktop QA ran on Mac; Windows acceptance used generated fixtures and packaged checks, with an actual-dataset Windows GUI walkthrough still outstanding.

## Earlier full-codebook practice check

The [portable practice kit](examples/pace-synthetic-practice.zip) contains 18 fictional PDFs, a reusable 512-field extraction type, independent answer keys, and coverage records. It includes one text-layer case and one raster-only case, with nine ordered PDFs per case. Its 253 codebook entries expand to the exact 512 export columns. Conditional responses exercise all branches for software coverage and do not describe a clinically coherent patient. The kit is separate from the supplied train and held-out datasets.

The raw app extraction matched all 512 text-case cells and 506 of 512 scan-case cells. The native Mac workflow then corrected six scan values, confirmed all 512 fields for each case, entered a reviewer, approved both records, confirmed the mapping, and exported XLSX through the Save dialog. The [actual app export](examples/quickcap-synthetic-pace-readout.xlsx) has two data rows and 512 ordered columns. Independent comparison matched all 1,024 cells, including eight expected blanks and 343 zeroes, with no formulas, spreadsheet errors, or hidden content. This corrected export result is separate from raw OCR accuracy. See [the run report](docs/testing/SYNTHETIC_PACE_GUI_2026-11-18.md) for the before-and-after results and limitations.

Verify the included export without creating an app session or changing the workbook. Run this command from the repository root with the configured Python environment:

```sh
python tools/verify_synthetic_pace_readout.py examples/quickcap-synthetic-pace-readout.xlsx
```

The readout retains default column widths, so long headers and identifiers can clip or wrap. Use Excel AutoFit and adjust row heights for readability. These layout limits do not change the verified cell values.

At revision `0793411`, the source suite passed 238 tests with seven skips. The [earlier private Windows prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-pace-2026-11-18) includes that revision. Its [Windows acceptance run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44407671706) passed 238 source tests with one POSIX-only skip, built and extracted the portable app, and passed all ten then-current acceptance stages. A person-driven Windows laptop walkthrough remains a pilot check.

For another AI or developer, [docs/HANDOFF.md](docs/HANDOFF.md) provides the source map, exact continuation steps, test commands, and dataset boundaries. The PACE smoke verifier and the full practice-kit GUI run are separate checks.

## Create and review an extraction type

The app starts with no fields or preset categories. Create an extraction type for your own form:

1. Import a PDF or supported image. The first upload opens the mask designer on its rendered pages.
2. Name the extraction type. Choose **Draw field**, then drag around an answer area. Give each field a unique lowercase variable name and a human label. Choose text, integer, number, ISO date (`YYYY-MM-DD`), or choice codes such as `1=Yes;0=No`. Explicitly select one text field as the required record identifier.
3. Select a field in the list or click its mask to edit it. **Advanced > Form type** provides redraw, delete, and coordinate-entry commands. Coordinate entry accepts the page and normalized percentages for the mask. All masks on the current page remain visible.
4. Choose **Apply type** to extract the queued documents using your masks. **Advanced > Form type > Save extraction type…** writes a named reusable JSON definition. **Load extraction type…** applies that definition to another matching PDF or image.
5. Compare each proposed value with the source pages. Correct it, confirm each field, enter a reviewer, and approve the record.
6. Open **Map & export**. Select a blank XLSX or CSV destination, or choose **Use fields as columns**. Drag a source field to its destination column, or use the selected column's assignment control. Inspect the populated preview before you confirm the mapping and export approved rows.
7. Save a project explicitly to resume later. Projects contain source documents, entered values, the active extraction type and unfinished type drafts. Loading a project requires review again. Older v1 projects remain supported.

Field confirmation, record approval, and spreadsheet assignment confirmation are separate steps. Printed labels and configured page regions suggest values; they do not establish that an answer is correct. Simple blank spreadsheet templates are supported. Existing destination data, formulas, macros, embedded objects, and complex Excel behavior are rejected. Direct submission to REDCap, camera capture, repeating instruments, longitudinal events, and branching logic evaluation are outside this prototype.

An extraction-type file contains only its name, identifier selection, field rules, page shapes and normalized mask coordinates. It contains no source files, source filenames, OCR text, extracted answers or review evidence. Keep a project when you need to retain sources and drafts; keep a type when you need to reuse the extraction rules.

**Design masks** edits a draft while retaining the committed type. Apply or load reprocesses sources and clears field confirmations, approvals and spreadsheet mapping confirmation. Review, approval and spreadsheet operations stay blocked until a valid type is applied and while a type draft is open. New/open/close actions offer to save project changes, including unfinished drafts.

Types require the same page count and approximately the same page aspect ratios. A mismatch keeps the source available, clears suggested answers and blocks review/approval until the correct type is loaded or designed. Matching dimensions do not establish that documents have the same layout: inspect every mask and answer. A mask may include a printed label and answer, but drawing tightly around the answer usually avoids ambiguity. Text-only `.txt` files can be opened for legacy review but cannot define visual masks. Scanned/image sources need a working local OCR engine for suggestions; manual source review remains essential.

The **Advanced** menu retains the form-type, review, and spreadsheet commands. Command-K on Mac or Ctrl-K on Windows confirms the current field and advances. **Expand…** opens text answers. CSV templates support CSV output. Use an XLSX template or **Use fields as columns** for XLSX output. The main export button follows the selected template format. Exports include approved records only.

## Open a packaged application

On macOS, open `QuickCapCV.app`. Keep the whole app bundle together. On Windows, open `QuickCapCV\QuickCapCV.exe` and retain the entire `QuickCapCV` folder, including its dependencies and companion worker. Copying only the `.exe` is insufficient. A packaged build includes Python and its runtime dependencies; the source launchers below are not needed.

The macOS build compiles the included `native_ocr.swift` adapter into an executable and bundles it with Apple Vision OCR. It does not need Swift on the computer running the packaged app. Optional Tesseract discovery checks `PATH`, then the standard Homebrew locations on macOS or standard installations on Windows. An explicit `FORMBRIDGE_TESSERACT` executable path takes precedence. An invalid explicit path disables OCR instead of silently selecting another engine. Tesseract needs English language data and is not bundled or downloaded by the app. Tesseract 5.5.3_1 was installed with operator approval for the current Mac run. Without a working OCR engine, scans remain available for manual review and entry; text PDFs can still use their text layers.

These are development builds without distribution signing or notarization. The Windows x64 portable ZIP passed automated native Windows and packaged-worker checks on 2026-11-18, including all five fictional scans and independently reopened spreadsheet exports. See [the Windows evidence](docs/TESTING.md#windows-portable-build-2026-11-18). A complete person-driven workflow on a Windows laptop remains a pilot check.

On 2026-11-13, a fresh macOS arm64 environment installed the unchanged runtime and build pins and passed all 156 source tests. That `QuickCapCV.app` built, and the source and packaged-worker custom-mask checks each passed all ten groups. Later PACE and Windows work has separate [recorded results and limits](docs/TESTING.md). The current full practice-kit GUI status is recorded above. Mouse-drag mask creation and real-study REDCap import remain unverified.

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

The result is `dist/macos/QuickCapCV.app`. PyInstaller also leaves its supporting `dist/macos/QuickCapCV` directory. Distribute the complete `.app` bundle. The console worker is built first, then included in the GUI bundle under `helpers`. Both the GUI and its document worker include the PACE catalog. The compiled OCR helper is included with both processes.

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update(); root.destroy()"
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
```

The result is `dist\windows\QuickCapCV\QuickCapCV.exe` with its adjacent dependencies. Distribute the complete `QuickCapCV` directory. Windows packages do not include Apple Vision or Tesseract.

The builder checks that the GUI, companion worker, source modules, samples, and spreadsheet directory exist before building. It requires the installed PyInstaller version pinned in `requirements-build.txt`. Each run uses a new intermediate directory. If the selected destination already contains `QuickCapCV` or `QuickCapCV.app`, choose another `--dist-dir`; the builder preserves existing output. Retained work directories can be inspected or removed manually after review.

The manually dispatched [Windows workflow](.github/workflows/windows-build.yml) builds and verifies the portable ZIP on Windows with fictional fixtures. Its 11 checks include native startup, required local OCR, custom masks, patient bundles, the packaged PACE printed-form reader, and spreadsheet values after extraction outside the checkout. It retains notices and a component inventory. It has no push, pull-request, or schedule trigger and does not publish releases. `desktop-build.yml` remains an older inactive matrix template.

## Local data and review limits

Documents, extracted values, and source pages are processed locally. Workers use private temporary storage; a crash can leave temporary files. Saved projects and exported spreadsheets persist where you save them, and project files include the source documents. The prototype does not provide managed access controls, encryption at rest, tamper-evident audit trails, or a compliance determination. Use fictional data until the full environment and workflow are approved for the intended research use.

LLM extraction, learning from corrections, and camera capture are not implemented. [The LLM privacy proposal](docs/LLM_PRIVACY.md) describes future requirements and does not change the current app.

See `README_BROWSER.md` for field definitions, input limits, spreadsheet restrictions, and the earlier browser workflow. This desktop build kit includes the native launchers; the earlier browser interface is a separate delivery.

## Private repository

This repository is proprietary. See [OWNERSHIP.md](OWNERSHIP.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [FIXTURES.md](FIXTURES.md). Pilot and collaboration documents under `docs/` are proposals for review. Customer builds and feedback do not include core source access by default. The Windows workflow runs only when manually dispatched. `desktop-build.yml` remains an inactive template outside `.github/workflows/`. See [docs/BUILD_ENVIRONMENT.md](docs/BUILD_ENVIRONMENT.md) for current exact-pin evidence, the historical dependency snapshot, and distribution license and notice work. QuickCap (CV) is a working name only, pending public name clearance.
