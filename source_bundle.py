"""Create an ordered, local PDF bundle for one operator-confirmed study record."""
from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import logging
import math
import re
import unicodedata

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, StreamObject
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from limits import MAX_BUNDLE_DOCUMENTS as MAX_DOCUMENTS, MAX_PAGES

MAX_INPUT_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024 * 1024
MAX_REQUEST_BYTES = ((MAX_INPUT_BYTES + 2) // 3) * 4 + 64 * 1024

_RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
_PDF_SIGNATURE = re.compile(rb"%PDF-[12]\.[0-9](?:\r|\n|\s)")
_FLATTEN_MESSAGE = "Export each form as a flattened or scanned PDF before combining it. Interactive fields and visual annotations are not supported."
_EXCLUDED_KEYS = (
    "/Annots", "/A", "/AA", "/OpenAction", "/JS", "/JavaScript",
    "/EmbeddedFiles", "/EF", "/AF", "/AcroForm", "/XFA", "/Names",
    "/RichMediaContent", "/RichMediaSettings", "/PresSteps", "/Metadata",
)


class BundleError(ValueError):
    """A bounded, operator-readable source bundle validation error."""


@dataclass(frozen=True)
class _Document:
    filename: str
    data: bytes
    reader: PdfReader
    pages: int


class _OutputBuffer(io.BytesIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_OUTPUT_BYTES:
            raise BundleError("The combined PDF exceeds the 12 MiB limit. Use fewer or smaller source PDFs.")
        return super().write(value)


@contextmanager
def _quiet_pdf():
    logger = logging.getLogger("pypdf")
    handlers, propagate, level = logger.handlers[:], logger.propagate, logger.level
    logger.handlers = [logging.NullHandler()]
    logger.propagate = False
    logger.setLevel(logging.CRITICAL + 1)
    try:
        yield
    finally:
        logger.handlers, logger.propagate = handlers, propagate
        logger.setLevel(level)


def _filename(value) -> str:
    if (
        not isinstance(value, str) or not 1 <= len(value) <= 200
        or any(character in value for character in ("/", "\\", ":"))
        or any(unicodedata.category(character).startswith("C") for character in value)
        or not value.lower().endswith(".pdf")
        or value in {".", ".."}
    ):
        raise BundleError("Each source needs a PDF basename of at most 200 characters without paths or control characters.")
    return value


def _source_bytes(value) -> bytes:
    if not isinstance(value, str) or not value or len(value) > ((MAX_INPUT_BYTES + 2) // 3) * 4:
        raise BundleError("Source PDFs must contain valid base64 data within the 12 MiB input limit.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise BundleError("Source PDFs must contain valid base64 data.") from None
    if base64.b64encode(decoded).decode("ascii") != value:
        raise BundleError("Source PDFs must contain canonical base64 data.")
    if not _PDF_SIGNATURE.match(decoded):
        raise BundleError("Each source must be a PDF with a valid PDF signature.")
    return decoded


def _read_pdf(filename: str, data: bytes) -> _Document:
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise BundleError("Encrypted PDFs are not supported. Export an unencrypted, flattened PDF first.")
    root = reader.trailer["/Root"]
    if not isinstance(root, DictionaryObject):
        raise BundleError("A source PDF has an invalid document structure.")
    if "/AcroForm" in root:
        raise BundleError(_FLATTEN_MESSAGE)
    count = len(reader.pages)
    if not 1 <= count < MAX_PAGES:
        raise BundleError("The bundle supports at most 32 pages including its cover, and each source must have at least one page.")
    for page in reader.pages:
        if page.get("/Type") != "/Page":
            raise BundleError("A source PDF has an invalid page structure.")
        box = page.mediabox
        coordinates = [float(number) for number in box]
        if len(coordinates) != 4 or not all(math.isfinite(number) for number in coordinates) or box.width <= 0 or box.height <= 0:
            raise BundleError("A source PDF has an invalid page size.")
        rotation = page.get("/Rotate", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or rotation % 90:
            raise BundleError("A source PDF has an invalid page rotation.")
        contents = page.get("/Contents")
        if contents is not None:
            contents = contents.get_object()
            streams = contents if isinstance(contents, ArrayObject) else [contents]
            if not all(isinstance(stream.get_object(), StreamObject) for stream in streams):
                raise BundleError("A source PDF has an invalid page content structure.")
        annotations = page.get("/Annots")
        if annotations is not None:
            annotations = annotations.get_object()
            if not isinstance(annotations, ArrayObject):
                raise BundleError("A source PDF has an invalid annotation structure.")
            for annotation in annotations:
                annotation = annotation.get_object()
                if not isinstance(annotation, DictionaryObject):
                    raise BundleError("A source PDF has an invalid annotation structure.")
                if annotation.get("/Subtype") != "/Link":
                    raise BundleError(_FLATTEN_MESSAGE)
    return _Document(filename, data, reader, count)


def _wrap(value: str, width: float, size: float) -> list[str]:
    lines, line = [], ""
    for character in value:
        if line and stringWidth(line + character, "Helvetica", size) > width:
            lines.append(line)
            line = ""
        line += character
    if line:
        lines.append(line)
    return lines


def _cover(record_id: str, manifest: list[dict]) -> tuple[bytes, dict]:
    width, height = letter
    margin, font_size, line_height = 54, 8, 11
    entries = []
    for index, item in enumerate(manifest, 1):
        display_name = item["filename"].encode("ascii", "backslashreplace").decode("ascii")
        if len(display_name) > 88:
            suffix = f"... [sha256 {item['sha256'][:12]}]"
            display_name = display_name[:88 - len(suffix)] + suffix
        page_range = str(item["firstPage"]) if item["pages"] == 1 else f"{item['firstPage']}-{item['lastPage']}"
        entries.append(_wrap(f"{index}. Pages {page_range} | {display_name}", width - 2 * margin, font_size))
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height), invariant=1, pageCompression=1)
    pdf.setTitle("Operator-confirmed source bundle")
    pdf.setAuthor("")
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(margin, height - 48, "Source bundle for one study record")
    annotation = ["Study record ID entered by operator; confirm these forms belong to the same patient.", "No patient identity was inferred."]
    pdf.setFont("Helvetica", 10)
    for index, line in enumerate(line for sentence in annotation for line in _wrap(sentence, width - 2 * margin, 10)):
        pdf.drawString(margin, height - 76 - index * 14, line)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, height - 136, "Study record ID (operator-entered)")
    left, top, box_width, box_height = margin, 148, width - 2 * margin, 42
    pdf.rect(left, height - top - box_height, box_width, box_height, stroke=1, fill=0)
    id_font_size = min(18, 18 * (box_width - 20) / max(1, stringWidth(record_id, "Helvetica", 18)))
    pdf.setFont("Helvetica", id_font_size)
    pdf.drawString(left + 10, height - top - 27, record_id)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, height - 228, "Ordered source PDFs")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin, height - 244, "Filename previews may be shortened. Unicode uses escapes. Page ranges refer to this PDF.")
    pdf.drawString(margin, height - 255, "Full original filenames and checksums are in Patient bundle sources and the project manifest.")
    for row, lines in enumerate(entries):
        for index, line in enumerate(lines):
            pdf.drawString(margin, height - 278 - row * 28 - index * line_height, line)
    pdf.showPage()
    pdf.save()
    region = {"page": 1, "x": left / width, "y": top / height, "width": box_width / width, "height": box_height / height}
    return output.getvalue(), region


def make_bundle(payload) -> dict:
    """Validate an explicit record ID and ordered PDFs without writing any files."""
    if not isinstance(payload, dict) or set(payload) != {"recordId", "documents"}:
        raise BundleError("A source bundle requires only a study record ID and an ordered list of PDF documents.")
    record_id, requested = payload["recordId"], payload["documents"]
    if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
        raise BundleError("Enter a study record ID of 1-80 ASCII letters, digits, underscores, periods or hyphens, starting with a letter or digit.")
    if not isinstance(requested, list) or not 1 <= len(requested) <= MAX_DOCUMENTS:
        raise BundleError("Select between 1 and 16 source PDFs in the required order.")
    source_values, total_bytes = [], 0
    for item in requested:
        if not isinstance(item, dict) or set(item) != {"filename", "data"}:
            raise BundleError("Each source must contain only a PDF filename and base64 data.")
        filename, data = _filename(item["filename"]), _source_bytes(item["data"])
        total_bytes += len(data)
        if total_bytes > MAX_INPUT_BYTES:
            raise BundleError("The original source PDFs exceed the combined 12 MiB input limit.")
        source_values.append((filename, data))
    try:
        with _quiet_pdf():
            documents = [_read_pdf(filename, data) for filename, data in source_values]
            if 1 + sum(document.pages for document in documents) > MAX_PAGES:
                raise BundleError("The combined PDF exceeds 32 pages including its cover. Use fewer source pages.")
            manifest, first_page = [], 2
            for document in documents:
                manifest.append({"filename": document.filename, "sha256": hashlib.sha256(document.data).hexdigest(), "pages": document.pages, "firstPage": first_page, "lastPage": first_page + document.pages - 1})
                first_page += document.pages
            cover, region = _cover(record_id, manifest)
            writer = PdfWriter()
            writer.metadata = None
            writer.add_page(PdfReader(io.BytesIO(cover), strict=True).pages[0])
            for document in documents:
                for page in document.reader.pages:
                    writer.add_page(page, excluded_keys=_EXCLUDED_KEYS)
            output = _OutputBuffer()
            writer.write(output)
            combined = output.getvalue()
    except BundleError:
        raise
    except Exception:
        raise BundleError("A source PDF could not be processed safely. Export a valid, unencrypted, flattened PDF and try again.") from None
    return {
        "data": base64.b64encode(combined).decode("ascii"),
        "manifest": manifest,
        "identifierField": {"name": "record_id", "label": "Study record ID (operator-entered)", "type": "text", "required": True, "region": region},
    }
