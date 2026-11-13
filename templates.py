"""Bounded, local spreadsheet templates and deliberate field-to-column mapping.

Template inputs are untrusted. Inspect ZIP/XML before openpyxl can deserialize
them, never evaluate spreadsheet expressions, and re-inspect before every export.
Only the selected worksheet survives an XLSX export.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import io
import math
from pathlib import PurePosixPath
import posixpath
import re
import stat
import unicodedata
from urllib.parse import unquote
import zipfile

MAX_TEMPLATE_BYTES = 4 * 1024 * 1024
MAX_EXPANDED_BYTES = 30 * 1024 * 1024
MAX_ZIP_ENTRIES = 300
MAX_COLUMNS = 100
MAX_TEMPLATE_ROWS = 2000
MAX_EXPORT_ROWS = 60
MAX_VALUE_LENGTH = 4000
MAX_EXCEL_ROW_HEIGHT = 409.5


class TemplateError(ValueError):
    """An unsafe, unsupported, or incomplete template or mapping."""


def _dependencies():
    try:
        import openpyxl
        from defusedxml import ElementTree
    except ImportError as error:
        raise TemplateError("Spreadsheet support requires openpyxl and defusedxml. Install the application requirements.") from error
    return openpyxl, ElementTree


def _letter(index: int) -> str:
    result = ""
    value = index + 1
    while value:
        value, digit = divmod(value - 1, 26)
        result = chr(65 + digit) + result
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_validation_constants(root) -> set[int]:
    """OOXML names literal validation bounds 'formula1'; these are not code.

    Permit only numeric constants or short quoted code lists in their precise
    validation context. References, functions, named ranges, and custom
    validation expressions never qualify.
    """
    allowed = set()
    numeric = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?\Z")
    for validation in root.iter():
        if _local_name(validation.tag) != "dataValidation":
            continue
        kind = validation.attrib.get("type", "")
        for expression in validation:
            tag = _local_name(expression.tag)
            if tag not in {"formula1", "formula2"} or len(expression):
                continue
            text = expression.text or ""
            if kind in {"whole", "decimal"} and len(text) <= 100 and numeric.fullmatch(text):
                number = Decimal(text)
                if number.is_finite() and -307 <= number.adjusted() <= 308:
                    allowed.add(id(expression))
            elif kind == "list" and tag == "formula1" and 2 <= len(text) <= 255 and text.startswith('"') and text.endswith('"'):
                codes = text[1:-1].split(",")
                if 1 <= len(codes) <= 100 and all(re.fullmatch(r"[A-Za-z0-9_. -]{1,64}", code) and code.strip() for code in codes):
                    allowed.add(id(expression))
    return allowed


def _format(data: bytes, filename: str) -> str:
    if not isinstance(data, bytes) or not data or len(data) > MAX_TEMPLATE_BYTES:
        raise TemplateError("Upload a nonempty template no larger than 4 MB.")
    if not isinstance(filename, str) or "\x00" in filename:
        raise TemplateError("A CSV or XLSX filename is required.")
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise TemplateError("Only CSV and XLSX templates are supported; XLS/XLSM and macro-enabled workbooks are rejected.")
    if suffix == ".xlsx":
        if not data.startswith(b"PK\x03\x04"):
            raise TemplateError("The XLSX file signature does not match its filename.")
        return "xlsx"
    if data.startswith((b"PK", b"%PDF", b"\xd0\xcf\x11\xe0")) or b"\x00" in data:
        raise TemplateError("The CSV file signature or encoding is invalid. Use UTF-8 CSV.")
    return "csv"


def _preflight_xlsx(data: bytes) -> None:
    _, safe_xml = _dependencies()
    forbidden = ("vbaproject", "externallinks/", "embeddings/", "activex/", "ctrlprops/", "customui/", "connections", "querytables/", "macrosheets/", "dialogsheets/", "vml")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise TemplateError("The XLSX archive contains too many entries (maximum 300).")
            names: set[str] = set()
            total = 0
            for entry in entries:
                name = entry.filename
                parts = name.split("/")
                if not name or name.startswith("/") or "\\" in name or ":" in name or any(part in {".", ".."} for part in parts) or "\x00" in name:
                    raise TemplateError("The XLSX archive contains an unsafe traversal path.")
                lowered = name.casefold()
                if lowered in names:
                    raise TemplateError("The XLSX archive contains duplicate entries.")
                names.add(lowered)
                mode = (entry.external_attr >> 16) & 0xFFFF
                if mode and stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise TemplateError("Symbolic links and special archive members are rejected.")
                if entry.flag_bits & 1:
                    raise TemplateError("Encrypted XLSX members are not supported.")
                if entry.file_size < 0 or entry.compress_size < 0:
                    raise TemplateError("The XLSX archive has invalid member sizes.")
                total += entry.file_size
                if total > MAX_EXPANDED_BYTES:
                    raise TemplateError("The expanded XLSX exceeds the 30 MB processing limit.")
                if any(token in lowered for token in forbidden) or lowered.endswith((".bin", ".xlsm", ".xlam", ".exe", ".dll", ".js", ".svg", ".html", ".htm", ".hta", ".vbs", ".ps1")):
                    raise TemplateError("Macros, embedded objects, controls, connections, and external links are rejected.")
            if not {"[content_types].xml", "xl/workbook.xml"}.issubset(names):
                raise TemplateError("The archive is not a supported XLSX workbook.")
            expanded = 0
            for entry in entries:
                if entry.is_dir():
                    continue
                with archive.open(entry) as member:
                    payload = member.read(MAX_EXPANDED_BYTES + 1)
                expanded += len(payload)
                if len(payload) != entry.file_size or expanded > MAX_EXPANDED_BYTES:
                    raise TemplateError("The expanded XLSX exceeds its declared size or processing limit.")
                lowered = entry.filename.casefold()
                if not lowered.endswith((".xml", ".rels")):
                    raise TemplateError("Use a simple XLSX template containing only worksheet XML and styling parts. Embedded images and unsupported package parts are rejected.")
                try:
                    root = safe_xml.fromstring(payload, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                except Exception as error:
                    raise TemplateError("The XLSX contains malformed or unsafe XML.") from error
                literal_validations = _safe_validation_constants(root)
                for element in root.iter():
                    tag = _local_name(element.tag)
                    if tag == "f" or tag.casefold().endswith("formula") or (tag in {"formula1", "formula2"} and id(element) not in literal_validations):
                        raise TemplateError("Formula-containing templates are rejected. Remove every formula first.")
                    if tag in {"oleObject", "control", "externalReference", "connection", "webPr", "ddeLink", "oleLink", "script"}:
                        raise TemplateError("Active or external workbook content is rejected.")
                    if tag == "Override":
                        content_type = element.attrib.get("ContentType", "").casefold()
                        if any(token in content_type for token in ("macroenabled", "vbaproject", "activex", "oleobject", "external link")):
                            raise TemplateError("Macro-enabled or active content is rejected.")
                    if tag == "Relationship":
                        target = unquote(element.attrib.get("Target", ""))
                        relation_type = element.attrib.get("Type", "").casefold()
                        if element.attrib.get("TargetMode", "").casefold() == "external" or ":" in target or "\\" in target or any(ord(char) < 32 for char in target):
                            raise TemplateError("External links and relationships are rejected.")
                        if any(token in relation_type for token in ("external", "oleobject", "activex", "attachedtemplate", "connections", "vbaproject")):
                            raise TemplateError("Active or external relationships are rejected.")
                        base = posixpath.dirname(posixpath.dirname(entry.filename))
                        resolved = posixpath.normpath(posixpath.join(base, target)) if not target.startswith("/") else posixpath.normpath(target.lstrip("/"))
                        if resolved == ".." or resolved.startswith("../"):
                            raise TemplateError("The XLSX contains an unsafe relationship traversal path.")
                    if tag == "row":
                        try:
                            if int(element.attrib.get("r", "1")) not in range(1, MAX_TEMPLATE_ROWS + 1):
                                raise TemplateError("A worksheet exceeds the 2,000-row processing limit.")
                        except ValueError as error:
                            if isinstance(error, TemplateError):
                                raise
                            raise TemplateError("A worksheet has an invalid row reference.") from error
                    if tag in {"c", "dimension"}:
                        reference = element.attrib.get("r" if tag == "c" else "ref", "")
                        for address in reference.split(":"):
                            match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", address)
                            if not match:
                                raise TemplateError("A worksheet has an invalid cell reference.")
                            column = 0
                            for char in match[1]:
                                column = column * 26 + ord(char) - 64
                            if column > MAX_COLUMNS or int(match[2]) > MAX_TEMPLATE_ROWS:
                                raise TemplateError("A worksheet exceeds 100 columns or 2,000 rows.")
    except TemplateError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError, NotImplementedError) as error:
        raise TemplateError("The XLSX archive is damaged or unsupported.") from error


def _load_xlsx(data: bytes):
    _preflight_xlsx(data)
    openpyxl, _ = _dependencies()
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=False, data_only=False, keep_links=False)
    except Exception as error:
        raise TemplateError("The XLSX workbook could not be read safely.") from error
    for worksheet in workbook.worksheets:
        if worksheet.max_row > MAX_TEMPLATE_ROWS or worksheet.max_column > MAX_COLUMNS:
            raise TemplateError("A worksheet exceeds 100 columns or 2,000 rows.")
        if any(cell.data_type == "f" for cell in worksheet._cells.values()):
            raise TemplateError("Formula-containing templates are rejected.")
    return workbook


def _populated(value) -> bool:
    return value is not None and value != ""


def _headers(values: list) -> list[dict]:
    while values and not _populated(values[-1]):
        values.pop()
    if not values or len(values) > MAX_COLUMNS:
        raise TemplateError("The header must contain between 1 and 100 columns.")
    columns = []
    seen = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise TemplateError("Every column inside the header must have a nonempty text name.")
        if len(value) > 255 or any(unicodedata.category(char) in {"Cc", "Cf"} for char in value):
            raise TemplateError("Column names must be at most 255 characters without control characters.")
        if value.lstrip().startswith(("=", "+", "-", "@")):
            raise TemplateError("Column names beginning with spreadsheet formula characters are rejected.")
        identity = unicodedata.normalize("NFKC", value).strip().casefold()
        if identity in seen:
            raise TemplateError("Duplicate column names are rejected.")
        seen.add(identity)
        columns.append({"name": value, "letter": _letter(index), "index": index})
    return columns


def _best_header(worksheet) -> int | None:
    counts: Counter[int] = Counter()
    for cell in worksheet._cells.values():
        if cell.row <= 20 and isinstance(cell.value, str) and cell.value.strip():
            counts[cell.row] += 1
    candidates = [(count, -row) for row, count in counts.items()]
    return -max(candidates)[1] if candidates else None


def inspect_template(data: bytes, filename: str, sheet: str | None = None, header_row: int | None = None) -> dict:
    """Return safe names/order; no workbook cell values are returned."""
    kind = _format(data, filename)
    if kind == "csv":
        if sheet not in {None, ""} or header_row not in {None, 1}:
            raise TemplateError("CSV templates use their first row as headers and have no worksheet selector.")
        try:
            text = data.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text, newline=""), strict=True)
            values = next(reader)
            columns = _headers(values)
            for index, row in enumerate(reader, start=2):
                if index > MAX_TEMPLATE_ROWS or len(row) > MAX_COLUMNS:
                    raise TemplateError("The CSV exceeds 100 columns or 2,000 rows.")
                if any(_populated(value) for value in row):
                    raise TemplateError("The template already contains destination data. Upload a blank template.")
        except (UnicodeDecodeError, csv.Error, StopIteration) as error:
            raise TemplateError("The template is not a valid UTF-8 CSV with a header row.") from error
        return {"format": "csv", "sheet": None, "sheets": [], "headerRow": 1, "columns": columns, "warnings": []}
    workbook = _load_xlsx(data)
    try:
        visible = [worksheet for worksheet in workbook.worksheets if worksheet.sheet_state == "visible"]
        if sheet is None:
            worksheet = next((item for item in visible if _best_header(item) is not None), None)
            if worksheet is None:
                raise TemplateError("The workbook has no visible worksheet with text headers.")
        else:
            if not isinstance(sheet, str) or sheet not in workbook.sheetnames:
                raise TemplateError("Choose an existing worksheet.")
            worksheet = workbook[sheet]
            if worksheet.sheet_state != "visible":
                raise TemplateError("Hidden worksheets cannot be destinations.")
        if header_row is None:
            header_row = _best_header(worksheet)
        if type(header_row) is not int or not 1 <= header_row <= min(MAX_TEMPLATE_ROWS - MAX_EXPORT_ROWS, worksheet.max_row):
            raise TemplateError("Choose a valid header row with room for exported records.")
        if any(merged.min_row <= header_row <= merged.max_row for merged in worksheet.merged_cells.ranges):
            raise TemplateError("Merged header cells are rejected. Use one separate header cell per column.")
        columns = _headers([cell.value for cell in worksheet[header_row]])
        if any(cell.row > header_row and _populated(cell.value) for cell in worksheet._cells.values()):
            raise TemplateError("The template already contains destination data. Upload a blank template.")
        if any(merged.max_row > header_row for merged in worksheet.merged_cells.ranges):
            raise TemplateError("Merged destination cells are rejected. Unmerge the data-entry area.")
        warnings = []
        if len(workbook.worksheets) > 1:
            warnings.append("Export retains only the selected worksheet; all other worksheets, including hidden sheets, are removed.")
        warnings.append("Workbook properties, comments, hyperlinks, and defined names are removed on export.")
        warnings.append("Export makes populated rows and columns visible, clears filters and conditional formatting, and uses readable data-cell formats.")
        return {"format": "xlsx", "sheet": worksheet.title, "sheets": [item.title for item in visible], "headerRow": header_row, "columns": columns, "warnings": warnings}
    finally:
        workbook.close()


def _schema_fields(schema) -> list[dict]:
    fields = schema.get("fields") if isinstance(schema, dict) else schema
    if not isinstance(fields, list) or not fields or len(fields) > 500:
        raise TemplateError("The source schema must contain between 1 and 500 fields.")
    names = set()
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not field["name"] or field["name"] in names:
            raise TemplateError("The source schema has invalid or duplicate field names.")
        names.add(field["name"])
    return fields


def validate_mapping(spec: dict, schema, mappings: dict, confirmed: bool = False) -> dict:
    """Every destination must explicitly select one field or None (leave blank)."""
    errors = []
    unmapped = []
    identifier_column = None
    try:
        fields = _schema_fields(schema)
        columns = spec["columns"]
        if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_COLUMNS:
            raise TemplateError("The template specification has invalid columns.")
        names = [column["name"] for column in columns]
        if any(not isinstance(name, str) for name in names) or len(set(names)) != len(names):
            raise TemplateError("The template specification has duplicate or invalid columns.")
        if not isinstance(mappings, dict):
            raise TemplateError("The field mapping must be an object.")
        known = {field["name"] for field in fields}
        unknown = set(mappings) - set(names)
        if unknown:
            errors.append("The mapping contains columns absent from this template.")
        sources = []
        for name in names:
            if name not in mappings:
                unmapped.append(name)
                continue
            source = mappings[name]
            if source is None:
                continue
            if not isinstance(source, str) or source not in known:
                errors.append(f"Column {name!r} references an unknown source field.")
                continue
            sources.append(source)
            if source == fields[0]["name"]:
                identifier_column = name
        if unmapped:
            errors.append("Resolve every destination column: choose a source field or explicitly leave it blank.")
        if any(count > 1 for count in Counter(sources).values()):
            errors.append("A source field cannot be assigned to more than one destination column.")
        if sources.count(fields[0]["name"]) != 1:
            errors.append("Map the first schema field (record identifier) to exactly one destination column.")
            identifier_column = None
    except (TemplateError, KeyError, TypeError) as error:
        errors.append(str(error) if isinstance(error, TemplateError) else "The template specification is invalid.")
    return {"valid": not errors, "errors": errors, "unmapped": unmapped, "identifierColumn": identifier_column}


def _normalized(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", value).casefold() if char.isalnum())


def suggested_mapping(spec: dict, schema) -> dict:
    """Literal normalized name/label/alias matches only; suggestions are not consent."""
    fields = _schema_fields(schema)
    lookup: dict[str, set[str]] = {}
    for field in fields:
        aliases = field.get("aliases", [])
        candidates = [field["name"], field.get("label", "")] + (aliases if isinstance(aliases, list) else [])
        for candidate in candidates:
            if isinstance(candidate, str) and _normalized(candidate):
                lookup.setdefault(_normalized(candidate), set()).add(field["name"])
    suggestions = {}
    for column in spec.get("columns", []):
        candidates = lookup.get(_normalized(column["name"]), set())
        if len(candidates) == 1:
            suggestions[column["name"]] = next(iter(candidates))
    counts = Counter(suggestions.values())
    return {name: source for name, source in suggestions.items() if counts[source] == 1}


def _numeric_value(value: str, field: dict, identifier: bool):
    if identifier or field.get("choices") or field.get("type") not in {"integer", "number"} or not value:
        return value
    try:
        number = Decimal(value)
    except InvalidOperation:
        return value
    if not number.is_finite() or (field.get("type") == "integer" and number != number.to_integral_value()):
        return value
    significant = len(number.as_tuple().digits)
    for digit in reversed(number.as_tuple().digits):
        if digit:
            break
        significant -= 1
    if significant > 15 or number.adjusted() > 308 or number.adjusted() < -307:
        return value
    if number == number.to_integral_value():
        return int(number)
    converted = float(number)
    return converted if math.isfinite(converted) else value


def _export_rows(rows, fields: list[dict]) -> None:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_EXPORT_ROWS:
        raise TemplateError("Export between 1 and 60 approved records at a time.")
    known = {field["name"] for field in fields}
    identifiers = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - known:
            raise TemplateError("An export record has unknown source fields.")
        for value in row.values():
            if not isinstance(value, str) or len(value) > MAX_VALUE_LENGTH or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
                raise TemplateError("Export values must be text of at most 4,000 characters without unsafe control characters.")
        identifier = row.get(fields[0]["name"], "")
        if not identifier.strip() or identifier in identifiers:
            raise TemplateError("Export record identifiers must be nonempty and unique.")
        identifiers.add(identifier)


def _without_personal_properties(data: bytes) -> bytes:
    # openpyxl adds a modification timestamp while saving. Replace the core
    # property part after save so no supplied names or document timestamps leak.
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as destination:
        total = 0
        for entry in source.infolist():
            payload = source.read(entry)
            if entry.filename == "docProps/core.xml":
                payload = b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"/>'
            total += len(payload)
            if total > MAX_EXPANDED_BYTES:
                raise TemplateError("The export exceeds the 30 MB expanded workbook limit.")
            destination.writestr(entry, payload)
    return output.getvalue()


def _display_height(worksheet, cell) -> float:
    """Conservatively estimate wrapped text without a spreadsheet renderer.

    Excel column widths use default-font characters (about seven pixels at
    11 pt); text width and line height also follow this cell's actual font.
    Explicit line breaks always consume a line, including empty lines.
    """
    dimension = worksheet.column_dimensions.get(cell.column_letter)
    if dimension is None:
        dimension = next((item for item in worksheet.column_dimensions.values()
                          if item.min is not None and item.max is not None
                          and item.min <= cell.column <= item.max), None)
    width = dimension.width if dimension is not None else worksheet.sheet_format.defaultColWidth
    width = width if width is not None and math.isfinite(width) and width > 0 else 8.43
    size = cell.font.sz or 11
    size = size if math.isfinite(size) and size > 0 else 11
    available = max(1, (width * 7 + 5) * .75 - 6 - (cell.alignment.indent or 0) * size)
    bold = 1.06 if cell.font.bold else 1
    monospace = any(name in (cell.font.name or "").casefold() for name in ("courier", "consolas", "mono"))

    def text_width(text):
        total = 0
        for char in text:
            if unicodedata.east_asian_width(char) in {"W", "F"}:
                total += 1
            elif monospace:
                total += .62
            elif char in "ilI.,:;!'|":
                total += .3
            elif char in "MW@#%&":
                total += .9
            elif char.isupper():
                total += .68
            else:
                total += .56
        return total * size * bold

    lines = 0
    for paragraph in re.split(r"\r\n|\r|\n", str(cell.value) if cell.value is not None else ""):
        lines += 1
        used = 0
        for word in paragraph.split():
            length = text_width(word)
            gap = size * .33 if used else 0
            if used and used + gap + length > available:
                lines += 1
                used = 0
                gap = 0
            if length > available:
                extra = max(0, math.ceil(length / available) - 1)
                lines += extra
                used = length - extra * available
            else:
                used += gap + length
    return lines * size * 1.35 + 4


def fill_template(data: bytes, filename: str, spec: dict, mappings: dict, schema, rows: list[dict[str, str]], export_format: str | None = None) -> bytes:
    """Fill only caller-supplied approved rows after a fresh template/mapping check."""
    if not isinstance(spec, dict):
        raise TemplateError("Inspect the template before exporting.")
    fresh = inspect_template(data, filename, sheet=spec.get("sheet"), header_row=spec.get("headerRow"))
    if any(fresh.get(key) != spec.get(key) for key in ("format", "sheet", "headerRow", "columns")):
        raise TemplateError("The template changed after mapping. Inspect and map it again.")
    if export_format not in {None, "native", "csv", "xlsx"}:
        raise TemplateError("Choose CSV or the native template export format.")
    output_format = fresh["format"] if export_format in {None, "native"} else export_format
    if output_format == "xlsx" and fresh["format"] != "xlsx":
        raise TemplateError("Upload an XLSX template to export XLSX with preserved formatting.")
    validation = validate_mapping(fresh, schema, mappings, confirmed=True)
    if not validation["valid"]:
        raise TemplateError(" ".join(validation["errors"]))
    fields = _schema_fields(schema)
    _export_rows(rows, fields)
    by_name = {field["name"]: field for field in fields}
    columns = fresh["columns"]
    if output_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow([column["name"] for column in columns])
        for row in rows:
            values = []
            for column in columns:
                source = mappings[column["name"]]
                value = row.get(source, "") if source is not None else ""
                if value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")):
                    numeric = _numeric_value(value, by_name[source], source == fields[0]["name"]) if source is not None else value
                    if isinstance(numeric, str):
                        raise TemplateError("CSV cannot safely preserve formula-like text. Export XLSX for values beginning with =, +, -, or @.")
                values.append(value)
            writer.writerow(values)
        return output.getvalue().encode("utf-8-sig")
    workbook = _load_xlsx(data)
    try:
        worksheet = workbook[fresh["sheet"]]
        for other in list(workbook.worksheets):
            if other is not worksheet:
                workbook.remove(other)
        workbook.active = 0
        workbook.defined_names.clear()
        if hasattr(workbook, "custom_doc_props"):
            workbook.custom_doc_props.props = []
        for key in workbook.properties.__elements__:
            if key not in {"created", "modified"}:
                setattr(workbook.properties, key, None)
        workbook.code_name = None
        worksheet.sheet_properties.codeName = None
        from openpyxl.worksheet.filters import AutoFilter
        from openpyxl.formatting.formatting import ConditionalFormattingList
        from openpyxl.styles import PatternFill
        worksheet.auto_filter = AutoFilter()
        worksheet.conditional_formatting = ConditionalFormattingList()
        worksheet.row_dimensions[fresh["headerRow"]].hidden = False
        worksheet.row_dimensions[fresh["headerRow"]].height = max(24, worksheet.row_dimensions[fresh["headerRow"]].height or 24)
        for dimension in worksheet.column_dimensions.values():
            dimension.hidden = False
            dimension.collapsed = False
            if dimension.width is not None and dimension.width < 8:
                dimension.width = 12
        from openpyxl.cell.cell import MergedCell
        for cell in worksheet._cells.values():
            if isinstance(cell, MergedCell):
                continue
            cell.comment = None
            cell.hyperlink = None
        from copy import copy
        from openpyxl.comments import Comment
        style_row = fresh["headerRow"] + 1
        # Capture this before sizing the first exported row. Its content must
        # not make every later row inherit that row's new display height.
        template_row_height = worksheet.row_dimensions[style_row].height or 24
        for row_index, row in enumerate(rows, start=style_row):
            worksheet.row_dimensions[row_index].hidden = False
            worksheet.row_dimensions[row_index].collapsed = False
            height = max(24, template_row_height, worksheet.row_dimensions[row_index].height or 24)
            for column in columns:
                source = mappings[column["name"]]
                value = row.get(source, "") if source is not None else ""
                cell = worksheet.cell(row_index, column["index"] + 1)
                if row_index != style_row:
                    cell._style = copy(worksheet.cell(style_row, column["index"] + 1)._style)
                converted = _numeric_value(value, by_name[source], source == fields[0]["name"]) if source is not None else ""
                cell.value = converted
                if isinstance(converted, str):
                    cell.data_type = "s"
                    cell.number_format = "@"
                else:
                    cell.number_format = "General"
                font = copy(cell.font)
                font.color = "243A43"
                cell.font = font
                cell.fill = PatternFill("solid", fgColor="FFFFFF")
                alignment = copy(cell.alignment)
                alignment.wrap_text = True
                cell.alignment = alignment
                required_height = _display_height(worksheet, cell)
                height = max(height, required_height)
                if required_height > MAX_EXCEL_ROW_HEIGHT:
                    cell.comment = Comment(
                        "Display is limited to Excel's maximum row height (409.5 points). "
                        "The full cell value is preserved. Select the cell to review all text in the formula bar.",
                        "Formbridge",
                    )
            worksheet.row_dimensions[row_index].height = min(MAX_EXCEL_ROW_HEIGHT, height)
        output = io.BytesIO()
        workbook.save(output)
        return _without_personal_properties(output.getvalue())
    finally:
        workbook.close()
