"""Run the VD simulator command loop on the Newton dictionary."""

from __future__ import annotations

from newton import build_newton_instance
from repl import REPL
from simulator import Simulator


def main() -> None:
    vd = build_newton_instance()
    REPL(Simulator(vd)).run()


if __name__ == "__main__":
    main()
