# Continue QuickCap (CV) on another computer

The private repository is [pranavdabeast24/capitolinus-form-extraction](https://github.com/pranavdabeast24/capitolinus-form-extraction). The owner notice is **Property of Capitolinus Ventures**. QuickCap (CV) is a working label without commercial name clearance. Read [the naming record](COMPETITORS_AND_NAME.md) before public distribution.

## Current state, 2026-11-18

The native Python and Tk app processes documents locally, reviews values, and exports approved records to a confirmed spreadsheet mapping. It does not use an LLM, a cloud extraction account, a model download, or a remote fallback.

The completed synthetic PACE run uses two fictional cases and 18 PDFs. Each case covers all 253 source entries and all 512 destination columns. Raw extraction matched 512 of 512 text cells and 506 of 512 scan cells. The native Mac workflow corrected six scan values, confirmed every field, entered a reviewer, approved both records, confirmed the mapping, and saved the XLSX export. The [actual app readout](../examples/quickcap-synthetic-pace-readout.xlsx) has two data rows and 512 ordered columns. Independent checks matched all 1,024 cells, with no formulas, spreadsheet errors, or hidden rows or columns. All 38 date cells, 832 choice cells, 343 expected zeroes, and eight expected blanks were preserved. See [the run report](testing/SYNTHETIC_PACE_GUI_2026-11-18.md). The corrected export result must remain separate from raw OCR accuracy.

The final source suite ran 236 tests with seven skips and no failures, including the final UI changes and four negative tests for the read-only export verifier. The latest UI source compiles. The reviewed OCR pipeline SHA-256 is `e24e91624bcae61ec7f2b473cdc9bfaaffff15da515ef23e053787ec12a6dbec`. The UI changes add document navigation, spreadsheet navigation, and direct choice-code entry while retaining validation and approval gates. The current Mac run uses separately installed Tesseract 5.5.3_1. The older [Windows package](TESTING.md#windows-portable-build-2026-11-18) predates these OCR and UI changes. Its binary does not include the current source changes.

## Source map

| File or directory | Responsibility |
| --- | --- |
| `desktop.py` | Tk widgets, menus, focus, dialogs, review controls, and the serial command queue. |
| `desktop_model.py` | `DesktopSession`, type drafts, projects, patient bundles, and review operations. |
| `pipeline.py` | Bounded rendering, text extraction, local OCR, masks, typed candidates, and source evidence. |
| `form_types.py` | Strict extraction-type parsing, page geometry, and normalized masks. |
| `server.py` | Shared `Workspace`, validation, worker boundaries, spreadsheet state, and legacy browser endpoints. |
| `worker.py`, `template_worker.py`, `bundle_worker.py` | Separate document, spreadsheet, and PDF-bundle jobs. |
| `desktop_worker.py`, `runtime_paths.py` | Packaged worker dispatch and resource lookup. |
| `templates.py`, `field_catalog.py`, `neurology_profile.py` | Spreadsheet inspection, field metadata, and the earlier neurology profile. |
| `study_profiles/pace.json`, `spreadsheets/pace-import-template.csv` | Reference field metadata and exact destination headers, without patient rows. |
| `native_ocr.swift` | Apple Vision adapter compiled into Mac packages. |
| `branding.py`, `build_desktop.py` | Product identity and target-OS packaging with pinned installed tools. |
| `tests/`, `tools/`, `verify_*.py` | Synthetic source tests and portable acceptance checks. |

The Mac bundle identifier is `com.capitolinusventures.quickcapcv`. Older Formbridge builds use a different identifier. Target the intended executable and window explicitly when testing. Saved project and type formats keep their `formbridge-*` identifiers. `FormbridgeWorker` and `FORMBRIDGE_TESSERACT` also remain stable. Renaming the app does not migrate stored data.

## Set up and build

Clone while authenticated to an account with repository access. Use Python 3.12 with working Tk. Follow the root [README](../README.md) for separate macOS and Windows environment, dependency, launch, and build commands. [GETTING_STARTED.md](GETTING_STARTED.md) adds first-run guidance. Install the exact requirements explicitly. Neither launcher nor builder installs dependencies.

Source Mac OCR needs an existing Swift toolchain or Tesseract. Packaged Mac apps include the compiled Vision adapter. Optional Tesseract needs English language data. Discovery checks `PATH` and standard platform locations. `FORMBRIDGE_TESSERACT` can specify an executable, and an invalid explicit path blocks fallback. Windows packages include neither OCR engine. See [WINDOWS.md](WINDOWS.md) for the existing portable download and its limits.

Build on the target operating system after explicitly installing `requirements-build.txt`. Use a new distribution directory for each build. Keep the complete Mac `.app` or Windows application directory, including its worker and resources. Signing and Mac notarization remain unfinished.

## Reproduce the full practice-kit workflow

Extract [examples/pace-synthetic-practice.zip](../examples/pace-synthetic-practice.zip) into a local scratch directory. The kit contains its own `README.txt`, 18 PDFs, `synthetic-pace-extraction-type.json`, independent JSON and CSV answer keys, source-coverage ledgers, and generation proof. It contains no supplied train or held-out test documents.

1. Open the actual app and load `synthetic-pace-extraction-type.json` through **Load type**. Do not import an answer key as extraction input.
2. Combine the nine PDFs in `text/forms/` in filename order, 01 through 09, under study ID `SYNTH-PACE-0001`. Explicitly confirm that the sources belong together.
3. Combine the nine `scan/forms/` PDFs in the same order under `SYNTH-PACE-0002`. Each case has 26 source pages plus the app's operator ID cover.
4. Compare every suggested value with its source and the independent answer key. Correct errors through the app. Confirm each field, enter a reviewer name, and approve each patient row.
5. Choose **Use categories as columns**, inspect all 512 assignments, and confirm the mapping. Export XLSX through the app.
6. Independently reopen the workbook. Require exactly two data rows, the exact 512 ordered headers, and all 1,024 expected cells. Preserve blanks, zeroes, choice codes, and normalized dates. Record raw extraction and manual corrections separately.

The included readout is the accepted result from this native workflow. Long headers and identifiers can clip or wrap at the default column widths. Excel AutoFit and adjusted row heights improve readability without changing the data.

Useful menu shortcuts use Command on Mac and Ctrl on Windows. Shift-N and Shift-P move between documents. Shift-B opens the spreadsheet view. K confirms the current field and advances. Shift-R edits the reviewer, Shift-A approves, Shift-C creates category columns, Shift-M confirms mapping, and Shift-E exports XLSX. L focuses the current answer. Choice fields accept an exact code or a displayed option, and invalid codes remain blocked by validation.

The fixture exercises all branches for software coverage without asserting clinical applicability. Six display, calculation, or unavailable-attachment references stay outside the export. The 69 option columns with clipped or uncertain source labels test exact code transport without resolving missing wording. Printed checkbox codes are explicit observations, not checkbox-mark recognition. The output is a reviewed patient staging sheet. Repeating instruments, longitudinal events, and live REDCap import still need a separate validated conversion.

## Run portable checks

From the repository root on macOS:

```sh
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python verify_samples.py
.venv/bin/python verify_spreadsheet_flow.py
.venv/bin/python tools/verify_custom_masks.py
.venv/bin/python tools/verify_pace_flow.py
.venv/bin/python tools/verify_synthetic_pace_readout.py examples/quickcap-synthetic-pace-readout.xlsx
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. [TESTING.md](TESTING.md) describes evidence directories and packaged-worker arguments. The existing `tools/verify_pace_flow.py` generates a smaller patient-bundle smoke test. It does not reproduce the full 512-field, two-case GUI practice run above. The new `tools/verify_synthetic_pace_readout.py` reads the practice kit's literal expected rows and checks the XLSX headers, types, and values. It creates no app session, changes no approvals, and preserves the workbook bytes. Pass a newly exported workbook instead of the included readout to validate a repeat run. Keep generated source-bearing projects and raw verification output outside commits.

For a built Mac application:

```sh
.venv/bin/python verify_desktop_bundle.py dist/macos/QuickCapCV.app --output verification/bundle
.venv/bin/python tools/verify_pace_flow.py --bundle dist/macos/QuickCapCV.app --output verification/pace-bundle
```

These commands exercise the packaged worker without establishing GUI interaction. Recheck menus, focus, choice edits, drawing, approval, save prompts, and exports in the actual app after UI changes. Record the source revision, platform, dependencies, command, result, and skipped checks.

## Data and security boundaries

Only generated fictional practice inputs and selected summary evidence belong in this clone. Keep original attachments, private documents, source-bearing projects, reviewer details, raw screenshots, logs, credentials, environments, caches, and compiled packages outside Git. A saved project embeds source documents. An extraction type contains reusable rules and geometry instead of answers or source bytes.

The separately supplied synthetic dataset uses `train/forms`, `test/forms`, `answer_keys`, and `manifest.pdf`. The current task checked metadata for 28 PDFs in `train/forms`. It did not inspect their contents. The held-out test inputs remain untouched. Do not open or use `test/forms` or its answer keys for development without explicit authorization that changes this constraint. The practice kit is generated independently of this dataset.

Processing remains local, but the app does not provide managed access controls, encryption at rest, tamper-evident audit trails, or a compliance determination. Read [SECURITY.md](../SECURITY.md) and [LLM_PRIVACY.md](LLM_PRIVACY.md) before expanding use. Existing limits include 600 fields or destination columns, 32 pages per combined document, 16 source PDFs per patient bundle, a 1 MiB rule definition, 120 megapixels of aggregate rendering, and 128 MiB of generated assets. OCR calls retain a 45-second timeout and document workers a 180-second timeout. These are processing limits, not clinical validation.

## Next steps and historical context

Validate the later changes on Windows before replacing the recorded portable release. Repeat the practice-kit workflow on each new target configuration. Mouse-drag mask creation, handwriting, camera capture, learning from corrections, and live-study REDCap import remain unverified or unimplemented.

[history/CONVERSATION.md](history/CONVERSATION.md) and [history/WINDOWS_2026-11-18.md](history/WINDOWS_2026-11-18.md) preserve earlier sanitized context. Treat historical names, experiments, and test counts as records of their revisions. Current source and dated evidence take precedence. [COLLABORATION.md](COLLABORATION.md) and [PILOT_PLAN.md](PILOT_PLAN.md) remain proposals, without granting repository access or product approval.
