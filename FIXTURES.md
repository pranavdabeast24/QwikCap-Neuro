# Fictional fixtures

These fixtures were generated for this prototype. They contain fictional practice records, not patient data, and are not an authorized-train or other research dataset. No training, testing split, processed record, or prior verification output is included in this repository.

`generate_samples.py` documents and regenerates the fictional PDF/image samples and their answer key. The included blank spreadsheet templates were authored for this prototype; their source generator is not shipped because it used a workstation-specific path. `spreadsheets/template-manifest.json` records the intended example field associations. SHA-256 below identifies the exact staged files, not a clinical validation claim.

Use `python -m unittest discover -s tests -v` for the portable source tests after installing the pinned dependencies. `verify_samples.py` and `verify_spreadsheet_flow.py` generate ignored local verification outputs; the latter also generates ignored filled example spreadsheets. They must use fictional inputs only. The browser README retains historical references to filled examples and verification reports that are deliberately excluded from this clean source repository.

The ten clean printed English practice forms do not establish accuracy for other layouts, handwriting, capture devices, or Windows OCR. Current REDCap-shaped exports have not been validated against a live REDCap project. Windows and desktop drag behavior remain unverified. Review every value against its source.

| Fixture | SHA-256 |
| --- | --- |
| `samples/README.md` | `21dbf8bff5e8e97e619b381acb2593049dfe5780024f164a689551ad8dbc4274` |
| `samples/answer-key.json` | `bb279b0155abcf8aea5f62c5dfb8deefd8eb489f3543f272fb6f5e0e7ec3aec2` |
| `samples/blank-form.pdf` | `c78b0a7c108adc7a05f641233a7ae40355fbca0f8022eacd08ca5d9981a7a5e4` |
| `samples/expected-redcap.csv` | `23fecca5162b094d68f6adf0fdc985f804832eef46321a31981c234c26567f55` |
| `samples/practice-01-text.pdf` | `5863addc68114251f3cda36fe719c871a1d6e414c24dc6133bc5977f275f41f0` |
| `samples/practice-02-text.pdf` | `5abadc53f262d8c026dfb6ff957360ac3b4544921f70f279da21076cfe29402d` |
| `samples/practice-03-text.pdf` | `800c571bc647ba5bfcc46c099429d08790937204dece525d519d0a72fc13c028` |
| `samples/practice-04-text.pdf` | `3d7d2e198103ca6c6d37c2716682bb126a554855f4fb06565f4a1a5c6e4e5b58` |
| `samples/practice-05-text.pdf` | `24a4558e9fdbebbca0bfa3c06c31b9473dc90bc9232d83c77dcb337a9f0cc4ca` |
| `samples/practice-06-scan.pdf` | `0aa45cffe935e8008e4ff6e8a4658652d1b05e4524859d25287738aac945039d` |
| `samples/practice-06-scan.png` | `4baee391ec7811de9564f4c65a48f024d1162f8c8fea3f8d24a1213e53734714` |
| `samples/practice-07-scan.pdf` | `6fd35a21a1b84b94b44bb892c2c4c7286f297c4cba7b56c0bec0979e6bade539` |
| `samples/practice-08-scan.pdf` | `9bc48bafc620b413edab978800c34eaffff2cc7106b03b9b08912224171f7df3` |
| `samples/practice-09-scan.pdf` | `ecf580b874e7529f826183753f10c8a6761f053c7bdfdc6983631f4f24f904d6` |
| `samples/practice-10-scan.pdf` | `0e0986ed139aac87777f12dbb9ed75e28f20bbbd410694c6cf81eb07cd6fc014` |
| `samples/redcap-import-template.csv` | `ad6131f2ab5062c831f7bc57e86458a9880f5cb8659b007b9a204a87d1764afa` |
| `samples/sample-data-dictionary.csv` | `c32077c4ab7c34a5071245c5363284988ef648b2f1b479be2a50ba9b9ef97079` |
| `samples/sample-schema.json` | `fa9a5a0462571162edb46f258ed68c00fc41e8520d67df3107d17365c2a58787` |
| `spreadsheets/friendly-template.xlsx` | `a3470a92c8a9a17dd9305f563320d71a6c32b020e3a0a6620170125c90791991` |
| `spreadsheets/redcap-template.csv` | `367548e0312d926306f4c226d3e35a2def985cfcbc68fa1ffde7bc41ba439a37` |
| `spreadsheets/redcap-template.xlsx` | `5626cb2018896440d9b1aaf9dc34722023730af5fae940a3cfdd40cb540cd864` |
| `spreadsheets/template-manifest.json` | `832eec6a323e6ebfb589e1f42fc15b1f29a9456bc5953b3b354b1d67990d01d8` |
