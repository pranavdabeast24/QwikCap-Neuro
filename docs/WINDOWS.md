# QwikCap on Windows

## Clinic-enabled build status

Use the [SIH clinic delivery](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19) for the new packet. Its runtime includes the post-evaluation narrative hardening at `da33054`. The [current Windows verification run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44506631638) targets that runtime. See [the hardening record](testing/SIH_CLINIC_HARDENING_2026-11-19.md) for the final package checks and archive hashes, and compare your download with the release's `SHA256SUMS.txt`.

The earlier [frozen-reader Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44501222833) passed all 12 acceptance stages and 311 tests with one POSIX-only skip at `e2fbd2e`. Its archive audit belongs to that source. It is separate from the hardened delivery.

Check **Advanced > Form type** for **Read SIH clinic forms** before uploading the new `sih_clinic_dataset/` packet. The earlier `qwikcap-2026-11-19` prerelease lacks this reader. Follow the [SIH clinic walkthrough](SIH_CLINIC_WORKFLOW.md) for the new forms. Custom masks remain the default.

Windows acceptance uses generated fictional fixtures and the real packaged worker. The [actual supplied clinic evaluation](testing/SIH_CLINIC_2026-11-19.md) ran on Mac before the later hardening. Its source was frozen before test access. The current test packet has now been used, and a later replay does not establish a fresh held-out result. Neither check establishes a complete person-driven workflow on a Windows laptop with those documents.

## Earlier tested preview

The historical [QwikCap pilot prerelease](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-2026-11-19) was built from software revision `d150f75`. Its [native Windows acceptance run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44473031594) ran 283 source tests with one POSIX-only skip and passed all 11 packaging and verification stages. It uses QwikCap naming and quieter branding, with the PACE printed reader and the three-menu, two-tab interface. This is a download for the earlier packet, not the new SIH clinic reader.

That earlier `QwikCap-Windows-x64.zip` has SHA-256 `bc86b9ab0182fb38f2b6772dd5e45977e4c99523710909568429ed3ad6ba978f`. Its archive and component hashes were checked independently. Windows acceptance used generated fixtures; actual train and held-out desktop QA ran on Mac. A complete person-driven Windows laptop workflow remains unverified. See [the historical Windows record](testing/QWIKCAP_WINDOWS_2026-11-19.md).

## Open the portable app

Use a 64-bit Windows computer. Download the Windows ZIP from the private
[repository releases](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases),
while signed into a GitHub account with repository access.

1. In File Explorer, right-click the ZIP and choose **Extract All**. Extract to
   a folder where your account can write, such as Documents.
2. Open the extracted `QwikCap` folder and double-click `QwikCap.exe`.
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

For the current clinic packet, choose **Advanced > Form type > Read SIH clinic forms**, then **Add documents > Combine PDFs for one patient**. Include registration and confirm its printed Research Study ID. The reader links the other PDFs through MRN, full name, and birth date. Preserve leading zeroes in MRN. The [clinic walkthrough](SIH_CLINIC_WORKFLOW.md) lists the train groups and expected export shape.

Use **Read PACE printed forms** for the earlier `sih_dataset/` packet and **Read NEU clinic forms** for the older `Form NEU-xxx` pages. The [PACE guide](PACE_PRINTED_WALKTHROUGH.md) preserves that earlier workflow. Custom masks remain available for other layouts. Several clinic PDFs become one reviewed row with 512 columns. Repeating REDCap instruments need a separate validated conversion before live-project import.

## Enable OCR for scanned documents

Text PDFs can use their existing text layer. Scans and images need a local OCR
engine for suggested answers. Without OCR, sources remain available for manual
review and entry.

Install the 64-bit Windows Tesseract distribution linked by
[Tesseract's installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
and the [UB Mannheim Windows installer page](https://github.com/UB-Mannheim/tesseract/wiki).
Keep English language data selected. Use the installer's suggested folder or a
new dedicated folder. Tesseract is a separate installation and is not included
or automatically downloaded by QwikCap.

Close and reopen QwikCap after installation. It looks on `PATH`, then in the
usual `Tesseract-OCR` locations under Program Files and your local application
programs folder. You should not need to edit `PATH` for a standard installation.

For a custom installation, start the app from PowerShell with an explicit path:

```powershell
$env:FORMBRIDGE_TESSERACT = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
& 'C:\Users\YOUR_NAME\Documents\QwikCap\QwikCap.exe'
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
