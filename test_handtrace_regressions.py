"""Regression tests: bookkeeping errors found in earlier hand traces.

Each test reintroduces one error and asserts that the recorder (handtrace
v2.3) catches it.

* R01-R08: errors that adversarial reviews found in the hand Atwood traces.
* R09-R17: further error classes a hand tracer could make.
* R18-R26: errors the first review of the recorder reported as uncaught
  (regress-*, review-code-*, enc-*); v2 catches them.
* v2.1 closed the v2 findings on these classes: an arithmetic slip is a found
  mistake, not a conflict (R03, R14, R16); an answer resting on an unchecked
  DERIVE is warned (R21b); a withdrawn premise taints what rests on it (R26).
* v2.2 closes the v2.1 regress-* findings (ids refer to the v2.1 findings
  file): deliver_through works on any chain (R01b, regress-1); an unrelated
  hidden value no longer blocks a slip (R06c, regress-2); solve() records one
  DERIVE per fixed value with its own provenance (R20c, R26d, R31,
  regress-3); every part of a combined ref must hold the quote (R24c, R32,
  regress-4); a copy made before a withdrawal is named (R26c, regress-5);
  consistency() refuses a hidden value that would change its result (R13b,
  regress-6); a relation that only shares a description is not a re-supply
  (R19c, regress-7); ':=' is not a word (R32, regress-8); a failed
  determination binds nothing (R21, regress-10). Withdrawal now taints by
  value: the name stays usable and the quantity may be determined again
  (R26, R27).
* R27-R33 probe the v2.2 mechanisms: re-determination after a withdrawal,
  the hidden-value rule, claims that cannot be evaluated, the global check as
  of the answer, per-value solve provenance, quotes against the Design 2.1
  entries file, and the minimal-citation threshold.
* v2.3 fixes three v2.2 bugs: a hidden value that changes the verdict
  category blocks the step (R06d); a relation rests only on the binding steps
  of the names it mentions, not on their values (R27b); the global check
  reads a per-name value history (R27d). A restatement that needs a withdrawn
  value is refused until it is determined again (R26), the joint check names
  a minimal inconsistent subset (R29), and a quantity whose value was
  withdrawn is listed as undetermined (R27e).
* test_gap_* pins an error class v2.2 still leaves open, and test_note_* a
  v2.2 friction. Each pins the current behaviour so that closing the gap
  shows up as a failure to rewrite; none of them endorses that behaviour.

A test marked xfail(strict=True) is a bug still open; its reason
gives the repro.
"""

import json
import random
import re
import time
from fractions import Fraction
from pathlib import Path

import pytest

from handtrace import (ROOT, CheckError, HiddenLookupError, Trace, TraceError, UndefinedValue, _digest,
                       load_entries)

G = Fraction(49, 5)
LAWS = ["law1", "law2", "meq", "kin"]
UNKNOWNS = ["a1", "a2", "T1", "T2"]

E8 = ("For one material-object, its net-force-material-object divided by its "
      "inertial-mass-material-object.")
# E8 as the Design 2.1 Draft 1 entries file states it (R24b checks this copy).
ENTRIES = {"E8": "inertial-acceleration-material-object := " + E8}
ENTRIES_FILE = Path("C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/07_design_2_1/"
                    "DESIGN_2_1_DRAFT_1_ENTRIES.md")
needs_entries_file = pytest.mark.skipif(not ENTRIES_FILE.exists(),
                                        reason="Design 2.1 entries file not available here")


# -- builders (one upward axis; block 1 is 3 kg, block 2 is 5 kg) -------------


def block(t, k, m, g="deliver", *, law_first=False, g_value="9.8"):
    """One block frame.

    g: 'supply' inputs g here; 'deliver' delivers it from the root (block 1's
    g is visible there because results flow up); 'resupply' inputs a fresh
    g<k> here instead of delivering (error R19).
    law_first binds the sum law before the weight has a value (error R02c).
    Each block's weight relation has its own description. v2.1 warned when two
    relation INPUTs shared a description; v2.2 warns only for values (R19c).
    """
    d = t.demand(ROOT, f"D{k}", f"inertial-acceleration-material-object(B{k}, t0, R)")
    t.input(d, f"m{k}", "value", f"inertial mass of B{k}", value=m, unit="kg")
    t.unknown(d, f"fG{k}", f"weight on B{k}", address=f"(i_G{k}, B{k}, t0)", ref="C-CM")
    t.unknown(d, f"T{k}", f"string force on B{k}", address=f"(i_S{k}, B{k}, t0)", ref="C-CM")
    t.unknown(d, f"a{k}", f"acceleration of B{k}", address=f"(B{k}, t0, R)", label="ENTRY", ref="E8", quote=E8,
              unit="m/s^2")

    def law():
        t.contract(d, "C-FS", "net force is the sum of the members", source="S8.1", binds=f"law{k}",
                   relation=f"m{k}*a{k} = fG{k} + T{k}")

    if law_first:
        law()
    gname = f"g{k}" if g == "resupply" else "g"
    if g == "deliver":
        t.deliver(d, "g")
    else:
        t.input(d, gname, "value", "local free-fall acceleration", value=g_value, unit="m/s^2")
    t.input(d, f"peqv{k}", "identity", f"the gravitational mass of B{k} is m{k}")
    t.input(d, f"w{k}", "model", f"uniform-field weight on B{k}", relation=f"fG{k} = -m{k}*{gname}",
            uses=[f"peqv{k}"])
    gv = G if g == "deliver" else Fraction(g_value)
    t.derive(d, f"fG{k} = {-m * gv}", from_relations=[f"w{k}"], binds=f"fG{k}", tag=f"weight{k}")
    if not law_first:
        law()
    return d


def couple(t):
    t.input(ROOT, "meq", "model", "ideal string over an ideal pulley: equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "length constraint differentiated twice", relation="a1 + a2 = 0",
               binds="kin")
    return t


def atwood(strict=True):
    t = Trace("Atwood regression", {"name": "regressions"}, strict=strict, entries=ENTRIES)
    block(t, 1, 3, g="supply")
    block(t, 2, 5)
    return couple(t)


def finished(strict=True):
    t = atwood(strict)
    t.solve(ROOT, LAWS, UNKNOWNS, tag="solve")
    t.answer(["a1", "a2", "T1"])
    return t


def joint_solve():
    """x and y fixed by one solve; each rests on its own premise."""
    t = Trace("q")
    for n in "xy":
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    t.input(ROOT, "A", "recognition", "the premise behind x")
    t.input(ROOT, "B", "recognition", "the premise behind y")
    t.input(ROOT, "r1", "model", "x is three", relation="x = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "y is four", relation="y = 4", uses=["B"])
    return t, t.solve(ROOT, ["r1", "r2"], ["x", "y"])


def spring_account(t):
    """A on a spring; the account assumes the spring is A's only interaction."""
    t.input(ROOT, "complete", "completeness", "the spring is the only interaction on A")
    t.input(ROOT, "m", "value", "mass of A", value=2)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    t.input(ROOT, "r", "model", "spring-only account", relation="m*a = 2", uses=["complete"])
    t.derive(ROOT, "a = 1", from_relations=["r"], binds="a")
    return t


def hidden_y(y_value):
    """Lenient trace: y's value is fixed at the root after y was delivered
    into D1 by name only, so the value exists but is hidden in D1."""
    t = Trace("q", strict=False)
    d1 = t.demand(ROOT, "D1", "block 1")
    for q in "xy":
        t.unknown(ROOT, q, q, address=f"({q})", ref="C")
    t.deliver(d1, "x")
    t.deliver(d1, "y")  # names only: y has no value yet
    t.input(ROOT, "ry", "model", f"y is {y_value}", relation=f"y = {y_value}")
    t.solve(ROOT, ["ry"], ["y"])
    t.input(d1, "r", "model", "x is three", relation="x = 3")
    t.input(d1, "r2", "model", "y is five, as copied into block 1", relation="y = 5")
    return t, d1


def names(rows):
    return [r["name"] for r in rows]


def real_warnings(led):
    """Warnings other than the one-line 'no status yet' summary."""
    return [w for w in led["warnings"] if "no status yet" not in w]


def section(markdown, title):
    """The body of the first '### title' section of a rendered trace."""
    return markdown.split(f"### {title}\n", 1)[1].split("\n###", 1)[0]


def conflict_refs(t, label=None):
    return [c["ref"] for c in t.ledger(label)["conflicts"]]


# -- R01-R08: errors found by adversarial review ---------------------------------


def test_r01_second_block_bindings_by_reference_are_refused():
    """Block 2 uses g, a block-1 premise or a block-1 relation without delivery."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply")
    d2 = t.demand(ROOT, "D2", "inertial-acceleration-material-object(B2, t0, R)")
    t.input(d2, "m2", "value", "inertial mass of B2", value=5, unit="kg")
    t.unknown(d2, "fG2", "weight on B2", address="(i_G2, B2, t0)", ref="C-CM")
    with pytest.raises(HiddenLookupError, match="g"):
        t.input(d2, "w2", "model", "uniform-field weight", relation="fG2 = -m2*g")
    with pytest.raises(HiddenLookupError, match="peqv1"):
        t.input(d2, "w2", "model", "uniform-field weight", relation="fG2 = -49", uses=["peqv1"])
    with pytest.raises(HiddenLookupError, match="w1"):
        t.derive(d2, "fG1 = -147/5", from_relations=["w1"])
    # a delivery passes a binding down from the caller: it cannot skip the
    # caller (review-code-11), and nothing is delivered into the root
    d2a = t.demand(d2, "D2a", "a sub-demand of block 2")
    with pytest.raises(HiddenLookupError, match="caller 'D2'"):
        t.deliver(d2a, "g")
    with pytest.raises(TraceError, match="root"):
        t.deliver(ROOT, "g")
    # the delivery is a recorded step, it reaches D2 and below only, and g stays one member
    dl = t.deliver(d2, "g")
    assert t.derive(d2a, "2*g = 98/5").check == "checked"
    d3 = t.demand(ROOT, "D3", "a third frame")
    with pytest.raises(HiddenLookupError, match="g"):
        t.derive(d3, "2*g = 98/5")
    t.input(d2, "peqv2", "identity", "the gravitational mass of B2 is m2")
    t.input(d2, "w2", "model", "uniform-field weight on B2", relation="fG2 = -m2*g", uses=["peqv2"])
    t.derive(d2, "fG2 = -49", from_relations=["w2"], binds="fG2")
    t.answer(["fG2"])
    led = t.ledger()
    assert names(led["commitments"]).count("g") == 1
    # v2.2: a step rests on the binding and value steps, not on the delivery
    # route, so the DELIVER is outside the cone and g's own INPUT is inside
    assert dl.index not in t.cone() and t.bindings["g"].step in t.cone()


def test_r01b_deliver_through_passes_a_binding_down_a_chain_of_callers():
    """atwood-3 / regress-1 (xfail in v2.1, fixed in v2.2): one DELIVER into the
    highest frame below the nearest frame that sees the name; that delivery
    reaches every frame below it. The call is all or nothing."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply")
    d2 = t.demand(ROOT, "D2", "inertial-acceleration-material-object(B2, t0, R)")
    d2a = t.demand(d2, "D2a", "a sub-demand of block 2")
    d2b = t.demand(d2a, "D2b", "a sub-sub-demand of block 2")
    n = len(t.steps)
    steps = t.deliver_through(d2b, "g")
    assert [(s.op, s.frame) for s in steps] == [("DELIVER", d2)] and len(t.steps) == n + 1
    assert t.value_visible(d2a, "g") is not None and t.value_visible(d2b, "g") is not None
    assert t.derive(d2b, "2*g = 98/5").check == "checked"
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(d2a, "g")
    # the middle frame sees the name but not the value: the value is delivered there
    x = Trace("q")
    d1 = x.demand(ROOT, "D1", "one")
    d1a = x.demand(d1, "D1a", "two")
    x.unknown(ROOT, "v", "v", address="(v)", ref="C")
    x.deliver(d1, "v")  # name only
    x.input(ROOT, "rv", "model", "v is three", relation="v = 3")
    x.derive(ROOT, "v = 3", from_relations=["rv"], binds="v")
    assert [(s.frame, s.text.split(",")[0]) for s in x.deliver_through(d1a, "v")] == [(d1, "v = 3")]
    # unbound and withdrawn names are a TraceError, not a hidden lookup (probes-13), and record nothing
    x.input(ROOT, "c", "completeness", "only the spring")
    x.withdraw(ROOT, "c", "B pulls too")
    n = (len(x.steps), len(x.commands))
    for bad, msg in (("c", "withdrawn"), ("zz", "not bound")):
        with pytest.raises(TraceError, match=msg) as exc:
            x.deliver_through(d1a, bad)
        assert not isinstance(exc.value, HiddenLookupError)
    assert (len(x.steps), len(x.commands)) == n


def test_r02_values_come_only_from_recorded_steps():
    """An arithmetic substitution (fG1 = -m1*g = -147/5) used without its own step."""
    t = Trace("Atwood regression")
    d = t.demand(ROOT, "D1", "block 1")
    t.input(d, "m1", "value", "mass", value=3, unit="kg")
    # a 'value' INPUT that supplies no number is refused; v2 bound it as a fact (regress-8b / review-v2-23)
    with pytest.raises(TraceError, match="must supply value="):
        t.input(d, "g", "value", "g")
    t.input(d, "g", "value", "g", value="9.8", unit="m/s^2")
    t.unknown(d, "fG1", "weight on B1", address="(i_G1, B1, t0)", ref="C-CM")
    t.unknown(d, "T1", "string force", address="(i_S1, B1, t0)", ref="C-CM")
    t.unknown(d, "a1", "acceleration", address="(B1, t0, R)", label="ENTRY", ref="E8", quote=E8)
    t.input(d, "w1", "model", "uniform-field weight", relation="fG1 = -m1*g")
    t.contract(d, "C-FS", "sum of members", source="S8.1", binds="law1", relation="m1*a1 = fG1 + T1")
    # a determined value without a cited relation is refused
    with pytest.raises(TraceError, match="cite"):
        t.derive(d, "fG1 = -147/5", binds="fG1")
    # the unrecorded value cannot be used: fG1 is still symbolic
    with pytest.raises(CheckError):
        t.derive(d, "fG1 = -147/5")
    with pytest.raises(CheckError):
        t.derive(d, "3*a1 = -147/5 + T1", from_relations=["law1"])
    # a 'value' that still depends on unknowns is refused
    with pytest.raises(TraceError, match="not a value"):
        t.derive(d, "fG1 = 3*a1 - T1", from_relations=["law1"], binds="fG1")
    # once recorded, the substitution checks
    w = t.derive(d, "fG1 = -147/5", from_relations=["w1"], binds="fG1", tag="weight1")
    assert t.value_step["fG1"] == w.index
    sub = t.derive(d, "3*a1 = -147/5 + T1", from_relations=["law1"])
    assert sub.check == "checked"
    # law1 predates fG1's value; the step that produced the value is still a dependency (v1 bug, fixed)
    assert w.index in sub.deps


def test_r02b_a_value_written_into_the_books_by_hand_fails_replay():
    """A value set directly on the trace object, not by a step."""
    t = Trace("q")
    t.unknown(ROOT, "x", "a quantity", address="(x)", ref="C")
    t.input(ROOT, "r", "model", "relation", relation="2*x = 6")
    # the honest record replays: a trace without entries replays with entries=None (v2.1)
    assert len(Trace.replay(json.loads(json.dumps(t.to_record()))).steps) == 2
    t.values["x"], t.value_step["x"] = Fraction(3), 1
    t.answer(["x"])
    with pytest.raises(TraceError, match="no value"):
        Trace.replay(json.loads(json.dumps(t.to_record())))


@pytest.mark.parametrize("route", ["derive", "solve"])
def test_r02c_a_law_written_before_its_weight_keeps_the_weight_route(route):
    """regress-1 / review-code-1 / enc-spring1-1: values substituted into a cited
    relation must bring the steps that produced them into the cone."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply", law_first=True)
    block(t, 2, 5, law_first=True)
    couple(t)
    if route == "derive":
        t.derive(ROOT, "a1 = 49/20", from_relations=LAWS, binds="a1")
    else:
        t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    led = t.ledger()
    assert {"m1", "m2", "g", "peqv1", "peqv2", "w1", "w2", "meq"} <= set(names(led["commitments"]))
    assert not {"g", "w1", "w2"} & set(names(led["not_in_answer"]))
    assert {"weight1", "weight2"} <= {s["tag"] for s in led["step_members"]}


def test_r03_adding_instead_of_subtracting_the_block_relations():
    """On one upward axis law1 - law2 eliminates T; law1 + law2 does not.
    v2.1 reports the slip as a found mistake, apart from premise conflicts
    (regress-7 / probes-16 / spring2-6)."""
    t = atwood()
    with pytest.raises(CheckError, match="mistake: does not follow"):
        t.derive(ROOT, "3*a1 + 5*a2 = -147/5 - 49", from_relations=["law1", "law2", "meq"])
    with pytest.raises(CheckError, match="mistake"):
        t.derive(ROOT, "-2*a1 = -392/5", from_relations=LAWS)
    with pytest.raises(CheckError, match="mistake"):
        t.derive(ROOT, "a1 = 196/5", from_relations=LAWS, binds="a1")
    assert "a1" not in t.values
    assert t.derive(ROOT, "3*a1 - 5*a2 = 98/5", from_relations=["law1", "law2", "meq"]).check == "checked"
    assert t.derive(ROOT, "8*a1 = 98/5", from_relations=LAWS).check == "checked"
    # lenient mode keeps the slip as a found mistake
    t2 = atwood(strict=False)
    slip = t2.derive(ROOT, "3*a1 + 5*a2 = -147/5 - 49", from_relations=["law1", "law2", "meq"], tag="slip")
    t2.solve(ROOT, LAWS, UNKNOWNS)
    t2.answer(["a1"])
    assert slip.check == "failed" and slip.detail.startswith("mistake: does not follow")
    led = t2.ledger()
    assert [f["step"] for f in led["mistakes"]] == [slip.id]
    assert led["conflicts"] == []
    assert not real_warnings(led)  # the slip does not feed the answer
    assert t2.values["a1"] == Fraction(49, 20)
    md = t2.to_markdown()
    assert slip.id in section(md, "Found mistakes") and section(md, "Conflicts").strip() == "- none"


def test_r04_needs_without_a_countermodel_is_refused():
    t = finished()
    before = len(t.commands)
    for cm in ("", "   "):
        with pytest.raises(TraceError, match="countermodel"):
            t.annotate("m1", "NEEDS", countermodel=cm)
    assert "m1" not in t.annotations and len(t.commands) == before
    with pytest.raises(TraceError, match="INPUT"):
        t.annotate("law1", "NEEDS", countermodel="another sum rule")
    with pytest.raises(TraceError, match="no answer labelled"):
        t.annotate("m1", "NEEDS", countermodel="m1 = 4 kg", answer="p9")
    t.annotate("m1", "NEEDS", countermodel="m1 = 4 kg, all else held: a1 = 49/45")
    with pytest.raises(TraceError, match="countermodel"):
        t.annotate("m1", "NEEDS")
    row = next(c for c in t.ledger()["commitments"] if c["name"] == "m1")
    assert row["status"] == "NEEDS" and row["countermodel"].startswith("m1 = 4 kg")


def test_r05_two_encounters_under_one_address_are_refused():
    """Two reactions on one recipient (two string segments on pulley P) merged."""
    t = Trace("pulley")
    t.unknown(ROOT, "TL", "left segment pull on P", address="(i_S, P, t0)", ref="C-CM")
    with pytest.raises(TraceError, match="address"):
        t.unknown(ROOT, "TR", "right segment pull on P", address="(i_S, P, t0)", ref="C-CM")
    d = t.demand(ROOT, "DP", "pulley frame")
    with pytest.raises(TraceError, match="address"):
        t.unknown(d, "TR", "right segment pull on P", address="(i_S, P, t0)", ref="C-CM")
    # spacing does not make a second address (regress-10 / review-code-18)
    for spaced in ("(i_S,P,t0)", " (i_S, P, t0) ", "(i_S,\tP,\nt0)"):
        with pytest.raises(TraceError, match="address"):
            t.unknown(d, "TR", "right segment pull on P", address=spaced, ref="C-CM")
    t.unknown(d, "TR", "right segment pull on P", address="(i_SR, P, t0)", ref="C-CM")
    # in the Atwood trace: a second reaction on B1 under the string's address
    a = atwood()
    with pytest.raises(TraceError, match="address"):
        a.unknown("D1", "N1", "a second reaction on B1", address="(i_S1, B1, t0)", ref="C-CM")


def test_r06_root_value_in_a_child_frame_needs_delivery():
    t = atwood()
    t.solve(ROOT, LAWS, UNKNOWNS)
    assert t.value_visible("D1", "a1") is None
    # reported as a hidden lookup, not as an arithmetic failure (regress-12, fixed)
    with pytest.raises(HiddenLookupError, match="a1.*deliver"):
        t.derive("D1", "3*a1 = 147/20")
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive("D1", "T1 = 147/4", from_relations=["law1"])
    d3 = t.demand(ROOT, "D3", "a later child frame")
    with pytest.raises(HiddenLookupError, match="a1"):
        t.derive(d3, "2*a1 = 49/10")
    t.deliver("D1", "a1")
    assert t.derive("D1", "3*a1 = 147/20").check == "checked"
    # lenient mode does not record it as a found mistake either
    t2 = atwood(strict=False)
    t2.solve(ROOT, LAWS, UNKNOWNS)
    n = len(t2.steps)
    with pytest.raises(HiddenLookupError):
        t2.derive("D1", "3*a1 = 147/20")
    assert len(t2.steps) == n
    # the same error inside a product, in a solve, and in a determined right side
    s = Trace("q")
    d = s.demand(ROOT, "D1", "block 1")
    for q in ("x", "y", "z"):
        s.unknown(d, q, f"quantity {q}", address=f"({q})", ref="C")
    s.input(ROOT, "rx", "model", "rx", relation="x = 2")
    s.input(ROOT, "ry", "model", "ry", relation="y = 3")
    s.solve(ROOT, ["rx", "ry"], ["x", "y"])
    with pytest.raises(HiddenLookupError, match="deliver"):
        s.derive(d, "x*y = 6")
    s.input(d, "rz", "model", "rz", relation="z = x + 1")
    # v2 raised a plain TraceError in both places (regress-5 / review-v2-20, fixed)
    with pytest.raises(HiddenLookupError, match="deliver"):
        s.solve(d, ["rz"], ["z"])
    with pytest.raises(HiddenLookupError, match="deliver"):
        s.derive(d, "z = x + 1", from_relations=["rz"], binds="z")
    assert "z" not in s.values


def test_r06c_an_unrelated_hidden_value_does_not_turn_a_slip_into_a_hidden_lookup():
    """regress-2 / review-v2-19 (xfail in v2.1, fixed in v2.2): y's hidden value
    5 agrees with r2, so it cannot change the verdict; the slip is recorded
    as the found mistake it is, and is the same mistake after delivery."""
    t, d1 = hidden_y(5)
    slip = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert slip.check == "failed" and slip.detail.startswith("mistake: does not follow")
    t.deliver(d1, "y")
    again = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert (again.check, again.detail) == (slip.check, slip.detail)
    # a hidden name that cancels out of the claim is not consulted either
    assert t.derive(d1, "x + y - y = 3", from_relations=["r"]).check == "checked"


def test_r06d_a_hidden_value_that_turns_a_mistake_into_a_conflict_blocks_the_step():
    """xfail in v2.2, fixed in v2.3: v2.2 compared only the check status, so
    with y = 6 hidden in D1 the slip x = 4 was filed as 'mistake: does not
    follow from r, r2', yet as a conflict (r2: y = 5) once y was delivered.
    The hidden value decides the category, so the step is now blocked."""
    t, d1 = hidden_y(6)
    with pytest.raises(HiddenLookupError):
        t.derive(d1, "x = 4", from_relations=["r", "r2"])


def test_r07_an_unused_premise_is_not_a_hypothesis_set_member():
    t = atwood()
    t.input(ROOT, "paint", "recognition", "the blocks are painted red")
    t.open(ROOT, "does paint mass matter?", uses=["paint"])
    side = t.demand(ROOT, "D3", "ceiling height (side check)")
    t.input(side, "h", "value", "ceiling height", value=2, unit="m")
    check = t.derive(side, "2*h = 4")
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    led = t.ledger()
    assert {"paint", "h"} <= set(names(led["not_in_answer"]))
    assert not {"paint", "h"} & set(names(led["commitments"]))
    assert check.id in [r["step"] for r in led["outside_answer"]]
    members = " ".join(m["member"] for m in t.hypothesis_set())
    assert "painted" not in members and "ceiling" not in members
    t.annotate("paint", "NEEDS", countermodel="unpainted blocks")
    t.annotate("h", "REQUIRED")
    warnings = " ".join(t.ledger()["warnings"])
    assert "paint is marked NEEDS" in warnings and "h is marked REQUIRED" in warnings


def test_r08_answer_quantity_without_a_value_is_refused():
    t = atwood()
    with pytest.raises(TraceError, match="no value"):
        t.answer(["a1"])
    st = t.solve(ROOT, ["law1", "law2", "kin"], UNKNOWNS)  # tension coupling forgotten
    assert "underdetermined" in st.detail and "a1" not in t.values
    t.input(ROOT, "taut", "recognition", "the string is taut")
    for bad in (["a1"], ["taut"], ["law1"], ["a1", "m1"]):
        with pytest.raises(TraceError, match="no value"):
            t.answer(bad)
    with pytest.raises(TraceError, match="not bound"):
        t.answer(["acc"])
    with pytest.raises(TraceError):
        t.answer([])
    assert t.answers == []
    # the underdetermined solve stays on the books once an answer exists; an
    # external competence that happens to be called 'linear solve' is not
    # filed as one (review-v2-15, fixed: solve steps carry kind='solve')
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.external(ROOT, "linear solve", "solved by hand elsewhere")
    t.answer(["a1"])
    assert [r["step"] for r in t.ledger()["solve_reports"]] == [st.id]


# -- R09-R17: further error classes -------------------------------------------------


def test_r09_one_name_for_two_quantities_is_refused():
    """Both block frames call their string force T."""
    t = Trace("q")
    d1, d2 = t.demand(ROOT, "D1", "block 1"), t.demand(ROOT, "D2", "block 2")
    t.unknown(d1, "T", "string force on B1", address="(i_S1, B1, t0)", ref="C-CM")
    with pytest.raises(TraceError, match="already bound"):
        t.unknown(d2, "T", "string force on B2", address="(i_S2, B2, t0)", ref="C-CM")
    with pytest.raises(TraceError, match="already bound"):
        t.input(d2, "T", "value", "string force on B2", value=37)
    # a second name that only looks the same is refused too (review-v2-11, fixed)
    for twin in ("T\n", "T ", " T"):
        with pytest.raises(TraceError, match="identifiers"):
            t.unknown(d2, twin, "string force on B2", address="(i_S2, B2, t0)", ref="C-CM")


def test_r10_rounded_value_carried_forward_is_refused():
    t = atwood()
    with pytest.raises(CheckError):
        t.derive(ROOT, "a1 = 2.4", from_relations=LAWS, binds="a1")
    with pytest.raises(CheckError):
        t.derive(ROOT, "T1 = 36.8", from_relations=LAWS, binds="T1")
    # literals are read exactly from their text, not through float (review-code-4)
    with pytest.raises(CheckError):
        t.derive(ROOT, "a1 = 2.4500000000000001", from_relations=LAWS, binds="a1")
    assert t.derive(ROOT, "a1 = 245e-2", from_relations=LAWS).check == "checked"
    assert t.derive(ROOT, "a1 = 2.45", from_relations=LAWS, binds="a1").check == "checked"  # exact
    assert t.values["a1"] == Fraction(49, 20)
    # a non-finite float is refused as a TraceError, not a bare ValueError (review-v2-16, fixed)
    for v in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(TraceError, match="finite"):
            t.input(ROOT, "g_tab", "value", "g from a table", value=v)


def test_r11_second_value_for_a_determined_quantity_is_refused():
    t = atwood()
    t.derive(ROOT, "a1 = 49/20", from_relations=LAWS, binds="a1")
    with pytest.raises(TraceError, match="already has a value"):
        t.derive(ROOT, "a1 = 49/20", from_relations=LAWS, binds="a1")
    with pytest.raises(TraceError, match="already has a value"):
        t.solve(ROOT, LAWS, UNKNOWNS)
    with pytest.raises(TraceError, match="already bound"):
        t.input(ROOT, "a1", "value", "acceleration from the textbook", value="2.45")


def test_r12_delivery_made_before_the_value_existed_does_not_carry_it():
    t = atwood()
    d3 = t.demand(ROOT, "D3", "check frame")
    d3a = t.demand(d3, "D3a", "a sub-check")
    t.deliver(d3, "a1")  # name only: a1 has no value yet
    st = t.solve(ROOT, LAWS, UNKNOWNS)
    assert t.value_visible(d3, "a1") is None and t.value_visible(d3a, "a1") is None
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d3, "2*a1 = 49/10")
    with pytest.raises(HiddenLookupError, match="deliver"):
        t.derive(d3a, "4*a1 = 49/5")
    # delivering into the sub-frame names the caller that lacks the value (probes-12, fixed)
    with pytest.raises(HiddenLookupError, match="caller 'D3'"):
        t.deliver(d3a, "a1")
    dl = t.deliver(d3, "a1")
    # the DELIVER names the binding step and the step that fixed the value (spring1-4, fixed).
    # v2.2: that step is the solve's own DERIVE 'a1 = 49/20', which names the solve report
    vstep = t.steps[t.value_step["a1"]]
    assert vstep.op == "DERIVE" and vstep.claim == "a1 = 49/20" and st.id in vstep.text
    assert f"bound at {t.steps[t.bindings['a1'].step].id}, value fixed at {vstep.id}" in dl.text
    assert t.derive(d3, "2*a1 = 49/10").check == "checked"
    # the stale name-only delivery does not shadow the later one (review-code-6)
    assert t.derive(d3a, "4*a1 = 49/5").check == "checked"
    with pytest.raises(TraceError, match="already visible"):
        t.deliver(d3a, "a1")


def test_r13_contradictory_coupling_is_a_conflict_that_stays_in_the_ledger():
    t = atwood()
    t.input(ROOT, "meq2", "model", "equal tensions, mis-copied", relation="T1 = T2 + 1")
    st = t.solve(ROOT, LAWS + ["meq2"], UNKNOWNS)
    assert st.check == "failed" and "inconsistent" in st.detail
    assert not set(UNKNOWNS) & set(t.values)
    # an inconsistent solve fixes nothing, so it records no value step
    assert t.steps[-1] is st
    with pytest.raises(TraceError, match="no value"):
        t.answer(["a1"])
    # strict mode records a deliberate conflict with consistency(), which never
    # raises; solve() now needs unknowns (spring2-3, fixed)
    with pytest.raises(TraceError, match="consistency"):
        t.solve(ROOT, ["meq", "meq2"], [])
    chk = t.consistency(ROOT, ["meq", "meq2"], text="are the two couplings compatible?")
    assert chk.check == "failed" and chk.kind == "consistency" and chk.detail.startswith("conflict")
    # dropping the mis-copied relation and solving again does not erase the evidence (regress-4)
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    led = t.ledger()
    assert [c["step"] for c in led["conflicts"]] == [st.id, chk.id]
    assert led["mistakes"] == []
    assert [r["step"] for r in led["solve_reports"]] == [st.id]
    assert "meq2" in names(led["not_in_answer"])


def test_r13b_consistency_refuses_a_hidden_value_that_would_change_its_result():
    """regress-6 (a gap test in v2.1, closed in v2.2): in D1, where a1's value
    is hidden, a mis-copied a1 = 1 is no longer reported 'consistent'. A
    hidden value that agrees with the relation, or that cannot remove a
    conflict, does not block the check."""
    t = atwood()
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.input("D1", "wrong", "model", "a mis-copied result", relation="a1 = 1")
    n = len(t.steps)
    with pytest.raises(HiddenLookupError, match="a1.*would change the result"):
        t.consistency("D1", ["wrong"])
    assert len(t.steps) == n
    t.input("D1", "right", "model", "the result, copied correctly", relation="a1 = 49/20")
    assert (t.consistency("D1", ["right"]).detail) == "consistent"
    assert t.consistency("D1", ["right", "wrong"]).check == "failed"  # a conflict either way
    t.unknown("D1", "q1", "a spare quantity", address="(q, B1)", ref="C")
    t.input("D1", "rq", "model", "q follows a1", relation="q1 = a1 + 1")
    with pytest.raises(HiddenLookupError):
        t.solve("D1", ["rq"], ["q1"])
    assert t.consistency("D1", ["rq"]).detail == "consistent"  # q1 is free: a1 cannot change it
    assert t.consistency(ROOT, ["wrong"]).check == "failed"  # where a1's value is visible


def test_r14_doctoring_the_record_to_hide_a_found_mistake_fails_replay():
    t = atwood(strict=False)
    t.derive(ROOT, "2*a1 + 5*a1 = 98/5", from_relations=LAWS, tag="slip")
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    rec = json.loads(json.dumps(t.to_record()))
    assert len(rec["ledgers"]["p1"]["mistakes"]) == 1
    for s in rec["steps"]:
        if s["check"] == "failed":
            s["check"], s["detail"] = "checked", "follows from law1, law2, meq, kin"
    rec["ledgers"]["p1"]["mistakes"] = []
    rec["sha256"] = _digest({k: v for k, v in rec.items() if k != "sha256"})
    with pytest.raises(TraceError, match="did not reproduce"):
        Trace.replay(rec)


def test_r15_using_a_name_before_its_step_is_refused():
    t = Trace("q")
    with pytest.raises(TraceError, match="not bound"):
        t.derive(ROOT, "3*m1 = 9")
    with pytest.raises(TraceError, match="not bound"):
        t.reading(ROOT, "B1 hangs on the left", uses=["peqv1"])
    assert t.steps == [] and t.commands == []


def test_r16_answer_built_on_a_failed_step_is_warned():
    """Lenient mode: a wrong named claim is cited downstream (regress-5 /
    review-code-12). The failed relation stays citable; the ledger warns. In
    v2.1 the slip is a found mistake, and the global check also finds that
    the wrong a1 contradicts law2, which the answer rests on through the slip."""
    t = atwood(strict=False)
    bad = t.derive(ROOT, "2*a1 + 5*a1 = 98/5", from_relations=LAWS, name="slip")
    t.derive(ROOT, "a1 = 14/5", from_relations=["slip"], binds="a1")
    t.solve(ROOT, ["law1", "meq", "kin"], ["a2", "T1", "T2"])
    t.answer(["a1", "T1"])
    assert bad.check == "failed" and bad.index in t.cone()
    led = t.ledger()
    assert [f["step"] for f in led["mistakes"]] == [bad.id]
    assert any(bad.id in w and "failed" in w for w in led["warnings"])
    assert [c["ref"] for c in led["conflicts"]] == ["law2"]
    assert "the answer rests on law2, which the trace's own values contradict" in led["warnings"]
    flagged = [m for m in t.hypothesis_set() if m.get("check") == "failed"]
    assert [m["from"] for m in flagged] == [bad.id]


def test_r17_wrong_sign_coupling_is_at_least_flagged_unchecked():
    """a1 = a2 instead of a1 + a2 = 0 gives free fall; only the label flags it.
    Physics is out of reach by design; this stays a partial catch. The
    unchecked-step warning of R21b covers DERIVE steps only, so an external
    competence's output is listed but not warned."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply")
    block(t, 2, 5)
    t.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "length constraint (sign slip)", relation="a1 = a2", binds="kin")
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    assert t.values["a1"] == -G  # wrong physics, not detectable here
    led = t.ledger()
    assert [u["claim"] for u in led["unchecked"]] == ["a1 = a2"]
    assert any(m.get("check") == "unchecked" and "a1 = a2" in m["member"] for m in t.hypothesis_set())
    assert not real_warnings(led)


# -- R18-R26: errors the first review reported as uncaught; v2 / v2.1 catch them --


def test_r18_contradictory_cited_relations_prove_nothing():
    """regress-3 / review-code-10 / enc-spring2-7: no ex falso."""
    t = atwood()
    t.input(ROOT, "meq2", "model", "equal tensions, mis-copied", relation="T1 = T2 + 1")
    with pytest.raises(CheckError, match="contradict"):
        t.derive(ROOT, "a1 = 1000", from_relations=LAWS + ["meq2"], binds="a1")
    assert "a1" not in t.values
    # lenient: recorded as a conflict and determines nothing
    s = Trace("q", strict=False)
    s.unknown(ROOT, "x", "a quantity", address="(x)", ref="C")
    s.input(ROOT, "r1", "model", "copied once", relation="x = 2")
    s.input(ROOT, "r2", "model", "copied again with a slip", relation="x = 3")
    both = s.derive(ROOT, "x = 7", from_relations=["r1", "r2"], binds="x")
    assert both.check == "failed" and "contradict" in both.detail and "x" not in s.values
    # a cited relation contradicted by a visible value passes nothing, not even a true claim
    s.input(ROOT, "v", "value", "v", value=2)
    s.input(ROOT, "rv", "model", "rv", relation="v = 3")
    false_claim = s.derive(ROOT, "v = 7", from_relations=["rv"])
    true_claim = s.derive(ROOT, "v = 2", from_relations=["rv"])
    assert false_claim.check == true_claim.check == "failed"
    s.derive(ROOT, "x = 2", from_relations=["r1"], binds="x")
    s.answer(["x"])
    led = s.ledger()
    assert [c["step"] for c in led["conflicts"]] == [both.id, false_claim.id, true_claim.id]
    assert led["mistakes"] == []


def test_r18b_a_contradiction_hidden_by_frames_is_found():
    """probes-7 / review-v2-1 (open in v2): D1 cites x = 7 while x = 5 is fixed
    at the root. v2.2 refuses the step in D1, because the hidden value would
    turn it into a conflict. If x is fixed only after the D1 step, the step
    checks, and the ledger's global check finds the contradiction instead."""
    t = Trace("q")
    for n in "xy":
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")  # names only
    t.input(ROOT, "rx", "model", "x is five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(d1, "r", "model", "x is seven", relation="x = 7")
    t.input(d1, "r2", "model", "y follows x", relation="y = x + 1")
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y")
    t.deliver(d1, "x")
    with pytest.raises(CheckError, match="conflict"):
        t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y")
    # the same relations, with x fixed at the root only after the D1 step
    u = Trace("q")
    for n in "xy":
        u.unknown(ROOT, n, n, address=f"({n})", ref="C")
    d1 = u.demand(ROOT, "D1", "one")
    u.deliver(d1, "x")
    u.deliver(d1, "y")
    u.input(d1, "r", "model", "x is seven", relation="x = 7")
    u.input(d1, "r2", "model", "y follows x", relation="y = x + 1")
    assert u.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y").check == "checked"
    u.input(ROOT, "rx", "model", "x is five", relation="x = 5")
    u.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    u.answer(["x", "y"])
    led = u.ledger()
    assert conflict_refs(u) == ["r", "r2"]
    assert all(c["detail"].startswith("conflict") for c in led["conflicts"])
    assert "the answer rests on r, which the trace's own values contradict" in led["warnings"]
    # a relation reached only through uses= is checked the same way
    w = Trace("q")
    w.input(ROOT, "m", "value", "mass", value=2)
    w.input(ROOT, "bad", "model", "the mass, mis-copied", relation="m = 3")
    w.unknown(ROOT, "x", "x", address="(x)", ref="C")
    w.input(ROOT, "rx", "model", "x is one", relation="x = 1")
    w.derive(ROOT, "x = 1", from_relations=["rx"], binds="x", uses=["bad"])
    w.answer(["x"])
    assert conflict_refs(w) == ["bad"]


def test_r19_re_supplying_a_premise_under_a_new_name_is_warned():
    """regress-8: block 2 inputs g again as g2 instead of delivering g."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply")
    block(t, 2, 5, g="resupply")
    couple(t)
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    led = t.ledger()
    assert {"g", "g2"} <= set(names(led["commitments"]))
    assert any(w.startswith("g2 repeats the INPUT g") and "deliver" in w for w in led["warnings"])


def test_r19b_re_supplying_a_premise_with_a_different_value_is_warned():
    """regress-1 of the v2 findings (xfail in v2, fixed in v2.1): g2 = 9.81 next
    to g = 9.8 with the same description. v2.2 keys the warning on the
    description of a value INPUT alone, so a change of kind does not hide it
    (probes-14)."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply")
    block(t, 2, 5, g="resupply", g_value="9.81")
    couple(t)
    t.solve(ROOT, LAWS, UNKNOWNS)
    t.answer(["a1"])
    assert real_warnings(t.ledger()) == ["g2 has the same description as g but a different value"]
    k = Trace("q")
    k.input(ROOT, "g", "value", "local g", value="9.8")
    k.input(ROOT, "g2", "value/model", "local g", value="9.81")
    k.answer(["g2"])
    assert real_warnings(k.ledger()) == ["g2 has the same description as g but a different value"]


def test_r19c_parallel_premises_sharing_a_description_are_not_re_supplies():
    """regress-7 (a v2.1 friction, closed in v2.2): w1: fG1 = -m1*g and w2:
    fG2 = -m2*g, both 'uniform-field weight', are one law applied to two
    blocks. The different-value warning now covers value INPUTs only."""
    t = Trace("q")
    t.input(ROOT, "g", "value", "local free-fall acceleration", value="9.8")
    for k in (1, 2):
        t.input(ROOT, f"m{k}", "value", f"inertial mass of B{k}", value=k + 2)
        t.unknown(ROOT, f"fG{k}", f"weight on B{k}", address=f"(i_G{k}, B{k}, t0)", ref="C-CM")
        t.input(ROOT, f"w{k}", "model", "uniform-field weight", relation=f"fG{k} = -m{k}*g")
        t.derive(ROOT, f"fG{k} = {-(k + 2) * G}", from_relations=[f"w{k}"], binds=f"fG{k}")
    t.answer(["fG1"])
    assert real_warnings(t.ledger()) == []


def test_r20_over_cited_relations_do_not_pull_in_premises():
    """regress-9: a derive keeps only the cited relations it needs."""
    t = Trace("q")
    t.unknown(ROOT, "x", "x", address="(x)", ref="C")
    t.input(ROOT, "r", "model", "r", relation="2*x = 6")
    t.input(ROOT, "paint", "recognition", "blocks are red")
    t.input(ROOT, "k", "value", "k", value=4)
    t.input(ROOT, "kr", "model", "irrelevant", relation="k = 4", uses=["paint"])
    st = t.derive(ROOT, "x = 3", from_relations=["r", "kr"], binds="x")
    t.answer(["x"])
    assert st.check == "checked" and "cited but not needed: kr" in st.detail
    led = t.ledger()
    assert names(led["commitments"]) == ["r"]
    assert {"paint", "k", "kr"} <= set(names(led["not_in_answer"]))
    # Atwood: citing a weight relation that the law step does not need
    a = atwood()
    st = a.derive(ROOT, "8*a1 = 98/5", from_relations=LAWS + ["w1"])
    assert "cited but not needed: w1" in st.detail
    assert a.bindings["w1"].step not in st.deps
    # a smallest subset is kept, and ties go to the relation cited first (probes-8 / review-v2-4, fixed)
    s = Trace("q")
    for n in "xy":
        s.unknown(ROOT, n, n, address=f"({n})", ref="C")
    s.input(ROOT, "rxy", "model", "the sum", relation="x + y = 5")
    s.input(ROOT, "ry", "model", "y is two", relation="y = 2")
    s.input(ROOT, "rx", "model", "x is three", relation="x = 3")
    s.input(ROOT, "rx2", "model", "twice x is six", relation="2*x = 6")
    for order, kept in ((["rx", "ry", "rxy"], "rx"), (["rxy", "ry", "rx"], "rx"),
                        (["rxy", "rx2", "rx"], "rx2"), (["rx", "rx2"], "rx")):
        assert s.derive(ROOT, "x = 3", from_relations=order).detail.startswith(f"follows from {kept} (")


def test_r20b_over_cited_relations_in_a_solve_do_not_pull_in_premises():
    """regress-3 / probes-9 / review-v2-3 (a gap test in v2, closed in v2.1):
    solve() keeps, for each value it fixes, a smallest set of relations that
    fixes it, and reports the relations no fixed value needs. In v2.2 the
    report step cites every relation but feeds no answer; each value's own
    DERIVE step carries its provenance."""
    t = Trace("q")
    t.unknown(ROOT, "x", "x", address="(x)", ref="C")
    t.input(ROOT, "r", "model", "r", relation="2*x = 6")
    t.input(ROOT, "paint", "recognition", "blocks are red")
    t.input(ROOT, "k", "value", "k", value=4)
    t.input(ROOT, "kr", "model", "irrelevant", relation="k = 4", uses=["paint"])
    st = t.solve(ROOT, ["r", "kr"], ["x"])
    t.answer(["x"])
    assert st.kind == "solve" and "relations not needed for the fixed values: kr" in st.detail
    led = t.ledger()
    assert names(led["commitments"]) == ["r"]
    assert {"paint", "k", "kr"} <= set(names(led["not_in_answer"]))
    assert st.index not in t.cone()
    # Atwood: a weight relation cited into the joint solve
    a = atwood()
    st = a.solve(ROOT, LAWS + ["w1"], UNKNOWNS)
    assert "relations not needed for the fixed values: w1" in st.detail
    for u in UNKNOWNS:
        assert a.bindings["w1"].step not in a.steps[a.value_step[u]].deps


def test_r20c_a_joint_solve_keeps_each_values_own_relations():
    """regress-3 / probes-9 (xfail in v2.1, fixed in v2.2)."""
    t, _ = joint_solve()
    t.answer(["x"])
    assert set(names(t.ledger()["commitments"])) == {"A", "r1"}


def test_r21_a_value_from_a_nonlinear_relation_is_refused():
    """regress-2 / review-code-2: x = 1000 'from' x*y = 6."""
    t = Trace("q")
    t.unknown(ROOT, "x", "x", address="(x)", ref="C")
    t.unknown(ROOT, "y", "y", address="(y)", ref="C")
    t.input(ROOT, "r", "model", "product", relation="x*y = 6")
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "x = 1000", from_relations=["r"], binds="x")
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "x = 1000*y", from_relations=["r"], name="r2")
    assert "x" not in t.values and "r2" not in t.bindings
    # a superfluous nonlinear citation no longer blocks a check the linear
    # citations settle (review-v2-21, fixed), is named as not checked (v2.2),
    # and is still refused when needed
    t.unknown(ROOT, "z", "z", address="(z)", ref="C")
    t.input(ROOT, "rz", "model", "z is three", relation="z = 3")
    st = t.derive(ROOT, "z = 3", from_relations=["r", "rz"], binds="z")
    assert st.check == "checked" and st.detail == "follows from rz (nonlinear citations not checked: r)"
    assert t.bindings["r"].step not in st.deps
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "x = 2", from_relations=["r", "rz"], binds="x")
    s = Trace("q", strict=False)
    s.unknown(ROOT, "x", "x", address="(x)", ref="C")
    s.unknown(ROOT, "y", "y", address="(y)", ref="C")
    s.input(ROOT, "r", "model", "product", relation="x*y = 6")
    st = s.derive(ROOT, "x = 1000", from_relations=["r"], binds="x")
    assert st.check == "unchecked" and "x not determined" in st.detail and "x" not in s.values
    # a determination that fails binds nothing (regress-10, fixed in v2.2)
    assert st.binds == ()
    s.input(ROOT, "rx", "model", "x is two", relation="x = 2")
    slip = s.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    assert slip.binds == () and "\u21d2" not in s.to_markdown().split(f"| {slip.id} |", 1)[1].split("\n")[0]


@pytest.mark.parametrize("route", ["solve", "derive"])
def test_r21b_an_answer_resting_on_an_unchecked_derive_is_warned(route):
    """regress-2 / probes-1 / review-v2-2 (xfail in v2, fixed in v2.1): an
    unchecked nonlinear DERIVE registered with name= still lets a later step
    determine x = 1000 from x*y = 6, but the answer's ledger now warns."""
    t = Trace("q", strict=False)
    t.unknown(ROOT, "x", "x", address="(x)", ref="C")
    t.unknown(ROOT, "y", "y", address="(y)", ref="C")
    t.input(ROOT, "r", "model", "product", relation="x*y = 6")
    bad = t.derive(ROOT, "x = 1000*y", from_relations=["r"], name="r2")
    t.input(ROOT, "r3", "model", "y", relation="y = 1")
    if route == "solve":
        t.solve(ROOT, ["r2", "r3"], ["x", "y"])
    else:
        t.derive(ROOT, "y = 1", from_relations=["r3"], binds="y")
        t.derive(ROOT, "x = 1000", from_relations=["r2"], binds="x")
    t.answer(["x"])
    assert bad.check == "unchecked" and bad.index in t.cone() and t.values["x"] == 1000
    led = t.ledger()
    assert f"the answer rests on {bad.id}, which could not be checked" in led["warnings"]
    assert [u["step"] for u in led["unchecked"]] == [bad.id]
    assert [m["from"] for m in t.hypothesis_set() if m.get("check") == "unchecked"] == [bad.id]


def test_r22_a_check_that_holds_identically_is_not_reported_as_following():
    """enc-spring1-5 / enc-atwood-14: a value lock restated after the values
    exist is 2 = 2; it must not read 'follows from' the cited relation."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    t.unknown(ROOT, "f", "spring force", address="f(i_s, A)", ref="C-D")
    t.input(ROOT, "r1", "model", "spring", relation="f = 2")
    t.input(ROOT, "r2", "model", "E8 relation", relation="a = f/m")
    t.derive(ROOT, "f = 2", from_relations=["r1"], binds="f")
    t.derive(ROOT, "a = 1", from_relations=["r2"], binds="a")
    t.input(ROOT, "junk", "model", "unrelated", relation="a + f = 3")
    lock = t.derive(ROOT, "f = m*a", from_relations=["junk"], tag="value lock")
    assert lock.check == "checked"
    assert "no independent content" in lock.detail and "follows from" not in lock.detail
    assert t.bindings["junk"].step not in lock.deps


def test_r23_an_address_declaration_is_not_a_world_commitment():
    """enc-atwood-1 / enc-spring1-2 / regress-13a: unknown(label='INPUT')."""
    t = Trace("q")
    t.input(ROOT, "qn", "normalization", "the question asks for a(A)")
    with pytest.raises(TraceError, match="CONTRACT, ENTRY or READING"):
        t.unknown(ROOT, "a", "acceleration", address="a(A)", label="INPUT", uses=["qn"])
    with pytest.raises(TraceError, match="quote"):
        t.unknown(ROOT, "a", "acceleration", address="a(A)", label="ENTRY", ref="E8")
    # only an ENTRY carries a quote: under CONTRACT or READING an unverified
    # quote would look verified (review-v2-9, fixed)
    for label in ("CONTRACT", "READING"):
        with pytest.raises(TraceError, match="only an unknown introduced by ENTRY"):
            t.unknown(ROOT, "a", "acceleration", address="a(A)", label=label, ref="E8", quote=E8)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", label="READING", uses=["qn"])
    t.input(ROOT, "r", "model", "r", relation="a = 1")
    t.derive(ROOT, "a = 1", from_relations=["r"], binds="a")
    t.answer(["a"])
    # provisional (10 November 2026): the normalization qn is pruned by kind, like a convention
    assert set(names(t.ledger()["commitments"])) == {"r"} and set(names(t.ledger()["pruned"])) == {"qn"}
    assert not any("unknown a" in m["member"] for m in t.hypothesis_set())


def test_r24_a_misquoted_entry_is_refused_when_entries_are_supplied():
    """regress-14d / enc-spring1-11 / enc-atwood-15."""
    t = Trace("q", entries=ENTRIES)
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E8", "net force times mass, probably")
    with pytest.raises(TraceError, match="not in the supplied entries"):
        t.entry(ROOT, "E9", E8)
    with pytest.raises(TraceError, match="verbatim"):
        t.unknown(ROOT, "a", "acceleration", address="a(A)", label="ENTRY", ref="E8", quote="net force times mass")
    # a quote is at least two whole words, matched at word boundaries
    # (probes-11 / spring1-1 / review-v2-8, fixed); ':=' is not a word (v2.2)
    for fragment in ("ass", "a", "material-object", "inertial-acceleration-material-object :=", ":= For"):
        with pytest.raises(TraceError, match="two whole words"):
            t.entry(ROOT, "E8", fragment)
    for fragment in ("rce-material-object divided by", "or one material-object", "without being a free"):
        with pytest.raises(TraceError, match="verbatim"):
            t.entry(ROOT, "E8", fragment)
    t.entry(ROOT, "E8", E8.replace(" ", "\n   ", 3))  # whitespace is normalised
    t.unknown(ROOT, "a", "acceleration", address="a(A)", label="ENTRY", ref="E8", quote=E8)
    # a quoted demand is verified, and linked to the latest ENTRY with its ref (spring1-3)
    with pytest.raises(TraceError, match="verbatim"):
        t.demand(ROOT, "DA", "the acceleration of A", ref="E8", quote="net force times mass")
    with pytest.raises(TraceError, match="needs the entry ref"):
        t.demand(ROOT, "DA", "the acceleration of A", quote=E8)
    latest = [s for s in t.steps if s.op == "ENTRY" and s.ref == "E8"][-1]
    t.demand(ROOT, "DA", "the acceleration of A", ref="E8", quote="divided by its inertial-mass-material-object")
    assert t.steps[-1].op == "DEMAND" and t.steps[-1].deps == (latest.index,)
    # an empty mapping no longer turns checking off silently (review-v2-7, fixed)
    with pytest.raises(TraceError, match="empty"):
        Trace("q", entries={})
    # without entries (entries=None) a quote is not checked (unchanged)
    assert Trace("q").entry(ROOT, "E8", "net force times mass, probably").op == "ENTRY"


@needs_entries_file
def test_r24b_quotes_check_against_the_design_2_1_entries_file():
    entries = load_entries(str(ENTRIES_FILE))
    assert entries["E8"] == ENTRIES["E8"]
    t = Trace("q", entries=entries)
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E8", "net force times mass, probably")
    t.entry(ROOT, "E8", E8)
    # the source's combined heading is accepted as a ref (review-v2-18, fixed)
    assert t.entry(ROOT, "K16 / E1", "A frame-indexed interval property of a point-particle").op == "ENTRY"


def test_r24c_every_part_of_a_combined_ref_must_be_a_supplied_entry():
    """regress-4 (xfail in v2.1, fixed in v2.2)."""
    t = Trace("q", entries=ENTRIES)
    with pytest.raises(TraceError, match=r"not in the supplied entries \(E99\)"):
        t.entry(ROOT, "E8 / E99", E8)
    with pytest.raises(TraceError, match="E99"):
        t.unknown(ROOT, "a", "acceleration", address="a(A)", label="ENTRY", ref="E8 / E99", quote=E8)
    with pytest.raises(TraceError, match="E99"):
        t.demand(ROOT, "DA", "the acceleration of A", ref="E8 / E99", quote=E8)
    assert t.steps == []


def test_r25_conventions_choices_and_pruned_premises_are_not_members():
    """enc-atwood-2 / enc-spring2-5: a negated axis convention or a USES
    premise cannot refute p, so neither is a member of H."""
    t = Trace("q")
    t.input(ROOT, "axis", "convention", "one upward axis")
    t.input(ROOT, "sys", "choice", "the system is block 1")
    t.input(ROOT, "rigid", "recognition/choice", "B1 is a rigid block, chosen as the system")
    t.input(ROOT, "same", "identity", "the same block throughout")
    t.input(ROOT, "fmt", "model", "quote to three figures")
    t.unknown(ROOT, "x", "x", address="(x)", ref="C")
    t.input(ROOT, "r", "model", "r", relation="x = 2", uses=["axis", "sys", "rigid", "same", "fmt"])
    t.solve(ROOT, ["r"], ["x"])
    t.answer(["x"])
    t.annotate("same", "ENTAILED", note="by rigid")
    t.annotate("fmt", "USES")
    led = t.ledger()
    assert set(names(led["pruned"])) == {"axis", "sys", "same", "fmt"}
    assert names(led["commitments"]) == ["rigid", "r"]
    members = " ".join(m["member"] for m in t.hypothesis_set())
    assert "upward axis" not in members and "three figures" not in members and "rigid block" in members
    assert led["warnings"] == ["2 commitment(s) have no status yet: rigid, r"]
    # a NEEDS status on a non-world premise is warned when its kind prunes it (probes-14, fixed)
    t.annotate("axis", "NEEDS", countermodel="a downward axis flips the sign of x")
    assert ("axis is marked NEEDS but its kind convention is not a claim about the world, so it is not a "
            "member") in t.ledger()["warnings"]
    # need is relative to a prediction: a status given for one answer prunes
    # nothing from another (atwood-1 / probes-10 / review-v2-5, fixed)
    t.unknown(ROOT, "y", "y", address="(y)", ref="C")
    t.input(ROOT, "ry", "model", "ry", relation="y = 3*x")
    t.solve(ROOT, ["ry"], ["y"])
    t.answer(["y"], label="q2")
    t.annotate("rigid", "USES", answer="p1", note="for p1 only")
    t.annotate("ry", "NEEDS", countermodel="y = 2*x gives y = 4", answer="q2")
    assert "rigid" in names(t.ledger("p1")["pruned"])
    assert "rigid" in names(t.ledger("q2")["commitments"])
    assert not any(w.startswith("ry is marked") for w in t.ledger("p1")["warnings"])
    # v2.2: a default status warns only if the premise feeds no answer; a
    # per-answer status warns in its own answer (V21R-11, fixed)
    t.annotate("ry", "REQUIRED")
    assert not any(w.startswith("ry is marked") for w in t.ledger("p1")["warnings"])
    t.annotate("ry", "REQUIRED", answer="p1")
    assert "ry is marked REQUIRED but does not feed this answer" in t.ledger("p1")["warnings"]
    assert not any(w.startswith("ry is marked") for w in t.ledger("q2")["warnings"])


def test_r26_a_withdrawn_premise_taints_what_rests_on_it():
    """enc-spring2-1 / spring2-1 / regress-6: a premise is withdrawn after a
    conflict. v2.1 refused every name whose provenance included it. v2.2
    taints by value: the premise, and any binding whose own step rests on it
    (r), are refused; a value that rests on it (a, v) is visible nowhere, but
    the name stays usable. Earlier steps and answers stay as history. v2.3: a
    restatement whose verdict a withdrawn value would change is refused, in
    strict and lenient mode, until that value is determined again; v2.2 filed
    it as a found mistake ('not an identity')."""
    t = spring_account(Trace("q"))
    t.unknown(ROOT, "v", "velocity gained in one second", address="dv(A, 1 s)", ref="C")
    t.input(ROOT, "rv", "model", "uniform acceleration for one second", relation="v = a")
    t.derive(ROOT, "v = 1", from_relations=["rv"], binds="v")
    t.answer(["a"], label="q1")
    w = t.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    d = t.demand(ROOT, "D", "a diagnostic frame")
    before = (len(t.steps), len(t.commands))
    refused = [
        lambda: t.reading(ROOT, "still complete", uses=["complete"]),
        lambda: t.reading(ROOT, "the spring-only account", uses=["r"]),
        lambda: t.derive(ROOT, "a = 1", from_relations=["r"]),
        lambda: t.input(ROOT, "r9", "model", "built on the account", relation="m*a = 2", uses=["r"]),
        lambda: t.deliver(d, "complete"),
        lambda: t.deliver(d, "r"),
        lambda: t.deliver_many(d, ["m", "r"]),
        lambda: t.deliver_through(d, "complete"),
    ]
    for call in refused:
        with pytest.raises(TraceError, match="withdrawn") as exc:
            call()
        assert not isinstance(exc.value, CheckError)
    # an answer on a tainted value names the withdrawn premise
    for q in ("a", "v"):  # v is two steps from the premise
        with pytest.raises(TraceError, match=f"value of '{q}' rests on 'complete'.*determine it again"):
            t.answer([q], label="q2")
    assert (len(t.steps), len(t.commands)) == before
    # v2.3: the tainted values are gone, and a restatement that needs one of them is refused until it is
    # determined again; it is not a CheckError and records nothing
    assert t.known_values(ROOT) == {"m": 2}
    for claim, q in (("2*a = 2", "a"), ("v = 1", "v")):
        with pytest.raises(TraceError, match=re.escape(
                f"the step needs the value of {q} (rests on complete), which rests on a withdrawn premise; "
                "determine it again first")) as exc:
            t.derive(ROOT, claim)
        assert not isinstance(exc.value, CheckError)
    # a claim the withdrawn value would not rescue is still the found mistake it is
    with pytest.raises(CheckError, match="mistake: not an identity"):
        t.derive(ROOT, "2*a = 3")
    assert (len(t.steps), len(t.commands)) == before
    # what does not rest on it stays usable, and the names travel without their values
    assert t.deliver(d, "m").op == "DELIVER"
    dl = t.deliver(d, "a")
    assert dl.text.startswith("a, delivered") and t.value_visible(d, "a") is None
    assert [s.frame for s in t.deliver_through(d, "v")] == [d]
    with pytest.raises(TraceError, match="INPUT"):
        t.withdraw(ROOT, "a", "not a premise")
    with pytest.raises(TraceError, match="already withdrawn"):
        t.withdraw(ROOT, "complete", "again")
    # a premise that rests on a withdrawn one can be withdrawn itself (v2.2)
    wr = t.withdraw(ROOT, "r", "the account it states is gone")
    led = t.ledger("q1")
    assert not real_warnings(led)  # q1 was recorded before both withdrawals
    assert [(c["name"], c["withdrawn_at"]) for c in led["withdrawn"]] == [("complete", w.id), ("r", wr.id)]
    assert led["answer"] == "a = 1"
    # v2.3: the restatement is refused in lenient mode too, where v2.2 recorded a found mistake
    lt = spring_account(Trace("q", strict=False))
    lt.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    n = len(lt.steps)
    with pytest.raises(TraceError, match=re.escape(
            "the step needs the value of a (rests on complete), which rests on a withdrawn premise; "
            "determine it again first")):
        lt.derive(ROOT, "2*a = 2")
    assert len(lt.steps) == n


def test_r26b_re_supplying_a_withdrawn_premise_is_named_as_such():
    """probes-5 / review-v2-22: v2 advised 'deliver the original', which
    withdrawal forbids. v2.1 names the withdrawal instead."""
    t = spring_account(Trace("q"))
    w = t.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    t.input(ROOT, "complete2", "completeness", "the spring is the only interaction on A")
    t.unknown(ROOT, "b", "acceleration, second account", address="a(A) | second account", ref="E8")
    t.input(ROOT, "rb", "model", "spring-only account, restated", relation="m*b = 2", uses=["complete2"])
    t.derive(ROOT, "b = 1", from_relations=["rb"], binds="b")
    t.answer(["b"])
    led = t.ledger()
    assert (f"complete2 repeats complete word for word; complete was withdrawn at {w.id}, and complete2 was "
            "not withdrawn with it") in led["warnings"]
    assert not any("deliver the original" in x for x in led["warnings"])
    assert "complete2" in names(led["commitments"])


def test_r26c_a_copy_made_before_the_withdrawal_is_flagged_too():
    """regress-5 (xfail in v2.1, fixed in v2.2)."""
    t = Trace("q")
    t.input(ROOT, "complete", "completeness", "the spring is the only interaction on A")
    t.input(ROOT, "complete2", "completeness", "the spring is the only interaction on A")
    t.input(ROOT, "m", "value", "mass of A", value=2)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    t.input(ROOT, "r", "model", "spring-only account", relation="m*a = 2", uses=["complete2"])
    w = t.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    t.derive(ROOT, "a = 1", from_relations=["r"], binds="a")
    t.answer(["a"])
    warnings = t.ledger()["warnings"]
    assert not any("deliver the original" in x for x in warnings)
    assert (f"complete2 repeats complete word for word; complete has since been withdrawn at {w.id}, and "
            "complete2 was not withdrawn with it") in warnings


def test_r26d_withdrawal_taints_only_the_values_that_rest_on_the_premise():
    """regress-3 (xfail in v2.1, fixed in v2.2 with per-value solve provenance)."""
    t, _ = joint_solve()
    t.withdraw(ROOT, "B", "the premise behind y is dropped")
    t.answer(["x"])
    assert set(names(t.ledger()["commitments"])) == {"A", "r1"}
    with pytest.raises(TraceError, match="value of 'y' rests on 'B'"):
        t.answer(["y"])


# -- R27-R33: v2.2 mechanisms ---------------------------------------------------------


def test_r27_a_quantity_whose_value_was_withdrawn_can_be_determined_again():
    """probes-11 (a gap test in v2.1, closed in v2.2): a quantity fixed from a
    withdrawn premise was dead. Now derive(binds=) or solve() may determine
    it again, a new relation may mention it, and the new value is the one an
    answer uses."""
    t = spring_account(Trace("q"))
    t.answer(["a"], label="q1")
    t.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    t.input(ROOT, "both", "completeness", "the spring and B's pull are A's only interactions")
    t.input(ROOT, "r2", "model", "two-interaction account", relation="m*a = 4", uses=["both"])
    again = t.derive(ROOT, "a = 2", from_relations=["r2"], binds="a")
    assert again.binds == ("a",) and t.value_step["a"] == again.index and t.values["a"] == 2
    with pytest.raises(TraceError, match="already has a value"):
        t.derive(ROOT, "a = 2", from_relations=["r2"], binds="a")
    assert t.derive(ROOT, "2*a = 4").check == "checked"
    t.answer(["a"], label="q2")
    led = t.ledger("q2")
    assert names(led["commitments"]) == ["m", "both", "r2"] and not real_warnings(led)
    assert t.ledger("q1")["answer"] == "a = 1" and t.ledger("q2")["answer"] == "a = 2"
    assert len(Trace.replay(json.loads(t.to_json())).steps) == len(t.steps)
    # by solve: withdrawing y's premise leaves x, and y alone is solved again
    s, _ = joint_solve()
    s.withdraw(ROOT, "B", "the premise behind y is dropped")
    s.input(ROOT, "B2", "recognition", "a new premise behind y")
    s.input(ROOT, "r3", "model", "y is five", relation="y = 5", uses=["B2"])
    with pytest.raises(TraceError, match="'x' already has a value"):
        s.solve(ROOT, ["r1", "r3"], ["x", "y"])
    assert s.solve(ROOT, ["r3"], ["y"]).detail == "unique: y = 5"
    s.answer(["x", "y"])
    assert set(names(s.ledger()["commitments"])) == {"A", "r1", "B2", "r3"}


@pytest.mark.parametrize("law_first", [True, False])
def test_r27b_withdrawing_a_world_premise_leaves_the_sum_law_usable(law_first):
    """law_first=False was xfail in v2.2, fixed in v2.3: a relation recorded,
    as deps, the value steps of the names it mentions, so law1 written after
    the weight step rested on peqv1 and was refused once peqv1 was withdrawn.
    A relation now rests only on the binding steps of its names, so the
    order of recording no longer matters."""
    t = Trace("Atwood regression", entries=ENTRIES)
    block(t, 1, 3, g="supply", law_first=law_first)
    t.withdraw("D1", "peqv1", "the gravitational mass of B1 is in doubt")
    assert t.value_visible("D1", "fG1") is None  # the weight's value rests on peqv1
    assert t.reading("D1", "the sum law still applies to B1", uses=["law1"]).op == "READING"


def test_r27c_a_restated_premise_is_not_told_to_deliver_a_tainted_original():
    """xfail in v2.2, fixed in v2.3: the re-supply warning checked only whether
    the original INPUT was itself withdrawn. r rests on the withdrawn complete,
    so deliver(r) is refused, yet r2 (r restated on a new premise) was told to
    deliver the original. It is now told why r cannot be delivered."""
    t = spring_account(Trace("q"))
    t.withdraw(ROOT, "complete", "B pulls on A too")
    with pytest.raises(TraceError, match="rests on 'complete'"):
        t.deliver(t.demand(ROOT, "D", "a diagnostic frame"), "r")
    t.input(ROOT, "complete2", "completeness", "the spring and nothing else acts on A, rechecked")
    t.input(ROOT, "r2", "model", "spring-only account", relation="m*a = 2", uses=["complete2"])
    t.derive(ROOT, "a = 1", from_relations=["r2"], binds="a")
    t.answer(["a"])
    warnings = real_warnings(t.ledger())
    assert not any("deliver the original" in x for x in warnings)
    assert "r2 repeats r word for word; r rests on complete, which was withdrawn, so it cannot be delivered" \
        in warnings


def test_r27d_determining_a_value_again_does_not_rewrite_an_earlier_answers_ledger():
    """xfail in v2.2, fixed in v2.3: v2.2 kept only the latest value of a
    quantity, so determining x = 5 (fixed before answer p1, withdrawn after
    it) again as x = 7 made p1's conflict on r: x = 7 disappear. The global
    check now reads a per-name value history as of the answer."""
    t = Trace("q")
    for n in "xz":
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    t.input(ROOT, "r", "model", "x is seven", relation="x = 7")
    t.input(ROOT, "P", "recognition", "the premise behind x = 5")
    t.input(ROOT, "rx", "model", "x is five", relation="x = 5", uses=["P"])
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(ROOT, "rz", "model", "z is two", relation="z = 2", uses=["r"])
    t.derive(ROOT, "z = 2", from_relations=["rz"], binds="z")
    t.answer(["z"], label="p1")
    assert conflict_refs(t, "p1") == ["r"]
    t.withdraw(ROOT, "P", "x = 5 rested on a misreading")
    assert conflict_refs(t, "p1") == ["r"]  # the value was fixed before p1 and withdrawn after it
    t.input(ROOT, "Q", "recognition", "the premise behind x = 7")
    t.input(ROOT, "rx2", "model", "x is seven, measured", relation="x = 7", uses=["Q"])
    t.derive(ROOT, "x = 7", from_relations=["rx2"], binds="x")
    assert conflict_refs(t, "p1") == ["r"]


def test_r27e_a_quantity_whose_value_was_withdrawn_is_listed_as_undetermined():
    """probes-11 remainder (a test_note_* friction in v2.2, closed in v2.3):
    v2.2 read 'undetermined' from self.values, which keeps the tainted value,
    so nothing in the ledger said that a must be determined again. v2.3: the
    ledger lists a as undetermined, with a note naming the withdrawn premise."""
    t = spring_account(Trace("q"))
    t.withdraw(ROOT, "complete", "B's trajectory contradicts the spring-only account")
    t.answer(["m"])
    led = t.ledger()
    assert t.value_visible(ROOT, "a") is None
    assert led["undetermined"] == [{"name": "a", "address": "a(A)", "step": t.steps[2].id,
                                    "note": "its value was withdrawn: it rested on complete"}]
    assert names(led["withdrawn"]) == ["complete"]


def test_r28_a_claim_or_relation_that_cannot_be_evaluated_is_a_mistake_or_conflict():
    """V21R-4 (a v2.1 crash, fixed in v2.2): division by zero after substitution
    is a found mistake in a claim and a conflict in a cited relation. The
    ledger's global check reports it as a conflict row instead of crashing."""
    t = Trace("q", strict=False)
    t.input(ROOT, "m", "value", "mass", value=0)
    t.input(ROOT, "F", "value", "force", value=2)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    t.input(ROOT, "law", "model", "E8 relation", relation="a = F/m")
    claim = t.derive(ROOT, "a = 1/m")
    assert claim.check == "failed" and claim.detail.startswith("mistake: the claim cannot be evaluated")
    rel = t.derive(ROOT, "a = 2", from_relations=["law"], binds="a")
    assert rel.check == "failed" and rel.detail.startswith("conflict: relation law cannot be evaluated")
    assert rel.binds == () and "a" not in t.values
    assert t.consistency(ROOT, ["law"]).check == "failed"
    s = Trace("q")
    s.input(ROOT, "m", "value", "mass", value=0)
    s.input(ROOT, "F", "value", "force", value=2)
    s.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    s.input(ROOT, "law", "model", "E8 relation", relation="a = F/m")
    with pytest.raises(CheckError, match="cannot be evaluated"):
        s.derive(ROOT, "a = 2", from_relations=["law"])
    # an answer that rests on the relation through uses=
    s.unknown(ROOT, "x", "x", address="(x)", ref="C")
    s.input(ROOT, "rx", "model", "x is one", relation="x = 1", uses=["law"])
    s.derive(ROOT, "x = 1", from_relations=["rx"], binds="x")
    s.answer(["x"])
    led = s.ledger()
    assert [(c["ref"], c["detail"].split(" (")[0]) for c in led["conflicts"]] == [
        ("law", "conflict: law cannot be evaluated with the values determined in this trace")]
    assert "the answer rests on law, which the trace's own values make undefined" in led["warnings"]
    assert "cannot be evaluated" in section(s.to_markdown(), "Conflicts")
    assert len(Trace.replay(json.loads(s.to_json())).steps) == len(s.steps)


def test_r29_the_global_check_reads_the_trace_as_of_the_answer():
    """probes-5, probes-6, probes-9, probes-16 / V21R-12 (v2.1 gaps and bugs,
    closed in v2.2). v2.3: the joint check names a minimal inconsistent
    subset, found by a deletion filter in citation order (r3, r4), where
    v2.2 named every open relation (r1, r3, r2, r4)."""
    # values fixed after the answer do not add conflicts to it
    t = Trace("q")
    for n in "xy":
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    t.input(ROOT, "r1", "model", "the sum", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "the difference", relation="x - y = 1")
    t.derive(ROOT, "x = 3", from_relations=["r1", "r2"], binds="x")
    t.answer(["x"], label="p1")
    t.input(ROOT, "ry", "model", "y is three", relation="y = 3")
    t.derive(ROOT, "y = 3", from_relations=["ry"], binds="y")
    t.answer(["x", "y"], label="p2")
    assert conflict_refs(t, "p1") == [] and conflict_refs(t, "p2") == ["r1", "r2"]
    # a value resting on a premise withdrawn before the answer does not count
    u = Trace("q")
    for n in "xz":
        u.unknown(ROOT, n, n, address=f"({n})", ref="C")
    u.input(ROOT, "r", "model", "x is five", relation="x = 5")
    u.input(ROOT, "rx", "model", "x is three", relation="x = 3")
    u.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    u.withdraw(ROOT, "rx", "x = 3 was misread")
    u.input(ROOT, "rz", "model", "z is two", relation="z = 2", uses=["r"])
    u.derive(ROOT, "z = 2", from_relations=["rz"], binds="z")
    u.answer(["z"])
    assert conflict_refs(u) == [] and not real_warnings(u.ledger())
    # a relation withdrawn after the answer was asserted when it was made
    v = Trace("q")
    for n in "xz":
        v.unknown(ROOT, n, n, address=f"({n})", ref="C")
    v.input(ROOT, "r", "model", "x is seven", relation="x = 7")
    v.input(ROOT, "rx", "model", "x is five", relation="x = 5")
    v.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    v.input(ROOT, "rz", "model", "z is two", relation="z = 2", uses=["r"])
    v.derive(ROOT, "z = 2", from_relations=["rz"], binds="z")
    v.answer(["z"], label="p1")
    v.withdraw(ROOT, "r", "contradicted")
    assert conflict_refs(v, "p1") == ["r"]
    # premises that are jointly inconsistent, with no single relation contradicted
    j = Trace("q")
    for n in "xyz":
        j.unknown(ROOT, n, n, address=f"({n})", ref="C")
    j.input(ROOT, "r1", "model", "the sum", relation="x + y = 5")
    j.input(ROOT, "r3", "model", "the difference", relation="x - y = 1")
    j.derive(ROOT, "x = 3", from_relations=["r1", "r3"], binds="x")
    j.input(ROOT, "r2", "model", "y is three", relation="y = 3")
    j.input(ROOT, "r4", "model", "z is twice y", relation="z = 2*y")
    j.derive(ROOT, "z = 6", from_relations=["r2", "r4"], binds="z")
    j.answer(["x", "z"])
    led = j.ledger()
    # v2.3: only the minimal subset r3 (y = 2 given x = 3) and r4 (y = 3 given z = 6) is named
    assert [c["ref"] for c in led["conflicts"]] == ["r3, r4"]
    assert led["conflicts"][0]["detail"] == ("conflict: the relations r3, r4, which this answer rests on, are "
                                             "jointly inconsistent with the values determined in this trace")
    assert "the answer rests on relations that are jointly inconsistent: r3, r4" in led["warnings"]
    assert j.consistency(ROOT, ["r1", "r3", "r2"]).check == "failed"  # the explicit check agrees


def test_r30_a_joint_solve_records_one_checked_derive_per_fixed_value():
    """regress-3 (fixed in v2.2): one EXTERNAL report step, then one DERIVE
    'x = value' per fixed unknown with a smallest relation set of its own.
    value_step points to that DERIVE; the report step feeds no answer. v2.3:
    the report step still binds the fixed names, but once one of its DERIVE
    steps feeds the answer it is no longer listed in outside_answer."""
    t = Trace("q")
    for n in "xy":
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    t.input(ROOT, "A", "recognition", "the premise behind the sum")
    t.input(ROOT, "B", "recognition", "the premise behind y")
    t.input(ROOT, "r1", "model", "the sum", relation="x + y = 7", uses=["A"])
    t.input(ROOT, "r2", "model", "y is four", relation="y = 4", uses=["B"])
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y"], tag="solve")
    assert (st.op, st.kind, st.detail, st.binds) == ("EXTERNAL", "solve", "unique: x = 3, y = 4", ("x", "y"))
    vx, vy = t.steps[st.index + 1:]
    assert [(s.op, s.claim, s.check, s.detail, s.tag) for s in (vx, vy)] == [
        ("DERIVE", "x = 3", "checked", "follows from r1, r2", "solve"),
        ("DERIVE", "y = 4", "checked", "follows from r2", "solve")]
    assert (t.value_step["x"], t.value_step["y"]) == (vx.index, vy.index)
    assert st.id in vx.text and st.id in vy.text
    t.answer(["y"], label="py")
    t.answer(["x"], label="px")
    assert set(names(t.ledger("py")["commitments"])) == {"B", "r2"}
    assert set(names(t.ledger("px")["commitments"])) == {"A", "B", "r1", "r2"}  # x needs both relations
    assert [s["step"] for s in t.ledger("px")["step_members"]] == [vx.id]
    # v2.3: the report step is in neither the cone nor outside_answer; only y's DERIVE is outside px
    assert [r["step"] for r in t.ledger("px")["outside_answer"]] == [vy.id]
    assert t.hypothesis_set("px")[-1]["member"] == f"step {vx.id} went wrong: x = 3"
    assert len(Trace.replay(json.loads(t.to_json())).steps) == len(t.steps)
    # a family records a DERIVE only for the values it fixes anyway
    f = Trace("q")
    for n in "xyz":
        f.unknown(ROOT, n, n, address=f"({n})", ref="C")
    f.input(ROOT, "r1", "model", "x is three", relation="x = 3")
    f.input(ROOT, "r2", "model", "y plus z", relation="y + z = 4")
    fs = f.solve(ROOT, ["r1", "r2"], ["x", "y", "z"])
    assert fs.detail.startswith("underdetermined") and "relations not needed for the fixed values: r2" in fs.detail
    assert [(s.op, s.claim) for s in f.steps[fs.index + 1:]] == [("DERIVE", "x = 3")]


@needs_entries_file
def test_r31_quotes_against_the_design_2_1_entries_file():
    """regress-4 and regress-8 / probes-12 (v2.1, fixed in v2.2): every part of
    a combined ref must be a supplied entry holding the quote; ':=' is not a
    word; word boundaries are Unicode-aware (K4 has 'r0 + λu, with r0
    fixed')."""
    t = Trace("q", entries=load_entries(str(ENTRIES_FILE)))
    with pytest.raises(TraceError, match=r"not in the supplied entries \(E99\)"):
        t.entry(ROOT, "E8 / E99", E8)
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "E8 / E9", "divided by its inertial-mass-material-object")  # E8 only
    with pytest.raises(TraceError, match="not verbatim"):
        t.demand(ROOT, "DA", "a(A)", ref="E8 / E9", quote="divided by its inertial-mass-material-object")
    assert t.entry(ROOT, "E9 / E8", "For one material-object, its").op == "ENTRY"  # both entries say it
    assert t.entry(ROOT, "K16 / E1", "A frame-indexed interval property").op == "ENTRY"
    for bare in ("inertial-acceleration-material-object :=", ":= For"):
        for ref in ("E7", "E8", "E7 / E8"):
            with pytest.raises(TraceError, match="two whole words"):
                t.entry(ROOT, ref, bare)
    for inside in ("u, with", "r0 + \u03bb"):  # 'u' follows λ; 'λ' is followed by 'u'
        with pytest.raises(TraceError, match="not verbatim"):
            t.entry(ROOT, "K4", inside)
    assert t.entry(ROOT, "K4", "\u03bbu, with r0").op == "ENTRY"
    assert t.entry(ROOT, "K4", "+ \u03bbu, with").op == "ENTRY"


def test_r32_a_dense_solve_is_fast_and_minimal_citation_is_exhaustive_up_to_eight():
    """The v2.1 exhaustive search made a dense 10x10 solve take 12.6 s; v2.2
    is exhaustive up to 8 relations and greedy beyond (test_gap_* below)."""
    rnd = random.Random(1)
    t = Trace("q")
    xs = [f"x{i}" for i in range(10)]
    for x in xs:
        t.unknown(ROOT, x, x, address=f"({x})", ref="C")
    for i in range(10):
        terms = " + ".join(f"{rnd.randint(1, 9)}*{x}" for x in xs)
        t.input(ROOT, f"r{i}", "model", f"dense relation {i}", relation=f"{terms} = {rnd.randint(1, 50)}")
    start = time.perf_counter()
    st = t.solve(ROOT, [f"r{i}" for i in range(10)], xs)
    assert time.perf_counter() - start < 6
    assert st.detail.startswith("unique") and len(t.steps) == 21 + 10
    assert minimal_citation(5) == (8, "follows from rx")  # exhaustive: the smallest set


def minimal_citation(junk):
    """x = 3 cited from [rxy, ry, junk..., rx]; rx alone suffices, rxy + ry too."""
    t = Trace("q")
    for n in ["x", "y"] + [f"j{i}" for i in range(junk)]:
        t.unknown(ROOT, n, n, address=f"({n})", ref="C")
    t.input(ROOT, "rxy", "model", "the sum", relation="x + y = 5")
    t.input(ROOT, "ry", "model", "y is two", relation="y = 2")
    rels = ["rxy", "ry"]
    for i in range(junk):
        t.input(ROOT, f"k{i}", "model", f"unrelated {i}", relation=f"j{i} = {i}")
        rels.append(f"k{i}")
    t.input(ROOT, "rx", "model", "x is three", relation="x = 3")
    rels.append("rx")
    return len(rels), t.derive(ROOT, "x = 3", from_relations=rels).detail.split(" (")[0]


# -- Known gaps v2.2 leaves open --------------------------------------------------------
#
# Out of reach by design and not tested: physics and sign conventions (fG2 =
# +m2*g on an upward axis is accepted; R17 shows the one partial catch);
# merging two encounters into one unknown (the address rule fires only when
# two unknowns are declared); conditional branches; the observation side of a
# trial; the C3 approximation budget; editions; explicit RETURN (results flow
# up to every caller unconditionally). Units and a minimum-size citation
# search beyond 8 relations are pinned below.


def test_gap_a_substitution_laundered_as_an_input():
    """regress-6 / regress-4 (v2): the substituted law supplied as a model INPUT
    instead of derived; its real sources leave the hypothesis set without a
    warning."""
    t = atwood()
    t.input(ROOT, "law1s", "model", "block 1 law, substituted", relation="3*a1 = -147/5 + T1")
    t.input(ROOT, "law2s", "model", "block 2 law, substituted", relation="5*a2 = -49 + T2")
    t.solve(ROOT, ["law1s", "law2s", "meq", "kin"], UNKNOWNS)
    t.answer(["a1"])
    led = t.ledger()
    assert {"m1", "g", "w1", "m2", "w2"} <= set(names(led["not_in_answer"]))
    assert not real_warnings(led)


def test_gap_hidden_lookup_in_prose():
    """regress-7: only relations and uses= are checked for visibility."""
    t = Trace("q")
    t.demand(ROOT, "D1", "block 1")
    t.demand(ROOT, "D2", "block 2")
    t.input("D1", "g", "value", "local g", value="9.8")
    assert t.reading("D2", "the weight of B2 is m2 times g from block 1").op == "READING"


def test_gap_units_are_not_checked():
    """regress-11: units are carried as text (a spec non-goal)."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3, unit="kg")
    t.input(ROOT, "g", "value", "g", value="9.8", unit="m/s^2")
    assert t.derive(ROOT, "m + g = 3 + 9.8").check == "checked"


def test_gap_countermodels_are_not_checked():
    """regress-14e / enc-atwood-15: any non-empty countermodel is accepted,
    even one in which p still holds (countermodels are recorded, not checked)."""
    t = finished()
    t.annotate("m1", "NEEDS", countermodel="TODO")
    t.annotate("m2", "NEEDS", countermodel="m2 = 5 kg gives a1 = 49/20")
    assert t.ledger()["commitments"][0]["countermodel"] == "TODO"


def test_gap_short_quotes_still_verify():
    """probes-11 / spring1-1 / review-v2-8 / regress-8: v2.2 refuses one-word
    and mid-word quotes and no longer counts ':=' (R24, R31), but any two
    whole words of the entry verify, including a content-free fragment, and
    the shared headword line plus one word verifies under every entry that
    opens with it. A verified quote shows the words are in the entry, not
    that the tracer quoted the clause being applied."""
    t = Trace("q", entries=ENTRIES)
    assert t.entry(ROOT, "E8", "divided by").op == "ENTRY"
    assert t.entry(ROOT, "E8", "inertial-acceleration-material-object := For").op == "ENTRY"
    if ENTRIES_FILE.exists():
        f = Trace("q", entries=load_entries(str(ENTRIES_FILE)))
        assert f.entry(ROOT, "E7 / E8", "inertial-acceleration-material-object := For").op == "ENTRY"


def test_gap_minimal_citation_beyond_eight_relations_is_greedy():
    """probes-17 (deliberately open): beyond 8 cited relations needed_relations
    drops relations from the end of the list, so one more irrelevant citation
    turns the kept set from rx into rxy, ry, and the members of H change."""
    assert minimal_citation(5) == (8, "follows from rx")
    assert minimal_citation(6) == (9, "follows from rxy, ry")


def test_note_solve_on_a_relation_that_cannot_be_evaluated_raises():
    """v2.2 friction, narrowed in v2.3: derive(), consistency() and the global
    check record a relation that divides by a zero value as a conflict (R28).
    v2.2's solve() raised a bare TraceError('division by zero'); v2.3 raises
    UndefinedValue naming the relation, but still records nothing, and so
    cannot record the conflict in lenient mode either."""
    t = Trace("q", strict=False)
    t.input(ROOT, "m", "value", "mass", value=0)
    t.input(ROOT, "F", "value", "force", value=2)
    t.unknown(ROOT, "a", "acceleration", address="a(A)", ref="E8")
    t.input(ROOT, "law", "model", "E8 relation", relation="a = F/m")
    n = len(t.steps)
    with pytest.raises(UndefinedValue,
                       match=r"^relation law cannot be evaluated with these values \(division by zero\)$"):
        t.solve(ROOT, ["law"], ["a"])
    assert len(t.steps) == n


def test_note_re_supply_warnings_are_trace_wide():
    """regress-10 (open in v2.2): an answer recorded before the re-supply, and
    not resting on it, still carries the re-supply warning."""
    t = spring_account(Trace("q"))
    t.answer(["a"], label="q1")
    t.input(ROOT, "complete2", "completeness", "the spring is the only interaction on A")
    assert real_warnings(t.ledger("q1")) == [
        "complete2 repeats the INPUT complete word for word; deliver the original instead of re-supplying it"]
