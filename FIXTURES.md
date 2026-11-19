# Fictional fixtures

The 2026-11-17 study reference assets are separate from the generated fictional record fixtures below. `study_profiles/pace.json` contains bounded field metadata derived from the user-confirmed blank codebook. `spreadsheets/pace-import-template.csv` contains only the 512 named destination headers. Neither contains patient rows. The original references are not shipped. Instrument content and commercial distribution rights still need appropriate review.

| Study reference asset | SHA-256 |
| --- | --- |
| `study_profiles/pace.json` | `e8a2c021405da7defead007e9f8e7f5f3852ae926c35f2fb687a474e6f8faf53` |
| `spreadsheets/pace-import-template.csv` | `cdcd6ba3a0449bcde17cb1049c026572bd1224e55bad32084fc9c579bcb9fd8e` |

`tools/verify_pace_flow.py` generates new fictional forms for patient-bundle acceptance. Its generated source PDFs, source-bearing projects and exports remain ignored verification outputs.

The original practice fixtures were generated for this prototype and contain fictional records. The separately [supplied synthetic SIH packet](datasets/sih-synthetic/README.md) is now included at the owner's request. It contains 111 unchanged original PDFs, including 28 train forms, 27 test forms, their 55 answer keys, and the index. Its hash manifest and independent evaluation files travel with the clone. This is the packet used for the actual train/test results, not the app-authored practice kit. Source-bearing projects and unreviewed outputs remain excluded.

`examples/quickcap-actual-train-readout.xlsx` is a byte-identical copy of the native desktop export from 28 fictional train PDFs, combined into five patient rows. All 2,560 destination cells and 512 ordered headers passed independent verification, with zero manual value corrections. Its SHA-256 is `f8aae166a92cbe5815f6008cf1fc85bc90651fbd5b47cb03e21198cb5f978a03`. See [the actual-dataset report](docs/testing/actual-pace-dataset-2026-11-18.md) for the coverage limits, including nine total-score entries absent from the supplied destination template.

`examples/qwikcap-supplied-test-reviewed-readout.xlsx` preserves the actual native Mac app export from 27 supplied fictional test forms, combined into five patient rows. Source review corrected one raw word omission. All 2,560 reviewed cells passed independent verification. Its SHA-256 is `ed30b51f2752dcec51f0ce478ff3e2148aeedc707eee7c4fb8631cdce8b12343`. Raw extraction remains 550 of 551 mapped key values and 2,559 of 2,560 patient destination cells. Eight key-only totals are outside the destination. See [the held-out report](docs/testing/heldout-pace-2026-11-18.md). Neither reviewed workbook was regenerated or modified during packaging.

`generate_samples.py` documents and regenerates the fictional PDF/image samples and their answer key. The included blank spreadsheet templates were authored for this prototype; their source generator is not shipped because it used a workstation-specific path. `spreadsheets/template-manifest.json` records the intended example field associations. SHA-256 below identifies the exact staged files, not a clinical validation claim.

Use `python -m unittest discover -s tests -v` for the portable source tests after installing the pinned dependencies. `verify_samples.py` and `verify_spreadsheet_flow.py` generate ignored local verification outputs; the latter also generates ignored filled example spreadsheets. They must use fictional inputs only. The browser README retains historical references to filled examples and verification reports that are deliberately excluded from this clean source repository.

The ten clean printed English practice forms do not establish accuracy for other layouts, handwriting, or capture devices. Windows OCR and packaging acceptance are recorded in [the testing guide](docs/TESTING.md). A person-driven Windows walkthrough of the supplied packet and native desktop drag behavior remain unverified. Current REDCap-shaped exports have not been validated against a live REDCap project. Review every value against its source.

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
