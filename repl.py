"""REPL loop for simulator inspection commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from application import HeadwordApplicationError, HeadwordArityError
from demand import (
    Demand,
    ExpandProvenance,
    ExpandResolution,
    InjectProvenance,
    InjectResolution,
    RecallResolution,
    Trace,
)
from simulator import Simulator


PICK_PREVIEW_WIDTH = 60
PICK_TRUNCATION_MARKER = "..."

# Message convention: action confirmations are lowercase and end with a
# period. Refusals and status displays are lowercase and do not, unless
# a command-specific contract says otherwise.


@dataclass(frozen=True)
class RecalledEntry:
    """Entry selected by the RECALL operation."""

    index: int
    headword: str
    text: str


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
        self.reduce_policy = "on_settle"
        self.cleanup_policy = "on_settled_only"
        self.dispatch = {
            "all_headwords": self.cmd_headwords,
            "cancel": self.cmd_cancel,
            "events": self.cmd_events,
            "expand": self.cmd_expand,
            "flatten": self.cmd_flatten,
            "fold": self.cmd_fold,
            "go": self.cmd_go,
            "goto": self.cmd_goto,
            "headwords": self.cmd_headwords,
            "help": self.cmd_help,
            "inject": self.cmd_inject,
            "count": self.cmd_count,
            "onward": self.cmd_onward,
            "recall": self.cmd_recall,
            "reduce": self.cmd_reduce,
            "return": self.cmd_return,
            "set": self.cmd_set,
            "state": self.cmd_state,
            "tidy": self.cmd_tidy,
            "trace": self.cmd_trace,
            "unreduce": self.cmd_unreduce,
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

        try:
            handler(rest)
        except HeadwordArityError as exc:
            self.print_fn(f"arity error: {exc}")
        except HeadwordApplicationError as exc:
            self.print_fn(f"headword error: {exc}")
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
            (
                "set cleanup <policy>",
                "cleanup offers: on_settled_only|on_every_resolution|off",
            ),
            ("set reduce <on_settle|off>", "toggle reduce offers on settle"),
            ("trace <text>", "start a new trace"),
        ]
        trace_only = [
            ("cancel", "abandon the entire trace"),
            ("events", "show trace event history"),
            ("expand [pos]", "expand an open hole into a dictionary entry"),
            ("flatten [pos|all]", "make active open holes inert literals"),
            ("fold", "offer reduce across settled nodes, leaves-up"),
            ("go to N, goto N", "move active focus to worklist entry N"),
            ("inject [pos]", "fill an open hole with user-supplied text"),
            ("onward", "leave settled frames for the deepest open ancestor"),
            ("reduce", "replace the active node's render with equivalent text"),
            ("return", "return resolved active demand to its parent"),
            ("state", "show the active demand"),
            (
                "tidy [scope]",
                "sweep settled prose for cleanup (active|subtree|all)",
            ),
            ("unreduce", "clear the active node's reduction"),
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
            entry = self._recall_entry(headword, preview_choices=False)
        except IndexError as exc:
            self.print_fn(str(exc))
            return

        if entry is not None:
            self.print_fn(f"E{entry.index}: {entry.text}")

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
        if active.reduced is not None:
            self.print_fn("(reduced)")
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
            suffix = ""
            closer = demand.ancestor_cycle(pos)
            if closer is not None:
                suffix = f"  (cycle: open at {self._location_tag(closer)})"
            self.print_fn(
                f"{marker} [{index}] {tag:<12} pos {pos}  ->  "
                f"{{{headword}}}{suffix}"
            )

    def cmd_events(self, rest: str) -> None:
        """Print the current trace event history."""
        if not self._require_trace():
            return

        assert self.trace is not None
        if not self.trace.events:
            self.print_fn("no events")
            return

        for index, event in enumerate(self.trace.events):
            self.print_fn(f"[{index}] {event.kind}: {event.detail}")

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
        closer = active.ancestor_cycle(pos)
        if closer is not None:
            self.print_fn(
                f"note: '{headword}' is already open at "
                f"{self._location_tag(closer)}; expanding will revisit it."
            )
        entry = self._recall_entry(headword, preview_choices=True)
        if entry is None:
            return

        self._expand_active_with_entry(pos, entry)

    def _cmd_trace_recall(self, rest: str) -> None:
        """Fill an active trace hole with raw dictionary entry text."""
        assert self.trace is not None
        active = self.trace.active
        pos = self._position_for_hole_command(rest, active)
        if pos is None:
            return

        headword = active.headword_at(pos)
        entry = self._recall_entry(headword, preview_choices=True)
        if entry is None:
            return

        self._recall_active_with_entry(pos, entry)

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

        self._inject_active_with_text(pos, text)

    def cmd_flatten(self, rest: str) -> None:
        """Resolve active open holes as inert literal headwords."""
        if not self._require_trace():
            return

        assert self.trace is not None
        raw = rest.strip().lower()
        try:
            if not raw or raw == "all":
                positions = self.trace.flatten_active()
            else:
                try:
                    pos = int(raw)
                except ValueError:
                    self.print_fn("invalid position")
                    return
                positions = self.trace.flatten_active_position(pos)
        except ValueError as exc:
            self.print_fn(str(exc))
            return

        if not positions:
            self.print_fn("no open holes to flatten")
            return

        if len(positions) == 1:
            self.print_fn(f"flattened position {positions[0]}.")
        else:
            rendered = ", ".join(str(pos) for pos in positions)
            self.print_fn(f"flattened positions {rendered}.")
        self._offer_reduce_on_settle(self.trace.active)
        self._announce_completion()

    def cmd_return(self, rest: str) -> None:
        """Return a resolved active demand to its parent."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        if active.parent is None:
            self.print_fn("already at root")
            return
        if not active.is_resolved:
            self.print_fn("active demand is not resolved")
            return

        parent = active.parent
        from_tag = self._location_tag(active)
        self.trace.active = parent
        self.trace.record_event(
            "return",
            f"{from_tag} to {self._location_tag(parent)}",
        )
        self.print_fn("returned to parent.")

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

    def cmd_onward(self, rest: str) -> None:
        """Leave settled frames for the deepest open ancestor."""
        if not self._require_trace():
            return

        assert self.trace is not None
        node = self.trace.active
        if not node.is_resolved:
            self.print_fn("already at open work")
            return

        from_tag = self._location_tag(node)
        while node.is_resolved and node.parent is not None:
            node = node.parent
        self.trace.active = node
        self.trace.record_event(
            "onward",
            f"{from_tag} to {self._location_tag(node)}",
        )
        self.print_fn(f"onward to {self._location_tag(node)}.")

    def cmd_cancel(self, rest: str) -> None:
        """Cancel the whole trace."""
        if not self._require_trace():
            return

        self.trace = None
        self.print_fn("trace cancelled.")

    def cmd_reduce(self, rest: str) -> None:
        """Replace the active node's render with an equivalent text."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        if not active.is_resolved:
            self.print_fn("node is not fully resolved")
            return

        self.print_fn("current render:")
        self.print_fn(f"  {active.text()}")
        try:
            text = self.input_fn("replacement (empty to abort): ").strip()
        except EOFError:
            text = ""
        if not text:
            self.print_fn("reduce aborted: no text")
            return

        if not self._apply_reduction(active, text):
            return
        self.print_fn("reduced.")

        parent = active.parent
        if parent is not None:
            from_tag = self._location_tag(active)
            self.trace.active = parent
            self.trace.record_event(
                "return",
                f"{from_tag} to {self._location_tag(parent)}",
            )
            self.print_fn("returned to parent.")

    def cmd_unreduce(self, rest: str) -> None:
        """Clear the active node's reduction overlay."""
        if not self._require_trace():
            return

        assert self.trace is not None
        active = self.trace.active
        if active.reduced is None:
            self.print_fn("node is not reduced")
            return

        active.clear_reduction()
        self.trace.record_event(
            "unreduce",
            self._location_tag(active),
        )
        self.print_fn("unreduced.")

    def cmd_fold(self, rest: str) -> None:
        """Offer reduce across settled nodes, post-order, leaves-up."""
        if not self._require_trace():
            return

        assert self.trace is not None
        targets: list[Demand] = []

        def walk(node: Demand) -> None:
            if node.reduced is not None:
                return
            for pos in sorted(node.children()):
                walk(node.children()[pos])
            if node.is_resolved:
                targets.append(node)

        walk(self.trace.root)
        if not targets:
            self.print_fn("nothing to fold")
            return

        reduced_count = 0
        skipped_count = 0
        for node in targets:
            self.print_fn(f"fold: {self._breadcrumb(node)}")
            self.print_fn("current render:")
            self.print_fn(f"  {node.text()}")
            try:
                text = self.input_fn(
                    "replacement (empty to skip): "
                ).strip()
            except EOFError:
                text = ""
            if not text:
                skipped_count += 1
                continue
            if not self._apply_reduction(node, text):
                skipped_count += 1
                continue
            self.print_fn("reduced.")
            reduced_count += 1

        self.print_fn(
            f"fold complete: {reduced_count} reduced, "
            f"{skipped_count} skipped."
        )

    def cmd_set(self, rest: str) -> None:
        """Set a REPL policy: reduce offers or cleanup offers."""
        name, _, value = rest.strip().partition(" ")
        name = name.lower()
        policy = value.strip().lower()
        if name == "reduce":
            if policy in ("on_settle", "off"):
                self.reduce_policy = policy
                self.print_fn(f"reduce policy: {policy}.")
                return
            self.print_fn("usage: set reduce <on_settle|off>")
            return
        if name == "cleanup":
            if policy in (
                "on_settled_only",
                "on_every_resolution",
                "off",
            ):
                self.cleanup_policy = policy
                self.print_fn(f"cleanup policy: {policy}.")
                return
            self.print_fn(
                "usage: set cleanup "
                "<on_settled_only|on_every_resolution|off>"
            )
            return
        self.print_fn("usage: set <reduce|cleanup> <policy>")

    def cmd_tidy(self, rest: str) -> None:
        """Sweep settled prose, offering cleanup per target."""
        if not self._require_trace():
            return

        assert self.trace is not None
        scope = rest.strip().lower() or "subtree"
        if scope == "active_subtree":
            scope = "subtree"
        if scope not in ("active", "subtree", "all"):
            self.print_fn("usage: tidy [active|subtree|all]")
            return

        active = self.trace.active
        targets: list[tuple] = []

        def collect(node: Demand, recurse: bool) -> None:
            if node.reduced is not None and scope != "active":
                return
            if self._node_settled_text(node) and (
                not node.cleaned or scope == "active"
            ):
                targets.append(("node", node))
            for pos in sorted(node.resolutions):
                resolution = node.resolutions[pos]
                if isinstance(resolution, RecallResolution):
                    if (
                        pos not in node.cleaned_recalls
                        or scope == "active"
                    ):
                        targets.append(("recall", node, pos))
                elif recurse and isinstance(
                    resolution,
                    (ExpandResolution, InjectResolution),
                ):
                    collect(resolution.child, recurse)

        if scope == "active":
            reducer = self._masking_reducer(active)
            if reducer is not None:
                self.print_fn(
                    f"note: this prose is masked by a reduction "
                    f"at {self._location_tag(reducer)}"
                )
            collect(active, recurse=False)
        elif scope == "subtree":
            collect(active, recurse=True)
        else:
            collect(self.trace.root, recurse=True)

        if not targets:
            self.print_fn("nothing to tidy")
            return

        cleaned_count = 0
        skipped_count = 0
        for target in targets:
            if self._tidy_one(target):
                cleaned_count += 1
            else:
                skipped_count += 1
        self.print_fn(
            f"tidy complete: {cleaned_count} cleaned, "
            f"{skipped_count} skipped."
        )

    def _tidy_one(self, target: tuple) -> bool:
        """Run one visible tidy interaction; report whether cleaned."""
        assert self.trace is not None
        if target[0] == "node":
            _, node = target
            self.print_fn(f"tidy: {self._breadcrumb(node)}")
            latents = node.definiens.residual.latent
            headwords = node.definiens.headwords
            for i, latent in enumerate(latents):
                self.print_fn(f"  [{i}] {latent!r}")
                if i < len(headwords):
                    self.print_fn(f"  {{{headwords[i]}}}")
            new_latents = list(latents)
            changed = False
            for i in range(len(latents)):
                try:
                    reply = self.input_fn(f"gap {i} (empty to keep): ")
                except EOFError:
                    break
                if reply.strip():
                    new_latents[i] = reply
                    changed = True
            if not changed:
                return False
            hits = sorted({
                hit
                for i in range(len(latents))
                if new_latents[i] != latents[i]
                for hit in self._headword_hits(new_latents[i])
            })
            if hits:
                self.print_fn(self._cleanup_rejection(hits))
                return False
            node.set_latents(new_latents)
            self.trace.record_event("clean", self._location_tag(node))
            self.print_fn("cleaned.")
            return True

        _, node, pos = target
        resolution = node.resolutions[pos]
        self.print_fn(f"tidy: {self._breadcrumb(node)} recall pos {pos}")
        self.print_fn(f"  [0] {resolution.text!r}")
        try:
            reply = self.input_fn("gap 0 (empty to keep): ")
        except EOFError:
            reply = ""
        if not reply.strip():
            return False
        hits = self._headword_hits(reply)
        if hits:
            self.print_fn(self._cleanup_rejection(hits))
            return False
        node.clean_recall_text(pos, reply)
        self.trace.record_event(
            "clean",
            f"{self._location_tag(node)} pos {pos}",
        )
        self.print_fn("cleaned.")
        return True

    def _offer_cleanup_recall(self, node: Demand, pos: int) -> None:
        """Prompt-only cleanup offer on a just-recalled hole's text."""
        if self.cleanup_policy == "off":
            return
        if self._is_masked(node):
            return
        resolution = node.resolutions[pos]
        try:
            reply = self.input_fn(
                f"clean {self._breadcrumb(node)} pos {pos} "
                f"[{resolution.text}] "
                f"(replacement or empty to skip): "
            )
        except EOFError:
            reply = ""
        if not reply.strip():
            return
        hits = self._headword_hits(reply)
        if hits:
            self.print_fn(self._cleanup_rejection(hits))
            return
        node.clean_recall_text(pos, reply)
        assert self.trace is not None
        self.trace.record_event(
            "clean",
            f"{self._location_tag(node)} pos {pos}",
        )
        self.print_fn("cleaned.")

    def _offer_cleanup_node(self, node: Demand) -> None:
        """Prompt-only cleanup offer on a child node's latents."""
        if self.cleanup_policy == "off":
            return
        if self._is_masked(node):
            return
        latents = node.definiens.residual.latent
        new_latents = list(latents)
        changed = False
        for i in range(len(latents)):
            try:
                reply = self.input_fn(
                    f"clean {self._breadcrumb(node)} gap {i} "
                    f"[{latents[i]}] (replacement or empty to keep): "
                )
            except EOFError:
                break
            if reply.strip():
                new_latents[i] = reply
                changed = True
        if not changed:
            return
        hits = sorted({
            hit
            for i in range(len(latents))
            if new_latents[i] != latents[i]
            for hit in self._headword_hits(new_latents[i])
        })
        if hits:
            self.print_fn(self._cleanup_rejection(hits))
            return
        node.set_latents(new_latents)
        assert self.trace is not None
        self.trace.record_event("clean", self._location_tag(node))
        self.print_fn("cleaned.")

    def _cleanup_rejection(self, hits: list[str]) -> str:
        return (
            f"{hits} are headwords; cleanup edits non-headword "
            f"prose only. To use the word literally, escape it; "
            f"to reference it, expand."
        )

    def _is_masked(self, node: Demand) -> bool:
        return self._masking_reducer(node) is not None

    def _masking_reducer(self, node: Demand) -> Demand | None:
        cursor: Demand | None = node
        while cursor is not None:
            if cursor.reduced is not None:
                return cursor
            cursor = cursor.parent
        return None

    def _node_settled_text(self, node: Demand) -> bool:
        return not node.open_positions

    def _apply_reduction(self, node: Demand, text: str) -> bool:
        """Guard and store a reduction; report success."""
        hits = self._headword_hits(text)
        if hits:
            self.print_fn(
                f"{hits} are headwords; reduction takes non-headword "
                f"prose only. To use the word literally, escape it; "
                f"to reference it, expand."
            )
            return False

        node.set_reduction(text)
        assert self.trace is not None
        self.trace.record_event(
            "reduce",
            f"{self._location_tag(node)}: {text}",
        )
        return True

    def _headword_hits(self, text: str) -> list[str]:
        """Headword tokens present in text, per tokeniser identity."""
        return sorted(set(self.sim.analyse(text).headwords))

    def _offer_reduce_on_settle(self, node: Demand | None) -> None:
        """Offer reduce on each newly settled node, deepest-first.

        The offer lives in the input prompt; empty input or EOF skips.
        Existing output is unchanged unless an offer is accepted.
        """
        if self.reduce_policy != "on_settle":
            return

        chain: list[Demand] = []
        while node is not None and node.is_resolved:
            if node.reduced is None:
                chain.append(node)
            node = node.parent

        for target in chain:
            try:
                text = self.input_fn(
                    f"reduce {self._breadcrumb(target)} "
                    f"[{target.text()}] "
                    f"(replacement or empty to skip): "
                ).strip()
            except EOFError:
                text = ""
            if not text:
                continue
            if not self._apply_reduction(target, text):
                continue
            self.print_fn("reduced.")

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
                self.print_fn("no open holes; use 'up' or 'onward'")
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

    def _recall_entry(
        self,
        headword: str,
        *,
        preview_choices: bool,
    ) -> RecalledEntry | None:
        """Resolve a headword to selected entry text.

        This is the RECALL operation: it composes dictionary lookup with
        optional user choice, but does not analyse text or mutate trace state.
        """
        index = self._pick_entry_index(
            headword,
            preview_choices=preview_choices,
        )
        if index is None:
            return None

        return RecalledEntry(
            index=index,
            headword=headword,
            text=self.sim.instantiated_entry_text(index, headword),
        )

    def _pick_entry_index(
        self,
        headword: str,
        *,
        preview_choices: bool,
    ) -> int | None:
        idxs = self.sim.entry_indexes(headword)
        if not idxs:
            self.print_fn(f"no entry for '{headword}'")
            return None

        if len(idxs) == 1:
            return idxs[0]

        self.print_fn(f"multiple entries for '{headword}':")
        for index in idxs:
            choice_text = self._entry_choice_text(
                index,
                preview_choices,
                headword,
            )
            self.print_fn(f"  E{index}: {choice_text}")

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

    def _entry_choice_text(
        self,
        index: int,
        preview: bool,
        headword: str,
    ) -> str:
        text = self.sim.instantiated_entry_text(index, headword)
        if preview:
            return self._entry_preview(text)
        return text

    def _entry_preview(self, text: str) -> str:
        if len(text) <= PICK_PREVIEW_WIDTH:
            return text
        width = PICK_PREVIEW_WIDTH - len(PICK_TRUNCATION_MARKER)
        return text[:width] + PICK_TRUNCATION_MARKER

    def _expand_active_with_entry(
        self,
        pos: int,
        entry: RecalledEntry,
    ) -> None:
        assert self.trace is not None
        active = self.trace.active
        child = Demand(
            self.sim.analyse(entry.text),
            provenance=ExpandProvenance(entry.index),
        )
        active.resolve_expand(pos, child, source_index=entry.index)
        self.trace.active = child
        self.trace.record_event(
            "expand",
            f"E{entry.index} at position {pos}",
        )
        self.print_fn(
            f"expanded E{entry.index} at position {pos}; now at child."
        )
        self._offer_reduce_on_settle(child)
        if self.cleanup_policy == "on_every_resolution":
            self._offer_cleanup_node(child)
        self._announce_completion()

    def _recall_active_with_entry(
        self,
        pos: int,
        entry: RecalledEntry,
    ) -> None:
        assert self.trace is not None
        active = self.trace.active
        active.resolve_recall(pos, entry.text, entry.index)
        self.trace.record_event(
            "recall",
            f"E{entry.index} at position {pos}",
        )
        self.print_fn(f"recalled E{entry.index} at position {pos}.")
        self._offer_reduce_on_settle(active)
        self._offer_cleanup_recall(active, pos)
        self._announce_completion()

    def _inject_active_with_text(self, pos: int, text: str) -> None:
        assert self.trace is not None
        active = self.trace.active
        child = Demand(
            self.sim.analyse(text),
            provenance=InjectProvenance(text),
        )
        active.resolve_inject(pos, child)
        self.trace.active = child
        self.trace.record_event(
            "inject",
            f"position {pos}: {text}",
        )
        self.print_fn(f"injected at position {pos}; now at child.")
        self._offer_reduce_on_settle(child)
        if self.cleanup_policy == "on_every_resolution" or (
            self.cleanup_policy == "on_settled_only"
            and not child.open_positions
        ):
            self._offer_cleanup_node(child)
        self._announce_completion()

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
