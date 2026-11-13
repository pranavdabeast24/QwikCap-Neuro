# Formbridge desktop source

Start with [README_DESKTOP.md](README_DESKTOP.md) for the native Mac and Windows application, the neurology training profile, build instructions and current limits. Launch `desktop.py` or the packaged Formbridge application. The browser instructions below describe the earlier interface and are retained as reference.

Formbridge is a local prototype for fictional research forms. Upload a document, inspect extracted answers against the source, confirm each value, and map the reviewed fields to an Excel or REDCap-like template. Preview every populated row before downloading approved records as XLSX or CSV. The real study form, REDCap dictionary, and import template are still needed.

The browser interface is a good fit for this stage: the same visual review and spreadsheet mapper can run on Windows, macOS, and Linux while the Python service processes files on the same computer. No cloud account or extraction service is used. This is a local service with a browser interface, rather than a standalone HTML file; keep the terminal running while using it. A desktop installer can wrap the same components after Windows validation. Browser camera capture can join the existing input pipeline later, with explicit permission.

## Start on Windows

Install Python 3.12 or later. In PowerShell, open this folder and run:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe server.py
```

Open http://127.0.0.1:8765 in Edge, Chrome, or Firefox. On later runs, double-click `start-windows.bat`.

For image-only scans, install Tesseract with English language data using the Windows distribution linked in the [Tesseract installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html#windows). Add its executable to PATH or set `FORMBRIDGE_TESSERACT` to its full path before starting the app. The app never downloads an OCR model automatically.

```powershell
$env:FORMBRIDGE_TESSERACT = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
.venv\Scripts\python.exe server.py
```

The Python service and browser interface are portable. Windows execution has not been tested in this build environment.

## Start on macOS or Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Open http://127.0.0.1:8765. Tesseract works when installed and on PATH. macOS can also use the included Apple Vision helper when Swift is available. PDF text extraction does not need an OCR engine. OCR failure remains visible and leaves the document available for manual review.

## Practice the complete workflow

1. Click **Load 10 sample documents**. The app reads ten actual PDFs from `samples`, renders their pages, and extracts suggestions. Five have text layers and five contain only page images.
2. Open a record. Compare each answer with its source region. Correct OCR mistakes and confirm every field, including an intentionally empty optional field.
3. Enter a reviewer name and approve the record. Confirmations alone do not approve it.
4. Choose **Spreadsheet preview**. Try **REDCap XLSX** or **Intake XLSX · header row 3**, or import your own blank XLSX/CSV. Choose the worksheet and header row if detection needs adjustment.
5. Drag each extracted source field onto its destination column, or use the column's dropdown. Assignments apply to every record; changing the sample document changes the example values, not the associations. Select **Leave blank** for a deliberately unused column. Resolve every column, map the record identifier once, and remove duplicate assignments.
6. Inspect the full row preview, acknowledge the mapping review, and confirm the assignments. Mapping confirmation and record approval are separate. Download **filled XLSX** or **filled CSV**; only approved records are included. Unapproved rows remain visible in the preview with their status. Friendly headers are for a generic spreadsheet; REDCap imports require the actual project's variable names and codes. Inspect CSV in a REDCap test project's import tool before importing.
7. Save a project explicitly if you need to continue later. Loading restores source files, draft values, the original spreadsheet, and column associations. It reprocesses documents and clears every field confirmation, record approval, and mapping confirmation.

You can also upload `samples/practice-06-scan.png` to test the image path, or upload one PDF at a time. `samples/answer-key.json` contains the fictional expected values. Regenerate the practice set with `python generate_samples.py`.

## Included spreadsheet examples

`spreadsheets/redcap-template.xlsx` has six REDCap-like variable headers in row 1. `friendly-template.xlsx` has a title, headers in row 3, and a different column order. `redcap-template.csv` is headers only. The blank XLSX templates have styled empty entry rows and literal validation rules. `template-manifest.json` records their intended associations.

`filled-redcap.xlsx`, `filled-friendly.xlsx`, and their CSV counterparts contain all ten fictional records downloaded from the application's real HTTP export path. They demonstrate that values follow field associations even when the destination columns are reordered. Identifiers, ISO dates, and answer codes stay text; ordinary numeric measures stay numeric. Empty optional answers and zero values are preserved. These examples do not establish compatibility with an actual REDCap project.

Only simple blank tabular templates are supported. Existing destination data, merged data cells, formulas, macros, embedded objects/images, external links, and complex Excel features are rejected. XLSX export keeps the selected sheet's headers and useful layout, removes unrelated sheets and metadata, and makes populated cells visible and readable. It does not preserve arbitrary Excel behavior. CSV export includes headers and values without title rows or workbook formatting. **Export field CSV** under source setup exports the source schema directly; the spreadsheet workspace exports your chosen destination columns.

## Configure your REDCap fields

Use **Field mapping** to import a REDCap data dictionary CSV or edit the JSON schema under **Advanced field definitions**. The fictional `samples/sample-data-dictionary.csv` lets you practice this import. A headers-only data import template does not provide enough information about types, answer codes, or labels. The first field must be your REDCap record identifier, with type `text`. Its original name stays in the exported CSV.

To map a fixed-layout form visually, open a source document in the review queue, then choose **Field mapping**. Select the target field and page. Drag a rectangle around the answer and click **Apply field mapping**. Choose **Use label matching for this field** to remove its region. You can adjust normalized coordinates in the advanced editor if needed.

Each field has a unique REDCap variable name, a label, a type, and a required flag. Choice fields map exact answer labels to their REDCap codes. Aliases support alternative printed labels. Regions select a rectangular answer area on a fixed page layout. Their coordinates use fractions of the page, measured from its top-left corner.

```json
{
  "name": "consent",
  "label": "Consent",
  "type": "choice",
  "required": true,
  "choices": {"1": "Yes", "0": "No"},
  "region": {"page": 1, "x": 0.32, "y": 0.51, "width": 0.58, "height": 0.07}
}
```

Changing a mapping reprocesses documents and clears approvals. Region mappings assume aligned pages of the same form version. Rotated, shifted, handwritten, marked-checkbox, and poor-quality scans need separate validation. The prototype does not infer clinical meaning or guess missing values.

Dictionary import supports text, notes, integer, number, ISO date, dropdown, radio, yes/no, true/false, and checkbox columns. It reports skipped fields and unsupported validation. Checkbox columns expand to `variable___code`. Branching logic is not evaluated, so conditional fields require manual applicability review. Calculations, uploads, repeating instruments, longitudinal events, and direct REDCap API submission are outside this prototype. Verify the exported column names against the actual test project's template.

## Data and security boundaries

The server binds only to `127.0.0.1`. It uses a random local session cookie, per-run CSRF token, Host and Origin checks, no cross-origin API access, and a restrictive content security policy. Uploads have size, page, image dimension, file type, and processing limits. Values and choice codes are validated again at approval and export. Uploaded filenames never become filesystem paths. The interface has no external scripts, fonts, analytics, or cloud extraction calls. Mapping and record revisions reject stale-tab changes and stale preview downloads. Mapping confirmation cannot bypass record review.

Records and OCR text live in process memory and bounded local worker processes. Rendered page images live in a private temporary directory. A normal shutdown removes that directory. A crash can leave temporary files, and the operating system can write memory to swap. Reset removes temporary images but does not securely erase storage. Explicit project downloads contain source documents and review values. CSV exports and downloaded projects persist wherever your browser saves them. The local audit list is a session activity log, not a tamper-evident regulatory audit system.

Each document is limited to 12 MB and eight pages. A session holds at most 60 documents and 20 MB of source files. Workers have a 180-second document timeout, and each OCR call has a 45-second timeout. A spreadsheet is limited to 4 MB, 100 columns, 2,000 rows, 300 archive entries, and 30 MB expanded content. Spreadsheet parsing and export use isolated workers with a 30-second timeout. XML is preflighted with defusedxml; unsafe ZIP members and unsupported package parts are rejected. Dynamic formulas are rejected; literal numeric and quoted-choice validation constants are accepted. XLSX output stores formula-like text as literal text; CSV rejects unsafe formula-like values. Review text and mapping sizes are capped so a saved project fits within the 40 MB import limit.

This prototype does not provide multi-user authentication, institutional access controls, encryption at rest, managed retention, validated OCR accuracy, or a compliance determination. Use fictional data until your research, privacy, security, and applicable AI governance teams approve the complete environment and workflow. A personal computer and a local OCR engine do not establish approval to process PHI.

## Add camera capture later

Capture should produce the same PDF or image input as file upload. The document pipeline already keeps capture, rendering, OCR, mapping, review, and export separate. Camera permissions are disabled in this build. Add a capture screen only after selecting the hardware, then evaluate focus, lighting, perspective correction, page alignment, and field accuracy against a representative fictional test set.

## Verify a change

Run these commands after installing the requirements:

```sh
python -m unittest discover -s tests -v
python verify_samples.py
python verify_spreadsheet_flow.py
```

The last command processes the ten PDFs through the real service, confirms and approves their exact extracted answers, downloads the XLSX/CSV outputs, reopens them independently, and compares actual cells with the answer key. It rewrites only the generated filled examples and its verification report. Tests also exercise rejected templates, mapping gates, stale revisions, project reload, and HTTP boundaries. See `VERIFICATION.md` for measured results and limitations.

Dependencies are pinned to the versions used here. Review their licenses and vulnerability status under your institution's software process before deploying the app.
