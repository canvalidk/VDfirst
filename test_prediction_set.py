"""Trace evidence and prediction projection contracts."""

from dataclasses import FrozenInstanceError
import json

import pytest

from demand import Demand, ExpandProvenance, InjectProvenance, Trace
from engine import VDInstance
from prediction_set import Classification, build_prediction_set
from repl import REPL
from simulator import Simulator


@pytest.fixture
def sim():
    instance = VDInstance("prediction tests")
    instance.append_many([("mass", "2 kg"), ("force", "mass times 5")])
    return Simulator(instance)


def run(sim, commands):
    inputs = iter(commands)
    output = []

    def read(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    repl = REPL(sim, input_fn=read, print_fn=output.append)
    repl.run()
    return repl, output


def test_repeated_reductions_keep_exact_stimuli_after_clear(sim):
    trace = Trace.start(sim, "5+6")
    trace.reduce_node(trace.root, "11", "first")
    trace.reduce_node(trace.root, "eleven", "second")
    first = build_prediction_set(trace)
    trace.root.clear_reduction()
    trace.record_event("unreduce", "root")
    later = build_prediction_set(trace)
    assert [(p.evidence.stimulus, p.evidence.response)
            for p in later.predictions if p.operation == "reduce"] == [
        ("5+6", "11"), ("11", "eleven"),
    ]
    assert [p.id for p in later.predictions] == ["P0", "P1", "P2"]
    assert later.predictions == first.predictions
    assert later.result == "5+6"
    assert first.result == "eleven"
    assert first.coverage_complete is False
    assert later.scope == "recorded trace history"


def test_snapshot_retains_local_arguments_and_provenance(sim):
    trace = Trace.start(sim, "force")
    child = Demand(sim.analyse("mass times 5"), provenance=ExpandProvenance(1))
    trace.root.resolve_expand(0, child, 1)
    child.resolve_recall(0, "2 kg", 0)
    trace.reduce_node(child, "10 N", "child")
    evidence = next(
        p for p in build_prediction_set(trace).predictions if p.operation == "reduce"
    ).evidence
    child.clean_recall_text(0, "3 kg")
    child.set_latents(["now ", " times 7"])
    assert evidence.stimulus == "2 kg times 5"
    assert evidence.before.address == (0,)
    assert evidence.before.latents == ("", " times 5")
    assert evidence.before.headwords == ("mass",)
    assert evidence.before.source_index == 1
    assert evidence.before.arguments[0].text == "2 kg"
    assert evidence.before.arguments[0].source_index == 0
    with pytest.raises(FrozenInstanceError):
        evidence.response = "different"


def test_identical_children_have_distinct_addresses_and_ids(sim):
    trace = Trace.start(sim, "mass and mass")
    for pos in (0, 1):
        child = Demand(sim.analyse("5+6"), provenance=InjectProvenance("5+6"))
        trace.inject_node(trace.root, pos, child, "5+6", "input")
        trace.reduce_node(child, "11", "same answer")
    claims = build_prediction_set(trace).predictions
    assert [p.id for p in claims] == ["P0", "P1", "P2", "P3", "P4"]
    assert [p.evidence.before.address for p in claims if p.operation == "reduce"] == [
        (0,), (1,),
    ]
    assert [p.evidence.position for p in claims if p.operation == "inject"] == [0, 1]


def test_injection_keeps_raw_response_before_analysis_or_reduction(sim):
    trace = Trace.start(sim, "force")
    child = Demand(sim.analyse("mass times 5"), provenance=InjectProvenance("mass times 5"))
    trace.inject_node(trace.root, 0, child, "mass times 5", "input")
    claim = build_prediction_set(trace).predictions[-1]
    assert claim.id == "P1"
    child.resolve_recall(0, "2 kg", 0)
    trace.reduce_node(child, "10 N", "answer")
    assert claim.kind == "supplied_input"
    assert claim.evidence.stimulus == "force"
    assert claim.evidence.response == "mass times 5"
    assert claim.evidence.after.render == "{mass} times 5"
    assert claim.classification.category == "unclassified"


def test_cleanup_records_changed_prose_even_under_reduction(sim):
    trace = Trace.start(sim, "the mass")
    trace.root.resolve_recall(0, "2 kg", 0)
    trace.reduce_node(trace.root, "an answer", "reduce")
    trace.clean_node(trace.root, ["a value of ", ""], "clean")
    claim = build_prediction_set(trace).predictions[-1]
    assert claim.evidence.stimulus == "the 2 kg"
    assert claim.evidence.response == "a value of 2 kg"
    assert claim.evidence.before.render == claim.evidence.after.render == "an answer"
    assert claim.kind == "meaning_preservation"


def test_cleanup_of_compressed_recall_records_actual_text(sim):
    trace = Trace.start(sim, "mass")
    trace.root.resolve_recall(0, "2 kg", 0, compressed=True)
    trace.clean_recall(trace.root, 0, "two kilograms", "clean")
    claim = build_prediction_set(trace).predictions[-1]
    assert claim.operation == "clean"
    assert claim.evidence.stimulus == "2 kg"
    assert claim.evidence.response == "two kilograms"
    assert claim.evidence.position == 0
    assert trace.root.text() == "mass"


def test_labels_never_verify_claims_and_projection_does_not_mutate(sim):
    trace = Trace.start(sim, "5+6")
    trace.reduce_node(trace.root, "12", "intentionally wrong")
    events = tuple(trace.events)
    annotations = {"P1": Classification("correct maths", "reader supplied")}
    result = build_prediction_set(trace, annotations)
    assert [p.id for p in result.predictions] == ["P0", "P1"]  # the question, then the reduction
    assert all(p.verification == "unchecked" for p in result.predictions)
    assert result.predictions[1].classification.category == "correct maths"
    assert result.predictions[0].classification.category == "unclassified"
    assert tuple(trace.events) == events
    assert trace.root.text() == "12"
    assert build_prediction_set(trace).predictions[1].classification.category == "unclassified"
    data = json.loads(result.to_json())
    assert data["predictions"][1]["evidence"]["stimulus"] == "5+6"
    assert data["predictions"][1]["evidence"]["response"] == "12"
    assert data["predictions"][1]["classification"]["note"] == "reader supplied"
    assert data["coverage_complete"] is False
    data["predictions"].clear()
    assert len(result.predictions) == 2


def test_incomplete_and_legacy_traces_do_not_invent_claims(sim):
    trace = Trace.start(sim, "force")
    trace.record_event("reduce", "old event without source text")
    trace.record_event("inject", "old input")
    trace.record_event("clean", "old wording change")
    trace.record_event("up", "navigation")
    trace.record_event("expand", "old entry application")
    trace.record_event("recall", "old recall")
    trace.record_event("flatten", "old flatten")
    result = build_prediction_set(trace)
    assert [p.id for p in result.predictions] == ["P0"]  # only the recorded question
    assert result.unrecorded_events == (1, 2, 3, 5, 6, 7)
    assert not result.dependency_selection_complete
    assert not result.trace_complete
    assert result.result == "{force}"


def test_a_trace_assembled_without_start_has_no_recorded_question(sim):
    root = Demand(sim.analyse("5+6"))
    trace = Trace(root=root, active=root)
    trace.reduce_node(root, "11", "response")
    result = build_prediction_set(trace)
    assert [p.kind for p in result.predictions] == ["meaning_preservation"]
    assert not result.dependency_selection_complete
    assert result.historical_prediction_ids == ()


def test_every_step_kind_is_listed_once_in_recorded_order():
    instance = VDInstance("step kinds")
    instance.append_many([
        ("weight", "mass times gravity near ground"),
        ("mass", "2 kg"),
        ("mass", "the quantity of matter"),
        ("gravity", "9.8 m/s^2"),
    ])
    sim = Simulator(instance)
    trace = Trace.start(sim, "weight")                                  # 0
    trace.expand_node(sim, trace.root, 0, 0, "apply the weight entry")  # 1
    trace.active = trace.root.children()[0]
    trace.recall_node(sim, trace.active, 0, 1, "recall the first mass entry")  # 2
    trace.flatten_active()                                              # 3: gravity left as it stands
    trace.reduce_node(trace.active, "19.6 N", "worked out")             # 4
    result = build_prediction_set(trace)
    assert [(p.id, p.operation, p.kind) for p in result.predictions] == [
        ("P0", "trace", "normalization"),
        ("P1", "expand", "entry_application"),
        ("P2", "recall", "entry_recall"),
        ("P3", "flatten", "left_unexpanded"),
        ("P4", "reduce", "meaning_preservation"),
    ]
    assert result.unrecorded_events == ()
    assert result.dependency_selection_complete
    assert result.current_prediction_ids == ("P0", "P1", "P2", "P3", "P4")
    by_id = {p.id: p for p in result.predictions}
    recall = by_id["P2"].evidence.entry
    assert recall.candidates == (1, 2)  # two entries define 'mass'; the choice is on record
    assert by_id["P2"].statement == (
        "According to 'step kinds', entry E1 defines 'mass' as '2 kg'; chosen over E2. "
        "Its text is inserted as it stands, without further expansion."
    )
    assert by_id["P1"].statement == (
        "According to 'step kinds', entry E0 defines 'weight' as "
        "'mass times gravity near ground'."
    )
    left = by_id["P3"].evidence
    assert (left.stimulus, left.position) == ("gravity", 1)
    assert left.after.arguments[1].resolution == "LiteralResolution"
    assert by_id["P3"].statement == (
        "The headword 'gravity' is left as plain text here; no entry is applied to it."
    )
    assert by_id["P4"].evidence.stimulus == "2 kg times gravity near ground"
    assert by_id["P4"].evidence.dependencies == (2, 3)


def test_flattening_several_headwords_is_one_recorded_step(sim):
    trace = Trace.start(sim, "mass and force")
    trace.flatten_active()
    claim = build_prediction_set(trace).predictions[-1]
    assert (claim.id, claim.kind) == ("P1", "left_unexpanded")
    assert claim.evidence.stimulus == claim.evidence.response == "mass, force"
    assert claim.evidence.position is None
    assert claim.statement == (
        "The headwords 'mass', 'force' are left as plain text here; no entry is applied to them."
    )


def test_recorded_entry_steps_refuse_what_the_dictionary_does_not_license(sim):
    trace = Trace.start(sim, "force and 5+6")
    with pytest.raises(ValueError, match="does not define"):
        trace.expand_node(sim, trace.root, 0, 0, "the mass entry for a force demand")
    with pytest.raises(ValueError, match="out of range"):
        trace.recall_node(sim, trace.root, 3, 1, "no such hole")
    trace.expand_node(sim, trace.root, 0, 1, "apply the force entry")
    with pytest.raises(ValueError, match="already resolved"):
        trace.recall_node(sim, trace.root, 0, 1, "filled already")
    assert [event.kind for event in trace.events] == ["trace", "expand"]


def test_reopening_keeps_evidence_of_what_was_set_aside(sim):
    trace = Trace.start(sim, "5+6")
    trace.reduce_node(trace.root, "12", "mistake")
    event = trace.unreduce_node(trace.root, "reopen")
    assert (event.change.stimulus, event.change.response) == ("12", "5+6")
    assert event.change.dependencies == (0, 1)  # the question and the response set aside
    assert event.change.before.reduction == "12" and event.change.after.reduction is None
    # A reopening asserts nothing, so it adds no candidate.
    assert [p.id for p in build_prediction_set(trace).predictions] == ["P0", "P1"]


def test_invalid_annotation_and_detached_node_are_rejected(sim):
    trace = Trace.start(sim, "force")
    with pytest.raises(ValueError, match="unknown prediction"):
        build_prediction_set(trace, {"P9": Classification("parameter input")})
    with pytest.raises(ValueError, match="nonempty"):
        Classification(" ")
    with pytest.raises(ValueError, match="not attached"):
        trace.reduce_node(Demand(sim.analyse("5+6")), "11", "bad node")
    with pytest.raises(ValueError, match="not fully resolved"):
        trace.reduce_node(trace.root, "11", "not ready")
    assert len(trace.events) == 1
    assert trace.root.reduced is None


def test_repl_prediction_flow_and_json_export(sim):
    repl, output = run(sim, [
        "set cleanup off", "set reduce off", "trace mass",
        "inject", "5+6", "reduce", "11",
        "classify P1 parameter input", "classify P2 correct maths",
        "predictions", "predictions json",
    ])
    result = json.loads(output[-1])
    assert result["result"] == "11"
    assert [(p["id"], p["classification"]["category"]) for p in result["predictions"]] == [
        ("P0", "unclassified"), ("P1", "parameter input"), ("P2", "correct maths"),
    ]
    assert all(p["verification"] == "unchecked" for p in result["predictions"])
    assert any("P2 [correct maths]" in line for line in output)
    assert repl.trace.root.text() == "11"


@pytest.mark.parametrize("commands", [
    ["set reduce off", "trace 5+6", "reduce", "11"],
    ["set reduce off", "trace 5+6", "fold", "11"],
    ["trace mass", "inject", "5+6", "11", ""],
])
def test_all_reduction_paths_record_sources(sim, commands):
    repl, _ = run(sim, ["set cleanup off"] + commands)
    reductions = [
        p for p in build_prediction_set(repl.trace).predictions if p.operation == "reduce"
    ]
    assert len(reductions) == 1
    assert reductions[0].evidence.stimulus == "5+6"
    assert reductions[0].evidence.response == "11"


@pytest.mark.parametrize("commands, expected", [
    (["set cleanup off", "trace prose", "tidy active", "new prose"], ("prose", "new prose")),
    (["trace mass", "recall", "two kilograms"], ("2 kg", "two kilograms")),
    (["trace mass", "inject", "prose", "new prose"], ("prose", "new prose")),
    (
        ["set cleanup off", "trace mass", "recall", "tidy active", "", "", "two kilograms"],
        ("2 kg", "two kilograms"),
    ),
])
def test_all_cleanup_paths_record_sources(sim, commands, expected):
    repl, _ = run(sim, ["set reduce off"] + commands)
    claims = [p for p in build_prediction_set(repl.trace).predictions if p.operation == "clean"]
    assert len(claims) == 1
    assert (claims[0].evidence.stimulus, claims[0].evidence.response) == expected


def test_repl_expand_recall_and_flatten_reach_the_list(sim):
    repl, output = run(sim, [
        "set cleanup off", "set reduce off", "trace force and mass",
        "expand", "flatten", "up", "recall 1", "predictions",
    ])
    result = build_prediction_set(repl.trace)
    assert [(p.operation, p.kind) for p in result.predictions] == [
        ("trace", "normalization"),
        ("expand", "entry_application"),
        ("flatten", "left_unexpanded"),
        ("recall", "entry_recall"),
    ]
    assert result.result == "mass times 5 and 2 kg"
    assert result.unrecorded_events == ()
    assert result.dependency_selection_complete
    assert set(result.current_prediction_ids) == {p.id for p in result.predictions}
    application, left, recall = result.predictions[1:]
    assert (application.evidence.entry.index, application.evidence.stimulus) == (1, "force")
    assert left.evidence.before.address == (0,)  # inside the applied entry
    assert (recall.evidence.entry.index, recall.evidence.response) == (0, "2 kg")
    assert any("entry_application at root hole 0" in line for line in output)
    assert not any("events missing evidence" in line for line in output)


def test_repl_resets_annotations_and_rejects_bad_commands(sim):
    repl, output = run(sim, [
        "predictions", "classify P1 correct maths", "set reduce off",
        "trace 5+6", "reduce", "11", "classify P1 correct maths",
        "classify P99 maths", "classify P1", "predictions nope",
        "cancel", "trace 6+7", "reduce", "13", "predictions json",
    ])
    assert output.count("not in a trace; use 'trace <text>' to start one") == 2
    assert "unknown prediction: P99" in output
    assert "usage: classify <id> <category>" in output
    assert "usage: predictions [json]" in output
    fresh = json.loads(output[-1])["predictions"]
    assert [p["id"] for p in fresh] == ["P0", "P1"]  # P1 was labelled in the cancelled trace
    assert all(p["classification"]["category"] == "unclassified" for p in fresh)
    assert repl.prediction_classifications == {}


def test_rejected_or_skipped_reduction_does_not_generate_claim(sim):
    repl, _ = run(sim, [
        "set reduce off", "trace 5+6", "reduce", "mass", "reduce", "",
    ])
    assert [p.id for p in build_prediction_set(repl.trace).predictions] == ["P0"]
