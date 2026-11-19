# Supplied synthetic SIH clinic packet

The project owner supplied this packet as `Neuro Synthetic Forms/sih_clinic_dataset/`, confirmed that it is entirely fictional or synthetic, and authorized its inclusion in the private repository. The source PDFs and their answer keys are separate from QwikCap's generated practice fixtures.

This packet is the current clinic-layout validation target. It is not the earlier PACE printed packet in [../sih-synthetic](../sih-synthetic/README.md), and it is not the older NEU-coded document-staging packet.

## Packet contents

| Folder or file | Original PDFs | Purpose |
| --- | --- | --- |
| `train/forms/` | 28 | Train-based implementation and source review. |
| `train/answer_keys/` | 28 | Independent train expectations. Never app input. |
| `test/forms/` | 27 | Evaluation after train fixes and reader freeze. |
| `test/answer_keys/` | 27 | Independent test expectations. Never app input. |
| `manifest.pdf` | 1 | Dataset index and patient grouping reference. Never app input. |

The complete supplied packet has 111 PDFs, totaling 13,929,598 bytes. Every copied PDF was verified byte for byte against the original. [INVENTORY.json](INVENTORY.json) records sizes and hashes, and [SHA256SUMS](SHA256SUMS) uses paths relative to this folder. The test split and index were copied only after the recorded reader freeze.

The source-only train census covers 28 forms across 43 pages and nine instrument families. All inspected pages contain native PDF text. The census found no raster images, AcroForm fields, or widget annotations. Some answers use handwriting-style fonts, circled printed options, and native checkbox marks. This does not establish performance on real handwriting, scans, or camera capture.

## Reader and patient identity

Select **Advanced > Form type > Read SIH clinic forms** in a clinic-enabled build. Follow [the operator walkthrough](../../docs/SIH_CLINIC_WORKFLOW.md) to combine source documents, review answers, and export Excel.

Each patient bundle needs its registration sheet. That sheet prints a **Research Study ID** linked to MRN, name, and birth date. Other clinic pages identify the patient through demographics and MRN. They do not each print a REDCap record ID. The operator-entered study ID must agree with registration, and all original PDFs must belong to that patient. MRN remains a separate literal identifier, including leading zeroes.

The target retains the same 512 exact destination headers as the supplied blank import table. Several reviewed clinic documents become one patient row. This is a staging table, not a validated repeating-instrument REDCap import.

## Interpretation and evaluation limits

Source blanks and unmentioned narrative findings do not establish zero or No. Conditional questions can remain physically printed when skipped. The clinic pages do not print REDCap instrument completion selectors or every catalog-specific reader choice. Those values must not be invented to match an answer key.

Keep raw extraction, manual source corrections, and reviewed export checks separate. Record any key value that the source document cannot establish as a coverage limitation. The earlier PACE results of 600/600 train mapped values and 550/551 test mapped values do not measure this clinic packet.

The clinic validation used independent source-only censuses and answer-key audits. Test content was evaluated after train fixes and a recorded 72-file freeze. Strict original exact-key agreement is 558/572 train and 495/508 test. Expanding the test key's single wildcard into its 16 literal catalog siblings gives 500/524. Complete-grid comparisons retain 181 train and 121 test differences. Read the [dated report](../../docs/testing/SIH_CLINIC_2026-11-19.md) for denominators, source coverage limits, app-written workbook checks, and reproducibility commands.

The `evaluation/` directory retains the independent censuses, literal expectations, key audits, and separate test wildcard expansion. Never upload these evaluation files into QwikCap. The [train workbook](../../examples/qwikcap-sih-clinic-train-readout.xlsx) and [test workbook](../../examples/qwikcap-sih-clinic-test-readout.xlsx) are desktop app exports, separate from the keys.

To check the original PDFs on Mac or Linux, run `shasum -a 256 -c SHA256SUMS` from this folder. On Windows PowerShell, use `Get-FileHash -Algorithm SHA256` and compare against `INVENTORY.json`. Do not change the original forms to match extraction rules.

The owner authorized private project inclusion. This does not establish public redistribution rights for third-party instrument content. Source-bearing projects, local outputs, screenshots, and caches remain outside the packet.
