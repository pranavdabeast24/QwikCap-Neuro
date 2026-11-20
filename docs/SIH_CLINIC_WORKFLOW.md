# Try one patient

Open QwikCap. PACE is ready when the app opens. You do not need to select a reader or draw every field.

## Add the sample forms

1. Save any open project, then choose **File > New project**.
2. Click **Add documents…**.
3. Open `datasets/sih-clinic-synthetic/train/forms/` in your downloaded source packet.
4. Select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`.
   Hold Command on Mac or Ctrl on Windows to select several files.
5. In **Check patient groups**, select the proposed patient. Open each source preview and check its MRN, name and birth date.
6. Check the statement that you verified every source sticker, then click **Check patient group**.
7. Click **Add checked patients**. The sources become one patient row.

Use only PDFs from `forms/`. Do not import answer keys or the manifest.
You can select several patients' forms together; check each proposed group before adding it.
Conflicting identities, unknown layouts and repeated assessments remain blocked.
Keep all forms for one patient in the same import. To add a missing form, remove that patient row and import their complete set again.

## Check the answers

1. Select the patient, then select a field. Its suggestion appears beside the source page.
2. Read the complete source answer. Correct the answer if needed. Choices use the PACE codebook's codes and labels; dates use `YYYY-MM-DD`.
3. If the app read the wrong area, click **Redraw answer area** and drag around the right answer. Check the new suggestion.
4. Click **Confirm & next** for each answer, including source blanks. A blank does not mean zero or No.
5. If a field is missing, click **Add PACE field…**, choose its exact study field, and draw its area on the correct source page.
6. Enter your name in **Reviewer**, then click **Approve patient**.

If a required answer cannot be established, leave the patient unapproved.
Patient identity conflicts need to be resolved against the original sources; typing a different MRN does not silently regroup forms.

## Save the layout and export

1. Click **Save form layout…** to keep corrected answer boxes for matching forms. The layout contains rules, without patient answers or documents.
2. On the next project, click **Load form layout…** before adding the forms. The app applies a correction only when its form anchors match. Review every new answer.
3. Open **Map & export**. The PACE destination columns are already loaded.
4. For an Excel workbook, click **Use fields as columns**. Inspect the populated preview, then click **Confirm column mapping** and **Export XLSX…**.
5. For the supplied REDCap CSV template, inspect and confirm its mapping, then choose **Export CSV…**. CSV files also open in Excel.
6. Choose **File > Save project as…** to keep the documents, answers and unfinished review. Reopening clears confirmations and approvals. Check the patient group again before approving.

Expect one row with 512 headers. New rows use temporary IDs such as `NEW000001`; these are not MRNs or assigned REDCap study IDs.
For a new-record import, select automatic numbering in REDCap. This workflow does not update existing REDCap patients by matching MRN. Get the real REDCap record IDs before attempting updates.

Use [Test patients](TEST_PATIENTS.md) for the other supplied groups. Process a large study in small batches; the session retains at most 20 MiB of sources and 60 patient rows, and each patient can have at most 31 source pages.
Projects and exports are not encrypted. Read [the storage limits](../SECURITY.md) before using real records.
