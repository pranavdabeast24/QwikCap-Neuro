# SIH clinic hardening after frozen evaluation

The downloadable app contains software revision `da33054561d836ff336e9ad72fec07e49bac21de`, plus later documentation and dataset commits. The original [train/test evaluation](SIH_CLINIC_2026-11-19.md) remains measured at `e2fbd2e`. All 72 frozen files stayed unchanged through its completed native test export. The [completion snapshot](SIH_CLINIC_FROZEN_EVALUATION_COMPLETE_2026-11-19.json) preserves that boundary.

After evaluation, an independent code review used invented inputs and found two errors:

- “CSF-venous fistula cannot be excluded” and “may be present” could become a positive finding.
- Known procedure terms in “no neck pain” and “not burning” could become positive location or quality options.

The fix leaves these suggestions unresolved and adds field-specific source-review messages. Negated known quality terms do not fall back to Other. Explicit “no headache” remains a valid selected option, and positive terms in separate comma or semicolon clauses are preserved. The reader remains a bounded rule-based parser for supported layouts, with source review required.

Failing regressions were committed before the production change. Five additional test methods cover the uncertainty variants, negated descriptors, Other fallback, explicit no-headache, and both mixed-term orders. All 11 narrative tests and four independent qualifier probes pass. See [the probe evidence](SIH_CLINIC_QUALIFIER_PROBES_2026-11-19.json).

Only `clinic_narratives.py` and `tests/test_clinic_narratives.py` differ among the 72 frozen files. The other 70 remain identical. Neither the three threshold-negative gaps nor any key/code mapping was adjusted from held-out answers. This later fix and replay are **regression evidence, not a new independent held-out evaluation**.

## Supplied-form replay and current native app

The [55-form replay](SIH_CLINIC_HARDENING_REPLAY_2026-11-19.json) compares every source result with its frozen diagnostic counterpart. Values, applicability, source context, issue lists, source PDF hashes, and page counts are unchanged for all 28 train and 27 test forms. Evidence serialization is not claimed to be byte-identical. The replay did not read answer keys, create approvals, or export a workbook.

The rebuilt native Mac app separately imported patient 1031's five original PDFs from the repository copy, confirmed 200 applicable fields, approved the patient, confirmed the 512-column mapping, and exported XLSX. All 512 ordered headers and typed data cells match that patient's row in the frozen train workbook, with zero value edits. See [native regression evidence](SIH_CLINIC_HARDENING_NATIVE_2026-11-19.json). This repeats the current import-to-export path without relabeling it as another full held-out trial.

The final Mac source suite passes 316 tests with seven Windows-only skips. [Unit output](SIH_CLINIC_HARDENING_MAC_UNIT_2026-11-19.txt) and [packaged clinic checks](SIH_CLINIC_HARDENING_MAC_PACKAGED_2026-11-19.json) are retained. The packaged helper passes seven generated clinic groups, 14 literal fields, and 1,024 CSV/XLSX cells. Generated fixtures do not replace the actual supplied-packet evaluation.

## Download checks

Use the [private clinic release](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19), rather than the earlier pre-clinic release. It contains the complete Mac arm64 and Windows x64 packages, a source packet containing the original synthetic dataset, and SHA-256 checksums. Keep complete application folders and resources together.

The final [Mac archive audit](SIH_CLINIC_HARDENING_MAC_ARCHIVE_2026-11-19.json) verifies 286 regular files, 46 symlinks, all file modes and hashes after extraction, 27 outer arm64 Mach-O files, 24 embedded helper Mach-O files, and 32 external notice files. The original app remains unmodified, and its ad-hoc signature verifies before and after ZIP extraction. Fifteen project code objects in each executable match the hardened Git source, including the narrative fix. GUI/helper catalogs match all 512 fields. Mac ZIP SHA-256 is `609a0fa6681bae0eba6071f028c2fc8df30392e4e13945445ce5abea1d412dd8`.

The [final Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44506631638) passes all 12 gates and 316 tests with one POSIX-only skip. The [runtime archive audit](SIH_CLINIC_HARDENING_WINDOWS_ARCHIVE_2026-11-19.json) checks 76 outer native files, 125 embedded inventory payloads, 32 notices, 24 approved resources, matching 512-field catalogs, and 15 source-matching code objects in each executable. Its original CI ZIP has SHA-256 `37913faac47496bf2ec5400a66f31205f964db4baa58838a2d5ad3aa55088f1e`.

The release uses a [documentation-only Windows repack](SIH_CLINIC_WINDOWS_DELIVERY_2026-11-19.json). The CI archive's outer Windows guide was outdated. The delivery replaces only `WINDOWS_README.md` and adds the clinic walkthrough and a provenance record. Both guide sources are pinned to `5530aa9`; relative links become repository URLs. All 1,109 other original entries retain their bytes, ZIP metadata, and compressed local records exactly, including the original build manifest, every executable, resource, and notice. The original CI archive remains unchanged. The final Windows download SHA-256 is `0bb1f8a570b3315006d9b3eb044beb7d4059926aec6c0bdc39c301452424f245`.

Mac Intel support, notarization, Windows signing, a person-driven supplied-packet workflow on a Windows laptop, real handwriting, and live REDCap import remain outside the verified scope. Packages include Python and application dependencies. Tesseract remains an optional separate local installation.
