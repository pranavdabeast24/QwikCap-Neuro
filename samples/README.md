# Fictional practice inputs

Every value is synthetic. These fixtures do not contain patient records.

- `practice-01-text.pdf` through `practice-05-text.pdf`: selectable PDF text.
- `practice-06-scan.pdf` through `practice-10-scan.pdf`: image-only PDFs, for actual OCR.
- `practice-06-scan.png`: equivalent image upload fixture.
- `blank-form.pdf`: same layout without answers.
- `sample-schema.json`: six fields and normalized answer regions (top-left origin).
- `answer-key.json` and `expected-redcap.csv`: exact expected normalized values.
- `redcap-import-template.csv`: header-only REDCap-shaped CSV template.
- `sample-data-dictionary.csv`: importable fictional REDCap field definitions.

The REDCap headers are `record_id,visit_date,age,consent,symptom_score,notes`.
Consent values export as 1 (Yes) or 0 (No). The optional notes value is blank
for DEMO-005; the review interface should preserve that deliberate blank.

Regenerate with `python generate_samples.py` from the application folder.
All records and layout values are fixed in that script. PDF timestamps and
document IDs are deterministic. No external service is contacted.
