# Preview and review controls

This update improves document inspection. It does not change field extraction or the PACE codebook.
The runtime change is commit `055fbd4c2c2bd00aa472a57381ceb0517ae28d63`.

## What changed

The source page gets more width. Zoom buttons and Larger view are visible without Advanced.
Double-click zooms at the cursor. Shift-double-click zooms out.
Command-wheel on Mac and Ctrl-wheel on Windows zoom at the cursor.
Normal scrolling moves vertically. Shift-scroll moves horizontally.
Fit width restores automatic fitting.

The patient check appears before the answer list. Corrections appear before Confirm & next.
Reviewer and approval follow answer review. Layouts and infrequent answer tools use compact menus.
The source remains beside the answer. Larger view is a separate view-only window.

## Native checks on Mac

At 1320 by 850, the source canvas measures 702 by 407 pixels and the answer list is 227 pixels high.
At 1024 by 700, the source measures 406 by 257 pixels and the answer list is 77 pixels high.
Approval stays visible at both sizes.
The normal 1320-pixel window shows a letter-size source at 55%, compared with 45% in the previous app.

The full source suite passed 364 tests, with seven Windows-only skips.
Independent review passed the six native layout tests, five viewport tests, and five reader presentation tests.
These checks cover pointer anchors, rounded coordinates, reverse-direction masks after scrolling, field navigation, view-only state, popup fitting and modal cleanup.

The checks found and corrected small-window overlap and a second scroll shift after window enlargement.
Manual resizing preserves the selected scale and the scroll position that Tk keeps within the page bounds.
It does not promise to keep the page center fixed during a resize.
Mouse zoom does keep the chosen point fixed, except at the page edges where scrolling reaches its limit.

Run the native geometry checks with a working desktop display:

```sh
python -m unittest discover -s tests -p 'test_desktop_layout.py' -v
python -m unittest discover -s tests -p 'test_preview_viewport.py' -v
```

All fixtures in these checks are fictional. View changes do not confirm or alter an answer.
The existing patient identity, source blank, approval, and export mapping gates remain required.

## Packaged Mac checks

The final Apple Silicon app passed native startup with the 512-field catalog.
Its packaged worker passed nine automatic PACE checks and ten custom-mask checks, including reviewed spreadsheet exports.
Compiled application code matches the reviewed source.

Desktop control opened the final app with a fictional project and showed the wider preview, zoom controls, field list, and approval action.
Desktop control stalled during launch, and pointer input was unreliable.
This is visual inspection, not a verified complete mouse-driven correction and export.
The native interaction tests provide the zoom and mask-coordinate evidence.

## Windows checks

The [corrected Windows run](https://github.com/pranavdabeast24/capitolinus-form-extraction/actions/runs/44778600216) passed at commit `bc5b4edb902f3ade1e94d5f3ecd244a0f54e224f`.
It ran the 364-test source suite with one platform skip and passed all 14 source, build, and package checks.
Those checks include packaged startup, local OCR fixtures, reviewed exports, and the nine automatic PACE checks.
The first Windows run exposed a requested-window-size assumption in the layout test.
A constrained native window reproduced its exact 458-pixel preview allocation.
The check now uses the actual client size while retaining the 1024-by-700 client minimum and minimum readable allocations.

## Scope of the results

These are interface and regression checks. They do not establish a new extraction success rate.
The [earlier packet results](PACE_AUTO_2026-11-20.md) retain their original meaning and known gaps.
Real handwriting, clinical deployment, live REDCap import, encryption, and signed distribution remain outside this update.
