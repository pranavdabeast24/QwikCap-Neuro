# Product decisions carried forward

This record summarizes the available project conversation. It is not a legal assignment, a claim of production readiness, or an instruction to access data outside a new task's authorization.

| Topic | Decision and reason |
| --- | --- |
| First phase | A desktop app for macOS and Windows source support, with PDF/image upload. A desktop camera is not required. |
| Interface | Native Python/Tk rather than an iPhone app. The current desktop workflow starts no web server and requires no cloud extraction account. |
| Extraction setup | No preset staging categories on startup. The first uploaded form defines selected fields and page masks. Save them as a reusable named form type. |
| Persistence | Reusable types contain rules only. Projects retain sources and drafts separately. Reopening projects clears review gates. |
| Identifier | The user explicitly chooses a text record identifier. The app does not invent or merge patient/study identities. |
| Review | Extraction suggestions remain tied to source regions. Every applicable field needs confirmation and a reviewer must approve a record before export. |
| Spreadsheet output | Match selected fields to a blank XLSX/CSV template and confirm assignments. Live study REDCap import remains unvalidated. |
| Geometry | Normalized rectangles survive display zoom/scroll. Page-count/shape mismatches block review. Matching dimensions do not prove matching content. |
| Accessibility | Coordinate entry provides a native keyboard path to define masks. Mouse drawing remains implemented but unverified by prior desktop automation. |
| Data scope | The owner authorized both supplied synthetic packets for the private repository. Their test sets have now been used. Use new held-out material for a new independent accuracy claim. |
| Branding | The current name is QwikCap. Company branding has been removed. Earlier working names and build records remain historical. |
| Repository | Private repository under `pranavdabeast24/capitolinus-form-extraction`. The earlier `pmukund24` connector identity is not the selected destination. |
| Collaborator | Developer and potential customer. Contribution/IP and institutional authority must be settled separately from pilot purchase terms. No access invitation has been sent. |
| Future assistance | Evaluate vision-capable handwriting/context assistance later on synthetic material. Local, institution-hosted and contracted-cloud choices require different privacy review. No LLM integration is delivered now. |
| Commercial readiness | Existing competitors validate the category but do not establish differentiation, legal clearance or willingness to pay. Prove reviewer time and error reduction in a bounded pilot. |

See [the conversation record](CONVERSATION.md), [the competitor scan](../COMPETITORS_AND_NAME.md), [privacy design](../LLM_PRIVACY.md), and [testing notes](../TESTING.md) for evidence and limits.

On 2026-11-17 the user supplied a blank PACE import template and reference codebook, confirmed both were blank or fictional, and selected combining several forms into one patient row. The app now offers an optional 512-field catalog and an ordered source bundle with an explicitly entered study ID. This does not authorize automatic patient matching, score calculation, or repeat-instance inference. The original references and source-bearing test projects remain outside Git.
