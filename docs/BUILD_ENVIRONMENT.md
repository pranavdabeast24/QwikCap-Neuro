# Recorded environments and distribution work

The current handoff was installed in a fresh isolated Python 3.12 environment from the unchanged runtime and build requirement files on 2026-11-13. All declared pins matched, and all 156 source tests passed on this Mac. See [the new environment record](testing/ENVIRONMENT_MACOS.json) and [test output](testing/UNIT_TEST_RESULTS_MACOS.txt). This validates the source setup on the recorded Mac configuration. It does not validate Windows, other Python/Tk distributions, a future model, or clinical use.

The final QuickCap (CV) Mac app also built and opened in that environment. Both custom-mask verification paths passed ten groups. The packaged fictional-fixture regression matched 60 extracted fields and 240 reopened export cells. The [build record](testing/BUILD_MACOS.json) links the worker reports, source hashes, and blank startup/About screenshots. Native branding was inspected separately; mouse drawing and the complete native workflow remain unverified for this build.

The following snapshot describes the earlier prototype build at commit `cfd0762`. It is retained as historical evidence, not the current handoff environment.

`BUILD_ENVIRONMENT.json` records public package/version/license metadata from the local development environment at the earlier repository preparation. At that point the exact requirements installation had not been validated. Requirements were preserved during that branding task. This historical snapshot is not a complete third-party notice file.

| Package | Requirement pin | Recorded installed version |
| --- | --- | --- |
| Pillow | 12.3.0 | 13.0.0 |
| pypdfium2 | 5.14.0 | 5.13.0 |
| pypdf | 6.10.0 | 6.21.4 |

The remaining historical package versions matched their requirement pins. Those earlier tests did not validate an exact-pin installation. The current clean-install source result above closes that gap for the recorded Mac configuration. Every target operating system and final binary distribution still needs its own validation.

Metadata indicates generally permissive library licenses, but it is not a clearance conclusion. Before customer distribution, create and review a release-specific inventory and required notices for Python, Tcl/Tk, PDFium and its dependencies, Pillow native codecs, other bundled libraries, the macOS OCR integration, and PyInstaller's applicable distribution exception. Check actual package contents and license texts for the exact shipped build. Tesseract is optional and not bundled; evaluate its terms if a future distribution includes it.

Legacy instrument names and scoring rights remain unresolved. This repository includes no questionnaire assets or authorized-train sources. Do not add or distribute those materials without the necessary rights review. The proprietary source notice does not replace third-party licenses or establish ownership of institution or contributor materials.
