# QwikCap v1 prototype

QwikCap is a desktop app that copies suggested answers from PDF forms into a PACE spreadsheet.
You check each answer beside its source before you export.
Files are processed on your computer.

## Open the app

1. Open the [v1 prototype release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/v1.0.0-prototype). Sign in to GitHub with access to this private repository.
2. Download the ZIP for your computer and extract it.
3. On an Apple Silicon Mac, open **QwikCap.app**. On 64-bit Windows, open **QwikCap/QwikCap.exe**. Keep the whole extracted folder together.

The packaged app does not need Python or Excel.
To run a clone or edit the software, follow [Run from source](docs/GETTING_STARTED.md).

## Process a document

1. Click **Add documents…**. Select all PDFs for a patient, or a small batch of patients.
2. Check every source sticker. MRN links the forms; name and birth date must agree. Select the verification checkbox and click **Check patient group**. Then click **Add checked patients**.
3. Select a patient and a field. Compare its suggested answer with the source. Correct the answer or use **Redraw answer area**, then click **Confirm & next**.
4. Click **Save form layout…** to reuse corrected boxes on matching forms. Load that layout for the next batch.
5. Enter your name in **Reviewer**, then click **Approve patient**.
6. Open **Map & export**. For Excel, click **Use fields as columns**. Check the preview, click **Confirm column mapping**, then **Export XLSX…**. The supplied CSV template exports CSV instead.
7. Use **File > Save project as…** to keep the documents, answers and unfinished review.

PACE is the only preset. The output has 512 columns and one row per approved patient.
A saved layout contains rules. A saved project also contains source documents and answers.
Reopened projects require fresh review and approval.

[Try one supplied patient](docs/SIH_CLINIC_WORKFLOW.md) · [Correct and reuse a layout](docs/CUSTOM_FORMS.md)

## Know the v1 limits

Review every answer and use small batches. Some source fields remain blank or need correction.
New-record exports use temporary row IDs. Select automatic numbering for new records in REDCap; the app does not update existing REDCap records by MRN.
Projects and exports are not encrypted. Mac builds are not notarized, and Windows builds are unsigned.
Read [prototype status and remaining work](docs/V1_PROTOTYPE.md) before a research pilot with real records.

The original clinic packet matched 2,374 of 2,555 non-ID cells in train and 2,434 of 2,555 in test, including blanks.
Every exported cell matched the saved review. [Test results](docs/TESTING.md) explain the remaining gaps.

[Developer handoff](docs/HANDOFF.md) · [Sample patients](docs/TEST_PATIENTS.md) · [Data storage](SECURITY.md) · [Licensing](docs/LICENSING.md)

This repository is private and proprietary. No open-source license has been granted.
