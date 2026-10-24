"""Cross-branch integration and recorded-support regression tests."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from correction_demo import DEMO_ENTRIES, build_correction_demo
from demand import Demand, ExpandProvenance, Trace
from engine import VDInstance
from prediction_set import build_prediction_set
from repl import REPL
from simulator import Simulator


def simulator():
    dictionary = VDInstance("correction tests")
    dictionary.append_many(DEMO_ENTRIES)
    return Simulator(dictionary)


def expanded_trace():
    sim = simulator()
    trace = Trace.start(sim, "force_cart_0")
    calculation = Demand(
        sim.analyse(sim.instantiated_entry_text(0, "force_cart_0")),
        provenance=ExpandProvenance(0),
    )
    trace.root.resolve_expand(0, calculation, 0)
    calculation.resolve_recall(0, "2 kg", 1)
    calculation.resolve_recall(1, "5 m/s^2", 2)
    return trace, calculation


def test_demo_keeps_mistake_history_and_selects_corrected_support():
    stages = build_correction_demo()
    assert [s.prediction_set.result for s in stages] == [
        "2 kg times 5 m/s^2", "12 N", "Prediction: 12 N",
        "2 kg times 5 m/s^2", "Prediction: 10 N",
    ]
    before = stages[2].prediction_set
    reopened = stages[3].prediction_set
    final = stages[4].prediction_set
    assert before.current_prediction_ids == ("P2", "P3", "P4", "P5")
    assert reopened.current_prediction_ids == ("P2", "P3")
    assert final.current_prediction_ids == ("P2", "P3", "P7", "P8")
    assert final.historical_prediction_ids == ("P4", "P5")
    assert before.result == "Prediction: 12 N"  # frozen earlier stage
    assert final.predictions[:4] == before.predictions
    assert final.predictions[-2].evidence.stimulus == "2 kg times 5 m/s^2"
    assert final.predictions[-1].evidence.dependencies == (2, 3, 7)
    assert all(s.prediction_set.dependency_selection_complete for s in stages)
    assert all(not s.prediction_set.coverage_complete for s in stages)
    assert all(p.verification == "unchecked" for p in final.predictions)


def test_demo_records_instantiated_demands_and_local_arguments():
    final = build_correction_demo()[-1].prediction_set
    assert [p.evidence.stimulus for p in final.predictions[:2]] == [
        "mass_cart", "acceleration_cart_0",
    ]
    correction = final.predictions[-2].evidence
    assert correction.before.address == (0,)
    assert correction.before.source_index == 0
    assert correction.before.headwords == ("mass_cart", "acceleration_cart_0")
    assert [a.text for a in correction.before.arguments] == ["2 kg", "5 m/s^2"]


def test_replacing_an_overlay_keeps_the_consumed_claim():
    trace = Trace.start(simulator(), "5+6")
    trace.reduce_node(trace.root, "11", "first response")
    trace.reduce_node(trace.root, "eleven", "response to the overlay")
    result = build_prediction_set(trace)
    assert result.current_prediction_ids == ("P1", "P2")
    assert result.historical_prediction_ids == ()
    assert result.predictions[-1].evidence.dependencies == (1,)
    assert result.predictions[-1].evidence.stimulus == "11"


def test_reopening_then_correcting_drops_the_old_claim_from_current_support():
    trace = Trace.start(simulator(), "5+6")
    trace.reduce_node(trace.root, "12", "mistake")
    trace.unreduce_node(trace.root, "reopen")
    trace.reduce_node(trace.root, "11", "corrected response")
    result = build_prediction_set(trace)
    assert result.current_prediction_ids == ("P3",)
    assert result.historical_prediction_ids == ("P1",)
    assert result.predictions[-1].evidence.stimulus == "5+6"
    assert result.predictions[-1].evidence.dependencies == ()


@pytest.mark.parametrize("change", ["unreduce", "replace", "cleanup", "recall cleanup"])
def test_changing_a_child_invalidates_consuming_overlays(change):
    trace, calculation = expanded_trace()
    if change in ("unreduce", "replace"):
        trace.reduce_node(calculation, "12 N", "old response")
    trace.reduce_node(trace.root, "old report", "consumer")
    if change == "unreduce":
        trace.unreduce_node(calculation, "reopen")
    elif change == "replace":
        trace.reduce_node(calculation, "10 N", "replace")
    elif change == "cleanup":
        trace.clean_node(calculation, ["", " multiplied by ", ""], "wording")
    else:
        trace.clean_recall(calculation, 0, "two kilograms", "wording")
    assert trace.root.reduced is None
    assert trace.root.text() != "old report"


def test_masked_cleanup_only_becomes_current_after_reopening():
    trace, calculation = expanded_trace()
    trace.reduce_node(calculation, "10 N", "calculation")
    trace.reduce_node(trace.root, "report", "consumer")
    trace.clean_node(calculation, ["", " multiplied by ", ""], "masked wording")
    masked = build_prediction_set(trace)
    assert trace.root.text() == "report"
    assert masked.current_prediction_ids == ("P1", "P2")
    assert masked.historical_prediction_ids == ("P3",)
    trace.unreduce_node(calculation, "show the edited product")
    reopened = build_prediction_set(trace)
    assert reopened.result == "2 kg multiplied by 5 m/s^2"
    assert reopened.current_prediction_ids == ("P3",)
    assert reopened.historical_prediction_ids == ("P1", "P2")


def test_compression_keeps_child_support():
    trace, calculation = expanded_trace()
    trace.reduce_node(calculation, "10 N", "calculation")
    trace.root.set_compression(0, True)
    result = build_prediction_set(trace)
    assert result.result == "force_cart_0"
    assert result.current_prediction_ids == ("P1",)


def test_low_level_response_mutations_report_an_incomplete_selection():
    trace = Trace.start(simulator(), "5+6")
    trace.reduce_node(trace.root, "12", "recorded")
    trace.root.set_reduction("11")
    result = build_prediction_set(trace)
    assert not result.dependency_selection_complete
    assert result.historical_prediction_ids == ()  # cannot infer history-only status
    trace.root.clear_reduction()
    trace.reduce_node(trace.root, "11", "recorded correction")
    repaired = build_prediction_set(trace)
    assert repaired.dependency_selection_complete
    assert repaired.current_prediction_ids == ("P2",)
    assert repaired.historical_prediction_ids == ("P1",)


def test_invalid_unreduce_does_not_mutate_history():
    trace = Trace.start(simulator(), "5+6")
    with pytest.raises(ValueError, match="not reduced"):
        trace.unreduce_node(trace.root, "invalid")
    with pytest.raises(ValueError, match="not attached"):
        trace.unreduce_node(Demand(simulator().analyse("5+6")), "detached")
    assert len(trace.events) == 1


def test_parameterized_repl_records_candidates_and_correction():
    """Use only commands available to a reader, including revisiting the child."""
    commands = iter([
        "set cleanup off", "set reduce off", "trace force_cart_0", "expand",
        "inject 0", "2 kg", "up", "inject 1", "5 m/s^2", "up",
        "reduce", "12 N", "reduce", "Prediction: 12 N",
        "down 0", "unreduce", "predictions", "reduce", "10 N",
        "reduce", "Prediction: 10 N", "predictions", "predictions json",
    ])
    output = []

    def read(prompt):
        try:
            return next(commands)
        except StopIteration:
            raise EOFError

    repl = REPL(simulator(), input_fn=read, print_fn=output.append)
    repl.run()
    calculation = repl.trace.root.children()[0]
    data = json.loads(output[-1])
    assert calculation.reduced == "10 N"
    assert data["result"] == "Prediction: 10 N"
    assert data["schema_version"] == 2
    assert data["dependency_selection_complete"]
    assert len(data["historical_prediction_ids"]) == 2
    assert any("[history only]" in line for line in output)
    assert any("[current support]" in line for line in output)
    assert data["predictions"][0]["evidence"]["stimulus"] == "mass_cart"


@pytest.mark.parametrize("change", ["node cleanup", "recall cleanup", "injection"])
def test_unrecorded_source_changes_leave_a_selection_gap(change):
    trace, calculation = expanded_trace()
    if change == "node cleanup":
        calculation.set_latents(["", " multiplied by ", ""])
    elif change == "recall cleanup":
        calculation.clean_recall_text(0, "three kilograms")
    else:
        trace = Trace.start(simulator(), "mass_cart")
        trace.root.resolve_inject(0, Demand(simulator().analyse("2 kg")))
    result = build_prediction_set(trace)
    assert not result.dependency_selection_complete
    assert result.historical_prediction_ids == ()


def test_reopening_invalidates_all_consumers_but_preserves_a_sibling():
    sim = simulator()
    trace = Trace.start(sim, "force_cart_0 and force_other_0")
    middle = Demand(sim.analyse("force_cart_0"))
    leaf = Demand(sim.analyse("2 kg times 5 m/s^2"))
    sibling = Demand(sim.analyse("5 kg times 2 m/s^2"))
    trace.root.resolve_expand(0, middle, 0)
    middle.resolve_expand(0, leaf, 0)
    trace.root.resolve_expand(1, sibling, 0)
    trace.reduce_node(leaf, "12 N", "mistake")
    trace.reduce_node(middle, "12 N", "consumer")
    trace.reduce_node(sibling, "10 N", "independent calculation")
    trace.reduce_node(trace.root, "combined report", "outer consumer")
    trace.unreduce_node(leaf, "reopen")
    assert middle.reduced is None
    assert trace.root.reduced is None
    assert sibling.reduced == "10 N"
    result = build_prediction_set(trace)
    assert result.current_prediction_ids == ("P3",)
    assert result.historical_prediction_ids == ("P1", "P2", "P4")


def test_down_rejects_invalid_navigation_without_changing_the_trace():
    output = []
    repl = REPL(simulator(), print_fn=output.append)
    repl.cmd_down("0")
    repl.cmd_trace("force_cart_0")
    root = repl.trace.root
    repl.cmd_down("")
    repl.cmd_down("-1")
    repl.cmd_down("99")
    assert repl.trace.active is root
    assert "usage: down <pos>" in output
    assert "no child at position -1" in output
    assert "no child at position 99" in output
    assert len(repl.trace.events) == 1


@pytest.mark.parametrize("mode", ["text", "json", "interactive"])
def test_demo_command_line(mode):
    command = [sys.executable, "-B", str(Path(__file__).with_name("correction_demo.py"))]
    if mode == "json":
        command.append("--json")
    if mode == "interactive":
        command.append("--interactive")
        completed = subprocess.run(
            command, text=True, input="\n".join([
                "set cleanup off", "set reduce off", "trace force_cart_0", "expand",
                "inject 0", "2 kg", "up", "inject 1", "5 m/s^2", "up",
                "reduce", "12 N", "reduce", "Prediction: 12 N",
                "down 0", "unreduce", "reduce", "10 N",
                "reduce", "Prediction: 10 N", "predictions", "quit", "",
            ]), capture_output=True, check=True,
        )
        assert "current render: Prediction: 10 N" in completed.stdout
        assert "[history only]" in completed.stdout
        assert "unknown command" not in completed.stdout
        return
    output = subprocess.check_output(command, text=True, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if mode == "json":
        data = json.loads(output)
        assert data["scripted_responses"]
        assert data["stages"][-1]["prediction_set"]["result"] == "Prediction: 10 N"
    else:
        assert "4. Calculation reopened" in output
        assert "P4 [history only; calculation; unchecked]" in output
        assert "P7 [current support; calculation; unchecked]" in output
