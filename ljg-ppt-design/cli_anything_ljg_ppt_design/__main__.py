"""HKUDS hub-style CLI entry."""

import sys
from ljg_ppt_design import cli as _ljg_cli


def main() -> int:
    return _ljg_cli.main()


if __name__ == "__main__":
    sys.exit(main())
