# Contributing privately

Source access and contributions are by invitation to this private repository. Agree on scope, confidentiality, permitted use, and contribution intellectual-property terms before development begins. Participation, a pull request, and a review do not automatically transfer ownership or grant a license to either party's pre-existing work. Resolve contributor authority and any employer or institution rights before accepting code.

Use a branch and a private pull request. Describe the user-visible change, relevant risks, and validation. Keep changes small and require maintainer review before merging. Run `python -m unittest discover -s tests -v` with the pinned dependencies; use only fictional fixtures. Native packaging requires validation on each target operating system. Keep the inactive CI template outside `.github/workflows/` until deliberately reviewed and enabled.

The current Mac and Windows builds use the declared dependency pins. See [the current testing evidence](docs/TESTING.md) and [historical environment record](docs/BUILD_ENVIRONMENT.md). Do not change dependencies or install packages without the applicable authorization. Customer distribution also requires a release-specific license and notice inventory, including bundled native libraries. The authorized user-supplied synthetic packet is identified in [FIXTURES.md](FIXTURES.md). Its private inclusion does not establish permission for public redistribution of third-party instruments.

Never include patient information, possible PHI, credentials, private research datasets, customer documents, saved projects, exports, screenshots of private records, or workstation-specific paths in source, issues, commits, logs, or pull requests. Use generated fictional examples. Check staged files and their diffs before every commit; `.gitignore` is only a convenience.

Report vulnerabilities through the private channel described in [SECURITY.md](SECURITY.md). See [OWNERSHIP.md](OWNERSHIP.md) for the proprietary notice and [docs/COLLABORATION.md](docs/COLLABORATION.md) for proposed roles and agreement topics.
