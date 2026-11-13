"""Console-enabled companion. GUI code never runs in a document worker."""
import sys


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in {"document", "template"}:
        return 2
    if sys.stdin is None or sys.stdout is None:
        return 2
    if args[0] == "document":
        from worker import main as run
    else:
        from template_worker import main as run
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
