# QwikCap Windows package, 2026-11-19

The [native Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44473031594) built software commit `d150f7580317a87832875ef2310ea4859babc8d2`. It passed all 11 acceptance stages and 283 source tests, with one POSIX-only process test skipped. The runner used Windows Server 2022 x64, Python 3.12.10, the unchanged dependency pins, and separately installed hash-verified Tesseract. OCR is not bundled.

The current [private pilot release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-2026-11-19) includes `QwikCap-Windows-x64.zip`, 48,363,996 bytes, with SHA-256 `bc86b9ab0182fb38f2b6772dd5e45977e4c99523710909568429ed3ad6ba978f`.

Independent inspection of the downloaded ZIP verified the checksum, both x64 executables, all 76 outer native files, all 125 helper-embedded native files, and all 32 notice payloads against the build manifest. The GUI and companion worker each contain the identical canonical 512-field PACE catalog. The renamed executable is `QwikCap/QwikCap.exe`; the compatible helper remains `FormbridgeWorker.exe`. No Windows executable was run on Mac.

The acceptance run starts the real relocated GUI and companion outside the checkout with Python absent from the packaged `PATH`. It checks Unicode paths and JSON, a no-OCR path, source and packaged custom masks, patient bundles, local OCR, and reopened exports. Generated fixtures match 60 extracted fields and 240 export cells across ten documents. The invented printed-form packaging fixture matches all 16 fields and retains 512 destination columns.

Evidence is retained in the [run result](QWIKCAP_WINDOWS_2026-11-19.json), [independent archive audit](QWIKCAP_WINDOWS_ARCHIVE_2026-11-19.json), and [build manifest](QWIKCAP_WINDOWS_BUILD_MANIFEST_2026-11-19.json). The component manifest is not an SPDX or CycloneDX SBOM.

The supplied 28-train and 27-test packet's native review and export walkthroughs were performed on Mac. The Windows generated-fixture checks do not establish a person-driven Windows walkthrough of that packet. The original raw held-out word omission remains unchanged by the rename. This is an unsigned private development build.
