# Vision-model privacy design

Status: **PLANNED; no LLM integration is implemented.** Reviewed 2026-11-13.

The current handoff is a native Tk application for local PDF/OCR extraction, custom region masks, human confirmation, and spreadsheet export. It has no LLM or cloud extraction feature. This note proposes requirements for a future handwriting/context assistant; it does not certify HIPAA compliance, authorize patient-data processing, select a provider, or change any model/runtime configuration.

## Recommendation

Start with synthetic documents, then an institution-approved de-identified evaluation set. Measure whether image-based assistance actually improves handwriting extraction before considering patient material. Handwriting requires a model that can inspect image regions (or a separately validated handwriting-recognition system); a text-only LLM cannot recover strokes discarded by OCR. Context may help suggest a reading, but may also produce a plausible, incorrect value.

For a patient workflow, first ask the institution which deployment and data flow it already approves. Prefer on-device processing when it meets the measured quality and operational needs, or an institution-managed endpoint when its security team can operate it. A contracted cloud API is an option only after institutional review of the exact service, configuration, contracts, and downstream processors. Treat consumer chat/upload services as unsuitable by default for patient documents; personal account settings or a marketing claim are insufficient approval.

| Deployment | Main advantage | Risks and prerequisites | Proposed decision |
| --- | --- | --- | --- |
| On-device vision model | Images can remain on the workstation; no inference-provider transfer is needed. | Hardware/accuracy limits; model provenance and licensing; workstation access, encrypted disk, swap/temp files, caches, backups, telemetry, crash reports, and local server exposure still matter. | Evaluate on synthetic data first. Patient use requires approved device controls and verified local data flow. |
| Institution-hosted private endpoint | Central access controls, operational ownership, and audit practices may already exist. | “Private” does not establish who operates hosting, logging, support, backups, or subprocessors. Capacity, model changes, and retention need owners. | Preferred shared-service route if the institution explicitly approves the exact endpoint and study workflow. |
| Contracted cloud API | Managed operations and potentially stronger image recognition. | External disclosure, vendor/subprocessor chain, retention, training, support access, residency, contractual scope, and service configuration require review. | Use only an approved institutional account and covered service after the necessary agreements and controls are effective. |

These are engineering recommendations, not findings that a deployment is safe or compliant.

## Approval and legal scope

HIPAA does not govern every research dataset or researcher. Establish whether a covered entity/business associate is involved, what the data are, and which institutional, study, contractual, state, or other requirements apply. For covered-entity research, HHS describes authorization and specific permitted alternatives, including documented IRB/Privacy Board waivers; human-subject protections are separate. A user's per-job confirmation cannot replace the applicable research permission. [HHS: HIPAA and Research](https://www.hhs.gov/hipaa/for-professionals/special-topics/research/index.html)

Where HIPAA applies, a cloud service processing ePHI on behalf of a covered entity or business associate generally is a business associate, including relevant subcontractors. A BAA and a documented risk analysis are needed; encryption or private hosting alone does not settle those obligations. A BAA alone is not a complete compliance program. [HHS: Cloud Computing](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html)

Before patient use, the institution should approve a data-flow inventory and responsibility matrix covering the app, endpoint operator, model provider, hosting, monitoring, support, and all relevant subprocessors. Obtain written answers for:

- Permitted purpose and access: who can see images, prompts, outputs, and metadata; administrator/support access; authentication, authorization, encryption, keys, incident response, and contract scope.
- Secondary use: whether any payload or output is used for training, evaluation, product improvement, or human review; opt-out/default behavior; abuse-monitoring and support logs, exceptions, and access controls.
- Lifecycle: retention for each data category, retries/queues, caches, replicas, backups, recovery copies, deletion deadlines, legal holds, and evidence of deletion. Include operating and support locations, data residency, and cross-border access.
- Contract chain: required BAAs/subcontractor protections, notification duties, change notices, termination, and return/destruction terms. HHS identifies subcontractor restrictions and return/destruction where feasible among BAA requirements. [HHS: Business Associate Contracts](https://www.hhs.gov/hipaa/for-professionals/covered-entities/sample-business-associate-agreement-provisions/index.html)

Do not promise “zero retention,” “never trained on,” or a particular residency/deletion outcome unless the applicable contract and actual configuration support it. Unknown answers block patient-data submission.

## Minimize disclosure without claiming de-identification

The proposed app should send only the smallest reviewed image region and essential neighboring labels, never a whole document merely for convenience. Render the final permitted crop locally; do not send the original PDF, hidden text, unrelated pages, filenames containing identifiers, or unused metadata. Keep the patient-to-study-ID mapping local in an access-controlled location and use nonidentifying job/region references in requests.

**Cropped context and pseudonymous IDs can still be PHI.** Dates, unusual clinical narratives, handwriting, and combinations of remaining details can be identifying. Masking selected boxes is not a de-identification determination. HIPAA de-identification uses Safe Harbor or Expert Determination; the appropriate institutional process must establish that a dataset qualifies. [HHS: De-identification Guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html)

## Proposed extraction boundary and review

These controls are requirements for future implementation, not capabilities delivered by this handoff:

1. Keep model assistance off by default. Before each job, show the destination/operator, model/version, exact outgoing images and text, sensitivity, and relevant retention terms. Require an authorized user's explicit approval of that payload and destination under the approved study workflow. Any changed payload or destination requires renewed review.
2. Treat all document text and images as untrusted evidence, including instructions written inside a form. Give the extraction component no agent loop, filesystem tools, browser, shell, secrets, or model-controlled network access. Only the application may call the approved inference endpoint. Do not rely on a prompt alone to contain document instructions. NIST describes indirect prompt injection through externally supplied content. [NIST: Adversarial Machine Learning, AI 100-2e2025](https://csrc.nist.gov/pubs/ai/100/2/e2025/final)
3. Request bounded structured suggestions for explicitly selected fields. Enforce schema, field allowlists, lengths, types, ranges, and existing application validators outside the model. Reject invalid output; preserve the manual path. A well-formed answer is not proof of accuracy.
4. Require `null`/`uncertain` for illegible, absent, or conflicting evidence. Preserve source page/region, displayed evidence, OCR/model origin, model/version, and subsequent human edits in the approved local record. Model confidence is not a calibrated probability unless demonstrated by evaluation. Never infer missing patient facts, invent or reconcile patient identifiers, mark approval, or bypass a human decision.
5. Display each suggestion beside its source region. Require human acceptance or correction before spreadsheet export; distinguish suggested from approved values. NIST identifies confident false output, privacy harms, and human over-reliance as generative-AI risks. [NIST: Generative AI Profile, AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
6. Keep PHI out of application/debug logs, analytics, git, issues, screenshots, and support bundles. Use minimal nonidentifying operational events; protect any necessary sensitive audit/provenance records separately. Apply approved storage and deletion controls to originals, crops, outputs, exports, and temporary artifacts.
7. Fail closed on unavailable endpoints, unapproved configuration, missing review, or validation failure. Never switch silently to another model, cloud service, consumer chat, or remote OCR provider. External fallback requires its own institutional approval and per-job payload review.

## Release gate

Before implementation: agree on the approved data flow, responsible owners, field-level quality criteria, and privacy controls. Before patient use: complete institutional security/privacy and research review, relevant agreements, access/retention configuration, and an evaluation using representative authorized material. Include difficult handwriting, missing values, conflicting labels, injected document instructions, wrong-patient boundaries, and network/validation failures. Measure incorrect accepted values and abstentions as well as transcription accuracy. Reassess material model, endpoint, contract, or data-flow changes. Until those gates are satisfied, retain the existing local OCR and manual confirmation workflow.
