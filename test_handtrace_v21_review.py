"""Adversarial review of handtrace.py, updated to v2.2 (fresh reviewer), then to v2.3.

Passing tests document behaviour v2.2 gets right, gaps it leaves open on
purpose (test_gap_*) and notes (test_note_*). The v2.2 bugs pinned here
(V22-1 .. V22-4) and the V22-6 gap are fixed in v2.3, so their tests are
ordinary passing tests; the V22-5 and V22-8 notes and the tests of syntax
refused at entry and of stale values assert the v2.3 behaviour.

The v2.1 findings (V21-1 .. V21-17) keep their tests where the test still
applies. Those v2.2 fixed are ordinary passing tests now. Those whose
semantics v2.2 changed on purpose (withdrawal taints by value, solve records
one DERIVE per fixed value, deliveries are not provenance, the threshold of
the minimal-citation search) assert the new behaviour.

Deliberately open, documented and not failing: conditional branches, units,
the observation side, the C3 budget, editions, explicit RETURN, and a
minimum-size citation search beyond 8 citations.

Areas: the global conflict check in ledger(), minimal citation and per-value
solve provenance, unevaluable and nonlinear claims, hidden lookups, value
taint and re-determination, deliver_through / deliver_many, per-answer
annotations and replay, quotes against the Design 2.1 entries, and the cost
of a ~300-step synthetic trace.
"""

import functools
import itertools
import json
import random
import time
from fractions import Fraction
from pathlib import Path

import pytest

import handtrace
from handtrace import (
    ROOT,
    CheckError,
    HiddenLookupError,
    Trace,
    TraceError,
    entails,
    frac,
    mentioned_names,
    parse_equation,
)


def unknowns(t, frame, *names):
    for n in names:
        t.unknown(frame, n, n, address=f"({n})", ref="t")


def closure(t, index):
    seen, stack = set(), [index]
    while stack:
        i = stack.pop()
        if i not in seen:
            seen.add(i)
            stack.extend(t.steps[i].deps)
    return seen


def commitments(t, answer=None):
    return sorted(c["name"] for c in t.ledger(answer)["commitments"])


def conflict_refs(t, answer=None):
    return [c["ref"] for c in t.ledger(answer)["conflicts"]]


E8 = ("inertial-acceleration-material-object := For one material-object, its net-force-material-object "
      "divided by its inertial-mass-material-object.")

ENTRIES_FILE = Path(r"C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/07_design_2_1/"
                    r"DESIGN_2_1_DRAFT_1_ENTRIES.md")
needs_entries = pytest.mark.skipif(not ENTRIES_FILE.exists(), reason="the Design 2.1 entries file is not present")


@functools.lru_cache(maxsize=None)
def _entries():
    return handtrace.load_entries(str(ENTRIES_FILE))


# =============================================================================
# A. The global conflict check in ledger()
# =============================================================================


def _route_trace():
    """D1 derives y = 8 from r: x = 7 and r2: y = x + 1 while x has no value anywhere; ROOT then fixes x = 5."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")
    t.input(d1, "r", "model", "x seven", relation="x = 7")
    t.input(d1, "r2", "model", "y is x plus one", relation="y = x + 1")
    assert t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y").check == "checked"
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.answer(["x", "y"])
    return t


def test_global_check_reports_a_contradiction_made_before_the_value_was_fixed():
    """V2R-1 case 1, in the one order v2.2 still lets through: the global check reports r at the answer."""
    led = _route_trace().ledger()
    assert "r" in [c["ref"] for c in led["conflicts"]]
    assert any("rests on r, which the trace's own values contradict" in w for w in led["warnings"])


def test_hidden_value_that_would_expose_a_conflict_is_a_hidden_lookup():
    """V2R-1 case 1 in its original order (x = 5 fixed at ROOT before D1 cites x = 7) is now refused at the
    step, because substituting the hidden x would turn 'checked' into a conflict. After delivery the same
    step is a conflict."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(d1, "r", "model", "x seven", relation="x = 7")
    t.input(d1, "r2", "model", "y is x plus one", relation="y = x + 1")
    n = len(t.steps)
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y")
    assert len(t.steps) == n
    t.deliver(d1, "x")
    with pytest.raises(CheckError, match="conflict"):
        t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y")


def test_note_global_check_blames_every_relation_on_the_route():
    """r2 (y = x + 1) is innocent: y = 8 came from it with the bad x = 7. The per-relation check cannot
    localise, so r2 is reported too."""
    assert sorted(conflict_refs(_route_trace())) == ["r", "r2"]


def test_global_check_reports_a_relation_reached_only_through_uses():
    """V2R-1 case 2 stays caught."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "bad", "model", "m is three", relation="m = 3")
    t.input(ROOT, "r", "model", "x is m", relation="x = m")
    t.derive(ROOT, "x = 2", from_relations=["r"], binds="x", uses=["bad"])
    t.answer(["x"])
    assert conflict_refs(t) == ["bad"]


def test_global_check_ignores_contradicted_relations_outside_the_cone():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "bad", "model", "m is three", relation="m = 3")
    t.input(ROOT, "r", "model", "x is m", relation="x = m")
    t.derive(ROOT, "x = 2", from_relations=["r"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert led["conflicts"] == []
    assert "bad" in [c["name"] for c in led["not_in_answer"]]


def test_unchecked_named_derive_is_warned_and_caught_by_the_global_check():
    """The v2 laundering repro (R21b): x = 1000 from x*y = 6 and y = 1."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "product", relation="x*y = 6")
    b = t.derive(ROOT, "x = 1000*y", from_relations=["r"], name="r2")
    t.input(ROOT, "r3", "model", "y", relation="y = 1")
    t.solve(ROOT, ["r2", "r3"], ["x", "y"])
    t.answer(["x"])
    led = t.ledger()
    assert b.check == "unchecked"
    assert any(b.id in w and "could not be checked" in w for w in led["warnings"])
    assert "r" in [c["ref"] for c in led["conflicts"]]


UNEVALUABLE = {
    "non-integer power": ("v = (2*g*h)**0.5", {"g": 10, "h": 5}),
    "modulo": ("n % 2 = 1", {"n": 7}),
    "division by a value that is zero": ("y = 6/c", {"c": 0}),
}


def _unevaluable_setup(case):
    """The values and unknowns of UNEVALUABLE[case], before rel is registered."""
    relation, values = UNEVALUABLE[case]
    t = Trace("q")
    for n, v in values.items():
        t.input(ROOT, n, "value", n, value=v)
    unknowns(t, ROOT, "z")
    for n in ("v", "y"):
        if relation.startswith(f"{n} = "):  # not mentioned_names(): v2.3 refuses n % 2 there too
            unknowns(t, ROOT, n)
    return t, relation


def _unevaluable_in_cone(case):
    t, relation = _unevaluable_setup(case)
    t.input(ROOT, "rel", "model", "a model relation", relation=relation)
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["rel"])
    t.answer(["z"])
    return t


@pytest.mark.parametrize("case", sorted(UNEVALUABLE))
def test_ledger_survives_a_relation_it_cannot_evaluate(case):
    """V21-1 is fixed: ledger(), to_markdown(), to_record() and replay no longer raise. v2.3: modulo is outside
    the checker's syntax, so n % 2 = 1 is refused at entry and nothing is recorded."""
    if case == "modulo":
        t, relation = _unevaluable_setup(case)
        steps, commands = len(t.steps), len(t.commands)
        with pytest.raises(TraceError, match=r"^outside the checker's syntax \(Mod\) in 'n % 2'; "):
            t.input(ROOT, "rel", "model", "a model relation", relation=relation)
        assert (len(t.steps), len(t.commands)) == (steps, commands)
        assert "rel" not in t.bindings
        return
    t = _unevaluable_in_cone(case)
    t.ledger()
    t.to_markdown()
    again = Trace.replay(json.loads(json.dumps(t.to_record())))
    assert again.to_record()["sha256"] == t.to_record()["sha256"]


def test_division_by_a_zero_value_in_the_cone_is_a_conflict_row():
    led = _unevaluable_in_cone("division by a value that is zero").ledger()
    [row] = led["conflicts"]
    assert row["ref"] == "rel" and "division by zero" in row["detail"]
    assert "the answer rests on rel, which the trace's own values make undefined" in led["warnings"]


def test_division_by_zero_after_substitution_is_a_mistake_or_a_conflict():
    """_verdict() no longer crashes: a claim that divides by a zero value is a found mistake, a cited
    relation that does is a conflict, and consistency() records a conflict."""
    t = Trace("q", strict=False)
    t.input(ROOT, "c", "value", "c", value=0)
    unknowns(t, ROOT, "y", "z")
    st = t.derive(ROOT, "y = 6/c")
    assert st.check == "failed" and st.detail.startswith("mistake") and "division by zero" in st.detail
    t.input(ROOT, "rel", "model", "rel", relation="y = 6/c")
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    st = t.derive(ROOT, "z = 1", from_relations=["rz", "rel"])
    assert st.check == "failed" and st.detail.startswith("conflict: relation rel cannot be evaluated")
    assert t.consistency(ROOT, ["rel"]).check == "failed"
    with pytest.raises(CheckError, match="division by zero"):
        Trace("q").derive(ROOT, "1/0 = 1")


UNSUPPORTED = ("claim with a non-integer power", "claim with modulo", "superfluous cited relation",
               "consistency of a true relation")


def _unsupported_step(case):
    """The step for a TRUE statement written in syntax v2.2's checker did not support (v2.2 recorded it as a
    found mistake or a conflict)."""
    t = Trace("q", strict=False)
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "h", "value", "h", value=5)
    t.input(ROOT, "n", "value", "n", value=7)
    unknowns(t, ROOT, "v", "z")
    if case == "claim with a non-integer power":
        return t.derive(ROOT, "(2*g*h)**0.5 = 10")
    if case == "claim with modulo":
        return t.derive(ROOT, "n % 2 = 1")
    if case == "superfluous cited relation":
        t.input(ROOT, "rz", "model", "z", relation="z = 1")
        t.input(ROOT, "rel", "model", "free fall", relation="v = (2*g*h)**0.5")
        return t.derive(ROOT, "z = 1", from_relations=["rz", "rel"])
    t.input(ROOT, "rel", "model", "n is odd", relation="n % 2 = 1")
    return t.consistency(ROOT, ["rel"])


@pytest.mark.parametrize("case", UNSUPPORTED)
def test_unsupported_syntax_is_not_a_found_mistake_or_a_conflict(case):
    """V22-1 is fixed in v2.3: v2.2 classed syntax its checker lacked (a non-integer power, %) like a division by
    zero, so TRUE claims became found mistakes and n % 2 = 1 (n = 7) a conflict. v2.3 evaluates fractional powers
    exactly and refuses % at entry."""
    try:
        st = _unsupported_step(case)
    except TraceError:
        return  # refusing the syntax outright, as v2.1 did, is an acceptable fix
    assert st.check != "failed", st.detail


def test_global_check_does_not_call_unsupported_syntax_a_conflict():
    """V22-1 is fixed in v2.3: v2.2's global check filed v = (2*g*h)**0.5 (g = 10, h = 5) as a conflict the
    trace's own values make undefined; v2.3 evaluates it exactly (v = 10)."""
    try:
        t = _unevaluable_in_cone("non-integer power")
    except TraceError:
        return  # refusing the syntax at registration is an acceptable fix
    led = t.ledger()
    assert not any(r["ref"] == "rel" for r in led["conflicts"])
    assert not any("make undefined" in w for w in led["warnings"])


def test_found_mistake_in_the_cone_is_not_also_a_premise_conflict():
    """V21-2 is fixed: the global check skips relations bound by a failed step."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "y")
    t.input(ROOT, "x", "value", "x", value=3)
    bad = t.derive(ROOT, "2*x = 7", name="bad")
    assert bad.check == "failed" and bad.detail.startswith("mistake")
    t.input(ROOT, "ry", "model", "y", relation="y = 1")
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"], uses=["bad"])
    t.answer(["y"])
    led = t.ledger()
    assert [r["step"] for r in led["mistakes"]] == [bad.id]
    assert led["conflicts"] == []


def _tainted_value_trace(withdraw_before_answer):
    """x = 7 is derived in D from r: x + z = 10 and r2: x - z = 4 (which imply z = 3) while z has no value;
    z = 1 is then fixed at ROOT from rz, which rests on completeness c."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    d = t.demand(ROOT, "D", "d")
    t.deliver(d, "z")
    t.deliver(d, "x")
    t.input(d, "r", "model", "sum", relation="x + z = 10")
    t.input(d, "r2", "model", "difference", relation="x - z = 4")
    t.derive(d, "x = 7", binds="x", from_relations=["r", "r2"])
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1", uses=["c"])
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"])
    if withdraw_before_answer:
        t.withdraw(ROOT, "c", "the trajectory shows another force")
    t.answer(["x"], label="p")  # accepted either way: x does not rest on c
    if not withdraw_before_answer:
        t.withdraw(ROOT, "c", "the trajectory shows another force")
    return t


def test_global_check_does_not_use_values_resting_on_withdrawn_premises():
    """V21-3 is fixed: z = 1 rests on c, withdrawn before the answer, so it is no evidence against r, r2."""
    assert _tainted_value_trace(withdraw_before_answer=True).ledger("p")["conflicts"] == []


def test_global_check_keeps_values_whose_premise_was_withdrawn_after_the_answer():
    assert sorted(conflict_refs(_tainted_value_trace(withdraw_before_answer=False), "p")) == ["r", "r2"]


def test_later_values_do_not_change_an_earlier_answers_global_check():
    """v2.1 gap closed: only values fixed before the answer count. A later answer resting on r sees z."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "r", "model", "sum", relation="x + z = 10")
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"], uses=["r"])
    t.answer(["x"], label="p")
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"])
    assert t.ledger("p")["conflicts"] == []
    t.answer(["x"], label="p2")
    assert conflict_refs(t, "p2") == ["r"]


def test_withdrawing_a_relation_after_the_answer_keeps_its_conflict():
    """v2.1 gap closed: p rested on r while r was live, so withdrawing r afterwards keeps the conflict."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "r", "model", "sum", relation="x + z = 10")
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"])
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"], uses=["r"])
    t.answer(["x"], label="p")
    assert conflict_refs(t, "p") == ["r"]
    t.withdraw(ROOT, "r", "contradicted by z")
    led = t.ledger("p")
    assert [c["ref"] for c in led["conflicts"]] == ["r"]
    assert "r" in [c["name"] for c in led["commitments"]]


def _answer_then_withdraw_the_value():
    """p rests on bad: x = 5 (registered before x had a value) while x = 3 rests on c; c is withdrawn after p."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "bad", "model", "x is five", relation="x = 5")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y one", relation="y = 1")
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"], uses=["bad"])
    t.answer(["y"], label="p")
    assert conflict_refs(t, "p") == ["bad"]
    t.withdraw(ROOT, "c", "another force acts")
    return t


def test_a_withdrawal_after_the_answer_keeps_the_value_it_was_made_with():
    assert conflict_refs(_answer_then_withdraw_the_value(), "p") == ["bad"]


def test_redetermining_a_value_does_not_rewrite_an_earlier_answers_global_check():
    """V22-3 is fixed in v2.3: re-determining x after p no longer drops p's conflict on bad: x = 5, because the
    global check reads each name's value history as of the answer."""
    t = _answer_then_withdraw_the_value()
    t.input(ROOT, "rx7", "model", "x seven, revised", relation="x = 7")
    t.derive(ROOT, "x = 7", binds="x", from_relations=["rx7"])
    assert conflict_refs(t, "p") == ["bad"]


def test_gap_cited_but_not_needed_relation_escapes_the_global_check():
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    t.input(ROOT, "rb", "model", "x plus z", relation="x + z = 10")
    st = t.derive(ROOT, "x = 3", from_relations=["rx", "rb"], binds="x")
    assert "cited but not needed: rb" in st.detail
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    t.derive(ROOT, "z = 1", from_relations=["rz"], binds="z")
    t.answer(["x"])
    assert t.ledger()["conflicts"] == []  # rb (3 + 1 = 10) was cited by the answer's step


def test_jointly_inconsistent_relations_in_the_cone_are_reported():
    """v2.1 gap closed: x = u + 1 and x = u + 2 never reduce to constants, but together they are inconsistent."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "u", "z")
    t.input(ROOT, "r1", "model", "r1", relation="x = u + 1")
    t.input(ROOT, "r2", "model", "r2", relation="x = u + 2")
    t.input(ROOT, "rz", "model", "rz", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["r1", "r2"])
    t.answer(["z"])
    led = t.ledger()
    assert conflict_refs(t) == ["r1, r2"]
    assert "jointly inconsistent" in led["conflicts"][0]["detail"]
    assert "the answer rests on relations that are jointly inconsistent: r1, r2" in led["warnings"]


def test_joint_conflict_names_a_minimal_inconsistent_subset_and_runs_beside_a_flagged_relation():
    """V22-8, changed in v2.3: the joint row names a minimal inconsistent subset (r1, r2), not every relation
    still holding unknowns (the innocent r3: w = v + 1 is left out); and the joint test always runs, excluding
    relations flagged individually, so the r1/r2 inconsistency is reported beside 'bad'."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "u", "w", "v", "z")
    t.input(ROOT, "r1", "model", "r1", relation="x = u + 1")
    t.input(ROOT, "r2", "model", "r2", relation="x = u + 2")
    t.input(ROOT, "r3", "model", "r3, innocent", relation="w = v + 1")
    t.input(ROOT, "rz", "model", "rz", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["r1", "r2", "r3"])
    t.answer(["z"], label="p")
    assert conflict_refs(t, "p") == ["r1, r2"]
    t.input(ROOT, "bad", "model", "z two", relation="z = 2")
    t.derive(ROOT, "z = 1", from_relations=["rz"], uses=["r1", "r2", "bad"], name="z_again")
    unknowns(t, ROOT, "s")
    t.input(ROOT, "rs", "model", "s", relation="s = 1")
    t.derive(ROOT, "s = 1", binds="s", from_relations=["rs"], uses=["z_again"])
    t.answer(["s"], label="q")
    assert conflict_refs(t, "q") == ["bad", "r1, r2"]
    warnings = t.ledger("q")["warnings"]
    assert "the answer rests on bad, which the trace's own values contradict" in warnings
    assert "the answer rests on relations that are jointly inconsistent: r1, r2" in warnings


# =============================================================================
# B. Minimal citations and solve provenance
# =============================================================================


def test_exhaustive_search_finds_the_smallest_subset_and_prefers_the_first_cited():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "rxy", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "ry", "model", "y", relation="y = 2")
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    t.input(ROOT, "rx2", "model", "2x", relation="2*x = 6")
    st = t.derive(ROOT, "x = 3", from_relations=["rxy", "ry", "rx2", "rx"], binds="x")
    assert st.detail == "follows from rx2 (cited but not needed: rxy, ry, rx)"


def test_solve_drops_an_identically_zero_relation_and_reports_it():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="2*x = 6")
    t.input(ROOT, "paint", "recognition", "the blocks are red")
    t.input(ROOT, "k", "value", "k", value=4)
    t.input(ROOT, "kr", "model", "irrelevant", relation="k = 4", uses=["paint"])
    st = t.solve(ROOT, ["r", "kr"], ["x"])
    assert "relations not needed for the fixed values: kr" in st.detail
    t.answer(["x"])
    assert commitments(t) == ["r"]


def _random_case(rng):
    """Consistent random relations over unknowns u0..u3 whose coefficients may be value names."""
    t = Trace("q")
    sol = {f"u{i}": rng.randint(-3, 3) for i in range(4)}
    unknowns(t, ROOT, *sol)
    vals = {f"v{j}": rng.choice([-2, -1, 1, 2, 3]) for j in range(3)}
    for n, v in vals.items():
        t.input(ROOT, n, "value", n, value=v)
    rels, rows = [], []
    for k in range(rng.randint(2, 6)):
        terms = rng.sample(sorted(sol), rng.randint(1, 3))
        coeff, text = {}, []
        for u in terms:
            if rng.random() < 0.5:
                v = rng.choice(sorted(vals))
                coeff[u] = vals[v]
                text.append(f"{v}*{u}")
            else:
                c = rng.choice([-2, -1, 1, 2, 3])
                coeff[u] = c
                text.append(f"{c}*{u}")
        rhs = sum(c * sol[u] for u, c in coeff.items())
        t.input(ROOT, f"r{k}", "model", f"r{k}", relation=" + ".join(text) + f" = {rhs}")
        rels.append(f"r{k}")
        rows.append((coeff, rhs))
    pick = rng.sample(range(len(rels)), rng.randint(1, len(rels)))
    total, const = {}, 0
    for i in pick:
        m = rng.choice([-2, -1, 1, 2])
        for u, c in rows[i][0].items():
            total[u] = total.get(u, 0) + m * c
        const += m * rows[i][1]
    terms = [f"{c}*{u}" for u, c in sorted(total.items()) if c]
    if not terms:
        return None
    order = rels[:]
    rng.shuffle(order)
    return t, " + ".join(terms) + f" = {const}", order


def _smallest(forms, claim):
    if claim.is_zero():
        return 0
    return next(s for s in range(1, len(forms) + 1)
                if any(entails([forms[i] for i in c], claim) for c in itertools.combinations(range(len(forms)), s)))


def test_provenance_always_justifies_a_checked_derive():
    """End to end: the relations and values in the derive step's dependency closure entail its claim,
    and the number of relations kept equals a brute-force minimum. 300 random consistent systems."""
    rng = random.Random(2111)
    done = 0
    while done < 300:
        case = _random_case(rng)
        if case is None:
            continue
        t, claim, order = case
        st = t.derive(ROOT, claim, from_relations=order)
        assert st.check == "checked", (claim, st.detail)
        cl = closure(t, st.index)
        vals = {n: v for n, v in t.values.items() if t.value_step[n] in cl}
        kept = [b.equation for b in t.bindings.values() if b.sort == "relation" and b.step in cl]
        form = parse_equation(claim, vals)[0]
        assert form.is_zero() or entails([parse_equation(e, vals)[0] for e in kept], form)
        allv = dict(t.values)
        forms = [parse_equation(t.bindings[r].equation, allv)[0] for r in order]
        assert len(kept) == _smallest(forms, parse_equation(claim, allv)[0])
        done += 1


def test_per_value_solve_provenance_is_a_smallest_fixing_set():
    """v2.2: every value a solve fixes gets its own checked DERIVE 'u = value'. Its dependency closure holds a
    set of the cited relations that entails the value and is as small as a brute-force search finds, and it
    never reaches the EXTERNAL report. 150 random consistent systems."""
    rng = random.Random(2202)
    done = 0
    while done < 150:
        case = _random_case(rng)
        if case is None:
            continue
        t, _, order = case
        vals = dict(t.values)
        forms = [parse_equation(t.bindings[r].equation, vals)[0] for r in order]
        rep = t.solve(ROOT, order, [f"u{i}" for i in range(4)])
        assert rep.op == "EXTERNAL" and rep.check == "checked"
        for k in rep.binds:
            st = t.steps[t.value_step[k]]
            assert (st.op, st.check, st.binds) == ("DERIVE", "checked", (k,))
            assert st.claim == f"{k} = {frac(t.values[k])}"
            cl = closure(t, st.index)
            assert rep.index not in cl
            kept = [b.name for b in t.bindings.values() if b.sort == "relation" and b.step in cl]
            claim = parse_equation(st.claim)[0]
            assert entails([forms[order.index(r)] for r in kept], claim)
            assert len(kept) == _smallest(forms, claim)
        done += 1


def _citation_trace(extra):
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "B", "recognition", "premise B")
    t.input(ROOT, "r0", "model", "sum", relation="x + y = 5", uses=["A"])
    t.input(ROOT, "r1", "model", "y two", relation="y = 2", uses=["A"])
    dummies = []
    for i in range(extra):
        unknowns(t, ROOT, f"z{i}")
        t.input(ROOT, f"d{i}", "model", f"dummy {i}", relation=f"z{i} = {i}")
        dummies.append(f"d{i}")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["B"])
    st = t.derive(ROOT, "x = 3", from_relations=["r0", "r1"] + dummies + ["rx"], binds="x")
    t.answer(["x"])
    return t, st


def test_with_eight_citations_or_fewer_the_direct_premise_is_kept():
    t, st = _citation_trace(5)  # 8 citations
    assert st.detail.startswith("follows from rx ")
    assert commitments(t) == ["B", "rx"]


def test_gap_beyond_eight_citations_the_kept_set_may_not_be_smallest():
    """V21-4, now a declared open gap (exhaustive up to 8, greedy beyond): a ninth, irrelevant citation flips
    the provenance from {rx} to {r0, r1} and changes the hypothesis set. The detail does not say so."""
    t, st = _citation_trace(6)  # 9 citations
    assert st.detail.startswith("follows from r0, r1 ")
    assert "greedy" not in st.detail
    assert commitments(t) == ["A", "r0", "r1"]


def _two_premise_solve():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "B", "recognition", "premise B")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "y four", relation="y = 4", uses=["B"])
    rep = t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    return t, rep


def test_solve_provenance_is_per_value():
    """V21-5 is fixed: the solve records an EXTERNAL report, then one checked DERIVE per fixed value, and an
    answer naming x rests only on x's relation and premise."""
    t, rep = _two_premise_solve()
    assert rep.op == "EXTERNAL" and rep.detail == "unique: x = 3, y = 4"
    dx, dy = (t.steps[t.value_step[n]] for n in ("x", "y"))
    assert (dx.op, dx.claim, dx.binds, dx.check, dx.detail) == ("DERIVE", "x = 3", ("x",), "checked",
                                                                 "follows from r1")
    assert dy.claim == "y = 4" and dy.index == dx.index + 1 == rep.index + 2
    t.answer(["x"])
    assert commitments(t) == ["A", "r1"]


def test_withdrawing_a_premise_only_y_needs_leaves_x_usable():
    t, _ = _two_premise_solve()
    t.withdraw(ROOT, "B", "B was misread")
    t.answer(["x"], label="px")
    assert t.derive(ROOT, "2*x = 6").check == "checked"
    with pytest.raises(TraceError, match="rests on 'B'"):
        t.answer(["y"])


def test_the_solve_report_is_not_listed_outside_an_answer_its_values_feed():
    """V22-5, changed in v2.3: the answer's value rests on the per-value DERIVE, which does not depend on the
    EXTERNAL report, so the report is not in the cone; but since one of its per-value DERIVE steps is, the
    report is no longer filed under 'Other steps that do not feed the answer' either. Only y's DERIVE is."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "r1", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "r2", relation="x - y = 1")
    rep = t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    assert rep.binds == ("x", "y")
    t.answer(["x"])
    led = t.ledger()
    assert [s["step"] for s in led["step_members"]] == [t.steps[t.value_step["x"]].id]
    assert [r["step"] for r in led["outside_answer"]] == [t.steps[t.value_step["y"]].id]
    assert rep.index not in t.cone()


def test_note_a_joint_answer_takes_the_union_of_per_value_minima():
    """x is fixed by r3 alone, y needs {r1, r2}. Answering x rests on r3 only; answering both rests on all
    three, although {r1, r2} would fix both."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "r1", relation="x + y = 3")
    t.input(ROOT, "r2", "model", "r2", relation="x - y = 1")
    t.input(ROOT, "r3", "model", "r3", relation="2*x = 4")
    st = t.solve(ROOT, ["r1", "r2", "r3"], ["x", "y"])
    assert "not needed" not in st.detail
    t.answer(["x"], label="px")
    assert commitments(t, "px") == ["r3"]
    t.answer(["x", "y"], label="pxy")
    assert commitments(t, "pxy") == ["r1", "r2", "r3"]


def _dense_solve(k, seed=1):
    rng = random.Random(seed)
    t = Trace("q")
    names = [f"u{i}" for i in range(k)]
    unknowns(t, ROOT, *names)
    rels = []
    for i in range(k):
        lhs = " + ".join(f"{rng.randint(1, 9)}*{n}" for n in names)
        t.input(ROOT, f"s{i}", "model", f"s{i}", relation=f"{lhs} = {rng.randint(1, 50)}")
        rels.append(f"s{i}")
    return t, rels, names


def _count_entails(monkeypatch):
    calls = []
    real = handtrace.entails

    def counting(rels, claim):
        calls.append(1)
        return real(rels, claim)

    monkeypatch.setattr(handtrace, "entails", counting)
    return calls


def test_dense_ten_by_ten_solve_no_longer_takes_seconds(monkeypatch):
    """V21-6 is fixed for 10 relations: beyond 8 the search is greedy, k checks per value (12.6 s in v2.1,
    about 0.3 s now)."""
    calls = _count_entails(monkeypatch)
    t, rels, names = _dense_solve(10)
    t0 = time.perf_counter()
    st = t.solve(ROOT, rels, names)
    assert st.detail.startswith("unique")
    assert len(calls) <= 10 * 10
    assert time.perf_counter() - t0 < 5.0


def test_note_eight_dense_relations_are_the_worst_case(monkeypatch):
    """V22-9: the exhaustive search still runs once per fixed value, so a dense 8x8 solve costs
    8 * (2**8 - 1) = 2040 entailment checks (about 1.1 s), against 81 for 9x9 (about 0.2 s)."""
    calls = _count_entails(monkeypatch)
    t, rels, names = _dense_solve(8)
    t.solve(ROOT, rels, names)
    assert len(calls) == 8 * (2 ** 8 - 1)


def test_superfluous_nonlinear_citation_no_longer_blocks_a_check():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "product", relation="y*z = 1")
    st = t.derive(ROOT, "x = 3", from_relations=["r1", "r2"], binds="x")
    assert st.check == "checked"
    assert st.detail == "follows from r1 (nonlinear citations not checked: r2)"
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "y = 1", from_relations=["r2"])


def test_gap_a_superfluous_nonlinear_citation_that_contradicts_is_noted_not_checked():
    """V21-7, now disclosed rather than fixed: x = 0 with a superfluous x*y = 6 (0 = 6 once x = 0) is
    'checked' with the note 'nonlinear citations not checked: rn'; rn stays outside the cone, so no conflict
    is reported. consistency() on rn alone does find it."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "rx", "model", "x zero", relation="x = 0")
    t.input(ROOT, "rn", "model", "product", relation="x*y = 6")
    st = t.derive(ROOT, "x = 0", from_relations=["rx", "rn"], binds="x")
    assert st.check == "checked" and "nonlinear citations not checked: rn" in st.detail
    t.answer(["x"])
    assert t.ledger()["conflicts"] == []
    assert t.consistency(ROOT, ["rn"]).check == "failed"


def test_note_consistency_and_solve_still_refuse_a_superfluous_nonlinear_relation():
    """derive() tolerates it; consistency() and solve() still raise TraceError."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "product", relation="y*z = 1")
    with pytest.raises(TraceError, match="nonlinear"):
        t.consistency(ROOT, ["r1", "r2"])
    with pytest.raises(TraceError, match="nonlinear"):
        t.solve(ROOT, ["r1", "r2"], ["x"])


# =============================================================================
# C. Hidden lookups
# =============================================================================


def _hidden_y_frame(strict=False):
    t = Trace("q", strict=strict)
    unknowns(t, ROOT, "x", "y", "w")
    d1 = t.demand(ROOT, "D1", "one")
    for n in ("x", "y", "w"):
        t.deliver(d1, n)
    t.input(ROOT, "ry", "model", "y five", relation="y = 5")
    t.derive(ROOT, "y = 5", from_relations=["ry"], binds="y")
    return t, d1


def test_hidden_value_in_solve_and_in_a_bound_right_side_is_a_hidden_lookup():
    t, d1 = _hidden_y_frame(strict=True)
    unknowns(t, d1, "v")
    t.input(d1, "r", "model", "v from y", relation="v = y + 1")
    with pytest.raises(HiddenLookupError, match="y"):
        t.solve(d1, ["r"], ["v"])
    with pytest.raises(HiddenLookupError, match="y"):
        t.derive(d1, "v = y + 1", from_relations=["r"], binds="v")


def test_slip_with_an_unrelated_hidden_value_in_a_cited_relation_is_a_mistake():
    """V21-8 (V2R-19's own repro) is fixed: the hidden y = 5 agrees with r2, so it cannot change the verdict."""
    t, d1 = _hidden_y_frame()
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "y five again", relation="y = 5")
    st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("mistake")


def test_unchecked_step_with_an_unrelated_hidden_value_is_recorded():
    """V21-9 is fixed: y = 5 cannot make x*w = 6 linear."""
    t, d1 = _hidden_y_frame()
    t.input(d1, "rn", "model", "product", relation="x*w = 6")
    t.input(d1, "r2", "model", "y five again", relation="y = 5")
    st = t.derive(d1, "x = 3", from_relations=["rn", "r2"])
    assert st.check == "unchecked"


def test_hidden_value_that_would_turn_a_check_into_a_conflict_is_a_hidden_lookup():
    t, d1 = _hidden_y_frame()
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "y six", relation="y = 6")
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d1, "x = 3", from_relations=["r", "r2"])


def test_with_the_value_delivered_the_slip_beside_a_contradicted_relation_is_a_conflict():
    """Companion of V22-2: once y = 5 is delivered, citing r2: y = 6 makes x = 4 a conflict, not a mistake."""
    t, d1 = _hidden_y_frame()
    t.deliver(d1, "y")
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "y six", relation="y = 6")
    st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("conflict")


def test_hidden_value_that_turns_a_mistake_into_a_conflict_is_a_hidden_lookup():
    """V22-2 is fixed in v2.3: the hidden-value check compares the verdict category, not only the check word,
    so a hidden y = 5 that would turn the slip x = 4 (cited beside r2: y = 6) from a found mistake into a
    conflict is no longer filed as a mistake."""
    t, d1 = _hidden_y_frame()
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "y six", relation="y = 6")
    try:
        st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    except HiddenLookupError:
        return
    assert st.detail.startswith("conflict"), st.detail


def test_consistency_with_a_hidden_value_is_a_hidden_lookup():
    """V21-10 is fixed: a hidden value that would change the result raises; one that would not is ignored,
    and a conflict found without the hidden value is recorded."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    d = t.demand(ROOT, "D", "d")
    t.deliver(d, "x")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx"])
    t.input(d, "r", "model", "x seven", relation="x = 7")
    with pytest.raises(HiddenLookupError, match="would change the result"):
        t.consistency(d, ["r"])
    t.input(d, "r5", "model", "x five again", relation="x = 5")
    assert t.consistency(d, ["r5"]).detail == "consistent"
    t.input(d, "r8", "model", "x eight", relation="x = 8")
    assert t.consistency(d, ["r", "r8"]).check == "failed"


def test_consistency_records_a_deliberate_conflict_in_strict_mode():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "x four", relation="x = 4")
    st = t.consistency(ROOT, ["r1", "r2"])
    assert st.check == "failed" and st.kind == "consistency"
    with pytest.raises(TraceError, match="unknowns"):
        t.solve(ROOT, ["r1"], [])
    t.input(ROOT, "m", "value", "m", value=1)
    t.external(ROOT, "linear solve", "solved by hand elsewhere")
    t.answer(["m"])
    led = t.ledger()
    assert [r["step"] for r in led["conflicts"]] == [st.id]
    assert led["solve_reports"] == []


# =============================================================================
# D. Withdrawal taint and re-determination
# =============================================================================


def _withdrawn_x():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.answer(["x"], label="before")
    w = t.withdraw(ROOT, "c", "the trajectory shows another force")
    return t, w


def test_withdrawal_taints_the_value_not_the_name():
    """v2.2 semantics: x's value 3 (resting on c through rx) is visible nowhere and answer() names c; the name
    x stays usable and is delivered without a value; rx, whose binding rests on c, is refused. v2.3: a derive
    whose verdict the withdrawn value would change is refused with a TraceError (not a CheckError, nothing
    recorded) asking for x to be determined again, and the ledger lists x as undetermined with that note."""
    t, w = _withdrawn_x()
    d = t.demand(ROOT, "D", "d")
    assert t.known_values(ROOT) == {}
    with pytest.raises(TraceError, match="rests on 'c'"):
        t.answer(["x"])
    with pytest.raises(TraceError, match="rests on 'c'"):
        t.reading(ROOT, "r", uses=["rx"])
    steps = len(t.steps)
    with pytest.raises(TraceError, match=r"^the step needs the value of x \(rests on c\), which rests on a "
                                         r"withdrawn premise; determine it again first$") as exc:
        t.derive(ROOT, "2*x = 6")  # the old value is not substituted, and the step is not filed as a slip
    assert not isinstance(exc.value, CheckError) and len(t.steps) == steps
    st = t.deliver(d, "x")
    assert "x = 3" not in st.text and st.deps == (t.bindings["x"].step,)
    t.reading(ROOT, "x is the spring's extension", uses=["x"])
    unknowns(t, ROOT, "y")
    t.input(ROOT, "ry", "model", "y two", relation="y = 2")
    t.derive(ROOT, "y = 2", binds="y", from_relations=["ry"])
    t.deliver(d, "y")
    t.answer(["y"], label="after")
    assert t.ledger("after")["warnings"] == ["1 commitment(s) have no status yet: ry"]
    x_decl = t.steps[t.bindings["x"].step].id
    assert t.ledger("after")["undetermined"] == [{"name": "x", "address": "(x)", "step": x_decl,
                                                  "note": "its value was withdrawn: it rested on c"}]
    assert t.ledger("before")["withdrawn"][0]["withdrawn_at"] == w.id


def test_a_quantity_whose_value_is_tainted_can_be_determined_again():
    """V21-11 is fixed: x takes a revised relation and a new value; the earlier answer keeps its own."""
    t, _ = _withdrawn_x()
    t.input(ROOT, "rx2", "model", "revised account of x", relation="x = 4")
    st = t.derive(ROOT, "x = 4", binds="x", from_relations=["rx2"])
    assert (t.value_step["x"], t.values["x"]) == (st.index, 4)
    t.answer(["x"], label="revised")
    assert t.ledger("revised")["answer"] == "x = 4"
    assert t.ledger("before")["answer"] == "x = 3"
    assert commitments(t, "revised") == ["rx2"]


def test_a_tainted_value_can_be_determined_again_by_solve():
    t, _ = _withdrawn_x()
    t.input(ROOT, "rx2", "model", "revised account of x", relation="2*x = 8")
    assert t.solve(ROOT, ["rx2"], ["x"]).detail == "unique: x = 4"
    t.answer(["x"], label="revised")
    assert commitments(t, "revised") == ["rx2"]


def test_a_premise_resting_on_a_withdrawn_one_can_itself_be_withdrawn():
    """V21-12 is fixed."""
    t, _ = _withdrawn_x()
    w = t.withdraw(ROOT, "rx", "the spring-only account is dropped as well")
    assert t.bindings["rx"].withdrawn == w.index
    with pytest.raises(TraceError, match="which was withdrawn"):
        t.answer(["x"])


def test_a_tainted_declaration_frees_its_address():
    """V22-6, fixed in v2.3: a name whose own declaration rests on a withdrawn premise is refused, and address
    uniqueness ignores it, so the corrected account can declare the quantity again at the same address."""
    t = Trace("q")
    t.input(ROOT, "c", "recognition", "the string is the only thing pulling the block")
    t.unknown(ROOT, "T", "tension", address="T(string, B1)", label="READING", uses=["c"])
    t.withdraw(ROOT, "c", "a second string also pulls the block")
    with pytest.raises(TraceError, match="rests on 'c'"):
        t.reading(ROOT, "uses T", uses=["T"])
    t.input(ROOT, "c2", "recognition", "two strings pull the block")
    st = t.unknown(ROOT, "T_rev", "tension, re-declared", address="T(string, B1)", label="READING", uses=["c2"])
    assert st.binds == ("T_rev",) and t.bindings["T_rev"].address == "T(string, B1)"
    assert t.reading(ROOT, "uses T_rev", uses=["T_rev"]).deps == (st.index,)


def test_friction_a_superfluous_tainted_citation_blocks_the_step():
    """Unlike a superfluous nonlinear citation, a superfluous tainted one refuses the whole step."""
    t, _ = _withdrawn_x()
    unknowns(t, ROOT, "y")
    t.input(ROOT, "ry", "model", "y two", relation="y = 2")
    with pytest.raises(TraceError, match="withdrawn"):
        t.derive(ROOT, "y = 2", binds="y", from_relations=["ry", "rx"])


def test_resupplying_a_withdrawn_fact_is_warned_as_such():
    t = Trace("q")
    unknowns(t, ROOT, "y")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    w = t.withdraw(ROOT, "c", "trajectory")
    t.input(ROOT, "c2", "completeness", "only the spring acts")
    t.input(ROOT, "ry", "model", "y", relation="y = 2", uses=["c2"])
    t.derive(ROOT, "y = 2", binds="y", from_relations=["ry"])
    t.answer(["y"])
    assert (f"c2 repeats c word for word; c was withdrawn at {w.id}, and c2 was not withdrawn with it"
            in t.ledger()["warnings"])


def test_duplicate_supplied_before_the_withdrawal_is_flagged():
    """V21-13 is fixed: the warning says the original has since been withdrawn, and no longer advises
    delivering it."""
    t = Trace("q")
    unknowns(t, ROOT, "y")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "c2", "completeness", "only the spring acts")
    w = t.withdraw(ROOT, "c", "trajectory shows another force")
    t.input(ROOT, "ry", "model", "y", relation="y = 2", uses=["c2"])
    t.derive(ROOT, "y = 2", binds="y", from_relations=["ry"])
    t.answer(["y"])
    warnings = t.ledger()["warnings"]
    assert (f"c2 repeats c word for word; c has since been withdrawn at {w.id}, and c2 was not withdrawn with it"
            in warnings)
    assert not any("deliver the original" in x for x in warnings)


def test_note_corrected_value_after_withdrawal_is_warned_without_mentioning_it():
    t = Trace("q")
    t.input(ROOT, "g", "value", "local g", value="9.8")
    t.withdraw(ROOT, "g", "wrong site")
    t.input(ROOT, "g2", "value", "local g", value="9.81")
    t.answer(["g2"])
    w = t.ledger()["warnings"]
    assert "g2 has the same description as g but a different value" in w
    assert not any("withdrawn" in x for x in w)


def test_same_description_warning_applies_to_value_inputs_only():
    """v2.1 friction closed: per-object relations that share a description are not warned."""
    t = Trace("q")
    t.input(ROOT, "g", "value", "local g", value="9.8")
    unknowns(t, ROOT, "f1", "f2")
    t.input(ROOT, "w1", "model", "uniform-field weight", relation="f1 = -2*g")
    t.input(ROOT, "w2", "model", "uniform-field weight", relation="f2 = -3*g")
    t.derive(ROOT, "f1 = -98/5", binds="f1", from_relations=["w1"])
    t.derive(ROOT, "f2 = -147/5", binds="f2", from_relations=["w2"])
    t.answer(["f1", "f2"])
    assert not any("same description" in w for w in t.ledger()["warnings"])


def _x_value_then_law(register_law_first):
    """s: y = x + 1 is a law that never uses x's value. x = 3 rests on c; c is withdrawn and x re-determined."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    if register_law_first:
        t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    if not register_law_first:
        t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")  # x = 3 is visible here
    t.withdraw(ROOT, "c", "another force acts")
    t.input(ROOT, "rx5", "model", "x five, revised", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx5"])
    return t


def test_a_law_registered_before_the_value_survives_the_withdrawal():
    t = _x_value_then_law(register_law_first=True)
    assert t.derive(ROOT, "y = 6", binds="y", from_relations=["s"]).check == "checked"


def test_a_law_registered_while_the_value_was_visible_survives_the_withdrawal():
    """V22-4 is fixed in v2.3: registering s: y = x + 1 depends only on x's binding, not on x's value step, so
    withdrawing c (behind x = 3) no longer taints s, whichever order s and x = 3 were recorded in."""
    t = _x_value_then_law(register_law_first=False)
    assert t.derive(ROOT, "y = 6", binds="y", from_relations=["s"]).check == "checked"


def test_resupplying_a_tainted_law_gets_advice_that_can_be_followed():
    """V22-4 (consequence) is fixed in v2.3: s no longer rests on the withdrawn c, so if the word-for-word
    re-supply s2 is told to deliver the original instead, deliver() accepts s."""
    t = _x_value_then_law(register_law_first=False)
    t.input(ROOT, "s2", "model", "y is x plus one", relation="y = x + 1")
    t.derive(ROOT, "y = 6", binds="y", from_relations=["s2"])
    t.answer(["y"])
    if any("s2 repeats the INPUT s" in w and "deliver the original" in w for w in t.ledger()["warnings"]):
        t.deliver(t.demand(ROOT, "D", "d"), "s")  # the advice must be followable


# =============================================================================
# E. Delivery
# =============================================================================


def test_deliver_through_one_level_and_value_step_in_the_text():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, d1a, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    s = t.solve(ROOT, ["rx"], ["x"])
    vs = t.steps[t.value_step["x"]]
    assert vs.op == "DERIVE" and vs.index == s.index + 1
    with pytest.raises(HiddenLookupError, match="caller 'D1'"):
        t.deliver(d1a, "x")
    [st] = t.deliver_through(d1, "x")
    assert f"value fixed at {vs.id}" in st.text
    assert t.value_visible(d1a, "x") is not None  # a delivery reaches the whole subtree


def test_deliver_through_two_levels():
    """V21-14 is fixed: one DELIVER, into the highest frame below the frame that sees the value."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    t.input(ROOT, "g", "value", "g", value=2)
    n = len(t.steps)
    [st] = t.deliver_through(d1b, "g")
    assert st.frame == d1 and len(t.steps) == n + 1
    assert t.value_visible(d1b, "g") is not None
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(d1b, "g")


def test_deliver_through_delivers_just_below_the_nearest_frame_that_sees_the_value():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    unknowns(t, d1, "x")
    t.input(d1, "rx", "model", "x three", relation="x = 3")
    t.derive(d1, "x = 3", binds="x", from_relations=["rx"])
    [st] = t.deliver_through(d1b, "x")
    assert st.frame == d1a and st.text.startswith("x = 3, delivered from D1 ")


def test_deliver_through_unbound_or_withdrawn_name_is_not_a_hidden_lookup():
    """V21-15 is fixed."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "c", "completeness", "c")
    t.withdraw(ROOT, "c", "why")
    for name, word in (("nope", "not bound"), ("c", "withdrawn")):
        with pytest.raises(TraceError, match=word) as info:
            t.deliver_through(d, name)
        assert not isinstance(info.value, HiddenLookupError)


def test_deliver_many_is_atomic_for_unbound_names():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "m", "value", "m", value=2)
    n, c = len(t.steps), len(t.commands)
    with pytest.raises(TraceError):
        t.deliver_many(d, ["m", "nope"])
    assert (len(t.steps), len(t.commands)) == (n, c)


def test_deliver_many_is_atomic_for_tainted_names():
    """V21-16 is fixed: rx's binding rests on c, so it cannot be delivered and nothing is recorded. x itself
    (only its value is tainted) is delivered by name."""
    t, _ = _withdrawn_x()
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "m", "value", "m", value=2)
    n, c = len(t.steps), len(t.commands)
    with pytest.raises(TraceError, match="withdrawn"):
        t.deliver_many(d, ["m", "rx"])
    assert (len(t.steps), len(t.commands)) == (n, c)
    t.deliver_many(d, ["m", "x"])
    assert t.value_visible(d, "m") is not None
    assert t.visible(d, "x") is not None and t.value_visible(d, "x") is None


def test_steps_rest_on_the_binding_and_value_not_on_the_delivery():
    """v2.2: a DELIVER step is not provenance; the cone holds the binding and value steps instead."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    g = t.input(ROOT, "g", "value", "g", value=2)
    dl = t.deliver(d, "g")
    unknowns(t, d, "y")
    t.input(d, "r", "model", "y twice g", relation="y = 2*g")
    st = t.derive(d, "y = 4", binds="y", from_relations=["r"])
    assert g.index in st.deps and dl.index not in st.deps
    t.answer(["y"])
    assert dl.index not in t.cone() and g.index in t.cone()


# =============================================================================
# F. Answers, annotations and replay
# =============================================================================


def test_per_answer_annotations_and_replay():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "k", "value", "k", value=3)
    t.answer(["m"], label="pm")
    t.answer(["k"], label="pk")
    t.annotate("k", "NEEDS", countermodel="k = 4", answer="pk")
    assert not any("k is marked" in w for w in t.ledger("pm")["warnings"])
    t.annotate("m", "REQUIRED")
    t.annotate("m", "USES", answer="pm")
    assert [(c["name"], c["status"]) for c in t.ledger("pm")["pruned"]] == [("m", "USES")]
    with pytest.raises(TraceError, match="no answer"):
        t.annotate("m", "USES", answer="nope")
    again = Trace.replay(json.loads(json.dumps(t.to_record())))
    assert again.annotations == t.annotations
    assert again.to_record()["ledgers"] == t.to_record()["ledgers"]


def test_a_default_status_warns_only_where_the_premise_feeds_no_answer():
    """v2.1 note closed: a default NEEDS on m (which feeds pm) is not warned in pk; a default on j (which feeds
    no answer) is warned in every ledger; a per-answer status is warned in its own answer."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "k", "value", "k", value=3)
    t.input(ROOT, "j", "value", "j", value=4)
    t.answer(["m"], label="pm")
    t.answer(["k"], label="pk")
    t.annotate("m", "NEEDS", countermodel="m = 5")
    t.annotate("j", "REQUIRED")
    t.annotate("k", "NEEDS", countermodel="k = 1", answer="pm")
    assert t.ledger("pk")["warnings"] == ["j is marked REQUIRED but does not feed this answer",
                                          "1 commitment(s) have no status yet: k"]
    assert t.ledger("pm")["warnings"] == ["k is marked NEEDS but does not feed this answer",
                                          "j is marked REQUIRED but does not feed this answer"]


def test_labels_and_default_label():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    assert t.answer(["m"], label="p1").tag == "p1"
    assert t.answer(["m"]).tag == "p2"
    for bad in ("p 1", "a\n# injected", "*", "p1\n"):
        with pytest.raises(TraceError):
            t.answer(["m"], label=bad)
    assert t.answer(["m"], label=".").tag == "."  # allowed, if odd


def test_failed_determination_binds_nothing():
    """v2.2: a failed derive(binds=) no longer lists its intended binding."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="x = 2")
    st = t.derive(ROOT, "x = 3", from_relations=["r"], binds="x")
    assert (st.check, st.binds) == ("failed", ())
    assert st.detail.endswith("; x not determined") and "x" not in t.values


def test_lenient_replay_with_global_conflicts_mistakes_and_withdrawal():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "y", "z")
    t.input(ROOT, "x", "value", "x", value=3)
    t.derive(ROOT, "2*x = 7", name="bad")
    t.input(ROOT, "c", "completeness", "c")
    t.input(ROOT, "ry", "model", "y", relation="y = 1", uses=["c"])
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"], uses=["bad"])
    t.answer(["y"])
    t.withdraw(ROOT, "c", "why")
    t.input(ROOT, "rz", "model", "z", relation="z = 2")
    t.input(ROOT, "rz2", "model", "z again", relation="2*z = 5")
    t.consistency(ROOT, ["rz", "rz2"])
    t.solve(ROOT, ["rz"], ["z"])
    t.answer(["z"], label="second")
    t.annotate("rz", "NEEDS", countermodel="z = 3", answer="second")
    rec = json.loads(json.dumps(t.to_record()))
    assert rec["entries"] == {}
    again = Trace.replay(rec)
    assert again.to_record()["sha256"] == rec["sha256"]


def test_replay_reproduces_the_v22_mechanisms():
    """Per-value solve steps, withdrawal of a tainted premise, re-determination, a two-level deliver_through,
    a found mistake, a joint conflict and a division-by-zero row all replay exactly."""
    t = Trace("q", strict=False)
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, ROOT, "x", "y", "u", "z", "w", "v")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "sum", relation="x + y = 5", uses=["c"])
    t.input(ROOT, "ry", "model", "difference", relation="x - y = 1")
    t.solve(ROOT, ["rx", "ry"], ["x", "y"])
    t.answer(["x"], label="p1")
    t.withdraw(ROOT, "c", "another force acts")
    t.withdraw(ROOT, "rx", "dropped as well")
    t.input(ROOT, "rx2", "model", "x revised", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx2"])
    t.deliver_through(d1a, "x")
    assert t.derive(d1a, "2*x = 9").detail.startswith("mistake")
    t.input(ROOT, "r1", "model", "r1", relation="u = z + 1")
    t.input(ROOT, "r2", "model", "r2", relation="u = z + 2")
    t.input(ROOT, "rw", "model", "w", relation="w = 1")
    t.derive(ROOT, "w = 1", binds="w", from_relations=["rw"], uses=["r1", "r2"])
    t.answer(["x", "w"], label="p2")
    t.input(ROOT, "zero", "value", "zero", value=0)
    t.input(ROOT, "rq", "model", "q", relation="u = 6/zero")
    t.input(ROOT, "rv", "model", "v", relation="v = 2")
    t.derive(ROOT, "v = 2", binds="v", from_relations=["rv"], uses=["rq"])
    t.answer(["v"], label="p3")
    assert t.ledger("p1")["answer"] == "x = 3"
    assert conflict_refs(t, "p2") == ["r1, r2"] and conflict_refs(t, "p3") == ["rq"]
    rec = json.loads(json.dumps(t.to_record()))
    again = Trace.replay(rec)
    assert again.to_record()["sha256"] == rec["sha256"]


V2_RECORD = Path(__file__).resolve().parent.parent / "atwood_v2_record.json"


@pytest.mark.skipif(not V2_RECORD.exists(), reason="the saved v2 Atwood record is not present")
def test_note_a_v2_record_is_rejected_as_a_mismatch_not_as_an_old_version():
    """VERSION is still 1 although the ledger schema and step texts changed (and v2.2 adds a DERIVE per solved
    value), so a saved v2 record fails with 'did not reproduce', which reads like tampering."""
    rec = json.loads(V2_RECORD.read_text(encoding="utf-8"))
    assert rec["version"] == handtrace.VERSION == 1
    assert "mistakes" not in next(iter(rec["ledgers"].values()))
    with pytest.raises(TraceError, match="did not reproduce"):
        Trace.replay(rec)


# =============================================================================
# G. Entries and validation
# =============================================================================


def test_quotes_must_be_two_whole_words():
    t = Trace("q", entries={"E8": E8})
    for q in ("ass", "net-force-material-object", "rce-material-object divided", "material-object divided"):
        with pytest.raises(TraceError):
            t.entry(ROOT, "E8", q)
    t.entry(ROOT, "E8", "its net-force-material-object divided by")
    with pytest.raises(TraceError, match="empty"):
        Trace("q", entries={})


@needs_entries
def test_quote_rule_counts_only_word_tokens_and_uses_unicode_boundaries():
    """v2.1 notes closed, against the Design 2.1 entries: ':=' is not a word, so ':= For' and the bare headword
    line are refused; 'u' inside 'λu' (K4) is not a word start; '∈' is not a word."""
    t = Trace("q", entries=_entries())
    for ref, q in (("E8", ":= For"), ("E7", "inertial-acceleration-material-object :="), ("K4", "u, with"),
                   ("K1", "∈ R;"), ("E4", "without being a free"), ("K12", "Second derivative")):
        with pytest.raises(TraceError):
            t.entry(ROOT, ref, q)
    for ref, q in (("K4", "r0 + λu"), ("K4", "λu, with r0"), ("K1", "t ∈ R"), ("E4", "being a free-particle."),
                   ("K12", "second derivative")):
        t.entry(ROOT, ref, q)


@needs_entries
def test_note_the_headword_plus_one_word_verifies_under_two_definitions():
    """Two word tokens are enough: 'inertial-acceleration-material-object := For' verifies under E7, E8 and the
    combined ref 'E7 / E8', so such a quote does not show which definition is applied."""
    t = Trace("q", entries=_entries())
    for ref in ("E7", "E8", "E7 / E8"):
        t.entry(ROOT, ref, "inertial-acceleration-material-object := For")


@needs_entries
def test_a_combined_ref_needs_every_part_to_hold_the_quote():
    """V21-17 is fixed."""
    t = Trace("q", entries=_entries())
    t.entry(ROOT, "K16 / E1", "A frame-indexed interval property")
    t.entry(ROOT, "E8/E9", "For one material-object")  # in both texts
    with pytest.raises(TraceError, match="E99"):
        t.entry(ROOT, "E8 / E99", "divided by its inertial-mass-material-object.")
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E7 / E8", "For one material-object")  # E7 reads 'For a material-object'
    with pytest.raises(TraceError, match="E99"):
        t.demand(ROOT, "D", "d", ref="E8 / E99", quote="divided by its")


def test_demand_quote_is_verified_and_linked():
    t = Trace("q", entries={"E8": E8})
    e = t.entry(ROOT, "E8", "its net-force-material-object divided by its inertial-mass-material-object.")
    t.demand(ROOT, "D1", "net force of A", ref="E8", quote="its net-force-material-object")
    assert t.steps[-1].deps == (e.index,)
    with pytest.raises(TraceError, match="verbatim"):
        t.demand(ROOT, "D2", "x", ref="E8", quote="its net-force")
    with pytest.raises(TraceError, match="only an unknown introduced by ENTRY"):
        t.unknown(ROOT, "x", "x", address="(x)", ref="E8", quote="its net-force-material-object divided")


def test_note_demand_link_does_not_reach_any_cone_and_a_bare_ref_is_unchecked():
    """The DEMAND step depends on the ENTRY, but nothing depends on a DEMAND step, so the entry-time quote
    stays outside every answer that the demand's frame returns. demand(ref=) without a quote is not checked
    against the entries."""
    t = Trace("q", entries={"E8": E8})
    e = t.entry(ROOT, "E8", "its net-force-material-object divided by its inertial-mass-material-object.")
    d = t.demand(ROOT, "D1", "net force of A", ref="E8")
    t.input(d, "F", "value", "net force", value=2)
    t.answer(["F"])
    led = t.ledger()
    assert led["theory"] == [] and e.id in [r["step"] for r in led["outside_answer"]]
    t.demand(ROOT, "X", "x", ref="E99")


def test_validation_rules():
    t = Trace("q")
    with pytest.raises(TraceError):
        t.input(ROOT, "m\n", "value", "m", value=2)
    with pytest.raises(TraceError, match="="):
        t.input(ROOT, "r", "model", "no equals", relation="x + 1")
    with pytest.raises(TraceError, match="value="):
        t.input(ROOT, "m", "value", "mass of A")
    for bad in (float("inf"), float("nan")):
        with pytest.raises(TraceError):
            t.input(ROOT, "v", "value", "v", value=bad)
    assert mentioned_names("a*b + c = d") == ("a", "b", "c", "d")


def test_note_unsupported_relations_are_refused_at_entry_and_value_model_without_value_is_a_fact():
    """'value/model' without value= becomes a fact (still open). v2.3: relations in syntax outside the checker
    (%, //, an attribute, a string) are refused at entry and nothing is recorded; a fractional power such as
    n**0.5 = 2 is inside the syntax and registers."""
    t = Trace("q")
    t.input(ROOT, "g", "value/model", "local g, uniform field")
    assert t.bindings["g"].sort == "fact"
    t.input(ROOT, "n", "value", "n", value=7)
    hint = "; use numbers, names, + - * / and ** (a root is **0.5 or **(1/3))"
    refused = {
        "n % 2 = 1": f"outside the checker's syntax (Mod) in 'n % 2'{hint}",
        "n // 2 = 3": f"outside the checker's syntax (FloorDiv) in 'n // 2'{hint}",
        "n.real = 7": f"outside the checker's syntax (Attribute) in 'n.real'{hint}",
        "n = 'seven'": "outside the checker's syntax (constant 'seven') in \"'seven'\"",
    }
    for i, (rel, message) in enumerate(refused.items()):
        steps, commands = len(t.steps), len(t.commands)
        with pytest.raises(TraceError) as exc:
            t.input(ROOT, f"r{i}", "model", rel, relation=rel)
        assert str(exc.value) == message
        assert (len(t.steps), len(t.commands)) == (steps, commands) and f"r{i}" not in t.bindings
    t.input(ROOT, "r4", "model", "n**0.5 = 2", relation="n**0.5 = 2")
    assert t.bindings["r4"].sort == "relation"


def test_note_an_unchecked_external_relation_can_fix_an_answer_without_a_warning():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.external(ROOT, "inspection", "x by inspection", relation="x = 1000", binds="rx")
    t.derive(ROOT, "x = 1000", from_relations=["rx"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert led["warnings"] == [] and [s["check"] for s in led["step_members"]] == ["unchecked", "checked"]


# =============================================================================
# H. Cost of a ~300-step synthetic trace
# =============================================================================


def synthetic(n_frames, *, nested=False, withdraw_early=False, answer_every=6):
    """n_frames frames, each: DEMAND, DELIVER (previous value and g), unknown, model INPUT, DERIVE."""
    t = Trace("synthetic")
    t.input(ROOT, "g", "value", "g", value="9.8")
    if withdraw_early:
        t.input(ROOT, "junk", "recognition", "an unrelated premise")
        t.withdraw(ROOT, "junk", "not needed")
    parent, prev = ROOT, None
    for i in range(1, n_frames + 1):
        f = t.demand(parent if nested else ROOT, f"D{i}", f"frame {i}")
        if prev is None:
            t.deliver(f, "g")
        elif nested:
            t.deliver(f, prev)
        else:
            t.deliver_many(f, [prev, "g"])
        x = f"x{i}"
        t.unknown(f, x, f"quantity {i}", address=f"(q{i})", ref="t")
        t.input(f, f"r{i}", "model", f"relation {i}", relation=f"{x} = g" if prev is None else f"{x} = {prev} + g")
        t.derive(f, f"{x} = {Fraction(49, 5) * i}", from_relations=[f"r{i}"], binds=x)
        if answer_every and i % answer_every == 0:
            t.answer([x], label=f"a{i}")
        if nested:
            parent = f
        prev = x
    return t


@pytest.mark.parametrize("shape", [
    dict(n_frames=50, nested=False, withdraw_early=False, answer_every=5),
    dict(n_frames=60, nested=True, withdraw_early=True, answer_every=6),
    dict(n_frames=50, nested=False, withdraw_early=True, answer_every=1),
])
def test_synthetic_300_step_trace_ledger_and_markdown_stay_fast(shape, capsys):
    t0 = time.perf_counter()
    t = synthetic(**shape)
    build = time.perf_counter() - t0
    assert 250 <= len(t.steps) <= 400
    t0 = time.perf_counter()
    led = t.ledger()
    ledger_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    md = t.to_markdown()
    md_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    Trace.replay(t.to_record())
    replay_s = time.perf_counter() - t0
    with capsys.disabled():
        print(f"\n[timing] {shape}: steps={len(t.steps)} answers={len(t.answers)} build={build:.3f}s "
              f"ledger={ledger_s:.4f}s markdown={md_s:.3f}s replay={replay_s:.3f}s")
    assert len(led["commitments"]) == shape["n_frames"] + 1
    assert md.count("## Ledger for answer") == len(t.answers)
    assert ledger_s < 1.0 and md_s < 3.0


def test_note_markdown_builds_every_answers_cone_for_every_ledger(monkeypatch):
    """V22-7: ledger() now builds every answer's cone (for the default-status warning), and to_markdown()
    computes two ledgers per answer, so rendering costs 2 * A * (A + 1) cone() calls. Measured on 100 answers
    over 702 steps: markdown 1.0-1.6 s (v2.1: 0.29 s), to_record 0.6-1.1 s (v2.1: 0.32 s)."""
    t = synthetic(30, answer_every=3)
    calls = []
    real = Trace.cone

    def counting(self, answer=None):
        calls.append(answer)
        return real(self, answer)

    monkeypatch.setattr(Trace, "cone", counting)
    t.to_markdown()
    a = len(t.answers)
    assert a == 10 and len(calls) == 2 * a * (a + 1)
