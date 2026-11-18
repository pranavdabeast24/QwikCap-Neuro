# Testing and portable evidence

## Current PACE and OCR preview, 2026-11-18

Source `0793411` passed [Windows acceptance](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44407671706) with 238 tests and one POSIX-only skip. The [private prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-pace-2026-11-18) retains the verified portable ZIP and checksum. Its [summary record](testing/SYNTHETIC_PACE_WINDOWS_2026-11-18.json) separates source tests, packaged fixtures and the smaller PACE smoke check. All ten stages passed, including native startup, Unicode paths, a separate no-OCR path, and source/packaged custom-mask checks.

The full [Mac GUI practice run](testing/SYNTHETIC_PACE_GUI_2026-11-18.md) used 18 fictional PDFs and two patients with all 512 fields. Its app-written Excel matches all 1,024 values after six manual scan corrections; raw scan extraction is 506/512. The Windows PACE smoke test maps 12 fields into one 512-column patient row and checks CSV and XLSX separately. Do not equate those two test scopes. The later Mac package reopened and saved the reviewed project with all 1,024 values preserved and approvals reset as designed. The current Mac source suite passes 238 tests with seven Windows-only skips.

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
.venv/bin/python verify_desktop_bundle.py dist/macos/QuickCapCV.app --output verification/bundle
.venv/bin/python tools/verify_custom_masks.py --bundle dist/macos/QuickCapCV.app --output verification/custom-masks-bundle
```

On Windows, pass `dist\windows\QuickCapCV` with the Windows environment's Python.
`--bundle` selects the existing bundled worker; it does not mock worker results,
launch the GUI, install anything, or create a network listener. On macOS the
worker check removes `PATH` inside the verification context to exercise the
packaged helper without relying on a Swift command at runtime.

## Native workflow checks still required

The current build record includes checks of the app name, header, and About
dialog. Those checks establish branding only.

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
