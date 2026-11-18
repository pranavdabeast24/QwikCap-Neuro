"""Inventory one explicitly selected dataset split without extracting document text."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from pypdf import PdfReader


def inventory(split_root: Path):
    split_root = split_root.resolve(strict=True)
    result = {"format": "quickcap-dataset-inventory-v1", "content_read": "PDF structure only; no document text", "forms": [], "answer_keys": []}
    for folder in ("forms", "answer_keys"):
        directory = split_root / folder
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Each split needs regular forms and answer_keys directories")
        for path in sorted(directory.glob("*.pdf")):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Inputs must be regular PDF files smaller than 16 MiB")
            data = path.read_bytes()
            reader = PdfReader(path)
            result[folder].append({"file": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                   "pages": len(reader.pages),
                                   "page_sizes": [[float(page.mediabox.width), float(page.mediabox.height)] for page in reader.pages]})
    expected = {Path(row["file"]).stem + "_key.pdf" for row in result["forms"]}
    actual = {row["file"] for row in result["answer_keys"]}
    result["missing_answer_keys"] = sorted(expected - actual)
    result["unpaired_answer_keys"] = sorted(actual - expected)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.split_root.resolve(strict=True)
        output = args.output.resolve()
        if output.suffix != ".json" or output.is_relative_to(root):
            raise ValueError("Write a JSON inventory outside the input split")
        result = inventory(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"forms": len(result["forms"]), "form_pages": sum(row["pages"] for row in result["forms"]),
                          "answer_keys": len(result["answer_keys"]), "key_pages": sum(row["pages"] for row in result["answer_keys"]),
                          "missing_keys": len(result["missing_answer_keys"]), "unpaired_keys": len(result["unpaired_answer_keys"])}))
        return 1 if result["missing_answer_keys"] or result["unpaired_answer_keys"] else 0
    except Exception:
        print("Could not inventory the explicitly selected PDF split.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
