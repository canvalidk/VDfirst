"""Adversarial correctness probes for handtrace.py (v2.2, updated for v2.3).

Plain tests pin correct behaviour, including every v1, v2, v2.1 and v2.2 bug
that a later version fixed (the v2.2 bugs once marked xfail(strict=True) here
are fixed in v2.3 and are now plain tests). test_gap_*
tests pin CURRENT behaviour for a gap, friction or note that is reported as a
finding; they are not endorsements and should change when the gap is closed.

Gaps v2.2 leaves open on purpose and that are not probed further here:
conditional branches and branch-local withdrawal (one short test below),
units (one short test below), the observation side of a trial (C2), the
shared approximation budget (C3), editions (C7), results flowing up without
an explicit RETURN, and a minimum-size citation search beyond 8 citations
(one documented threshold test below).

Sections: exact parsing; entailment and conflicts; the global conflict check
(answer-time values, joint inconsistency); minimal citation (exhaustive up to
8, ties to the first cited); solving and per-value solve provenance (one
DERIVE per fixed value); consistency(); strict and lenient nonlinear claims;
claims and relations that cannot be evaluated; hidden lookups (only when the
verdict would change); visibility and delivery; deliver_many and
deliver_through; the ledger and cone; multiple answers and per-answer
statuses; withdrawal and value taint; dictionary entries (including the
Design 2.1 file); validation; replay; markdown.
"""

import json
import random
import re
import time
from fractions import Fraction
from pathlib import Path

import pytest

import handtrace
from handtrace import (
    ROOT,
    CheckError,
    HiddenLookupError,
    Nonlinear,
    Trace,
    TraceError,
    _digest,
    entails,
    load_entries,
    mentioned_names,
    needed_relations,
    parse_equation,
    parse_expression,
    solve_linear,
)
from test_handtrace import E8, atwood, finish

ENTRIES_FILE = Path("C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/"
                    "07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md")
E8_TEXT = "inertial-acceleration-material-object := " + E8


def unknowns(t, frame, *names):
    for n in names:
        t.unknown(frame, n, n, address=f"({n})", ref="test")


def roundtrip(t):
    return Trace.replay(json.loads(json.dumps(t.to_record())))


def names_in(led, key):
    return [c["name"] for c in led[key]]


def refs_in(led, key):
    return [c["ref"] for c in led[key]]


def ops(t):
    return [s.op for s in t.steps]


# -- exact parsing -------------------------------------------------------------


@pytest.mark.parametrize("text, value", [
    ("0.1", Fraction(1, 10)), ("1e-3", Fraction(1, 1000)), ("-1e-3", Fraction(-1, 1000)),
    ("1.5e+2", Fraction(150)), (".5", Fraction(1, 2)), ("5.", Fraction(5)),
    ("6.02214076e23", Fraction(602214076 * 10**15)), ("1.602176634e-19", Fraction(1602176634, 10**28)),
    ("-2**2", Fraction(-4)), ("(-2)**2", Fraction(4)), ("2**3**2", Fraction(512)),
    ("--3", Fraction(3)), ("-(1 + 2)*3", Fraction(-9)), ("1/3 + 1/6", Fraction(1, 2)),
    ("1_000", Fraction(1000)), ("1e1_0", Fraction(10**10)), ("0x1F", Fraction(31)),
    ("0.30000000000000001", Fraction("0.30000000000000001")),
    ("3.14159265358979323846", Fraction("3.14159265358979323846")),
    ("1e-400", Fraction(1, 10**400)), ("1e400", Fraction(10**400)),
    ("10**-3", Fraction(1, 1000)), ("(-2)**-3", Fraction(-1, 8)), ("2**-1", Fraction(1, 2)),
])
def test_literals_and_precedence_are_exact(text, value):
    form, names = parse_expression(text)
    assert form.is_constant() and form.const == value and names == ()


def test_decimal_identities_hold_exactly():
    t = Trace("q")
    assert t.derive(ROOT, "0.1 + 0.2 = 0.3").check == "checked"
    assert t.derive(ROOT, "1e-3*1000 = 1").check == "checked"
    with pytest.raises(CheckError):
        t.derive(ROOT, "0.1 + 0.2 = 0.30000000000000004")
    with pytest.raises(CheckError):  # equal as floats, different as written
        t.derive(ROOT, "0.30000000000000001 = 0.3")


def test_cancelled_names_and_zero_division():
    form, names = parse_expression("x*(y - y)")
    assert form.is_zero() and names == ("x", "y")
    for text in ("1/(x - x)", "0**-1"):
        with pytest.raises(TraceError, match="division by zero"):
            parse_expression(text)
    with pytest.raises(TraceError):
        parse_expression("3 // 2")


@pytest.mark.parametrize("claim", ["m*g = 2.94e1", "m*g = 2_9.4", "m*g*1e0 = 29.4", "m*g = 0x1D + 0.4"])
def test_literals_in_nonlinear_claims_are_not_read_as_names(claim):
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3)
    t.input(ROOT, "g", "value", "g", value="9.8")
    assert t.derive(ROOT, claim).check == "checked"


def test_scientific_literal_in_nonlinear_relation():
    assert mentioned_names("W = m*g*1e0") == ("W", "m", "g")
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3)
    unknowns(t, ROOT, "W", "g")
    t.input(ROOT, "w", "model", "weight", relation="W = m*g*1e0")
    assert t.bindings["w"].sort == "relation"


@pytest.mark.parametrize("kw", ["lambda", "None", "True", "if"])
def test_keyword_names_are_refused(kw):
    t = Trace("q")
    with pytest.raises(TraceError, match="keyword"):
        t.input(ROOT, kw, "value", "a quantity", value=2)
    with pytest.raises(TraceError, match="keyword"):
        t.unknown(ROOT, kw, "a quantity", address="(k)", ref="test")
    assert t.steps == []


def test_soft_keywords_and_builtins_are_ordinary_names():
    t = Trace("q")
    t.input(ROOT, "match", "value", "soft keyword", value=2)
    t.input(ROOT, "sum", "value", "builtin name", value=3)
    assert t.derive(ROOT, "match + sum = 5").check == "checked"


@pytest.mark.parametrize("text", ["x = 3 # + 1", "x = 3#"])
def test_comments_are_refused(text):
    with pytest.raises(TraceError, match="#"):
        parse_equation(text)
    t = Trace("q")
    unknowns(t, ROOT, "x")
    with pytest.raises(TraceError, match="#"):
        t.input(ROOT, "r", "model", "r", relation=text)


def test_newline_inside_an_expression_is_refused():
    with pytest.raises(TraceError, match="cannot parse"):
        parse_equation("x = 3\n+ 1")


def test_gap_power_of_a_name_is_nonlinear_even_with_exponent_one():
    """Friction kept by v2.2: x**1 counts as nonlinear (a constant base is required)."""
    with pytest.raises(Nonlinear):
        parse_expression("x**1")


@pytest.mark.parametrize("v", [float("inf"), float("nan"), float("-inf")])
def test_non_finite_float_values_are_refused_cleanly(v):
    """v2 let a bare ValueError escape from Fraction."""
    t = Trace("q")
    with pytest.raises(TraceError, match="finite"):
        t.input(ROOT, "v", "value", "v", value=v)
    assert t.steps == []


def test_mentioned_names_are_in_source_order():
    """v2 used a breadth-first walk: 'a*b + c' gave ('c', 'a', 'b')."""
    assert mentioned_names("a*b + c") == ("a", "b", "c")
    assert mentioned_names("c*(b + a) = a + d") == ("c", "b", "a", "d")
    t = Trace("q")
    for n in ("a", "b", "c"):
        t.input(ROOT, n, "value", n, value=1)
    assert t.derive(ROOT, "a*b + c = 2").uses == ("a", "b", "c")


# -- entailment and conflicts among cited relations ----------------------------------


def test_entailment_scaling_redundancy_and_zero_rows():
    r, _ = parse_equation("x/1000 = 3/1000")
    zero, _ = parse_equation("x - x = 0")
    assert entails([r], parse_equation("1000*x = 3000")[0])
    assert entails([r, r, zero], parse_equation("x = 3")[0])
    assert not entails([zero], parse_equation("x = 3")[0])
    assert entails([zero], parse_equation("0 = 0")[0])
    assert not entails([r], parse_equation("y = 0")[0])


def test_inconsistent_cited_relations_are_a_conflict():
    """v1 'checked' T1 - T2 = 42 from contradictory relations (ex falso)."""
    t = Trace("q")
    unknowns(t, ROOT, "T1", "T2")
    t.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t.input(ROOT, "slip", "model", "sign slip", relation="T1 = T2 + 1")
    n = len(t.steps)
    with pytest.raises(CheckError, match="conflict"):
        t.derive(ROOT, "T1 - T2 = 42", from_relations=["meq", "slip"])
    assert len(t.steps) == n
    st = t.solve(ROOT, ["meq", "slip"], ["T1", "T2"])
    assert st.check == "failed" and st.detail.startswith("conflict: inconsistent") and st.binds == ()

    lt = Trace("q", strict=False)
    unknowns(lt, ROOT, "T1", "T2")
    lt.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    lt.input(ROOT, "slip", "model", "sign slip", relation="T1 = T2 + 1")
    bad = lt.derive(ROOT, "T1 = 42", binds="T1", from_relations=["meq", "slip"])
    assert bad.check == "failed" and bad.detail.startswith("conflict") and "T1 not determined" in bad.detail
    assert "T1" not in lt.values


def test_claim_contradicting_a_visible_value_is_a_conflict():
    """v1 'checked' x = 7 from r: x = 3 while x = 2 was visible."""
    t = Trace("q")
    t.input(ROOT, "x", "value", "x", value=2)
    t.input(ROOT, "r", "model", "r", relation="x = 3")
    with pytest.raises(CheckError, match="conflict"):
        t.derive(ROOT, "x = 7", from_relations=["r"])
    with pytest.raises(CheckError, match="conflict"):  # a conflict outranks an identity
        t.derive(ROOT, "2 = 2", from_relations=["r"])


def test_conflict_detection_with_partially_known_values():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "difference", relation="x - y = 1")
    assert t.derive(ROOT, "x = 3", from_relations=["r1", "r2"]).check == "checked"  # y still unknown
    t.input(ROOT, "ry", "model", "y three", relation="y = 3")
    t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"])
    with pytest.raises(CheckError, match="conflict"):
        t.derive(ROOT, "x = 3", from_relations=["r1", "r2"])
    assert t.derive(ROOT, "x = 2", from_relations=["r1"]).check == "checked"
    with pytest.raises(CheckError, match="conflict"):  # a superfluous but conflicting citation still fails
        t.derive(ROOT, "x = 2", from_relations=["r1", "r2"])
    st = t.solve(ROOT, ["r1", "r2"], ["x"])
    assert st.check == "failed" and "x" not in t.values


def test_zero_claim_is_flagged_as_having_no_independent_content():
    """The value-lock reuse: f = m*a substitutes to 2 = 2."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    unknowns(t, ROOT, "a", "f", "z")
    t.input(ROOT, "r1", "model", "spring", relation="f = 2")
    t.input(ROOT, "r2", "model", "E8", relation="a = f/m")
    t.derive(ROOT, "f = 2", from_relations=["r1"], binds="f")
    t.derive(ROOT, "a = 1", from_relations=["r2"], binds="a")
    junk = t.input(ROOT, "junk", "model", "unrelated", relation="z = 7")
    st = t.derive(ROOT, "f = m*a", from_relations=["junk"])
    assert st.check == "checked" and "no independent content" in st.detail and "follows from" not in st.detail
    assert junk.index not in st.deps
    assert t.derive(ROOT, "0 = 0").detail == "identity"
    assert "no independent content" in t.derive(ROOT, "f = m*a").detail


def test_mistakes_and_conflicts_are_separate_ledger_lists():
    """v2 put arithmetic slips and premise conflicts in one 'conflicts' list."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x three", relation="x = 3")
    t.input(ROOT, "s", "model", "x four", relation="x = 4")
    slip = t.derive(ROOT, "2*x = 7", from_relations=["r"])
    bare = t.derive(ROOT, "2 = 3")
    clash = t.derive(ROOT, "x = 3", from_relations=["r", "s"])
    clash_solve = t.solve(ROOT, ["r", "s"], ["x"])
    t.input(ROOT, "k", "value", "k", value=1)
    t.answer(["k"])
    led = t.ledger()
    assert [m["step"] for m in led["mistakes"]] == [slip.id, bare.id]
    assert [c["step"] for c in led["conflicts"]] == [clash.id, clash_solve.id]
    assert all(m["detail"].startswith("mistake") for m in led["mistakes"])
    assert all(c["detail"].startswith("conflict") for c in led["conflicts"])
    md = t.to_markdown()
    assert "### Found mistakes" in md and "### Conflicts" in md
    assert led["warnings"] == ["1 commitment(s) have no status yet: k"]  # none of them feeds k


# -- the global conflict check -------------------------------------------------------


def cross_frame_conflict():
    """V2R-1 / probes-7, v2.2 form: at D, r1 and r2 fix x = 3 and 'y = 2' checks
    while y has no value anywhere; ROOT later fixes y = 3, which contradicts both.
    (With y = 3 fixed first, v2.2 refuses the D derive as a hidden lookup: see
    test_hidden_value_that_would_change_the_verdict_blocks_the_cross_frame_derive.)"""
    t = Trace("q")
    d = t.demand(ROOT, "D", "x")
    unknowns(t, d, "x", "y")
    t.input(d, "r1", "model", "sum", relation="x + y = 5")
    t.input(d, "r2", "model", "difference", relation="x - y = 1")
    assert t.derive(d, "x = 3", binds="x", from_relations=["r1", "r2"]).check == "checked"
    assert t.derive(d, "y = 2", from_relations=["r1", "r2"]).check == "checked"  # frame-local
    t.input(ROOT, "ry", "model", "y three", relation="y = 3")
    t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"])
    return t


def test_hidden_value_that_would_change_the_verdict_blocks_the_cross_frame_derive():
    """v2.1 checked x = 3 at D from r1, r2 with y = 3 hidden; the hidden y makes
    r1 and r2 contradict each other, so v2.2 refuses the step until y arrives."""
    for strict in (True, False):
        t = Trace("q", strict=strict)
        d = t.demand(ROOT, "D", "x")
        unknowns(t, d, "x", "y")
        t.input(d, "r1", "model", "sum", relation="x + y = 5")
        t.input(d, "r2", "model", "difference", relation="x - y = 1")
        t.input(ROOT, "ry", "model", "y three", relation="y = 3")
        t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"])
        n = len(t.steps)
        with pytest.raises(HiddenLookupError, match=r"values of \['y'\].*would change the verdict"):
            t.derive(d, "x = 3", binds="x", from_relations=["r1", "r2"])
        assert len(t.steps) == n and "x" not in t.values
        t.deliver(d, "y")
        if strict:
            with pytest.raises(CheckError, match="conflict"):
                t.derive(d, "x = 3", binds="x", from_relations=["r1", "r2"])
        else:
            st = t.derive(d, "x = 3", binds="x", from_relations=["r1", "r2"])
            assert st.check == "failed" and st.detail.startswith("conflict") and st.binds == ()


def test_global_check_catches_premises_that_conflict_across_frames():
    t = cross_frame_conflict()
    t.answer(["x", "y"])
    led = t.ledger()
    assert refs_in(led, "conflicts") == ["r1", "r2"]
    rows = {c["ref"]: c for c in led["conflicts"]}
    assert rows["r1"]["step"] == t.steps[t.bindings["r1"].step].id and rows["r1"]["claim"] == "x + y = 5"
    assert rows["r1"]["detail"] == ("conflict: r1 is contradicted by the values determined in this trace "
                                    "(lhs - rhs = 1)")
    for r in ("r1", "r2"):
        assert f"the answer rests on {r}, which the trace's own values contradict" in led["warnings"]
    assert led["mistakes"] == []
    md = t.to_markdown()
    assert "r1 is contradicted by the values determined in this trace" in md


def test_global_check_covers_relations_reached_only_through_uses():
    """V2R-1 second case: a relation cited only in uses= was never checked."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    t.input(ROOT, "bad", "model", "a wrong mass law", relation="m = 3")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "rx", "model", "x one", relation="x = 1")
    t.derive(ROOT, "x = 1", binds="x", from_relations=["rx"], uses=["bad"])
    t.answer(["x"])
    led = t.ledger()
    assert refs_in(led, "conflicts") == ["bad"]
    assert "the answer rests on bad, which the trace's own values contradict" in led["warnings"]


def test_global_check_only_charges_answers_whose_cone_holds_the_relation():
    t = cross_frame_conflict()
    t.answer(["y"], label="py")  # y = 3 rests on ry only
    t.answer(["x"], label="px")
    assert t.ledger("py")["conflicts"] == []
    assert refs_in(t.ledger("px"), "conflicts") == ["r1", "r2"]


def test_global_check_substitutes_into_nonlinear_relations_and_skips_open_ones():
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3)
    t.input(ROOT, "g", "value", "g", value=10)
    unknowns(t, ROOT, "W", "p", "q")
    t.input(ROOT, "w", "model", "weight", relation="W = m*g")
    t.input(ROOT, "pq", "model", "an open product", relation="p*q = W")
    t.input(ROOT, "rW", "model", "a wrong weight", relation="W = 31")
    t.derive(ROOT, "W = 31", binds="W", from_relations=["rW"], uses=["w", "pq"])
    t.answer(["W"])
    led = t.ledger()
    assert refs_in(led, "conflicts") == ["w"]  # 31 != 30; pq stays nonlinear and is skipped
    assert "lhs - rhs = 1" in led["conflicts"][0]["detail"]


def test_answer_on_failed_step_is_warned_and_its_premise_conflict_is_listed():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    r = t.input(ROOT, "r", "model", "x is three", relation="x = 3")
    bad = t.derive(ROOT, "x = 4", from_relations=["r"], name="r4")
    assert bad.check == "failed" and t.bindings["r4"].sort == "relation"  # still citable
    t.derive(ROOT, "x = 4", binds="x", from_relations=["r4"])
    t.answer(["x"])
    t.annotate("r", "REQUIRED")
    led = t.ledger()
    assert led["answer"] == "x = 4" and [s["check"] for s in led["step_members"]] == ["failed", "checked"]
    assert [m["step"] for m in led["mistakes"]] == [bad.id]
    assert [c["step"] for c in led["conflicts"]] == [r.id]  # global check: x = 4 contradicts r
    assert "r4" not in refs_in(led, "conflicts")  # the failed step's own relation is a mistake only
    assert f"the answer rests on {bad.id}, whose check failed" in led["warnings"]
    assert "the answer rests on r, which the trace's own values contradict" in led["warnings"]


def test_found_mistake_in_the_cone_is_not_also_a_premise_conflict():
    """V21-2 / fresh-6: a failed derive registered with name= was listed under both
    'mistakes' and 'conflicts'; v2.2 skips relations bound by failed steps."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "y")
    t.input(ROOT, "x", "value", "x", value=3)
    bad = t.derive(ROOT, "2*x = 7", name="bad")
    t.input(ROOT, "ry", "model", "y one", relation="y = 1")
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"], uses=["bad"])
    t.answer(["y"])
    led = t.ledger()
    assert bad.index in t.cone() and [m["step"] for m in led["mistakes"]] == [bad.id]
    assert led["conflicts"] == [] and f"the answer rests on {bad.id}, whose check failed" in led["warnings"]


def test_global_check_reports_joint_inconsistency():
    """probes-9 (v2.1 gap, closed): r1, r3 imply y = 2 and r2 implies y = 3; y is
    never determined, so no relation is false alone, but jointly they are.
    v2.3: the row names a minimal inconsistent subset, found by a deletion
    filter in citation order (r3, r4), not every open relation of the cone."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "r3", "model", "difference", relation="x - y = 1")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["r1", "r3"])
    t.input(ROOT, "r2", "model", "y three", relation="y = 3")
    t.input(ROOT, "r4", "model", "z twice y", relation="z = 2*y")
    t.derive(ROOT, "z = 6", binds="z", from_relations=["r2", "r4"])
    t.answer(["x", "z"])
    led = t.ledger()
    assert len(led["conflicts"]) == 1
    row = led["conflicts"][0]
    # r1 goes (r3 still gives y = 2 against r2 and r4), r2 goes (r4 still gives y = 3); r3 and r4 both stay
    assert row["step"] == "" and row["ref"] == "r3, r4"
    assert row["detail"] == ("conflict: the relations r3, r4, which this answer rests on, are jointly "
                             "inconsistent with the values determined in this trace")
    assert "the answer rests on relations that are jointly inconsistent: r3, r4" in led["warnings"]
    assert "the answer rests on relations that are jointly inconsistent: r3, r4" in t.to_markdown()


def test_global_check_joint_case_with_a_free_unknown():
    """fresh-18(d): x = u + 1 and x = u + 2 contradict whatever u is."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "u", "z")
    t.input(ROOT, "r1", "model", "r1", relation="x = u + 1")
    t.input(ROOT, "r2", "model", "r2", relation="x = u + 2")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["r1", "r2"])
    t.answer(["z"])
    assert refs_in(t.ledger(), "conflicts") == ["r1, r2"]


def test_joint_check_runs_even_when_a_single_relation_is_contradicted():
    """v2.3: the joint check always runs, leaving out the relations flagged one by
    one, so an independent joint inconsistency (r1, r2) in the same cone as a
    relation contradicted alone (bad) is reported too."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    unknowns(t, ROOT, "x", "u", "z")
    t.input(ROOT, "bad", "model", "a wrong mass law", relation="m = 3")
    t.input(ROOT, "r1", "model", "r1", relation="x = u + 1")
    t.input(ROOT, "r2", "model", "r2", relation="x = u + 2")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["bad", "r1", "r2"])
    t.answer(["z"])
    led = t.ledger()
    assert refs_in(led, "conflicts") == ["bad", "r1, r2"]
    assert led["conflicts"][0]["detail"] == ("conflict: bad is contradicted by the values determined in this trace "
                                             "(lhs - rhs = -1)")
    assert led["conflicts"][1]["detail"] == ("conflict: the relations r1, r2, which this answer rests on, are "
                                             "jointly inconsistent with the values determined in this trace")
    assert "the answer rests on bad, which the trace's own values contradict" in led["warnings"]
    assert "the answer rests on relations that are jointly inconsistent: r1, r2" in led["warnings"]


def test_global_check_uses_only_values_fixed_before_the_answer():
    """probes-16 / V21R-12 (v2.1 note, closed): a value fixed after p1 no longer adds
    conflicts to p1's ledger; an answer recorded after it is charged."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "difference", relation="x - y = 1")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["r1", "r2"])
    t.answer(["x"], label="p1")
    assert t.ledger("p1")["conflicts"] == []
    ry = t.input(ROOT, "ry", "model", "y three", relation="y = 3")
    t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"])
    assert t.ledger("p1")["conflicts"] == [] and ry.index not in t.cone("p1")
    t.answer(["x"], label="p2")
    assert refs_in(t.ledger("p2"), "conflicts") == ["r1", "r2"]


def test_global_check_reports_a_relation_undefined_at_the_values_as_a_conflict():
    """V21R-4 / fresh-1 (v2.1 crash, closed): y = 6/c with c = 0 in the cone made
    ledger(), markdown and to_record() raise."""
    t = Trace("q")
    t.input(ROOT, "c", "value", "c", value=0)
    unknowns(t, ROOT, "y", "z")
    t.input(ROOT, "rel", "model", "rel", relation="y = 6/c")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["rel"])
    t.answer(["z"])
    led = t.ledger()
    assert refs_in(led, "conflicts") == ["rel"]
    assert led["conflicts"][0]["detail"] == ("conflict: rel cannot be evaluated with the values determined in this "
                                             "trace (division by zero)")
    assert "the answer rests on rel, which the trace's own values make undefined" in led["warnings"]
    t.to_markdown()
    roundtrip(t)


def test_withdrawing_a_contradicted_relation_keeps_the_conflict_in_earlier_ledgers():
    """probes-5 (v2.1 bug, fixed): a relation withdrawn after the answer still counts for it."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "x seven", relation="x = 7")  # registered before x has a value
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y is x plus one", relation="y = x + 1")
    t.derive(ROOT, "y = 6", binds="y", from_relations=["ry"], uses=["r"])
    t.answer(["y"], label="p1")
    assert refs_in(t.ledger("p1"), "conflicts") == ["r"]
    t.withdraw(ROOT, "r", "contradicted by rx")
    led = t.ledger("p1")
    assert names_in(led, "withdrawn") == ["r"]
    assert refs_in(led, "conflicts") == ["r"]  # p1 still rests on r, which x = 5 contradicts
    with pytest.raises(TraceError, match="the value of 'y' rests on 'r'"):  # y's derive cited r in uses=
        t.answer(["y"], label="p2")


def test_global_check_ignores_values_resting_on_withdrawn_premises():
    """probes-6 / V21-3 (v2.1 bug, fixed)."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "r", "model", "x five", relation="x = 5")  # registered before x has a value
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.withdraw(ROOT, "rx", "x = 3 was wrong")
    t.input(ROOT, "rz", "model", "z two, given r", relation="z = 2", uses=["r"])
    t.derive(ROOT, "z = 2", binds="z", from_relations=["rz"])
    t.answer(["z"])
    led = t.ledger()
    assert t.bindings["r"].step in t.cone()
    assert led["conflicts"] == []


# -- minimal citation ----------------------------------------------------------------------


def test_minimal_citation_drops_superfluous_relations_from_the_cone():
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.input(ROOT, "junk", "model", "unrelated", relation="z = 7")
    st = t.derive(ROOT, "x = 3", binds="x", from_relations=["junk", "rx"])
    assert st.detail == "follows from rx (cited but not needed: junk)"
    assert st.uses == ("x", "junk", "rx")  # the table still shows what was cited
    t.answer(["x"])
    led = t.ledger()
    assert names_in(led, "commitments") == ["rx"] and names_in(led, "not_in_answer") == ["junk"]


def test_minimal_citation_is_a_smallest_subset_whatever_the_order():
    """v2's greedy pass dropped the direct premise rx when it was cited first."""
    def run(order):
        t = Trace("q")
        unknowns(t, ROOT, "x", "y")
        t.input(ROOT, "rxy", "model", "sum", relation="x + y = 5")
        t.input(ROOT, "ry", "model", "y two", relation="y = 2")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
        t.derive(ROOT, "x = 3", binds="x", from_relations=order)
        t.answer(["x"])
        return sorted(names_in(t.ledger(), "commitments"))

    for order in (["rxy", "ry", "rx"], ["rx", "ry", "rxy"], ["rx", "rxy", "ry"], ["ry", "rx", "rxy"]):
        assert run(order) == ["rx"]


def test_minimal_citation_ties_go_to_the_relations_cited_first():
    def dup(order):
        t = Trace("q")
        unknowns(t, ROOT, "x")
        t.input(ROOT, "a", "model", "x three (a)", relation="x = 3")
        t.input(ROOT, "b", "model", "x three (b)", relation="2*x = 6")
        return t.derive(ROOT, "x = 3", binds="x", from_relations=order).detail

    assert dup(["a", "b"]) == "follows from a (cited but not needed: b)"
    assert dup(["b", "a"]) == "follows from b (cited but not needed: a)"

    def pair(order):
        t = Trace("q")
        unknowns(t, ROOT, "x", "y")
        t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
        t.input(ROOT, "r2", "model", "y two", relation="y = 2")
        t.input(ROOT, "r3", "model", "difference", relation="x - y = 1")
        return t.derive(ROOT, "x = 3", from_relations=order).detail

    # any two of the three fix x; the lexicographically first pair in citation order wins
    assert pair(["r1", "r2", "r3"]) == "follows from r1, r2 (cited but not needed: r3)"
    assert pair(["r3", "r2", "r1"]) == "follows from r3, r2 (cited but not needed: r1)"
    assert pair(["r2", "r3", "r1"]) == "follows from r2, r3 (cited but not needed: r1)"


def test_needed_relations_is_exhaustive_up_to_eight_then_greedy():
    """Documented (deliberately open beyond 8): v2.2 lowered the threshold from ten
    to eight; beyond it a greedy pass drops from the end, so the kept set is
    irreducible but not always smallest and earlier citations win."""
    def run(njunk):
        t = Trace("q")
        junk = [f"z{i}" for i in range(njunk)]
        unknowns(t, ROOT, "x", "y", *junk)
        t.input(ROOT, "rxy", "model", "sum", relation="x + y = 5")
        t.input(ROOT, "ry", "model", "y two", relation="y = 2")
        for i, z in enumerate(junk):
            t.input(ROOT, f"j{i}", "model", f"junk {i}", relation=f"{z} = {i}")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
        rels = ["rxy", "ry"] + [f"j{i}" for i in range(njunk)] + ["rx"]
        return len(rels), t.derive(ROOT, "x = 3", from_relations=rels).detail.split(" (")[0]

    assert run(5) == (8, "follows from rx")
    assert run(6) == (9, "follows from rxy, ry")

    forms = [parse_equation(s)[0] for s in ("x + y = 5", "y = 2", "x = 3")]
    claim = parse_equation("x = 3")[0]
    assert needed_relations(forms, claim) == [2]
    assert needed_relations(forms, claim, exhaustive_up_to=0) == [0, 1]
    assert needed_relations(forms, parse_equation("0 = 0")[0]) == []


# -- solving and per-value solve provenance -----------------------------------------------


def test_solve_zero_rows_redundancy_and_contradiction_after_substitution():
    r1, _ = parse_equation("x = 3")
    r2, _ = parse_equation("2*x = 6")
    zero, _ = parse_equation("0 = 0")
    assert solve_linear([r1, r2, zero], ["x"])["values"] == {"x": 3}
    t = Trace("q")
    t.input(ROOT, "a", "value", "a", value=3)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="a = 4 + 0*x")
    st = t.solve(ROOT, ["r"], ["x"])
    assert "inconsistent" in st.detail and st.check == "failed"


def test_solve_refuses_repeated_relations_and_unknowns_and_needs_unknowns():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="x = 3")
    with pytest.raises(TraceError, match="repeat"):
        t.solve(ROOT, ["r"], ["x", "x"])
    with pytest.raises(TraceError, match="repeat"):
        t.solve(ROOT, ["r", "r"], ["x"])
    with pytest.raises(TraceError, match="repeat"):
        solve_linear([parse_equation("x = 3")[0]], ["x", "x"])
    with pytest.raises(TraceError, match="consistency"):  # v2 used solve(..., []) as a consistency check
        t.solve(ROOT, ["r"], [])
    assert t.solve(ROOT, ["r"], ["x"]).binds == ("x",) and t.values["x"] == 3


def test_solve_steps_carry_kind_solve():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "r", relation="x + y = 1")
    st = t.solve(ROOT, ["r"], ["x", "y"])
    ext = t.external(ROOT, "linear solve", "solved by hand elsewhere")  # V2R-15
    t.input(ROOT, "k", "value", "k", value=1)
    t.answer(["k"])
    assert st.kind == "solve" and ext.kind == ""
    assert [r["step"] for r in t.ledger()["solve_reports"]] == [st.id]


def test_solve_fixes_what_a_family_determines():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "y and z", relation="y + z = 1")
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y", "z"])
    assert st.check == "checked" and st.binds == ("x",) and t.values["x"] == 3
    assert "underdetermined" in st.detail and "free: z" in st.detail and "fixed anyway: x = 3" in st.detail
    assert st.detail.endswith("(relations not needed for the fixed values: r2)")
    t.answer(["x"])
    led = t.ledger()
    assert [r["step"] for r in led["solve_reports"]] == [st.id]
    assert {u["name"] for u in led["undetermined"]} == {"y", "z"}
    assert names_in(led, "commitments") == ["r1"]  # V2R-3 family case: r2 no longer feeds x


def test_solve_fixes_an_unknown_that_only_a_combination_determines():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z", "w")
    t.input(ROOT, "r1", "model", "r1", relation="x + y = 1")
    t.input(ROOT, "r2", "model", "r2", relation="x + y + z = 1")
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y", "z", "w"])
    assert st.binds == ("z",) and t.values["z"] == 0 and "x" not in t.values
    assert "free: y, w" in st.detail and "not needed" not in st.detail
    t.answer(["z"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["r1", "r2"]


def test_solve_drops_relations_no_fixed_value_needs():
    """regress-3: an identically-zero relation and its premises left the cone in derive
    but not in solve."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="2*x = 6")
    t.input(ROOT, "paint", "recognition", "blocks are red")
    t.input(ROOT, "k", "value", "k", value=4)
    t.input(ROOT, "kr", "model", "irrelevant", relation="k = 4", uses=["paint"])
    st = t.solve(ROOT, ["r", "kr"], ["x"])
    assert st.detail == "unique: x = 3 (relations not needed for the fixed values: kr)"
    assert st.uses == ("r", "kr", "x")  # the table still shows what was cited
    t.answer(["x"])
    led = t.ledger()
    assert names_in(led, "commitments") == ["r"]
    assert sorted(names_in(led, "not_in_answer")) == ["k", "kr", "paint"]


def test_solve_per_value_smallest_set_prefers_the_first_cited():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    a = t.input(ROOT, "a", "model", "a", relation="x = 3")
    b = t.input(ROOT, "b", "model", "b", relation="2*x = 6")
    st = t.solve(ROOT, ["b", "a"], ["x"])
    assert st.detail == "unique: x = 3 (relations not needed for the fixed values: a)"
    fix = t.steps[t.value_step["x"]]
    assert fix.op == "DERIVE" and fix.uses == ("b",) and fix.detail == "follows from b"
    assert b.index in fix.deps and a.index not in fix.deps
    assert {a.index, b.index} <= set(st.deps)  # the report step cites everything; it is not provenance


def test_solve_keeps_every_relation_a_coupled_value_needs():
    """Atwood-shaped: every fixed value needs all three relations, so nothing is dropped."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "T")
    t.input(ROOT, "l1", "model", "law 1", relation="3*x = T - 30")
    t.input(ROOT, "l2", "model", "law 2", relation="5*y = T - 50")
    t.input(ROOT, "k", "model", "coupling", relation="x + y = 0")
    st = t.solve(ROOT, ["l1", "l2", "k"], ["x", "y", "T"])
    assert st.detail == "unique: x = 5/2, y = -5/2, T = 75/2"
    t.answer(["x"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["k", "l1", "l2"]


def test_solve_per_value_sets_for_a_family_with_nothing_fixed():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    r = t.input(ROOT, "r", "model", "r", relation="x + y = 1")
    st = t.solve(ROOT, ["r"], ["x", "y"])
    assert st.binds == () and st.check == "checked" and r.index in st.deps
    assert t.steps[-1] is st and "x" not in t.value_step  # nothing fixed: no DERIVE step
    assert "not needed" not in st.detail


def test_solve_records_a_report_then_one_derive_per_fixed_value():
    """v2.2: solve() returns the EXTERNAL report; each fixed value gets a checked
    DERIVE 'x = value' whose provenance is that value's own smallest set."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "A", "recognition", "A")
    t.input(ROOT, "B", "recognition", "B")
    r1 = t.input(ROOT, "r1", "model", "x three", relation="x = 3", uses=["A"])
    r2 = t.input(ROOT, "r2", "model", "y four", relation="y = 4", uses=["B"])
    n = len(t.steps)
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y"], tag="S")
    assert st is t.steps[n] and (st.op, st.kind, st.check) == ("EXTERNAL", "solve", "checked")
    assert st.detail == "unique: x = 3, y = 4" and st.binds == ("x", "y")
    fx, fy = t.steps[n + 1], t.steps[n + 2]
    assert len(t.steps) == n + 3 and t.value_step == {"x": fx.index, "y": fy.index}
    for fix, name, rel, other in ((fx, "x", r1, r2), (fy, "y", r2, r1)):
        assert (fix.op, fix.check, fix.binds, fix.tag) == ("DERIVE", "checked", (name,), "S")
        assert fix.claim == f"{name} = {t.values[name]}" and fix.text == f"value fixed by the linear solve {st.id}"
        assert rel.index in fix.deps and other.index not in fix.deps and st.index not in fix.deps
    assert [c["op"] for c in t.commands[-1:]] == ["solve"]  # one command; replay regenerates the DERIVEs
    assert [s.op for s in roundtrip(t).steps[n:]] == ["EXTERNAL", "DERIVE", "DERIVE"]


def test_solve_provenance_follows_the_value_the_answer_names():
    """probes-2 / V2R-3 / V21R-6 (v2.1 bug, fixed)."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "y four", relation="y = 4")
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    assert st.detail == "unique: x = 3, y = 4"
    t.answer(["x"])
    assert names_in(t.ledger(), "commitments") == ["r1"]


def test_solve_per_value_sets_in_a_coupled_system():
    """fresh-3 note: with r1: x + y = 3, r2: x - y = 1, r3: 2x = 4, x needs only r3
    and y the first-cited pair r1, r2; nothing is reported as not needed."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "r1", relation="x + y = 3")
    t.input(ROOT, "r2", "model", "r2", relation="x - y = 1")
    t.input(ROOT, "r3", "model", "r3", relation="2*x = 4")
    st = t.solve(ROOT, ["r1", "r2", "r3"], ["x", "y"])
    assert st.detail == "unique: x = 2, y = 1"
    assert [t.steps[t.value_step[n]].detail for n in ("x", "y")] == ["follows from r3", "follows from r1, r2"]
    t.answer(["x"], label="px")
    t.answer(["y"], label="py")
    assert names_in(t.ledger("px"), "commitments") == ["r3"]
    assert names_in(t.ledger("py"), "commitments") == ["r1", "r2"]


def test_withdrawing_a_premise_only_y_needs_leaves_x_usable():
    """probes-2 / R26d (v2.1 bug, fixed): the union provenance also over-tainted."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "y four", relation="y = 4")
    t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    t.withdraw(ROOT, "r2", "y was mis-stated")
    assert t.derive(ROOT, "2*x = 6").check == "checked"
    assert t.answer(["x"]).detail == "x = 3"
    with pytest.raises(TraceError, match="the value of 'y' rests on 'r2', which was withdrawn; determine it again"):
        t.answer(["y"])


def test_solve_report_step_is_neither_in_the_cone_nor_outside_an_answer_its_values_feed():
    """v2.3: the per-value DERIVEs carry the provenance and do not depend on the
    EXTERNAL report, which still binds the fixed names. When one of its DERIVEs
    feeds the answer, the report is listed neither in the cone nor under 'Other
    steps that do not feed the answer' (v2.2 listed it there, although each
    DERIVE says 'value fixed by the linear solve [k]'); an answer none of its
    DERIVEs feed still lists it there. The hypothesis set has one member per
    fixed value instead."""
    t = finish(atwood())
    st = next(s for s in t.steps if s.op == "EXTERNAL" and s.kind == "solve")
    assert st.binds == ("a1", "a2", "T1", "T2")
    led = t.ledger()
    outside = [r["step"] for r in led["outside_answer"]]
    assert st.index not in t.cone() and st.id not in outside
    assert st.id not in [s["step"] for s in led["step_members"]]
    assert [s["claim"] for s in led["step_members"] if s["tag"] == "solve"] == ["a1 = 49/20", "a2 = -49/20",
                                                                               "T1 = 147/4"]
    assert t.steps[t.value_step["T2"]].id in outside  # the DERIVE of a value the answer does not name
    assert st.id not in [m["from"] for m in t.hypothesis_set()]
    s = Trace("q")
    unknowns(s, ROOT, "x", "y")
    s.input(ROOT, "r1", "model", "x three", relation="x = 3")
    s.input(ROOT, "r2", "model", "y four", relation="y = 4")
    rep = s.solve(ROOT, ["r1", "r2"], ["x", "y"])
    s.input(ROOT, "k", "value", "k", value=1)
    s.answer(["k"], label="pk")
    s.answer(["x"], label="px")
    assert rep.id in [r["step"] for r in s.ledger("pk")["outside_answer"]]
    assert rep.id not in [r["step"] for r in s.ledger("px")["outside_answer"]] and rep.index not in s.cone("px")


def test_dense_ten_by_ten_solve_is_fast():
    """V21-6 / fresh-4 (v2.1 bug, fixed): a dense 10x10 solve took 12.6 s."""
    t, rels, names = dense_system(10)
    t0 = time.perf_counter()
    st = t.solve(ROOT, rels, names)
    assert time.perf_counter() - t0 < 5 and st.detail.startswith("unique")


def dense_system(k, seed=3):
    rnd = random.Random(seed)
    t = Trace("q")
    names = [f"x{i}" for i in range(k)]
    unknowns(t, ROOT, *names)
    rels = []
    for j in range(k):
        eq = " + ".join(f"{rnd.randint(1, 9)}*{n}" for n in names) + f" = {rnd.randint(1, 50)}"
        t.input(ROOT, f"r{j}", "model", f"row {j}", relation=eq)
        rels.append(f"r{j}")
    return t, rels, names


def test_gap_exhaustive_search_cost_peaks_at_eight_relations(monkeypatch):
    """Note: the exhaustive search costs up to k*(2**k - 1) entailment checks for a
    dense system, so the cliff moved from 10 to 8: 2040 checks at 8 relations
    (about 1.2 s here) against 81 at 9 (greedy)."""
    calls = []
    real = handtrace.entails
    monkeypatch.setattr(handtrace, "entails", lambda *a, **k: calls.append(1) or real(*a, **k))
    counts = {}
    for k in (8, 9):
        t, rels, names = dense_system(k)
        calls.clear()
        t.solve(ROOT, rels, names)
        counts[k] = len(calls)
    assert counts == {8: 8 * 255, 9: 81}


# -- consistency() -----------------------------------------------------------------------------


def test_consistency_records_a_conflict_without_raising_in_strict_mode():
    """spring2-3: a deliberate conflict needed the undocumented solve(..., [])."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "a", "model", "spring-only account", relation="x = 3")
    t.input(ROOT, "b", "model", "trajectory", relation="x = 4")
    bad = t.consistency(ROOT, ["a", "b"], text="spring-only account against the trajectory", tag="C1")
    assert (bad.op, bad.kind, bad.ref, bad.check, bad.binds) == ("EXTERNAL", "consistency", "consistency check",
                                                                  "failed", ())
    assert bad.detail == "conflict: a, b contradict each other or the values visible here"
    ok = t.consistency(ROOT, ["a"])
    assert ok.check == "checked" and ok.detail == "consistent" and ok.text == "consistency check"
    assert "x" not in t.values
    t.input(ROOT, "k", "value", "k", value=1)
    t.answer(["k"])
    led = t.ledger()
    assert [c["step"] for c in led["conflicts"]] == [bad.id]
    assert led["solve_reports"] == [] and led["mistakes"] == []
    assert bad.index not in t.cone() and ok.index not in t.cone()


def test_consistency_uses_the_values_visible_here():
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    t.input(ROOT, "g", "value", "g", value=10)
    unknowns(t, ROOT, "W")
    t.input(ROOT, "w", "model", "weight", relation="W = m*g")  # linear once m, g are substituted
    t.input(ROOT, "rW", "model", "measured weight", relation="W = 21")
    assert t.consistency(ROOT, ["w", "rW"]).check == "failed"
    unknowns(t, ROOT, "p", "q")
    t.input(ROOT, "pq", "model", "an open product", relation="p*q = 1")
    with pytest.raises(TraceError, match="cannot check consistency"):
        t.consistency(ROOT, ["pq"])


def test_consistency_refuses_bad_arguments_and_replays():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "a", "model", "a", relation="x = 3")
    t.input(ROOT, "m", "value", "m", value=1)
    for rels, msg in (([], "distinct"), (["a", "a"], "distinct"), (["m"], "not a relation")):
        with pytest.raises(TraceError, match=msg):
            t.consistency(ROOT, rels)
    t.input(ROOT, "b", "model", "b", relation="x = 4")
    t.consistency(ROOT, ["a", "b"], uses=["m"])
    again = roundtrip(t)
    assert again.to_record() == t.to_record() and again.steps[-1].check == "failed"


def test_consistency_of_a_hidden_nonlinear_relation_is_a_hidden_lookup():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, d, "W", "m")
    t.input(d, "w", "model", "weight", relation="W = m*10")
    unknowns(t, d, "p")
    t.input(d, "pm", "model", "product", relation="p*m = 1")
    t.input(ROOT, "rm", "model", "m two", relation="m = 2")
    t.solve(ROOT, ["rm"], ["m"])
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.consistency(d, ["pm"])


def test_consistency_with_a_hidden_linear_value_is_a_hidden_lookup():
    """probes-3 / V21R-3 (v2.1 bug, fixed): v2.1 recorded 'consistent'."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, d, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    t.input(d, "r", "model", "x five", relation="x = 5")
    assert t.visible(d, "x") is not None and t.value_visible(d, "x") is None
    n = len(t.steps)
    with pytest.raises(HiddenLookupError, match="would change the result"):
        t.consistency(d, ["r"])
    assert len(t.steps) == n


def test_consistency_ignores_a_hidden_value_that_cannot_change_the_result():
    """v2.2 rule: a hidden value blocks consistency() only if it would change the result."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, d, "x", "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    t.input(d, "free", "model", "x plus y", relation="x + y = 7")  # y absorbs any x
    t.input(d, "same", "model", "x three again", relation="x = 3")  # true for the hidden x = 3
    assert t.consistency(d, ["free"]).detail == "consistent"
    assert t.consistency(d, ["same"]).detail == "consistent"
    t.input(d, "y2", "model", "y two", relation="y = 2")
    assert t.consistency(d, ["y2", "same"]).detail == "consistent"
    with pytest.raises(HiddenLookupError):  # y = 2 and x + y = 7 force x = 5
        t.consistency(d, ["y2", "free"])


# -- strict and lenient nonlinear claims --------------------------------------------------


def test_nonlinear_claim_without_relations_is_refused_in_strict_mode():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "x*y = 6", name="conj")
    assert "conj" not in t.bindings and ops(t) == ["CONTRACT", "CONTRACT"]


def test_unchecked_derive_cannot_determine_a_value():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "sq", "model", "x squared is 4", relation="x*x = 4")
    with pytest.raises(CheckError):
        t.derive(ROOT, "x = 1000", binds="x", from_relations=["sq"])
    assert "x" not in t.values

    lt = Trace("q", strict=False)
    unknowns(lt, ROOT, "x")
    lt.input(ROOT, "sq", "model", "x squared is 4", relation="x*x = 4")
    st = lt.derive(ROOT, "x = 1000", binds="x", from_relations=["sq"])
    assert st.check == "unchecked" and "x not determined" in st.detail and "x" not in lt.values


def test_nonlinearity_disappears_where_values_are_visible_only():
    t = Trace("q")
    d1, d2 = t.demand(ROOT, "D1", "one"), t.demand(ROOT, "D2", "two")
    unknowns(t, d1, "m", "g", "W")
    t.input(d1, "w", "model", "weight", relation="W = m*g")
    t.deliver_many(d2, ["w", "W", "m", "g"])  # names only: no values exist yet
    t.input(d1, "rm", "model", "m three", relation="m = 3")
    t.input(d1, "rg", "model", "g", relation="g = 9.8")
    t.derive(d1, "m = 3", binds="m", from_relations=["rm"])
    t.derive(d1, "g = 9.8", binds="g", from_relations=["rg"])
    assert t.derive(d1, "W = 147/5", from_relations=["w"]).check == "checked"
    assert t.derive(ROOT, "W = 147/5", from_relations=["w"]).check == "checked"  # values flow up
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d2, "W = 147/5", from_relations=["w"])
    with pytest.raises(HiddenLookupError, match="deliver"):  # v2: a plain TraceError
        t.solve(d2, ["w"], ["W"])
    t.deliver_many(d2, ["m", "g"])  # now with their values
    assert t.derive(d2, "W = 147/5", from_relations=["w"]).check == "checked"


def test_answer_resting_on_an_unchecked_derive_is_warned():
    """probes-1 / V2R-2: an unchecked derive registered with name= still determines
    a value through a later checked derive, but the answer is now warned."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y")
    conj = t.derive(ROOT, "x*y = 6", name="conj")
    t.input(ROOT, "ry", "model", "y two", relation="y = 2")
    t.derive(ROOT, "y = 2", binds="y", from_relations=["ry"])
    t.derive(ROOT, "x = 3", binds="x", from_relations=["conj"])
    t.answer(["x"])
    led = t.ledger()
    assert conj.index in t.cone() and names_in(led, "commitments") == ["ry"]
    assert f"the answer rests on {conj.id}, which could not be checked" in led["warnings"]
    assert [u["step"] for u in led["unchecked"]] == [conj.id]


def test_unchecked_external_competence_is_not_warned():
    t = Trace("q")
    unknowns(t, ROOT, "a1", "a2")
    t.external(ROOT, "differentiation", "length constraint", relation="a1 + a2 = 0", binds="kin")
    t.input(ROOT, "r", "model", "a1 one", relation="a1 = 1")
    t.solve(ROOT, ["r", "kin"], ["a1", "a2"])
    t.answer(["a2"])
    led = t.ledger()
    assert len(led["unchecked"]) == 1 and not any("could not be checked" in w for w in led["warnings"])


def test_superfluous_nonlinear_citation_no_longer_blocks_a_check():
    """V2R-21: r1 alone checks x = 3; the nonlinear r2 is reported as not needed."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    r1 = t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    r2 = t.input(ROOT, "r2", "model", "a product", relation="y*z = 1")
    st = t.derive(ROOT, "x = 3", from_relations=["r1", "r2"], binds="x")
    assert st.check == "checked" and st.detail == "follows from r1 (nonlinear citations not checked: r2)"
    assert r1.index in st.deps and r2.index not in st.deps and t.values["x"] == 3
    unknowns(t, ROOT, "w")
    t.input(ROOT, "r3", "model", "z one", relation="z = 1")
    t.input(ROOT, "r4", "model", "w two", relation="w = 2")
    both = t.derive(ROOT, "w = 2", from_relations=["r2", "r3", "r4"])
    assert both.detail == "follows from r4 (cited but not needed: r3) (nonlinear citations not checked: r2)"

    lt = Trace("q", strict=False)
    unknowns(lt, ROOT, "x", "y", "z")
    lt.input(ROOT, "r1", "model", "x and y", relation="x + y = 3")
    lt.input(ROOT, "r2", "model", "a product", relation="y*z = 1")
    st = lt.derive(ROOT, "x = 3", from_relations=["r1", "r2"])
    assert st.check == "unchecked" and "needs the nonlinear relations r2" in st.detail

    s = Trace("q")
    unknowns(s, ROOT, "x", "y", "z")
    s.input(ROOT, "r1", "model", "x and y", relation="x + y = 3")
    s.input(ROOT, "r2", "model", "a product", relation="y*z = 1")
    with pytest.raises(CheckError, match="unchecked"):
        s.derive(ROOT, "x = 3", from_relations=["r1", "r2"])


def test_superfluous_nonlinear_citation_that_contradicts_is_noted_not_checked():
    """V21-7 / fresh-7: rn reads 0 = 6 once x = 0; v2.2 still passes the step, but the
    detail now says that rn was not checked."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "rx", "model", "x zero", relation="x = 0")
    t.input(ROOT, "rn", "model", "a product", relation="x*y = 6")
    st = t.derive(ROOT, "x = 0", from_relations=["rx", "rn"], binds="x")
    assert st.check == "checked" and st.detail == "follows from rx (nonlinear citations not checked: rn)"
    assert t.consistency(ROOT, ["rn"]).check == "failed"  # an explicit check does see it


def test_gap_linear_refutation_is_unchecked_when_a_nonlinear_relation_is_cited():
    """Design gap left open by v2.2 (probes-10): x = 4 contradicts r1 alone (no
    further relation can rescue it), but citing the unrelated nonlinear r2 turns
    the found mistake into 'unchecked'."""
    lt = Trace("q", strict=False)
    unknowns(lt, ROOT, "x", "y", "z")
    lt.input(ROOT, "r1", "model", "x three", relation="x = 3")
    lt.input(ROOT, "r2", "model", "a product", relation="y*z = 1")
    with_r2 = lt.derive(ROOT, "x = 4", from_relations=["r1", "r2"])
    alone = lt.derive(ROOT, "x = 4", from_relations=["r1"])
    assert with_r2.check == "unchecked" and alone.check == "failed" and alone.detail.startswith("mistake")


# -- claims and relations that cannot be evaluated --------------------------------------------


def test_division_by_zero_claim_is_a_mistake_and_relation_a_conflict():
    """v2.2: _verdict records what cannot be evaluated instead of crashing."""
    t = Trace("q", strict=False)
    t.input(ROOT, "m", "value", "mass", value=0)
    unknowns(t, ROOT, "a", "F")
    claim = t.derive(ROOT, "a = 6/m")
    assert claim.check == "failed" and claim.detail == ("mistake: the claim cannot be evaluated with these values "
                                                        "(division by zero)")
    t.input(ROOT, "e8", "model", "E8", relation="a = F/m")
    t.input(ROOT, "rF", "model", "F six", relation="F = 6")
    rel = t.derive(ROOT, "F = 6", from_relations=["rF", "e8"])
    assert rel.check == "failed" and rel.detail == ("conflict: relation e8 cannot be evaluated with these values "
                                                    "(division by zero)")
    assert t.consistency(ROOT, ["e8"]).check == "failed"
    t.answer(["m"])
    led = t.ledger()
    assert [m["step"] for m in led["mistakes"]] == [claim.id] and rel.id in [c["step"] for c in led["conflicts"]]
    s = Trace("q")
    s.input(ROOT, "m", "value", "mass", value=0)
    with pytest.raises(CheckError, match="cannot be evaluated"):
        s.derive(ROOT, "6/m = 1")
    unknowns(s, ROOT, "a")
    s.input(ROOT, "e8", "model", "E8", relation="a = 6/m")
    with pytest.raises(TraceError, match="division by zero"):  # solve() still refuses rather than records
        s.solve(ROOT, ["e8"], ["a"])


def sqrt_trace():
    t = Trace("q", strict=False)
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "h", "value", "drop height", value=5)
    t.input(ROOT, "n", "value", "a count", value=3)
    unknowns(t, ROOT, "v")
    t.input(ROOT, "fall", "model", "free-fall speed", relation="v = (2*g*h)**0.5")  # true: v = 10
    t.input(ROOT, "rv", "model", "measured speed", relation="v = 10")
    return t


@pytest.mark.parametrize("case", ["square-root claim", "modulo claim", "cited square-root relation",
                                  "consistency of a square-root relation"])
def test_syntax_the_checker_cannot_parse_is_not_a_found_mistake_or_conflict(case):
    """v2.2 bug, fixed in v2.3: a claim or relation the checker could not parse (a
    non-integer power, '%') was filed as a found mistake or a premise conflict,
    although 10 = (2*g*h)**0.5 is true at g = 10, h = 5. v2.3 evaluates the root
    exactly and refuses '%' at entry with a TraceError."""
    t = sqrt_trace()
    call = {"square-root claim": lambda: t.derive(ROOT, "10 = (2*g*h)**0.5"),
            "modulo claim": lambda: t.derive(ROOT, "n % 2 = 1"),
            "cited square-root relation": lambda: t.derive(ROOT, "v = 10", from_relations=["rv", "fall"]),
            "consistency of a square-root relation": lambda: t.consistency(ROOT, ["fall", "rv"])}[case]
    try:
        st = call()
    except TraceError:
        return  # refusing, as v2.1 did, is also acceptable
    assert st.check != "failed"  # v2.2: 'failed', filed under mistakes or conflicts (fixed in v2.3)


def test_global_check_evaluates_a_square_root_relation_exactly():
    """v2.3: the global check evaluates v = (2*g*h)**0.5 exactly (v = 10 at g = 10,
    h = 5), so a true square-root relation in the cone is no conflict and draws no
    warning (v2.2 called it undefined); a false one is contradicted, and one that
    the trace's own values make an even root of a negative number is undefined."""
    t = sqrt_trace()
    t.derive(ROOT, "v = 10", binds="v", from_relations=["rv"], uses=["fall"])
    t.answer(["v"])
    led = t.ledger()
    assert led["conflicts"] == []
    assert led["warnings"] == ["4 commitment(s) have no status yet: g, h, fall, rv"]
    wrong = sqrt_trace()
    wrong.input(ROOT, "rv11", "model", "a misread speed", relation="v = 11")
    wrong.derive(ROOT, "v = 11", binds="v", from_relations=["rv11"], uses=["fall"])
    wrong.answer(["v"])
    led = wrong.ledger()
    assert refs_in(led, "conflicts") == ["fall"]
    assert led["conflicts"][0]["detail"] == ("conflict: fall is contradicted by the values determined in this trace "
                                             "(lhs - rhs = 1)")
    assert "the answer rests on fall, which the trace's own values contradict" in led["warnings"]
    neg = Trace("q", strict=False)
    neg.input(ROOT, "g", "value", "g", value=10)
    neg.input(ROOT, "h", "value", "a negative drop height", value=-5)
    unknowns(neg, ROOT, "v")
    neg.input(ROOT, "fall", "model", "free-fall speed", relation="v = (2*g*h)**0.5")
    neg.input(ROOT, "rv", "model", "measured speed", relation="v = 10")
    neg.derive(ROOT, "v = 10", binds="v", from_relations=["rv"], uses=["fall"])
    neg.answer(["v"])
    led = neg.ledger()
    assert refs_in(led, "conflicts") == ["fall"]
    assert led["conflicts"][0]["detail"] == ("conflict: fall cannot be evaluated with the values determined in this "
                                             "trace (an even root of a negative number)")
    assert "the answer rests on fall, which the trace's own values make undefined" in led["warnings"]


# -- hidden lookups ---------------------------------------------------------------------------


def test_name_visible_value_hidden_raises_hidden_lookup():
    for strict in (True, False):
        t = Trace("q", strict=strict)
        d1 = t.demand(ROOT, "D1", "one")
        unknowns(t, d1, "x")
        t.input(ROOT, "r", "model", "x three", relation="x = 3")
        t.solve(ROOT, ["r"], ["x"])
        n = len(t.steps)
        with pytest.raises(HiddenLookupError, match="deliver"):
            t.derive(d1, "2*x = 6")
        assert len(t.steps) == n  # not recorded as a found mistake


def test_hidden_value_in_binds_or_solve_is_a_hidden_lookup():
    """probes-13 / V2R-20: v2 raised a plain TraceError in both places."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, d, "x", "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    t.input(d, "r", "model", "y is x plus one", relation="y = x + 1")
    n = len(t.steps)
    with pytest.raises(HiddenLookupError):
        t.derive(d, "y = 4", from_relations=["r"])
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d, "y = x + 1", binds="y", from_relations=["r"])
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.solve(d, ["r"], ["y"])
    assert len(t.steps) == n and "y" not in t.values
    t.deliver(d, "x")
    assert t.derive(d, "y = x + 1", binds="y", from_relations=["r"]).check == "checked" and t.values["y"] == 4


def test_cancelled_hidden_value_does_not_turn_a_slip_into_a_hidden_lookup():
    """The case v2.1 already fixed: a hidden name that cancels out of the residual."""
    t = Trace("q", strict=False)
    d1 = t.demand(ROOT, "D1", "d")
    unknowns(t, ROOT, "y")
    t.deliver(d1, "y")
    t.input(ROOT, "ry", "model", "y five", relation="y = 5")
    t.derive(ROOT, "y = 5", binds="y", from_relations=["ry"])
    unknowns(t, d1, "x")
    t.input(d1, "r", "model", "x three", relation="x = 3")
    st = t.derive(d1, "x = 4 + 0*y", from_relations=["r"])
    assert st.check == "failed" and st.detail.startswith("mistake: does not follow from r")


def hidden_y_trace(y_value, r2):
    """y = y_value fixed at ROOT and delivered name-only into D1; in D1, r: x = 3 and r2."""
    t = Trace("q", strict=False)
    d1 = t.demand(ROOT, "D1", "d")
    unknowns(t, ROOT, "y", "z")
    t.deliver_many(d1, ["y", "z"])
    t.input(ROOT, "ry", "model", "y at ROOT", relation=f"y = {y_value}")
    t.derive(ROOT, f"y = {y_value}", binds="y", from_relations=["ry"])
    unknowns(t, d1, "x")
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "a relation on y", relation=r2)
    assert t.visible(d1, "y") is not None and t.value_visible(d1, "y") is None
    return t, d1


@pytest.mark.parametrize("y_value, r2", [(5, "y = 5"), (5, "y = z")])
def test_unrelated_hidden_value_in_a_cited_relation_does_not_block_a_mistake(y_value, r2):
    """V2R-19 / probes-4 / V21R-7 (v2.1 bugs, fixed): the hidden y cannot change the verdict."""
    t, d1 = hidden_y_trace(y_value, r2)
    st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("mistake: does not follow from r, r2")


def test_hidden_value_that_would_make_the_claim_follow_is_a_hidden_lookup():
    t, d1 = hidden_y_trace(5, "y = 5")
    n = len(t.steps)
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d1, "x + y = 8", from_relations=["r"])
    assert len(t.steps) == n


def test_hidden_value_that_turns_a_mistake_into_a_conflict_is_a_hidden_lookup():
    """v2.2 bug, fixed in v2.3: the hidden-value rule compared only the check status
    ('failed' both ways), so a hidden y = 6 that would make the cited r2 (y = 5) a
    premise conflict was ignored and the step was filed as a found mistake; the
    rule now compares the verdict category."""
    t, d1 = hidden_y_trace(6, "y = 5")
    with pytest.raises(HiddenLookupError):
        t.derive(d1, "x = 4", from_relations=["r", "r2"])  # v2.2: 'failed', 'mistake: does not follow ...'


# -- visibility and delivery ----------------------------------------------------------


def test_results_flow_up_two_levels_not_sideways_and_not_down():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "one")
    d1a = t.demand(d1, "D1a", "child")
    d2 = t.demand(ROOT, "D2", "two")
    t.input(d1a, "m", "value", "m", value=3)
    t.input(ROOT, "k", "value", "k", value=2)
    assert t.derive(ROOT, "m = 3").check == "checked"
    with pytest.raises(HiddenLookupError):
        t.derive(d2, "m = 3")
    with pytest.raises(HiddenLookupError):
        t.derive(d1, "k = 2")  # root bindings need delivery down


def test_nothing_can_be_delivered_into_the_root():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "one")
    t.input(d1, "m", "value", "m", value=3)
    for call in (lambda: t.deliver(ROOT, "m"), lambda: t.deliver_many(ROOT, ["m"])):
        with pytest.raises(TraceError, match="root"):
            call()
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(ROOT, "m")


def test_caller_only_delivery_chain():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    t.input(ROOT, "g", "value", "g", value="9.8")
    with pytest.raises(HiddenLookupError, match="caller 'D1a'.*deliver_through"):
        t.deliver(d1b, "g")
    with pytest.raises(HiddenLookupError, match="caller 'D1'"):
        t.deliver(d1a, "g")
    st = t.deliver(d1, "g")
    assert "delivered from ROOT" in st.text and "49/5" in st.text
    assert t.value_visible(d1a, "g") == t.value_visible(d1b, "g") == st.index  # the ancestor chain counts
    with pytest.raises(TraceError, match="already visible"):
        t.deliver(d1a, "g")
    unknowns(t, d1b, "W")
    t.input(d1b, "w", "model", "weight", relation="W = 3*g")
    t.derive(d1b, "W = 147/5", binds="W", from_relations=["w"])
    t.answer(["W"])
    # v2.2: steps depend on the binding and value steps, not on the DELIVER that carried them
    assert st.index not in t.cone() and t.bindings["g"].step in t.cone()
    assert "g" in names_in(t.ledger(), "commitments")


def test_delivery_to_a_cousin_goes_through_the_common_caller():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d2 = t.demand(ROOT, "D2", "c")
    d2a = t.demand(d2, "D2a", "d")
    t.input(d1a, "k", "value", "k", value=2)
    with pytest.raises(HiddenLookupError, match="caller 'D2'"):
        t.deliver(d2a, "k")
    st = t.deliver(d2, "k")
    assert "delivered from ROOT" in st.text and st.deps == (t.bindings["k"].step,)
    assert t.value_visible(d2a, "k") == st.index


def test_delivery_before_value_carries_name_only():
    t = Trace("q")
    d1, d2 = t.demand(ROOT, "D1", "one"), t.demand(ROOT, "D2", "two")
    unknowns(t, d1, "x")
    t.deliver(d2, "x")
    t.input(d1, "rx", "model", "x three", relation="x = 3")
    t.derive(d1, "x = 3", binds="x", from_relations=["rx"])
    assert t.value_visible(d2, "x") is None and t.value_visible(ROOT, "x") is not None
    unknowns(t, d2, "y")
    t.input(d2, "ry", "model", "y is x", relation="y = x")
    with pytest.raises(HiddenLookupError, match="deliver"):  # v2: TraceError 'not a value'
        t.derive(d2, "y = x", binds="y", from_relations=["ry"])
    st = t.deliver(d2, "x")
    assert "x = 3" in st.text and t.value_visible(d2, "x") == st.index


def test_deliver_of_a_determined_value_names_the_binding_and_the_value_step():
    """spring1-4 / spring2-8: v2 named only the declaration."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    decl = t.unknown(ROOT, "x", "x", address="(x)", ref="test", unit="m")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    fix = t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    st = t.deliver(d, "x")
    assert st.text.startswith(f"x = 3 m, delivered from ROOT (bound at {decl.id}, value fixed at {fix.id})")
    assert st.ref == decl.id and st.deps == (decl.index, fix.index)
    g = t.input(ROOT, "g", "value", "g", value=10)
    assert f"(bound at {g.id})" in t.deliver(d, "g").text  # an INPUT value: one step


def test_value_delivered_to_ancestor_is_visible_below():
    t = Trace("q")
    d2 = t.demand(ROOT, "D2", "two")
    d2a = t.demand(d2, "D2a", "child")
    unknowns(t, d2, "x")
    t.deliver(d2a, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    st = t.deliver(d2, "x")
    assert t.value_visible(d2a, "x") == st.index
    assert t.derive(d2a, "2*x = 6").check == "checked"


def test_delivery_after_the_value_is_determined_higher_up():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, d1a, "x", "y")
    t.input(d1a, "ry", "model", "y twice x", relation="y = 2*x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    assert t.visible(d1a, "x") is not None and t.value_visible(d1a, "x") is None
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d1a, "2*x = 6")
    st = t.deliver(d1, "x")
    assert "x = 3" in st.text and t.value_visible(d1a, "x") == st.index
    t.derive(d1a, "y = 6", binds="y", from_relations=["ry"])
    t.answer(["y"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["rx", "ry"]


def test_deliver_names_the_caller_when_only_the_value_is_missing():
    """probes-12: v2 said 'already visible; no delivery needed'."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, d1a, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    with pytest.raises(HiddenLookupError, match="caller 'D1'") as exc:
        t.deliver(d1a, "x")
    assert "no delivery needed" not in str(exc.value)


def test_gap_redelivering_a_value_into_its_binding_frame_exposes_it_below():
    """Note (probes-15): D1's own binding x is invisible to its child D1a, but the
    DELIVER that brings x's value back into D1 also makes x visible in D1a."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, d1, "x")
    t.input(d1, "g", "value", "g", value=10)
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    assert t.visible(d1a, "x") is None and t.visible(d1a, "g") is None
    st = t.deliver(d1, "x")
    assert t.visible(d1a, "x") == t.value_visible(d1a, "x") == st.index
    assert t.visible(d1a, "g") is None


# -- deliver_many and deliver_through -----------------------------------------------------


@pytest.mark.parametrize("bad", ["nope", "w", "hid", "g", "g_twice"])
def test_deliver_many_is_all_or_nothing(bad):
    """probes-2 / V2R-10: v2 kept the deliveries before the failing name."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d = t.demand(d1, "D1a", "b")
    t.input(d1, "k", "value", "D1's own value: visible at D1, not at D1a", value=2)
    for n_, v in (("g", 1), ("hid", 3)):
        t.input(ROOT, n_, "value", n_, value=v)
    t.input(ROOT, "w", "completeness", "only the spring")
    t.deliver_many(d1, ["g", "w"])  # g and w now reach D1a too; hid stays hidden at D1a's caller D1
    t.withdraw(ROOT, "w", "the trajectory says otherwise")
    names = {"nope": ["k", "nope"], "w": ["k", "w"], "hid": ["k", "hid"], "g": ["k", "g"],
             "g_twice": ["k", "k"]}[bad]
    n, c = len(t.steps), len(t.commands)
    with pytest.raises(TraceError):
        t.deliver_many(d, names)
    assert len(t.steps) == n and len(t.commands) == c and t.visible(d, "k") is None
    assert t.deliver_many(d, ["k"])[0].frame == "D1a"  # the good name alone goes through


def test_deliver_many_is_all_or_nothing_for_a_tainted_name():
    """probes-7 / V21R-2 (v2.1 bug, fixed), in v2.2 form: the name r itself rests on
    the withdrawn c (a tainted VALUE alone no longer blocks delivery of the name)."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "only the spring")
    t.input(ROOT, "r", "model", "x one, given c", relation="x = 1", uses=["c"])
    t.input(ROOT, "g", "value", "g", value=1)
    t.withdraw(ROOT, "c", "wrong")
    n, c = len(t.steps), len(t.commands)
    with pytest.raises(TraceError, match="'r' rests on 'c', which was withdrawn"):
        t.deliver_many(d, ["g", "r"])
    assert len(t.steps) == n and len(t.commands) == c and t.visible(d, "g") is None


def test_name_with_a_tainted_value_is_delivered_without_the_value():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    decl = t.unknown(ROOT, "x", "x", address="(x)", ref="test")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.withdraw(ROOT, "rx", "wrong")
    st = t.deliver_many(d, ["x"])[0]
    assert st.text.startswith(f"x, delivered from ROOT (bound at {decl.id})") and st.deps == (decl.index,)
    assert t.visible(d, "x") == st.index and t.value_visible(d, "x") is None
    with pytest.raises(TraceError, match="already visible"):
        t.deliver(d, "x")


def test_deliver_through_one_level_is_a_deliver():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "c", "completeness", "only the spring")
    steps = t.deliver_through(d, "g") + t.deliver_through(d, "c")
    assert [(s.op, s.frame, s.uses) for s in steps] == [("DELIVER", "D", ("g",)), ("DELIVER", "D", ("c",))]
    assert t.value_visible(d, "g") == steps[0].index and t.visible(d, "c") == steps[1].index
    assert [c["op"] for c in t.commands[-2:]] == ["deliver", "deliver"]  # replays as plain deliveries
    roundtrip(t)
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(d, "g")


@pytest.mark.parametrize("case", ["root value to great-grandchild", "grandchild's own unknown",
                                  "name in the middle, value at the root"])
def test_deliver_through_reaches_frames_below_the_caller(case):
    """probes-1 / regress-1 / V21R-1 (v2.1 bug, fixed): one DELIVER into the highest
    frame below the nearest frame that sees the name with its value."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    if case == "root value to great-grandchild":
        t.input(ROOT, "g", "value", "g", value="9.8")
        target, name = d1b, "g"
    elif case == "grandchild's own unknown":  # the remedy the HiddenLookupError for this case recommends
        unknowns(t, d1a, "x")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
        t.solve(ROOT, ["rx"], ["x"])
        target, name = d1a, "x"
    else:  # D1 already sees the name (delivered before the value existed), not the value
        unknowns(t, ROOT, "x")
        t.deliver(d1, "x")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
        t.solve(ROOT, ["rx"], ["x"])
        target, name = d1b, "x"
    n, c = len(t.steps), len(t.commands)
    steps = t.deliver_through(target, name)
    assert len(steps) == 1 and len(t.steps) == n + 1 and len(t.commands) == c + 1
    assert steps[0].op == "DELIVER" and steps[0].frame == "D1" and "delivered from ROOT" in steps[0].text
    assert t.value_visible(target, name) == steps[0].index
    assert t.commands[-1] == {"op": "deliver", "args": {"frame": "D1", "name": name, "text": ""}}
    roundtrip(t)


@pytest.mark.parametrize("name", ["nope", "c", "r"])
def test_deliver_through_refuses_unbound_withdrawn_and_tainted_names_as_trace_errors(name):
    """probes-13 / V21-15 (v2.1 friction, closed): v2.1 raised HiddenLookupError
    'not visible at the root', which invites a delivery."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "only the spring")
    t.input(ROOT, "r", "model", "x one, given c", relation="x = 1", uses=["c"])
    t.withdraw(ROOT, "c", "the trajectory says otherwise")
    n = len(t.steps)
    msg = {"nope": "not bound anywhere", "c": "was withdrawn at", "r": "rests on 'c'"}[name]
    with pytest.raises(TraceError, match=msg) as exc:
        t.deliver_through(d, name)
    assert not isinstance(exc.value, HiddenLookupError) and len(t.steps) == n


# -- ledger and cone ---------------------------------------------------------------------


def test_atwood_fixture_cone_has_every_input():
    led = finish(atwood()).ledger()
    assert set(names_in(led, "commitments")) == {"m1", "m2", "g", "peqv1", "peqv2", "w1", "w2", "meq"}
    assert names_in(led, "not_in_answer") == [] and led["conflicts"] == [] and led["mistakes"] == []


def test_ledger_has_the_v22_sections():
    led = finish(atwood()).ledger()
    for key in ("mistakes", "conflicts", "unchecked", "solve_reports", "withdrawn", "pruned", "outside_answer",
                "label", "warnings"):
        assert key in led
    assert "failed" not in led and led["label"] == "p1"


def test_value_substituted_through_relation_stays_in_cone():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "y is twice x", relation="y = 2*x")
    t.input(ROOT, "rx", "model", "x is three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.derive(ROOT, "y = 6", binds="y", from_relations=["r"])
    t.answer(["y"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["r", "rx"]


def test_value_substituted_into_a_solve_stays_in_cone():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "y is twice x", relation="y = 2*x")
    t.input(ROOT, "k", "value", "stiffness", value=20)
    t.input(ROOT, "rx", "model", "x from k", relation="x = k/10")
    t.solve(ROOT, ["rx"], ["x"])
    t.solve(ROOT, ["r"], ["y"])
    t.answer(["y"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["k", "r", "rx"]


def atwood_laws_first():
    """The Atwood fixture with each law written before its weight is derived."""
    t = Trace("Atwood")
    for k, m in ((1, 3), (2, 5)):
        d = t.demand(ROOT, f"D{k}", f"acceleration of B{k}")
        t.input(d, f"m{k}", "value", f"mass of B{k}", value=m, unit="kg")
        if k == 1:
            t.input(d, "g", "value", "local g", value="9.8")
        else:
            t.deliver(d, "g")
        for n, a in ((f"fG{k}", f"(G{k})"), (f"T{k}", f"(S{k})"), (f"a{k}", f"(a{k})")):
            t.unknown(d, n, n, address=a, ref="C-CM")
        t.contract(d, "C-FS", "net force", source="S8.1", binds=f"law{k}", relation=f"m{k}*a{k} = fG{k} + T{k}")
        t.input(d, f"w{k}", "model", f"uniform-field weight on B{k}", relation=f"fG{k} = -m{k}*g")
        t.derive(d, f"fG{k} = {-m * Fraction(49, 5)}", from_relations=[f"w{k}"], binds=f"fG{k}")
    t.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "length constraint", relation="a1 + a2 = 0", binds="kin")
    t.solve(ROOT, ["law1", "law2", "meq", "kin"], ["a1", "a2", "T1", "T2"])
    t.answer(["a1"])
    return t


def test_laws_first_atwood_still_solves():
    assert atwood_laws_first().values["a1"] == Fraction(49, 20)


def test_laws_first_atwood_cone_keeps_g_and_weights():
    led = atwood_laws_first().ledger()
    assert set(names_in(led, "commitments")) == {"m1", "m2", "g", "w1", "w2", "meq"}
    assert names_in(led, "not_in_answer") == [] and led["conflicts"] == []


def test_redelivered_value_used_via_relation_stays_in_cone():
    t = Trace("q")
    d1, d2 = t.demand(ROOT, "D1", "one"), t.demand(ROOT, "D2", "two")
    unknowns(t, d1, "m")
    t.deliver(d2, "m")
    unknowns(t, d2, "F")
    t.input(d2, "a", "value", "acceleration", value=2)
    t.input(d2, "newton", "model", "F = m a", relation="F = m*a")
    t.input(d1, "rm", "model", "m is three", relation="m = 3")
    t.derive(d1, "m = 3", binds="m", from_relations=["rm"])
    redeliver = t.deliver(d2, "m")
    t.derive(d2, "F = 6", binds="F", from_relations=["newton"])
    t.answer(["F"])
    # v2.2: the cone holds m's value step, not the DELIVER that carried it
    assert redeliver.index not in t.cone() and t.value_step["m"] in t.cone()
    assert sorted(names_in(t.ledger(), "commitments")) == ["a", "newton", "rm"]


def test_derive_and_solve_uses_enter_the_cone():
    t = Trace("q")
    t.input(ROOT, "persist", "identity", "same objects throughout")
    t.input(ROOT, "regime", "recognition", "the string stays taut")
    t.input(ROOT, "paint", "recognition", "the blocks are red")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.input(ROOT, "ry", "model", "y is x", relation="y = x")
    t.solve(ROOT, ["rx"], ["x"], uses=["persist"])
    t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"], uses=["regime"])
    t.answer(["y"])
    led = t.ledger()
    assert sorted(names_in(led, "commitments")) == ["persist", "regime", "rx", "ry"]
    assert names_in(led, "not_in_answer") == ["paint"]


def test_unknown_cannot_be_introduced_by_input():
    t = Trace("q")
    with pytest.raises(TraceError, match="CONTRACT, ENTRY or READING"):
        t.unknown(ROOT, "x", "x", address="(x)", label="INPUT")
    with pytest.raises(TraceError, match="ref"):
        t.unknown(ROOT, "x", "x", address="(x)", label="CONTRACT")
    with pytest.raises(TraceError, match="quote"):
        t.unknown(ROOT, "x", "x", address="(x)", label="ENTRY", ref="E8")
    t.input(ROOT, "qn", "normalization", "the question asks for x")
    st = t.unknown(ROOT, "x", "x", address="(x)", label="READING", uses=["qn"], unit="m")
    assert st.op == "READING" and st.kind == "" and t.bindings["x"].unit == "m"
    with pytest.raises(TraceError, match="address"):  # whitespace does not make a new address
        t.unknown(ROOT, "x2", "x", address=" ( x ) ", label="READING")


def test_unknown_quote_only_with_label_entry():
    """V2R-9: v2 displayed an unverified quote under CONTRACT and READING."""
    t = Trace("q", entries={"E8": E8_TEXT})
    for label, ref in (("CONTRACT", "E8"), ("READING", "")):
        with pytest.raises(TraceError, match="only an unknown introduced by ENTRY"):
            t.unknown(ROOT, "x", "x", address="x", label=label, ref=ref, quote="divided by its")
    assert t.steps == []


def test_input_kinds_combine_with_a_slash():
    t = Trace("q")
    assert t.input(ROOT, "a", "recognition/model", "a").kind == "recognition/model"
    assert t.input(ROOT, "b", " value / model ", "b", value=3).kind == "value/model"
    assert t.input(ROOT, "c", "value//haze", "c", value=0).kind == "value/haze"
    assert t.input(ROOT, "H", "haze", "no haze", value=0).kind == "haze"
    with pytest.raises(TraceError, match="kind 'value'"):
        t.input(ROOT, "d", "recognition/model", "d", value=3)
    with pytest.raises(TraceError, match="kind"):
        t.input(ROOT, "e", "model/representation", "e")
    with pytest.raises(TraceError, match="kind"):
        t.input(ROOT, "f", "/", "f")


def test_conjured_relation_is_refused_in_strict_mode():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    with pytest.raises(CheckError):
        t.derive(ROOT, "x*y = 6", name="conj")
    with pytest.raises(TraceError, match="not a relation"):
        t.derive(ROOT, "x = 3", binds="x", from_relations=["conj"])


def test_failed_derive_binds_only_what_it_bound():
    """regress-10 (v2.1 friction, closed): a failed derive listed x in binds."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x is three", relation="x = 3")
    bad = t.derive(ROOT, "x = 4", binds="x", from_relations=["r"])
    assert bad.binds == () and "x" not in t.values and bad.detail.endswith("x not determined")
    named = t.derive(ROOT, "x = 5", binds="x", from_relations=["r"], name="r5")
    assert named.binds == ("r5",) and t.bindings["r5"].sort == "relation" and "x" not in t.values
    row = next(r for r in step_rows(t.to_markdown()) if r.startswith(f"| {bad.id}"))
    assert "⇒" not in row


def test_hypothesis_set_prunes_non_world_kinds_and_entailed_or_uses_statuses():
    t = Trace("q")
    t.input(ROOT, "ax", "convention", "y up")
    t.input(ROOT, "S", "choice", "system S = {A, B}")
    t.input(ROOT, "both", "convention/choice", "units and system")
    t.input(ROOT, "mix", "convention/model", "axis plus an ideal model")
    t.input(ROOT, "qn", "normalization", "read the question")
    t.input(ROOT, "ent", "identity", "an entailed identity")
    t.input(ROOT, "usesit", "recognition", "a USES premise")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x two", relation="x = 2", uses=["ax", "S", "both", "mix", "qn"])
    t.derive(ROOT, "x = 2", binds="x", from_relations=["r"], uses=["ent", "usesit"])
    t.answer(["x"])
    t.annotate("ent", "ENTAILED")
    t.annotate("usesit", "USES")
    led = t.ledger()
    assert names_in(led, "pruned") == ["ax", "S", "both", "ent", "usesit"]
    assert names_in(led, "commitments") == ["mix", "qn", "r"]
    members = " ".join(m["member"] for m in t.hypothesis_set())
    for gone in ("y up", "system S", "units and system", "entailed identity", "USES premise"):
        assert gone not in members
    assert "axis plus an ideal model" in members and "read the question" in members
    assert led["warnings"] == ["3 commitment(s) have no status yet: mix, qn, r"]


@pytest.mark.parametrize("status", ["NEEDS", "REQUIRED"])
def test_needs_or_required_on_a_non_world_input_is_warned(status):
    """probes-14: v2 pruned it silently."""
    t = Trace("q")
    t.input(ROOT, "ax", "convention", "y up")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x two", relation="x = 2", uses=["ax"])
    t.solve(ROOT, ["r"], ["x"])
    t.answer(["x"])
    t.annotate("ax", status, countermodel="flip the axis: x = -2")
    t.annotate("r", "REQUIRED")
    led = t.ledger()
    assert names_in(led, "pruned") == ["ax"] and led["pruned"][0]["status"] == status
    assert led["warnings"] == [f"ax is marked {status} but its kind convention is not a claim about the world, "
                               "so it is not a member"]


def test_gap_units_are_carried_not_checked():
    """Deliberately open (spec section 3): adding kg to m/s passes."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3, unit="kg")
    t.input(ROOT, "v", "value", "speed", value=2, unit="m/s")
    assert t.derive(ROOT, "m + v = 5").check == "checked"


# -- multiple answers and per-answer statuses -----------------------------------------------


def test_multiple_answers_have_their_own_cones_and_ledgers():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    a1 = t.answer(["x"], "first")
    later = t.derive(ROOT, "2*x = 6", tag="consequence")
    t.input(ROOT, "ry", "model", "y is x plus one", relation="y = x + 1")
    t.derive(ROOT, "y = 4", binds="y", from_relations=["ry"])
    a2 = t.answer(["y"], "second", label="second")
    assert t.answers == [("p1", a1.index), ("second", a2.index)]
    assert max(t.cone("p1")) == a1.index and later.index not in t.cone("p1")
    assert t.cone() == t.cone("second") and a1.index not in t.cone("second")
    l1, l2 = t.ledger("p1"), t.ledger()
    assert l1["label"] == "p1" and l1["answer"] == "x = 3" and l2["answer"] == "y = 4"
    assert names_in(l1, "commitments") == ["rx"] and names_in(l1, "not_in_answer") == ["ry"]
    assert later.id in [r["step"] for r in l1["outside_answer"]]
    assert sorted(names_in(l2, "commitments")) == ["rx", "ry"]
    assert t.hypothesis_set("p1")[0]["member"] == "the prediction holds: x = 3"
    rec = t.to_record()
    assert "ledger" not in rec and list(rec["ledgers"]) == ["p1", "second"]
    headings = [ln for ln in t.to_markdown().splitlines() if ln.startswith("## Ledger")]
    assert headings == ["## Ledger for answer p1", "## Ledger for answer second"]


def test_answer_labels_must_be_unique_known_and_well_formed():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    with pytest.raises(TraceError, match="no answer"):
        t.ledger()
    with pytest.raises(TraceError, match="at least one"):
        t.answer([])
    t.answer(["m"])
    with pytest.raises(TraceError, match="already used"):
        t.answer(["m"], label="p1")
    with pytest.raises(TraceError, match="no answer labelled"):
        t.ledger("nope")
    for bad in ("a b", "p1\n", "p1\n# injected", "a/b", "\u00e9", "a|b"):
        with pytest.raises(TraceError, match="answer labels use"):
            t.answer(["m"], label=bad)
    assert t.answer(["m"], label="Q3-internal.v2").tag == "Q3-internal.v2"
    unknowns(t, ROOT, "x")
    with pytest.raises(TraceError, match="no value"):
        t.answer(["x"])


def test_default_answer_label_is_the_first_free_p_n():
    """probes-4 / V2R-13: v2 computed p{len+1} and collided with a chosen label."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.answer(["m"], label="p2")
    assert [t.answer(["m"]).tag for _ in range(3)] == ["p1", "p3", "p4"]


def per_answer_trace():
    """atwood-1: c feeds both answers; k feeds only q2."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "c", "model", "c", relation="x = 2")
    t.solve(ROOT, ["c"], ["x"])
    t.answer(["x"], label="p")
    t.input(ROOT, "k", "model", "k", relation="y = 3*x")
    t.solve(ROOT, ["k"], ["y"])
    t.answer(["y"], label="q2")
    return t


def test_status_for_one_answer_does_not_prune_another():
    t = per_answer_trace()
    t.annotate("c", "USES", note="relative to p only", answer="p")
    assert names_in(t.ledger("p"), "pruned") == ["c"]
    led = t.ledger("q2")
    assert led["pruned"] == [] and names_in(led, "commitments") == ["c", "k"]
    assert led["commitments"][0]["status"] == ""
    assert led["warnings"] == ["2 commitment(s) have no status yet: c, k"]


def test_needs_for_one_answer_is_not_warned_in_another():
    """probes-10 / V2R-5: v2 warned 'marked NEEDS but does not feed this answer' in p."""
    t = per_answer_trace()
    t.annotate("k", "NEEDS", countermodel="y = 2*x gives 4", answer="q2")
    t.annotate("c", "REQUIRED")
    assert t.ledger("p")["warnings"] == []
    assert names_in(t.ledger("p"), "not_in_answer") == ["k"]
    # V21R-11 (v2.1 friction, closed): a default warns only if the premise feeds no answer
    t.annotate("k", "NEEDS", countermodel="y = 2*x gives 4")
    assert t.ledger("p")["warnings"] == []
    t.annotate("k", "REQUIRED", answer="p")  # a status given for p itself is warned in p
    assert t.ledger("p")["warnings"] == ["k is marked REQUIRED but does not feed this answer"]
    t.input(ROOT, "lonely", "recognition", "feeds no answer")
    t.annotate("lonely", "NEEDS", countermodel="a world without it")
    for label in ("p", "q2"):
        assert "lonely is marked NEEDS but does not feed this answer" in t.ledger(label)["warnings"]


def test_per_answer_status_overrides_the_default_and_replays():
    t = per_answer_trace()
    t.annotate("c", "NEEDS", countermodel="x = 5")
    t.annotate("c", "ENTAILED", answer="q2")
    assert t.ledger("p")["commitments"][0]["status"] == "NEEDS"
    assert names_in(t.ledger("q2"), "pruned") == ["c"] and t.ledger("q2")["pruned"][0]["status"] == "ENTAILED"
    assert t.commands[-1]["args"]["answer"] == "q2"
    again = roundtrip(t)
    assert again.annotations == t.annotations and again.to_record() == t.to_record()


def test_annotate_answer_must_name_an_existing_answer():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=1)
    with pytest.raises(TraceError, match="no answer labelled 'p1'"):
        t.annotate("m", "REQUIRED", answer="p1")
    t.annotate("m", "USES")  # a default given before any answer applies to later answers
    t.answer(["m"])
    with pytest.raises(TraceError, match="no answer labelled 'p2'"):
        t.annotate("m", "REQUIRED", answer="p2")
    assert names_in(t.ledger(), "pruned") == ["m"]


# -- withdrawal and value taint -----------------------------------------------------------------


def withdrawn_trace():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.answer(["x"], label="before")
    w = t.withdraw(ROOT, "rx", "conflicts with the trajectory input")
    return t, d, w


def test_withdrawn_premise_cannot_be_used_delivered_or_rebound():
    t, d, w = withdrawn_trace()
    assert w.op == "WITHDRAW" and w.ref == t.steps[t.bindings["rx"].step].id
    n = len(t.steps)
    with pytest.raises(TraceError, match="withdrawn"):
        t.derive(ROOT, "2*x = 6", from_relations=["rx"])
    with pytest.raises(TraceError, match="withdrawn"):
        t.reading(ROOT, "uses it", uses=["rx"])
    unknowns(t, ROOT, "z")
    with pytest.raises(TraceError, match="withdrawn"):
        t.solve(ROOT, ["rx"], ["z"])
    with pytest.raises(TraceError, match="withdrawn"):
        t.deliver(d, "rx")
    with pytest.raises(TraceError, match="already withdrawn"):
        t.withdraw(ROOT, "rx", "again")
    with pytest.raises(TraceError, match="already bound"):
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    assert len(t.steps) == n + 1  # only the unknown z
    assert t.visible(ROOT, "rx") is None


def test_tainted_value_is_visible_nowhere_but_the_name_stays_usable():
    """spring2-1 / V21-11 / probes-11 (v2.1 over-taint, closed): v2.2 taints by value.
    v2.1 refused every later mention of x, even in a revised relation."""
    t, d, w = withdrawn_trace()
    assert t.values["x"] == 3  # kept as history
    assert t.visible(ROOT, "x") is not None and t.value_visible(ROOT, "x") is None
    assert "x" not in t.known_values(ROOT) and t._hidden_values(ROOT, ["x"]) == []
    t.input(ROOT, "rx4", "model", "x four (revised account)", relation="x = 4")
    t.reading(ROOT, "x is the same quantity under the revised account", uses=["x"])
    st = t.deliver(d, "x")
    assert t.value_visible(d, "x") is None and st.text.startswith("x, delivered from ROOT")


def test_reusing_a_tainted_value_asks_for_it_to_be_determined_again():
    """v2.3: a step whose verdict would change if the withdrawn value were
    substituted is refused with a TraceError that names the withdrawn premise, in
    strict and lenient mode alike, and nothing is recorded (v2.2 read x as a free
    name: a CheckError 'not an identity' in strict mode, a found mistake in
    lenient mode). The ledger lists x under 'undetermined' with a note naming
    the premise its value rested on."""
    stale = re.escape("the step needs the value of x (rests on rx), which rests on a withdrawn premise; "
                      "determine it again first")
    t, d, w = withdrawn_trace()
    n = len(t.steps)
    with pytest.raises(TraceError, match=stale) as exc:
        t.derive(ROOT, "2*x = 6")
    assert type(exc.value) is TraceError and len(t.steps) == n  # not a CheckError, nothing recorded
    lt = Trace("q", strict=False)
    unknowns(lt, ROOT, "x")
    lt.input(ROOT, "rx", "model", "x three", relation="x = 3")
    lt.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    lt.withdraw(ROOT, "rx", "wrong")
    n = len(lt.steps)
    with pytest.raises(TraceError, match=stale) as exc:
        lt.derive(ROOT, "2*x = 6")
    assert type(exc.value) is TraceError and len(lt.steps) == n  # not a found mistake either
    lt.input(ROOT, "k", "value", "k", value=1)
    lt.answer(["k"])
    led = lt.ledger()
    assert led["mistakes"] == []
    assert led["undetermined"] == [{"name": "x", "address": "(x)", "step": lt.steps[lt.bindings["x"].step].id,
                                    "note": "its value was withdrawn: it rested on rx"}]


def test_answer_on_a_tainted_value_names_the_withdrawn_premise():
    """v2 accepted the answer and warned in its ledger; v2.1 and v2.2 refuse it."""
    t, d, w = withdrawn_trace()
    with pytest.raises(TraceError, match=re.escape("the value of 'x' rests on 'rx', which was withdrawn; "
                                                   "determine it again")):
        t.answer(["x"], label="after")
    assert [lb for lb, _ in t.answers] == ["before"]
    before = t.ledger("before")
    assert names_in(before, "withdrawn") == ["rx"] and before["withdrawn"][0]["withdrawn_at"] == w.id
    assert not any("withdrawn" in x for x in before["warnings"])
    assert names_in(before, "commitments") == ["rx"]


@pytest.mark.parametrize("route", ["derive", "solve"])
def test_a_quantity_with_a_tainted_value_can_be_determined_again(route):
    """probes-11 / V21-11 (v2.1 design gap, closed): x keeps its name and address
    and is determined again by a revised route."""
    t, d, w = withdrawn_trace()
    t.input(ROOT, "rx4", "model", "x four (revised account)", relation="x = 4")
    if route == "derive":
        fix = t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    else:
        fix = t.steps[t.solve(ROOT, ["rx4"], ["x"]).index + 1]
    assert fix.binds == ("x",) and t.values["x"] == 4 and t.value_step["x"] == fix.index
    assert t.value_visible(ROOT, "x") == fix.index and t.derive(ROOT, "2*x = 8").check == "checked"
    t.answer(["x"], label="after")
    led = t.ledger("after")
    assert led["answer"] == "x = 4" and names_in(led, "commitments") == ["rx4"]
    assert t.ledger("before")["answer"] == "x = 3"
    with pytest.raises(TraceError, match="already has a value"):
        t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    with pytest.raises(TraceError, match="already used by 'x'"):  # the address stays x's
        t.unknown(ROOT, "x_rev", "x under the revised account", address="(x)", ref="test")
    roundtrip(t)


def test_redetermined_value_must_be_delivered_again():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    old = t.deliver(d, "x")
    assert t.value_visible(d, "x") == old.index
    t.withdraw(ROOT, "rx", "wrong")
    assert t.value_visible(d, "x") is None
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    assert t.value_visible(d, "x") is None  # the old delivery carried the old value only
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d, "2*x = 8")
    new = t.deliver(d, "x")
    assert new.text.startswith("x = 4, delivered") and t.derive(d, "2*x = 8").check == "checked"


def test_withdrawal_taints_relations_registered_from_it_and_values_derived_from_it():
    """spring2-1 / regress-6, v2.2 form: a NAME whose binding step rests on the
    withdrawn premise is refused; a name whose VALUE rests on it stays usable."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "the spring is the only interaction")
    unknowns(t, ROOT, "F", "a", "z")
    t.input(ROOT, "m", "value", "mass", value=2)
    t.input(ROOT, "e8", "model", "E8", relation="F = m*a")  # registered before F has a value (order no longer matters in v2.3)
    t.input(ROOT, "fs", "model", "force sum over the spring only", relation="F = 2", uses=["c"])
    t.derive(ROOT, "F = 2", binds="F", from_relations=["fs"])
    t.derive(ROOT, "a = 1", binds="a", from_relations=["e8"])
    t.derive(ROOT, "2*a = 2", name="twice")  # an identity, but it rests on a's value
    t.input(ROOT, "rz", "model", "independent", relation="z = 5")
    t.derive(ROOT, "z = 5", binds="z", from_relations=["rz"])
    t.withdraw(ROOT, "c", "B's trajectory shows another interaction")
    n = len(t.steps)
    refused = [
        lambda: t.derive(ROOT, "F = 2", from_relations=["fs"]),  # registered with uses=['c']
        lambda: t.derive(ROOT, "z = 5", uses=["twice"]),  # registered by name= from a's value
        lambda: t.reading(ROOT, "the spring-only account", uses=["fs"]),
        lambda: t.deliver(t.demand(ROOT, "D", "d"), "twice"),
    ]
    for call in refused:
        with pytest.raises(TraceError, match="rests on 'c'"):
            call()
    with pytest.raises(TraceError, match="the value of 'a' rests on 'c'"):  # through two derives
        t.answer(["a"])
    assert len(t.steps) == n + 1  # only the DEMAND
    assert t.external(ROOT, "plot", "a plot of a", uses=["a"]).check == "unchecked"  # the name a is clean
    assert t.consistency(ROOT, ["e8"]).detail == "consistent"  # F and a are free again
    assert t.derive(ROOT, "z = 5").check == "checked"  # untouched by the withdrawal
    assert t.answer(["z"]).tag == "p1"


def test_withdrawal_taints_values_already_delivered():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.deliver(d, "x")
    assert t.derive(d, "2*x = 6").check == "checked"
    t.withdraw(ROOT, "rx", "wrong")
    assert t.value_visible(d, "x") is None and t.visible(d, "x") is not None
    n = len(t.steps)
    with pytest.raises(TraceError, match=re.escape("the step needs the value of x (rests on rx), which rests on a "
                                                   "withdrawn premise; determine it again first")) as exc:
        t.derive(d, "2*x = 6")  # v2.3: the value is withdrawn, not hidden, and the step says so
    assert type(exc.value) is TraceError and len(t.steps) == n
    d2 = t.demand(ROOT, "D2", "d2")
    st = t.deliver(d2, "x")  # v2.1 refused; v2.2 delivers the name without the value
    assert t.value_visible(d2, "x") is None and st.text.startswith("x, delivered")


def test_withdrawn_premise_cited_but_not_needed_does_not_taint():
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.input(ROOT, "junk", "model", "z seven", relation="z = 7")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx", "junk"])
    t.withdraw(ROOT, "junk", "irrelevant anyway")
    assert t.derive(ROOT, "2*x = 6").check == "checked"


def test_withdraw_refuses_non_inputs_hidden_names_and_missing_reasons():
    t = Trace("q")
    d1, d2 = t.demand(ROOT, "D1", "a"), t.demand(ROOT, "D2", "b")
    t.contract(ROOT, "C", "a connection", source="S", binds="cc")
    unknowns(t, ROOT, "x")
    t.input(d1, "k", "value", "k", value=1)
    with pytest.raises(TraceError, match="INPUT"):
        t.withdraw(ROOT, "cc", "no")
    with pytest.raises(TraceError, match="INPUT"):
        t.withdraw(ROOT, "x", "no")
    with pytest.raises(TraceError, match="reason"):
        t.withdraw(ROOT, "k", "  ")
    with pytest.raises(HiddenLookupError):
        t.withdraw(d2, "k", "no")


def test_a_premise_resting_on_a_withdrawn_one_can_itself_be_withdrawn():
    """V21-12 / V21R-13(4) (v2.1 bug, fixed)."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "complete")
    t.input(ROOT, "r", "model", "rests on c", relation="x = 1", uses=["c"])
    t.input(ROOT, "k", "value", "k", value=1)
    w1 = t.withdraw(ROOT, "c", "incomplete")
    w2 = t.withdraw(ROOT, "r", "the account built on c goes too")
    assert w2.op == "WITHDRAW" and w2.deps == (t.bindings["r"].step,) and t.bindings["r"].withdrawn == w2.index
    with pytest.raises(TraceError, match="was withdrawn at " + re.escape(w2.id)):  # now its own withdrawal
        t.reading(ROOT, "uses r", uses=["r"])
    t.answer(["k"])
    assert names_in(t.ledger(), "withdrawn") == ["c", "r"]
    assert [c["withdrawn_at"] for c in t.ledger()["withdrawn"]] == [w1.id, w2.id]
    roundtrip(t)


@pytest.mark.parametrize("order", ["registered before x's value", "registered after x's value"])
def test_relation_survives_the_withdrawal_of_the_premise_behind_a_value_it_mentions(order):
    """v2.2 bug, fixed in v2.3: a relation INPUT registered after a quantity's value
    was fixed recorded that value step as a dependency, so withdrawing the premise
    behind the value refused the relation itself, although the relation does not
    use the value. Registration now depends only on the binding steps of the
    names it mentions, so the order does not matter."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    if order == "registered before x's value":
        t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    if order == "registered after x's value":
        t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")
    t.withdraw(ROOT, "rx", "x was misread")
    t.input(ROOT, "rx4", "model", "x four (revised account)", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    st = t.derive(ROOT, "y = 8", binds="y", from_relations=["ry"])
    assert st.check == "checked" and t.values["y"] == 8
    t.answer(["y"])
    assert sorted(names_in(t.ledger(), "commitments")) == ["rx4", "ry"]


def test_e8_written_after_the_spring_only_force_survives_withdrawing_completeness():
    """The spring-two pattern in natural order: F from the spring-only force sum,
    then E8 as a model relation, then the completeness premise is withdrawn and F
    is determined again from a revised force sum. v2.2 bug, fixed in v2.3: E8
    could not be used again ('e8' rested on 'c' through F's value step)."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "the spring is the only interaction")
    t.input(ROOT, "m", "value", "mass of A", value=2)
    unknowns(t, ROOT, "F", "a")
    t.input(ROOT, "fs", "model", "force sum over the spring only", relation="F = 2", uses=["c"])
    t.derive(ROOT, "F = 2", binds="F", from_relations=["fs"])
    t.input(ROOT, "e8", "model", "E8 as a model relation", relation="F = m*a")
    t.derive(ROOT, "a = 1", binds="a", from_relations=["e8"])
    t.withdraw(ROOT, "c", "B's trajectory shows a second interaction")
    t.input(ROOT, "fs2", "model", "force sum over spring and contact", relation="F = 3")
    t.derive(ROOT, "F = 3", binds="F", from_relations=["fs2"])
    st = t.derive(ROOT, "a = 3/2", binds="a", from_relations=["e8"])  # v2.2: 'e8' rests on 'c'
    assert st.check == "checked"


def redetermined_after_answer():
    """p1 rests on r (x = 5) through uses=; x = 3 is fixed before p1 from rx, rx is
    withdrawn after p1, and x is then determined again as 5."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "r", "model", "x five", relation="x = 5")  # registered before x has a value
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    fix = t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "rz", "model", "z one, given r", relation="z = 1", uses=["r"])
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"])
    t.answer(["z"], label="p1")
    assert refs_in(t.ledger("p1"), "conflicts") == ["r"]
    t.withdraw(ROOT, "rx", "x = 3 was misread")
    assert refs_in(t.ledger("p1"), "conflicts") == ["r"]  # withdrawn after p1, so x = 3 still counts for p1
    t.input(ROOT, "rx5", "model", "x five, revised", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx5"])
    return t, fix


def test_determining_a_value_again_after_an_answer_keeps_that_answers_ledger():
    """v2.2 bug, fixed in v2.3: values kept only their latest value step, so
    determining x again after answer p1 dropped x = 3 (fixed before p1, withdrawn
    after it) from p1's global check and p1's conflict with r disappeared."""
    t, fix = redetermined_after_answer()
    assert refs_in(t.ledger("p1"), "conflicts") == ["r"]  # v2.2: []


def test_determining_a_value_again_keeps_the_original_step_rendering():
    """v2.2 bug, fixed in v2.3 (same root cause): once x was determined again, the
    step table no longer showed '=> x = 3' on the step that fixed x = 3."""
    t, fix = redetermined_after_answer()
    row = next(r for r in step_rows(t.to_markdown()) if r.startswith(f"| {fix.id} "))
    assert "⇒ x = 3" in row  # v2.2: '=> x' only


def test_gap_withdrawal_is_global_whatever_the_frame():
    """Deliberately open (branch-local premises): withdrawing in a diagnostic
    sub-frame removes the premise from the root and every other frame too."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "diagnostic branch")
    t.input(ROOT, "complete", "completeness", "the spring is the only interaction")
    t.deliver(d1, "complete")
    t.withdraw(d1, "complete", "withdrawn in the diagnostic branch only")
    with pytest.raises(TraceError, match="withdrawn"):
        t.reading(ROOT, "the spring-only account", uses=["complete"])


def test_resupplying_a_withdrawn_premise_is_flagged_as_such():
    """probes-5 / V2R-22: v2 advised 'deliver the original', which withdrawal forbids."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "the spring is the only interaction")
    w = t.withdraw(ROOT, "c", "the trajectory says otherwise")
    t.input(ROOT, "c2", "completeness", "the spring is the only interaction")
    unknowns(t, ROOT, "z")
    t.input(ROOT, "rz", "model", "z three", relation="z = 3", uses=["c2"])
    t.derive(ROOT, "z = 3", binds="z", from_relations=["rz"])
    t.answer(["z"])
    warnings = t.ledger()["warnings"]
    assert f"c2 repeats c word for word; c was withdrawn at {w.id}, and c2 was not withdrawn with it" in warnings
    assert not any("deliver the original" in x for x in warnings)
    assert names_in(t.ledger(), "commitments") == ["c2", "rz"]


def test_copy_made_before_the_withdrawal_is_flagged():
    """regress-5 / R26c / V21-13 (v2.1 bug, fixed): the copy came first, so v2.1
    still advised delivering the withdrawn original."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "only the spring")
    t.input(ROOT, "c2", "completeness", "only the spring")
    t.input(ROOT, "m", "value", "m", value=2)
    unknowns(t, ROOT, "a")
    t.input(ROOT, "r", "model", "r", relation="m*a = 2", uses=["c2"])
    w = t.withdraw(ROOT, "c", "conflict with the trajectory")
    t.derive(ROOT, "a = 1", from_relations=["r"], binds="a")
    t.answer(["a"])
    warnings = t.ledger()["warnings"]
    assert (f"c2 repeats c word for word; c has since been withdrawn at {w.id}, and c2 was not withdrawn with it"
            in warnings)
    assert not any("deliver the original" in x for x in warnings) and "c2" in names_in(t.ledger(), "commitments")


def test_duplicate_of_a_live_premise_still_advises_delivery():
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "the spring is the only interaction")
    t.input(ROOT, "c2", "completeness", "the  spring is the only interaction")
    t.input(ROOT, "k", "value", "k", value=1)
    t.answer(["k"])
    assert ("c2 repeats the INPUT c word for word; deliver the original instead of re-supplying it"
            in t.ledger()["warnings"])


def test_same_description_with_a_different_value_is_warned():
    """regress-1: g = 9.8 in D1 and g2 = 9.81 in D2 under one description."""
    t = Trace("q")
    t.demand(ROOT, "D1", "b1")
    t.demand(ROOT, "D2", "b2")
    t.input("D1", "g", "value", "local free-fall acceleration", value="9.8")
    t.input("D2", "g2", "value", "local free-fall acceleration", value="9.81")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="x = g + g2")
    t.derive(ROOT, "x = 1961/100", from_relations=["r"], binds="x")
    t.answer(["x"])
    assert "g2 has the same description as g but a different value" in t.ledger()["warnings"]


def test_same_description_warning_covers_value_inputs_only_whatever_the_kind():
    """probes-14 / regress-7 (v2.1 friction, closed): per-object relations sharing a
    description (the Atwood fixture's w1, w2) are no longer warned, and a value
    re-supplied under another value kind is."""
    led = finish(atwood()).ledger()
    assert not any("same description" in w for w in led["warnings"])
    t = Trace("q")
    t.input(ROOT, "g", "value", "local g", value="9.8")
    t.input(ROOT, "g2", "value/model", "local g", value="9.81")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="x = g + g2")
    t.derive(ROOT, "x = 1961/100", from_relations=["r"], binds="x")
    t.answer(["x"])
    assert "g2 has the same description as g but a different value" in t.ledger()["warnings"]


def test_gap_corrected_value_after_a_withdrawal_is_warned_without_mentioning_it():
    """Friction left open by v2.2 (V21R-8 / fresh-21(8)): m is withdrawn as misread
    and m2 supplies the corrected value; the warning reads as a suspicious
    duplicate and does not say that m was withdrawn."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass of A", value=2)
    t.withdraw(ROOT, "m", "misread")
    t.input(ROOT, "m2", "value", "mass of A", value=3)
    t.answer(["m2"])
    warnings = t.ledger()["warnings"]
    assert "m2 has the same description as m but a different value" in warnings
    assert not any("withdrawn" in w for w in warnings)


# -- dictionary entries ----------------------------------------------------------------


ENTRIES_MD = """# Entries

### [K16 / E1] uniform-motion

```text
uniform-motion :=
A frame-indexed interval property
of a point-particle.
```

### [E8] inertial-acceleration-material-object

```text
inertial-acceleration-material-object :=

For one material-object, its net-force-material-object divided by
its inertial-mass-material-object.
```
"""


@pytest.fixture
def entries(tmp_path):
    path = tmp_path / "entries.md"
    path.write_text(ENTRIES_MD, encoding="utf-8")
    return load_entries(str(path))


def test_load_entries_reads_the_design_layout(entries):
    assert sorted(entries) == ["E1", "E8", "K16"] and entries["K16"] == entries["E1"]
    assert entries["E8"] == E8_TEXT


def test_empty_entries_are_refused(tmp_path):
    """V2R-7: an empty mapping (e.g. load_entries on another file) silently turned checking off."""
    other = tmp_path / "CURRENT_STATE.md"
    other.write_text("# Current state\n\nNo entries here.\n", encoding="utf-8")
    for ents in ({}, load_entries(str(other))):
        with pytest.raises(TraceError, match="pass None"):
            Trace("q", entries=ents)
    t = Trace("q", entries=None)
    t.entry(ROOT, "E8", "anything at all")  # None: quote checking is off
    assert t.to_record()["entries"] == {} and roundtrip(t).entries == {}


def test_entry_quotes_are_verified(entries):
    t = Trace("q", entries=entries)
    t.entry(ROOT, "E8", E8.replace(" divided by ", " divided by\n   "))  # line breaks do not matter
    for ref, quote, msg in (("E8", "net force divided by mass", "not verbatim"),
                            ("E99", E8, "not in the supplied entries"),
                            ("E8", "material-object", "two whole words")):
        with pytest.raises(TraceError, match=msg):
            t.entry(ROOT, ref, quote)
    with pytest.raises(TraceError, match="not verbatim"):
        t.unknown(ROOT, "a", "acceleration", address="a(B)", label="ENTRY", ref="E8", quote="bogus quotation")
    with pytest.raises(TraceError, match="two whole words"):
        t.unknown(ROOT, "a", "acceleration", address="a(B)", label="ENTRY", ref="E8", quote="bogus")
    t.unknown(ROOT, "a", "acceleration", address="a(B)", label="ENTRY", ref="E8", quote=E8)
    assert ops(t) == ["ENTRY", "ENTRY"]
    rec = json.loads(json.dumps(t.to_record()))
    assert rec["entries"]["E8"].endswith(E8)
    roundtrip(t)
    rec["commands"][0]["args"]["quote"] = "net force divided by mass"
    rec["sha256"] = _digest({k: v for k, v in rec.items() if k != "sha256"})
    with pytest.raises(TraceError, match="not verbatim"):
        Trace.replay(rec)


@pytest.mark.parametrize("fragment, ok", [
    ("divided by", True), ("its net-force-material-object divided", True), ("For one material-object,", True),
    ("or one material-object", False),  # starts mid-word ('For')
    ("its net", False),  # ends inside a hyphenated word
    ("material-object divided", False),  # starts inside 'net-force-material-object'
    (".", False), ("inertial-mass-material-object.", False), ("divided", False),
])
def test_quote_check_needs_two_whole_words_at_word_boundaries(entries, fragment, ok):
    """probes-11 / V2R-8 / spring1-1: v2 accepted any substring."""
    t = Trace("q", entries=entries)
    if ok:
        assert t.entry(ROOT, "E8", fragment).op == "ENTRY"
    else:
        with pytest.raises(TraceError):
            t.entry(ROOT, "E8", fragment)


def test_combined_ref_is_accepted(entries):
    """V2R-18: 'K16 / E1' was refused."""
    t = Trace("q", entries=entries)
    assert t.entry(ROOT, "K16 / E1", "frame-indexed interval property").ref == "K16 / E1"
    st = t.unknown(ROOT, "u", "u", address="u", label="ENTRY", ref="K16 / E1", quote="interval property")
    assert st.ref == "K16 / E1"


@pytest.mark.parametrize("ref, msg", [("E8 / E99", r"not in the supplied entries \(E99\)"),
                                      ("K16 / E8", "not verbatim"), ("E99 / E8", r"\(E99\)")])
def test_combined_ref_needs_every_part_to_hold_the_quote(entries, ref, msg):
    """probes-8 / V21R-5 / V21-17 (v2.1 bug, fixed)."""
    t = Trace("q", entries=entries)
    with pytest.raises(TraceError, match=msg):
        t.entry(ROOT, ref, "divided by its")
    with pytest.raises(TraceError, match=msg):
        t.unknown(ROOT, "a", "a", address="a(B)", label="ENTRY", ref=ref, quote="divided by its")
    with pytest.raises(TraceError, match=msg):
        t.demand(ROOT, "D", "d", ref=ref, quote="divided by its")
    assert t.steps == [] and "D" not in t.frames


def test_quote_word_rule_ignores_punctuation_and_uses_unicode_boundaries():
    """probes-12 / regress-8 / V21R-9 (v2.1 gap, closed): ':=' no longer counts as a
    word, and 'u, with r0' no longer verifies inside 'r0 + \u03bbu, with r0 fixed'."""
    t = Trace("q", entries={"E8": E8_TEXT, "L": "a straight line r0 + \u03bbu, with r0 fixed, u nonzero"})
    for ref, quote, msg in (("E8", "inertial-acceleration-material-object :=", "two whole words"),
                            ("E8", ":= For", "two whole words"), ("L", "r0 +", "two whole words"),
                            ("L", "u, with r0", "not verbatim")):
        with pytest.raises(TraceError, match=msg):
            t.entry(ROOT, ref, quote)
    t.entry(ROOT, "L", "\u03bbu, with r0")
    t.entry(ROOT, "L", "r0 + \u03bbu")
    assert ops(t) == ["ENTRY"] * 2


def test_demand_quote_is_verified_and_linked_to_the_latest_entry(entries):
    t = Trace("q", entries=entries)
    with pytest.raises(TraceError, match="needs the entry ref"):
        t.demand(ROOT, "X", "x", quote="divided by its")
    with pytest.raises(TraceError, match="not verbatim"):
        t.demand(ROOT, "X", "x", ref="E8", quote="net force times mass")
    assert "X" not in t.frames and t.steps == []
    t.entry(ROOT, "E8", "divided by its")
    e2 = t.entry(ROOT, "E8", "For one material-object,")
    d = t.demand(ROOT, "D", "acceleration of B", ref="E8", quote="its net-force-material-object divided")
    st = t.steps[-1]
    assert st.deps == (e2.index,) and st.text.startswith("\u201cits net-force-material-object divided\u201d")
    t.demand(d, "DD", "deeper", ref="E8")  # no ENTRY in the parent frame D: nothing to link
    assert t.steps[-1].deps == ()
    roundtrip(t)


def test_gap_demand_link_does_not_reach_the_cone(entries):
    """Friction (spring1-3): the DEMAND step now depends on the ENTRY that exposed
    it, but no step depends on a DEMAND, so the entry still sits outside every
    answer. Without a quote, demand(ref=) is still not checked against the entries,
    and the link needs the ENTRY's ref string exactly ('K16' does not find 'K16 / E1')."""
    t = Trace("q", entries=entries)
    e = t.entry(ROOT, "E8", "divided by its")
    d = t.demand(ROOT, "D", "acceleration of B", ref="E8", quote="divided by its")
    t.input(d, "m", "value", "m", value=2)
    t.answer(["m"])
    assert e.index in t.steps[e.index + 1].deps and e.index not in t.cone()
    assert e.id in [r["step"] for r in t.ledger()["outside_answer"]]
    t.demand(ROOT, "X", "x", ref="E99")  # accepted although E99 is not an entry
    t.entry(ROOT, "K16 / E1", "frame-indexed interval property")
    t.demand(ROOT, "Y", "y", ref="K16")
    assert t.steps[-1].deps == ()


needs_design_file = pytest.mark.skipif(not ENTRIES_FILE.exists(),
                                       reason="Design 2.1 entries file not on this machine")


@needs_design_file
def test_fixture_e8_quote_is_verbatim_in_the_design_entries():
    ents = load_entries(str(ENTRIES_FILE))
    assert E8 in ents["E8"] and ents["K16"] == ents["E1"]
    t = Trace("q", entries=ents)
    t.entry(ROOT, "E8", E8)
    t.entry(ROOT, "K16 / E1", "A frame-indexed interval property of a point-particle")
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "E9", E8)


@needs_design_file
@pytest.mark.parametrize("ref, quote, verdict", [
    # v2.1 accepted these three (probes-12, regress-8, V21R-9)
    ("E7", "inertial-acceleration-material-object :=", "two whole words"),
    ("E8", "inertial-acceleration-material-object :=", "two whole words"),
    ("K8", ":= For", "two whole words"),
    ("K4", "u, with r0", "not verbatim"),  # inside 'r0 + λu, with r0 fixed'
    ("K4", "λu, with r0 fixed", "ok"),
    ("K4", "r0 + λu", "ok"),
    ("K4", "+ λu", "two whole words"),
    ("K1", "t ∈ R;", "ok"),
    ("K1", "∈ R", "two whole words"),
    # combined refs: every part must be an entry and hold the quote (probes-8)
    ("E8 / E9", "For one material-object, its", "ok"),  # the opening both definitions share
    ("E8 / E9", "divided by its", "not verbatim"),
    ("E9 / E8", "times its inertial-acceleration-material-object", "not verbatim"),
    ("E8 / E99", "divided by its", r"not in the supplied entries \(E99\)"),
    ("K16 / E1", "constant speed with unchanged direction", "ok"),
    # whole words (V2R-8)
    ("E4", "without being a free", "not verbatim"),
    ("E4", "being a free-particle.", "ok"),
    ("E8", "material-object := For", "not verbatim"),
    ("E9", "For one material-object, its net-force-material-object", "not verbatim"),
])
def test_design_file_quotes(ref, quote, verdict):
    t = Trace("q", entries=load_entries(str(ENTRIES_FILE)))
    if verdict == "ok":
        assert t.entry(ROOT, ref, quote).ref == ref
    else:
        with pytest.raises(TraceError, match=verdict):
            t.entry(ROOT, ref, quote)


@needs_design_file
def test_gap_the_headword_line_plus_one_word_still_verifies_under_two_entries():
    """Note: E7 and E8 share the headword 'inertial-acceleration-material-object'
    and both definitions open with 'For', so the headword line plus 'For' is a
    valid two-word quote under 'E7 / E8', a combined ref of two different
    entries, though it quotes neither definition."""
    t = Trace("q", entries=load_entries(str(ENTRIES_FILE)))
    assert t.entry(ROOT, "E7 / E8", "inertial-acceleration-material-object := For").ref == "E7 / E8"


# -- validation -------------------------------------------------------------------------------


def test_names_with_a_trailing_newline_are_refused():
    """V2R-11: '$' matched before a final newline."""
    t = Trace("q")
    with pytest.raises(TraceError, match="identifiers"):
        t.input(ROOT, "m\n", "value", "m", value=1)
    with pytest.raises(TraceError, match="identifiers"):
        t.unknown(ROOT, "x\n", "x", address="(x)", ref="test")
    assert t.steps == []


def test_relations_need_an_equals_sign_when_registered():
    """V2R-12: 'x + 1' was accepted and failed only when cited."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    for call in (lambda: t.input(ROOT, "r", "model", "r", relation="x + 1"),
                 lambda: t.contract(ROOT, "C", "c", source="S", binds="r", relation="x + 1"),
                 lambda: t.reading(ROOT, "r", binds="r", relation="x + 1"),
                 lambda: t.external(ROOT, "diff", "d", relation="x + 1", binds="r"),
                 lambda: t.input(ROOT, "r", "model", "r", relation="x = 1 = 2")):
        with pytest.raises(TraceError, match="exactly one '='"):
            call()
    assert "r" not in t.bindings


def test_value_kind_needs_a_value():
    """V2R-23: kind 'value' without value= became a fact."""
    t = Trace("q")
    with pytest.raises(TraceError, match="must supply value="):
        t.input(ROOT, "m", "value", "inertial mass of A")
    assert "m" not in t.bindings


def test_gap_compound_value_kind_without_a_value_is_a_fact():
    """Note: the value= rule covers kind 'value' alone; 'value/model' without a
    number still binds a fact, and kind 'value' may bind a relation."""
    t = Trace("q")
    assert t.input(ROOT, "m", "value/model", "inertial mass of A").op == "INPUT"
    assert t.bindings["m"].sort == "fact"
    unknowns(t, ROOT, "m2")
    t.input(ROOT, "rv", "value", "a number, given as a relation", relation="m2 = 3")
    assert t.bindings["rv"].sort == "relation"


# -- replay and digest ---------------------------------------------------------------------


def test_lenient_failed_steps_and_late_annotations_replay():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x is three", relation="x = 3")
    t.derive(ROOT, "x = 4", from_relations=["r"], tag="slip")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["r"])
    t.answer(["x"])
    t.annotate("r", "NEEDS", countermodel="x = 5 world")
    t.annotate("r", "REQUIRED")
    rec = t.to_record()
    again = roundtrip(t)
    assert again.to_record()["sha256"] == rec["sha256"] == t.to_record()["sha256"]
    assert again.ledger()["commitments"][0]["status"] == "REQUIRED"
    t.annotate("r", "USES")
    assert t.to_record()["sha256"] != rec["sha256"]


def test_tampered_command_with_recomputed_digest_is_caught():
    t = finish(atwood())
    rec = json.loads(json.dumps(t.to_record()))
    for c in rec["commands"]:
        if c["op"] == "input" and c["args"].get("name") == "m1":
            c["args"]["value"] = "4"
    rec["sha256"] = _digest({k: v for k, v in rec.items() if k != "sha256"})
    with pytest.raises(TraceError):
        Trace.replay(rec)


def test_float_fraction_and_string_values_replay_identically():
    t = Trace("q")
    for i, v in enumerate([0.1, 1e-7, Fraction(-1, 3), "1/3", 10**30, -0.0, "1e-400", "0.30000000000000001",
                           "10**-3", 1e300]):
        t.input(ROOT, f"v{i}", "value", "v", value=v)
    again = roundtrip(t)
    assert again.values == t.values and t.values["v0"] == Fraction(1, 10)
    assert t.values["v6"] == Fraction(1, 10**400) and t.values["v7"] == Fraction("0.30000000000000001")


def replays(build, strict=True):
    t = Trace("q", strict=strict)
    build(t)
    again = roundtrip(t)
    assert again.to_record() == t.to_record()
    return t


def test_replay_solve_without_relations():
    t = replays(lambda t: (unknowns(t, ROOT, "x"), t.solve(ROOT, [], ["x"])))
    assert "free: x" in t.steps[-1].detail


def test_replay_consistency_checks_in_strict_mode():
    def build(t):
        t.input(ROOT, "a", "value", "a", value=3)
        t.input(ROOT, "r", "model", "r", relation="a = 3")
        t.input(ROOT, "s", "model", "s", relation="a = 4")
        t.consistency(ROOT, ["r"])
        t.consistency(ROOT, ["r", "s"], text="", tag="")
    t = replays(build)
    assert [s.check for s in t.steps[-2:]] == ["checked", "failed"]


def test_replay_solve_with_empty_text():
    def build(t):
        unknowns(t, ROOT, "x")
        t.input(ROOT, "r", "model", "r", relation="x = 3")
        t.solve(ROOT, ["r"], ["x"], text="")
    t = replays(build)
    assert t.steps[-2].op == "EXTERNAL" and t.steps[-2].text == ""
    assert t.steps[-1].op == "DERIVE" and t.steps[-1].text == f"value fixed by the linear solve {t.steps[-2].id}"


def test_contract_with_empty_ref_is_refused():
    t = Trace("q")
    with pytest.raises(TraceError, match="ref"):
        t.contract(ROOT, "", "a connection", source="S8.1")
    assert t.steps == [] and t.commands == []


def build_every_command(t):
    """Every v2.2 command, with empty strings and empty lists where allowed, plus the
    v2.2 paths: a premise resting on a withdrawn one is withdrawn too, a tainted
    value is determined again by solve(), and deliver_through crosses two levels."""
    t.entry(ROOT, "E8", E8)
    d = t.demand(ROOT, "D1", "acceleration of B", ref="E8", quote="divided by its")
    t.entry(d, "E8", E8, text="")
    t.input(d, "m", "value/model", "inertial mass", value=Fraction(3), unit="kg")
    t.input(ROOT, "H", "haze", "no unkeyed influence", value=0)
    t.input(ROOT, "ax", "convention", "axis up")
    t.input(ROOT, "persist", "identity", "same block throughout")
    t.input(ROOT, "stale", "recognition", "a premise withdrawn later")
    t.deliver_many(d, ["H", "ax", "persist"], text="")
    t.unknown(d, "a", "acceleration", address="a(B, t0)", label="ENTRY", ref="E8", quote=E8, unit="m/s^2")
    t.unknown(d, "F", "net force", address="F(B, t0)", ref="C-FS", unit="N")
    t.unknown(d, "s", "spare", address="s(B)", label="READING", uses=[])
    t.input(d, "rF", "model", "the net force", relation="F = 6 + H", uses=[])
    t.solve(d, ["rF"], ["F"], tag="", text="", uses=["ax"])
    t.contract(d, "C-E8", "E8 as a relation", source="S", binds="e8", relation="F = m*a", uses=[])
    t.reading(d, "B is a material-object", uses=["persist"], binds="", relation="")
    t.derive(d, "a = 2", binds="a", from_relations=["e8", "rF"], uses=["persist"], tag="")
    t.consistency(d, ["e8", "rF"], text="", tag="", uses=[])
    t.external(ROOT, "differentiation", "a check", uses=[], relation="", binds="", tag="")
    t.input(ROOT, "rs", "model", "s from the stale premise", relation="s = 1", uses=["stale"])
    t.derive(ROOT, "s = 1", binds="s", from_relations=["rs"])
    t.answer(["a"], "", label="")
    t.withdraw(ROOT, "stale", "no longer believed")
    t.withdraw(ROOT, "rs", "built on the stale premise")
    t.input(ROOT, "rs2", "model", "s, revised", relation="s = 2")
    t.solve(ROOT, ["rs2"], ["s"])
    sub = t.demand(d, "D1a", "a consequence", ref="")
    t.deliver_many(sub, ["a", "m"])
    t.derive(sub, "m*a = 6", tag="consequence", uses=[])
    t.input(ROOT, "late", "recognition", "a late premise")
    deep = t.demand(sub, "D1b", "a deeper consequence")
    t.deliver_through(deep, "late")  # one DELIVER, into D1
    t.open(ROOT, "the observation side", uses=[])
    t.annotate("m", "REQUIRED", countermodel="", note="")
    t.annotate("persist", "USES", answer="p1")
    t.answer(["a", "F", "s"], label="again")
    t.annotate("ax", "NEEDS", countermodel="flip the axis", answer="again")


def test_every_v22_command_replays():
    t = Trace("q", {"name": "Design 2.1 Draft 1"}, entries={"E8": E8_TEXT})
    build_every_command(t)
    ops_recorded = {c["op"] for c in t.commands}
    assert ops_recorded == {"demand", "entry", "input", "deliver", "unknown", "solve", "contract", "reading",
                            "derive", "consistency", "external", "answer", "withdraw", "open", "annotate"}
    assert t.steps[0].ref == "E8" and t.steps[1].deps == (0,)
    assert t.ledger("p1")["answer"] == "a = 2 m/s^2"
    p1, again = t.ledger("p1"), t.ledger("again")
    assert ("persist", "USES") in [(c["name"], c["status"]) for c in p1["pruned"]]
    assert "persist" in names_in(again, "commitments")
    assert ("ax", "NEEDS") in [(c["name"], c["status"]) for c in again["pruned"]]
    assert ("ax is marked NEEDS but its kind convention is not a claim about the world, so it is not a member"
            in again["warnings"])
    assert names_in(p1, "withdrawn") == ["stale", "rs"] and not any("withdrawn" in w for w in again["warnings"])
    assert again["answer"] == "a = 2 m/s^2, F = 6 N, s = 2" and "rs2" in names_in(again, "commitments")
    assert [s.frame for s in t.steps if s.op == "DELIVER" and s.uses == ("late",)] == ["D1"]
    rec = json.loads(json.dumps(t.to_record()))
    again_t = Trace.replay(rec)
    assert again_t.to_record() == rec and again_t.answers == t.answers and again_t.values == t.values


def test_lenient_record_with_failed_unchecked_and_conflict_steps_replays():
    def build(t):
        unknowns(t, ROOT, "x", "y")
        t.input(ROOT, "r", "model", "x three", relation="x = 3")
        t.input(ROOT, "s", "model", "x four", relation="x = 4")
        t.derive(ROOT, "x*y = 6", name="conj")
        t.derive(ROOT, "x = 3", from_relations=["r", "s"], binds="x")
        t.derive(ROOT, "2*x = 7", from_relations=["r"])
        t.solve(ROOT, ["r", "s"], ["x"])
        t.consistency(ROOT, ["r", "s"])
        t.solve(ROOT, ["r"], ["x"])
        t.answer(["x"])
    t = replays(build, strict=False)
    assert [s.check for s in t.steps if s.op in ("DERIVE", "EXTERNAL")] == [
        "unchecked", "failed", "failed", "failed", "failed", "checked", "checked"]  # last: the solve's DERIVE
    led = t.ledger()
    assert len(led["mistakes"]) == 1 and len(led["conflicts"]) == 3 and len(led["unchecked"]) == 1


# -- markdown ------------------------------------------------------------------------------------


def step_rows(md):
    """The rows of the steps table only (ledger tables also start with '| [')."""
    lines = md.splitlines()
    out = []
    for ln in lines[lines.index("## Steps") + 1:]:
        if ln.startswith("## "):
            break
        if ln.startswith("| ["):
            out.append(ln)
    return out


def cells(row):
    return len(row.replace("\\|", "")[1:-1].split("|"))


def test_markdown_escapes_pipes_and_newlines_in_content():
    t = Trace("q")
    t.input(ROOT, "m", "value", "a|b\nc", value=3)
    rows = step_rows(t.to_markdown())
    assert len(rows) == 1 and "a\\|b c" in rows[0]


def test_markdown_escapes_frame_ids():
    t = Trace("q")
    d = t.demand(ROOT, "D|1", "first")
    t.input(d, "m", "value", "mass", value=3)
    rows = step_rows(t.to_markdown())
    assert len(rows) == 2 and all(cells(r) == 7 for r in rows)


def test_markdown_handles_crlf():
    t = Trace("q\r\nsecond line", {"name": "ed\rone"})
    t.input(ROOT, "m", "value", "mass\r\nsecond line", value=3)
    t.answer(["m"], "boxed\ranswer")
    md = t.to_markdown()
    rows = step_rows(md)
    assert len(rows) == 2 and all(cells(r) == 7 for r in rows)
    assert "**Question.** q second line" in md and "**Edition.** name: ed one" in md


def test_markdown_renders_every_answer_ledger_with_full_rows():
    t = Trace("q", entries={"E8": E8_TEXT})
    build_every_command(t)
    md = t.to_markdown()
    rows = step_rows(md)
    assert len(rows) == len(t.steps) and all(cells(r) == 7 for r in rows)
    for heading in ("### Pruned premises (feed the answer, not members)", "### Withdrawn premises",
                    "### Found mistakes", "### Conflicts", "### Solves that were not unique",
                    "### Hypothesis set for again (prediction side only)"):
        assert heading in md


def test_answer_labels_cannot_inject_markdown_headings():
    """probes-3 / V2R-14: labels are now validated, so a newline cannot reach a heading."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    with pytest.raises(TraceError, match="answer labels use"):
        t.answer(["m"], label="p1\n# injected")
    t.answer(["m"], label="p1")
    assert not any(ln.startswith("# injected") for ln in t.to_markdown().splitlines())
