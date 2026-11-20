# Correct and reuse a form layout

PACE is the only preset. Its variable names, answer choices and data types come from the supplied codebook.
The app recognizes the supported forms and suggests their answers first.
You do not need to draw 512 boxes.

## Correct an answer

Select the field in the review list. Type the correct answer, or choose its allowed option, then confirm it against the source.
This changes that patient's answer. It does not teach the app to reuse that value for another patient.

## Correct an answer box

1. Select the field and open the source page with its answer.
2. Click **Redraw answer area**.
3. Drag a rectangle around the answer. A box tells the app where to read; it does not hide or redact information.
4. Check the new suggestion and correct it if necessary.
5. Click **Confirm & next**.

If a supported source has a missing field, use **Add PACE field…** to select the exact variable from its instrument. Draw that answer area and review it.
The app does not infer a different visit or questionnaire version from a similar label.

## Reuse the boxes

Click **Save form layout…** and save the JSON file outside the repository.
It contains field rules and form anchors, without patient answers, documents, filenames or identifiers.
In another project, click **Load form layout…**, then add the next patient's forms.
The app checks the form anchors before using a saved box. Matching paper sizes alone are not enough.
The sticker is found again on each source; it is not copied from the previous patient.

A layout file differs from a project. **File > Save project as…** keeps source documents, answers and review work. Projects and exports are not encrypted.

Unknown layouts and ambiguous mappings remain blocked. Real handwriting and camera capture are not validated. Older custom projects remain compatible internally, but new work uses the PACE workflow.
