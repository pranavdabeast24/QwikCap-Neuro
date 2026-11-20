# PACE automatic review: implementation plan

Status: design agreed; implementation and verification in progress.

## What the user should do

1. Add one PDF, or several PDFs for a small batch of patients.
2. Check the suggested patient groups and the sticker on each source. MRN groups forms; name and birth date must agree.
3. Review only the PACE fields found on those forms. Confirm, correct the typed answer, or redraw the answer box.
4. Save corrected boxes as a layout. Reuse them on a matching form without storing a patient's answers in the layout.
5. Approve each patient and export one row per patient using the supplied 512-column template.

For new REDCap records, QwikCap supplies a temporary row ID distinct from MRN. REDCap can replace it when automatic numbering is selected. Updates need the real REDCap record ID. Automatic numbering does not look up existing patients by MRN.

## Chosen design

Keep one workspace record per patient and keep the existing bounded source-bundle and export validation. Add one automatic PACE reader as the desktop default. It selects the existing source readers internally; it does not expose staging schemas as alternative user presets.

Keep three concepts separate:

| Concept | Owner and checks |
| --- | --- |
| Source identity | Reader: MRN as text, name, DOB, source page and evidence. Never substitute an export ID for a sticker. |
| Patient group | Session: exact MRN and consistent name/DOB; conflicting identities and repeated assessments block. Human checks remain required. |
| Export identity | Session: stable temporary ID for a new record, or an explicitly entered existing REDCap ID. Printed study IDs remain source evidence. |
| Layout correction | Validated rules-only loadout, separate from canonical field definitions. PACE variable names, codes and types remain authoritative. |

The public desktop workflow should hide reader choice, PDF assembly and schema details. The session owns mutations; the UI displays snapshots and issues commands. Saved layout matching must include document anchors, rather than page dimensions alone. Patient stickers are detected dynamically and never reused as static patient values.

## Alternatives considered

- A generic label matcher over all 512 fields would be small, but many labels repeat across instruments and timepoints. It cannot safely choose an assessment from a label alone. Use literal source recognition and abstain on ambiguous mappings.
- A new patient/document database would make very large batches easier, but it would also replace project storage and approval/export behavior at once. Keep bounded patient bundles for this change and process 500 patients in batches.
- Global custom masks would reuse existing controls, but changing them changes the whole schema and removes the PACE source checks. Keep PACE corrections separate.

## Work and verification

- [x] Ground readers, identity gates, desktop state and current reuse limitations with independent read-only reviews.
- [x] Blocking first steps: preserve the original baseline, settle ID handling, and define the data boundary before code.
- [x] Independent workstreams: one code owner; independent verification and human-language documentation by the lead.
- [x] Shared mutable state: the code owner coordinates coupled modules; no parallel edits to those modules.
- [x] Smallest safe decomposition: reader/identity, session/loadout, UI, then integration checks. Preserve old profile contracts internally.
- [ ] Test movable stickers, leading-zero MRNs, conflicts, missing identity, unknown layouts, restricted choices and layout reuse without answer carryover.
- [ ] Exercise imports, confirmation/correction/redraw, save/reload and CSV/XLSX output on synthetic forms through the desktop.
- [ ] Re-run the supplied train packet and already-used test packet as regression checks. Report current results separately from historical accuracy scores.
- [ ] Build and check Mac and Windows packages, update plain-language guides and publish a reviewable GitHub change.

## Limits to keep visible

Existing memory/file limits stay in force. This change does not validate a 500-patient simultaneous import, genuine handwriting, cloud inference, live REDCap uploads or real-health-record storage security. Projects and exports remain unencrypted. Unknown answers stay blank for review.

## Decision trail

- The existing PACE and clinic readers already target the supplied columns. The visible reader choices and empty initial project made that capability hard to reach.
- Existing clinic identity gates require a registration sheet with a printed study ID. The new sticker workflow needs its own source identity contract; the older gates must stay intact.
- Existing masks are fixed whole-document rules. Corrections must be scoped to a recognized layout and remain separate from the canonical codebook.
- REDCap supports renumbering new imported records, but still requires a populated identifier column. See [BIDMC's import guide](https://research.bidmc.org/redcap-core/faq/importing-data).
- Baseline `9aa7bec` passed all 316 source tests on Mac (seven Windows-only skips). The run used a frozen source copy; sandbox-only failures for loopback and process inspection were resolved by running the same suite with those local permissions.
