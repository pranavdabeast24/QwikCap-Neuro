# Review SIH clinic forms and export Excel

Create one reviewed Excel row from several clinic PDFs for the same patient. This guide uses the current [SIH clinic packet](../datasets/sih-clinic-synthetic/README.md), originally supplied as `Neuro Synthetic Forms/sih_clinic_dataset/`.

Use the [clinic-enabled private release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19). The [dated evaluation](testing/SIH_CLINIC_2026-11-19.md) records raw accuracy, conservative blanks, export checks, and platform limits. The previous PACE printed-packet scores do not measure this reader.

## Open a clinic-enabled app

1. Open **QwikCap**. On Windows, extract the complete portable application folder and open `QwikCap.exe`. Keep `_internal` beside it. On Mac, open your local `QwikCap.app`. A packaged app does not require a separate Python or Excel installation to export a workbook.
2. Check **Advanced > Form type** for **Read SIH clinic forms**. If it is missing, use a newer clinic-enabled build. The earlier `qwikcap-2026-11-19` pilot release predates this reader. Check [the Windows guide](WINDOWS.md) for package status or [source setup](GETTING_STARTED.md) for development.
3. Find `datasets/sih-clinic-synthetic/` in your clone or source packet. Your original Desktop copy of `sih_clinic_dataset/` also works. Keep `train/forms/` and `train/answer_keys/` separate. Upload only the forms. The answer keys and `manifest.pdf` are references.

## Export the first train patient

1. Save any open project. Choose **File > New project**, then **Advanced > Form type > Read SIH clinic forms**. New project clears the previous reader choice, so select it again each time.
2. Choose **Add documents… > Combine PDFs for one patient…**. Open `train/forms/` and select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`. Hold Command on Mac or Ctrl on Windows to select these files together.
3. Enter `1031` in **Study record_id**. Open registration `doc_11.pdf` to verify its **Research Study ID**. Check that every other selected PDF has the same MRN, name, and birth date. Preserve leading zeroes in MRN. Do not substitute MRN for the study ID.
4. Keep the files in the listed order. Use **Move selected PDF up** or **Move selected PDF down** if needed. Check **I verified every PDF is for this patient and this is the intended source order.** Click **Combine into one patient row** and wait for processing.
5. Select the patient in **Design & review**. The combined source has an operator-entered ID cover followed by the original PDFs. Select a field to inspect its source region and proposed answer. Read the complete source answer, including text outside a narrow highlight.
6. Correct an answer when the source supports a different value. Click **Confirm & next** after each source check. Command-K on Mac or Ctrl-K on Windows does the same thing. Use **Expand…** for longer text. Review selected circles, checkbox marks, dates, units, and signed quantities.
7. Keep genuinely missing or unmentioned values blank. A blank answer is not a measured zero or a No response. Follow the displayed validation message for a required unanswered question. If the source cannot establish a required answer, keep the case unapproved and record the gap.
8. Enter your name under **Reviewer**. Click **Approve document** once every applicable field has been checked. The document queue should show **Approved** for one patient row.
9. Open **Map & export** and click **Use fields as columns**. This creates a 512-column XLSX destination and assigns every field to the matching column name. You do not need to drag 512 assignments manually.
10. Inspect **Populated preview**. Use **Next columns** and **Previous columns** to see the wide row. The preview displays a portion at a time; export retains all 512 columns. Click **Confirm column mapping**, then **Export XLSX…**. Save a new file such as `my-sih-clinic-train-1031.xlsx` outside the repository.
11. Open the workbook in Excel or another spreadsheet viewer. Check that it has one data row, `record_id` 1031, and 512 headers. Compare it with the original source PDFs and the matching `doc_11_key.pdf`, `doc_12_key.pdf`, `doc_13_key.pdf`, `doc_18_key.pdf`, and `doc_24_key.pdf` references in `train/answer_keys/`.
12. Choose **File > Save project as…** to retain sources and review work. A saved project is separate from the exported Excel workbook. Reopening preserves sources and entered values but requires fresh confirmations, approval, and mapping confirmation.

## Complete the train packet

Add the remaining four patient groups to the same train project. Do not import patient 1031 again after the first trial. Each group needs its registration sheet, even when another document has the same name or a similar filename.

| Study record_id | Registration PDF | PDFs from `train/forms/`, in order |
| --- | --- | --- |
| 1031 | `doc_11.pdf` | `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, `doc_24.pdf` |
| 1032 | `doc_02.pdf` | `doc_02.pdf`, `doc_06.pdf`, `doc_07.pdf`, `doc_10.pdf`, `doc_17.pdf`, `doc_23.pdf` |
| 1036 | `doc_15.pdf` | `doc_03.pdf`, `doc_08.pdf`, `doc_15.pdf`, `doc_25.pdf`, `doc_28.pdf` |
| 1040 | `doc_14.pdf` | `doc_01.pdf`, `doc_04.pdf`, `doc_09.pdf`, `doc_14.pdf`, `doc_20.pdf`, `doc_26.pdf` |
| 1042 | `doc_19.pdf` | `doc_05.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_27.pdf` |

Review and approve each group. Return to **Map & export**, inspect all five rows, and confirm the mapping before exporting a new train workbook. Only approved patient rows are exported. The complete train workbook has five data rows, rather than 28 separate document rows.

## Run the test packet separately

Save the train project before starting test. Choose **File > New project** and select **Read SIH clinic forms** again. Use `test/forms/` for this project. Both splits reuse filenames, so check the folder before selecting PDFs.

Use these independently source-linked groups. Verify the study ID and demographics against the actual PDFs before confirming each bundle. Keep the index and keys out of document upload. Review, approve, map, and export test rows to a different workbook. Compare against `test/answer_keys/`.

| Study record_id | Registration PDF | PDFs from `test/forms/`, in order |
| --- | --- | --- |
| 1046 | `doc_09.pdf` | `doc_05.pdf`, `doc_06.pdf`, `doc_09.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf` |
| 1055 | `doc_17.pdf` | `doc_03.pdf`, `doc_15.pdf`, `doc_17.pdf`, `doc_26.pdf`, `doc_27.pdf` |
| 1060 | `doc_04.pdf` | `doc_04.pdf`, `doc_07.pdf`, `doc_08.pdf`, `doc_10.pdf`, `doc_11.pdf`, `doc_25.pdf` |
| 1066 | `doc_24.pdf` | `doc_02.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_24.pdf` |
| 1073 | `doc_01.pdf` | `doc_01.pdf`, `doc_14.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_20.pdf`, `doc_23.pdf` |

The project evaluation opened test only after train-based fixes, native train export checks, and a recorded 72-file freeze. The test set has now been used. Later development based on those answers needs a fresh holdout for a new independent accuracy claim. This operator walkthrough does not establish a fresh held-out score by itself.

## Check the source and record corrections

Keep a note for every manual change, including patient, source PDF, field, raw suggestion, corrected value, and source reason. Compare raw extraction and reviewed export separately.

Some target fields cannot be established by these pages. The clinic sheets do not print REDCap completion selectors, repeat instances, or access-group metadata. A radiology report marked FINAL does not establish an instrument completion code. An unmentioned imaging finding does not establish a negative. Conditional questions can remain printed but blank after a No response. Use the original source to decide whether an answer exists.

The answer keys contain reference values for evaluation. Do not fill a missing source answer from a key and then report it as successful extraction. The packet's native handwriting-style fonts are text in the PDF. They do not measure recognition of real handwriting or scanned paper.

Use the [dated clinic report](testing/SIH_CLINIC_2026-11-19.md) for counts, workbook checks, and coverage limits. Reader codes absent from the source stay blank. Three negative finding options are not derived from available normal measurements in each split; these are documented gaps. Full-split verification expects all five patients and is not an acceptance check for the one-patient trial.

## Use a supplied or custom blank spreadsheet

For a CSV destination, choose **Advanced > Spreadsheet > Import XLSX / CSV…** and select `spreadsheets/pace-import-template.csv`. Choose **Advanced > Spreadsheet > Use suggested assignments**, inspect the preview, and click **Confirm column mapping**, then **Export CSV…**.

CSV templates produce CSV output. For Excel, use **Use fields as columns** or import a supported blank XLSX file. For another blank template, drag a source field onto a destination column, or select the destination and choose its source from the dropdown. Resolve every destination with an assignment or an explicit **Leave blank** choice. Map the record identifier exactly once.

This is a wide patient staging export. Repeating-instrument REDCap upload requires a separate validated conversion and an authorized test-project import. The app does not submit records to REDCap.

## Resolve a blocked step

- If the reader reports an unsupported layout, check the packet and reader. Use **Read SIH clinic forms** for `sih_clinic_dataset`, **Read PACE printed forms** for the earlier `sih_dataset`, and **Read NEU clinic forms** for the older `Form NEU-xxx` sheets.
- If a bundle is blocked, check its registration, study ID, MRN, name, birth date, and source order. Keep different patients and repeated assessments in separate groups. Do not override a source identity to force a merge.
- If approval is blocked, check the displayed message, field confirmations, and reviewer name. Keep an unverifiable case unapproved.
- If export is disabled, check patient approval, unsaved answer edits, and mapping confirmation. Enlarging the window or scrolling the assignment panel can reveal controls below the visible area.
- If XLSX export is unavailable after loading a CSV template, use **Use fields as columns** or import a blank XLSX destination. Review and confirm its mapping again.
