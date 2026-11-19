# QwikCap desktop

QwikCap is a native Python and Tk desktop app for macOS and Windows. Upload forms, review extracted answers against their source pages, map fields to spreadsheet columns, and export approved patient rows. Document and spreadsheet processing stays on the same computer.

The current working name replaces QuickCap (CV). Commercial name clearance has not been established. See [the naming record](docs/COMPETITORS_AND_NAME.md) and [ownership notice](OWNERSHIP.md).

The current packages are `QwikCap.app` on Mac and `QwikCap\QwikCap.exe` on Windows. The Mac bundle identifier is `com.capitolinusventures.qwikcap`. Saved project and type formats retain their `formbridge-*` identifiers. `FORMBRIDGE_TESSERACT` and the `FormbridgeWorker` helper stay compatible. Historical reports retain the names of the builds they tested.

Start with the [SIH clinic walkthrough](docs/SIH_CLINIC_WORKFLOW.md) for the current `sih_clinic_dataset` forms. The [new clinic packet](datasets/sih-clinic-synthetic/README.md) is separate from the [earlier PACE printed packet](datasets/sih-synthetic/README.md). For downloads and setup, use [the Windows guide](docs/WINDOWS.md), [developer handoff](docs/HANDOFF.md), and [source setup](docs/GETTING_STARTED.md). Saved projects and private documents need a separate approved transfer.

The [clinic release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19) provides Mac arm64 and Windows x64 packages plus a source-and-dataset packet. Use a build that offers **Read SIH clinic forms**. The earlier `qwikcap-2026-11-19` release predates that reader. New commits use Pranav Mukund's GitHub identity. Historical aliases resolve through `.mailmap` without rewriting shared history.

The app starts without preset fields. You can draw custom answer masks and save a reusable extraction type. Built-in readers are explicit choices for their supported layouts. The SIH clinic and PACE patient workflows keep the supplied template's exact 512 headers. You still confirm the source group, review its answers, and approve each patient row before export. Repeating-instrument REDCap upload needs a separate validated conversion.

## Choose the reader for your packet

The supplied packets have similar filenames but different layouts. Check the folder and printed form before selecting a reader.

| Your documents | Reader under **Advanced > Form type** | Import and output |
| --- | --- | --- |
| Current `Neuro Synthetic Forms/sih_clinic_dataset/` packet, copied as `datasets/sih-clinic-synthetic/`. Registration is marked `REG-100`; clinic pages use `HA-210C`, `HA-220P`, `HA-230`, `PROC-310`, or radiology exam titles. | **Read SIH clinic forms** | Include registration and combine one patient's PDFs. One reviewed patient per row, with 512 destination columns. |
| Original `Neuro Synthetic Forms/dataset/train/forms/` clinic packet, with printed `Form NEU-101`, `NEU-210`, `NEU-215`, `NEU-330`, or `NEU-410` | **Read NEU clinic forms** | Import separate forms. One reviewed document per row, with 45 staging columns. |
| Separate `Neuro Synthetic Forms/sih_dataset/` packet, copied into this repository as `datasets/sih-synthetic/` | **Read PACE printed forms** | Combine the listed PDFs for one confirmed patient. One reviewed patient per row, with 512 destination columns. |
| Another form layout | Start a new project and design custom fields and masks. | Use an extraction type for that layout and review its suggestions. |

QwikCap does not switch readers automatically. A HIT-6 page can occur in more than one packet and does not identify the reader by itself.

## Review SIH clinic forms

This walkthrough uses the new `sih_clinic_dataset` packet. The [full clinic guide](docs/SIH_CLINIC_WORKFLOW.md) includes all five train groups, spreadsheet options, and troubleshooting. The earlier PACE accuracy table below does not measure this clinic reader.

1. Open a clinic-enabled QwikCap build. Save an existing project, then choose **File > New project**.
2. Choose **Advanced > Form type > Read SIH clinic forms**. If that menu item is absent, the build predates this reader.
3. Choose **Add documents… > Combine PDFs for one patient…**. From `datasets/sih-clinic-synthetic/train/forms/`, select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`.
4. Enter `1031` in **Study record_id**. Check the **Research Study ID** in registration `doc_11.pdf`. Verify that the other PDFs have the same MRN, name, and birth date. Those pages do not each print the study ID. Keep the listed order, check the same-patient confirmation, and click **Combine into one patient row**.
5. Review each suggested answer beside its original source. Correct an error, then click **Confirm & next**. A missing or unmentioned answer is not automatically `0` or No. Follow the displayed validation message if a required value cannot be verified.
6. Enter your **Reviewer** name and click **Approve document**. The queue should show one approved patient row for `1031`.
7. Open **Map & export** and click **Use fields as columns**. The 512 field names map to matching columns automatically. Inspect the populated preview, then click **Confirm column mapping** and **Export XLSX…**.
8. Open your new workbook. The first trial should contain one data row and 512 headers. Compare it with the original PDFs and the matching train answer keys. Keep a note of raw extraction errors and your corrections. Save the project separately if you want to retain sources and review work.

The registration sheet supplies the study-ID link. MRN is a separate identifier and keeps leading zeroes. Unprinted completion fields and unmentioned narrative findings must not be filled from assumptions. The current source packet uses native PDF text, including handwriting-style fonts. It does not establish real handwriting or scan-only recognition.

## Results on the supplied SIH clinic packet

These results use your actual `sih_clinic_dataset` packet. All 111 original PDFs, including forms, answer keys, and index, are included byte for byte with [hashes and independent expectations](datasets/sih-clinic-synthetic/README.md). Generated practice fixtures remain separate.

| Check | Train | Held-out test |
| --- | --- | --- |
| Actual forms / pages / patient rows | 28 / 43 / 5 | 27 / 42 / 5 |
| Strict original exact-key destination values | 558 / 572, **97.55%** | 495 / 508, **97.44%** |
| Mapped values after documented test-key shorthand expansion | 558 / 572, **97.55%** | 500 / 524, **95.42%** |
| Strict complete patient-grid cells, including blanks and zeroes | 2,379 / 2,560, **92.93%** | 2,439 / 2,560, **95.27%** |
| App-written export cells faithful to reviewed project | 2,560 / 2,560 | 2,560 / 2,560 |
| Manual value edits | 0 | 0 |

The test key contains one `none checked` wildcard, expanded into 16 exact catalog columns for comparison. Strict complete-key checks remain **failing**, with 181 train and 121 test grid differences. Missing reader codes, unmentioned negative findings, three uncomputed threshold negatives in each split, and retained source punctuation explain those differences. The [dated report](docs/testing/SIH_CLINIC_2026-11-19.md) gives every denominator and the coverage reconciliation. Export fidelity does not mean every key field was extracted.

Both native Mac workflows loaded every original form, confirmed applicable fields, approved five patient rows, confirmed the 512-column mapping, and exported Excel. The [train](examples/qwikcap-sih-clinic-train-readout.xlsx) and [test](examples/qwikcap-sih-clinic-test-readout.xlsx) readouts preserve those app outputs. The reader was frozen at `e2fbd2e` before test access. Later hardening from invented uncertainty and negation examples is documented separately, with regression replay rather than a new held-out claim. The test set has now been used.

Windows uses native CI and packaged generated-fixture checks. A person-driven workflow with this packet on a Windows laptop remains unverified. Repeating-instrument REDCap import and real-study approval remain separate work.

## Review the original NEU clinic packet

1. Save your current project. Choose **File > New project**, then **Advanced > Form type > Read NEU clinic forms**. The banner reads **NEU clinic forms · review required**.
2. Choose **Add documents… > Import separate forms…**. Select PDFs from the original `dataset/train/forms/` folder. For an initial trial, select `doc_01.pdf` and `doc_03.pdf`. Keep answer keys and the index out of document upload.
3. Select a document in the queue. Review the source identity and each applicable answer. Correct any suggestion that differs from the source, then click **Confirm & next**. The source document ID is derived by the app; review the printed MRN, name, birth date, and form date separately.
4. Enter your reviewer name and click **Approve document** for each document. Use the matching files in `dataset/train/answer_keys/` to check your work independently.
5. Open **Map & export** and click **Use fields as columns**. This creates the 45-column NEU staging workbook and assigns matching names automatically. Inspect the populated preview, click **Confirm column mapping**, and choose **Export XLSX…**.
6. Open the saved workbook. If you approved both trial documents, it contains two data rows. Each row represents one source document. Questions from other instrument families remain blank on that row.

If clinic forms were imported under the PACE reader, choose **Read NEU clinic forms** and confirm the rule change. QwikCap reprocesses the existing sources and clears prior field confirmations, approvals, and mapping confirmation. Keep a saved copy first if you want to retain the earlier project.

The NEU output is document staging. It does not combine the forms into the PACE patient-row contract or establish a REDCap import mapping. Use the PACE walkthrough below only for the separate PACE packet. The recorded 512-column train/test rates apply to that PACE packet.

## Review supplied PACE forms

Use **Read PACE printed forms** only for the earlier `sih_dataset` packet in `datasets/sih-synthetic/`. The [complete PACE printed walkthrough](docs/PACE_PRINTED_WALKTHROUGH.md) retains its patient groups, source review, Excel export, and verification commands.

For the current `sih_clinic_dataset`, follow the [SIH clinic walkthrough](docs/SIH_CLINIC_WORKFLOW.md) and select **Read SIH clinic forms**. Similar filenames do not make the layouts interchangeable.

## Results on your supplied train/test packet

These historical results belong to the earlier PACE printed packet, `sih_dataset`. They are not accuracy results for the new `sih_clinic_dataset` reader. Clinic results require their own train and test evaluation record.

The [included packet](datasets/sih-synthetic/README.md) contains the original user-supplied forms and answer keys, copied byte for byte. It is entirely fictional. It contains 28 train forms, 27 test forms, 55 matching answer-key PDFs, and the original index. These results come from that packet, not the app-authored practice forms.

The evaluation ran on 2026-11-18. Each split contains five patient groups and nine instruments. Train has 45 form pages and test has 40. The reader was frozen at `26fb90e` before test access. No engine or extraction-rule tuning was made from test answers.

| Check | Supplied train set | Supplied test set |
| --- | --- | --- |
| Raw extraction of mapped answer-key values | 600 / 600, **100%** | 550 / 551, **99.82%** |
| Additional source-observed unchecked-checkbox zeroes | 483 / 483, **100%** | 390 / 390, **100%** |
| Raw patient-row destination cells, before correction | 2,560 / 2,560, **100%** | 2,559 / 2,560, **99.96%** |
| Reviewed app-written Excel cells | 2,560 / 2,560, **100%** | 2,560 / 2,560, **100%** |
| Manual value corrections | 0 | 1 |
| Key-only total-score entries without a destination column | 9 excluded | 8 excluded |

The 2,560-cell denominators cover five rows by 512 destination columns, including expected blanks and checkbox zeroes. They are export-fidelity measures and do not mean 2,560 independently populated answers. The mapped-key result is the narrower raw extraction measure. A literal test-key wildcard for `none checked` expands to 16 canonical checkbox destinations in the independent comparator. The [packet evaluation notes](datasets/sih-synthetic/README.md) preserve both the literal and normalized expectations.

The single test error is `personal_ctdisorder_v2`. The reader suggests `hypermobility` while the source says `Joint hypermobility`. Source review restored the omitted word through the native app. Every other value and all original source data remained unchanged. Reviewed 100% export accuracy includes this manual correction and is separate from raw extraction accuracy.

Both native Mac workflows imported every supplied form, confirmed all applicable fields, approved five patient rows, confirmed the exact 512-column mapping, and exported XLSX. The [train workbook](examples/quickcap-actual-train-readout.xlsx) and [reviewed test workbook](examples/qwikcap-supplied-test-reviewed-readout.xlsx) are actual app exports. [Train evidence](docs/testing/actual-pace-dataset-2026-11-18.md) and [test evidence](docs/testing/heldout-pace-2026-11-18.md) record the hashes, raw failure, review correction, and limits.

Actual supplied-dataset desktop QA ran on Mac. Windows acceptance used generated fixtures and packaged checks. A person-driven Windows walkthrough of this packet remains outstanding. The test set has now been used, so later tuning needs a fresh holdout before claiming another independent test score.

To verify the included workbooks from a configured clone, run:

```sh
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/train-expected.json --census-json datasets/sih-synthetic/evaluation/train-form-census.json --xlsx examples/quickcap-actual-train-readout.xlsx
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/test-expected-comparator.json --census-json datasets/sih-synthetic/evaluation/test-form-census.json --xlsx examples/qwikcap-supplied-test-reviewed-readout.xlsx
```

The separately [generated practice kit](examples/pace-synthetic-practice.zip) and [its historical report](docs/testing/SYNTHETIC_PACE_GUI_2026-11-18.md) remain supplemental regression material. Their results are not the supplied-packet success rates above. For another AI or developer, [the handoff](docs/HANDOFF.md) provides the source map, continuation steps, and evaluation boundaries.

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

On macOS, open `QwikCap.app`. Keep the whole app bundle together. On Windows, open `QwikCap\QwikCap.exe` and retain the entire `QwikCap` folder, including its dependencies and companion worker. Copying only the `.exe` is insufficient. A packaged build includes Python and its runtime dependencies; the source launchers below are not needed.

The macOS build compiles the included `native_ocr.swift` adapter into an executable and bundles it with Apple Vision OCR. It does not need Swift on the computer running the packaged app. Optional Tesseract discovery checks `PATH`, then the standard Homebrew locations on macOS or standard installations on Windows. An explicit `FORMBRIDGE_TESSERACT` executable path takes precedence. An invalid explicit path disables OCR instead of silently selecting another engine. Tesseract needs English language data and is not bundled or downloaded by the app. Tesseract 5.5.3_1 was installed with operator approval for the current Mac run. Without a working OCR engine, scans remain available for manual review and entry; text PDFs can still use their text layers.

These are development builds without distribution signing or notarization. The current Windows x64 runtime passes all 12 native and packaged checks, including five fictional scans and independently reopened spreadsheet exports. The current source suite passes 316 tests on both platforms, with platform-specific skips. See [the current package evidence](docs/testing/SIH_CLINIC_HARDENING_2026-11-19.md) for the verified runtime, documentation-only Windows repack, and download hashes. A complete person-driven workflow on a Windows laptop remains a pilot check.

On 2026-11-13, a fresh macOS arm64 environment installed the unchanged runtime and build pins and passed all 156 source tests. That earlier `QuickCapCV.app` built, and the source and packaged-worker custom-mask checks each passed all ten groups. Later PACE and Windows work has separate [recorded results and limits](docs/TESTING.md). Mouse-drag mask creation and real-study REDCap import remain unverified.

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

The result is `dist/macos/QwikCap.app`. PyInstaller also leaves its supporting `dist/macos/QwikCap` directory. Distribute the complete `.app` bundle. The console worker is built first, then included in the GUI bundle under `helpers`. Both the GUI and its document worker include the PACE catalog. The compiled OCR helper is included with both processes.

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update(); root.destroy()"
.venv\Scripts\python.exe build_desktop.py --work-dir work\desktop-build --dist-dir dist\windows
```

The result is `dist\windows\QwikCap\QwikCap.exe` with its adjacent dependencies. Distribute the complete `QwikCap` directory. Windows packages do not include Apple Vision or Tesseract.

The builder checks that the GUI, companion worker, source modules, samples, and spreadsheet directory exist before building. It requires the installed PyInstaller version pinned in `requirements-build.txt`. Each run uses a new intermediate directory. If the selected destination already contains `QwikCap` or `QwikCap.app`, choose another `--dist-dir`; the builder preserves existing output. Retained work directories can be inspected or removed manually after review.

The manually dispatched [Windows workflow](.github/workflows/windows-build.yml) builds and verifies the portable ZIP on Windows with fictional fixtures. Its 12 checks include native startup, required local OCR, custom masks, patient bundles, both packaged PACE and SIH clinic readers, and spreadsheet values after extraction outside the checkout. It retains notices and a component inventory. It has no push, pull-request, or schedule trigger and does not publish releases. `desktop-build.yml` remains an older inactive matrix template.

## Local data and review limits

Documents, extracted values, and source pages are processed locally. Workers use private temporary storage; a crash can leave temporary files. Saved projects and exported spreadsheets persist where you save them, and project files include the source documents. The prototype does not provide managed access controls, encryption at rest, tamper-evident audit trails, or a compliance determination. Use fictional data until the full environment and workflow are approved for the intended research use.

LLM extraction, learning from corrections, and camera capture are not implemented. [The LLM privacy proposal](docs/LLM_PRIVACY.md) describes future requirements and does not change the current app.

See `README_BROWSER.md` for field definitions, input limits, spreadsheet restrictions, and the earlier browser workflow. This desktop build kit includes the native launchers; the earlier browser interface is a separate delivery.

## Private repository

This repository is proprietary. See [OWNERSHIP.md](OWNERSHIP.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [FIXTURES.md](FIXTURES.md). Pilot and collaboration documents under `docs/` are proposals for review. Customer builds and feedback do not include core source access by default. The Windows workflow runs only when manually dispatched. `desktop-build.yml` remains an inactive template outside `.github/workflows/`. See [docs/BUILD_ENVIRONMENT.md](docs/BUILD_ENVIRONMENT.md) for current exact-pin evidence, the historical dependency snapshot, and distribution license and notice work. QwikCap is a working name pending public name clearance.
