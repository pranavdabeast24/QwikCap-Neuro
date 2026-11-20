# Permissions before a customer pilot

QwikCap can stay private and proprietary.
You do not have to add an open-source license.
Software permissions, third-party notices, and questionnaire permissions are separate matters.

## Set terms for your software

Confirm who owns the code and who can license it.
Agree on contributor rights before a collaborator develops the product.
For a customer pilot, put the allowed use, access, support, and ownership terms in writing.
Do not assume that GitHub access or a trial purchase settles those rights.

The current repository grants no open-source license.
GitHub explains that a project does not have to choose one.
See [GitHub's licensing guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) and [the source permissions](../OWNERSHIP.md).

## Keep the software notices

The app uses Python, Tcl/Tk, PDFium, and other libraries.
Their terms still apply when you distribute a customer build.
Keep the notices supplied with each package.

PyInstaller allows commercial, proprietary applications under its packaging exception.
That exception does not replace the licenses of bundled dependencies.
See [PyInstaller's terms](https://www.pyinstaller.org/en/stable/license.html) and [pypdfium2's licensing notes](https://github.com/pypdfium2-team/pypdfium2/blob/5.14.0/README.md#licensing).

The Windows Python package also includes Microsoft runtime conditions.
Check those conditions when preparing customer terms.
The [package inventory](testing/SIH_CLINIC_HARDENING_WINDOWS_MANIFEST_2026-11-19.json) records the examined components and notices.
An inventory is not a legal clearance.

Tesseract is optional and is not bundled.
If you later bundle it, check that engine, its language data, and its dependencies.

## Check questionnaire rights

The sample packet includes HIT-6 content.
IQVIA lists HIT-6 in its [instrument catalog](https://coas.iqvia.com/OurCoas/en) and describes signed licenses for its instruments and scoring algorithms.
See [IQVIA's licensing information](https://www.iqvia.com/solutions/research-and-development/consulting/patient-centered-solutions/clinical-outcome-assessments-coa).

Ask the study team or rights holder whether permission covers:

- The included form copies and synthetic demonstrations.
- Display, reproduction, scoring, and redistribution.
- A commercial vendor processing the study's completed PDFs.

Those sources do not settle whether reading an existing PDF needs a separate QwikCap license from the instrument owner.
Get confirmation for the exact workflow.
Fictional answers do not establish permission to reproduce questionnaire text.
Check other third-party instruments in the same way.

## Keep REDCap separate

QwikCap exports a spreadsheet. It does not include REDCap software.
Use an authorized REDCap installation for a real import or integration.
Do not imply endorsement or guaranteed compatibility.
See the [official REDCap FAQ](https://www.project-redcap.org/about/faq/).

Before a paid pilot, resolve code ownership, customer terms, and instrument permissions with the study team and legal adviser.
This page records questions to resolve. It is not a license agreement or a legal clearance.
