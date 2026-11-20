# Recorded environments and distribution work

This page records earlier builds. Read [the test summary](TESTING.md) for current checks and [licensing](LICENSING.md) for distribution questions.

The [2026-11-18 Windows record](testing/WINDOWS_BUILD.json) describes the portable
x64 ZIP built at `f9eb862` on Windows Server 2022 with Python 3.12.10 and Tk
8.6.15. All 219 source tests ran successfully with one POSIX-only skip. Source
and packaged PACE/mask acceptance, real scanned forms and extracted native
startup passed. The ZIP includes 32 retained notice files and an inventory of
76 outer native files and 124 hashed worker archive entries, including 75 native
files. The v1 manifest calls that full embedded inventory `embeddedNativeFiles`;
it also contains data files. This inventory is not a commercial
license-clearance conclusion. A person-driven client-laptop trial remains open.

The same final source passed 219 tests on macOS with seven Windows-only skips.
This delivery adds a Windows binary; the earlier Mac binary was not rebuilt.

The 2026-11-17 PACE update passed 208 source tests and nine patient-bundle acceptance groups through both source and packaged workers. See [the current build and environment record](testing/PACE_BUILD_MACOS.json). The notes below describe the earlier 2026-11-13 handoff.

The earlier handoff was installed in a fresh isolated Python 3.12 environment from the unchanged runtime and build requirement files on 2026-11-13. All declared pins matched, and all 156 source tests passed on this Mac. See [that environment record](testing/ENVIRONMENT_MACOS.json) and [test output](testing/UNIT_TEST_RESULTS_MACOS.txt). This validates the source setup on the recorded Mac configuration. It does not validate Windows, other Python/Tk distributions, a future model, or clinical use.

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

Instrument names and scoring rights still need review. The earlier source snapshot had no supplied questionnaire packet. The owner has since authorized the two synthetic packets for this private repository. That authorization does not settle third-party instrument rights. The proprietary source notice does not replace third-party licenses or establish ownership of institution or contributor materials.
