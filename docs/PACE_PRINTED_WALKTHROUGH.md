# Try the earlier printed PACE packet

Open QwikCap. PACE is already selected.
Use **Add documents…** and select PDFs from `datasets/sih-synthetic/train/forms/`.
The app suggests patient groups; check their MRN, name and birth date against every source.

Follow [the clinic walkthrough](SIH_CLINIC_WORKFLOW.md) for the check, correction and export controls.
For its one-patient example, use the same five filenames from this packet's `train/forms/` folder.
Do not mix this packet with the separate `sih-clinic-synthetic` packet in one project.

For the complete packet, import the 28 train forms in a train project and the 27 test forms in a separate test project.
Each split contains five patients. Do not import answer keys or `manifest.pdf`.
New exports use temporary row IDs so REDCap can number new records during import.

The older printed-reader trial and its results remain in the [train report](testing/actual-pace-dataset-2026-11-18.md) and [test report](testing/heldout-pace-2026-11-18.md).
Those historical scores do not measure the new automatic grouping workflow.
The test set has already been used; another replay is a regression check.
