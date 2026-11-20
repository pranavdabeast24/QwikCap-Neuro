# Create fields for your form

QwikCap starts with no preset fields.
An answer mask is a rectangle that tells the app where to read one answer.
Use a practice PDF from `samples/` for your first type.

## Create a reusable extraction type

1. Choose **File > New project**.
2. Import a PDF or image.
   The mask designer shows its pages.
3. Enter a **Type name**.
4. Click **Draw field**.
5. Drag a rectangle around one answer area.
   A field appears in **Your fields**.
6. Enter a unique lowercase **Field name**, such as `record_id`.
7. Enter a readable **Label**.
8. Choose the **Value type**.
   The options are text, integer, number, date, and choice.
   Dates use `YYYY-MM-DD`.
9. For a choice field, enter codes such as `{"1":"Yes","0":"No"}`.
10. Repeat these steps for each answer you need.
11. Select one text field.
    Check **Required**.
    Check **Use as record identifier (text)**.
12. Click **Apply type**.
    The app shows suggested answers for review.
13. Choose **Advanced > Form type > Save extraction type…**.
    The saved type contains rules and masks, without source documents or answers.

To reuse the type, choose **Advanced > Form type > Load extraction type…**.
Use it only with the same form layout.
Matching page sizes do not establish a matching layout.
Check every mask on the new source.

## Review and export

1. Compare each suggested answer with its complete source answer.
2. Correct any error.
3. Click **Confirm & next** after each source check.
   Keep missing answers blank.
   A blank does not mean zero or No.
4. Enter your name in **Reviewer**.
5. Click **Approve document**.
6. Open **Map & export**.
7. Click **Use fields as columns** for a new Excel workbook.
   To use your own blank template, choose **Advanced > Spreadsheet > Import XLSX / CSV…** instead.
8. Assign each destination column to a field or **Leave blank**.
   The record identifier must appear exactly once.
9. Inspect **Populated preview**.
10. Click **Confirm column mapping**.
11. Export the workbook or CSV.
    Only approved records appear in the export.
    CSV templates produce CSV output.

Use a blank table without formulas, macros, or existing data.
Repeating REDCap rows need a separate validated conversion before import.

Choose **File > Save project as…** to keep sources, values, and unfinished work.
Reopening a project requires fresh field checks, approval, and mapping confirmation.
