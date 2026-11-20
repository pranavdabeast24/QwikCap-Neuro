# Four-patient packet and export coverage

The owner confirmed that the supplied project test documents and example exports are entirely synthetic.
The four original PDFs are in [the variants packet](../../datasets/sih-variants-synthetic/README.md), with a byte inventory.
Each contains one four-page HA-220P patient questionnaire. They form four separate patient rows.

## The supplied one-patient CSV

The CSV contains one row and exactly the 512 columns from the PACE catalog, in the expected order.
It matches `patient_04.pdf` by literal MRN.
All 511 non-ID values match a fresh extraction, including typed numeric comparisons. Batch-assigned temporary record IDs were excluded from that comparison.
No fresh source suggestion was populated while its CSV destination was blank.
This compares reader output with the file. It does not establish the accuracy of every source answer.

The row contains 114 populated values, including 54 zeroes, and 398 blanks.

| Reason for a blank | Columns |
| --- | ---: |
| Other study instruments or metadata not supplied by this questionnaire | 382 |
| Blank conditional follow-ups on this questionnaire | 14 |
| Unmarked `periods_v2` answer | 1 |
| Questionnaire completion-status metadata absent from the paper | 1 |
| Total | 398 |

An independent visual check of all 16 questionnaire blanks found no visible missed answer.
The conditional follow-ups include unselected Other descriptions and follow-ups to source No answers.
The procedure-success cells are themselves unmarked. A separate Had it? No answer does not establish Did it help? No.
The periods row has no marked answer or N/A indication. Its allowed codes are 1, 2 and 3, so zero would be invalid.
The app does not infer why that row is unmarked or automatically set the REDCap completion status.

The clinician questionnaire, HIT-6, procedure, registration and imaging columns remain separate from patient-questionnaire fields.
Patient variables often use `_v2`; matching labels do not authorize copying values into the clinician version.

## Field-list visibility

The main answer list uses detected source fields. The separate study-field catalog includes all 512 columns.
Open **Answer tools… > Add PACE field…**, clear Search, and select **All instruments**.
Record IDs and sticker identities use their own workflow. Repeat and access-group columns are administrative context, not source answer regions.

A separate reader defect could omit a detected text question when no answer passed its font filter.
The same invented question appeared with a Courier answer but disappeared with a Helvetica answer, without a warning.
The parent reproduced that difference in the actual native answer list.

Runtime commit `c8ff236a5b2883d4c76ed31a352fd2d27ebcb45a` registers the detected question before reading its answer.
When unreadable, the field retains empty-text source-page and region evidence and a manual-review issue.
The font filter, values, branching, source-blank waivers, identity checks and approval gates retain their previous behavior.
No missing answer is replaced with zero.

## Replay of the four original PDFs

The correction exposes more located questions for review. It preserves the populated and zero counts.

| Original PDF | Review fields before | Review fields after | Populated values | Blank export cells | Zero values |
| --- | ---: | ---: | ---: | ---: | ---: |
| patient_01.pdf | 119 | 129 | 117 | 395 | 55 |
| patient_02.pdf | 118 | 128 | 115 | 397 | 54 |
| patient_03.pdf | 113 | 128 | 106 | 406 | 66 |
| patient_04.pdf | 118 | 129 | 114 | 398 | 54 |

No fields were approved and no exports were made during that replay. Group confirmation was automated for these declared synthetic fixtures.
The PDF03 `mri_prev_date_v2` region has no single recognized date and needs manual review.
The table is a coverage regression, not an answer-key accuracy score.

## Verification

Five new session tests cover unreadable and blank text, allowed-font text, malformed date and number inputs, absent prompts, and manual recovery.
Before the fix, the session module failed three omission assertions. Afterward all 18 session tests passed.
The native before/after check now displays both font variants, with the unreadable answer kept blank and flagged.
Independent review checked source navigation, highlighting, repeated-call behavior and required-value gates.
The full Mac source suite passed 369 tests with seven Windows-only skips.
Platform package results and exact archive hashes are recorded in the release verification files.

Run the source checks from a configured clone:

```sh
python -m unittest discover -s tests -p 'test_sih_clinic_session.py' -v
python -m unittest discover -s tests -v
```

The supplied CSV remains unchanged and is not part of the packet. The packet contains the four original input PDFs, its guide and inventory.
Real handwriting, clinical deployment and live REDCap import are not validated by these synthetic checks.
