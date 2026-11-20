# Try one patient

Open QwikCap. PACE automatic review is ready when the app opens.
This example uses five fictional PDFs included with the source download.

## Add the sample forms

1. If a project is already open, save it, then choose **File > New project**.
2. Click **Add documents…**.
3. Open `datasets/sih-clinic-synthetic/train/forms/` in the source folder.
4. Select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`.
   Hold Command on Mac or Ctrl on Windows to select several files.
5. In **Check patient groups**, select the proposed patient.
6. Use **‹** and **›** to inspect every source page. Check each sticker's exact MRN, name, and birth date.
   Click **Enlarge page…** if you need a larger view.
7. Select **I checked every source sticker and verified that these PDFs belong to this patient.**
8. Click **Check patient group**, then **Add checked patients**.
   The five PDFs become one patient row in **Review patients**.

Import only the PDFs from `forms/`. Answer keys and the manifest are reference files.
For several patients, repeat the source check and **Check patient group** for each proposed group before **Add checked patients**.
Identity conflicts, unknown layouts, and repeated assessments remain blocked.
Keep all forms for one patient in the same import.
To add a missing form later, remove that patient's row and import the complete set again.

## Check the answers

1. Select the patient, then select a field in **Review answers**.
   Read the suggested answer beside its source page.
2. Correct the answer if needed. For a choice field, select an option from the fixed PACE list.
   The app shows each allowed label and code. Enter dates as `YYYY-MM-DD`.
3. If the answer box covers the wrong area, click **Redraw answer area**.
   Drag around the correct answer on the source page, then check the new suggestion.
4. Click **Confirm & next** for every answer in the review list.
   For a required source blank, the button reads **Confirm blank & next**.
   Leave a source blank empty. A blank does not mean zero or No.
5. If a supported form is missing a field, click **Add PACE field…**.
   Choose the exact PACE field, draw its answer area on the correct page, and review the suggestion.
6. Enter your name in **Reviewer**, then click **Approve patient**.

Resolve reported errors before approval. Leave the patient unapproved if you cannot establish a required answer or a source blank.
Resolve identity conflicts against the original documents. Editing the MRN does not regroup the sources.

## Save your work

Click **Save form layout…** to reuse corrected answer boxes on matching forms.
The layout contains rules and form anchors, without patient answers or documents.
In the next project, click **Load form layout…** before adding the forms.
The app applies a saved box only when the form anchors match. Review every new answer.

Choose **File > Save project as…** to keep the original PDFs, answers, layouts, and unfinished review.
Use **File > Save project** for later saves.
When you reopen a project, check the patient group first, then confirm the answers and approve the patient again.
Reopening clears the previous confirmations and approvals.

## Export the patient row

Open **Map & export** after approving the patient. The supplied PACE columns and assignments are already loaded.

- For the supplied REDCap CSV, inspect the **Populated preview**, click **Confirm column mapping**, then **Export CSV…**.
- For an Excel workbook, click **Use fields as columns** first. Inspect the **Populated preview**, click **Confirm column mapping**, then **Export XLSX…**.

Check the saved file. This example produces one patient row with 512 columns, plus the header row.
CSV files also open in Excel.

New rows use temporary IDs such as `NEW000001`. These are separate from MRNs and assigned REDCap record IDs.
For new REDCap records, select automatic record numbering during import.
This workflow does not find or update existing REDCap records by MRN.
Existing-record updates need a separate import with the real REDCap record IDs.

## Continue in small batches

Use [Test patients](TEST_PATIENTS.md) for the other supplied groups.
Save each batch as a separate project before starting the next batch.
A 500-patient simultaneous import is not supported.
Imports accept at most 60 PDFs at a time. A session allows at most 60 patient rows and 20 MiB of retained sources.
Each patient can have at most 31 source pages. File size limits may require a smaller batch.

Keep layouts, projects, and exports outside Git. A fresh clone does not restore them.
Projects and exports are not encrypted.
Read the [storage limits](../SECURITY.md) before using real records.
