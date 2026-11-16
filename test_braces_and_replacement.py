"""Braces in the text of a trace, and values that go in through a definition.

Contract for specs/2026-11-15-braces-and-replacement-at-expansion.md:

    force                        still to be expanded
    {mass times acceleration}    expanded
    {mass}                       left unexpanded on purpose

The braces are text. Nothing reads them, and a person may take a pair out.
A value never answers a bare headword: it replaces the text of a definition.
"""

import copy
import json

import pytest

from demand import Demand, InjectProvenance, Trace, split_response
from engine import VDInstance
from member_list_demo import build_demo_simulator
from prediction_set import build_prediction_set
from repl import REPL
from simulator import Simulator
from workbench import apply_command, start_record, validate_record


@pytest.fixture
def sim() -> Simulator:
    instance = VDInstance("braces")
    instance.append_many([
        ("mass", "2 kg"),
        ("acceleration", "5 m/s^2"),
        ("force", "mass times acceleration"),
    ])
    return Simulator(instance)


@pytest.fixture
def frame_sim() -> Simulator:
    """A definition whose text still has headwords in it."""
    instance = VDInstance("measured acceleration")
    instance.append_many([
        ("point-particle", "an idealised object"),
        ("inertial-frame", "a frame in which free bodies move uniformly"),
        (
            "inertial-acceleration",
            "the acceleration of a point-particle as measured in an inertial-frame",
        ),
    ])
    return Simulator(instance)


def drive(sim: Simulator, inputs: list[str]) -> tuple[REPL, list[str], list[str]]:
    """Run the REPL as shipped: the offer at expansion is on."""
    out: list[str] = []
    prompts: list[str] = []
    it = iter(inputs)

    def input_fn(prompt: str) -> str:
        prompts.append(prompt)
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
    offers = [p for p in prompts if p.startswith(("replace ", "reduce "))]
    return repl, out, offers


# ── The convention ──────────────────────────────────────────────────


def test_bare_is_still_to_expand_and_braces_mark_a_headword_dealt_with(sim):
    trace = Trace.start(sim, "force")
    assert trace.root.text() == "force"
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    assert trace.root.text() == "{mass times acceleration}"
    calculation = trace.root.children()[0]
    trace.flatten_node(calculation, [0], "mass left as it is")
    assert trace.root.text() == "{{mass} times acceleration}"
    assert calculation.open_positions == [1]            # acceleration still needs expanding
    trace.expand_node(sim, calculation, 1, 1, "the acceleration entry")
    assert trace.root.text() == "{{mass} times {5 m/s^2}}"
    assert trace.is_complete


def test_recalled_text_and_a_reduced_result_keep_their_braces(sim):
    trace = Trace.start(sim, "force")
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    calculation = trace.root.children()[0]
    trace.recall_node(sim, calculation, 0, 0, "recall mass")
    trace.recall_node(sim, calculation, 1, 1, "recall acceleration")
    assert calculation.text() == "{2 kg} times {5 m/s^2}"
    trace.reduce_node(calculation, "10 N", "worked out")
    assert trace.root.text() == "{10 N}"


def test_braces_keep_where_a_nested_definition_begins_and_ends():
    # Without them this read "haze_A plus contribution_A divided by inertial-mass_A",
    # which a reader takes as haze plus (contribution over mass).
    demo = build_demo_simulator()
    trace = Trace.start(demo, "inertial-acceleration_A")
    trace.expand_node(demo, trace.root, 0, 0, "acceleration")
    trace.expand_node(demo, trace.root.children()[0], 0, 1, "net force")
    assert trace.root.text() == "{{haze_A plus contribution_A} divided by inertial-mass_A}"


def test_a_supplied_call_is_still_to_be_expanded_so_it_has_no_braces():
    demo = build_demo_simulator()
    trace = Trace.start(demo, "contribution_A")
    text = "contribution_A_[A:gravity:A]"
    child = Demand(demo.analyse(text), provenance=InjectProvenance(text))
    trace.inject_node(trace.root, 0, child, text, "the members acting on A")
    assert trace.root.text() == text
    assert child.open_positions == [0]


def test_the_text_alone_does_not_tell_a_one_headword_definition_from_a_headword_left_unexpanded():
    # Known limit of the convention: the impressed force of an action member is
    # defined as that member's action force, one headword and nothing else. Once
    # expanded it reads exactly as a headword left unexpanded would. The engine
    # knows the difference; the text does not show it.
    demo = build_demo_simulator()
    trace = Trace.start(demo, "impressed-force_A:spring:s1_A")
    trace.expand_node(demo, trace.root, 0, 4, "dispatch on action")
    assert trace.root.text() == "{action-force_spring:s1}"
    assert trace.root.children()[0].open_positions == [0]       # still to be expanded
    other = Trace.start(demo, "action-force_spring:s1")
    other.flatten_node(other.root, [0], "left as it is")
    assert other.root.text() == "{action-force_spring:s1}"
    assert other.root.open_positions == []                      # dealt with


# ── Taking braces out ───────────────────────────────────────────────


def test_braces_can_be_taken_out_and_put_back_as_a_recorded_edit(sim):
    trace = Trace.start(sim, "force")
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    event = trace.set_braces_node(trace.root, 0, False, "braces out")
    assert trace.root.text() == "mass times acceleration"
    assert event.kind == "clean"
    assert (event.change.stimulus, event.change.response) == (
        "{mass times acceleration}", "mass times acceleration",
    )
    assert event.change.position == 0
    claim = build_prediction_set(trace).predictions[-1]
    assert (claim.id, claim.operation, claim.kind) == ("P2", "clean", "meaning_preservation")
    assert claim.statement == (
        "What is meant by '{mass times acceleration}' is the same as what is meant by "
        "'mass times acceleration' in the recorded context."
    )
    trace.set_braces_node(trace.root, 0, True, "braces back")
    assert trace.root.text() == "{mass times acceleration}"
    result = build_prediction_set(trace)
    assert result.dependency_selection_complete
    assert result.current_prediction_ids == ("P0", "P1", "P2", "P3")


def test_only_braces_that_are_there_can_be_taken_out(sim):
    trace = Trace.start(sim, "force and mass")
    with pytest.raises(ValueError, match="still to be expanded"):
        trace.set_braces_node(trace.root, 0, False, "nothing there")
    trace.flatten_node(trace.root, [0], "left as it is")
    with pytest.raises(ValueError, match="already has its braces"):
        trace.set_braces_node(trace.root, 0, True, "already there")
    trace.set_braces_node(trace.root, 0, False, "out")
    with pytest.raises(ValueError, match="already has no braces"):
        trace.set_braces_node(trace.root, 0, False, "out again")
    with pytest.raises(ValueError, match="out of range"):
        trace.set_braces_node(trace.root, 7, False, "no such position")
    assert [event.kind for event in trace.events] == ["trace", "flatten", "clean"]


def test_a_headword_left_unexpanded_stays_dealt_with_when_its_braces_are_out(sim):
    # The engine does not read braces. With them out the text shows a bare
    # headword that is nonetheless finished: only the record tells.
    trace = Trace.start(sim, "mass")
    trace.flatten_node(trace.root, [0], "left as it is")
    assert trace.root.text() == "{mass}"
    assert trace.root.instances() == ("mass",)
    trace.set_braces_node(trace.root, 0, False, "out")
    assert trace.root.text() == "mass"
    assert trace.root.open_positions == []
    assert trace.is_complete
    assert trace.root.instances() == ()


def test_taking_braces_out_reopens_what_was_worked_out_from_the_text(sim):
    trace = Trace.start(sim, "force")
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    calculation = trace.root.children()[0]
    trace.recall_node(sim, calculation, 0, 0, "recall mass")
    trace.recall_node(sim, calculation, 1, 1, "recall acceleration")
    trace.reduce_node(trace.root, "a report", "consumer of the braced text")
    trace.set_braces_node(calculation, 0, False, "out")
    assert trace.root.reduced is None
    assert trace.root.text() == "{2 kg times {5 m/s^2}}"


def test_taking_braces_out_beneath_a_reduction_reopens_nothing(sim):
    trace = Trace.start(sim, "force")
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    calculation = trace.root.children()[0]
    trace.recall_node(sim, calculation, 0, 0, "recall mass")
    trace.recall_node(sim, calculation, 1, 1, "recall acceleration")
    trace.reduce_node(calculation, "10 N", "worked out")
    trace.reduce_node(trace.root, "a report", "consumer of the reduction")
    trace.set_braces_node(calculation, 0, False, "out")
    assert calculation.reduced == "10 N"
    assert trace.root.reduced == "a report"
    calculation.clear_reduction()
    assert trace.root.text() == "{2 kg times {5 m/s^2}}"


# ── A value replaces the text of a definition ───────────────────────


def test_a_replacement_at_expansion_is_three_recorded_steps(frame_sim):
    trace = Trace.start(frame_sim, "inertial-acceleration")
    entry = trace.expand_node(
        frame_sim, trace.root, 0, 2, "measured", replacement="5 m/s^2",
    )
    assert entry.kind == "expand"
    assert [event.kind for event in trace.events] == ["trace", "expand", "flatten", "reduce"]
    assert trace.root.text() == "{5 m/s^2}"
    assert trace.is_complete
    result = build_prediction_set(trace)
    assert [(p.id, p.kind) for p in result.predictions] == [
        ("P0", "normalization"),
        ("P1", "entry_application"),
        ("P2", "left_unexpanded"),
        ("P3", "meaning_preservation"),
    ]
    assert result.predictions[2].statement == (
        "The headwords 'point-particle', 'inertial-frame' are left unexpanded here; "
        "no entry is applied to them."
    )
    # The value answers the wording of one entry, not the headword.
    assert result.predictions[3].statement == (
        "What is meant by 'the acceleration of a {point-particle} as measured in an "
        "{inertial-frame}' is the same as what is meant by '5 m/s^2' in the recorded context."
    )
    # As for any reduction of an expanded demand, the replacement lists the steps
    # inside the definition's text. The entry step belongs to the position it
    # filled, and is in the support of the whole result.
    assert result.predictions[3].evidence.dependencies == (2,)
    assert result.dependency_selection_complete
    assert result.current_prediction_ids == ("P0", "P1", "P2", "P3")


def test_a_definition_without_headwords_needs_no_step_between(sim):
    trace = Trace.start(sim, "mass")
    trace.expand_node(sim, trace.root, 0, 0, "the mass entry", replacement="two kilograms")
    assert [event.kind for event in trace.events] == ["trace", "expand", "reduce"]
    change = trace.events[-1].change
    assert (change.stimulus, change.response) == ("2 kg", "two kilograms")


def test_a_replacement_naming_another_headword_is_refused_and_records_nothing(frame_sim):
    trace = Trace.start(frame_sim, "inertial-acceleration")
    for text in (
        "5 m/s^2 in the inertial-frame",       # a headword of the text, but not in braces
        "what the inertial-acceleration is",   # a headword that is not in the text
        "   ",
    ):
        with pytest.raises(ValueError):
            trace.expand_node(frame_sim, trace.root, 0, 2, "refused", replacement=text)
    assert len(trace.events) == 1
    assert trace.root.open_positions == [0]


# ── Responses may keep a headword left unexpanded ───────────────────


def test_a_replacement_may_keep_a_headword_of_the_text_in_braces(frame_sim):
    trace = Trace.start(frame_sim, "the inertial-acceleration")
    trace.expand_node(
        frame_sim, trace.root, 0, 2, "measured",
        replacement="5 m/s^2 for the {point-particle}",
    )
    child = trace.root.children()[0]
    assert child.instances() == ("point-particle",)
    assert trace.root.text() == "the {5 m/s^2 for the {point-particle}}"
    # The next response may carry it on, but only as it stood.
    assert trace.root.instances() == ("point-particle",)
    assert split_response(frame_sim, trace.root.instances(), "{point-particle}: 5 m/s^2") == (
        ("point-particle",), [],
    )
    assert split_response(frame_sim, trace.root.instances(), "point-particle: 5 m/s^2") == (
        (), ["point-particle"],
    )
    # inertial-frame was in the definition's text, but the replacement dropped it.
    assert split_response(frame_sim, trace.root.instances(), "in the {inertial-frame}") == (
        (), ["inertial-frame"],
    )


def test_a_reduction_drops_the_instances_it_does_not_carry(sim):
    trace = Trace.start(sim, "force")
    trace.expand_node(sim, trace.root, 0, 2, "the force entry")
    calculation = trace.root.children()[0]
    trace.flatten_node(calculation, [0, 1], "both left as they are")
    assert trace.root.instances() == ("mass", "acceleration")
    carried, others = split_response(sim, calculation.instances(), "{acceleration} times {mass}")
    assert (carried, others) == (("acceleration", "mass"), [])
    trace.reduce_node(calculation, "{acceleration} times {mass}", "reordered", instances=carried)
    assert trace.root.text() == "{{acceleration} times {mass}}"
    assert trace.root.instances() == ("acceleration", "mass")
    trace.reduce_node(trace.root, "a number", "nothing carried")
    assert trace.root.instances() == ()
    trace.unreduce_node(trace.root, "reopen")
    assert trace.root.instances() == ("acceleration", "mass")


# ── The REPL ────────────────────────────────────────────────────────


def test_repl_offers_to_replace_the_definition_before_it_goes_in(sim):
    repl, out, offers = drive(sim, ["set cleanup off", "trace force", "expand", "10 N", "", "events"])
    assert offers == [
        "replace E2 [mass times acceleration] (replacement or empty to expand as it is): ",
        "reduce root [{10 N}] (replacement or empty to skip): ",
    ]
    assert out[5:] == [
        "expanded E2 at position 0; text replaced.",
        "trace complete.",
        "{10 N}",
        "[0] trace: started from 'force'",
        "[1] expand: E2 at position 0",
        "[2] flatten: E2 at position 0: headwords left unexpanded by the replacement",
        "[3] reduce: E2 at position 0: text replaced",
    ]
    assert repl.trace is not None
    assert repl.trace.active is repl.trace.root     # nothing to do inside the replaced text


def test_repl_asks_once_about_a_definition_it_has_just_offered(sim):
    _, out, offers = drive(sim, ["set cleanup off", "trace mass", "expand", "", "", "state"])
    assert offers == [
        "replace E0 [2 kg] (replacement or empty to expand as it is): ",
        "reduce root [{2 kg}] (replacement or empty to skip): ",
    ]
    assert out[5:] == [
        "expanded E0 at position 0; now at child.",
        "trace complete.",
        "{2 kg}",
        "at: E0 @ parent pos 0",
        "2 kg",
        "open positions: none",
    ]


def test_repl_refuses_a_replacement_that_names_a_headword_and_expands_as_it_is(sim):
    repl, out, _ = drive(sim, [
        "set cleanup off", "set reduce off", "trace force", "expand", "more than the acceleration",
    ])
    assert out[-2:] == [
        "['acceleration'] are headwords; reduction takes non-headword prose only. "
        "To use the word literally, escape it; to reference it, expand. "
        "A headword left unexpanded in this text may be kept by writing it in braces.",
        "expanded E2 at position 0; now at child.",
    ]
    assert [event.kind for event in repl.trace.events] == ["trace", "expand"]


def test_repl_replacement_may_keep_a_headword_in_braces_and_a_later_reduce_may_carry_it(sim):
    repl, out, _ = drive(sim, [
        "set cleanup off", "set reduce off", "trace force", "expand", "{mass} times five",
        "reduce", "five times {mass}",
        "reduce", "five times mass",
    ])
    assert out[2:] == [
        "trace started.",
        "at: root",
        "force",
        "open positions: 0",
        "expanded E2 at position 0; text replaced.",
        "trace complete.",
        "{{mass} times five}",
        "current render:",
        "  {{mass} times five}",
        "reduced.",
        "current render:",
        "  five times {mass}",
        # Without its braces the headword is refused, as any headword is.
        "['mass'] are headwords; reduction takes non-headword prose only. "
        "To use the word literally, escape it; to reference it, expand. "
        "A headword left unexpanded in this text may be kept by writing it in braces.",
    ]
    assert repl.trace.root.reduced == "five times {mass}"
    assert repl.trace.root.instances() == ("mass",)


def test_repl_offer_can_be_switched_off(sim):
    _, out, offers = drive(sim, ["set replace off", "set reduce off", "trace force", "expand", "state"])
    assert offers == []
    assert out[0] == "replace policy: off."
    assert out[-3:] == ["at: E2 @ parent pos 0", "mass times acceleration", "open positions: 0, 1"]


def test_repl_set_replace_rejects_an_unknown_policy(sim):
    _, out, _ = drive(sim, ["set replace sometimes"])
    assert out == ["usage: set replace <on_expand|off>"]


def test_repl_unbrace_and_brace_are_recorded(sim):
    _, out, _ = drive(sim, [
        "set replace off", "set reduce off", "set cleanup off",
        "trace force", "expand", "up",
        "unbrace 0", "state", "brace 0", "state",
        "unbrace 5", "unbrace", "brace 0", "events",
    ])
    assert out[9:] == [
        "braces taken out.",
        "at: root",
        "mass times acceleration",
        "open positions: none",
        "braces put back.",
        "at: root",
        "{mass times acceleration}",
        "open positions: none",
        "position 5 out of range; valid: 0..0",
        "usage: unbrace <pos>",
        "position 0 already has its braces",
        "[0] trace: started from 'force'",
        "[1] expand: E2 at position 0",
        "[2] clean: root pos 0: braces taken out",
        "[3] clean: root pos 0: braces put back",
    ]


def test_repl_brace_commands_need_a_trace(sim):
    _, out, _ = drive(sim, ["unbrace 0", "brace 0"])
    assert out == ["not in a trace; use 'trace <text>' to start one"] * 2


# ── The bridge ──────────────────────────────────────────────────────


DICTIONARY = {
    "name": "bridge braces",
    "entries": [["force", "mass times acceleration"], ["mass", "2 kg"], ["acceleration", "5 m/s^2"]],
}


def frame(record, identity="F"):
    return next(item for item in record["snapshots"][-1]["frames"] if item["id"] == identity)


def test_bridge_frames_say_which_positions_show_braces():
    record = start_record(DICTIONARY, "force")
    assert frame(record)["render"] == "force"
    assert frame(record)["holes"][0]["braced"] is False
    record = apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 0})
    assert frame(record)["render"] == "{mass times acceleration}"
    assert frame(record)["holes"][0]["braced"] is True
    record = apply_command(record, {"operation": "flatten", "frame_id": "F/0", "position": 0})
    assert frame(record, "F/0")["render"] == "{mass} times acceleration"
    assert [hole["braced"] for hole in frame(record, "F/0")["holes"]] == [True, False]
    assert record["snapshots"][-1]["prediction_set"]["schema_version"] == 6


def test_bridge_takes_braces_out_as_one_recorded_command():
    record = start_record(DICTIONARY, "force")
    record = apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 0})
    record = apply_command(record, {
        "operation": "braces", "frame_id": "F", "position": 0, "shown": False, "note": "plain",
    })
    assert frame(record)["render"] == "mass times acceleration"
    assert frame(record)["holes"][0]["braced"] is False
    claim = record["snapshots"][-1]["prediction_set"]["predictions"][-1]
    assert (claim["operation"], claim["kind"]) == ("clean", "meaning_preservation")
    assert claim["evidence"]["stimulus"] == "{mass times acceleration}"
    assert claim["evidence"]["response"] == "mass times acceleration"
    assert len(record["events"]) == len(record["commands"]) + 1
    assert validate_record(json.loads(json.dumps(record))) == record
    record = apply_command(record, {"operation": "braces", "frame_id": "F", "position": 0, "shown": True})
    assert frame(record)["render"] == "{mass times acceleration}"


@pytest.mark.parametrize("bad_command", [
    {"operation": "braces", "frame_id": "F", "position": 0, "shown": "no"},
    {"operation": "braces", "frame_id": "F", "position": 0},
    {"operation": "braces", "frame_id": "F", "shown": False},
    {"operation": "braces", "frame_id": "F", "position": 0, "shown": True},      # already braced
    {"operation": "braces", "frame_id": "F/0", "position": 0, "shown": False},   # still to be expanded
    {"operation": "braces", "frame_id": "F", "position": 3, "shown": False},
    {"operation": "inject", "frame_id": "F/0", "position": 0, "response": "2 kg"},
])
def test_bridge_refusals_leave_the_record_unchanged(bad_command):
    record = start_record(DICTIONARY, "force")
    record = apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 0})
    before = copy.deepcopy(record)
    with pytest.raises(ValueError):
        apply_command(record, bad_command)
    assert record == before


def test_bridge_value_goes_in_as_expand_then_reduce():
    # The bridge records one step per command, so a client sends the steps of
    # a replacement one by one: the entry, any headwords left unexpanded, the text.
    record = start_record(DICTIONARY, "mass")
    record = apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 1})
    record = apply_command(record, {"operation": "reduce", "frame_id": "F/0", "response": "two kilograms"})
    assert frame(record)["render"] == "{two kilograms}"
    claim = record["snapshots"][-1]["prediction_set"]["predictions"][-1]
    assert (claim["evidence"]["stimulus"], claim["evidence"]["response"]) == ("2 kg", "two kilograms")
    assert validate_record(json.loads(json.dumps(record))) == record
