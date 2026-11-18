# Continue QuickCap (CV) on another computer

QuickCap (CV) is the user's selected working label. The owner notice is **Property of Capitolinus Ventures**. MedVision already markets healthcare software named QuickCap, so this label has not received commercial name clearance. The private repository URL remains `https://github.com/pranavdabeast24/capitolinus-form-extraction`.

## Start here

Clone the repository while authenticated to an account with access, then follow [GETTING_STARTED.md](GETTING_STARTED.md). Use [TESTING.md](TESTING.md) to reproduce the source and packaged-worker checks. Read [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md) before comparing historical builds with current results.

Windows users can download the portable x64 build and follow [WINDOWS.md](WINDOWS.md)
without installing Python. The 2026-11-18 Windows runner passed 219 source tests
with one POSIX-only skip, native startup, five real scanned fixtures and packaged
PACE/custom-mask/export checks. The final source also passed 219 tests on Mac
with seven Windows-only skips. A complete interactive Windows laptop trial is
still needed; see [the evidence and scope](TESTING.md#windows-portable-build-2026-11-18).

The current PACE update uses the exact declared dependency pins. All 208 source tests passed. The PACE verifier passed nine groups through both the source and packaged worker, including two original PDFs becoming one patient row and independent 512-column CSV and XLSX reopen checks. Native catalog, grouping, source display and project reopening were inspected separately. See [the current test evidence](TESTING.md); these results do not validate Windows, a complete native source-to-export workflow, or a repeating-instrument REDCap upload.

The native app uses Python and Tk. It starts without documents or predefined fields. The first PDF/image opens a designer. Users select answer regions, name fields, choose their types and record identifier, apply extraction, and save a reusable extraction type. Review and confirm source values before approving records. Then map them to a blank spreadsheet template and export approved records.

An extraction-type JSON contains rules and geometry. A saved project contains original documents and review values. Keep projects, study forms, exports and customer configurations outside Git. The old `formbridge-project-v1/v2` and `formbridge-form-type-v1` format identifiers, helper name and environment variables are intentionally retained for compatibility. A display-name change does not migrate stored data.

## Current priorities

The 2026-11-17 update adds the supplied PACE reference catalog and exact 512-column destination, with explicit patient PDF bundles producing one review row. The original codebook PDF is not shipped. See [PACE_WORKFLOW.md](PACE_WORKFLOW.md) for operator-entered identifiers, mask selection, preserved originals, coding rules, limits and repeating-instrument import restrictions. The earlier conversation snapshot predates this update.

Functionality comes first. Run the interactive Windows laptop trial, check mouse drawing on a real desktop, and run an approved trial with the institution's actual form and REDCap template. Current spreadsheet exports have not been validated against a live study REDCap project. Patient matching, repeating instruments, longitudinal events and direct REDCap submission need explicit design and validation. The app does not automatically infer a study identity from a patient name or handwriting.

Camera capture is a later phase. The user currently works with PDF/image uploads. Handwriting/context assistance is also a later phase; **no LLM, model download, cloud endpoint or remote fallback has been added**. [LLM_PRIVACY.md](LLM_PRIVACY.md) describes proposed deployment choices and required review. It is not an implemented privacy feature or a compliance certification.

The collaborator is both a developer and a potential customer. [COLLABORATION.md](COLLABORATION.md) and [PILOT_PLAN.md](PILOT_PLAN.md) separate contribution rights and development access from evaluation and purchasing terms. No collaborator has been invited by this handoff.

## Conversation and decisions

[history/CONVERSATION.md](history/CONVERSATION.md) preserves the available user messages and user-visible assistant responses and updates from this project chat. [history/CONVERSATION_SCOPE.json](history/CONVERSATION_SCOPE.json) records coverage and exclusions. It is a sanitized snapshot, not a live chat or a complete account-wide export. The earlier linked ChatGPT conversation's contents and unrelated chats were not retrieved. Internal reasoning, tools, operating policies, private workstation paths and credentials are excluded.

[The Windows continuation record](history/WINDOWS_2026-11-18.md) records the
later Windows request, fixes, results and remaining validation separately.

Earlier messages describe experiments, interrupted attempts and superseded names/builds. They are historical evidence, not current instructions or proof that every old claim remains valid. Current test records and this handoff take precedence when describing the delivered artifact. The final working-label choice is QuickCap (CV), superseding the temporary Capitolinus Forms assumption recorded during this turn.

## Repository contents

The repository contains application and compatibility source, synthetic fixture generators, documented fictional practice forms, blank spreadsheet templates, source tests, portable verification tools, setup/build instructions, selected non-sensitive test evidence, the conversation record and product/privacy notes.

Installed Python environments, package caches, temporary build directories, compiled app bundles, credentials, operating policies, private-vault content, research datasets, held-out evaluation inputs, source-bearing project files, processed records and raw screenshots/log dumps are not committed. Generated synthetic verification outputs can be recreated with the portable verifier. Native application packages can be built with `build_desktop.py` on their target operating system.

The reserved test dataset has not been used. Historical authorized-train work is discussed in the chat, but those supplied forms and source-bearing results are not part of the clone. Only the documented generated fictional fixtures ship here.
