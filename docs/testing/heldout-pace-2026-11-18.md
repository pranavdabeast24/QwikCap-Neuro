# Held-out PACE evaluation, 2026-11-18

**The frozen raw reader has one known extraction error.** It matches 550 of 551 mapped answer-key values and all 390 additional unchecked-checkbox zeroes. One free-text suggestion omits a source word. Native Mac source review corrected exactly that suggestion, and the app-written reviewed workbook independently matches all 2,560 destination cells with zero issues. The corrected workbook does not establish perfect raw extraction.

This report concerns the separately supplied, user-confirmed fictional held-out dataset. The user authorized this evaluation after train fixes and acceptance. [Actual train acceptance](actual-pace-dataset-2026-11-18.md) and [earlier generated practice evidence](SYNTHETIC_PACE_GUI_2026-11-18.md) remain separate results.

## Freeze and evaluation boundary

The runtime was frozen at commit `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5` on `2026-11-18T23:45:26.040166Z`, before any held-out access. The [freeze snapshot](actual-pace-freeze-2026-11-18.json) records 37 source, rule, and dependency file hashes. All 37 hashes were verified unchanged before and after the raw held-out run and again after final reviewed export. Pushed revision `b139c4656c2f9f9ce356c278830b4699a81beecd` retains those frozen runtime files.

No extraction engine, rule, or verifier changes were made from the test answers. Answer keys are evaluation evidence, not extraction input. Any later development based on this failure needs a new evaluation scope and fresh held-out material.

## Independent inventory and expectations

| Check | Evidence | Scope or limit |
| --- | --- | --- |
| Forms census | 27 PDFs, 40 pages, five patient groups, nine instruments, 330 choice families. | Independent source inventory. |
| Answer-key inventory | 27 PDFs, 41 pages, 544 literal rows. | Independently audited; 24 pages rendered for the audit, with zero ambiguities found. |
| Key normalization | 559 normalized rows: 551 mapped values and eight key-only totals. | One literal checkbox wildcard expands to 16 canonical destination entries. |
| Raw mapped values | 550 of 551 match. | One known free-text word omission. |
| Additional checkbox zeroes | All 390 match. | These are additional source-observed unchecked controls, separate from explicit mapped key rows. |
| Expected populated destination cells | 941, from 551 mapped values plus 390 additional zeroes. | Remaining cells in the five-by-512 destination are expected blank. |
| Native raw project | All 27 PDFs imported into five patient rows; 2,559 of 2,560 destination cells match. | The same one-word omission remains before review. |
| Native review | 941 applicable fields confirmed, five patient rows approved, and all 512 column assignments confirmed through desktop control. | Exactly one source-reviewed correction; all other 2,559 values unchanged. |
| App-written reviewed XLSX | All 2,560 destination cells match, with zero issues. | Reviewed export accuracy is separate from raw extraction accuracy. |
| Frozen runtime | All 37 recorded file hashes unchanged after final evaluation. | No test-derived extraction changes; original source data unchanged. |
| Windows workflow | Independently audited [run 44424411229](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229): 283 source tests, one POSIX-only skip, all 11 acceptance checks passing at `b139c46`. | Generated-fixture and packaged checks; actual-dataset desktop QA was on Mac. |

One answer-key row uses `scan_findings___*=0` with the annotation `none checked`. Evaluation-only normalization expands that row to the 16 exact checkbox destinations already present in the canonical schema. This expansion occurs outside the app and adds 15 rows to the literal count: 544 becomes 559. It changes neither the extraction rules nor the destination schema.

Eight normalized total-score entries have no destination column. They remain explicit coverage omissions and are not exported. The 551 mapped key values and 390 additional checkbox zeroes must not be described as extraction of every key row.

## Known raw failure

For `personal_ctdisorder_v2`, the reader suggests `hypermobility`; the fictional printed source reads `Joint hypermobility`. The omission counts as a raw extraction failure even though the remaining word is correct. The native source-review correction restored the complete printed phrase. It was visually checked against the source and was the only changed value among the 2,560 destination cells.

The app-saved raw project independently matches 2,559 of 2,560 cells before correction. All original source data remain unchanged after review. No expected-answer rule, patient-specific alias, engine change, or verifier relaxation was introduced. The [raw diagnostic report](actual-pace-test-raw-2026-11-18.json), [review-change audit](actual-pace-test-review-2026-11-18.json), and [reviewed workbook comparison](actual-pace-test-xlsx-2026-11-18.json) preserve separate value-free evidence.

## Completed native review and export

The Mac `research-mac-dist` app imported all 27 held-out PDFs into five confirmed patient bundles. Desktop control performed the one source-checked correction, confirmed all 941 applicable fields, approved all five patient rows, confirmed the exact 512-column mapping, and saved XLSX through the app.

Independent reopening verifies five patient rows, the exact 512-header order, and all 2,560 destination cells, with zero issues. The check covers expected blanks and zeroes, identifier strings, normalized dates, literal codes, numbers, and absence of formulas, spreadsheet errors, active content, and hidden rows or columns. All other 2,559 values are identical to the raw project. The eight key-only totals remain outside this destination and are not captured or exported.

The original app-written workbook remains in the validation workspace at `outputs/actual-pace-2026-11-18/quickcap-test-reviewed-readout.xlsx`. On 2026-11-19 a [byte-identical reviewed test workbook](../../examples/qwikcap-supplied-test-reviewed-readout.xlsx) was included at the owner's request. Its SHA-256 is `ed30b51f2752dcec51f0ce478ff3e2148aeedc707eee7c4fb8631cdce8b12343`. The raw and reviewed projects and screenshots remain outside Git. The separately accepted [train workbook](../../examples/quickcap-actual-train-readout.xlsx) is also included.

## Audited Windows package and remaining scope

Independent audit of [Windows run 44424411229](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229) confirms 283 source tests with one POSIX-only skip and all 11 acceptance checks passing at `b139c4656c2f9f9ce356c278830b4699a81beecd`. The portable ZIP is 48,373,698 bytes with SHA-256 `2da5c9fe56ace1a01373b49764511c152268173c75ea415217a9dc40246881f7`.

The GUI and worker contain identical 512-field catalogs. All manifest hashes match for 76 native components, 125 embedded components, and 32 notices. The component inventory is not a separate SPDX or CycloneDX SBOM. The [private printed PACE prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-printed-pace-2026-11-18) is published at this CI revision; its uploaded ZIP digest matches the audited package. Use [the Windows guide](../WINDOWS.md) for setup. The historical `0793411` release predates the printed reader and simplified interface.

Actual train and held-out desktop QA ran on Mac. Windows evidence covers generated fixtures and packaged checks, not a person-driven actual-dataset GUI session. That Windows walkthrough, live REDCap import validation, and approval for production research use remain separate work.

## Reproduction and limits

Use the explicit-path tools and configured environment described in [the actual-dataset report](actual-pace-dataset-2026-11-18.md#reproduce-local-checks). Keep raw extraction diagnostics, the app-saved project, and the final workbook comparison as separate evidence. `verify_actual_pace_readout.py` reports `readout_passed` separately from optional raw-diagnostic coverage; key-only totals can make the raw coverage result fail even when a workbook matches every destination cell.

On 2026-11-19 the owner requested the original entirely fictional packet and audited evaluation files in Git. They are now included in the [supplied packet](../../datasets/sih-synthetic/README.md), unchanged and hash-listed. Source-bearing projects, raw screenshots, and logs remain outside Git. This report preserves the completed 2026-11-18 evaluation and one fictional error example. Local printed-PDF success does not establish handwriting recognition, scan-only marked-choice decoding, camera capture, live REDCap import, or production research readiness.
