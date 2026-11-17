"""Bounded, local-only document extraction and deterministic form suggestions.

The returned values are *suggestions*: callers must require human review before
export. No document bytes or OCR text leave this process or local OCR subprocess.
Regions use a top-left origin and values normalized to the page dimensions.
"""

from __future__ import annotations

import csv
import hashlib
from decimal import Decimal, InvalidOperation
import ctypes
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from neurology_profile import is_profile, extract as extract_neurology, applicable_fields
from limits import MAX_FIELDS, MAX_SCHEMA_BYTES, MAX_PAGES, MAX_RENDER_PIXELS, MAX_ASSET_BYTES

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

MAX_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_DIMENSION = 12_000
MAX_TEXT = 500_000
MAX_WORDS = 50_000
MAX_PDF_OBJECTS = 50_000
MAX_REGION_RETRIES = 8
OCR_TIMEOUT = 45
_OCR_LAST_OPERATIONAL: bool | None = None


class DocumentError(ValueError):
    """An upload cannot be processed within the supported safety limits."""


def _tesseract_path() -> str | None:
    override = os.environ.get("FORMBRIDGE_TESSERACT")
    if override:
        candidate = Path(override)
        if (
            not candidate.is_absolute()
            or candidate.name.casefold() not in {"tesseract", "tesseract.exe"}
            or not candidate.is_file()
            or not os.access(candidate, os.X_OK)
        ):
            return None
        return str(candidate.resolve())
    return shutil.which("tesseract")


def _vision_available() -> bool:
    binary = Path(__file__).with_name("native_ocr")
    return (
        sys.platform == "darwin"
        and ((binary.is_file() and os.access(binary, os.X_OK))
             or (bool(shutil.which("swift"))
                 and Path(__file__).with_name("native_ocr.swift").is_file()))
    )


def capabilities() -> dict[str, Any]:
    """Describe detected local capabilities without starting or downloading OCR."""
    tesseract = _tesseract_path()
    vision = _vision_available()
    return {
        "pdf": pdfium is not None and PdfReader is not None,
        "ocr": bool(tesseract or vision),
        "ocrEngine": "tesseract" if tesseract else "apple-vision" if vision else None,
        "ocrDetected": bool(tesseract or vision),
        "ocrOperational": _OCR_LAST_OPERATIONAL,
        "ocrStatus": "verified" if _OCR_LAST_OPERATIONAL is True else "last-attempt-failed" if _OCR_LAST_OPERATIONAL is False else "detected-not-verified" if tesseract or vision else "unavailable",
        "ocrLanguages": ["en"],
        "platform": sys.platform,
        "localOnly": True,
        "limits": {"maxBytes": MAX_BYTES, "maxPages": MAX_PAGES, "maxPixelsPerPage": MAX_PIXELS},
        "supportedTypes": ["pdf", "png", "jpeg", "tiff", "webp", "bmp", "txt"],
    }


def _identify(data: bytes, filename: str) -> str:
    if not isinstance(data, bytes) or not data:
        raise DocumentError("The uploaded document is empty.")
    if len(data) > MAX_BYTES:
        raise DocumentError("Documents must be 12 MB or smaller.")
    suffix = Path(filename).suffix.casefold()
    if data.startswith(b"%PDF-"):
        kind = "pdf"
        allowed = {".pdf"}
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind, allowed = "image", {".png"}
    elif data.startswith(b"\xff\xd8\xff"):
        kind, allowed = "image", {".jpg", ".jpeg"}
    elif data.startswith((b"II*\x00", b"MM\x00*")):
        kind, allowed = "image", {".tif", ".tiff"}
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        kind, allowed = "image", {".webp"}
    elif data.startswith(b"BM"):
        kind, allowed = "image", {".bmp"}
    elif suffix == ".txt":
        try:
            value = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentError("Text uploads must use UTF-8 encoding.") from exc
        if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in value):
            raise DocumentError("This file contains binary data, not supported plain text.")
        if len(value) > MAX_TEXT:
            raise DocumentError("Text documents must contain no more than 500,000 characters.")
        return "text"
    else:
        raise DocumentError("Use a PDF, PNG, JPEG, TIFF, WebP, BMP, or UTF-8 TXT document.")
    if suffix not in allowed:
        raise DocumentError("The file extension does not match its document signature.")
    return kind


def _region(x: float, y: float, width: float, height: float) -> dict[str, float]:
    x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
    width, height = max(0.0, min(1.0 - x, width)), max(0.0, min(1.0 - y, height))
    return {"x": round(x, 6), "y": round(y, 6), "width": round(width, 6), "height": round(height, 6)}


def _union(words: list[dict[str, Any]]) -> dict[str, float]:
    left = min(word["x"] for word in words)
    top = min(word["y"] for word in words)
    right = max(word["x"] + word["width"] for word in words)
    bottom = max(word["y"] + word["height"] for word in words)
    return _region(left, top, right - left, bottom - top)


def _line(words: list[dict[str, Any]], text: str | None = None) -> dict[str, Any]:
    return {"text": text if text is not None else " ".join(w["text"] for w in words), "words": words, **_union(words)}


def _pdf_lines(page: Any, pixel_width: int, pixel_height: int) -> list[dict[str, Any]]:
    """Use PDFium's page-to-device transform, including crop/rotation, for boxes."""
    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()
        if count > MAX_TEXT:
            raise DocumentError("A PDF page exceeds the 500,000 character limit.")
        words: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []
        chars: list[str] = []
        boxes: list[dict[str, Any]] = []

        def flush_word() -> None:
            if chars:
                text = "".join(chars).strip()
                if text and boxes:
                    words.append({"text": text, **_union(boxes)})
                chars.clear()
                boxes.clear()

        def flush_line() -> None:
            flush_word()
            if words:
                lines.append(_line(list(words)))
                words.clear()

        for index in range(count):
            char = textpage.get_text_range(index, 1)
            if not char:
                continue
            if char in "\r\n":
                flush_line()
                continue
            if char.isspace():
                flush_word()
                continue
            if ord(char[0]) < 32:
                continue
            left, bottom, right, top = textpage.get_charbox(index)
            corners = []
            for px, py in ((left, bottom), (right, top), (left, top), (right, bottom)):
                dx, dy = ctypes.c_int(), ctypes.c_int()
                pdfium.raw.FPDF_PageToDevice(page, 0, 0, pixel_width, pixel_height, 0, px, py, ctypes.byref(dx), ctypes.byref(dy))
                corners.append((dx.value / pixel_width, dy.value / pixel_height))
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            box = _region(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            chars.append(char)
            boxes.append(box)
        flush_line()
        return lines
    finally:
        textpage.close()


def _tesseract_lines(path: Path, width: int, height: int, executable: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [executable, str(path), "stdout", "--psm", "6", "tsv"],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=OCR_TIMEOUT, check=False,
    )
    if result.returncode:
        raise DocumentError("Local Tesseract OCR could not read this page.")
    if len(result.stdout) > 12_000_000:
        raise DocumentError("Local OCR output exceeds the processing limit.")
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    word_count = 0
    for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", "replace")), delimiter="\t"):
        value = (row.get("text") or "").strip()
        if not value or row.get("level") != "5":
            continue
        try:
            x, y, w, h = (float(row[key]) for key in ("left", "top", "width", "height"))
        except (ValueError, TypeError, KeyError):
            continue
        if not all(math.isfinite(n) for n in (x, y, w, h)) or w <= 0 or h <= 0:
            continue
        key = tuple(row.get(k, "") for k in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append({"text": value, **_region(x / width, y / height, w / width, h / height)})
        word_count += 1
        if word_count > MAX_WORDS:
            raise DocumentError("Local OCR produced too many words on this page.")
    return [_line(words) for words in groups.values() if words]


def _vision_lines(path: Path) -> list[dict[str, Any]]:
    import json

    binary = Path(__file__).with_name("native_ocr")
    if binary.is_file() and os.access(binary, os.X_OK):
        command = [str(binary), str(path)]
    else:
        cache = path.parent.parent / ".swift-module-cache"
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        command = [shutil.which("swift") or "/usr/bin/swift", "-module-cache-path", str(cache), str(Path(__file__).with_name("native_ocr.swift")), str(path)]
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=OCR_TIMEOUT, check=False,
    )
    if result.returncode:
        raise DocumentError("Built-in Apple Vision OCR could not read this page.")
    if len(result.stdout) > 12_000_000:
        raise DocumentError("Local OCR output exceeds the processing limit.")
    try:
        decoded = json.loads(result.stdout)
        observations = decoded["lines"]
    except (ValueError, KeyError, TypeError) as exc:
        raise DocumentError("Built-in Apple Vision returned an invalid OCR result.") from exc
    lines = []
    word_count = 0
    for entry in observations:
        words = []
        for item in entry.get("words", []):
            try:
                coords = [float(item[key]) for key in ("x", "y", "width", "height")]
                text = str(item["text"]).strip()
            except (ValueError, TypeError, KeyError):
                continue
            if text and all(math.isfinite(n) for n in coords):
                words.append({"text": text, **_region(*coords)})
                word_count += 1
        if word_count > MAX_WORDS:
            raise DocumentError("Local OCR produced too many words on this page.")
        if words:
            lines.append(_line(words, str(entry.get("text", ""))))
    return lines


def _ocr(path: Path, width: int, height: int) -> tuple[list[dict[str, Any]], str, str | None]:
    global _OCR_LAST_OPERATIONAL
    executable = _tesseract_path()
    method = "tesseract" if executable else "apple-vision" if _vision_available() else "unavailable"
    if method == "unavailable":
        _OCR_LAST_OPERATIONAL = False
        return [], method, "Local OCR is unavailable. Install Tesseract locally to read scanned pages; manual entry remains available."
    try:
        lines = _tesseract_lines(path, width, height, executable) if executable else _vision_lines(path)
        _OCR_LAST_OPERATIONAL = True
        return lines, method, None if lines else "Local OCR found no readable text on this page."
    except subprocess.TimeoutExpired:
        _OCR_LAST_OPERATIONAL = False
        return [], method, "Local OCR exceeded its 45-second page limit. Enter fields manually or upload a smaller page."
    except (OSError, DocumentError) as exc:
        _OCR_LAST_OPERATIONAL = False
        return [], method, str(exc) if isinstance(exc, DocumentError) else "The local OCR program could not be started."


def _make_pdf_pages(data: bytes, folder: Path) -> list[dict[str, Any]]:
    if pdfium is None or PdfReader is None:
        raise DocumentError("PDF support is unavailable. Install the documented local Python dependencies.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise DocumentError("Encrypted PDFs are unsupported. Upload an unencrypted research copy.")
        if len(reader.pages) > MAX_PAGES:
            raise DocumentError(f"Documents may contain at most {MAX_PAGES} pages.")
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("The PDF is damaged or could not be opened.") from exc
    pages = []
    render_pixels = 0
    try:
        document = pdfium.PdfDocument(data)
        try:
            if not 1 <= len(document) <= MAX_PAGES:
                raise DocumentError(f"Documents must contain between 1 and {MAX_PAGES} pages.")
            for index in range(len(document)):
                page = document[index]
                try:
                    pw, ph = page.get_size()
                    if not all(math.isfinite(v) and v > 0 for v in (pw, ph)) or max(pw, ph) > 14400:
                        raise DocumentError("A PDF page has unsupported dimensions.")
                    scale = min(2.0, math.sqrt(MAX_PIXELS / (pw * ph)) * 0.99, MAX_DIMENSION / max(pw, ph))
                    render_pixels += math.ceil(pw * scale) * math.ceil(ph * scale)
                    if render_pixels > MAX_RENDER_PIXELS:
                        raise DocumentError("Document rendering exceeds the aggregate 120-megapixel limit.")
                    bitmap = page.render(scale=scale, may_draw_forms=False)
                    try:
                        rendered = bitmap.to_pil().convert("RGB")
                        width, height = rendered.size
                        if width * height > MAX_PIXELS or max(width, height) > MAX_DIMENSION:
                            raise DocumentError("A rendered PDF page exceeds the image limit.")
                        path = folder / f"page-{index + 1}.png"
                        rendered.save(path, "PNG")
                        os.chmod(path, 0o600)
                        rendered.close()
                        _check_asset_bytes(folder)
                    finally:
                        bitmap.close()
                    # PDFium exposes images nested in Form XObjects without
                    # decoding them again. Bound both recursion and enumeration.
                    has_raster = False
                    for object_count, obj in enumerate(page.get_objects(max_depth=15), 1):
                        if object_count > MAX_PDF_OBJECTS:
                            raise DocumentError("A PDF page exceeds the 50,000 object processing limit.")
                        if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                            has_raster = True
                            break
                    lines = _pdf_lines(page, width, height)
                    pages.append({"page": index + 1, "width": width, "height": height, "path": path, "lines": lines, "method": "pdf-text" if lines else None, "hasRaster": has_raster})
                finally:
                    page.close()
        finally:
            document.close()
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("The PDF could not be rendered safely.") from exc
    return pages


def _make_image_pages(data: bytes, folder: Path) -> list[dict[str, Any]]:
    pages = []
    render_pixels = 0
    try:
        with Image.open(io.BytesIO(data)) as source:
            count = getattr(source, "n_frames", 1)
            if not 1 <= count <= MAX_PAGES:
                raise DocumentError(f"Image documents may contain at most {MAX_PAGES} frames.")
            for index in range(count):
                source.seek(index)
                width, height = source.size
                if width * height > MAX_PIXELS or max(width, height) > MAX_DIMENSION:
                    raise DocumentError("Images must be at most 20 megapixels and 12,000 pixels per side.")
                render_pixels += width * height
                if render_pixels > MAX_RENDER_PIXELS:
                    raise DocumentError("Document rendering exceeds the aggregate 120-megapixel limit.")
                frame = ImageOps.exif_transpose(source).convert("RGB")
                width, height = frame.size
                path = folder / f"page-{index + 1}.png"
                frame.save(path, "PNG")
                os.chmod(path, 0o600)
                frame.close()
                _check_asset_bytes(folder)
                pages.append({"page": index + 1, "width": width, "height": height, "path": path, "lines": [], "method": None})
    except DocumentError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, EOFError, Image.DecompressionBombError) as exc:
        raise DocumentError("The image is damaged or could not be decoded safely.") from exc
    return pages


def _check_asset_bytes(folder):
    if sum(path.stat().st_size for path in folder.glob("*.png")) > MAX_ASSET_BYTES:
        raise DocumentError("Rendered page assets exceed the aggregate 128 MiB limit.")


def _labels(field: dict[str, Any]) -> list[str]:
    labels = [field.get("label", ""), field.get("name", "").replace("_", " ")]
    aliases = field.get("aliases", [])
    if isinstance(aliases, list):
        labels.extend(aliases[:30])
    return sorted({str(item).strip() for item in labels if isinstance(item, str) and 0 < len(item.strip()) <= 200}, key=len, reverse=True)


def _label_value(text: str, labels: list[str], separator_only: bool = False) -> str | None:
    """Match escaped literal labels at the start, never a user-supplied regex."""
    for label in labels:
        # Label punctuation/spacing may vary, but matching is never fuzzy.
        parts = re.split(r"[\s_]+", label.casefold())
        literal = r"[\s_]+".join(re.escape(part) for part in parts)
        separator = r"\s*[:=]\s*" if separator_only else r"(?:\s*[:=]\s*|\s+|$)"
        match = re.match(r"^\s*" + literal + separator + r"(.*)$", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _valid_region(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    try:
        page = int(value.get("page", 1))
        x, y, w, h = (float(value[key]) for key in ("x", "y", "width", "height"))
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    if not all(math.isfinite(n) for n in (x, y, w, h)) or not (1 <= page <= MAX_PAGES and 0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x + 1e-9 and 0 < h <= 1 - y + 1e-9):
        return None
    return {"page": page, "x": x, "y": y, "width": w, "height": h}


def _in_region(word: dict[str, Any], region: dict[str, Any]) -> bool:
    center_x, center_y = word["x"] + word["width"] / 2, word["y"] + word["height"] / 2
    return region["x"] <= center_x <= region["x"] + region["width"] and region["y"] <= center_y <= region["y"] + region["height"]


def _retry_empty_regions(schema: list, pages: list[dict[str, Any]], folder: Path, rendered_pixels=None) -> tuple[int, int, list[str]]:
    """Retry at most eight empty boxes; isolated digits can evade full-page OCR."""
    attempts, recovered = 0, 0
    render_pixels = rendered_pixels if rendered_pixels is not None else sum(page["width"] * page["height"] for page in pages)
    issues = []
    for field in schema:
        if attempts >= MAX_REGION_RETRIES:
            break
        if not isinstance(field, dict):
            continue
        region = _valid_region(field.get("region"))
        if not region:
            continue
        page = next((item for item in pages if item["page"] == region["page"]), None)
        if not page or page["method"] not in {"tesseract", "apple-vision"} or not page["lines"]:
            continue
        if any(_in_region(word, region) for line in page["lines"] for word in line["words"]):
            continue
        attempts += 1
        path = folder / f"region-ocr-{attempts}.png"
        try:
            with Image.open(page["path"]) as image:
                x0, y0 = math.floor(region["x"] * image.width), math.floor(region["y"] * image.height)
                x1, y1 = math.ceil((region["x"] + region["width"]) * image.width), math.ceil((region["y"] + region["height"]) * image.height)
                crop = image.crop((x0, y0, x1, y1)).convert("RGB")
            scale = min(3.0, math.sqrt(2_000_000 / max(1, crop.width * crop.height)))
            resized_width, resized_height = max(1, round(crop.width * scale)), max(1, round(crop.height * scale))
            sx, sy = resized_width / crop.width, resized_height / crop.height
            enlarged = crop.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            crop.close()
            border = 80
            padded = ImageOps.expand(enlarged, border=border, fill="white")
            enlarged.close()
            crop_width, crop_height = padded.size
            render_pixels += crop_width * crop_height
            if render_pixels > MAX_RENDER_PIXELS:
                padded.close()
                raise DocumentError("Document rendering exceeds the aggregate 120-megapixel limit.")
            padded.save(path, "PNG")
            os.chmod(path, 0o600)
            padded.close()
            _check_asset_bytes(folder)
            lines, method, issue = _ocr(path, crop_width, crop_height)
            if issue:
                issues.append(f"Field region {field.get('name', '')}: {issue}")
            new_lines = []
            for line in lines:
                words = []
                for word in line["words"]:
                    box = _region(
                        (x0 + (word["x"] * crop_width - border) / sx) / page["width"],
                        (y0 + (word["y"] * crop_height - border) / sy) / page["height"],
                        word["width"] * crop_width / sx / page["width"],
                        word["height"] * crop_height / sy / page["height"],
                    )
                    mapped_word = {"text": word["text"], **box}
                    if _in_region(mapped_word, region):
                        words.append(mapped_word)
                if words:
                    new_lines.append(_line(words))
            if new_lines:
                page["lines"].extend(new_lines)
                recovered += 1
        except (OSError, ValueError):
            issues.append(f"Field region {field.get('name', '')}: The local OCR region retry could not be rendered.")
        finally:
            path.unlink(missing_ok=True)
    return attempts, recovered, issues


def _choice_pairs(field: dict[str, Any]) -> list[tuple[str, str]]:
    choices = field.get("choices", [])
    if isinstance(choices, dict):
        return [(str(code), str(label)) for code, label in choices.items()]
    result = []
    if isinstance(choices, list):
        for item in choices[:500]:
            if isinstance(item, dict):
                code = item.get("value", item.get("code", ""))
                label = item.get("label", code)
                result.append((str(code), str(label)))
            elif isinstance(item, str):
                result.append((item, item))
    return result


def _adjacent_value(label_line: dict[str, Any], page: dict[str, Any], all_labels: list[list[str]]) -> dict[str, Any] | None:
    """Pair an exact, empty label with the nearest distinct text on its row."""
    label_right = label_line["x"] + label_line["width"]
    label_center = label_line["y"] + label_line["height"] / 2
    neighbors = []
    for other in page["lines"]:
        gap = other["x"] - label_right
        if other is label_line or gap < -0.002 or gap > 0.6:
            continue
        center = other["y"] + other["height"] / 2
        if abs(center - label_center) > max(label_line["height"], other["height"]) * 0.6:
            continue
        # A different configured field label is never consumed as a value.
        if any(_label_value(other["text"], labels) is not None for labels in all_labels):
            continue
        neighbors.append(other)
    return min(neighbors, key=lambda line: line["x"]) if neighbors else None


def _validate_value(raw: str, field: dict[str, Any]) -> tuple[str, str | None]:
    value = raw.strip()
    if len(value) > 4000:
        return "", "The extracted value exceeds 4,000 characters and needs manual review."
    if not value:
        return "", None
    kind = str(field.get("type", "text")).casefold()
    choices = _choice_pairs(field)
    if choices:
        matches = {code for code, label in choices if value.casefold() in {code.casefold(), label.casefold()}}
        if len(matches) == 1:
            return matches.pop(), None
        return "", "The extracted choice does not uniquely match a configured code or label."
    if kind in {"number", "integer", "float", "decimal", "numeric"}:
        grammar = r"-?[0-9]+" if kind == "integer" else r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
        if not re.fullmatch(grammar, value):
            return "", "The extracted value is not a valid number."
        try:
            number = Decimal(value)
        except InvalidOperation:
            return "", "The extracted value is not valid for this numeric field."
        if not number.is_finite():
            return "", "The extracted value is not valid for this numeric field."
        for limit, comparator in (("min", lambda x, y: x < y), ("max", lambda x, y: x > y)):
            try:
                bound = Decimal(str(field[limit]))
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
            if bound.is_finite() and comparator(number, bound):
                return "", f"The extracted value is outside the configured {limit} limit."
    elif kind in {"date", "date_ymd"}:
        from datetime import date
        try:
            if field.get("sourceDateFormat") == "mdy" and re.fullmatch(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", value):
                month, day, year = map(int, value.split("/"))
                value = date(year, month, day).isoformat()
            elif not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError("Non-ISO date")
            date.fromisoformat(value)
        except ValueError:
            return "", "Dates must use YYYY-MM-DD; the source value needs manual review."
    elif kind in {"yesno", "boolean", "bool"}:
        boolean_values = {"yes": "1", "true": "1", "1": "1", "no": "0", "false": "0", "0": "0"}
        if value.casefold() not in boolean_values:
            return "", "The extracted value does not exactly match Yes/No or 1/0."
        return boolean_values[value.casefold()], None
    return value, None


def _map_fields(schema: list[dict[str, Any]], pages: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    values: dict[str, str] = {}
    evidence: dict[str, Any] = {}
    issues: list[str] = []
    all_labels = [_labels(field) for field in schema if isinstance(field, dict)]
    for field in schema:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name", ""))
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,99}", name):
            continue
        values[name] = ""
        if field.get("pattern"):
            issues.append(f"{name}: Custom regular expressions are not executed; use a label or page region.")
        requested_region = field.get("region")
        region = _valid_region(requested_region)
        if requested_region and region is None:
            issues.append(f"{name}: The configured region is invalid; mapping was skipped.")
            continue
        candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        explicit_candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for page in pages:
            if region and page["page"] != region["page"]:
                continue
            if region:
                selected = []
                selected_text = []
                for line in page["lines"]:
                    words = [word for word in line["words"] if _in_region(word, region)]
                    if words:
                        selected.extend(words)
                        selected_text.append(" ".join(word["text"] for word in words))
                if selected:
                    joined = "\n".join(selected_text).strip()
                    # A region can contain only a value, or an entire labeled line.
                    stripped = _label_value(joined, _labels(field))
                    candidates.append((stripped if stripped is not None else joined, page, _union(selected)))
            else:
                for line in page["lines"]:
                    candidate = _label_value(line["text"], _labels(field))
                    explicit = _label_value(line["text"], _labels(field), separator_only=True)
                    if candidate is not None and candidate:
                        entry = (candidate, page, {key: line[key] for key in ("x", "y", "width", "height")})
                        candidates.append(entry)
                        if explicit is not None:
                            explicit_candidates.append(entry)
                    elif candidate == "":
                        neighbor = _adjacent_value(line, page, all_labels)
                        if neighbor:
                            entry = (neighbor["text"], page, _union(line["words"] + neighbor["words"]))
                            candidates.append(entry)
                            if explicit is not None:
                                explicit_candidates.append(entry)
        if explicit_candidates:
            # Prefer explicit separators within a source, but do not discard a
            # disagreement merely because another extraction lost punctuation.
            explicit_methods = {candidate[1]["method"] for candidate in explicit_candidates}
            explicit_ids = {id(candidate) for candidate in explicit_candidates}
            candidates = [candidate for candidate in candidates if id(candidate) in explicit_ids or candidate[1]["method"] not in explicit_methods]
        if not candidates:
            if field.get("required"):
                issues.append(f"{name}: Required field was not found; enter or verify it manually.")
            continue
        unique = {candidate[0].strip() for candidate in candidates}
        if len(unique) > 1:
            methods = ", ".join(sorted({candidate[1]["method"] for candidate in candidates}))
            issues.append(f"{name}: Multiple different source values were found ({methods}); no value was selected.")
            continue
        raw, page, box = candidates[0]
        value, problem = _validate_value(raw, field)
        evidence[name] = {"text": raw, "page": page["page"], "region": box, "method": page["method"], "mapping": "region" if region else "label"}
        if problem:
            issues.append(f"{name}: {problem}")
        else:
            values[name] = value
    return values, evidence, issues


def process_document(data: bytes, filename: str, schema: list, asset_dir: Path, record_id: str) -> dict[str, Any]:
    """Render and extract an upload into a new local asset directory.

    ``asset_dir`` is the root containing per-record folders. A record directory
    must not already exist, preventing accidental overwrite of prior evidence.
    The caller owns cleanup if processing raises ``DocumentError``.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", record_id):
        raise DocumentError("Invalid local record identifier.")
    if not isinstance(schema, list) or len(schema) > MAX_FIELDS:
        raise DocumentError(f"The form schema must contain at most {MAX_FIELDS} fields.")
    if len(json.dumps(schema, ensure_ascii=True).encode()) > MAX_SCHEMA_BYTES:
        raise DocumentError("The form schema must be at most 1 MiB.")
    kind = _identify(data, filename)
    root = Path(asset_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = root / record_id
    folder.mkdir(mode=0o700, exist_ok=False)
    issues: list[str] = []
    pipeline = [{"stage": "Validate upload", "status": "complete", "detail": "File signature, size, and supported document type checked locally."}]
    if kind == "text":
        text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        source_lines = text.splitlines() or [""]
        for index, value in enumerate(source_lines):
            words = []
            for match in re.finditer(r"\S+", value):
                words.append({"text": match.group(), **_region(match.start() / max(len(value), 1), index / len(source_lines), len(match.group()) / max(len(value), 1), 1 / len(source_lines))})
            if words:
                lines.append(_line(words, value))
        pages = [{"page": 1, "lines": lines, "method": "plain-text", "width": 0, "height": 0}]
        pipeline.append({"stage": "Read document", "status": "complete", "detail": "UTF-8 text read locally; no document preview is generated."})
    else:
        pages = _make_pdf_pages(data, folder) if kind == "pdf" else _make_image_pages(data, folder)
        pipeline.append({"stage": "Render pages", "status": "complete", "detail": f"Rendered {len(pages)} page(s) into bounded local PNG previews."})
        for page in pages:
            if page["method"] is None:
                lines, method, issue = _ocr(page["path"], page["width"], page["height"])
                page["lines"], page["method"] = lines, method
                if issue:
                    issues.append(f"Page {page['page']}: {issue}")
        # Native text can cover only a heading while answers remain in a raster.
        # Keep OCR as a distinct mapping layer: concatenating both layers would
        # duplicate region answers and lose the method behind each suggestion.
        mapping_pages = list(pages)
        initial_values, _, _ = extract_neurology(pages, hashlib.sha256(data).hexdigest()) if is_profile(schema) else _map_fields(schema, pages)
        unresolved = any(not initial_values.get(name) for name in applicable_fields(schema, initial_values))
        fallback_pages = [page for page in pages if page["method"] == "pdf-text" and page.get("hasRaster")] if unresolved else []
        for page in fallback_pages:
            lines, method, issue = _ocr(page["path"], page["width"], page["height"])
            mapping_pages.append({**page, "lines": lines, "method": method})
            if issue:
                issues.append(f"Page {page['page']} mixed-content OCR fallback: {issue}")
        if fallback_pages:
            pipeline.append({"stage": "Read mixed-content pages", "status": "complete" if any(page["lines"] for page in mapping_pages[len(pages):]) else "needs-review", "detail": f"Retried {len(fallback_pages)} native-text page(s) with local OCR because schema fields remained unresolved; native and OCR candidates are compared independently."})
        methods = sorted({page["method"] for page in mapping_pages})
        pipeline.append({"stage": "Extract text", "status": "complete" if any(p["lines"] for p in mapping_pages) else "needs-review", "detail": "Local extraction method(s): " + ", ".join(methods) + "."})
        attempts, recovered, retry_issues = _retry_empty_regions(schema, [page for page in mapping_pages if page["method"] in {"tesseract", "apple-vision"}], folder,
                                                              sum(page["width"] * page["height"] for page in pages))
        issues.extend(retry_issues)
        if attempts:
            pipeline.append({"stage": "Retry field regions", "status": "complete" if recovered else "needs-review", "detail": f"Retried {attempts} empty configured region(s) with local OCR; recovered text in {recovered}."})
    if kind == "text":
        mapping_pages = pages
    source_pages = []
    for page in pages:
        native_text = {line["text"].strip() for line in page["lines"]}
        lines = [line["text"] for line in page["lines"]]
        for layer in mapping_pages[len(pages):]:
            if layer["page"] == page["page"]:
                lines.extend(line["text"] for line in layer["lines"] if line["text"].strip() not in native_text)
        source_pages.append("\n".join(lines))
    source_text = "\n\n".join(source_pages)
    if len(source_text) > MAX_TEXT:
        raise DocumentError("Extracted text exceeds the 500,000 character document limit.")
    values, evidence, mapping_issues = extract_neurology(mapping_pages, hashlib.sha256(data).hexdigest()) if is_profile(schema) else _map_fields(schema, mapping_pages)
    values = {f["name"]: values.get(f["name"], "") for f in schema}
    if is_profile(schema):
        for field in schema:
            value, problem = _validate_value(values[field["name"]], field)
            values[field["name"]] = value
            if problem:
                mapping_issues.append(f"{field['name']}: {problem}")
    issues.extend(mapping_issues)
    populated = sum(bool(value) for value in values.values())
    active_count = len(applicable_fields(schema, values))
    pipeline.append({"stage": "Match form fields", "status": "complete" if populated else "needs-review", "detail": f"Suggested {populated} of {active_count} applicable fields using literal labels and source geometry. Human review is required."})
    previews = [{"page": page["page"], "url": f"/api/assets/{record_id}/page-{page['page']}.png", "width": page["width"], "height": page["height"]} for page in pages if page.get("path")]
    result = {"sourceText": source_text, "values": values, "pages": previews, "previewUrl": previews[0]["url"] if previews else None, "evidence": evidence, "pipeline": pipeline, "issues": issues}
    if is_profile(schema):
        result["applicableFields"] = sorted(applicable_fields(schema, values))
        result["sourceInstrumentFamily"] = values.get("instrument_family", "")
        result["profileBlockingIssues"] = [issue for issue in mapping_issues if issue.startswith(("patient_name: Repeated", "patient_dob: Repeated", "patient_mrn: Repeated", "patient_dob: Invalid"))]
    return result
