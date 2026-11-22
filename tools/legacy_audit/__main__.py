"""Usage: python -B -m tools.legacy_audit --fixture /private/tmp/..."""
import argparse
import json
from pathlib import Path

from .sqlite_reader import FixtureError, audit


def main() -> int:
    parser = argparse.ArgumentParser(description='Phase 4A synthetic-only read-only audit')
    parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args()
    try:
        summary, _ = audit(args.fixture)
    except FixtureError:
        print(json.dumps({'status': 'BLOCKED', 'reason': 'INVALID_OR_UNSUPPORTED_SYNTHETIC_FIXTURE'}))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
