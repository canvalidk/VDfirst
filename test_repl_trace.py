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


@pytest.fixture
def sim_with_cycle() -> Simulator:
    v = VDInstance("cycle")
    v.append_many([
        ("velocity", "rate of change of position"),
        ("momentum", "mass times velocity"),
        ("mass", "momentum divided by velocity"),
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
    help_line(
        "set cleanup <policy>",
        "cleanup offers: on_settled_only|on_every_resolution|off",
    ),
    help_line("set reduce <on_settle|off>", "toggle reduce offers on settle"),
    help_line("trace <text>", "start a new trace"),
    "",
    "trace-only:",
    help_line("cancel", "abandon the entire trace"),
    help_line("events", "show trace event history"),
    help_line("expand [pos]", "expand an open hole into a dictionary entry"),
    help_line("flatten [pos|all]", "make active open holes inert literals"),
    help_line("fold", "offer reduce across settled nodes, leaves-up"),
    help_line("go to N, goto N", "move active focus to worklist entry N"),
    help_line("inject [pos]", "fill an open hole with user-supplied text"),
    help_line("onward", "leave settled frames for the deepest open ancestor"),
    help_line("reduce", "replace the active node's render with equivalent text"),
    help_line("return", "return resolved active demand to its parent"),
    help_line("state", "show the active demand"),
    help_line(
        "tidy [scope]",
        "sweep settled prose for cleanup (active|subtree|all)",
    ),
    help_line("unreduce", "clear the active node's reduction"),
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

    def test_flatten_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["flatten"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_events_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["events"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_return_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["return"]) == [
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
            "",
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
            "",
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
            "",
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


class TestFlatten:

    def test_flatten_resolves_all_active_open_positions(self, trace_sim):
        assert drive(trace_sim, [
            "trace force",
            "expand",
            "flatten",
            "",
            "",
            "state",
        ]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "flattened positions 0, 1.",
            "trace complete.",
            "mass times acceleration",
            "at: E2 @ parent pos 0",
            "mass times acceleration",
            "open positions: none",
        ]

    def test_flatten_can_resolve_one_position(self, trace_sim):
        assert drive(trace_sim, [
            "trace force",
            "expand",
            "flatten 1",
            "state",
        ]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "expanded E2 at position 0; now at child.",
            "flattened position 1.",
            "at: E2 @ parent pos 0",
            "{mass} times acceleration",
            "open positions: 0",
        ]

    def test_flatten_all_alias_matches_default(self, trace_sim):
        out = drive(trace_sim, ["trace force", "expand", "flatten all"])
        assert out[-3:] == [
            "flattened positions 0, 1.",
            "trace complete.",
            "mass times acceleration",
        ]

    def test_flattened_terms_can_be_exported_as_escaped_text(self, trace_sim):
        repl, _ = drive_repl(trace_sim, [
            "trace force",
            "expand",
            "flatten",
        ])

        assert repl.trace is not None
        escaped = repl.trace.active.escaped_text()
        assert escaped == "`mass` times `acceleration`"
        analysed = trace_sim.analyse(escaped)
        assert analysed.order == 0
        assert analysed.text == "mass times acceleration"

    def test_flatten_leaves_resolved_positions_unchanged(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall 0",
            "",
            "flatten",
        ])
        assert out[-3:] == [
            "flattened position 1.",
            "trace complete.",
            "2 kg times acceleration",
        ]

    def test_flatten_with_no_open_positions_reports_noop(self, trace_sim):
        assert drive(trace_sim, ["trace plain text", "flatten"])[-1] == (
            "no open holes to flatten"
        )

    def test_flatten_rejects_invalid_position(self, trace_sim):
        assert drive(trace_sim, ["trace force", "flatten x"])[-1] == (
            "invalid position"
        )

    def test_flatten_rejects_already_resolved_position(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall 0",
            "",
            "flatten 0",
        ])
        assert out[-1] == "position 0 is already resolved"


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

    def test_return_from_resolved_child_moves_to_parent(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "trace force",
            "expand",
            "flatten",
            "",
            "",
            "return",
            "state",
        ])
        assert out[-4:] == [
            "returned to parent.",
            "at: root",
            "mass times acceleration",
            "open positions: none",
        ]
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root

    def test_return_records_event(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "flatten",
            "",
            "",
            "return",
            "events",
        ])
        assert out[-1] == "[3] return: E2 to root"

    def test_return_refuses_unresolved_child(self, trace_sim):
        assert drive(trace_sim, ["trace force", "expand", "return"])[-1] == (
            "active demand is not resolved"
        )

    def test_return_at_root_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "return"])[-1] == (
            "already at root"
        )

    def test_up_at_root_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["trace force", "up"]) == [
            "trace started.",
            "at: root",
            "{force}",
            "open positions: 0",
            "already at root",
        ]

    def test_cancel_exits_trace_mode(self, trace_sim):
        repl, out = drive_repl(trace_sim, ["trace force", "cancel"])
        assert out[-1] == "trace cancelled."
        assert repl.trace is None

    def test_back_is_no_longer_a_command(self, trace_sim):
        assert drive(trace_sim, ["trace force", "back"])[-1] == (
            "unknown command: back"
        )


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
            "",
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


class TestCycleInfo:

    def test_worklist_marks_cycle_suffix(self, sim_with_cycle):
        out = drive(sim_with_cycle, [
            "trace momentum",
            "expand",
            "expand 0",
            "worklist",
        ])
        assert out[-3:] == [
            worklist_line(" ", 0, "E1", 1, "velocity"),
            worklist_line("*", 1, "E2", 0, "momentum"),
            worklist_line("*", 2, "E2", 1, "velocity")
            + "  (cycle: open at E1)",
        ]

    def test_worklist_no_suffix_when_acyclic(self, trace_sim):
        out = drive(trace_sim, ["trace force", "expand", "worklist"])
        assert out[-2:] == [
            worklist_line("*", 0, "E2", 0, "mass"),
            worklist_line("*", 1, "E2", 1, "acceleration"),
        ]

    def test_expand_warns_on_cycle_then_proceeds(self, sim_with_cycle):
        out = drive(sim_with_cycle, [
            "trace momentum",
            "expand",
            "expand 0",
            "expand 1",
        ])
        assert out[-2:] == [
            "note: 'velocity' is already open at E1; "
            "expanding will revisit it.",
            "expanded E0 at position 1; now at child.",
        ]


class TestReduceCommand:

    def test_reduce_on_settled_active_node(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "15",
        ])
        assert out[-4:] == [
            "current render:",
            "  2 kg times 5 m/s^2",
            "reduced.",
            "returned to parent.",
        ]
        assert repl.trace is not None
        assert repl.trace.root.children()[0].reduced == "15"
        assert repl.trace.root.text() == "15"

    def test_reduce_pops_one_frame_on_success(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "15",
        ])
        assert out[-1] == "returned to parent."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root

    def test_reduce_failure_does_not_pop(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "mass times 5",
        ])
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root.children()[0]

    def test_reduce_refused_when_unsettled(self, trace_sim):
        assert drive(trace_sim, ["trace force", "reduce"])[-1] == (
            "node is not fully resolved"
        )

    def test_reduce_rejects_headword_token(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "mass times 5",
        ])
        assert out[-1] == (
            "['mass'] are headwords; reduction takes non-headword "
            "prose only. To use the word literally, escape it; "
            "to reference it, expand."
        )

    def test_reduce_empty_input_aborts(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "",
        ])
        assert out[-1] == "reduce aborted: no text"

    def test_unreduce_clears_overlay(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "15",
            "reduce",
            "F = 15",
            "unreduce",
        ])
        assert out[-1] == "unreduced."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root
        assert repl.trace.root.reduced is None
        assert repl.trace.root.text() == "15"

    def test_unreduce_refused_when_not_reduced(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "unreduce",
        ])
        assert out[-1] == "node is not reduced"

    def test_state_marks_reduced_node(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "15",
            "reduce",
            "F = 15",
            "state",
        ])
        assert out[-4:] == [
            "at: root",
            "F = 15",
            "(reduced)",
            "open positions: none",
        ]

    def test_reduce_and_unreduce_record_events(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "reduce",
            "15",
            "reduce",
            "F = 15",
            "unreduce",
            "events",
        ])
        assert out[-4:] == [
            "[4] reduce: E2: 15",
            "[5] return: E2 to root",
            "[6] reduce: root: F = 15",
            "[7] unreduce: root",
        ]


class TestFold:

    def test_fold_offers_post_order(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "fold",
            "10",
            "F is 10",
        ])
        assert out[-9:] == [
            "fold: E2 @ parent pos 0",
            "current render:",
            "  2 kg times 5 m/s^2",
            "reduced.",
            "fold: root",
            "current render:",
            "  10",
            "reduced.",
            "fold complete: 2 reduced, 0 skipped.",
        ]
        assert repl.trace is not None
        assert repl.trace.root.reduced == "F is 10"

    def test_fold_skips_beneath_reduced_node(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "expand 0",
            "up",
            "recall 1",
            "reduce",
            "ten newtons",
            "fold",
            "",
        ])
        assert out[-4:] == [
            "fold: root",
            "current render:",
            "  ten newtons",
            "fold complete: 0 reduced, 1 skipped.",
        ]
        assert sum(line.startswith("fold: ") for line in out) == 1

    def test_fold_with_nothing_settled_reports_noop(self, trace_sim):
        assert drive(trace_sim, ["trace force", "fold"])[-1] == (
            "nothing to fold"
        )


class TestSettleOffers:

    def test_settle_cascade_offers_deepest_first(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "",
            "recall",
            "10",
            "F = 10",
        ])
        assert out[-4:] == [
            "reduced.",
            "reduced.",
            "trace complete.",
            "F = 10",
        ]
        assert repl.trace is not None
        assert repl.trace.root.children()[0].reduced == "10"
        assert repl.trace.root.reduced == "F = 10"

    def test_completion_announces_reduced_root(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "",
            "recall",
            "10",
            "F = 10",
        ])
        assert out[-2:] == [
            "trace complete.",
            "F = 10",
        ]

    def test_existing_output_unchanged_when_unreduced(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "",
            "recall",
        ])
        assert out[-2:] == [
            "trace complete.",
            "2 kg times 5 m/s^2",
        ]

    def test_set_reduce_off_disables_offers(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "10",
        ])
        assert out[-1] == "unknown command: 10"
        assert repl.trace is not None
        assert repl.trace.root.reduced is None

    def test_set_reduce_rejects_unknown_policy(self, trace_sim):
        assert drive(trace_sim, ["set reduce sometimes"])[-1] == (
            "usage: set reduce <on_settle|off>"
        )


class TestOnward:

    def test_onward_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["onward"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_onward_refused_when_active_has_open_work(self, trace_sim):
        assert drive(trace_sim, ["trace force", "onward"])[-1] == (
            "already at open work"
        )

    def test_onward_routes_to_deepest_unresolved_ancestor(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force and string",
            "expand 0",
            "recall",
            "recall",
            "onward",
        ])
        assert out[-1] == "onward to root."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root
        assert repl.trace.root.open_positions == [1]

    def test_onward_on_complete_trace_lands_at_root(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "onward",
        ])
        assert out[-1] == "onward to root."
        assert repl.trace is not None
        assert repl.trace.active is repl.trace.root

    def test_onward_records_event(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force and string",
            "expand 0",
            "recall",
            "recall",
            "onward",
            "events",
        ])
        assert out[-1] == "[4] onward: E2 to root"


class TestTidy:

    def test_tidy_outside_trace_is_rejected(self, trace_sim):
        assert drive(trace_sim, ["tidy"]) == [
            "not in a trace; use 'trace <text>' to start one",
        ]

    def test_tidy_rejects_unknown_scope(self, trace_sim):
        assert drive(trace_sim, ["trace force", "tidy everything"])[-1] == (
            "usage: tidy [active|subtree|all]"
        )

    def test_tidy_offers_gaps_and_cleans_node(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "tidy",
            "",
            " multiplied by ",
            "",
            "",
        ])
        assert out[-12:] == [
            "tidy: E2 @ parent pos 0",
            "  [0] ''",
            "  {mass}",
            "  [1] ' times '",
            "  {acceleration}",
            "  [2] ''",
            "cleaned.",
            "tidy: E2 @ parent pos 0 recall pos 0",
            "  [0] '2 kg'",
            "tidy: E2 @ parent pos 0 recall pos 1",
            "  [0] '5 m/s^2'",
            "tidy complete: 1 cleaned, 2 skipped.",
        ]
        assert repl.trace is not None
        assert repl.trace.active.text() == "2 kg multiplied by 5 m/s^2"

    def test_tidy_cleans_recall_text(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "tidy",
            "",
            "",
            "",
            "two kilograms",
        ])
        assert out[-1] == "tidy complete: 1 cleaned, 2 skipped."
        assert repl.trace is not None
        assert repl.trace.active.text() == "two kilograms times 5 m/s^2"

    def test_tidy_skips_cleaned_and_reoffers_skipped(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "tidy",
            "",
            "",
            "",
            "two kilograms",
            "",
            "tidy",
            "",
            "",
            "",
        ])
        node_headers = [
            line for line in out if line == "tidy: E2 @ parent pos 0"
        ]
        recall_zero_headers = [
            line for line in out
            if line == "tidy: E2 @ parent pos 0 recall pos 0"
        ]
        assert len(node_headers) == 2
        assert len(recall_zero_headers) == 1
        assert out[-1] == "tidy complete: 0 cleaned, 2 skipped."

    def test_tidy_rejects_headword_token(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "tidy",
            "",
            "mass heavy",
            "",
        ])
        assert (
            "['mass'] are headwords; cleanup edits non-headword "
            "prose only. To use the word literally, escape it; "
            "to reference it, expand."
        ) in out
        assert out[-1] == "tidy complete: 0 cleaned, 3 skipped."

    def test_tidy_skips_beneath_reduced_node(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "ten",
            "",
            "tidy",
            "tidy all",
            "",
            "",
        ])
        assert "nothing to tidy" in out
        assert [line for line in out if line == "tidy: root"] == [
            "tidy: root"
        ]
        assert not any(
            line.startswith("tidy: E2") for line in out
        )
        assert out[-1] == "tidy complete: 0 cleaned, 1 skipped."

    def test_tidy_active_reoffers_cleaned_targets(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "set reduce off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "tidy",
            "",
            "",
            "",
            "two kilograms",
            "",
            "tidy active",
            "",
            "",
            "",
            "",
        ])
        recall_zero_headers = [
            line for line in out
            if line == "tidy: E2 @ parent pos 0 recall pos 0"
        ]
        assert len(recall_zero_headers) == 2
        assert out[-1] == "tidy complete: 0 cleaned, 3 skipped."

    def test_tidy_active_masked_prints_note(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "trace force",
            "expand",
            "recall",
            "recall",
            "",
            "F is ten",
            "tidy active",
        ])
        assert (
            "note: this prose is masked by a reduction at root"
        ) in out
        assert out[-1] == "tidy complete: 0 cleaned, 3 skipped."


class TestCleanupOffers:

    def test_auto_offer_after_recall_cleans(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "2 kilograms",
            "state",
        ])
        assert out[-4:] == [
            "cleaned.",
            "at: E2 @ parent pos 0",
            "2 kilograms times {acceleration}",
            "open positions: 1",
        ]

    def test_auto_offer_records_event(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "2 kilograms",
            "events",
        ])
        assert out[-1] == "[3] clean: E2 pos 0"

    def test_auto_offer_rejects_headword_token(self, trace_sim):
        out = drive(trace_sim, [
            "trace force",
            "expand",
            "recall",
            "net mass",
        ])
        assert out[-1] == (
            "['mass'] are headwords; cleanup edits non-headword "
            "prose only. To use the word literally, escape it; "
            "to reference it, expand."
        )

    def test_inject_settled_child_gets_offer(self, trace_sim):
        out = drive(trace_sim, [
            "set reduce off",
            "trace force",
            "inject",
            "42 newtons",
            "forty-two newtons",
        ])
        assert out[-3:] == [
            "cleaned.",
            "trace complete.",
            "forty-two newtons",
        ]

    def test_expand_offer_under_on_every_resolution(self, trace_sim):
        repl, out = drive_repl(trace_sim, [
            "set cleanup on_every_resolution",
            "set reduce off",
            "trace force",
            "expand",
            "",
            " multiplied by ",
            "",
        ])
        assert out[-1] == "cleaned."
        assert repl.trace is not None
        assert repl.trace.active.text() == (
            "{mass} multiplied by {acceleration}"
        )

    def test_set_cleanup_off_disables_offers(self, trace_sim):
        out = drive(trace_sim, [
            "set cleanup off",
            "trace force",
            "expand",
            "recall",
            "state",
        ])
        assert out[-3:] == [
            "at: E2 @ parent pos 0",
            "2 kg times {acceleration}",
            "open positions: 1",
        ]

    def test_set_cleanup_rejects_unknown_policy(self, trace_sim):
        assert drive(trace_sim, ["set cleanup always"])[-1] == (
            "usage: set cleanup <on_settled_only|on_every_resolution|off>"
        )

    def test_set_unknown_name_prints_usage(self, trace_sim):
        assert drive(trace_sim, ["set foo bar"])[-1] == (
            "usage: set <reduce|cleanup> <policy>"
        )


class TestEvents:

    def test_trace_start_records_event(self, trace_sim):
        assert drive(trace_sim, ["trace force", "events"])[-1] == (
            "[0] trace: started from 'force'"
        )

    def test_expand_recall_inject_flatten_record_events(self, trace_sim):
        out = drive(trace_sim, [
            "trace force and string",
            "expand 0",
            "recall 0",
            "",
            "up",
            "inject 1",
            "mass",
            "flatten",
            "",
            "events",
        ])
        assert out[-5:] == [
            "[0] trace: started from 'force and string'",
            "[1] expand: E2 at position 0",
            "[2] recall: E0 at position 0",
            "[3] inject: position 1: mass",
            "[4] flatten: active position 0",
        ]


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
            "",
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
            "",
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
            "",
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
            "no open holes; use 'up' or 'onward'",
        ]

    def test_unknown_headword_for_hole_is_reported(self, trace_sim):
        assert drive(trace_sim, ["trace unknown-headword", "expand"]) == [
            "trace started.",
            "at: root",
            "unknown-headword",
            "open positions: none",
            "trace complete.",
            "unknown-headword",
            "no open holes; use 'up' or 'onward'",
        ]
