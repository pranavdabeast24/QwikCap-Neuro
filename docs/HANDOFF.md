# Continue QuickCap (CV) on another computer

The private repository is [pranavdabeast24/capitolinus-form-extraction](https://github.com/pranavdabeast24/capitolinus-form-extraction). The owner notice is **Property of Capitolinus Ventures**. QuickCap (CV) is a working label without commercial name clearance. Read [the naming record](COMPETITORS_AND_NAME.md) before public distribution.

## Current state, 2026-11-18

The native Python and Tk app processes documents locally, reviews values, and exports approved records to a confirmed spreadsheet mapping. It does not use an LLM, a cloud extraction account, a model download, or a remote fallback.

The current change adds an opt-in `pace-printed-v1` reader for the supplied printed PACE layouts. Custom masks remain the default. The reader uses native PDF text, row separators, and visible control outlines to decode radios, checkboxes, and matrix columns. Its schema contains all 512 destination fields, while each processed record has a source-derived applicable subset. The confirmed patient bundle path accepts variable instrument lengths without an absolute-page mask type.

Independent train diagnostics cover the actual supplied 28 PDFs and 45 pages. All 600 explicit key values with destination columns match, as do 483 expected checkbox zeroes. Two visible unmarked rows remain blank. Nine key-only totals, named `total28`, `total28_v2`, and `hit6_total`, have no destination column and remain outside the export. See [the actual-dataset report](testing/actual-pace-dataset-2026-11-18.md) for the measured scope.

The native desktop imported all 28 PDFs into five confirmed patient bundles, confirmed all 1,085 applicable fields, approved all five rows, confirmed the 512-column mapping, and exported [the train workbook](../examples/quickcap-actual-train-readout.xlsx). The app-saved raw project and app-written workbook each match all 2,560 expected destination cells with zero manual value corrections. The final workbook has zero verification issues. Its hash is in [the actual-dataset report](testing/actual-pace-dataset-2026-11-18.md).

Train acceptance is complete. The runtime was frozen at `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5` on `2026-11-18T23:45:26.040166Z`, before any held-out access. The [freeze snapshot](testing/actual-pace-freeze-2026-11-18.json) records hashes for 37 source, rule, and dependency files. All 37 hashes were verified unchanged before and after the authorized held-out raw run. The pushed revision `b139c4656c2f9f9ce356c278830b4699a81beecd` retains the frozen runtime files.

**The held-out raw reader has one known error.** The supplied 27 PDFs cover 40 pages, nine instruments, and five patient groups. Raw extraction matches 550 of 551 mapped key values and all 390 additional checkbox zeroes. The `personal_ctdisorder_v2` suggestion omits `Joint` from the fictional source text `Joint hypermobility`. Eight key-only total entries remain outside the 512-column destination. The app-saved raw project matches 2,559 of 2,560 destination cells. The native Mac workflow corrected exactly that one suggestion from the visible source, confirmed 941 applicable fields, approved five patient rows, confirmed all 512 column assignments, and exported XLSX. Independent verification matches all 2,560 reviewed cells with zero issues. All other values and original source data remain unchanged. No engine or rule tuning was made, and all 37 frozen file hashes still match after final evaluation. See [the held-out report](testing/heldout-pace-2026-11-18.md) for the reviewed workbook hash and evidence.

The Mac source suite ran 283 tests with seven Windows-specific skips and no failures. An independent review passes 27 adapter and session tests, including a forged-project check that preserves the required-answer gate. The final packaged PACE helper passes 16 invented fields and 512 destination values. Independent audit of the [new Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229) at `b139c4656c2f9f9ce356c278830b4699a81beecd` confirms 283 source tests with one POSIX-only skip and all 11 acceptance checks passing. The portable ZIP has SHA-256 `2da5c9fe56ace1a01373b49764511c152268173c75ea415217a9dc40246881f7`. Its GUI and worker have identical 512-field catalogs. All inventory hashes match across 76 native components, 125 embedded components, and 32 notices; this inventory is not a separate SPDX or CycloneDX SBOM. The historical release below is not a download for these new changes.

Actual train and held-out desktop QA used the Mac `research-mac-dist` app with the frozen runtime. Windows acceptance uses generated fixtures and packaged gates; it does not establish an actual-dataset Windows GUI walkthrough. The [published private prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-printed-pace-2026-11-18) targets the verified CI commit. The uploaded ZIP digest matches the independently checked package. Use the current [Windows guide](WINDOWS.md) for delivery instructions.

The interface has three menus and two tabs. Advanced controls default to hidden. The review action is **Confirm & next**, and the main export button follows the template format. Patient bundle rows use their confirmed IDs in the document queue. A new bundle opens for review after import.

## Earlier practice-kit evidence

The completed synthetic PACE run uses two fictional cases and 18 PDFs. Each case covers all 253 source entries and all 512 destination columns. Raw extraction matched 512 of 512 text cells and 506 of 512 scan cells. The native Mac workflow corrected six scan values, confirmed every field, entered a reviewer, approved both records, confirmed the mapping, and saved the XLSX export. The [actual app readout](../examples/quickcap-synthetic-pace-readout.xlsx) has two data rows and 512 ordered columns. Independent checks matched all 1,024 cells, with no formulas, spreadsheet errors, or hidden rows or columns. All 38 date cells, 832 choice cells, 343 expected zeroes, and eight expected blanks were preserved. See [the run report](testing/SYNTHETIC_PACE_GUI_2026-11-18.md). The corrected export result must remain separate from raw OCR accuracy.

The earlier source suite at `0793411` passed 238 tests with seven skips. Its OCR change retained block mode for single-column forms and used sparse mode for overlapping side-by-side masks. Native checks recovered all 30 fields across five legacy scans and preserved the dense case at 506 of 512 before review. The Mac run uses separately installed Tesseract 5.5.3_1. The [earlier private Windows prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-pace-2026-11-18) contains revision `0793411`. Its [Windows acceptance run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44407671706) passed 238 source tests with one POSIX-only skip and all ten then-current acceptance stages. That release predates the PACE printed-form reader and simplified UI. A person-driven Windows laptop walkthrough remains a pilot check.

## Source map

| File or directory | Responsibility |
| --- | --- |
| `desktop.py` | Tk widgets, menus, focus, dialogs, review controls, and the serial command queue. |
| `desktop_model.py` | `DesktopSession`, type drafts, projects, patient bundles, and review operations. |
| `pipeline.py` | Bounded rendering, text extraction, local OCR, masks, typed candidates, and source evidence. |
| `pace_profile.py` | PACE printed-row extraction, native control association, matrix codes, and immutable source context. |
| `extraction_profiles.py` | Canonical profile dispatch, source-derived applicability, identity checks, and instrument boundaries. |
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

Clone while authenticated to an account with repository access:

```sh
git clone https://github.com/pranavdabeast24/capitolinus-form-extraction.git
cd capitolinus-form-extraction
```

Use Python 3.12 with working Tk. Follow the root [README](../README.md) for separate macOS and Windows environment, dependency, launch, and build commands. [GETTING_STARTED.md](GETTING_STARTED.md) adds first-run guidance. Install the exact requirements explicitly. Neither launcher nor builder installs dependencies.

Source Mac OCR needs an existing Swift toolchain or Tesseract. Packaged Mac apps include the compiled Vision adapter. Optional Tesseract needs English language data. Discovery checks `PATH` and standard platform locations. `FORMBRIDGE_TESSERACT` can specify an executable, and an invalid explicit path blocks fallback. Windows packages include neither OCR engine. See [WINDOWS.md](WINDOWS.md) for the existing portable download and its limits.

Build on the target operating system after explicitly installing `requirements-build.txt`. Use a new distribution directory for each build. Keep the complete Mac `.app` or Windows application directory, including its worker and resources. Signing and Mac notarization remain unfinished.

Both the GUI and the one-file document worker need `study_profiles/pace.json`. Adding the resource only to the GUI lets the source tests pass while packaged extraction fails. `tools/verify_pace_printed.py` tests the actual companion executable to preserve this requirement.

## Continue from completed PACE acceptance

The native Mac train and reviewed held-out workflows each pass their independent 2,560-cell workbook check. The held-out reader still has its documented raw omission and required one manual correction. Preserve those separate results:

1. Keep raw extraction, the pre-correction project comparison, the single source-reviewed correction, and final workbook comparison as separate evidence. Do not report reviewed export accuracy as raw extraction accuracy.
2. Preserve the 37-file freeze record. Do not adjust extraction rules, the engine, or verifier to erase the held-out failure. Later development based on these answers requires a new evaluation scope and fresh held-out material.
3. Use the published printed PACE private prerelease and verify its recorded package hash. The historical `0793411` release predates the current reader and interface.
4. Perform a person-driven Windows laptop walkthrough, including the actual supplied fictional dataset, before claiming equivalent desktop acceptance there. Live-study REDCap import and production research approval remain separate work.

The PACE reader rejects missing or conflicting source identities, unknown instrument boundaries, repeated complete instruments, and conflicting values in a patient merge. It rebuilds source metadata from original PDFs on project reopening. Review values cannot alter field applicability or relax these checks. Keep those constraints in `extraction_profiles.py` and use record-aware validation at review, preview, approval, and export boundaries.

A checkbox zero requires a visible identified control. Missing or branch-hidden questions stay blank and inactive. Visible unanswered radios stay blank and applicable. Do not add an empty-to-zero default, infer a matrix code from its ordinal column, or resolve clipped labels through an answer lookup. Any alias must map authentic printed wording to a source field or choice code, without a patient ID or document filename.

Preserve the catalog's 14 required flags and the required record ID. A source-confirmed missing-answer exception requires a truly unmarked row, immutable `unansweredFields` metadata, matching `pace-unmarked-radio` evidence, and explicit field confirmation. Reopening a project requires fresh confirmation. An arbitrary blank or forged project metadata cannot satisfy that exception. The two blank periods rows in the actual train set are optional and do not need the exception.

## Reproduce the full practice-kit workflow

Extract [examples/pace-synthetic-practice.zip](../examples/pace-synthetic-practice.zip) into a local scratch directory. The kit contains its own `README.txt`, 18 PDFs, `synthetic-pace-extraction-type.json`, independent JSON and CSV answer keys, source-coverage ledgers, and generation proof. It contains no supplied train or held-out test documents.

1. Open the actual app and load `synthetic-pace-extraction-type.json` through **Advanced > Form type > Load extraction type…**. Do not import an answer key as extraction input.
2. Combine the nine PDFs in `text/forms/` in filename order, 01 through 09, under study ID `SYNTH-PACE-0001`. Explicitly confirm that the sources belong together.
3. Combine the nine `scan/forms/` PDFs in the same order under `SYNTH-PACE-0002`. Each case has 26 source pages plus the app's operator ID cover.
4. Compare every suggested value with its source and the independent answer key. Correct errors through the app. Confirm each field, enter a reviewer name, and approve each patient row.
5. Open **Map & export**, choose **Use fields as columns**, inspect all 512 assignments, and confirm the mapping. Export XLSX through the app.
6. Independently reopen the workbook. Require exactly two data rows, the exact 512 ordered headers, and all 1,024 expected cells. Preserve blanks, zeroes, choice codes, and normalized dates. Record raw extraction and manual corrections separately.

The included readout is the accepted result from this native workflow. Long headers and identifiers can clip or wrap at the default column widths. Excel AutoFit and adjusted row heights improve readability without changing the data.

Useful shortcuts use Command on Mac and Ctrl on Windows. Shift-U selects the PACE printed reader. Shift-I opens patient PDF selection. Shift-N and Shift-P move between records. Shift-B opens **Map & export**. K confirms the current field and advances. Shift-R edits the reviewer, Shift-A approves, Shift-C creates field columns, Shift-M confirms mapping, and Shift-E exports XLSX. L focuses the current answer. Choice fields accept an exact code or a displayed option, and invalid codes remain blocked by validation.

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

The actual-dataset tools accept explicit local paths. `inventory_dataset.py` checks one split without reading document text. `extract_pace_dataset.py` produces local raw diagnostics without opening answer keys, creating reviews, approving records, or exporting a workbook. `verify_actual_pace_readout.py` compares an app-saved project or an app-written workbook with independently audited expectations. Its optional extraction input reports raw coverage separately. See [the actual-dataset report](testing/actual-pace-dataset-2026-11-18.md) for commands and report semantics.

## Data and security boundaries

Only generated fictional practice inputs and selected summary evidence belong in this clone. Keep original attachments, private documents, source-bearing projects, reviewer details, raw screenshots, logs, credentials, environments, caches, and compiled packages outside Git. A saved project embeds source documents. An extraction type contains reusable rules and geometry instead of answers or source bytes.

The separately supplied dataset uses `train/forms`, `test/forms`, sibling `answer_keys` directories, and `manifest.pdf`. The user confirmed that all of its forms and keys are entirely fictional or synthetic. Train acceptance used the actual forms and audited keys. The runtime freeze preceded all held-out access. The user authorized final test evaluation with that reader. This does not authorize development against test answers. The generated practice kit remains separate from this dataset.

Processing remains local, but the app does not provide managed access controls, encryption at rest, tamper-evident audit trails, or a compliance determination. Read [SECURITY.md](../SECURITY.md) and [LLM_PRIVACY.md](LLM_PRIVACY.md) before expanding use. Existing limits include 600 fields or destination columns, 32 pages per combined document, 16 source PDFs per patient bundle, a 1 MiB rule definition, 120 megapixels of aggregate rendering, and 128 MiB of generated assets. OCR calls retain a 45-second timeout and document workers a 180-second timeout. These are processing limits, not clinical validation.

## Next steps and historical context

The Windows artifact is independently audited at `b139c46`, with all 11 acceptance checks passing, and its private printed PACE prerelease is published. Native Mac held-out export is complete after one documented source-reviewed correction. Retain the raw failure when continuing development. Repeat relevant scan and custom-mask regressions after later changes to the shared pipeline. Any future work based on the held-out answers needs a new evaluation scope and fresh holdout. Mouse-drag mask creation, handwriting, camera capture, learning from corrections, and live-study REDCap import remain unverified or unimplemented.

[history/CONVERSATION.md](history/CONVERSATION.md) and [history/WINDOWS_2026-11-18.md](history/WINDOWS_2026-11-18.md) preserve earlier sanitized context. Treat historical names, experiments, and test counts as records of their revisions. Current source and dated evidence take precedence. [COLLABORATION.md](COLLABORATION.md) and [PILOT_PLAN.md](PILOT_PLAN.md) remain proposals, without granting repository access or product approval.
