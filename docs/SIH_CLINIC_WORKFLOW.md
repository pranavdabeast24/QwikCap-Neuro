# Review clinic forms and export Excel

Create one reviewed patient row from five synthetic clinic PDFs.

Use the [current QwikCap release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-clean-outlines-2026-11-20).
On Windows, extract the whole application folder before opening `QwikCap.exe`.
Keep `_internal` beside it.
On Mac, open `QwikCap.app`.
The packaged app does not need Python or Excel to export a workbook.

## Combine the first patient's forms

1. Save any open project.
2. Choose **File > New project**.
3. Select **Advanced > Form type > Read SIH clinic forms**.
   If this option is missing, use a newer clinic-enabled build.
4. Choose **Add documents… > Combine PDFs for one patient…**.
5. Open `datasets/sih-clinic-synthetic/train/forms/`.
   Select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`.
   Hold Command on Mac or Ctrl on Windows to select several files.
   Keep this order.
6. Open registration `doc_11.pdf`.
   Check the printed **Research Study ID**.
   It must be `1031`.
7. Check that every selected PDF has the same MRN, name, and birth date.
   Keep leading zeroes in MRN.
   MRN is separate from the study ID.
8. Enter `1031` in **Study record_id**.
9. Check **I verified every PDF is for this patient and this is the intended source order.**
10. Click **Combine into one patient row**.
    The patient appears in the document queue.

## Review the answers

1. Select the patient in **Design & review**.
2. Select a field to see its source and suggested answer.
3. Read the complete source answer, including text outside the highlight.
4. Correct the suggestion when the source supports a different answer.
   Record each correction and its source.
5. Click **Confirm & next** after each source check.
   Use **Expand…** for long answers.
   Repeat for every applicable field.
6. Keep missing answers blank.
   A blank does not mean zero or No.
   If the source cannot establish a required answer, leave the patient unapproved.
7. Enter your name in **Reviewer**.
8. Click **Approve document**.
   The queue shows **Approved**.

## Export the row

1. Open **Map & export**.
2. Click **Use fields as columns**.
   This creates 512 matching columns.
3. Inspect **Populated preview**.
   **Next columns** shows more columns.
4. Click **Confirm column mapping**.
5. Click **Export XLSX…**.
6. Save the workbook outside the repository.
7. Open the workbook in a spreadsheet viewer.
   Expect one data row, `record_id` 1031, and 512 headers.
   Only approved patients appear in exports.
8. Choose **File > Save project as…** to keep your sources and values.
   Reopening a project requires fresh field checks, approval, and mapping confirmation.

Use [Test patients](TEST_PATIENTS.md) for the remaining groups.
Use [Custom forms](CUSTOM_FORMS.md) for other layouts or blank spreadsheets.
Repeating REDCap rows need a separate validated conversion before import.
QwikCap does not submit records to REDCap.
