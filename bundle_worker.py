"""Isolated local PDF bundle processing with bounded JSON-only output."""
import json
import sys


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not supported.")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON numbers are not supported.")


def main():
    try:
        from source_bundle import BundleError, MAX_REQUEST_BYTES, make_bundle
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if not raw or len(raw) > MAX_REQUEST_BYTES:
            raise BundleError("The source bundle request is empty or exceeds the input limit.")
        try:
            request = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_object, parse_constant=_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise BundleError("The source bundle request must be valid UTF-8 JSON without duplicate keys.") from None
        response = {"result": make_bundle(request)}
    except ValueError as error:
        response = {"error": str(error)[:300]}
    except Exception:
        response = {"error": "The source bundle could not be processed safely. Check the PDF files and application requirements."}
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
