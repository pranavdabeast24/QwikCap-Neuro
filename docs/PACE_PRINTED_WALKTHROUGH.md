# Review PACE printed forms and export Excel

This guide applies only to the earlier `sih_dataset` packet under `datasets/sih-synthetic/`. For the new `sih_clinic_dataset`, use **Read SIH clinic forms** and the [clinic walkthrough](SIH_CLINIC_WORKFLOW.md).

You will create an Excel file with one reviewed patient row, then repeat the same steps for the rest of the packet. No camera is needed for these PDFs.

## Open the app and find the packet

1. Open your current **QwikCap** app. On Windows, download `QwikCap-Windows-x64.zip` from the [private release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-2026-11-19), extract the whole folder, and open `QwikCap/QwikCap.exe`. Mac users can use their existing local app or [source setup](GETTING_STARTED.md).
2. Download and extract `QwikCap-Source-and-Supplied-Packet.zip` from that release, or use your clone. Find the folder containing the project's root [README](../README.md). The original forms are in `datasets/sih-synthetic/train/forms/` and `datasets/sih-synthetic/test/forms/`. Your original Desktop copy of the same packet also works.
3. Keep the sibling `answer_keys/` folders available for checking your results. The dataset index and answer keys are references. Upload only PDFs from a `forms/` folder.

## Export your first patient

1. If another project is open, save it and choose **File > New project**. Choose **Advanced > Form type > Read PACE printed forms**. On Mac you can press Command-Shift-U. On Windows use Ctrl-Shift-U. Check that the mode reads **PACE printed forms · review required**. This selects the reader for these supplied layouts. You do not need to draw masks or load a separate extraction type for this walkthrough.
2. Choose **Add documents… > Combine PDFs for one patient…**. In `train/forms/`, select `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, and `doc_24.pdf`. Hold Command on Mac or Ctrl on Windows to select the five files.
3. In **Combine patient PDFs**, enter `1031` in **Study record_id**. Check each PDF's printed identity against this ID. Keep the files in the order listed above. Use **Move selected PDF up** or **Move selected PDF down** if needed.
4. Check **I verified every PDF is for this patient and this is the intended source order.** Click **Combine into one patient row** and wait for processing. The document queue should show **Patient 1031**. Its combined source starts with an operator-entered ID cover, followed by the original PDFs.
5. In **Design & review**, select a field to see its suggested answer beside the source. Check the whole answer and the marked option. Edit the answer box or choice dropdown when needed, then click **Confirm & next**. Command-K on Mac or Ctrl-K on Windows does the same thing. Use **Expand…** for long text. Confirm every applicable field against the source; clicking through without reading does not check extraction accuracy.
6. Enter your name in **Reviewer**, then click **Approve document**. The queue should show **Approved** for Patient 1031. Only source-observed fields need confirmation. A question absent from these forms stays blank in the destination. A visibly unanswered question also stays blank; do not invent an answer to complete the row.
7. Open **Map & export** and click **Use fields as columns**. QwikCap creates an XLSX destination with all 512 exact field names and automatically assigns each field to its matching column. You do not need to drag 512 fields manually. Inspect the assignments and **Populated preview**. **Next columns** shows the next portion of the wide row; the export includes every column.
8. Click **Confirm column mapping**, then **Export XLSX…**. Save a new file such as `my-train-1031.xlsx` in your own output folder. Open it in Excel or another spreadsheet viewer. It should contain one data row for `record_id` 1031 and 512 headers. Blank cells are expected for instruments or questions absent from this patient's documents.
9. Compare your results with `doc_11_key.pdf`, `doc_12_key.pdf`, `doc_13_key.pdf`, `doc_18_key.pdf`, and `doc_24_key.pdf` in `train/answer_keys/`. Check identifiers, choice codes, checkbox zeroes, dates, and complete text. Dates may appear in normalized `YYYY-MM-DD` form. The keys include some total-score entries without destination columns; those are not exported.
10. Choose **File > Save project as…** to keep your sources and review work. Save outside the repository. A project is different from the Excel export. Reopening the project preserves its sources and values but requires fresh confirmations, patient approval, and mapping confirmation.

The primary interface has **File**, **Advanced**, and **Help** menus and two tabs. You can use the menu commands above while **Show advanced controls** is off. If controls fall below the visible area, enlarge the window or scroll the assignment panel.

## Finish all five train patients

In the same train project, repeat the combine, review, and approval steps for the remaining four patients. Patient 1031 is already present from the first trial; do not import that group a second time. Import one group at a time. Use the listed source order, and verify the printed IDs before confirming each group.

| Study record_id | PDFs from `train/forms/`, in order |
| --- | --- |
| 1031 | `doc_11.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf`, `doc_24.pdf` |
| 1032 | `doc_02.pdf`, `doc_06.pdf`, `doc_07.pdf`, `doc_10.pdf`, `doc_17.pdf`, `doc_23.pdf` |
| 1036 | `doc_03.pdf`, `doc_08.pdf`, `doc_15.pdf`, `doc_25.pdf`, `doc_28.pdf` |
| 1040 | `doc_01.pdf`, `doc_04.pdf`, `doc_09.pdf`, `doc_14.pdf`, `doc_20.pdf`, `doc_26.pdf` |
| 1042 | `doc_05.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_27.pdf` |

Return to **Map & export**, inspect all five patient rows, confirm the mapping, and export a new `my-train-readout.xlsx`. Check that all five patients are approved. Exports include approved rows only. The complete train export has five data rows and 512 columns, or 2,560 destination cells. It does not have 28 patient rows.

## Repeat with the supplied test set

Save the train project, choose **File > New project**, and select **Read PACE printed forms** again. Use `test/forms/` for this project. The test folder reuses filenames such as `doc_01.pdf`, so check the folder before selecting files.

| Study record_id | PDFs from `test/forms/`, in order |
| --- | --- |
| 1046 | `doc_05.pdf`, `doc_06.pdf`, `doc_09.pdf`, `doc_12.pdf`, `doc_13.pdf`, `doc_18.pdf` |
| 1055 | `doc_03.pdf`, `doc_15.pdf`, `doc_17.pdf`, `doc_26.pdf`, `doc_27.pdf` |
| 1060 | `doc_04.pdf`, `doc_07.pdf`, `doc_08.pdf`, `doc_10.pdf`, `doc_11.pdf`, `doc_25.pdf` |
| 1066 | `doc_02.pdf`, `doc_21.pdf`, `doc_22.pdf`, `doc_24.pdf` |
| 1073 | `doc_01.pdf`, `doc_14.pdf`, `doc_16.pdf`, `doc_19.pdf`, `doc_20.pdf`, `doc_23.pdf` |

Combine each group, review every applicable answer, enter your reviewer name, and approve each patient. Create the 512-column destination, confirm its mapping, and export a separate `my-test-readout.xlsx`. Expect five data rows. Compare against `test/answer_keys/`, not the train keys.

The current reader has one known test error. In patient 1046's `doc_18.pdf`, field `personal_ctdisorder_v2` suggests `hypermobility` while the source reads `Joint hypermobility`. Check the source and correct the full text before confirming it. Keep notes on any manual correction so you can distinguish raw extraction from your reviewed export. This test set has already been evaluated and is now regression material.

## Use the supplied CSV template or your own spreadsheet

For a CSV output, choose **Advanced > Spreadsheet > Import XLSX / CSV…** and select `spreadsheets/pace-import-template.csv`. Then choose **Advanced > Spreadsheet > Use suggested assignments**. Inspect the populated preview and assignments, click **Confirm column mapping**, then **Export CSV…**. These menu actions remain available when advanced controls are hidden. CSV templates produce CSV output. Use **Use fields as columns** or a supported blank XLSX template when you want an Excel workbook.

For another blank template, first import it with **Advanced > Spreadsheet > Import XLSX / CSV…**. Drag a source field onto a destination column, or select the destination and choose its source from the assignment dropdown. Inspect the preview after each change. Every destination needs an assignment or an explicit **Leave blank** choice before the full mapping can be confirmed. Keep the record identifier mapped exactly once.

The output is a reviewed patient staging table. Repeating-instrument REDCap import still requires a separate validated conversion. This walkthrough does not submit anything to REDCap.

## Check a complete export with the independent verifier

Manual source review and the answer-key PDFs are sufficient to walk through the app without a terminal. Developers with the pinned Python environment can also check a complete five-patient workbook. From the repository root, replace the output path with your file:

```sh
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/train-expected.json --census-json datasets/sih-synthetic/evaluation/train-form-census.json --xlsx "/path/to/my-train-readout.xlsx"
python tools/verify_actual_pace_readout.py --expected-json datasets/sih-synthetic/evaluation/test-expected-comparator.json --census-json datasets/sih-synthetic/evaluation/test-form-census.json --xlsx "/path/to/my-test-readout.xlsx"
```

Use `.venv/bin/python` on Mac or `.venv\Scripts\python.exe` on Windows if your environment is not activated. A correct complete reviewed workbook reports `readout_passed: true`, `full_checked_cells: 2560`, `patient_rows_matched: 5`, and no issues. These complete-split commands will report missing patients for the one-patient trial. They inspect the exported workbook and do not prove that you reviewed it through the app.

## If a step is blocked

- If the mask designer appears, select **Advanced > Form type > Read PACE printed forms** for these supplied layouts. **Load PACE fields** only loads reference metadata and does not activate the printed-form reader.
- If combining is blocked, check the folder, selected filenames, printed patient IDs, source order, and confirmation checkbox. Keep different patients and repeated assessments in separate groups.
- If approval is blocked, review the displayed validation message, confirm every applicable field, and enter a reviewer name. Keep source-observed missing answers blank when appropriate.
- If export is disabled, check patient approval, resolve any unsaved answer edit, and click **Confirm column mapping**. Only approved patient rows are exported.
- If **Export XLSX…** is unavailable after loading a CSV template, click **Use fields as columns** or choose a supported blank XLSX destination, then review and confirm its mapping.

The reader checks printed record IDs and demographics against the confirmed patient bundle. Unknown instruments, conflicting source identities, repeated assessments of one instrument, and conflicting source values block the one-row merge. A visibly unchecked checkbox can produce `0`. An absent question stays blank, and a visible unanswered radio stays blank and remains part of the review. Editing an answer cannot hide an observed field.

The shorter [PACE workflow reference](PACE_WORKFLOW.md) describes the reader and custom-mask alternatives.
