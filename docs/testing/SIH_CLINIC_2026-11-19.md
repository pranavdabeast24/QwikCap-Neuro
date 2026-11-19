# Supplied SIH clinic packet evaluation, 2026-11-19

The current packet is `sih_clinic_dataset`, included unchanged as [datasets/sih-clinic-synthetic](../../datasets/sih-clinic-synthetic/README.md). These measurements concern the owner's 28 train forms and 27 held-out test forms. They are separate from the earlier PACE printed packet and generated software fixtures.

Select **Read SIH clinic forms**, profile `sih-clinic-v1`. The [operator guide](../SIH_CLINIC_WORKFLOW.md) lists patient groups and the native import, review, mapping, and export steps.

## Results and denominators

| Check | Train | Held-out test |
| --- | --- | --- |
| Forms / pages / patient bundles | 28 / 43 / 5 | 27 / 42 / 5 |
| Strict original exact-key destination values | 558 / 572, 97.55% | 495 / 508, 97.44% |
| Strict mapped values after documented key shorthand expansion | 558 / 572, 97.55% | 500 / 524, 95.42% |
| Additional inferred checkbox zeroes | 316 / 483, 65.42% | 293 / 390, 75.13% |
| Strict complete patient grid, including blanks and zeroes | 2,379 / 2,560, 92.93% | 2,439 / 2,560, 95.27% |
| Key-only total entries without a destination | 9 excluded | 8 excluded |

The strict complete-key comparisons return **failure**. The app does not fill missing values from keys. Export transport and extraction coverage are different checks. A workbook can faithfully preserve every reviewed value while retaining source coverage gaps.

The test keys contain 517 literal rows: 508 exact destination variables, one wildcard, and eight totals. The single wildcard says `scan_findings___* = 0 (none checked)`. The independent auditor preserved the [literal expectations](../../datasets/sih-clinic-synthetic/evaluation/test-expected.json) and expanded that row to the 16 exact catalog siblings in a [separate comparator input](../../datasets/sih-clinic-synthetic/evaluation/test-expected-comparator.json). This adds 16 rows to the 508 exact-variable denominator. It is an expectation normalization, not a reader change. See the [normalization record](../../datasets/sih-clinic-synthetic/evaluation/test-key-normalization.json).

The 2,560-cell grid is five patients by 512 destination columns. It includes expected blanks and inferred zeroes and is not a count of independent populated answers. Expected nonblank cells are 1,055 train and 914 test. Actual nonblank cells are 877 train and 795 test.

## Source coverage and discrepancies

| Difference | Train cells | Test cells |
| --- | ---: | ---: |
| Catalog reader codes unavailable from the signing physician names | 11 | 11 |
| Source terminal periods retained where keys omit them | 3 | 2 |
| Unmentioned procedure options in free-text cells left blank | 119 | 56 |
| Individually unmentioned report findings left blank | 44 | 48 |
| Brain-sag option not inferred from a broad no-SIH impression | 1 | 1 |
| Negative threshold options not derived from captured measurements | 3 | 3 |
| Total strict patient-grid differences | 181 | 121 |

Eleven source reports in each split name physicians outside the six catalog reader choices. A signature does not establish the key's reader code. Those fields remain blank and inactive. The `myelogram` destination is also a reader question, rather than a myelogram yes/no flag.

The reader retains full source narrative sentences. Three train and two test key strings omit their final period. The existing comparator preserves punctuation, so the differences remain in the strict scores. Independent source review found no incorrect populated suggestion among the compared destination fields. This observation does not erase blank-field coverage gaps.

Procedure location, quality, and symptom cells contain positive free text. They do not independently negate every other catalog option. Likewise, a report's silence about an imaging finding does not establish a negative. The reader leaves these values blank instead of defaulting them to zero.

There is a specific derivable-negative gap. Train `doc_12.pdf` and test `doc_02.pdf` print mamillopontine, suprasellar, and prepontine measurements above the catalog's positive thresholds. The numeric measurements are captured, but the three corresponding finding zeroes are not computed. They remain blank in this frozen reader. Any development based on the test answers requires fresh held-out material for a new independent score.

The source pages do not print instrument completion selectors, repeat metadata, or access groups. FINAL report status is not a REDCap instrument-completion code. Nine train and eight test computed totals have no column in the supplied destination and are excluded rather than silently added.

The [train reconciliation](SIH_CLINIC_TRAIN_RECONCILIATION_2026-11-19.json) and [test reconciliation](SIH_CLINIC_TEST_RECONCILIATION_2026-11-19.json) retain value-free field details and hashes. The unchanged comparator reports retain all [train](SIH_CLINIC_TRAIN_RAW_2026-11-19.json) and [test](SIH_CLINIC_TEST_RAW_2026-11-19.json) failures.

## Evaluation separation and freeze

Train source layouts and answer keys were audited independently. Implementation used train only. The train keys resolved two clipped first-provocation symptom labels: `prov_associated_symptoms___2` is Photophobia and `prov_associated_symptoms___6` is Visual aura / halos. The reader requires a literal positive term in the corresponding source cell. These are general metadata aliases, not patient-specific answers or filename lookups. The base catalog remains unchanged.

Native Mac train acceptance preceded the [72-file freeze](SIH_CLINIC_FREEZE_2026-11-19.json) at `2026-11-19T10:10:31.871790Z`, source `e2fbd2e8bbb28d31427c229ad18cae5f896c9d93`. The freeze was committed as `e5bf722` before test or index access. The held-out source census and key audit were independent of each other and of engine outputs. Every frozen hash was checked before and after the held-out model run. No extraction rule, engine, dependency, or comparator tuning was made from test answers.

The supplied pages contain native PDF text, including handwriting-style fonts, circles, X marks, tables, and narratives. Both source censuses found zero embedded raster images, widgets, or AcroForm fields. These rates do not measure real handwriting, scanned-paper OCR, camera capture, or unseen form families.

The delivered app includes later [hardening from invented qualifier examples](SIH_CLINIC_HARDENING_2026-11-19.md). That separate change happened after the frozen evaluation. A 55-form regression replay retained every supplied-form value. The scores above remain historical frozen measurements, rather than a claim that the current runtime has all 72 original hashes or a fresh held-out score.

## Native desktop and export evidence

The actual packaged Mac app imported the original train PDFs through its native file picker, checked each source group, and combined five patient rows. Desktop control confirmed 926 applicable fields, entered the reviewer `Synthetic QA reviewer`, approved five rows, confirmed 512 column assignments, and exported [the train workbook](../../examples/qwikcap-sih-clinic-train-readout.xlsx). There were zero manual value edits. Independent checks verify all 2,560 typed export cells against the app-saved project, all 28 original embedded PDF hashes, and the exact header order. Strict key agreement remains 2,379/2,560. See [native train evidence](SIH_CLINIC_TRAIN_NATIVE_2026-11-19.json).

The frozen native Mac test workflow imported all 27 PDFs into five patient rows, confirmed 893 applicable fields, approved five patients, confirmed the mapping, and exported [the test workbook](../../examples/qwikcap-sih-clinic-test-readout.xlsx). Independent checks match all 2,560 typed cells to the saved project and all 27 embedded source PDFs to the originals. There were zero value edits, so raw and reviewed key agreement remain 2,439/2,560. See [native test evidence](SIH_CLINIC_TEST_NATIVE_2026-11-19.json). Neither workbook contains formulas, errors, hidden rows or columns, macros, external links, or merged cells. Leading-zero MRNs and numeric-looking study IDs remain text; supported numeric answers remain numbers. Dates remain normalized ISO text, as expected by the existing export contract.

| App-written workbook | SHA-256 |
| --- | --- |
| Train | `7626346d973cc9a2d04c71a0f0256fc275f032527cbd708361567add07ff43ce` |
| Test | `5c180a6bdcb9913022e5f5e2abb2507b6a950380527840d1276c87a596966213` |

The [completion snapshot](SIH_CLINIC_FROZEN_EVALUATION_COMPLETE_2026-11-19.json) records all 72 frozen hashes unchanged through the native test export at `2026-11-19T10:28:00.534537Z`. Its independent-audit field describes the state at that timestamp; the separate final native report records the later completed audit.

Save projects outside Git: they embed original PDFs. Reopening reconstructs source metadata and requires fresh confirmations, approvals, and mapping confirmation. Saved project JSON intentionally does not serialize prior approval as valid review.

## Platform and package checks

Source `e2fbd2e` passes 311 source tests on Mac with seven Windows-only skips. The [Mac unit output](SIH_CLINIC_MAC_UNIT_2026-11-19.txt) and [packaged clinic fixture result](SIH_CLINIC_MAC_PACKAGED_2026-11-19.json) are retained. Native testing caught an additional UI bug: the reader appeared in the menu while a PACE-only guard blocked its file picker. A callback regression and the shared patient-profile predicate fixed that path before the freeze.

The [native Windows CI run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44501222833) passes all 12 gates and 311 tests with one POSIX-only skip. Its clinic fixture checks seven groups, 14 literal fields, and 1,024 independently reopened CSV/XLSX cells. These generated Windows fixtures are separate from supplied-packet Mac GUI acceptance. A person-driven actual-packet walkthrough on a Windows laptop remains unverified.

The [frozen-source Windows archive audit](SIH_CLINIC_WINDOWS_ARCHIVE_2026-11-19.json) verifies 76 outer native files, 125 embedded inventory payloads, 32 notice files, 24 approved resources, identical 512-field GUI/worker catalogs, and the clinic modules in both executables. That historical ZIP SHA-256 is `4b21d4ed809c83ef5eabc3e629384c3446938363ebc16c69183223cc37dfc989`. Current download hashes are in the separate hardening report.

The [frozen-source Mac arm64 archive audit](SIH_CLINIC_MAC_ARCHIVE_2026-11-19.json) verifies the unmodified ad-hoc-signed app, 286 regular files, 46 symlinks, all modes and hashes after ZIP extraction, 27 outer arm64 Mach-O files, 24 embedded helper Mach-O files, 32 external notices, source-matching modules, and the 512-field catalogs. That historical ZIP SHA-256 is `d2c74d2cd18cfd6b6201476640aaa81d4fe38c7bcb72475452e0c6f827513a37`. Intel support, notarization, Windows signing, and clinical production approval are not established.

## Reproduce strict workbook comparisons

Use the setup in [GETTING_STARTED.md](../GETTING_STARTED.md). Run these from the clone root:

```sh
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-clinic-synthetic/evaluation/train-expected.json --census-json datasets/sih-clinic-synthetic/evaluation/train-form-census.json --xlsx examples/qwikcap-sih-clinic-train-readout.xlsx
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-clinic-synthetic/evaluation/test-expected-comparator.json --census-json datasets/sih-clinic-synthetic/evaluation/test-form-census.json --xlsx examples/qwikcap-sih-clinic-test-readout.xlsx
```

These commands deliberately return exit code 1 for the documented strict-key differences. Do not weaken the comparator or replace the outputs with answer-key values to make it green. To generate separate read-only source diagnostics, use `tools/extract_pace_dataset.py --profile sih-clinic-v1 --forms-dir <one split's forms folder> --output <new local JSON>`. Diagnostics create neither approvals nor an app export. Keep keys and the index out of the app's input queue.
