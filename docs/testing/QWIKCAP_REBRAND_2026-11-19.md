# QwikCap naming and supplied-packet regression, 2026-11-19

Software revision `d150f7580317a87832875ef2310ea4859babc8d2` changes the display and package names to QwikCap. The native header has a smaller product title and no large ownership line. A small footer credit and the About ownership notice remain. New commits use `Pranav Mukund <54599543+pranavdabeast24@users.noreply.github.com>`. A mailmap associates earlier author aliases without rewriting history.

The [machine-readable check](QWIKCAP_REBRAND_2026-11-19.json) records the supplied-packet replay. The original [111 PDFs](../../datasets/sih-synthetic/README.md), totaling 10,353,882 bytes, match the supplied files byte for byte. Seven unchanged evaluator JSON files and the two actual app-written Excel readouts travel with the clone. The generated practice kit remains separate.

## Extraction equivalence

All 28 train PDFs and all 27 test PDFs were reprocessed with QwikCap's current source. The extraction tool received only each split's `forms` folder. It never received the index, answer keys, or expectations.

For train, an isolated checkout of frozen source `26fb90e` processed the same original forms. Every per-document value, evidence item, applicability list, issue, source context, input hash, and page count matches the new output. The archived test diagnostics from the frozen reader match the new test output on those same properties. This is a regression replay of a known-used dataset, not a fresh held-out score.

Of the original 37 frozen files, 33 remain byte-identical. The four changed files are `branding.py`, `desktop.py`, `build_desktop.py`, and `tools/verify_windows_release.py`. Their changes concern branding, the About notice, save-dialog naming, bundle identifiers, and a release verification folder label. Extraction, validation, review, schema, export rules, and dependencies remain unchanged. The original freeze record still describes the earlier evaluation.

| Check | Train | Test |
| --- | --- | --- |
| Raw mapped answer-key values | 600/600, 100% | 550/551, 99.82% |
| Additional unchecked-checkbox zeroes | 483/483 | 390/390 |
| Reviewed workbook destination cells | 2,560/2,560 | 2,560/2,560 |
| Unsupported key-only total rows | 9 | 8 |

The one raw test word omission remains unchanged. The reviewed workbook includes the original one manual source correction. Full-grid counts include blanks and zeroes. See the [original train](actual-pace-dataset-2026-11-18.md) and [test](heldout-pace-2026-11-18.md) reports for raw patient-grid results and the native source-to-export walkthroughs.

The existing readout comparator reopened both workbooks without modifying them. With extraction diagnostics included, it returns exit code 1 for the unsupported totals and the known raw omission. Both `readout_passed` values remain true. The combined raw failure is retained in the machine-readable report instead of being converted to a pass.

## Mac package and native UI

The [current source suite](QWIKCAP_UNIT_MACOS_2026-11-19.txt) ran 283 tests with seven Windows-only skips and no failures. The initial restricted-shell run could not use `ps` for process cleanup and skipped the Tk display check. A repeat with normal desktop and process access passed. No test or app code changed to accommodate the sandbox.

The native arm64 `QwikCap.app` built with the existing exact pins. Its [actual packaged companion](QWIKCAP_MAC_PRINTED_2026-11-19.json) passed the 16-field, 512-destination invented printed-form packaging check. This check is separate from the supplied dataset results. This Mac app remains a local development build. The private release provides the audited Windows ZIP and source for both platforms.

The actual app opened with the window title QwikCap and a clean empty workspace. Native UI inspection verified the restrained header, footer credit, and full ownership notice in About. [Empty workspace](QWIKCAP_EMPTY_2026-11-19.jpg) and [About](QWIKCAP_ABOUT_2026-11-19.jpg) screenshots record that inspection. The original supplied-dataset native export evidence was collected on Mac before this presentation-only rename.

## Reproduce

Use the [packet verification commands](../../datasets/sih-synthetic/README.md#verify-the-packet-and-workbooks) and a configured pinned Python environment. Run the source suite with `python -m unittest discover -s tests -v`. Build on the target OS, then invoke `tools/verify_pace_printed.py --helper <packaged FormbridgeWorker> --output <new verification folder>`.

Windows packaging is verified on Windows independently. A person-driven Windows walkthrough of the supplied packet, signing, Mac notarization, handwriting, camera capture, and live REDCap import remain separate work.
