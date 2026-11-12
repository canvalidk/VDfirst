"""The hypothesis set of an issued result is a view: it sorts and removes nothing."""

import json

import pytest

from correction_demo import build_demo_simulator as correction_simulator
from demand import Demand, InjectProvenance, Trace
from engine import VDInstance
from hypothesis_set import MEMBER_KIND_DESCRIPTIONS, build_hypothesis_set
from member_list_demo import build_demo_simulator, trace_object
from prediction_set import build_prediction_set
from simulator import Simulator


@pytest.fixture(scope="module")
def block_a():
    return build_prediction_set(trace_object(build_demo_simulator(), "A"))


def test_the_member_list_scene_sorts_into_prediction_theory_and_members(block_a):
    view = build_hypothesis_set(block_a)
    assert (view.issued_id, view.result, view.demand) == ("I33", "-23/10 m/s^2", "inertial-acceleration_A")
    assert view.prediction == (
        "The result '-23/10 m/s^2' holds for the demand 'inertial-acceleration_A' in the recorded context."
    )
    assert view.dictionary == "member-list prototype"
    assert view.counts() == {"theory": 13, "commitment": 9, "substitution": 10}
    assert len(view.question) == 1
    assert view.steps_used == 33 and view.steps_in_history == 0
    assert view.record_complete


def test_every_used_step_lands_in_exactly_one_place(block_a):
    view = build_hypothesis_set(block_a)
    placed = [step.id for step in view.theory] + [member.of for member in view.members]
    assert len(placed) == len(set(placed)) == view.steps_used - len(view.question)
    assert set(placed) | {"P0"} == set(block_a.issued[-1].prediction_ids)


def test_the_theory_side_says_how_each_definition_came_to_be_used(block_a):
    view = build_hypothesis_set(block_a)
    choices = [step.choice for step in view.theory]
    assert choices.count("forced") == 10 and choices.count("only") == 3 and "judged" not in choices
    assert [index for index, _ in view.entries_used] == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert not any(member.kind == "definition_choice" for member in view.members)
    first = view.theory[0]
    assert (first.id, first.entry_index, first.demand, first.choice) == ("P1", 0, "inertial-acceleration_A", "only")


def test_members_are_the_failures_of_what_a_person_contributed(block_a):
    view = build_hypothesis_set(block_a)
    by_step = {member.of: member for member in view.members}
    assert by_step["P4"].statement == (
        "The supplied response 'contribution_A_[A:spring:s1,R:spring:s2,A:gravity:A]' is not appropriate "
        "for the demand 'contribution_A'."
    )
    assert by_step["P10"].kind == "substitution"
    assert by_step["P10"].statement == (
        "What is meant by 'the negative of 20 N/m times -1 m' is not the same as what is meant by '20 N'."
    )
    assert all(member.id == f"not-{member.of}" for member in view.members)
    assert {member.kind for member in view.members} <= set(MEMBER_KIND_DESCRIPTIONS)


def test_the_view_changes_nothing_in_the_record(block_a):
    before = block_a.to_json()
    view = build_hypothesis_set(block_a)
    assert block_a.to_json() == before
    data = view.to_dict()
    assert data["counts"] == view.counts()
    assert json.loads(view.to_json()) == data
    data["members"].clear()
    assert len(view.members) == 19


def test_a_redo_has_its_own_set_and_the_mistake_stays_out_of_it():
    sim = correction_simulator()
    trace = Trace.start(sim, "force_cart_0")                                   # 0
    trace.expand_node(sim, trace.root, 0, 0, "apply E0")                       # 1
    calculation = trace.root.children()[0]
    for pos, text in enumerate(("2 kg", "5 m/s^2")):                           # 2, 3
        child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
        trace.inject_node(calculation, pos, child, text, "input")
    trace.reduce_node(calculation, "12 N", "mistake")                          # 4
    trace.issue("first answer")                                                # 5
    trace.unreduce_node(calculation, "reopen")                                 # 6
    trace.reduce_node(calculation, "10 N", "redone")                           # 7
    trace.issue("second answer")                                               # 8
    record = build_prediction_set(trace)
    first = build_hypothesis_set(record, "I5")
    second = build_hypothesis_set(record)
    assert (first.result, second.result, second.issued_id) == ("12 N", "10 N", "I8")
    assert [member.of for member in first.members] == ["P2", "P3", "P4"]
    assert [member.of for member in second.members] == ["P2", "P3", "P7"]
    assert first.steps_in_history == 1 and second.steps_in_history == 1
    assert "1 recorded steps are history" in second.render()
    with pytest.raises(ValueError, match="no issued result 'I99'"):
        build_hypothesis_set(record, "I99")


def test_a_choice_a_person_made_and_a_headword_left_as_text_are_members():
    instance = VDInstance("choices")
    instance.append_many([
        ("weight", "mass times gravity"),
        ("mass", "2 kg"),
        ("mass", "the quantity of matter"),
        ("gravity", "9.8 m/s^2"),
    ])
    sim = Simulator(instance)
    trace = Trace.start(sim, "weight")
    trace.expand_node(sim, trace.root, 0, 0, "apply the weight entry")
    trace.active = trace.root.children()[0]
    trace.recall_node(sim, trace.active, 0, 1, "the first mass entry, chosen over the second")
    trace.flatten_active()
    trace.issue("left in terms of gravity")
    view = build_hypothesis_set(build_prediction_set(trace))
    assert [(step.entry_index, step.choice) for step in view.theory] == [(0, "only"), (1, "judged")]
    kinds = {member.kind: member for member in view.members}
    assert set(kinds) == {"definition_choice", "reading"}
    assert kinds["definition_choice"].statement == (
        "Entry E1 is not the definition to use for the demand 'mass'; one of E2 is."
    )
    assert kinds["reading"].statement == (
        "Reading 'gravity' as plain text, with no entry applied, loses what the result needs."
    )
    text = view.render()
    assert "chosen by a person" in text and "Members: reading (1)" in text


def test_no_issued_result_no_set_and_gaps_are_reported():
    sim = correction_simulator()
    trace = Trace.start(sim, "5+6")
    with pytest.raises(ValueError, match="no result has been issued"):
        build_hypothesis_set(build_prediction_set(trace))
    gappy = Trace.start(sim, "mass_cart")
    gappy.root.resolve_recall(0, "2 kg", 1)      # filled without a recorded step
    gappy.issue("answer")
    view = build_hypothesis_set(build_prediction_set(gappy))
    assert not view.record_complete
    assert "The record has gaps" in view.render()
