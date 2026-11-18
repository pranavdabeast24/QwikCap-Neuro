# Synthetic PACE GUI test, 2026-11-18

Status: complete. The native macOS app exported two reviewed fictional patient rows with 512 columns. Independent comparison passed all 1,024 output cells and the exact header order. Six scan values were corrected manually through the app; raw OCR was not perfect.

This report covers entirely fictional fixtures. It tests coded value transport and review workflow, without validating clinical meaning or applicability. No training or test dataset was changed.

## Fixture coverage

The source audit accounts for all 253 codebook entries in sequence. Of these, 247 map to export fields and six remain source references. The 32 checkbox entries expand to 294 destination columns. The other 215 mapped entries and three context columns produce 512 columns in the exact template order.

Each of two fictional cases has nine source PDFs with 26 pages in total. The app adds an operator ID cover when combining them, producing a 27-page patient bundle. The first case has a text layer. The second uses lossless grayscale raster pages at 144 DPI. Generation verifies 518 printed answer regions per case, including the six nonexport references, and all 26 raster pages for the scan case. The extraction type contains 512 rules. Generation bounds passed.

The six entries excluded from export are `total28`, `connective_tissue_prompt`, `hit6_total`, `total28_v2`, `image_dis_v2`, and `connective_tissue_prompt_v2`. The source ledger retains them as display, calculation, or unavailable-attachment references. They do not add export columns.

All conditional branches receive fictional responses for extraction coverage. This does not assert that every branch applies to one patient. Branch expressions remain reference metadata. One wide patient row aggregates multiple repeating instruments, so the repeat-instrument, repeat-instance, and data-access-group context cells remain blank. This output is a patient review export, without proof of a valid repeating-instrument REDCap import.

The audit identifies 69 destination option columns across 14 source entries with clipped or uncertain choice labels. Fixtures preserve the exact variable names and option codes with uncertainty labels. Matching these values proves code transport, without resolving missing choice wording. A checkbox zero represents explicitly printed unchecked evidence. Unobserved answers remain blank. Completion values are explicitly supplied, without inference from populated answers.

## Observed results

| Check | Result | Evidence or limit |
| --- | --- | --- |
| Text case in an app-saved project | 512 of 512 cells match | `audit/gui-draft-text-verified.json` passes with zero mismatches. |
| Scan case in the baseline app-saved project | 169 of 512 cells match | `audit/gui-draft-both.json` has 681 matches across both cases and 343 mismatches. Subtracting the verified 512 text matches gives 169 scan matches. |
| Separate native Vision diagnostic | 330 of 512 scan cells match | Task diagnostic observation. This is separate from the baseline app result and final GUI acceptance. |
| Tesseract in the rebuilt native app | 506 of 512 scan cells match before review | Local Tesseract 5.5.3_1, sparse layout for multi-column masked pages and bounded typed-region retries. The separately saved raw GUI draft has six mismatches. |
| Final GUI review and approval | Passed | Both records had all 512 fields confirmed and were approved by Synthetic QA through the native UI. Project serialization omits this state; the screenshots below prove the GUI run. |
| Final mapping confirmation and XLSX export | Passed | Mapping was explicitly confirmed, export became enabled, and the native save dialog wrote the workbook. All 512 headers and 1,024 cells match. No formulas, errors, hidden rows or hidden columns. |

The saved projects came from the app workflow. The comparison reports inspect their serialized values. The two-case comparison checks 1,024 cells, including eight expected blanks, 343 expected zeroes, 38 date cells, and 832 choice cells. It fails overall because the scan case does not match completely.

## OCR limits and completed acceptance

The scan shortfall was identified retrospectively by comparing extracted values with the independent expected rows. The 169-cell baseline and 330-cell native diagnostic describe these fixed synthetic pages and their respective execution paths. They do not establish an accuracy rate for other scans. Rendering, raster resolution, preprocessing, OCR engine, and field-region geometry can affect results. The text-layer success does not establish scan accuracy.

The fixture supplies coded responses for coverage. It does not test realistic missingness, clinical branching, or independent semantic interpretation. The review used agents from the same model family. No independent model-family review was performed.

The six manual scan corrections were three `Po` readings cleared from explicitly blank REDCap context fields; `med_topiramate` changed from 4 to 1; `baseline_headache_pain` from 4 to 1; and `csf_volume_delta_3` from 7.5 to -7.5. The app's code-entry control, draft validation, confirmations, approval and export gates were used. No saved project or approval state was seeded programmatically. A copied answer key was never loaded as app data.

The default generated workbook uses narrow columns, so long headers can clip and identifiers can wrap. AutoFit in Excel improves viewing; preserve the literal headers. Read-only first/middle/last-column rendering did not change the exported file. Microsoft Excel itself was not operated in this run. The new source was built and operated on macOS; the earlier Windows release predates these OCR changes.

The workbook SHA-256 is `c519d0dec4e316a55afb324ae49b362217c0601458eee65b38bc238d31314fb8`. Recheck the byte-identical committed copy from the repository root:

```sh
python tools/verify_synthetic_pace_readout.py examples/quickcap-synthetic-pace-readout.xlsx
```

The final source suite ran 238 tests with seven platform-specific skips and no failures. It includes the final UI changes and four negative checks for blank/zero distinctions, code types, minus signs, formulas, header order and identifiers. Native Windows checks remain separate from this macOS run.

## Evidence locations

The task artifact root is `work/synthetic-pace-2026-11-18/` in the task workspace. Paths below are relative to that root and contain no machine-specific prefixes.

- `generated/generation-proof.json` records fixture counts, page checks, raster encoding, and bounds.
- `audit/source-codebook-coverage-audit.json` records source-entry coverage, column order, and uncertainty counts.
- `audit/gui-draft-text-verified.json` records the passing text-case value comparison.
- `audit/gui-draft-both.json` records the failing two-case value comparison.

This report includes summary evidence only. Raw project contents, original attachments, and source documents are omitted.

Portable acceptance proof and fictional inputs are committed:

- [Machine-readable results](SYNTHETIC_PACE_GUI_2026-11-18.json)
- [Two records approved](SYNTHETIC_PACE_TWO_APPROVED.jpg)
- [Confirmed mapping and enabled export](SYNTHETIC_PACE_MAPPING.jpg)
- [Completed native export](SYNTHETIC_PACE_EXPORT.jpg)
- [Practice kit](../../examples/pace-synthetic-practice.zip)
- [Actual app-written Excel readout](../../examples/quickcap-synthetic-pace-readout.xlsx)

## Platform regression follow-up

The first Windows CI run of commit `bdf6ab2` exposed an OS-dependent permission assertion and two legacy single-column scan omissions. The permission negative now mocks executable access rather than relying on Unix chmod behavior. Sparse OCR selection now requires side-by-side masks with vertical overlap; single-column pages retain block mode. No fixture or answer key was changed. The native local engine again extracts all 30 fields in the five legacy scans, while the dense PACE scan remains 506/512 with the same six manual corrections. The final Mac source suite after this fix passes 238 tests with seven skips. This follow-up does not retroactively change the recorded Mac GUI build or its exported workbook.

The corrected source `0793411` subsequently passed [Windows CI](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44407671706): 238 tests, one POSIX-only skip, ten acceptance stages, and a verified extracted portable build. The [private prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-pace-2026-11-18) retains the ZIP. See [the Windows summary](SYNTHETIC_PACE_WINDOWS_2026-11-18.json) for the smaller Windows smoke-test scope.
