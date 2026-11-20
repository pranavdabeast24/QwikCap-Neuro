# Four synthetic patient packets

The project owner supplied these four fictional patient intake packets and authorized their inclusion in the repository for testing. Each PDF contains one patient and four pages. The copies preserve the original filenames and bytes.

| Input PDF | Fictional patients | Pages |
| --- | --- | --- |
| [patient_01.pdf](forms/patient_01.pdf) | 1 | 4 |
| [patient_02.pdf](forms/patient_02.pdf) | 1 | 4 |
| [patient_03.pdf](forms/patient_03.pdf) | 1 | 4 |
| [patient_04.pdf](forms/patient_04.pdf) | 1 | 4 |

For a single-patient trial, select one PDF from `forms/` in QwikCap. For a four-patient trial, select all four PDFs. Keep each patient's four pages together and compare captured fields with the original PDF during review.

[INVENTORY.json](INVENTORY.json) records each original basename, relative path, byte count, SHA-256 hash, and page count. The four PDFs total 1,417,384 bytes and 16 pages. File identity and PDF parsing checks do not measure extraction or export accuracy.

This packet contains only the four input PDFs, this guide, and the inventory. It is separate from the [SIH clinic packet](../sih-clinic-synthetic/README.md) and the [PACE printed packet](../sih-synthetic/README.md).
