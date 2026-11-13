"""One bounded document job per process. No document content is logged."""
import base64
import json
from pathlib import Path
import sys

from pipeline import DocumentError, process_document


def main():
    try:
        request = json.load(sys.stdin)
        result = process_document(base64.b64decode(request["data"], validate=True), request["filename"], request["schema"], Path(request["assetDir"]), request["recordId"])
    except DocumentError as exc:
        result = {"error": str(exc)[:500]}
    except Exception:
        result = {"error": "The local document reader could not process this file."}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
