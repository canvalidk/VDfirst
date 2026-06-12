"""Tests for repl.py inspection command loop."""

import pytest

from engine import VDInstance
from repl import REPL
from simulator import Simulator


@pytest.fixture
def empty_sim() -> Simulator:
    return Simulator(VDInstance("empty"))


@pytest.fixture
def small_sim() -> Simulator:
    v = VDInstance("small")
    v.append_many([
        ("mass", "numerical property of a particle"),
        ("particle", "thing that has mass"),
        ("force", "cause of acceleration"),
    ])
    return Simulator(v)


@pytest.fixture
def sim_with_redefines() -> Simulator:
    v = VDInstance("redef")
    v.append_many([
        ("mass", "first definition"),
        ("particle", "thing"),
        ("mass", "second definition"),
        ("force", "cause of acceleration"),
        ("particle", "redefined thing"),
    ])
    return Simulator(v)


def drive(sim: Simulator, inputs: list[str]) -> list[str]:
    """Run REPL against a fixed input list. Return captured output lines."""
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
    return out


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


class TestLoopMechanics:

    def test_one_command_then_exhausted_input_exits_cleanly(self, empty_sim):
        assert drive(empty_sim, ["count"]) == [
            "0 entries, 0 distinct headwords"
        ]

    def test_empty_lines_are_ignored(self, small_sim):
        assert drive(small_sim, ["", "count"]) == [
            "3 entries, 3 distinct headwords"
        ]

    def test_whitespace_only_input_is_ignored(self, small_sim):
        assert drive(small_sim, ["   ", "count"]) == [
            "3 entries, 3 distinct headwords"
        ]

    def test_unknown_command_prints_rejection_and_continues(self, small_sim):
        assert drive(small_sim, ["foo", "count"]) == [
            "unknown command: foo",
            "3 entries, 3 distinct headwords",
        ]

    def test_exit_exits_cleanly(self, small_sim):
        assert drive(small_sim, ["exit", "count"]) == []

    def test_quit_exits_cleanly(self, small_sim):
        assert drive(small_sim, ["quit", "count"]) == []

    def test_keyboard_interrupt_prints_blank_line_and_continues(self, small_sim):
        out = []
        inputs = iter([KeyboardInterrupt, "count", EOFError])

        def input_fn(prompt: str) -> str:
            item = next(inputs)
            if isinstance(item, type) and issubclass(item, BaseException):
                raise item
            return item

        REPL(
            small_sim,
            input_fn=input_fn,
            print_fn=lambda *args: out.append(" ".join(str(a) for a in args)),
        ).run()

        assert out == ["", "3 entries, 3 distinct headwords"]


class TestHelp:

    def test_help_outside_trace_prints_command_groups(self, small_sim):
        assert drive(small_sim, ["help"]) == EXPECTED_HELP


class TestHeadwords:

    def test_small_sim_prints_sorted_headwords(self, small_sim):
        assert drive(small_sim, ["headwords"]) == [
            "force",
            "mass",
            "particle",
        ]

    def test_empty_dictionary_prints_nothing(self, empty_sim):
        assert drive(empty_sim, ["headwords"]) == []

    def test_argument_is_ignored(self, small_sim):
        assert drive(small_sim, ["headwords whatever"]) == [
            "force",
            "mass",
            "particle",
        ]

    def test_uppercase_command_works(self, small_sim):
        assert drive(small_sim, ["HEADWORDS"]) == [
            "force",
            "mass",
            "particle",
        ]

    def test_all_headwords_alias_works(self, small_sim):
        assert drive(small_sim, ["ALL_HEADWORDS"]) == [
            "force",
            "mass",
            "particle",
        ]


class TestCount:

    def test_small_sim(self, small_sim):
        assert drive(small_sim, ["count"]) == [
            "3 entries, 3 distinct headwords"
        ]

    def test_redefined_sim(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["count"]) == [
            "5 entries, 3 distinct headwords"
        ]

    def test_empty_sim(self, empty_sim):
        assert drive(empty_sim, ["count"]) == [
            "0 entries, 0 distinct headwords"
        ]

    def test_argument_is_ignored(self, small_sim):
        assert drive(small_sim, ["count whatever"]) == [
            "3 entries, 3 distinct headwords"
        ]


class TestRecallSingleEntry:

    def test_recalls_entry_text(self, small_sim):
        assert drive(small_sim, ["recall mass"]) == [
            "E0: numerical property of a particle"
        ]

    def test_unknown_headword(self, small_sim):
        assert drive(small_sim, ["recall unknown"]) == [
            "no entry for 'unknown'"
        ]

    def test_missing_argument(self, small_sim):
        assert drive(small_sim, ["recall"]) == [
            "usage: recall <headword>"
        ]

    def test_empty_quoted_argument_is_usage(self, small_sim):
        assert drive(small_sim, ['recall ""']) == [
            "usage: recall <headword>"
        ]

    def test_headword_argument_is_case_sensitive(self, small_sim):
        assert drive(small_sim, ["recall Mass"]) == [
            "no entry for 'Mass'"
        ]


class TestRecallMultiEntry:

    def test_user_picks_first_entry(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["recall mass", "0"]) == [
            "multiple entries for 'mass':",
            "  E0: first definition",
            "  E2: second definition",
            "E0: first definition",
        ]

    def test_user_picks_second_entry(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["recall mass", "2"]) == [
            "multiple entries for 'mass':",
            "  E0: first definition",
            "  E2: second definition",
            "E2: second definition",
        ]

    def test_user_picks_out_of_range_entry(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["recall mass", "99"]) == [
            "multiple entries for 'mass':",
            "  E0: first definition",
            "  E2: second definition",
            "invalid choice; aborted",
        ]

    def test_user_picks_non_integer(self, sim_with_redefines):
        assert drive(sim_with_redefines, ["recall mass", "xyz"]) == [
            "multiple entries for 'mass':",
            "  E0: first definition",
            "  E2: second definition",
            "invalid choice; aborted",
        ]


class TestNonMutation:

    def test_session_does_not_mutate_instance(self, sim_with_redefines):
        before = (
            sim_with_redefines.entry_count(),
            sim_with_redefines.headword_count(),
        )

        drive(sim_with_redefines, [
            "headwords",
            "count",
            "recall mass",
            "2",
            "recall unknown",
        ])

        after = (
            sim_with_redefines.entry_count(),
            sim_with_redefines.headword_count(),
        )
        assert after == before
