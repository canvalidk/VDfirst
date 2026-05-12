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


class TestTraceBootstrap:

    def test_trace_starts_and_prints_state(self, trace_sim):
        assert drive(trace_sim, ["trace force"]) == [
            "trace started.",
            "{force}",
            "open positions: 0",
        ]

    def test_trace_with_no_headwords_is_immediately_complete(self, trace_sim):
        assert drive(trace_sim, ["trace plain text"]) == [
            "trace started.",
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


class TestExpand:

    def test_expand_default_open_position_and_move_to_child(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand", "state"]) == [
            "trace started.",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "{mass} times {acceleration}",
            "open positions: 0, 1",
        ]

    def test_expand_can_take_explicit_position(self, trace_sim):
        assert drive(trace_sim, ["trace force and mass", "expand 1"]) == [
            "trace started.",
            "{force} and {mass}",
            "open positions: 0, 1",
            "expanded E0 at position 1; now at child.",
        ]

    def test_expand_prompts_for_multi_entry_headword(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["trace mass", "expand", "2"]) == [
            "trace started.",
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
            "{force}",
            "open positions: 0",
            "invalid position",
        ]


class TestTraceRecall:

    def test_recall_inside_trace_fills_in_place(self, trace_sim):
        assert drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "state",
        ]) == [
            "trace started.",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "recalled E0 at position 0.",
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
            "{force}",
            "open positions: 0",
            "injected at position 0; now at child.",
            "{mass} of this object",
            "open positions: 0",
        ]

    def test_inject_empty_text_aborts(self, trace_sim):
        assert drive(trace_sim, ["trace force", "inject", ""]) == [
            "trace started.",
            "{force}",
            "open positions: 0",
            "inject aborted: no text",
        ]


class TestNavigationAndBack:

    def test_up_from_child_returns_to_parent(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand", "up", "state"]) == [
            "trace started.",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "moved up.",
            "{mass} times {acceleration}",
            "open positions: none",
        ]

    def test_up_at_root_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "up"]) == [
            "trace started.",
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
            "{force}",
            "open positions: 0",
            "already at root",
        ]


class TestHoleCommandEdges:

    def test_no_open_holes_message(self, trace_sim):
        assert drive(trace_sim, ["trace plain text", "recall"]) == [
            "trace started.",
            "plain text",
            "open positions: none",
            "trace complete.",
            "plain text",
            "no open holes; use 'up' or 'back'",
        ]

    def test_unknown_headword_for_hole_is_reported(self, trace_sim):
        assert drive(trace_sim, ["trace unknown-headword", "expand"]) == [
            "trace started.",
            "unknown-headword",
            "open positions: none",
            "trace complete.",
            "unknown-headword",
            "no open holes; use 'up' or 'back'",
        ]
