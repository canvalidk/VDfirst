"""REPL loop for simulator inspection commands."""

from __future__ import annotations

from collections.abc import Callable

from demand import Demand, ExpandProvenance, InjectProvenance, Trace
from simulator import Simulator


PICK_PREVIEW_WIDTH = 60
PICK_TRUNCATION_MARKER = "..."

# Message convention: action confirmations are lowercase and end with a
# period. Refusals and status displays are lowercase and do not, unless
# a command-specific contract says otherwise.


class REPL:
    """Input loop hosting simulator inspection and trace commands."""

    def __init__(
        self,
        sim: Simulator,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
    ) -> None:
        self.sim = sim
        self.trace: Trace | None = None
        self.input_fn = input_fn
        self.print_fn = print_fn
        self.dispatch = {
            "all_headwords": self.cmd_headwords,
            "back": self.cmd_back,
            "cancel": self.cmd_cancel,
            "expand": self.cmd_expand,
            "go": self.cmd_go,
            "goto": self.cmd_goto,
            "headwords": self.cmd_headwords,
            "help": self.cmd_help,
            "inject": self.cmd_inject,
            "count": self.cmd_count,
            "recall": self.cmd_recall,
            "state": self.cmd_state,
            "trace": self.cmd_trace,
            "up": self.cmd_up,
            "worklist": self.cmd_worklist,
        }

    def run(self) -> None:
        """Run until the user exits or EOF arrives."""
        while self.step():
            pass

    def step(self) -> bool:
        """Read one input, dispatch it, and report whether to continue."""
        try:
            line = self.input_fn(self._prompt())
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

    def _prompt(self) -> str:
        return "trace> " if self.trace is not None else "> "

    def cmd_help(self, rest: str) -> None:
        """Print the available command set."""
        always = [
            ("all_headwords, headwords", "list all headwords"),
            ("count", "entry and headword counts"),
            ("exit, quit", "leave the REPL"),
            ("help", "this list"),
            (
                "recall <headword>",
                "show a dictionary entry (or fill a hole in trace)",
            ),
            ("trace <text>", "start a new trace"),
        ]
        trace_only = [
            ("back", "undo the active child, return to its parent"),
            ("cancel", "abandon the entire trace"),
            ("expand [pos]", "expand an open hole into a dictionary entry"),
            ("go to N, goto N", "move active focus to worklist entry N"),
            ("inject [pos]", "fill an open hole with user-supplied text"),
            ("state", "show the active demand"),
            ("up", "move active focus to the parent demand"),
            ("worklist", "list all open holes across the tree"),
        ]

        self._print_help_section("always available:", always)
        self.print_fn("")
        self._print_help_section("trace-only:", trace_only)

    def _print_help_section(
        self,
        title: str,
        commands: list[tuple[str, str]],
    ) -> None:
        self.print_fn(title)
        for name, description in commands:
            self.print_fn(f"  {name:<28}{description}")

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
        """Recall entry text, or fill a trace hole while inside a trace."""
        if self.trace is not None:
            self._cmd_trace_recall(rest)
            return

        self._cmd_inspection_recall(rest)

    def _cmd_inspection_recall(self, rest: str) -> None:
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

    def cmd_trace(self, rest: str) -> None:
        """Start a trace from user text."""
        if self.trace is not None:
            self.print_fn(
                "trace only valid outside a trace; "
                "use 'cancel' first"
            )
            return

        text = rest.strip()
        if not text:
            self.print_fn("usage: trace <text>")
            return

        self.trace = Trace.start(self.sim, text)
        self.print_fn("trace started.")
        self.cmd_state("")
        self._announce_completion()

    def cmd_state(self, rest: str) -> None:
        """Print the active demand's current rendering."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        self.print_fn(f"at: {self._breadcrumb(active)}")
        self.print_fn(active.text())
        if active.open_positions:
            positions = ", ".join(str(p) for p in active.open_positions)
            self.print_fn(f"open positions: {positions}")
        else:
            self.print_fn("open positions: none")

    def cmd_worklist(self, rest: str) -> None:
        """List open holes across the current tree.

        Indices are recomputed on every call and may change after trace
        mutations. Use them as one-shot handles for the current worklist.
        """
        if not self._require_trace():
            return

        assert self.trace is not None
        worklist = self.trace.worklist
        if not worklist:
            self.print_fn("no open holes; trace is complete.")
            return

        for index, (demand, pos) in enumerate(worklist):
            marker = "*" if demand is self.trace.active else " "
            tag = self._location_tag(demand)
            headword = demand.headword_at(pos)
            self.print_fn(
                f"{marker} [{index}] {tag:<12} pos {pos}  ->  "
                f"{{{headword}}}"
            )

    def cmd_goto(self, rest: str) -> None:
        """Move active focus to the demand at the current worklist index."""
        if not self._require_trace():
            return

        raw = rest.strip()
        if not raw:
            self.print_fn("usage: goto N")
            return

        try:
            index = int(raw)
        except ValueError:
            self.print_fn("invalid index")
            return

        assert self.trace is not None
        worklist = self.trace.worklist
        if not worklist:
            self.print_fn("no open holes")
            return

        if index < 0 or index >= len(worklist):
            self.print_fn(
                f"index {index} out of range; "
                f"worklist has {len(worklist)} entries"
            )
            return

        demand, _ = worklist[index]
        self.trace.active = demand
        self.print_fn(f"moved to {self._location_tag(demand)}.")

    def cmd_go(self, rest: str) -> None:
        """Alias for the natural-language form: go to N."""
        raw = rest.strip()
        word, _, target = raw.partition(" ")
        if word.lower() != "to" or not target.strip():
            self.print_fn("usage: go to N")
            return

        self.cmd_goto(target)

    def cmd_expand(self, rest: str) -> None:
        """Expand an active trace hole into a dictionary entry child."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        pos = self._position_for_hole_command(rest, active)
        if pos is None:
            return

        headword = active.headword_at(pos)
        index = self._pick_entry_index(headword)
        if index is None:
            return

        text = self.sim.entry_text(index)
        child = Demand(
            self.sim.analyse(text),
            provenance=ExpandProvenance(index),
        )
        active.resolve_expand(pos, child, source_index=index)
        self.trace.active = child
        self.print_fn(f"expanded E{index} at position {pos}; now at child.")
        self._announce_completion()

    def _cmd_trace_recall(self, rest: str) -> None:
        """Fill an active trace hole with raw dictionary entry text."""
        assert self.trace is not None
        active = self.trace.active
        pos = self._position_for_hole_command(rest, active)
        if pos is None:
            return

        headword = active.headword_at(pos)
        index = self._pick_entry_index(headword)
        if index is None:
            return

        active.resolve_recall(pos, self.sim.entry_text(index), index)
        self.print_fn(f"recalled E{index} at position {pos}.")
        self._announce_completion()

    def cmd_inject(self, rest: str) -> None:
        """Inject user text as a child demand at an active trace hole."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        pos = self._position_for_hole_command(rest, active)
        if pos is None:
            return

        text = self.input_fn("text: ").strip()
        if not text:
            self.print_fn("inject aborted: no text")
            return

        child = Demand(
            self.sim.analyse(text),
            provenance=InjectProvenance(text),
        )
        active.resolve_inject(pos, child)
        self.trace.active = child
        self.print_fn(f"injected at position {pos}; now at child.")
        self._announce_completion()

    def cmd_up(self, rest: str) -> None:
        """Move active trace focus to its parent demand."""
        if not self._require_trace():
            return

        assert self.trace is not None
        try:
            self.trace.up()
        except ValueError:
            self.print_fn("already at root")
            return

        self.print_fn("moved up.")

    def cmd_back(self, rest: str) -> None:
        """Back out of the active child."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        parent = active.parent
        if parent is None:
            self.print_fn("already at root")
            return

        for pos, child in parent.children().items():
            if child is active:
                parent.unresolve(pos)
                self.trace.active = parent
                self.print_fn(f"backed out of child at position {pos}.")
                return

        self.print_fn("could not find active child on parent")

    def cmd_cancel(self, rest: str) -> None:
        """Cancel the whole trace."""
        if not self._require_trace():
            return

        self.trace = None
        self.print_fn("trace cancelled.")

    def _require_trace(self) -> bool:
        if self.trace is None:
            self.print_fn("not in a trace; use 'trace <text>' to start one")
            return False
        return True

    def _position_for_hole_command(
        self,
        rest: str,
        active: Demand,
    ) -> int | None:
        raw = rest.strip()
        if not raw:
            if not active.open_positions:
                self.print_fn("no open holes; use 'up' or 'back'")
                return None
            return active.open_positions[0]

        try:
            pos = int(raw)
        except ValueError:
            self.print_fn("invalid position")
            return None

        try:
            active.headword_at(pos)
        except ValueError as exc:
            self.print_fn(str(exc))
            return None

        if pos not in active.open_positions:
            self.print_fn(f"position {pos} is already resolved")
            return None

        return pos

    def _pick_entry_index(self, headword: str) -> int | None:
        idxs = self.sim.entry_indexes(headword)
        if not idxs:
            self.print_fn(f"no entry for '{headword}'")
            return None

        if len(idxs) == 1:
            return idxs[0]

        self.print_fn(f"multiple entries for '{headword}':")
        for index in idxs:
            self.print_fn(
                f"  E{index}: {self._entry_preview(index)}"
            )

        pick = self.input_fn("pick E-number: ")
        try:
            chosen = int(pick)
        except ValueError:
            self.print_fn("invalid choice; aborted")
            return None

        if chosen not in idxs:
            self.print_fn("invalid choice; aborted")
            return None

        return chosen

    def _entry_preview(self, index: int) -> str:
        text = self.sim.entry_text(index)
        if len(text) <= PICK_PREVIEW_WIDTH:
            return text
        width = PICK_PREVIEW_WIDTH - len(PICK_TRUNCATION_MARKER)
        return text[:width] + PICK_TRUNCATION_MARKER

    def _location_tag(self, demand: Demand) -> str:
        if demand.parent is None:
            return "root"
        if isinstance(demand.provenance, ExpandProvenance):
            return f"E{demand.provenance.source_index}"
        if isinstance(demand.provenance, InjectProvenance):
            return "injected"
        return "child"

    def _breadcrumb(self, demand: Demand) -> str:
        tag = self._location_tag(demand)
        if demand.parent is None:
            return tag

        for pos, child in demand.parent.children().items():
            if child is demand:
                return f"{tag} @ parent pos {pos}"

        return f"{tag} @ parent pos ?"

    def _announce_completion(self) -> None:
        if self.trace is not None and self.trace.is_complete:
            self.print_fn("trace complete.")
            self.print_fn(self.trace.root.text())
