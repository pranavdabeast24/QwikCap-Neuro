# QwikCap

QwikCap helps you copy information from PDF forms into a spreadsheet.
You check the suggested answers beside the original document before you export.
The app processes files on your computer.

[Download the app](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-pace-auto-2026-11-20) · [Try one patient](docs/SIH_CLINIC_WORKFLOW.md) · [Edit the software](docs/GETTING_STARTED.md)

## Use the app

1. Add one PDF or a small batch of forms.
2. Check the suggested patient groups against each source sticker.
3. Confirm or correct the suggested answers. Redraw an answer box when needed.
4. Save the form layout to reuse its corrected boxes on matching forms.
5. Approve each patient, check the spreadsheet preview, and export.

PACE is the only preset. The app suggests fields from your supplied codebook
and recognizes the supported clinic and printed layouts automatically.
MRN links forms; name and birth date provide cross-checks.
Each confirmed patient exports as one row with the supplied 512 columns.
The [walkthrough](docs/SIH_CLINIC_WORKFLOW.md) shows the process.

## Before you start

- Downloads support Apple Silicon Macs and 64-bit Intel or AMD Windows computers.
- The sample packet contains fictional patients.
- Review every answer. Some fields need manual work or remain blank.
- New-record exports use temporary row IDs. Select automatic numbering in REDCap when creating new records; this does not look up existing patients by MRN.
- Work in small batches. A 500-patient simultaneous import is not supported.
- Repeated visits in REDCap need an extra conversion before import.
- This is a research prototype. Read the [data limits](SECURITY.md) before using real records.

## Find what you need

The supplied clinic packet produced five patient rows in each split.
Against the frozen keys, 2,374 of 2,555 non-ID cells matched in train and 2,434 of 2,555 in test, including blanks.
Every exported cell matched the saved review. Some answers still need manual work.
See [the current test record](docs/testing/PACE_AUTO_2026-11-20.md) for the limits and counts.

| Task | Guide |
| --- | --- |
| Try the supplied forms | [One-patient walkthrough](docs/SIH_CLINIC_WORKFLOW.md) |
| Find the other sample patients | [Patient groups](docs/TEST_PATIENTS.md) |
| Check the measured results | [Test summary](docs/TESTING.md) |
| Run or change the code | [Developer setup](docs/GETTING_STARTED.md) and [handoff](docs/HANDOFF.md) |
| Understand permissions before a pilot | [Licensing](docs/LICENSING.md) |

The source remains private and proprietary. No open-source license has been granted.
