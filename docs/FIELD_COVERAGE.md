# Find a field and understand a blank export cell

The export contains all 512 PACE columns. One PDF usually supplies only part of that study record.
The answer list shows fields detected on the patient's uploaded forms.
The separate study-field catalog contains all 512 destinations.

## Find a REDCap field

1. Open the source page containing the answer.
2. Choose **Answer tools… > Add PACE field…**.
3. Clear **Search** and select **All instruments** to see the complete catalog.
4. Search for the exact variable name from the CSV header, or its label.
5. Select the field and click **Use field**. Draw its answer area, then check the suggestion or enter the correct value.

Choose a field from the instrument shown on that page. A patient questionnaire and a clinician questionnaire have separate destinations.
Patient variables often end in `_v2`. Their codes can differ from clinician codes, so the app does not copy one version into the other.

Record IDs and sticker identity fields use the patient-group workflow.
REDCap repeat and data-access-group columns are export metadata, not answer boxes on the source.
The app does not automatically assign repeat metadata or form-completion codes.

## Read an empty cell

An empty cell means the app has no accepted value for that destination.
The source form may be absent, a conditional follow-up may be blank, or an answer may need manual review.
Approval confirms the reviewed source fields. It does not fill every study column.

Zero is a recorded code or measurement. It is not a general replacement for an empty cell.
For example, `periods_v2` accepts codes `1`, `2`, and `3`. If no option is marked, writing `0` would create an invalid answer.
For checkboxes, the app writes `0` only when its source evidence supports an unchecked option.

Detected text questions remain visible when their answers cannot be read. Select the field to see its source area, then correct the answer or confirm an optional blank against the PDF.
An unreadable answer is not automatically classified as a verified source blank.

## Try the four original examples

The [four supplied patient PDFs](../datasets/sih-variants-synthetic/README.md) are now in the repository.
Each is a four-page patient intake questionnaire for one fictional patient.
They do not include that patient's clinician questionnaire, HIT-6, imaging, or procedure forms.
Those other template columns remain blank until the corresponding sources are supplied and reviewed.
Import all of one patient's forms together so they share one patient row.

The owner confirmed that all currently supplied project test documents and example exports are synthetic.
The [coverage audit](testing/FIELD_COVERAGE_2026-11-20.md) explains the reviewed one-patient CSV.
