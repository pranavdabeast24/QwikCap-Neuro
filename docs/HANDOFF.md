# Continue QwikCap on another computer

Clone the private [pranavdabeast24/capitolinus-form-extraction repository](https://github.com/pranavdabeast24/capitolinus-form-extraction). Start with [source setup](GETTING_STARTED.md), then use the [SIH clinic walkthrough](SIH_CLINIC_WORKFLOW.md) for the current packet. New commits use Pranav Mukund's GitHub identity. Historical author aliases remain in `.mailmap` without a history rewrite.

QwikCap is a native Python and Tk desktop app for macOS and Windows. It reads local documents, proposes answers with source evidence, and exports approved records through a confirmed spreadsheet mapping. It has no LLM extraction, cloud fallback, camera capture, learning from corrections, or live REDCap connection.

The working name and quiet Capitolinus Ventures ownership notice do not establish commercial name clearance. See [OWNERSHIP.md](../OWNERSHIP.md) and [the naming record](COMPETITORS_AND_NAME.md).

## Current SIH clinic work, 2026-11-19

Choose **Advanced > Form type > Read SIH clinic forms**, the explicit `sih-clinic-v1` profile. Custom masks remain the default for a new project. The [current packet](../datasets/sih-clinic-synthetic/README.md) was supplied as `Neuro Synthetic Forms/sih_clinic_dataset/`. Its owner confirmed that the forms and answer keys are synthetic and authorized the private repository copy. The [clinic delivery](https://github.com/pranavdabeast24/capitolinus-form-extraction/releases/tag/qwikcap-sih-clinic-2026-11-19) replaces the earlier pre-clinic download for this workflow.

The [frozen evaluation](testing/SIH_CLINIC_2026-11-19.md) used source `e2fbd2e`. Native Mac train acceptance preceded the 72-file freeze at `2026-11-19T10:10:31.871790Z`. The freeze was committed as `e5bf722` before any test or index access. All 72 hashes remained unchanged through the native test export at `2026-11-19T10:28:00.534537Z`, as recorded in the [completion snapshot](testing/SIH_CLINIC_FROZEN_EVALUATION_COMPLETE_2026-11-19.json).

Both native Mac workflows imported every original form, confirmed the applicable fields, approved five patients, confirmed the 512-column mapping, and exported Excel with zero manual value edits. The [train](testing/SIH_CLINIC_TRAIN_NATIVE_2026-11-19.json) and [test](testing/SIH_CLINIC_TEST_NATIVE_2026-11-19.json) audits each verify 2,560 typed export cells against the saved project. That is export fidelity, not complete-key accuracy.

| Frozen evaluation measure | Train | Test |
| --- | --- | --- |
| Forms and applicable field confirmations | 28 and 926 | 27 and 893 |
| Strict original exact-key destination agreement | 558/572, 97.55% | 495/508, 97.44% |
| Strict agreement after documented key shorthand expansion | 558/572, 97.55% | 500/524, 95.42% |
| Strict patient grid, including expected blanks and zeroes | 2,379/2,560 | 2,439/2,560 |
| Export cells matching actual reviewed project values | 2,560/2,560 | 2,560/2,560 |

The test shorthand expands one wildcard into 16 catalog checkbox columns. The [master report](testing/SIH_CLINIC_2026-11-19.md) preserves both denominators and explains every difference. Eleven reader codes per split cannot be derived from the named signing physicians. Three train and two test narratives retain source terminal periods omitted by keys. Conservative blanks and a three-field measurement-to-negative gap also remain. The strict complete-key comparisons fail. Do not fill those gaps from answer keys or describe reviewed export fidelity as extraction accuracy.

## Post-evaluation hardening

After the frozen evaluation, independent invented cases exposed false positives for uncertain findings and negated procedure terms. Commit `4c41fb3` adds regressions, and `da33054` fixes those cases in `clinic_narratives.py`. The hardened source passes 316 Mac tests with seven Windows-only skips. See [the hardening record](testing/SIH_CLINIC_HARDENING_2026-11-19.md) for the supplied-packet replay, current package checks, and archive hashes.

The [new Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44506631638) targets the hardened source. The earlier [311-test Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44501222833) passed all 12 gates for the frozen reader. Keep those source revisions separate. The latest runtime differs from the frozen evaluation, and the supplied test set is now used. A regression replay is not a fresh held-out score. Any further accuracy claim after test-informed development needs new held-out material.

The [clinic development record](history/SIH_CLINIC_2026-11-19.md) preserves the implementation sequence. [TESTING.md](TESTING.md) separates source checks, generated package fixtures, frozen supplied-document evaluation, and later hardening.

## Keep the three packets separate

The filenames overlap across packets. A HIT-6 title alone does not select a reader.

| Packet | Explicit reader | Output |
| --- | --- | --- |
| `sih_clinic_dataset/`, copied to `datasets/sih-clinic-synthetic/` | **Read SIH clinic forms**, `sih-clinic-v1` | Several source PDFs become one patient row with 512 exact destination columns. |
| Earlier `sih_dataset/`, copied to `datasets/sih-synthetic/` | **Read PACE printed forms**, `pace-printed-v1` | The earlier printed PACE layouts become one patient row with 512 columns. |
| Older `dataset/`, with printed `Form NEU-101`, `NEU-210`, `NEU-215`, `NEU-330`, or `NEU-410` | **Read NEU clinic forms**, `neurology-training-v1` | Import separate documents into 45 staging columns. |

For another layout, create custom fields and answer masks, then save an extraction type. Reader selection stays explicit. **File > New project** clears the previous reader choice.

## Preserve the clinic identity and interpretation rules

Each patient bundle needs exactly one registration source with a printed **Research Study ID**. The operator-entered ID must match registration. Every original PDF must share registration's MRN, full name, and birth date. MRN is a separate literal identifier and keeps leading zeroes. A non-registration page need not print the study ID, but a printed conflicting ID blocks the bundle.

The reader derives applicability and identity from original sources. Project reopening reconstructs that context and clears field confirmations, approvals, and mapping confirmation. Saved values cannot relax source identity, complete-page, repeated-instrument, or required-answer checks. Keep these checks at review, preview, approval, and export boundaries.

The clinic packet contains native PDF text, including handwriting-style fonts. The reader uses text placement, font information, circled options, checkbox marks, tables, and narrative wording. These results do not measure real handwriting, scanned-paper OCR, or camera capture.

Leave an unmentioned narrative finding blank. An absent assertion is not an observed negative. A report marked FINAL does not establish a REDCap completion code. A radiologist's signature does not establish a catalog-specific reader code. Do not add defaults, filename lookups, patient-specific mappings, or answer-key recovery.

The destination is a wide patient staging table. Repeating instruments and longitudinal events need a separate validated conversion. Live-study import requires an authorized REDCap test project and its own verification.

## Source map

| File or directory | Responsibility |
| --- | --- |
| `desktop.py` | Tk widgets, menus, dialogs, keyboard commands, review controls, and the serial command queue. |
| `desktop_model.py` | `DesktopSession`, projects, extraction types, patient bundles, review, and export operations. |
| `pipeline.py` | Bounded rendering, native text and geometry, local OCR, masks, candidates, and evidence. |
| `clinic_profile.py` | SIH clinic layouts, registration anchors, native controls, tables, and source context. |
| `clinic_narratives.py` | Source-supported clinic radiology findings and measurements. |
| `pace_profile.py`, `neurology_profile.py` | The earlier PACE printed and NEU readers. |
| `extraction_profiles.py` | Canonical profile dispatch, the patient-profile family, applicability, identity, and instrument checks. |
| `form_types.py` | Strict extraction-type parsing, page geometry, and normalized masks. |
| `server.py` | Shared workspace, validation, worker boundaries, spreadsheet state, and legacy browser endpoints. |
| `worker.py`, `template_worker.py`, `bundle_worker.py` | Separate document, spreadsheet, and PDF-bundle jobs. |
| `desktop_worker.py`, `runtime_paths.py` | Packaged worker dispatch and resource lookup. |
| `field_catalog.py`, `study_profiles/pace.json`, `spreadsheets/pace-import-template.csv` | Reference metadata and the exact 512 destination headers. |
| `native_ocr.swift` | Apple Vision adapter compiled into Mac packages. |
| `branding.py`, `build_desktop.py` | Product identity and packaging on the target OS. |
| `tools/verify_sih_clinic.py` | Generated clinic fixtures, packaged companion checks, and independent CSV and XLSX readback. |
| `tools/extract_pace_dataset.py` | Read-only raw diagnostics with an explicit patient-reader profile. |
| `tools/verify_actual_pace_readout.py` | Independent comparison against audited expectations and source census. |
| `tools/verify_windows_release.py` | Native Windows build, relocation, OCR, source checks, and packaged acceptance. |

The Mac bundle identifier is `com.capitolinusventures.qwikcap`. Target the intended app path when several builds coexist. Saved formats retain `formbridge-*` identifiers. `FormbridgeWorker` and `FORMBRIDGE_TESSERACT` remain compatible.

## Build and verify a change

Use Python 3.12 with working Tk and the pinned requirements. Follow [GETTING_STARTED.md](GETTING_STARTED.md) for Mac and Windows commands. Build on the target OS into a new distribution directory. Keep the complete `.app` or Windows directory, including its companion worker and resources. The builder preserves earlier outputs and does not install dependencies.

Run the source suite and relevant acceptance tools after changing shared extraction code. Check the actual packaged companion when changing resource lists or dispatch. `tools/verify_sih_clinic.py --bundle` generates invented fixtures. It does not read a supplied packet or establish GUI acceptance.

Open the real app after UI changes. The clinic reader initially appeared in the menu while a PACE-only guard blocked **Combine patient PDFs** before its file picker. A callback regression and the shared `is_patient_profile` predicate fix that path. Model and packaged extraction checks alone did not catch the menu-to-picker defect.

For a supplied packet run, record raw diagnostics before corrections. Record every manual edit from the source, confirm applicable fields, approve patients, confirm the mapping, and export through the app. Independently inspect headers, cell values, blanks, types, and original PDF hashes. Keep extraction coverage, review corrections, and export fidelity as separate measurements.

## Historical PACE acceptance

These measurements concern `datasets/sih-synthetic/`, not the new clinic packet.

The [2026-11-18 train report](testing/actual-pace-dataset-2026-11-18.md) records 600 of 600 mapped key values, 483 additional checkbox zeroes, and a native Mac export matching all 2,560 destination cells. No manual value corrections were needed. Nine key-only total entries have no destination column.

The reader was frozen at `26fb90eaea6c4a2255c681ad9947e9ab0739c3a5` before held-out access. The [freeze record](testing/actual-pace-freeze-2026-11-18.json) covers 37 files. The [held-out report](testing/heldout-pace-2026-11-18.md) records 550 of 551 mapped key values and 390 additional checkbox zeroes. Raw extraction omitted `Joint` from `Joint hypermobility` in `personal_ctdisorder_v2`. One source-confirmed edit through the native Mac app produced a reviewed workbook matching all 2,560 cells. Eight key-only total entries remain outside the destination.

The [train workbook](../examples/quickcap-actual-train-readout.xlsx) and [reviewed test workbook](../examples/qwikcap-supplied-test-reviewed-readout.xlsx) preserve those app exports. The test set has been used. Later tuning requires a fresh holdout for a new independent score.

The [QwikCap rename regression](testing/QWIKCAP_REBRAND_2026-11-19.md) replays all 55 earlier PACE forms. Its [Windows package record](testing/QWIKCAP_WINDOWS_2026-11-19.md) covers source `d150f75`, 283 tests with one POSIX-only skip, and 11 acceptance stages. Those checks do not measure the clinic reader.

The separate [generated practice run](testing/SYNTHETIC_PACE_GUI_2026-11-18.md) used 18 PDFs and two fictional patients. Raw scan extraction matched 506 of 512 cells. Six manual scan corrections produced a reviewed 1,024-cell export. Keep generated practice evidence separate from either supplied packet.

## Data and distribution boundaries

The repository carries source, pinned dependencies, fictional regression fixtures, and the explicitly authorized supplied synthetic packets. Keep answer keys and indexes out of app upload. Keep credentials, environments, caches, compiled outputs, raw screenshots, and source-bearing projects outside Git. A project embeds original documents. An extraction type contains reusable rules and geometry.

Local processing does not provide encryption at rest, managed access controls, tamper-evident audit trails, or a compliance determination. Read [SECURITY.md](../SECURITY.md) and [LLM_PRIVACY.md](LLM_PRIVACY.md) before any real-study or model integration. Do not send patient-like data to an external model without the applicable data authorization and deployment controls.

Mac development builds use ad hoc signing and are not notarized. Windows builds are unsigned. Generated Windows acceptance does not establish a person-driven workflow on a Windows laptop with the supplied packet. [COLLABORATION.md](COLLABORATION.md) and [PILOT_PLAN.md](PILOT_PLAN.md) remain proposals and grant no repository access or product approval.

The earlier [conversation digest](history/CONVERSATION.md) and [Windows history](history/WINDOWS_2026-11-18.md) retain sanitized project context. Current source and dated evidence take precedence over historical plans and names.
