# Recorded build environment and distribution work

`BUILD_ENVIRONMENT.json` records public package/version/license metadata from the local development environment at repository preparation. It is a snapshot, not a reproducible-install result or a complete third-party notice file. The exact requirements installation has not been validated. Requirements were preserved without changing pins or installing packages.

| Package | Requirement pin | Recorded installed version |
| --- | --- | --- |
| Pillow | 12.3.0 | 13.0.0 |
| pypdfium2 | 5.14.0 | 5.13.0 |
| pypdf | 6.10.0 | 6.21.4 |

The remaining recorded package versions match their requirement pins. Tests run in this environment do not establish that an environment installed from the exact pins behaves identically. The preserved browser README's historical statement about versions used should be read with this explicit snapshot. A release needs an authorized clean-environment dependency installation and target-OS validation.

Metadata indicates generally permissive library licenses, but it is not a clearance conclusion. Before customer distribution, create and review a release-specific inventory and required notices for Python, Tcl/Tk, PDFium and its dependencies, Pillow native codecs, other bundled libraries, the macOS OCR integration, and PyInstaller's applicable distribution exception. Check actual package contents and license texts for the exact shipped build. Tesseract is optional and not bundled; evaluate its terms if a future distribution includes it.

Legacy instrument names and scoring rights remain unresolved. This repository includes no questionnaire assets or authorized-train sources. Do not add or distribute those materials without the necessary rights review. The proprietary source notice does not replace third-party licenses or establish ownership of institution or contributor materials.
