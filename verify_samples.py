"""Compare the real PDF/OCR pipeline with the fictional answer key."""
import json
from pathlib import Path
import tempfile

from pipeline import capabilities, process_document

ROOT = Path(__file__).resolve().parent


def main():
    schema = json.loads((ROOT / "samples/sample-schema.json").read_text())["fields"]
    key = json.loads((ROOT / "samples/answer-key.json").read_text())["records"]
    records = []
    total_matches = 0
    with tempfile.TemporaryDirectory(prefix="formbridge-verification-") as assets:
        for index, item in enumerate(key):
            result = process_document((ROOT / "samples" / item["file"]).read_bytes(), item["file"], schema, Path(assets), f"fictional-{index}")
            expected = {name: str(value) for name, value in item["expected"].items()}
            mismatches = {name: {"expected": value, "actual": result["values"].get(name)} for name, value in expected.items() if result["values"].get(name) != value}
            total_matches += len(expected) - len(mismatches)
            records.append({"file": item["file"], "mode": item["mode"], "fields": len(expected), "matches": len(expected) - len(mismatches), "mismatches": mismatches, "issues": result["issues"], "pipeline": result["pipeline"]})
    report = {"fixtureNotice": "Generated fictional practice records only.", "totalMatches": total_matches, "totalFields": sum(record["fields"] for record in records), "capabilities": capabilities(), "records": records, "limitation": "One deterministic set of ten clean printed English forms. No claim about handwriting, real clinical forms, camera images, or Windows Tesseract accuracy."}
    destination = ROOT / "verification/pipeline-results.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Matched {report['totalMatches']} of {report['totalFields']} fictional fields. Report: {destination}")
    if total_matches != report["totalFields"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
