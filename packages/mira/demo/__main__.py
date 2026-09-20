"""python -m mira.demo [reset|doctor]"""

from __future__ import annotations

import sys

from mira.demo.doctor import print_doctor
from mira.demo.reset import print_reset


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "doctor"

    if command == "doctor":
        return print_doctor()

    if command == "reset":
        return print_reset()

    print("Usage: python -m mira.demo [reset|doctor]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
