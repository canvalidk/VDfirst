"""Simulator and REPL integration tests for parameterized expansion."""

import pytest

from engine import VDInstance
from repl import REPL
from simulator import Simulator


@pytest.fixture
def calculus_sim() -> Simulator:
    vd = VDInstance("calculus")
    vd.append_many([
        ("velocity_t", "rate at time t"),
        (
            "inertial-acceleration_t",
            "derivative of velocity_t at time t",
        ),
    ])
    return Simulator(vd)


@pytest.fixture
def force_sim() -> Simulator:
    vd = VDInstance("force")
    vd.append_many([
        ("inertial-mass_p", "mass of p"),
        ("inertial-acceleration_p_t", "acceleration of p at t"),
        (
            "force_p_t",
            "inertial-mass_p multiply inertial-acceleration_p_t",
        ),
    ])
    return Simulator(vd)


def drive_repl(
    sim: Simulator,
    inputs: list[str],
) -> tuple[REPL, list[str]]:
    output: list[str] = []
    iterator = iter(inputs)

    def input_fn(prompt: str) -> str:
        try:
            return next(iterator)
        except StopIteration as exc:
            raise EOFError from exc

    repl = REPL(
        sim,
        input_fn=input_fn,
        print_fn=lambda *args: output.append(
            " ".join(str(arg) for arg in args)
        ),
    )
    repl.run()
    return repl, output


class TestSimulatorApplications:

    @pytest.mark.parametrize(
        "call",
        [
            "inertial-acceleration",
            "inertial-acceleration_t",
            "inertial-acceleration_3",
            "inertial-acceleration_T",
        ],
    )
    def test_entry_lookup_accepts_bare_and_supplied_calls(
        self,
        calculus_sim,
        call,
    ):
        assert calculus_sim.entry_indexes(call) == [1]

    def test_instantiated_entry_text_preserves_actual_spelling(
        self,
        calculus_sim,
    ):
        assert calculus_sim.instantiated_entry_text(
            1,
            "inertial-acceleration_T",
        ) == "derivative of velocity_T at time T"

    def test_partial_instantiation_leaves_unsupplied_formal(self, force_sim):
        assert force_sim.instantiated_entry_text(2, "force_Earth") == (
            "inertial-mass_Earth multiply "
            "inertial-acceleration_Earth_t"
        )


class TestParameterizedExpansion:

    def test_complete_application_is_instantiated_then_tokenised(
        self,
        calculus_sim,
    ):
        repl, output = drive_repl(
            calculus_sim,
            ["trace inertial-acceleration_3", "expand"],
        )
        assert output == [
            "trace started.",
            "at: root",
            "{inertial-acceleration_3}",
            "open positions: 0",
            "expanded E1 at position 0; now at child.",
        ]
        assert repl.trace is not None
        child = repl.trace.active
        assert child.definiens.render() == (
            "derivative of {velocity_3} at time 3"
        )

    def test_bare_application_leaves_formal_visible(self, calculus_sim):
        repl, _ = drive_repl(
            calculus_sim,
            ["trace inertial-acceleration", "expand"],
        )
        assert repl.trace is not None
        assert repl.trace.active.definiens.render() == (
            "derivative of {velocity_t} at time t"
        )

    def test_partial_application_instantiates_argument_segments(
        self,
        force_sim,
    ):
        repl, _ = drive_repl(force_sim, ["trace force_Earth", "expand"])
        assert repl.trace is not None
        assert repl.trace.active.definiens.headwords == [
            "inertial-mass_Earth",
            "inertial-acceleration_Earth_t",
        ]

    def test_over_application_reports_error_and_starts_no_trace(
        self,
        force_sim,
    ):
        repl, output = drive_repl(
            force_sim,
            ["trace force_Earth_3_extra"],
        )
        assert output == [
            "arity error: 'force_Earth_3_extra' supplies 3 arguments "
            "to 'force', which accepts 2"
        ]
        assert repl.trace is None


class TestParameterizedRecall:

    def test_inspection_recall_shows_instantiated_text(self, calculus_sim):
        _, output = drive_repl(
            calculus_sim,
            ["recall inertial-acceleration_3"],
        )
        assert output == [
            "E1: derivative of velocity_3 at time 3"
        ]

    def test_trace_recall_stores_instantiated_text(self, calculus_sim):
        repl, output = drive_repl(
            calculus_sim,
            ["trace inertial-acceleration_T", "recall"],
        )
        assert output[-3:] == [
            "recalled E1 at position 0.",
            "trace complete.",
            "derivative of velocity_T at time T",
        ]
        assert repl.trace is not None
        assert repl.trace.root.text() == (
            "derivative of velocity_T at time T"
        )
