# Supplied synthetic SIH evaluation packet

This is the original packet supplied by the project owner. The owner confirmed that every form and answer key is entirely fictional or synthetic and requested inclusion in this private repository. These PDFs were not authored by QwikCap's sample generators. The copies preserve the original PDF bytes and filenames.

The original packet contains 111 PDFs totaling 10,353,882 bytes:

| Folder or file | Files | PDF pages | Purpose |
| --- | --- | --- | --- |
| `train/forms/` | 28 | 45 | Training-stage extraction and native desktop acceptance. |
| `train/answer_keys/` | 28 | 47 | Independently checked evaluation answers. Never app input. |
| `test/forms/` | 27 | 40 | Authorized held-out evaluation after the reader freeze. |
| `test/answer_keys/` | 27 | 41 | Independently checked evaluation answers. Never app input. |
| `manifest.pdf` | 1 | 2 | Original dataset index. Evaluator reference, never app input. |

`SHA256SUMS.txt` lists the original 111 PDFs. Its SHA-256 is `adf3dce937044f9c54f0debf3b89e5e4ffdbfa15e771dae7bd3569d00bf6196a`. `packet-inventory.json` records each relative path, byte count, and hash. The source was `~/Desktop/Neuro Synthetic Forms/sih_dataset/`. No source PDF was edited during packaging.

The dataset index includes identities and instrument information for fictional cases. Keep the index, answer keys, and evaluation JSON out of document upload. Upload only the appropriate `forms/` PDFs, grouped by the confirmed synthetic patient ID.

## Evaluation history

Train fixes and native Mac acceptance preceded test access. The reader was frozen at `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5`, with 37 recorded runtime hashes, before the authorized test evaluation on 2026-11-18. The train and reviewed test workbooks each contain five rows and the exact 512 destination columns.

Raw mapped-key extraction matched 600 of 600 train values and 550 of 551 test values. Additional source-observed unchecked-checkbox zeroes matched 483 of 483 train entries and 390 of 390 test entries. The test reader omitted `Joint` from `Joint hypermobility`. Native source review corrected that one suggestion before export. Nine train and eight test total-score key entries have no destination columns and remain outside extraction and export.

The app-written [train workbook](../../examples/quickcap-actual-train-readout.xlsx) and [reviewed test workbook](../../examples/qwikcap-supplied-test-reviewed-readout.xlsx) each match all 2,560 destination cells. Those denominators include expected blanks and zeroes. The raw test patient rows match 2,559 of 2,560 cells before the correction. The [train report](../../docs/testing/actual-pace-dataset-2026-11-18.md) and [test report](../../docs/testing/heldout-pace-2026-11-18.md) distinguish extraction from reviewed export.

The test set has already been evaluated. It is no longer a fresh holdout. Do not tune against its keys and report the resulting score as a new independent evaluation. Current naming and packaging changes do not erase the original raw failure.

## Independent evaluation files

`evaluation/` contains unchanged files from the completed audit, with a separate `SHA256SUMS.txt`:

- `train-expected.json` and `test-expected.json` preserve literal audited key rows.
- `test-expected-comparator.json` expands one literal `scan_findings___*=0` row annotated `none checked` to 16 canonical destinations. This evaluator-only normalization changes 544 literal rows to 559 normalized rows. It changes no app rule or source document.
- `train-form-census.json` and `test-form-census.json` record independent visible-question and checkbox-family coverage.
- `train-key-audit.json` and `test-key-audit.json` record the independent PDF answer-key audit.

These files are evaluator evidence. The extraction tool does not read them. Their existing source paths are historical provenance and do not need to exist on a new machine. Use the normalized test expectation with the verifier because its literal wildcard is not an export column.

## Verify the packet and workbooks

From the repository root on macOS or Linux, check PDF and evaluator hashes:

```sh
(cd datasets/sih-synthetic && shasum -a 256 -c SHA256SUMS.txt)
(cd datasets/sih-synthetic/evaluation && shasum -a 256 -c SHA256SUMS.txt)
```

After configuring the pinned Python environment, verify the existing app exports without changing them:

```sh
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/train-expected.json --census-json datasets/sih-synthetic/evaluation/train-form-census.json --xlsx examples/quickcap-actual-train-readout.xlsx
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/test-expected-comparator.json --census-json datasets/sih-synthetic/evaluation/test-form-census.json --xlsx examples/qwikcap-supplied-test-reviewed-readout.xlsx
```

Both commands require `readout_passed: true`, 2,560 matched cells, and exit code zero. Use `.venv/bin/python` on Mac or `.venv\Scripts\python.exe` on Windows when the environment is not activated.

For a new raw train extraction run, choose a fresh output path:

```sh
python tools/extract_pace_dataset.py --forms-dir datasets/sih-synthetic/train/forms --output verification/supplied-train-raw.json
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/train-expected.json --census-json datasets/sih-synthetic/evaluation/train-form-census.json --xlsx examples/quickcap-actual-train-readout.xlsx --extraction-json verification/supplied-train-raw.json
```

For a regression replay on the already-used test set, choose another fresh output path:

```sh
python tools/extract_pace_dataset.py --forms-dir datasets/sih-synthetic/test/forms --output verification/supplied-test-raw.json
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/test-expected-comparator.json --census-json datasets/sih-synthetic/evaluation/test-form-census.json --xlsx examples/qwikcap-supplied-test-reviewed-readout.xlsx --extraction-json verification/supplied-test-raw.json
```

With raw diagnostics, the current verifier returns exit code one for the nine unsupported train totals, or the eight test totals and known raw text omission. Inspect `readout_passed` separately from `raw_diagnostics_passed` and inspect `document_diagnostics`. A reviewed workbook can pass while raw extraction retains those documented coverage failures. Do not remove totals or alter the verifier to obtain a green combined result.

These commands are diagnostics, not a native desktop walkthrough. To create another reviewed workbook, follow [the app workflow](../../README.md#review-supplied-pace-forms), upload only forms, confirm the patient groups, review every source value, approve the rows, confirm the mapping, and export through QwikCap. Actual supplied-packet GUI evidence is Mac-specific. Windows generated-fixture acceptance is separate.

The earlier [app-authored practice kit](../../examples/pace-synthetic-practice.zip) is supplemental software coverage. It is not this supplied evaluation packet. This inclusion grants no public redistribution rights for third-party instrument content.
