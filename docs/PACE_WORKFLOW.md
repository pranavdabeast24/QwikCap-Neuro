# Review PACE forms as one patient row

QuickCap (CV) includes an optional catalog derived from the supplied 2026-11-17 PACE codebook and blank REDCap import table. It contains 512 exact destination column names across nine instruments. The reference CSV's single trailing empty header cell is omitted. No patient rows, source codebook PDF, questionnaire images, or training/test dataset are included.

## Create the patient source bundle

1. Choose **Study fields**, then **Load PACE fields**. The command is also available in the **Form type** menu. Loading the catalog does not create 512 extraction fields.
2. Choose **Combine patient PDFs**. Select the PDFs for one patient, review their order, and enter the study record ID. Confirm that the selected forms belong to that patient. Identity is entered and confirmed by the operator.
3. The source viewer shows an operator cover followed by the original form pages. The cover clearly identifies the study ID as operator-entered. The original PDFs and checksums remain in the saved project. The cover is not an original clinical document.
4. Name the extraction type. The bundle includes the explicit study ID field on its cover. Use **Study fields** to search names or labels, filter by instrument, and add or assign only the fields relevant to the bundle. Draw each answer mask or enter its page coordinates.
5. Apply the type. Review each suggested value against the source, correct it where necessary, confirm every selected field, and approve the patient record with a reviewer name.
6. In **Fields & spreadsheet**, map the selected fields to their exact destination names. The explicit action to leave remaining columns blank resolves only unassigned destinations. Review and confirm the full mapping before export.

One reviewed patient bundle produces one wide patient row. An applied bundle extraction type can be reused for later patients with the same page count, page shapes, source order and layout. Matching page dimensions do not establish matching clinical content. Keep different layouts in separate projects and verify every mask.

## Interpret the codebook metadata

The catalog preserves exact variable names, including checkbox suffixes, version suffixes and spelling in the import table. Baseline medication codes differ from the patient-facing versions. They are kept separately. Dates explicitly described as month/day/year in the codebook are normalized to ISO dates only for fields carrying that source-format rule; the displayed source evidence retains the original text. Numeric ranges and choice codes come from the reference metadata.

Missing checkbox data remains blank. It does not become `0`. `0` means an explicitly reviewed unchecked value. Checkbox image-mark recognition is not validated; enter or confirm the correct code manually when OCR does not provide a clear coded answer.

The PDF clips 69 option labels. Those catalog entries retain explicit uncertainty notes. `hit6_date` has no printed field label and uses its variable name with a note. Branching expressions and potential inconsistencies in the reference remain visible guidance. QuickCap does not execute those expressions, invent applicability, calculate excluded scores, or default instrument completion. Review conditional fields manually. Obtain the native REDCap data dictionary CSV to resolve clipped labels before a production configuration.

Additional annotations, including date-relative limits such as `Max: today`, are reference guidance unless represented by an implemented validator. Verify them during study configuration. Exact field names, known numeric bounds, configured choice codes and explicit source date formats are enforced by the application.

## Distinguish patient review rows from REDCap repeating rows

The requested export combines forms into one patient review row and retains all 512 destination columns. The supplied codebook enables repeating instruments. REDCap repeating imports require instrument and instance information; a wide patient review row is not automatically a valid import for those instruments. No repeat instance is invented or clinical assessments collapsed automatically. See the official institutional [REDCap import training](https://portal.redcap.yale.edu/sites/default/files/2026-01/REDCap_Data_Export_Import_Training_2026.01.20.pdf).

Use this output for reviewed staging. A study-approved repeating-instrument conversion and an authorized REDCap test-project import remain required before claiming upload compatibility. The prototype has no live REDCap connection.

## Keep sources and extraction types separate

A saved project contains the original PDFs, the combined working PDF, the patient ID entered by the operator, values, masks, drafts and template mappings. Reopening requires fresh field confirmation, patient approval and mapping confirmation. A reusable extraction-type file contains selected rules and masks only. It contains no patient ID value, source documents, answers or full field catalog.

Keep patient projects and outputs outside Git. All processing runs locally. The update adds no LLM, remote OCR, camera capture or automatic patient matching. Production patient-data controls and institutional approval are separate requirements.

## Bounds and verification

The shared limits are 600 active fields and destination columns. A patient bundle accepts at most 16 static PDFs and 32 total pages including the cover. Original input PDFs together and the combined PDF are each limited to 12 MiB. Original and combined source bytes count toward the 20 MiB session limit. Rendering is capped at 120 million aggregate pixels and 128 MiB of preview assets. Per-page limits, worker timeouts and the review-value limits remain enforced.

Interactive forms and visual annotations that cannot be represented faithfully are rejected with a flattened/scanned-copy instruction. Originals are never overwritten. Inputs currently accepted by patient bundling are PDFs; the separate individual-form route also supports the existing image formats.

Run the [portable PACE acceptance tool](../tools/verify_pace_flow.py) using the pinned source environment:

```sh
.venv/bin/python tools/verify_pace_flow.py
.venv/bin/python tools/verify_pace_flow.py --bundle dist/macos/QuickCapCV.app --output verification/pace-bundle
```

The tool generates fictional forms and an independent answer key. It checks two original PDFs becoming one patient row, masks, instrument-specific codes, date normalization and raw evidence, blank versus zero, mapping and approval gates, all 512 CSV/XLSX headers and cells, original PDF preservation and project reopening. It does not read the supplied reference PDF or a dataset, test actual handwriting, or validate a live REDCap import. Windows execution still requires target-platform testing.
