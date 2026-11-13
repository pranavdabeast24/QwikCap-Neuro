# Dependency and content review before a customer pilot

This is a preliminary readiness review dated 2026-11-13. It is not a legal opinion, a complete software bill of materials, or permission to redistribute questionnaire content.

## Direct dependencies

| Dependency | Reviewed license reference | Remaining distribution work |
| --- | --- | --- |
| Pillow | [MIT-CMU](https://raw.githubusercontent.com/python-pillow/Pillow/12.3.0/LICENSE) | Preserve applicable notices and inventory native image codecs in the actual build. |
| pypdfium2 | [Apache-2.0 and BSD-3-Clause, plus PDFium dependencies](https://github.com/pypdfium2-team/pypdfium2/blob/5.14.0/README.md#licensing) | Retain the binding, PDFium and bundled dependency licenses for the exact wheel and platform. |
| ReportLab | [BSD](https://docs.reportlab.com/developerfaqs/#13-licensing) | Preserve required notices when distributing it. It is a fixture-generation dependency and is excluded from executable collection by the current builder. |
| pypdf | [BSD-3-Clause](https://raw.githubusercontent.com/py-pdf/pypdf/6.10.0/LICENSE) | Preserve notices and disclaimers. |
| openpyxl | [MIT](https://openpyxl.readthedocs.io/en/stable/) | Preserve copyright and permission notices. |
| defusedxml | [PSF License v2](https://raw.githubusercontent.com/tiran/defusedxml/main/LICENSE) | Preserve applicable license and copyright terms. |
| PyInstaller | [GPL with a commercial-bundling exception](https://pyinstaller.org/en/stable/license.html) | The exception permits proprietary application bundles, subject to dependency licenses. Distributing modified PyInstaller is a different case. |

These licenses do not establish ownership of the original application. They generally allow commercial use subject to their conditions. Python, Tcl/Tk, native libraries, transitive packages and any runtime hooks need a build-specific inventory and complete notices. The installed PDFium wheel alone includes multiple third-party build-license files.

## Historical environment mismatch and current source validation

The new handoff has now been installed from the unchanged runtime and build requirements in a fresh isolated environment. All declared pins matched and all 156 source tests passed on the recorded Mac. See [the current environment record](testing/ENVIRONMENT_MACOS.json). Windows validation and complete binary-distribution notices remain pending.

The inspected runtime has Pillow 13.0.0, pypdfium2 5.13.0 and pypdf 6.21.4. The requirement file pins 12.3.0, 5.14.0 and 6.10.0 respectively. Other inspected direct pins match. The environment inventory records both versions.

Those differences apply to the earlier branding build. The current source validation resolves the declared-pin installation gap for this Mac configuration. Before a customer release, inventory and review the actual Mac and Windows binary distributions and their notices. Do not extend the Mac source result to untested platforms or configurations.

## Research instrument and sample provenance

The default designer starts without a built-in research instrument. Legacy compatibility code still contains instrument names, short NIHSS item labels and HIT-6, MIDAS and NIHSS scoring/range rules. No complete HIT-6 or MIDAS question sentences were found in the reviewed profile source. This does not establish permission to redistribute those instruments or scoring implementations.

Confirm intended instrument permissions with their rights holders before a commercial release. Generated fictional patient values do not remove third-party rights in the form itself. The clean repository excludes the supplied dataset, source-bearing verification projects, train keys, processed exports and machine-specific train verifier. Its included fixtures are separately listed and hashed.

## Platform and security boundaries

Apple Vision uses the Mac's system frameworks. Windows needs a separately reviewed OCR installation and a Windows build/test run. The existing prototype has no managed access control, encryption-at-rest system or tamper-evident audit service. Complete the institution's security and data-governance review before using real research records. Never place records or source-bearing projects in Git, issues or build logs.
