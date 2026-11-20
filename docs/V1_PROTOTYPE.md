# V1 prototype status

The project owner tried the app and accepted the basic workflow on November 20, 2026.
This milestone saves that working prototype as `v1.0.0-prototype`.
It is a starting point for the next development round, not a claim that the software is ready for real health records.

## What works in v1

- Import supported PDF forms and suggest fields from the supplied PACE codebook.
- Propose patient groups from literal MRN, with name and birth-date checks.
- Review typed answers, choose allowed codes, redraw answer areas and save matching layouts for reuse.
- Approve patients and export one row per patient with 512 columns.
- Save local projects and reopen them for fresh review.
- Run packaged builds on Apple Silicon Mac and 64-bit Windows, or run the Python source on either platform.

MRN groups forms locally. It is separate from the temporary export ID for a new REDCap record.
The app has no live REDCap connection or LLM extraction service.

## What the evidence covers

The application build comes from runtime commit `5870a5245df9c1e9ffbf776d9f01eb656cf59952`.
That build passed 354 source tests on each platform, with platform-specific skips.
Windows passed 14 source, build and package checks.
The new automatic-review check passed nine checks through each platform's packaged worker.

Both bundled 55-document synthetic packets completed the session and export regression.
Their known answer-key differences remain in [the test record](testing/PACE_AUTO_2026-11-20.md).
The test sets have already been used. These are regression results, not a fresh independent accuracy study.

The later four-document trial loaded four synthetic patient PDFs and reached the review queue.
Desktop control timed out during the save step. No saved-project comparison or final Excel export was verified for that trial.
The owner's acceptance confirms the basic idea and usability direction. It does not replace a field-by-field accuracy audit.

## What needs work next

1. Reduce review effort and improve the desktop controls, while keeping source checks and corrections clear.
2. Add an explicit way to correct sticker OCR and map MRN to existing REDCap record IDs.
3. Improve changed-layout and scan coverage. Validate genuine handwriting before claiming support.
4. Support larger studies without keeping every source and preview in one in-memory batch. V1 retains the current 20 MiB source and 60-patient session bounds.
5. Add project and export encryption, stronger audit controls and an approved retention workflow.
6. Sign and notarize Mac builds and sign Windows builds for distribution.
7. Validate real REDCap imports, existing-record updates, and repeating assessments in a study sandbox.

LLM assistance is deferred. Any later model integration needs a separate privacy and deployment decision.

## Continue development

Clone the repository, follow [source setup](GETTING_STARTED.md), then read [the handoff](HANDOFF.md).
Use the bundled synthetic forms for changes and keep their answer keys separate from app inputs.
Keep patient documents, local projects, credentials and real-data exports out of Git.
Saved layouts and unsaved work in an open app are user files; they are not captured by a source tag.
