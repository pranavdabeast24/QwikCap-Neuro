# QuickCap (CV) on Windows

Property of Capitolinus Ventures

## Open the portable app

Use a 64-bit Windows computer. Download the Windows ZIP from the private
[repository releases](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases),
while signed into a GitHub account with repository access.

1. In File Explorer, right-click the ZIP and choose **Extract All**. Extract to
   a folder where your account can write, such as Documents.
2. Open the extracted `QuickCapCV` folder and double-click `QuickCapCV.exe`.
   Keep the whole folder, including `_internal`, together. Do not run the app
   inside the ZIP or copy the executable by itself.
3. The workspace starts empty. Import a fictional PDF or image, name a form
   type, select answer regions, and choose a text field as the record ID.
   Apply the type, review and confirm each answer, enter a reviewer, and
   approve the record.
4. Load a blank CSV or XLSX destination, match the extracted fields to columns,
   inspect the preview, confirm the assignments, and export. Save a type to
   reuse its rules. Save a project to retain documents and work in progress.

The portable app includes Python, Tk and its application dependencies. You do
not need to install Python, Excel or a web browser. It does not install itself,
create an account or send documents to an extraction service. The build is an
unsigned development prototype; managed computers may require an administrator
to approve it under the institution's software policy.

For the supplied PACE destination, follow
[PACE_WORKFLOW.md](https://github.com/pranavdabeast24/capitolinus-form-extraction/blob/main/docs/PACE_WORKFLOW.md).
Several PDFs can become one reviewed patient row. Repeating REDCap instruments
still need a separate validated conversion before import into a live project.

## Enable OCR for scanned documents

Text PDFs can use their existing text layer. Scans and images need a local OCR
engine for suggested answers. Without OCR, sources remain available for manual
review and entry.

Install the 64-bit Windows Tesseract distribution linked by
[Tesseract's installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
and the [UB Mannheim Windows installer page](https://github.com/UB-Mannheim/tesseract/wiki).
Keep English language data selected. Use the installer's suggested folder or a
new dedicated folder. Tesseract is a separate installation and is not included
or automatically downloaded by QuickCap (CV).

Close and reopen QuickCap after installation. It looks on `PATH`, then in the
usual `Tesseract-OCR` locations under Program Files and your local application
programs folder. You should not need to edit `PATH` for a standard installation.

For a custom installation, start the app from PowerShell with an explicit path:

```powershell
$env:FORMBRIDGE_TESSERACT = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
& 'C:\Users\YOUR_NAME\Documents\QuickCapCV\QuickCapCV.exe'
```

Replace the second path with the actual extracted app location. An invalid
explicit override disables OCR discovery until corrected or removed. Suggested
OCR answers always require comparison with the source and human confirmation.

## Files and troubleshooting

Save projects and exports in a location you control. Projects contain original
source documents and answers; extraction-type files contain rules and geometry.
Reopening a project clears approvals and spreadsheet confirmation for another
review. The app does not encrypt these saved files or manage user access.

If Excel has an existing output open, close that workbook before saving over it,
or choose another filename. A failed save should preserve the prior file and
leave your unsaved changes available to save again.

If the app does not open, first check that the ZIP was fully extracted and
`_internal` is still adjacent to the executable. Use only the release from this
private repository, and consult your administrator if device policy blocks it.
When reporting an issue, include the release version, Windows version and the
steps using a fictional document. Do not attach patient records or source-bearing
projects to GitHub issues.

## Build and verification

The manually dispatched workflow is
[windows-build.yml](https://github.com/pranavdabeast24/capitolinus-form-extraction/blob/main/.github/workflows/windows-build.yml). It uses a Windows
runner and generated fictional inputs. It does not run automatically on pushes
or pull requests and does not publish a release or receive research documents.
See [TESTING.md](https://github.com/pranavdabeast24/capitolinus-form-extraction/blob/main/docs/TESTING.md)
for the recorded results and remaining manual checks.

Developers can build locally using
[GETTING_STARTED.md](https://github.com/pranavdabeast24/capitolinus-form-extraction/blob/main/docs/GETTING_STARTED.md).
Native packaging must run on Windows. The source launcher
`start-desktop-windows.bat` is for a configured Python environment; it is not
needed for the portable app.
