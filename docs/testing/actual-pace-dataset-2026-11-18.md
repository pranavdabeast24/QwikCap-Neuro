# Actual PACE dataset validation, 2026-11-18

This report concerns the separately supplied synthetic dataset. The earlier dense practice cards and their accepted workbook remain a separate check in [SYNTHETIC_PACE_GUI_2026-11-18.md](SYNTHETIC_PACE_GUI_2026-11-18.md).

## Acceptance status

Train acceptance is complete. The native desktop imported all 28 PDFs into five patient bundles, confirmed all 1,085 applicable fields, approved all five rows, confirmed the 512-column mapping, and wrote [the train workbook](../../examples/quickcap-actual-train-readout.xlsx). Independent checks of both its saved raw project and final workbook match all 2,560 destination cells. The workbook has zero issues and required zero manual value corrections. The frozen held-out raw run has one known text omission; native Mac review corrected it and the reviewed export passes all 2,560 cells. Independent Windows artifact audit confirms all 11 acceptance checks. These later results are detailed in [the held-out report](heldout-pace-2026-11-18.md).

The user confirmed that the forms and answer keys are entirely fictional or synthetic. The user authorized final held-out evaluation after train fixes and acceptance. The runtime was frozen at `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5` on `2026-11-18T23:45:26.040166Z`, before any test access. The [freeze snapshot](actual-pace-freeze-2026-11-18.json) records hashes for 37 source, rule, and dependency files. Extraction code and rules remain unchanged during held-out evaluation. The [train workbook comparison](actual-pace-train-xlsx-2026-11-18.json) and [separate raw coverage report](actual-pace-train-raw-2026-11-18.json) contain value-free diagnostics.

| Check | Current evidence | Limit |
| --- | --- | --- |
| Train form inventory | 28 original PDFs, 45 pages, nine instruments, five explicit patient groups. | Native text PDFs only. No embedded images or AcroForms. |
| Independent key audit | 28 key PDFs, 47 pages, 609 explicit values. | Keys are evaluation evidence, never app-imported answers. |
| Exportable key values | 600 of 600 match the final local extraction diagnostics. | A per-document extraction check does not prove a desktop export. |
| Unchecked checkbox values | All 483 expected zeroes match. | Zero requires a visible identified control. |
| Unmarked source rows | Two visibly unanswered optional periods rows stay blank. | These rows do not require a required-field exception. |
| Key-only totals | Nine entries have no supplied destination column. | `total28`, `total28_v2`, and `hit6_total` are not exported. |
| Mac source suite | 283 tests ran with seven Windows-specific skips and no failures. | Target-platform acceptance remains separate. |
| Required-answer gates | All 14 catalog-required flags and the record ID remain required. Independent review passes 27 adapter and session tests. | Source-confirmed blanks require immutable evidence and fresh explicit confirmation. |
| Packaged printed-form reader | Corrected companion passes 16 invented fields and 512 destinations. | This check uses the packaged worker, not the GUI. |
| Native raw project | All 28 PDFs imported into five bundles. All 2,560 destination cells match. | Zero manual value corrections. |
| Native review and export | All 1,085 applicable fields confirmed, five rows approved, and 512-column mapping confirmed through the GUI. | Synthetic QA workflow. No production or clinical-use claim. |
| Native train workbook | App-written XLSX passes all 2,560 destination cells with zero issues. | Five patient rows and 512 exact headers. Nine key-only totals remain outside the destination. |
| Source freeze | Commit `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5`, with 37 recorded file hashes, before any test access. | No extraction changes during evaluation. |
| Held-out raw evaluation | 550 of 551 mapped key values and all 390 additional checkbox zeroes match. Raw app project matches 2,559 of 2,560 cells. | One source text loses a word; see [the held-out report](heldout-pace-2026-11-18.md). |
| Held-out reviewed export | Native Mac workflow confirms 941 applicable fields, approves five rows, and exports a verified 2,560-cell XLSX after exactly one manual correction. | Reviewed result is separate from raw extraction accuracy. Eight key-only totals remain outside the destination. |
| New Windows acceptance | Independently audited [run 44424411229](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229) at `b139c46`: 283 source tests, one POSIX-only skip, all 11 acceptance checks passing. | Generated-fixture and packaged checks; actual-dataset desktop QA was on Mac. |

## Extraction behavior

The optional `pace-printed-v1` reader uses native PDF text, printed row boundaries, and visible square or circular controls. It associates radio marks with their labels and matrix columns. It preserves each instrument's code values, including nonsequential matrix codes. Custom masks remain the default workflow for other layouts.

The schema retains all 512 destination fields in the supplied order. Each processed record also has immutable source context and an applicable-field subset. That subset comes from observed source questions. An edited review value cannot remove a confirmation requirement or populate an absent question.

The existing patient bundle operation supplies an operator-entered study ID and a source manifest. The PACE reader compares each original PDF's printed identity with that ID and the other sources. Missing or conflicting identities, unknown instrument starts, repeated complete instruments, and conflicting values block the one-row merge. Reopening a saved project reconstructs metadata from the original PDFs and clears confirmations and approvals.

The reader distinguishes three source conditions. A visible identified unchecked checkbox can produce `0`. An absent or branch-hidden question stays blank and inactive. A visible unanswered radio stays blank and applicable. Ambiguous marks do not produce a guessed choice.

The reader preserves all 14 catalog-required flags and the required record ID. A source-confirmed blank requires a truly unmarked row, immutable `unansweredFields` metadata, matching `pace-unmarked-radio` evidence, and an explicit field confirmation. Reopening a project requires fresh confirmation. Independent review passes 27 adapter and session tests and a forged-project check that cannot bypass a required answer. The two blank periods rows in this train set are optional and do not need this exception.

## Train fixes and independent review

The native desktop reproduction imported an actual train Patient Records PDF. A rules-only three-field type read the record ID, but marked sex and race answers remained blank with a validation warning. Two source-checked manual corrections verified the simplified review and export route. That three-column smoke export is not full train acceptance.

The first complete independent comparison found 590 correct values among 600 exportable key entries. Ten values were missing. None of its nonblank suggestions differed from the keys. Fixes retained long medication labels until the row's first control, resolved repeated personal and family questions from normalized source references, and repaired specific clipped choice labels from authentic printed wording. The final diagnostics match all 600 exportable entries and all 483 expected unchecked zeroes.

Independent review also reproduced and closed these failures:

- An unknown later source could inherit the preceding instrument. New source boundaries now require a recognized instrument.
- Repeated assessments could merge when their answers agreed. Complete instrument occurrences now prevent that merge.
- Small triangles and diamonds could resemble checkbox bounds. The geometry reader now validates rectangular paths and circular outlines.
- Controls inside nested PDF objects lost ancestor transforms. Their geometry now includes the containing object transforms before conversion to page coordinates.
- The GUI package included the PACE catalog while its one-file worker omitted it. Both now include the catalog, and a new packaged-worker check reproduces the old failure.

The full source suite and focused generated reproductions pass. None of these checks establishes handwriting recognition, camera capture, scan-only selection decoding, or production clinical validation.

## Native desktop acceptance

The desktop run has imported the actual supplied 28 train PDFs into five confirmed patient bundles. The app-saved raw project passes an independent comparison of all 2,560 expected destination cells, with zero manual value corrections. The local comparison report is `train-ui-raw-comparison.json`.

The final desktop run confirmed all 1,085 applicable fields, approved the five patient rows, confirmed the 512-column mapping, and saved the XLSX through the app. No value corrections were needed. The independent workbook comparison checks all 2,560 destination cells and reports zero issues.

The final check verifies five patient rows, the exact 512-header order, identifier strings, date normalization, literal choice codes, numbers, zeroes, and expected blanks. It also rejects formulas, spreadsheet errors, active content, and hidden rows or columns. These final export results remain separate from per-document raw extraction metrics.

The validation workspace retains the app-written workbook at `outputs/actual-pace-2026-11-18/quickcap-train-readout.xlsx`. The repository includes a byte-identical copy at [examples/quickcap-actual-train-readout.xlsx](../../examples/quickcap-actual-train-readout.xlsx). Both have SHA-256 `f8aae166a92cbe5815f6008cf1fc85bc90651fbd5b47cb03e21198cb5f978a03`.

The nine key-only total-score entries stay outside this 512-column comparison. They remain explicit coverage omissions. Do not claim that all 609 raw key entries were extracted or exported when the result covers 600 mapped entries.

## Reproduce local checks

The repository contains source, fictional practice fixtures, and verifiers. The separately supplied dataset, audited expectation files, projects containing sources, raw screenshots, and logs remain outside Git. On another computer, transfer authorized dataset materials separately. Do not construct independent expectations from the reader's own output.

These commands use a configured Python environment, a POSIX shell, and fresh output paths. Replace the input paths with your approved local copies. In PowerShell, put each command on one line and use the configured Windows Python executable and Windows paths.

Inventory only the train split:

```sh
python tools/inventory_dataset.py \
	--split-root "/path/to/sih_dataset/train" \
	--output "/path/to/local-evidence/train-inventory.json"
```

Produce raw extraction diagnostics without opening keys, creating reviews, approving records, or writing a spreadsheet:

```sh
python tools/extract_pace_dataset.py \
	--forms-dir "/path/to/sih_dataset/train/forms" \
	--output "/path/to/local-evidence/train-extraction.json"
```

Verify an app-written workbook against independently audited key expectations and the forms census:

```sh
python tools/verify_actual_pace_readout.py \
	--expected-json "/path/to/local-evidence/train-expected.json" \
	--census-json "/path/to/local-evidence/train-form-census.json" \
	--xlsx "/path/to/local-evidence/app-written-train-readout.xlsx"
```

Use `--project-json` instead of `--xlsx` to inspect an app-saved project's patient values before or after review. Add `--extraction-json` to report per-document raw coverage separately. When raw diagnostics are requested, the tool returns failure if those diagnostics omit key-only totals, even when `readout_passed` is true. Inspect `readout_passed`, `raw_diagnostics_passed`, and the key-only counts separately.

Test a built Mac companion with an invented form:

```sh
python tools/verify_pace_printed.py \
	--helper "dist/macos/QuickCapCV.app/Contents/Frameworks/helpers/FormbridgeWorker" \
	--output "/path/to/fresh-packaged-reader-evidence"
```

On Windows, point `--helper` at the packaged `FormbridgeWorker.exe`. `tools/verify_windows_release.py` runs this check after extraction and relocation with the other Windows acceptance checks. Keep the complete application folder together.

## Held-out and Windows continuation

The train desktop export has passed and the runtime freeze preceded all test access. The authorized held-out raw evaluation found one text omission. The native Mac workflow corrected exactly that suggestion from the visible source, and its app-written reviewed workbook independently passes all 2,560 destination cells. All other values and original source data remain unchanged. All 37 frozen file hashes still match after final evaluation. No extraction engine, rule, or verifier changes were made to remove the raw failure. See [the separate report](heldout-pace-2026-11-18.md). Any later development using these answers requires a new evaluation scope and a new holdout.

Independent audit of the new Windows workflow at `b139c4656c2f9f9ce356c278830b4699a81beecd` confirms 283 source tests with one POSIX-only skip and all 11 acceptance checks passing. Its ZIP has SHA-256 `2da5c9fe56ace1a01373b49764511c152268173c75ea415217a9dc40246881f7`. The [printed PACE private prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-printed-pace-2026-11-18) is published, and its uploaded digest matches that ZIP. The historical prerelease at `0793411` predates this reader and UI. Actual-dataset desktop QA used the Mac build, and a person-driven Windows actual-dataset walkthrough remains outstanding.
