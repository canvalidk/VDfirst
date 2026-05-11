"""REPL loop for simulator inspection commands."""

from __future__ import annotations

from collections.abc import Callable

from simulator import Simulator


class REPL:
    """Input loop hosting read-only simulator inspection commands."""

    def __init__(
        self,
        sim: Simulator,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
    ) -> None:
        self.sim = sim
        self.input_fn = input_fn
        self.print_fn = print_fn
        self.dispatch = {
            "headwords": self.cmd_headwords,
            "count": self.cmd_count,
            "recall": self.cmd_recall,
        }

    def run(self) -> None:
        """Run until the user exits or EOF arrives."""
        while self.step():
            pass

    def step(self) -> bool:
        """Read one input, dispatch it, and report whether to continue."""
        try:
            line = self.input_fn("> ")
        except EOFError:
            return False
        except KeyboardInterrupt:
            self.print_fn()
            return True

        line = line.strip()
        if not line:
            return True

        cmd, _, rest = line.partition(" ")
        cmd = cmd.lower()

        if cmd in ("exit", "quit"):
            return False

        handler = self.dispatch.get(cmd)
        if handler is None:
            self.print_fn(f"unknown command: {cmd}")
            return True

        handler(rest)
        return True

    def cmd_headwords(self, rest: str) -> None:
        """Print all known headwords, one per line."""
        for headword in self.sim.all_headwords():
            self.print_fn(headword)

    def cmd_count(self, rest: str) -> None:
        """Print entry and distinct-headword counts."""
        self.print_fn(
            f"{self.sim.entry_count()} entries, "
            f"{self.sim.headword_count()} distinct headwords"
        )

    def cmd_recall(self, rest: str) -> None:
        """Print entries matching a headword, prompting on redefinitions."""
        headword = rest.strip()
        if not headword or headword == '""':
            self.print_fn("usage: recall <headword>")
            return

        try:
            idxs = self.sim.entry_indexes(headword)
            if not idxs:
                self.print_fn(f"no entry for '{headword}'")
                return

            if len(idxs) == 1:
                index = idxs[0]
                self.print_fn(f"E{index}: {self.sim.entry_text(index)}")
                return

            self.print_fn(f"multiple entries for '{headword}':")
            for index in idxs:
                self.print_fn(f"  E{index}: {self.sim.entry_text(index)}")

            pick = self.input_fn("pick E-number: ")
            try:
                chosen = int(pick)
            except ValueError:
                self.print_fn("invalid choice; aborted")
                return

            if chosen not in idxs:
                self.print_fn("invalid choice; aborted")
                return

            self.print_fn(f"E{chosen}: {self.sim.entry_text(chosen)}")
        except IndexError as exc:
            self.print_fn(str(exc))
