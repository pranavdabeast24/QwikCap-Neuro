# Continue work on QwikCap

Start with [developer setup](GETTING_STARTED.md).
Use a branch and a pull request for changes.
Commit as Pranav Mukund when working on the owner's behalf.

## Understand the app

QwikCap is a Python desktop app with a Tk interface.
It reads PDFs locally and suggests answers.
A person checks the answers, approves each row, and confirms the spreadsheet mapping.
The app then exports Excel or CSV.
It has no LLM, cloud extraction service, camera capture, or live REDCap connection.

| File | What it does |
| --- | --- |
| `desktop.py` | Shows the windows, menus, review controls, and export preview. |
| `desktop_model.py` | Manages documents, saved projects, review, and export. |
| `pipeline.py` | Reads PDF text, page regions, marks, and local OCR results. |
| `clinic_profile.py` and `clinic_narratives.py` | Read the supplied clinic forms and reports. |
| `extraction_profiles.py` | Selects readers and enforces patient and field checks. |
| `templates.py` and `server.py` | Validate spreadsheet input and shared application state. |
| `form_types.py` | Stores and validates custom field selections. |
| `build_desktop.py` | Builds the app on the target operating system. |

The clinic reader is `sih-clinic-v1`.
The older PACE and NEU readers remain separate.
New projects start without preset fields.
See [the custom form guide](CUSTOM_FORMS.md) for the reader choices.

## Keep these checks

- Include one registration sheet in each clinic patient group.
- Match its study ID, full MRN, name, and birth date to the other sources.
- Keep leading zeroes in identifiers.
- Block conflicting patients, incomplete forms, and duplicate assessments.
- Require field checks, patient approval, and mapping confirmation before export.
- Rebuild source checks and clear approvals when a project reopens.
- Leave unknown values blank. Do not fill them from answer keys.

The clinic output has 512 columns and one row per patient.
It is not a validated import for repeated REDCap assessments.
Keep existing saved-file formats, worker names, environment variables, and platform identifiers compatible.

## Check a change

Run the source tests and the checks relevant to your change.
Test the built worker after changing package resources.
Open the real app after changing its interface.
Use fictional data only.

The [test summary](TESTING.md) links the exact results and commands.
The supplied test set has already been used.
Use new held-out documents for a new independent accuracy claim.
Keep historical scores separate from later changes and regression checks.

Keep projects, local exports, credentials, and real patient records out of Git.
The original synthetic packets and named example workbooks are approved exceptions.
Read [licensing](LICENSING.md) before sharing a customer build.
