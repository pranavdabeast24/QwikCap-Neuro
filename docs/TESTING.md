# What has been tested

The owner accepted the basic v1 workflow on November 20, 2026. [Prototype status](V1_PROTOTYPE.md) distinguishes that feedback from measured accuracy and the incomplete four-document audit.

The new PACE automatic workflow has a [separate verification record](testing/PACE_AUTO_2026-11-20.md).
The measurements below preserve the earlier explicit-reader trial.

The main clinic trial used the supplied `sih_clinic_dataset` packet.
It contains 28 train PDFs and 27 test PDFs.
Each split produces five patient rows.
Both workflows ran through the Mac desktop app and exported Excel.

## Results on the clinic packet

| Check | Train | Test |
| --- | --- | --- |
| Values that match the original exact-key answers | 558 of 572, 97.55% | 495 of 508, 97.44% |
| All expected spreadsheet cells, including blanks and zeroes | 2,379 of 2,560 | 2,439 of 2,560 |
| Exported cells that match the reviewed project | 2,560 of 2,560 | 2,560 of 2,560 |
| Manual answer changes | 0 | 0 |

The exported files preserve the reviewed answers.
That does not mean every answer-key field was filled.
Some reader codes are unavailable, some findings remain blank, and some source punctuation differs.
Three negative findings in each split are not derived from available measurements.
The complete answer-key checks still fail.

One test key uses shorthand for 16 unchecked options.
Expanding that shorthand gives a separate result of 500 matches out of 524.
The [full clinic report](testing/SIH_CLINIC_2026-11-19.md) explains the counts and remaining gaps.

## Software and platform checks

The automatic-review change passed 354 source tests on each platform, with platform-specific skips.
Windows also passed 14 source, build and package checks.
Those Windows checks use generated examples.
The complete supplied-packet desktop walkthrough ran on Mac.

After the trial, invented examples exposed uncertainty and negation errors.
The fixes left all 55 supplied-form results unchanged.
That replay is a regression check, not a new independent test score.
See [the change and package report](testing/SIH_CLINIC_HARDENING_2026-11-19.md).

The sample PDFs contain native text, including handwriting-style fonts.
They do not test real handwriting or camera capture.
Live REDCap import and a person-driven Windows laptop trial remain unverified.

## Run the checks

From the configured source folder:

```sh
python -m unittest discover -s tests -v
python tools/verify_sih_clinic.py --output verification/sih-clinic
python tools/verify_pace_auto.py --output verification/pace-auto
```

The acceptance commands create separate fictional examples.
They do not test the supplied packet or operate the desktop interface.
Use `tools/replay_pace_packets.py` for the supplied packet, as described in the current verification record.
Use the [walkthrough](SIH_CLINIC_WORKFLOW.md) for that workflow.

[All test records](testing/README.md) include commands, file hashes, older PACE results, and package evidence.
