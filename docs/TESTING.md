# Testing and portable evidence

## Current SIH clinic validation, 2026-11-19

The current target is the supplied `sih_clinic_dataset/` packet, copied as [datasets/sih-clinic-synthetic](../datasets/sih-clinic-synthetic/README.md). Select **Read SIH clinic forms**, the `sih-clinic-v1` profile. The [clinic walkthrough](SIH_CLINIC_WORKFLOW.md) covers patient grouping, source review, mapping, and export. The older PACE and NEU packets require their own readers.

The [master clinic report](testing/SIH_CLINIC_2026-11-19.md) records the frozen evaluation at source `e2fbd2e`. Native train acceptance preceded a 72-file freeze at `2026-11-19T10:10:31.871790Z`. The freeze commit `e5bf722` preceded test and index access. All 72 files remained unchanged through the native test export at `2026-11-19T10:28:00.534537Z`. The [completion snapshot](testing/SIH_CLINIC_FROZEN_EVALUATION_COMPLETE_2026-11-19.json) records that historical boundary.

Train covers 28 forms, 43 pages, and five patients. Test covers 27 forms, 42 pages, and five patients. Native Mac review confirmed 926 train and 893 test fields, approved every patient, confirmed the mapping, and exported five rows with 512 columns per split. There were zero manual value edits. Independent [train](testing/SIH_CLINIC_TRAIN_NATIVE_2026-11-19.json) and [test](testing/SIH_CLINIC_TEST_NATIVE_2026-11-19.json) audits match all 2,560 typed cells in each workbook to the actual saved project and verify every original PDF hash.

Strict train agreement is 558/572 mapped key values, 97.55%, and 2,379/2,560 full-grid cells. Strict test agreement is 495/508 original exact-key destination values, 97.44%. Expanding one test-key wildcard to 16 catalog checkbox columns yields 500/524, 95.42%, and 2,439/2,560 full-grid cells. Both strict complete-key comparisons fail. Export fidelity remains 2,560/2,560 for each actual reviewed project. Keep these measures separate.

The [train](testing/SIH_CLINIC_TRAIN_RECONCILIATION_2026-11-19.json) and [test](testing/SIH_CLINIC_TEST_RECONCILIATION_2026-11-19.json) reconciliations explain unsupported reader codes, retained source punctuation, conservative blanks for unasserted findings, and three threshold-negative coverage gaps per split. The master report records the literal and normalized key denominators. Neither answer keys nor absent assertions supply app values.

## Post-evaluation hardening and current packages

Independent invented cases found false positives for uncertain narrative findings and negated procedure terms after the frozen evaluation ended. The regression commit is `4c41fb3`; the fix is `da33054`. The current Mac source suite passes 316 tests with seven Windows-only skips. The [hardening record](testing/SIH_CLINIC_HARDENING_2026-11-19.md) records the regression cases, all-55-form replay, current package checks, and archive hashes. This later replay is a regression check on used material, not a fresh held-out evaluation.

The [current Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44506631638) targets the hardened runtime. The earlier [frozen-source run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44501222833) passed 311 tests with one POSIX-only skip and all 12 gates. The [clinic release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19) uses the hardened runtime rather than that earlier binary. Windows generated-fixture checks do not establish an actual-packet Windows GUI walkthrough. Mac arm64 is the packaged Mac target; Intel Mac support and notarization remain unverified.

## Reproduce the generated clinic check

Run from the source environment described in [GETTING_STARTED.md](GETTING_STARTED.md).

```sh
.venv/bin/python -B tools/verify_sih_clinic.py --output verification/sih-clinic-source
.venv/bin/python -B tools/verify_sih_clinic.py --bundle dist/macos/QwikCap.app --output verification/sih-clinic-bundle
```

On Windows, use `.venv\Scripts\python.exe`, `tools\verify_sih_clinic.py`, and `--bundle dist\windows\QwikCap`. The tool generates invented registration and HIT-6 forms. It reads no supplied documents, answer keys, or manifest. Its seven groups check the explicit profile, transactional identity rejection, 14 literal fields, confirmation and mapping gates, independently reopened CSV and XLSX, and project reopening. Each export has one patient row and 512 columns. The two exports provide 1,024 cell comparisons.

`--bundle` exercises the actual packaged companion through `DesktopSession`. It does not launch the native UI or establish that menus and file dialogs work. Native testing found a separate clinic import guard that rejected the reader before file selection. The regression in `tests/test_desktop_reader_ui.py` now calls the actual callback, and `desktop.py` uses the shared patient-profile predicate.

For raw diagnostics on the supplied clinic train forms, run:

```sh
.venv/bin/python -B tools/extract_pace_dataset.py --profile sih-clinic-v1 --forms-dir datasets/sih-clinic-synthetic/train/forms --output verification/clinic-train-raw.json
```

The default profile of this historical tool remains `pace-printed-v1`. Always pass `--profile sih-clinic-v1` for the clinic packet. The command reads forms, not keys, and creates neither approvals nor an app export. Compare actual app projects or workbooks separately with `tools/verify_actual_pace_readout.py` and the clinic packet's audited expectations.

The clinic pages contain native text and handwriting-style fonts, circled options, checkbox marks, tables, and report narratives. They do not measure real handwriting or scan-only OCR. Do not fill source omissions from answer keys, infer every unmentioned finding as zero, or manufacture REDCap completion and reader codes. Keep raw suggestions, source-confirmed manual edits, and reviewed export fidelity separate.

## Historical QwikCap packages, 2026-11-19

The [rename and supplied-packet regression](testing/QWIKCAP_REBRAND_2026-11-19.md) records native Mac startup, 283 passing source tests with seven Windows-only skips, packaged printed-reader checks, and unchanged extraction on all 55 supplied forms. The [QwikCap Windows record](testing/QWIKCAP_WINDOWS_2026-11-19.md) records all 11 acceptance stages, 283 tests with one POSIX-only skip, and an independent audit of the actual portable ZIP. These presentation and packaging changes do not claim a fresh held-out evaluation.

## Earlier PACE evaluation packet in the clone

The [earlier supplied PACE packet](../datasets/sih-synthetic/README.md) includes 111 unchanged PDFs, seven independent evaluation JSON files, hash manifests, and reproduction commands. The [train app export](../examples/quickcap-actual-train-readout.xlsx) and [reviewed test app export](../examples/qwikcap-supplied-test-reviewed-readout.xlsx) are included unchanged. These are the sources for the historical PACE rates in the [README](../README.md#results-on-your-supplied-traintest-packet). The generated practice kit and the new clinic packet are separate.

The dated reports below retain their historical build names and runtime freeze. Current QwikCap naming and packaging changes do not relabel those measurements as another fresh held-out test. The test set has been used. Future tuning requires fresh held-out material for an independent score.

## Printed PACE reader and actual-dataset checks, 2026-11-18

The [actual train report](testing/actual-pace-dataset-2026-11-18.md) and [held-out report](testing/heldout-pace-2026-11-18.md) distinguish raw suggestions from reviewed desktop exports. Train used 28 PDFs and no manual value corrections. Held-out evaluation used 27 PDFs and one source-confirmed text correction. Each native Mac workbook contains five patient rows and the exact 512 headers, with all 2,560 destination cells independently verified. The reader was frozen before held-out access; the one raw word omission remains a known failure.

The [Windows printed-reader record](testing/WINDOWS_PRINTED_PACE_2026-11-18.md) covers source `b139c46`, with the same frozen runtime as `26fb90e`. Its 283 tests ran with one POSIX-only skip and all 11 acceptance stages passed. The packaged printed-form fixture verifies the catalog inside the companion worker. Generated Windows fixtures and Mac actual-dataset UI acceptance are separate scopes.

## Earlier PACE and OCR preview, 2026-11-18

Source `0793411` passed [Windows acceptance](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44407671706) with 238 tests and one POSIX-only skip. The [private prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-pace-2026-11-18) retains the verified portable ZIP and checksum. Its [summary record](testing/SYNTHETIC_PACE_WINDOWS_2026-11-18.json) separates source tests, packaged fixtures and the smaller PACE smoke check. All ten stages passed, including native startup, Unicode paths, a separate no-OCR path, and source/packaged custom-mask checks.

The full [Mac GUI practice run](testing/SYNTHETIC_PACE_GUI_2026-11-18.md) used 18 fictional PDFs and two patients with all 512 fields. Its app-written Excel matches all 1,024 values after six manual scan corrections; raw scan extraction is 506/512. The Windows PACE smoke test maps 12 fields into one 512-column patient row and checks CSV and XLSX separately. Do not equate those two test scopes. The later Mac package reopened and saved the reviewed project with all 1,024 values preserved and approvals reset as designed. That earlier Mac source suite passed 238 tests with seven Windows-only skips.

## Windows portable build, 2026-11-18

The [Windows build record](testing/WINDOWS_BUILD.json) links the successful
[Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44374387855)
at `f9eb862`. The runner used Windows Server 2022 x64, Python 3.12.10, Tk 8.6.15
and the declared package pins. All 219 source tests ran successfully; the one
POSIX-only process test was skipped. The final source also passed 219 tests on
Mac with seven Windows-only skips.

The actual portable ZIP was extracted outside the checkout into a folder with
spaces, Chinese characters, an accented name and an emoji. Its native GUI and
companion worker ran with only System32 on `PATH`. The GUI initialized an empty
workspace and rendered the 512-field PACE catalog using its bundled resources.
The verification tools used an explicitly located development Python parent;
the GUI and companion executables used their bundled runtimes.

The [Windows results](testing/WINDOWS_RESULTS.json) record real process-tree
cancellation, a locked destination save, Unicode project save/reopen, all five
scanned fixtures through operational Tesseract, and a separate no-OCR manual
review path. Source and packaged custom-mask checks passed ten groups each;
PACE checks passed nine each. The packaged fixture regression matched 60 fields
and 240 independently reopened export cells. PACE combined two fictional PDFs
into one row and matched all 512 CSV and XLSX cells, 1,024 cells in total.

Windows execution found and corrected two platform issues. OCR now reads a
binary image stream instead of passing its Unicode filename to Tesseract.
XLSX preflight validates original ZIP names before Windows separator
normalization or NUL truncation; the hostile fixtures now preserve raw bytes.
An initial version-label check was also corrected to match the pinned vendor.

An independent static review checked the downloaded ZIP checksum, both x64
executable headers, all 24 approved resources, 32 notice files and the native
inventory. The embedded inventory is a superset: 124 hashed archive entries,
including 75 native files. See [archive verification](testing/WINDOWS_ARCHIVE.json).
Tesseract was installed separately on the disposable runner and is not bundled.
The Windows build is unsigned. A complete person-driven workflow on a client
Windows laptop, handwriting, and live-study REDCap import remain unverified.
The PACE repeating-instrument conversion restriction still applies.

## Earlier Mac evidence

The 2026-11-17 PACE update adds [patient-bundle acceptance](../tools/verify_pace_flow.py). It generates two fictional forms, combines them as one patient record, verifies instrument-specific codes and date normalization, and independently reopens all 512 CSV and XLSX destination cells. The reference codebook and any train/test dataset are not read by the acceptance tool. See [PACE_WORKFLOW.md](PACE_WORKFLOW.md) for the workflow and the repeating-instrument import restriction. Current PACE results are recorded separately from the historical checks below.

The final Mac source suite passed 208 tests. Both [source acceptance](testing/PACE_SOURCE_MACOS.json) and [packaged-worker acceptance](testing/PACE_BUNDLE_MACOS.json) passed nine groups. The [current build record](testing/PACE_BUILD_MACOS.json) records exact pins, source/resource hashes, native coverage and remaining limits. [The full unit output](testing/PACE_UNIT_MACOS.txt) is retained. Native checks covered catalog search, patient grouping, source display and project reopening. Desktop automation did not establish the complete native source-to-export path or mask drawing/coordinate entry. Those remain manual target-platform checks.

Run commands from the repository root using the Python 3.12 environment described
in [GETTING_STARTED.md](GETTING_STARTED.md). Use fictional fixtures. Tests and
verifiers do not establish suitability for patient data or a live REDCap
workflow.

On 2026-11-13, all 156 source tests passed in a fresh macOS arm64 environment
with Python 3.12.14, Tk 9.0, and the unchanged runtime and build requirement pins.
See [the environment record](testing/ENVIRONMENT_MACOS.json) and
[unit-test output](testing/UNIT_TEST_RESULTS_MACOS.txt). The source and packaged
worker also passed all ten custom-mask acceptance groups, and the final Mac app
built. The records are [source results](testing/CUSTOM_MASK_SOURCE_MACOS.json),
[bundled-worker results](testing/CUSTOM_MASK_BUNDLE_MACOS.json), and
[build and branding results](testing/BUILD_MACOS.json).

The final packaged fictional-fixture regression also matched 60 extracted fields
and 240 cells across four independently reopened exports. See
[the packaged fixture report](testing/STANDARD_BUNDLE_MACOS.json).

These results cover the recorded Mac configuration. They do not validate a new
machine, Windows, native mouse drawing, or real-study REDCap import. Record the
interpreter, dependency versions, OS, command, and actual result for each new
run. [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) preserves the earlier
`cfd0762` snapshot and its three package-version mismatches as historical evidence.

## Source checks

macOS:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python verify_samples.py
.venv/bin/python verify_spreadsheet_flow.py
.venv/bin/python tools/verify_custom_masks.py
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe verify_samples.py
.venv\Scripts\python.exe verify_spreadsheet_flow.py
.venv\Scripts\python.exe tools\verify_custom_masks.py
```

`verify_samples.py` processes the bundled fictional practice forms.
`verify_spreadsheet_flow.py` independently reopens its generated practice exports;
it writes ignored outputs in `spreadsheets/` and its report under `verification/`.
Scanned practice forms require working local OCR. The custom-mask verifier uses
new text-layer PDFs and does not need OCR or native UI controls.

## Independent custom-mask acceptance

`tools/verify_custom_masks.py` derives normalized coordinates from its own
ReportLab drawing geometry and checks them against an independent answer key.
It generates two fictional two-page shipping forms with four fields each, plus
same-label distractors outside all selected masks. It does not read a dataset,
old workflow report, existing form layout, or saved project.

The default output is ignored `verification/custom-masks/`. Use `--output` to
select another local evidence directory. The output includes generated PDFs,
the answer key, reusable and malformed type examples, projects, CSV/XLSX exports,
and `custom-mask-results.json`. These outputs are replaceable test artifacts;
keep them out of commits. The process returns nonzero on failure and reports
the number of completed check groups.

The verifier retains ten acceptance groups:

1. Blank startup and blank-project roundtrip.
2. First PDF rendering and exact extraction from four custom masks.
3. A strict saved-type allowlist, including absence of filenames and answers.
4. Fresh-session type reuse, exact second-form values, explicit review gates,
   and independently reopened CSV and XLSX headers and cells.
5. Project restoration of definitions and sources, with review gates cleared.
6. Export blocked during editing; applying edits reprocesses and clears gates.
7. Invalid type files rejected without changing live state.
8. Missing-page inputs blocked from processing or approval and export.
9. Incompatible aspect ratios blocked from processing or approval and export.
10. Invalid draft application rejected transactionally; discarding an edit
    preserves the applied type.

To exercise a real packaged companion worker, first build on its target OS, then
run both worker checks. Example for macOS:

```sh
.venv/bin/python verify_desktop_bundle.py dist/macos/QwikCap.app --output verification/bundle
.venv/bin/python tools/verify_custom_masks.py --bundle dist/macos/QwikCap.app --output verification/custom-masks-bundle
```

On Windows, pass `dist\windows\QwikCap` with the Windows environment's Python.
`--bundle` selects the existing bundled worker; it does not mock worker results,
launch the GUI, install anything, or create a network listener. On macOS the
worker check removes `PATH` inside the verification context to exercise the
packaged helper without relying on a Swift command at runtime.

## Native workflow checks still required

Historical build records include checks of the app name, header, and About
dialog. Those checks establish branding only. The clinic's complete native
source-to-export runs are recorded in the separate train and test evidence above.

Earlier macOS verification exercised the native coordinate-entry path and
source-to-export flow. Mouse-drag mask creation was not verified. The model
verifier above covers geometry and state transitions through `DesktopSession`;
it cannot establish that native drawing, resizing, focus, menus, scrolling, or
file dialogs behave correctly. Source UI tests also do not replace opening and
using the actual application.

For each target OS, manually exercise drawing and redrawing a mask, deletion,
coordinate entry, page navigation and zoom, keyboard commands, long-answer
editing, confirmation and approval, destination mapping, export, save/reopen,
and unsaved-change prompts. Independently compare exported cells with the
fictional pages and destination headers. Distribution signing/notarization and
live REDCap import remain unverified. The automated Windows execution above
does not establish the complete interactive client-laptop workflow.

## What to carry to another computer

Carry the source, pinned requirement files, fictional fixtures, test code, and
these instructions through Git. Regenerate fictional acceptance outputs on the
new machine. This gives inspectable inputs and repeatable checks without a full
workspace dump. Raw prior outputs may contain documents, reviewer names, paths,
or answers and are excluded. Keep any separately needed private project or type
outside Git and transfer it only through an approved channel.

The current implementation has no LLM extraction, learning from corrections,
camera capture, cloud extraction account, or live REDCap submission. Passing
source checks is evidence for the exercised local file workflow only. See
[HANDOFF.md](HANDOFF.md) for transfer scope and [LLM_PRIVACY.md](LLM_PRIVACY.md)
for proposed model requirements.
