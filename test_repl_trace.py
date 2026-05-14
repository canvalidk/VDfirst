"""Tests for REPL trace mode."""

import pytest

from engine import VDInstance
from repl import REPL
from simulator import Simulator


@pytest.fixture
def trace_sim() -> Simulator:
    v = VDInstance("trace")
    v.append_many([
        ("mass", "2 kg"),
        ("acceleration", "5 m/s^2"),
        ("force", "mass times acceleration"),
        ("string", "inextensible connector"),
    ])
    return Simulator(v)


@pytest.fixture
def sim_with_redefines() -> Simulator:
    v = VDInstance("redef")
    v.append_many([
        ("mass", "first definition"),
        ("particle", "thing with mass"),
        ("mass", "second definition"),
    ])
    return Simulator(v)


@pytest.fixture
def sim_with_long_redefines() -> Simulator:
    v = VDInstance("long-redef")
    v.append_many([
        (
            "mass",
            "A scalar property of a point-particle measuring its inertia, "
            "used throughout this example",
        ),
        ("particle", "thing with mass"),
        (
            "mass",
            "The positive scalar coefficient m such that net-force equals "
            "m times acceleration",
        ),
    ])
    return Simulator(v)


def drive(sim: Simulator, inputs: list[str]) -> list[str]:
    out = []
    it = iter(inputs)

    def input_fn(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError from exc

    REPL(
        sim,
        input_fn=input_fn,
        print_fn=lambda *args: out.append(" ".join(str(a) for a in args)),
    ).run()
    return out


def drive_repl(sim: Simulator, inputs: list[str]) -> tuple[REPL, list[str]]:
    out = []
    it = iter(inputs)

    def input_fn(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError from exc

    repl = REPL(
        sim,
        input_fn=input_fn,
        print_fn=lambda *args: out.append(" ".join(str(a) for a in args)),
    )
    repl.run()
    return repl, out


def help_line(name: str, description: str) -> str:
    return f"  {name:<28}{description}"


EXPECTED_HELP = [
    "always available:",
    help_line("all_headwords, headwords", "list all headwords"),
    help_line("count", "entry and headword counts"),
    help_line("exit, quit", "leave the REPL"),
    help_line("help", "this list"),
    help_line(
        "recall <headword>",
        "show a dictionary entry (or fill a hole in trace)",
    ),
    help_line("trace <text>", "start a new trace"),
    "",
    "trace-only:",
    help_line("back", "undo the active child, return to its parent"),
    help_line("cancel", "abandon the entire trace"),
    help_line("expand [pos]", "expand an open hole into a dictionary entry"),
    help_line("go to N, goto N", "move active focus to worklist entry N"),
    help_line("inject [pos]", "fill an open hole with user-supplied text"),
    help_line("state", "show the active demand"),
    help_line("up", "move active focus to the parent demand"),
    help_line("worklist", "list all open holes across the tree"),
]


def worklist_line(
    marker: str,
    index: int,
    tag: str,
    pos: int,
    headword: str,
) -> str:
    return f"{marker} [{index}] {tag:<12} pos {pos}  ->  {{{headword}}}"


class TestTraceBootstrap:

    def test_trace_starts_and_prints_state(self, trace_sim):
        assert drive(trace_sim, ["trace force"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
        ]

    def test_trace_with_no_headwords_is_immediately_complete(self, trace_sim):
        assert drive(trace_sim, ["trace plain text"]) == [
            "trace started.",
            "at: root",
            "plain text",
            "open positions: none",
            "trace complete.",
            "plain text",
        ]

    def test_trace_requires_text(self, trace_sim):
        assert drive(trace_sim, ["trace"]) == [
            "usage: trace <text>",
        ]

    def test_trace_is_outside_only(self, trace_sim):
        assert drive(trace_sim, ["trace force", "trace mass"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "trace only valid outside a trace; use 'cancel' first",
        ]


class TestModeDiscipline:

    def test_expand_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["expand"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_inject_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["inject"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_state_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["state"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_inspection_commands_still_work_inside_trace(self, trace_sim):
        out = drive(trace_sim, ["trace force", "count"])
        assert out[-1] == "4 entries, 4 distinct headwords"

    def test_help_inside_trace_prints_same_command_groups(self, trace_sim):
        out = drive(trace_sim, ["trace force", "help"])
        assert out[-len(EXPECTED_HELP):] == EXPECTED_HELP


class TestExpand:

    def test_expand_default_open_position_and_move_to_child(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand", "state"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "at: E2 @ parent pos 0",
            "{mass} times {acceleration}",
            "open positions: 0, 1",
        ]

    def test_expand_can_take_explicit_position(self, trace_sim):
        assert drive(trace_sim, ["trace force and mass", "expand 1"]) == [
            "trace started.",
            "at: root",
            "{force} and {mass}",
            "open positions: 0, 1",
            "expanded E0 at position 1; now at child.",
        ]

    def test_expand_prompts_for_multi_entry_headword(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["trace mass", "expand", "2"]) == [
            "trace started.",
            "at: root",
            "{mass}",
            "open positions: 0",
            "multiple entries for 'mass':",
            "  E0: first definition",
            "  E2: second definition",
            "expanded E2 at position 0; now at child.",
            "trace complete.",
            "second definition",
        ]

    def test_expand_invalid_position_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand x"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "invalid position",
        ]

    def test_expand_multi_entry_prompt_truncates_long_definitions(
        self,
        sim_with_long_redefines,
    ):
        out = drive(sim_with_long_redefines, ["trace mass", "expand", "0"])
        assert out[5].startswith("  E0: ")
        assert out[5].endswith("...")
        assert "used throughout" not in out[5]


class TestTraceRecall:

    def test_recall_inside_trace_fills_in_place(self, trace_sim):
        assert drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "state",
        ]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "recalled E0 at position 0.",
            "at: E2 @ parent pos 0",
            "2 kg times {acceleration}",
            "open positions: 1",
        ]

    def test_recall_inside_trace_can_finish_trace(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "recall",
        ])
        assert out[-2:] == [
            "trace complete.",
            "2 kg times 5 m/s^2",
        ]

    def test_recall_rejects_closed_position(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall 0",
            "recall 0",
        ])
        assert out[-1] == "position 0 is already resolved"


class TestInject:

    def test_inject_creates_child_and_moves_to_it(self, trace_sim):
        assert drive(trace_sim, [
            "trace force",
            "inject",
            "mass of this object",
            "state",
        ]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "injected at position 0; now at child.",
            "at: injected @ parent pos 0",
            "{mass} of this object",
            "open positions: 0",
        ]

    def test_inject_empty_text_aborts(self, trace_sim):
        assert drive(trace_sim, ["trace force", "inject", ""]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "inject aborted: no text",
        ]


class TestNavigationAndBack:

    def test_up_from_child_returns_to_parent(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand", "up", "state"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "moved up.",
            "at: root",
            "{mass} times {acceleration}",
            "open positions: none",
        ]

    def test_up_at_root_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "up"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "already at root",
        ]

    def test_back_child_reopens_parent_position(self, trace_sim):
        repl, out = drive_repl(trace_sim, ["trace force", "expand", "back"])
        assert out[-1] == "backed out of child at position 0."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root
        assert repl.trace.root.open_positions == [0]

    def test_cancel_exits_trace_mode(self, trace_sim):
        repl, out = drive_repl(trace_sim, ["trace force", "cancel"])
        assert out[-1] == "trace cancelled."
        assert repl.trace is None

    def test_back_at_root_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "back"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "already at root",
        ]


class TestWorklist:

    def test_worklist_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["worklist"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_root_only_trace_marks_root_active(self, trace_sim):
        assert drive(trace_sim, ["trace force", "worklist"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            worklist_line("*", 0, "root", 0, "force"),
        ]

    def test_active_demand_marks_all_of_its_open_holes(self, trace_sim):
        out = drive(trace_sim, ["trace force", "expand", "worklist"])
        assert out[-2:] == [
            worklist_line("*", 0, "E2", 0, "mass"),
            worklist_line("*", 1, "E2", 1, "acceleration"),
        ]

    def test_after_two_expands_and_up_lists_depth_first(self, trace_sim):
        out = drive(trace_sim, [
            "trace force and string",
            "expand 0",
            "expand 0",
            "up",
            "worklist",
        ])
        assert out[-2:] == [
            worklist_line(" ", 0, "root", 1, "string"),
            worklist_line("*", 1, "E2", 1, "acceleration"),
        ]

    def test_order_zero_root_has_empty_worklist(self, trace_sim):
        assert drive(trace_sim, ["trace plain text", "worklist"])[-1] == (
            "no open holes; trace is complete."
        )


class TestGoto:

    def test_goto_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["goto 0"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_goto_requires_argument(self, trace_sim):
        assert drive(trace_sim, ["trace force", "goto"])[-1] == (
            "usage: goto N"
        )

    def test_goto_zero_from_root_stays_at_root(self, trace_sim):
        repl, out = drive_repl(trace_sim, ["trace force", "goto 0"])
        assert out[-1] == "moved to root."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root

    def test_goto_returns_to_root_when_root_owns_worklist_zero(
        self,
        trace_sim,
    ):
        repl, out = drive_repl(trace_sim, [
            "trace force and string",
            "expand 1",
            "goto 0",
        ])
        assert out[-1] == "moved to root."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root

    def test_goto_rejects_out_of_range_index(self, trace_sim):
        assert drive(trace_sim, ["trace force", "goto 99"])[-1] == (
            "index 99 out of range; worklist has 1 entries"
        )

    def test_goto_rejects_non_integer_index(self, trace_sim):
        assert drive(trace_sim, ["trace force", "goto abc"])[-1] == (
            "invalid index"
        )

    def test_goto_rejects_complete_trace(self, trace_sim):
        assert drive(trace_sim, ["trace plain text", "goto 0"])[-1] == (
            "no open holes"
        )

    def test_goto_then_expand_uses_selected_demand(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "trace force and string",
            "expand 1",
            "goto 0",
            "expand",
        ])
        assert out[-1] == "expanded E2 at position 0; now at child."
        assert repl.trace is not None
        assert repl.trace.active is not repl.trace.root

    def test_go_to_alias_uses_worklist_index(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "trace force and string",
            "expand 1",
            "go to 0",
        ])
        assert out[-1] == "moved to root."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root


class TestHoleCommandEdges:

    def test_no_open_holes_message(self, trace_sim):
        assert drive(trace_sim, ["trace plain text", "recall"]) == [
            "trace started.",
            "at: root",
            "plain text",
            "open positions: none",
            "trace complete.",
            "plain text",
            "no open holes; use 'up' or 'back'",
        ]

    def test_unknown_headword_for_hole_is_reported(self, trace_sim):
        assert drive(trace_sim, ["trace unknown-headword", "expand"]) == [
            "trace started.",
            "at: root",
            "unknown-headword",
            "open positions: none",
            "trace complete.",
            "unknown-headword",
            "no open holes; use 'up' or 'back'",
        ]
