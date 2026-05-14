"""Run the VD simulator command loop on the Newton dictionary."""

from __future__ import annotations

from newton import build_newton_instance
from repl import REPL
from simulator import Simulator


def main() -> None:
    vd = build_newton_instance()
    sim = Simulator(vd)
    print(
        f"{vd.name} - {sim.entry_count()} entries, "
        f"{sim.headword_count()} distinct headwords. "
        "type 'help' for commands."
    )
    REPL(sim).run()


if __name__ == "__main__":
    main()
