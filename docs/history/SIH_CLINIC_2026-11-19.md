# SIH clinic development record, 2026-11-19

This is a sanitized continuation record for the current `sih_clinic_dataset/` work. It contains no source-bearing project or private account data. Use [HANDOFF.md](../HANDOFF.md) for the current continuation instructions and [TESTING.md](../TESTING.md) for accepted evidence.

## Requested behavior

The owner supplied a new clinic packet with 28 train forms, 27 test forms, sibling PDF answer keys, and an index. The owner confirmed that the complete packet is synthetic and authorized inclusion in the private `pranavdabeast24/capitolinus-form-extraction` repository. Train fixes must precede a recorded runtime freeze and held-out evaluation.

The app must combine several forms for one patient, review extracted answers beside the original source, and export one spreadsheet row with the supplied 512 headers. The desktop remains native Python and Tk for Mac and Windows. Custom masks remain the startup workflow for other layouts.

## Reader separation

The earlier failure screenshot showed a `Form NEU-210` HIT-6 page under the PACE reader. The older NEU reader was restored as an explicit menu choice. That document-staging profile has 45 columns and remains separate from both 512-column patient readers.

The new clinic packet uses registration, clinic questionnaires, procedures, and narrative radiology layouts. The new `sih-clinic-v1` profile is selected through **Read SIH clinic forms**. The older `pace-printed-v1` profile still handles `datasets/sih-synthetic/`. Similar filenames and shared questionnaire titles do not make these layouts interchangeable.

## Implementation decisions

Registration's printed Research Study ID anchors each bundle. Other pages link through MRN, full name, and birth date. The operator ID must agree with registration. MRNs retain leading zeroes. Conflicting identities, repeated instruments, incomplete source page sequences, and unsupported layouts block review and export.

Clinic extraction uses native text, font information, bounded circled-option geometry, visible checkbox marks, tables, and narrative assertions. The source-only train census found native text on all 43 pages and no raster or AcroForm input. Handwriting-style fonts do not establish real handwriting recognition.

Unprinted completion selectors, unsupported reader codes, and unmentioned findings remain blank. Source narrative punctuation is preserved. No patient-specific filename lookup or answer-key recovery was added. Source context is rebuilt from originals on reopening, and review gates reset.

Hardening covers full spaced MRNs, full study IDs and date tokens, ambiguous names and controls, complete-page boundaries, and Unicode letters in patient names. The original custom-mask, PACE, and NEU paths remain separate.

## Native import regression

Native testing found that the clinic menu appeared, but **Combine patient PDFs** displayed a new-project warning before the native file picker. The UI eligibility guard still recognized only the PACE profile. Model extraction and generated packaged checks did not exercise that guard.

Commit `7efabee` adds callback regressions using real reader snapshots. Commit `e2fbd2e` changes the guard to the shared `is_patient_profile` predicate. SIH and PACE reach the picker. Incompatible custom schemas, NEU, and ordinary-document projects retain their existing guard. The focused UI suite passes 15 tests. The full Mac suite passes 311 tests with seven Windows-only skips.

## Completed frozen evaluation

The real Mac train workflow imported all 28 original forms, confirmed 926 applicable fields, approved five patients, confirmed the 512-column mapping, and exported Excel with zero manual value edits. The 72-file runtime freeze at source `e2fbd2e` was recorded at `2026-11-19T10:10:31.871790Z` and committed as `e5bf722` before test or index access.

The frozen native test workflow imported all 27 forms, confirmed 893 fields, approved five patients, and exported another five-row workbook with zero value edits. All 72 frozen hashes remained unchanged through the native export at `2026-11-19T10:28:00.534537Z`. Each workbook independently matches all 2,560 typed cells to the actual saved project and every embedded PDF to the original. Those are export-fidelity checks.

Strict train agreement is 558/572 mapped key values, 97.55%, and 2,379/2,560 full-grid cells. Strict test agreement is 495/508 original exact-key values, 97.44%. Expanding one wildcard to 16 exact checkbox destinations yields 500/524 mapped values, 95.42%, and 2,439/2,560 full-grid cells. Both complete-key comparisons fail. The [master evaluation](../testing/SIH_CLINIC_2026-11-19.md) and its train and test reconciliations retain the differences and denominators.

Eleven key reader codes per split cannot be derived from signing physician names. Three train and two test narratives retain final periods omitted by the keys. Unasserted findings and procedure options remain blank. Three zeroes per split could be derived from captured measurements but are not computed. These coverage gaps remain separate from workbook transport fidelity.

The frozen-reader [Windows verification run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44501222833) passed 311 tests with one POSIX-only skip and all 12 gates. Its archive and the generated fixtures are separate from the actual supplied-packet Mac GUI runs.

## Post-evaluation hardening and delivery

After the frozen evaluation ended, an independent audit using invented cases found false positives for uncertain findings and negated procedure terms. Commit `4c41fb3` adds the regressions. Commit `da33054` fixes the cases in `clinic_narratives.py`. The current Mac suite passes 316 tests with seven Windows-only skips.

The [hardening record](../testing/SIH_CLINIC_HARDENING_2026-11-19.md) records the regression cases, all-55-form replay, and current package checks. The [new Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44506631638) targets that hardened source. The [clinic delivery](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19) uses the later runtime. Do not describe the current runtime as identical to the original 72-file freeze or treat the regression replay as a fresh held-out score.

The packet is now used evaluation material. Future test-informed tuning needs fresh held-out forms for a new independent accuracy claim. Keep historical PACE scores, generated fixture results, frozen clinic scores, and subsequent hardening checks separate. Mac arm64 and Windows x64 are the delivery targets. Intel Mac support, notarization, and an actual-packet person-driven Windows laptop walkthrough remain unverified.
