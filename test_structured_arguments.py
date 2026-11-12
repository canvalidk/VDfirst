"""Structured arguments, clause patterns, and choice of definition by form."""

import json

import pytest

from application import (
    FormalPattern,
    HeadwordApplicationError,
    HeadwordArityError,
    HeadwordCall,
    HeadwordSignature,
    HeadwordSignatureConflictError,
    instantiate_definition,
    is_value,
    list_items,
    scan_value,
    tagged_value,
)
from demand import Trace
from engine import Tokeniser, VDInstance
from member_list_demo import (
    DEMO_ENTRIES, MEMBERS, build_demo_simulator, forced_by_form, trace_object,
)
from prediction_set import build_prediction_set
from repl import REPL
from simulator import Simulator
from workbench import apply_command, start_record, validate_record


# ── Values ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "s1", "reference-frame", "[]", "[a]", "[a,b,c]", "A:s1", "A:spring:s1",
    "[A:spring:s1,R:spring:s2]", "[a,[b,c],T:[d]]", "T:[]",
])
def test_values_are_atoms_lists_and_tagged_values(text):
    assert is_value(text)


@pytest.mark.parametrize("text", [
    "", "[", "[a,]", "[,a]", "[a b]", "a:", ":a", "[a|b]", "a_b", "[a]]", "a,b",
])
def test_malformed_values_are_rejected(text):
    assert not is_value(text)


def test_scanning_stops_where_the_value_stops():
    assert scan_value("p: next", 0) == 1          # a colon with no value after it is punctuation
    assert scan_value("p. Next", 0) == 1
    assert scan_value("A:s1, then", 0) == 4
    assert scan_value("[a,b] and", 0) == 5
    assert scan_value("[a, b]", 0) is None        # no spaces inside a list
    assert scan_value(" x", 0) is None


def test_lists_and_tags_come_apart_at_the_top_level_only():
    assert list_items("[]") == ()
    assert list_items("[a,[b,c],T:[d]]") == ("a", "[b,c]", "T:[d]")
    assert list_items("a") is None and list_items("A:[x]") is None
    assert tagged_value("A:spring:s1") == ("A", "spring:s1")
    assert tagged_value("T:[a,b]") == ("T", "[a,b]")
    assert tagged_value("s1") is None and tagged_value("[A:s1]") is None


# ── Formals and signatures ──────────────────────────────────────────


def test_a_formal_is_a_name_or_one_of_three_patterns():
    assert FormalPattern.parse("p").kind == "name"
    assert FormalPattern.parse("[]").kind == "empty"
    cons = FormalPattern.parse("[m|rest]")
    assert (cons.kind, cons.names) == ("cons", ("m", "rest"))
    tag = FormalPattern.parse("A:x")
    assert (tag.kind, tag.tag, tag.names) == ("tag", "A", ("x",))
    for bad in ("[m|]", "[|rest]", "[m]", "[m|rest|more]", "A:", "A:3", "[m,rest]", "A:x:y"):
        assert FormalPattern.parse(bad) is None


def test_patterns_bind_names_or_refuse_the_form():
    assert FormalPattern.parse("p").bind("[a,b]") == (("p", "[a,b]"),)
    assert FormalPattern.parse("[]").bind("[]") == ()
    assert FormalPattern.parse("[]").bind("[a]") is None
    assert FormalPattern.parse("[]").bind("a") is None
    assert FormalPattern.parse("[m|rest]").bind("[a]") == (("m", "a"), ("rest", "[]"))
    assert FormalPattern.parse("[m|rest]").bind("[a,b,c]") == (("m", "a"), ("rest", "[b,c]"))
    assert FormalPattern.parse("[m|rest]").bind("[]") is None
    assert FormalPattern.parse("A:x").bind("A:spring:s1") == (("x", "spring:s1"),)
    assert FormalPattern.parse("A:x").bind("R:spring:s1") is None
    assert FormalPattern.parse("A:x").bind("a:spring:s1") is None    # tags are case-sensitive
    assert FormalPattern.parse("A:x").bind("A") is None


def test_signature_with_patterns_parses_and_keeps_its_text():
    signature = HeadwordSignature.parse("contribution_p_[m|rest]")
    assert (signature.stem, signature.formals, signature.arity) == ("contribution", ("p", "[m|rest]"), 2)
    assert signature.text == "contribution_p_[m|rest]"
    assert signature.is_patterned
    assert not HeadwordSignature.parse("force_p_t").is_patterned


@pytest.mark.parametrize("headword", ["f_[a|a]", "f_x_[x|t]", "f_A:x_x", "f_[a|]", "f_[a,b]", "f_A:"])
def test_invalid_patterned_signatures_are_rejected(headword):
    with pytest.raises(HeadwordApplicationError):
        HeadwordSignature.parse(headword)


def test_matching_ignores_positions_the_call_leaves_unsupplied():
    base = HeadwordSignature.parse("contribution_p_[]")
    step = HeadwordSignature.parse("contribution_p_[m|rest]")
    assert base.matches(HeadwordCall.parse("contribution_A_[]"))
    assert not step.matches(HeadwordCall.parse("contribution_A_[]"))
    assert step.matches(HeadwordCall.parse("contribution_A_[x]"))
    assert not base.matches(HeadwordCall.parse("contribution_A_[x]"))
    assert not base.matches(HeadwordCall.parse("contribution_A_members"))
    assert not step.matches(HeadwordCall.parse("contribution_A_members"))
    assert base.matches(HeadwordCall.parse("contribution_A")) and step.matches(HeadwordCall.parse("contribution_A"))
    assert not base.matches(HeadwordCall.parse("other_A_[]"))
    with pytest.raises(HeadwordArityError):
        base.bindings(HeadwordCall.parse("contribution_A_[]_extra"))


def test_two_entries_of_one_stem_need_one_arity_and_one_name_where_both_are_plain():
    base = HeadwordSignature.parse("contribution_p_[]")
    assert base.compatible_with(HeadwordSignature.parse("contribution_p_[m|rest]"))
    assert base.compatible_with(HeadwordSignature.parse("contribution_p_l"))
    assert not base.compatible_with(HeadwordSignature.parse("contribution_q_[m|rest]"))
    assert not base.compatible_with(HeadwordSignature.parse("contribution_p"))
    assert HeadwordSignature.parse("f_A:x").compatible_with(HeadwordSignature.parse("f_R:y"))


def test_instantiation_binds_the_parts_a_pattern_names():
    step = HeadwordSignature.parse("contribution_p_[m|rest]")
    assert instantiate_definition(
        "impressed-force_m_p plus contribution_p_rest", step,
        HeadwordCall.parse("contribution_A_[A:spring:s1,R:spring:s2]"),
    ) == "impressed-force_A:spring:s1_A plus contribution_A_[R:spring:s2]"
    tagged = HeadwordSignature.parse("impressed-force_A:x_p")
    assert instantiate_definition(
        "action-force_x on p", tagged, HeadwordCall.parse("impressed-force_A:spring:s1_B"),
    ) == "action-force_spring:s1 on B"
    plain = HeadwordSignature.parse("f_x")
    assert instantiate_definition("g_[x,y] and T:x", plain, HeadwordCall.parse("f_A")) == "g_[A,y] and T:A"
    with pytest.raises(HeadwordApplicationError, match="does not have the form"):
        instantiate_definition("anything", step, HeadwordCall.parse("contribution_A_[]"))


# ── Tokenizer ───────────────────────────────────────────────────────


def test_calls_with_structured_arguments_are_single_demands():
    tokeniser = Tokeniser()
    headwords = {"contribution_p_[]", "contribution_p_[m|rest]", "impressed-force_A:x_p", "impressed-force_R:x_p"}
    definiens = tokeniser.analyse(
        "impressed-force_A:spring:s1_A plus contribution_A_[R:spring:s2,A:gravity:A].", headwords,
    )
    assert definiens.headwords == ["impressed-force_A:spring:s1_A", "contribution_A_[R:spring:s2,A:gravity:A]"]
    assert definiens.residual.latent == ["", " plus ", "."]


def test_a_headword_spelled_inside_an_argument_is_not_a_demand_of_its_own():
    tokeniser = Tokeniser()
    headwords = {"holder_x", "spring", "rope"}
    definiens = tokeniser.analyse("holder_[spring,rope] holds a spring", headwords)
    assert definiens.headwords == ["holder_[spring,rope]", "spring"]
    tagged = tokeniser.analyse("holder_T:spring and rope", headwords)
    assert tagged.headwords == ["holder_T:spring", "rope"]


def test_punctuation_after_an_atom_is_still_punctuation():
    tokeniser = Tokeniser()
    definiens = tokeniser.analyse("mass_p: the quantity, and mass_q.", {"mass_p"})
    assert definiens.headwords == ["mass_p", "mass_q"]
    assert definiens.residual.latent == ["", ": the quantity, and ", "."]
    spaced = tokeniser.analyse("mass_[a, b] is not a list argument", {"mass_p"})
    assert spaced.headwords == []          # a malformed argument drops the match, as before


def test_a_reference_to_a_stem_counts_for_each_of_its_spellings():
    instance = VDInstance("spellings")
    instance.append_many([
        ("contribution_p_[]", "the zero vector"),
        ("contribution_p_[m|rest]", "impressed-force_m_p plus contribution_p_rest"),
        ("impressed-force_m_p", "supplied"),
        ("net-force_p", "haze plus contribution_p"),
    ])
    net_force = instance.entries[3]
    assert net_force.hw_tokens == {"contribution_p_[]", "contribution_p_[m|rest]"}
    step = instance.entries[1]
    # Its own spelling is dropped as a self-reference; the other clause is a real reference.
    assert step.hw_tokens == {"contribution_p_[]", "impressed-force_m_p"}


def test_conflicting_clauses_are_refused_and_leave_the_dictionary_unchanged():
    instance = VDInstance("conflicts")
    instance.append("contribution_p_[]", "the zero vector")
    with pytest.raises(HeadwordSignatureConflictError):
        instance.append("contribution_q_[m|rest]", "something")
    with pytest.raises(HeadwordSignatureConflictError):
        instance.append("contribution_p", "something")
    instance.append("contribution_p_[m|rest]", "impressed-force_m_p plus contribution_p_rest")
    assert [entry.headword for entry in instance.entries] == ["contribution_p_[]", "contribution_p_[m|rest]"]
    with pytest.raises(HeadwordSignatureConflictError):
        Tokeniser().analyse("x", {"f_p_[]", "f_q_[m|rest]"})


# ── Lookup: which definitions can answer a call ─────────────────────


@pytest.fixture
def sim():
    return build_demo_simulator()


def index_of(sim, headword):
    return next(i for i in range(sim.entry_count()) if sim.entry_headword(i) == headword)


def test_the_form_of_the_argument_decides_which_definition_answers(sim):
    base, step = index_of(sim, "contribution_p_[]"), index_of(sim, "contribution_p_[m|rest]")
    action, reaction = index_of(sim, "impressed-force_A:x_p"), index_of(sim, "impressed-force_R:x_p")
    assert sim.entry_indexes("contribution_A_[]") == [base]
    assert sim.entry_indexes("contribution_A_[A:gravity:A]") == [step]
    assert sim.entry_indexes("contribution_A") == [base, step]          # the list is not supplied yet
    assert sim.entry_indexes("contribution_A_members") == []            # an atom is neither form
    assert sim.entry_indexes("impressed-force_A:spring:s1_A") == [action]
    assert sim.entry_indexes("impressed-force_R:spring:s2_A") == [reaction]
    assert sim.entry_indexes("impressed-force_X:spring:s2_A") == []
    assert sim.entry_indexes("action-force_spring:s1") == [index_of(sim, "action-force_spring:s")]
    assert sim.entry_indexes("action-force_gravity:A") == [index_of(sim, "action-force_gravity:q")]
    assert sim.entry_indexes("inertial-mass_A") == [index_of(sim, "inertial-mass_p")]
    with pytest.raises(HeadwordArityError):
        sim.entry_indexes("contribution_A_[]_extra")


def test_entry_use_records_every_clause_and_which_ones_fit(sim):
    base, step = index_of(sim, "contribution_p_[]"), index_of(sim, "contribution_p_[m|rest]")
    use = sim.entry_use(step, "contribution_A_[A:spring:s1,R:spring:s2]")
    assert use.bindings == (("p", "A"), ("m", "A:spring:s1"), ("rest", "[R:spring:s2]"))
    assert use.text == "impressed-force_A:spring:s1_A plus contribution_A_[R:spring:s2]"
    assert use.clauses == ((base, "contribution_p_[]"), (step, "contribution_p_[m|rest]"))
    assert use.candidates == (step,)
    with pytest.raises(HeadwordApplicationError, match="does not have the form"):
        sim.entry_use(base, "contribution_A_[A:spring:s1]")


def test_a_plain_clause_beside_a_pattern_leaves_a_choice_to_the_person():
    instance = VDInstance("overlap")
    instance.append_many([("f_p_l", "anything about l"), ("f_p_[]", "nothing")])
    sim = Simulator(instance)
    assert sim.entry_indexes("f_A_[]") == [0, 1]       # both fit: not decided by form
    assert sim.entry_indexes("f_A_[x]") == [0]
    trace = Trace.start(sim, "f_A_[] and f_A_[x]")
    trace.expand_node(sim, trace.root, 0, 1, "the person picks the empty-list clause")
    trace.expand_node(sim, trace.root, 1, 0, "only the plain clause fits")
    picked, forced = build_prediction_set(trace).predictions[1:]
    assert picked.statement.endswith("for the demand 'f_A_[]'; chosen over E0.")
    assert forced.statement.endswith("for the demand 'f_A_[x]'; the form of the demand rules out E1.")
    other = Trace.start(sim, "f_A_[x]")
    with pytest.raises(ValueError, match="requires a form that 'f_A_\\[x\\]' does not have"):
        other.expand_node(sim, other.root, 0, 1, "wrong form")
    assert len(other.events) == 1


# ── The member-list scene, end to end ───────────────────────────────


def test_the_member_list_scene_reproduces_the_hand_recorded_answers(sim):
    a = build_prediction_set(trace_object(sim, "A"))
    b = build_prediction_set(trace_object(sim, "B"))
    assert a.issued[-1].result == "-23/10 m/s^2"
    assert b.issued[-1].result == "-24/5 m/s^2"
    for result in (a, b):
        assert result.trace_complete and result.dependency_selection_complete
        assert result.unrecorded_events == ()
        assert set(result.issued[-1].prediction_ids) == {claim.id for claim in result.predictions}


def test_every_split_and_dispatch_in_the_scene_is_forced_by_form(sim):
    result = build_prediction_set(trace_object(sim, "A"))
    applications = [claim for claim in result.predictions if claim.kind == "entry_application"]
    forced = forced_by_form(result)
    by_stem: dict[str, int] = {}
    for claim in applications:
        if claim.id in forced:
            stem = claim.evidence.entry.headword.split("_")[0]
            by_stem[stem] = by_stem.get(stem, 0) + 1
    # Three members and the empty remainder; three members dispatched on action or
    # reaction; three action laws dispatched on the kind of acting-object.
    assert by_stem == {"contribution": 4, "impressed-force": 3, "action-force": 3}
    assert len(applications) - len(forced) == 3      # acceleration, net force, reaction by negation
    # No entry application in the scene was a choice a person made.
    assert all(len(claim.evidence.entry.candidates) == 1 for claim in applications)


def test_the_remaining_list_is_bound_by_the_pattern_not_supplied(sim):
    result = build_prediction_set(trace_object(sim, "A"))
    steps = [claim.evidence.entry for claim in result.predictions
             if claim.kind == "entry_application" and claim.evidence.entry.headword == "contribution_p_[m|rest]"]
    assert [dict(use.bindings)["m"] for use in steps] == ["A:spring:s1", "R:spring:s2", "A:gravity:A"]
    assert [dict(use.bindings)["rest"] for use in steps] == ["[R:spring:s2,A:gravity:A]", "[A:gravity:A]", "[]"]
    reaction = next(claim for claim in result.predictions
                    if claim.kind == "entry_application" and claim.evidence.entry.headword == "impressed-force_R:x_p")
    assert reaction.statement == (
        "According to 'member-list prototype', entry E5 defines 'impressed-force_R:x_p' as "
        "'reaction-force_x'; with x := spring:s2, p := A that gives 'reaction-force_spring:s2' for the "
        "demand 'impressed-force_R:spring:s2_A'; the form of the demand rules out E4."
    )


def test_the_list_itself_is_the_one_thing_a_person_supplies_about_membership(sim):
    result = build_prediction_set(trace_object(sim, "A"))
    supplied = [claim for claim in result.predictions if claim.kind == "supplied_input"]
    membership = [claim for claim in supplied if claim.evidence.stimulus == "contribution_A"]
    assert len(membership) == 1
    assert membership[0].evidence.response == f"contribution_A_{MEMBERS['A']}"
    assert len(supplied) == 9      # the list, haze, inertial mass, two springs' two values, mass and field for gravity


def test_a_member_of_no_known_form_stops_the_trace_instead_of_guessing(sim):
    with pytest.raises(ValueError, match="answered by 0 entries"):
        trace_object(sim, "A", "[X:spring:s1]")


def test_the_engine_does_not_police_what_the_supplied_list_contains(sim):
    # Both members of s2 in one list is a claim about the scene, made where the list is
    # supplied. Nothing mechanical refuses it; the trace runs and its wording is unanswered.
    trace = trace_object(sim, "A", "[A:spring:s1,R:spring:s2,A:gravity:A,A:spring:s2]")
    result = build_prediction_set(trace)
    assert result.trace_complete
    assert "plus" in result.issued[-1].result      # no scripted response covers this wording


# ── The REPL and the bridge see the same choice ─────────────────────


def test_repl_expands_a_forced_choice_without_asking():
    lines = iter(["set cleanup off", "set reduce off", "trace contribution_A_[]", "expand", "state"])
    output = []

    def read(prompt):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    repl = REPL(build_demo_simulator(), input_fn=read, print_fn=output.append)
    repl.run()
    assert repl.trace.root.text() == "the zero vector"
    assert not any("multiple entries" in line for line in output)


def test_the_bridge_offers_only_the_definitions_whose_form_fits():
    dictionary = {"name": "member-list prototype", "entries": [list(pair) for pair in DEMO_ENTRIES]}
    record = start_record(dictionary, "contribution_A_[A:gravity:A]")
    hole = record["snapshots"][-1]["frames"][0]["holes"][0]
    assert [item["headword"] for item in hole["candidates"]] == ["contribution_p_[m|rest]"]
    assert hole["candidates"][0]["instantiated_definition"] == "impressed-force_A:gravity:A_A plus contribution_A_[]"
    with pytest.raises(ValueError, match="not a candidate"):
        apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 2})
    record = apply_command(record, {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 3})
    claim = record["snapshots"][-1]["prediction_set"]["predictions"][-1]
    assert claim["evidence"]["entry"]["clauses"] == [[2, "contribution_p_[]"], [3, "contribution_p_[m|rest]"]]
    assert claim["evidence"]["entry"]["candidates"] == [3]
    assert record["snapshots"][-1]["prediction_set"]["schema_version"] == 5
    assert validate_record(json.loads(json.dumps(record))) == record
