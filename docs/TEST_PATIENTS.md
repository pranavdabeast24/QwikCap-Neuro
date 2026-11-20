# Test patients

These groups belong to the [synthetic SIH clinic packet](../datasets/sih-clinic-synthetic/README.md).
Each listed group includes its registration PDF. Automatic PACE grouping uses MRN, name and birth date; registration is not required when the other supported sources establish identity.
Each complete split produces five patient rows with 512 columns.
Train and test reuse filenames but contain different forms.

## Train groups

The paths below are relative to `datasets/sih-clinic-synthetic/train/forms/`.
The first group is the example in [the clinic walkthrough](SIH_CLINIC_WORKFLOW.md).

| Printed sample study ID | Registration PDF | PDFs |
| --- | --- | --- |
| 1031 | `doc_11.pdf` | `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, `doc_24.pdf` |
| 1032 | `doc_02.pdf` | `doc_02.pdf`, `doc_06.pdf`, `doc_07.pdf`, `doc_10.pdf`, `doc_17.pdf`, `doc_23.pdf` |
| 1036 | `doc_15.pdf` | `doc_03.pdf`, `doc_08.pdf`, `doc_15.pdf`, `doc_25.pdf`, `doc_28.pdf` |
| 1040 | `doc_14.pdf` | `doc_01.pdf`, `doc_04.pdf`, `doc_09.pdf`, `doc_14.pdf`, `doc_20.pdf`, `doc_26.pdf` |
| 1042 | `doc_19.pdf` | `doc_05.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_27.pdf` |

## Test groups

The paths below are relative to `datasets/sih-clinic-synthetic/test/forms/`.
The test split needs a separate project and workbook.

| Printed sample study ID | Registration PDF | PDFs |
| --- | --- | --- |
| 1046 | `doc_09.pdf` | `doc_05.pdf`, `doc_06.pdf`, `doc_09.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf` |
| 1055 | `doc_17.pdf` | `doc_03.pdf`, `doc_15.pdf`, `doc_17.pdf`, `doc_26.pdf`, `doc_27.pdf` |
| 1060 | `doc_04.pdf` | `doc_04.pdf`, `doc_07.pdf`, `doc_08.pdf`, `doc_10.pdf`, `doc_11.pdf`, `doc_25.pdf` |
| 1066 | `doc_24.pdf` | `doc_02.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_24.pdf` |
| 1073 | `doc_01.pdf` | `doc_01.pdf`, `doc_14.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_20.pdf`, `doc_23.pdf` |

The `answer_keys/` folders contain reference answers.
The keys and `manifest.pdf` are not app inputs.
A key value does not establish an answer absent from the source form.
The [clinic test report](testing/SIH_CLINIC_2026-11-19.md) records measured results and gaps.

## Other supplied forms

PACE is the only visible preset. Supported clinic and printed PACE layouts are recognized internally.
Other older sheets must establish a supported PACE mapping; the app does not export the old 45-column staging schema through the new workflow.

Automatic new-record exports use temporary IDs, separate from the printed IDs in these tables.
Select automatic numbering in REDCap for new records. This is not an MRN-based update workflow.
