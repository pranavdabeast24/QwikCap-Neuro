# Windows printed PACE pilot, 2026-11-18

Built source: `b139c4656c2f9f9ce356c278830b4699a81beecd`. Its runtime is identical to the reader frozen at `26fb90e` before held-out access.

[Windows acceptance run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44424411229) succeeded on Windows Server 2022 x64 with Python 3.12.10 and the pinned dependencies. All 11 stages passed. The source suite ran 283 tests; one POSIX-only process-cleanup test was skipped.

The portable ZIP was extracted outside the checkout and ran without Python on the packaged application's PATH. Checks cover native startup, Unicode JSON and paths, the no-OCR route, local OCR, custom masks, patient bundles, and spreadsheet exports. The added printed-form check matched all 16 fields in an invented PACE form and retained all 512 destinations. Both the GUI and worker contain the same catalog. This catches the missing-worker-resource failure reproduced during Mac UI acceptance.

The ten packaged practice documents matched 60 extracted fields and 240 reopened export cells. These generated-fixture checks are separate from the [Mac actual train](actual-pace-dataset-2026-11-18.md) and [held-out desktop](heldout-pace-2026-11-18.md) workflows. An actual-dataset Windows GUI walkthrough remains unverified.

Independent archive inspection matched the ZIP, build manifest, 76 outer native files, 125 embedded native files, and 32 bundled notice files against their hashes. The package has a component build manifest, not a separate SPDX or CycloneDX SBOM document. Tesseract is installed separately and is not bundled.

[Download the private pilot](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/quickcap-cv-printed-pace-2026-11-18). Keep the complete extracted `QuickCapCV` directory together.

ZIP: `QuickCapCV-Windows-x64.zip`, 48,373,698 bytes.

SHA-256: `2da5c9fe56ace1a01373b49764511c152268173c75ea415217a9dc40246881f7`.

The [acceptance results](WINDOWS_PRINTED_PACE_2026-11-18.json) and [independent archive audit](WINDOWS_PRINTED_PACE_ARCHIVE_2026-11-18.json) retain the measured evidence without document contents.
