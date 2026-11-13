# Security and research-use limits

This is a research prototype. Local processing does not establish clinical suitability or permission to handle sensitive data. It lacks managed access controls, encryption at rest, managed retention, and tamper-evident audit trails. OCR and exported values require source review. Current REDCap-shaped outputs have not been validated with a live REDCap project. Windows execution and desktop drag behavior remain unverified.

Use fictional data until the intended institution approves the full environment, privacy and security controls, validation plan, and research workflow. Saved projects contain source documents and entered values. Exports persist at the chosen destination; crashes can leave local temporary files.

Do not put PHI, possible PHI, credentials, or private research data in issues, pull requests, discussions, logs, or vulnerability reports. For a suspected vulnerability, contact the repository owner through an already established private channel and provide a minimal fictional reproduction, affected version, impact, and proposed mitigation. Do not publish exploit details or real records. There is no invented support address, response-time promise, or production security commitment.

The owner should assess and privately coordinate fixes before broader disclosure. Do not enable hosted CI, upload artifacts, add telemetry, or introduce external processing without reviewing the data boundary and obtaining the relevant authorization.
