"""Adversarial review of handtrace.py, updated for v2.2.

Passing tests document behaviour that was checked and is correct.

* V2R-n tests come from the v2 review, V21R-n tests from the v2.1 review.
  Where a later version fixed the finding, the test is now an ordinary
  passing test of the new behaviour. Where v2.2 changed the semantics on
  purpose (withdrawal taints values, not names; solve() records one DERIVE
  per fixed value; a hidden value blocks a step only if it would change the
  verdict; the global check reads only values fixed before the answer;
  ':=' is not a word; combined refs need every part) the test asserts the
  new semantics.
* V22R-n tests are new findings on v2.2. Each genuine bug is an
  xfail(strict=True) test that asserts the behaviour the finding asks for;
  it fails until fixed. V21R-8 is still open in v2.2 and stays an xfail.
  Notes and frictions that are not bugs are passing tests that pin the
  current behaviour, with the finding id in the name.
* v2.3 fixed V22R-1 to V22R-4; their tests now pass unmarked. Tests that
  pinned v2.2 behaviour changed by v2.3 (V22R-1/2/3/5, V21R-13, the joint
  inconsistency subset) assert the v2.3 behaviour and say so. V21R-8 is still
  open and stays an xfail.
* Deliberately open gaps (conditional branches, units, the observation side,
  the C3 budget, editions, explicit RETURN, a minimum-size citation search
  beyond 8 relations) are short documented tests or comments at the end,
  never failures.
"""

import itertools
import json
import random
import re
import time
from fractions import Fraction
from pathlib import Path

import pytest

from handtrace import (
    ROOT,
    CheckError,
    Form,
    HiddenLookupError,
    Trace,
    TraceError,
    entails,
    load_entries,
    main,
    mentioned_names,
    needed_relations,
    parse_equation,
    parse_expression,
)

DESIGN = Path(r"C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/07_design_2_1")
ENTRIES_MD = DESIGN / "DESIGN_2_1_DRAFT_1_ENTRIES.md"
CURRENT_STATE_MD = DESIGN / "CURRENT_STATE.md"

# E8 exactly as the file lays it out, hard line break included.
E8_RAW = ("For one material-object, its net-force-material-object divided by\n"
          "its inertial-mass-material-object.")

needs_entries = pytest.mark.skipif(not ENTRIES_MD.exists(), reason="entries file not present")


def unknowns(t, frame, *names):
    for n in names:
        t.unknown(frame, n, f"quantity {n}", address=f"addr({n})", ref="C-test")


def entries():
    return load_entries(str(ENTRIES_MD))


def raw_entry_blocks():
    """Independent reader: {ref: raw fenced text with its line breaks, headword line dropped}."""
    out, refs, buf = {}, [], None
    for line in ENTRIES_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{2,4}\s*\[([^\]]+)\]", line)
        if m:
            refs = [r.strip() for r in m.group(1).split("/")]
            continue
        if line.strip().startswith("```"):
            if buf is None:
                buf = []
            else:
                body = "\n".join(buf).split(":=", 1)[1].strip("\n")
                for r in refs:
                    out[r] = body
                buf, refs = None, []
            continue
        if buf is not None:
            buf.append(line)
    return out


def counts(t):
    return len(t.steps), len(t.commands)


# ===========================================================================
# Exact literal parsing (passing)
# ===========================================================================


@pytest.mark.parametrize("text, value", [
    ("2.94e1", Fraction(147, 5)),
    ("0.30000000000000001", Fraction(30000000000000001, 10 ** 17)),
    ("0.1 + 0.2", Fraction(3, 10)),
    ("1e400", Fraction(10) ** 400),
    ("1e-400", Fraction(1, 10 ** 400)),
    ("1_000.000_1", Fraction(10000001, 10000)),
    ("1.e1", Fraction(10)),
    (".5", Fraction(1, 2)),
    ("1E+2", Fraction(100)),
    ("1.5e-1_0", Fraction(15, 10 ** 11)),
    ("0x10", Fraction(16)),
    ("2**-1", Fraction(1, 2)),
    ("10**-3", Fraction(1, 1000)),
    ("(-2)**-3", Fraction(-1, 8)),
    ("2**3**2", Fraction(512)),
    ("-2**2", Fraction(-4)),
    ("4**(2/2)", Fraction(4)),
    ("(1\n+ 2.5)", Fraction(7, 2)),
    ("+-+3", Fraction(-3)),
])
def test_literals_are_read_exactly(text, value):
    form, names = parse_expression(text)
    assert form.is_constant() and form.const == value and names == ()


@pytest.mark.parametrize("text", ["0**-1", "1j", "True", "None", "'a'", "3 # c", "x.y", "a[1]",
                                  "1 // 2", "5 % 2", "x ^ 2", "abs(2)", "1 if x else 2", "1\n+2", "x @ y"])
def test_unsupported_expressions_are_refused(text):
    with pytest.raises(TraceError):
        parse_expression(text, {"x": Fraction(2), "y": Fraction(1), "a": Fraction(1)})


def test_a_rational_root_is_evaluated_exactly():
    """v2.3: 4**0.5 is no longer refused; a fractional exponent whose root is rational is exact."""
    form, names = parse_expression("4**0.5")
    assert form.is_constant() and form.const == Fraction(2) and names == ()


@pytest.mark.parametrize("text", ["x <= 2", "x != 2", "x = 2 ==", "x = y = 2"])
def test_non_equations_are_refused(text):
    with pytest.raises(TraceError):
        parse_equation(text, {"x": Fraction(2)})


def test_supplied_values_are_exact():
    t = Trace("q")
    t.input(ROOT, "a", "value", "a", value="0.30000000000000001")
    t.input(ROOT, "b", "value", "b", value=0.1)
    t.input(ROOT, "c", "value", "c", value=Fraction(1, 3))
    t.input(ROOT, "h", "haze", "H = 0", value=0)
    assert t.values == {"a": Fraction(30000000000000001, 10 ** 17), "b": Fraction(1, 10), "c": Fraction(1, 3),
                        "h": 0}
    assert t.derive(ROOT, "3*c + 10*b = 2").check == "checked"


# ===========================================================================
# Validation (v2.1 closes V2R-11, -12, -16, -17, -23)
# ===========================================================================


@pytest.mark.parametrize("name", ["lambda", "None", "True", "if", "1x", "a-b", "", "x y", "m\n", "m\r", " m"])
def test_keywords_non_identifiers_and_trailing_newlines_are_refused_as_names(name):
    """V2R-11 fixed: names use fullmatch, so 'm\\n' is no longer a second m."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    with pytest.raises(TraceError):
        t.input(ROOT, name, "value", "v", value=1)


def test_v2r12_relation_without_equals_is_refused_at_registration():
    t = Trace("q")
    t.input(ROOT, "x", "value", "x", value=1)
    attempts = [
        lambda: t.input(ROOT, "r0", "model", "no equals sign", relation="x + 1"),
        lambda: t.contract(ROOT, "C", "c", source="s", binds="r1", relation="x + 1"),
        lambda: t.reading(ROOT, "r", binds="r2", relation="x + 1"),
        lambda: t.external(ROOT, "diff", "d", binds="r3", relation="x + 1"),
        lambda: t.derive(ROOT, "x + 1", name="r4"),
        lambda: t.input(ROOT, "r5", "model", "m", relation="x != 2"),
        lambda: t.input(ROOT, "r6", "model", "m", relation="x >= 2"),
    ]
    for attempt in attempts:
        before = counts(t)
        with pytest.raises(TraceError):
            attempt()
        assert counts(t) == before
    assert not any(n.startswith("r") for n in t.bindings)


def test_v2r23_value_kind_needs_a_value():
    with pytest.raises(TraceError, match="value="):
        Trace("q").input(ROOT, "m", "value", "inertial mass of A")


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), "inf", "nan"])
def test_v2r16_non_finite_values_are_trace_errors(value):
    with pytest.raises(TraceError):
        Trace("q").input(ROOT, "y", "value", "infinite", value=value)


@pytest.mark.parametrize("text, order", [
    ("a*b + c", ("a", "b", "c")),
    ("c + (b*a)", ("c", "b", "a")),
    ("y = b*a + c", ("y", "b", "a", "c")),
    ("b*a = c", ("b", "a", "c")),
    ("(z\n+ y)", ("z", "y")),
])
def test_v2r17_mentioned_names_are_in_source_order(text, order):
    assert mentioned_names(text) == order


def test_v21r13_note_validation_leftovers():
    """V21R-13 (note): what the v2.1 validation still lets through, pinned as current behaviour.

    A compound kind containing 'value' without value= becomes a fact; kind
    'value' with relation= binds a relation.
    """
    t = Trace("q")
    t.input(ROOT, "g", "value/model", "local free-fall acceleration")
    assert t.bindings["g"].sort == "fact"
    unknowns(t, ROOT, "x")
    t.input(ROOT, "rv", "value", "a value-kind relation", relation="x = 2")
    assert t.bindings["rv"].sort == "relation"


# ===========================================================================
# Provenance and minimal citation
# ===========================================================================


def test_value_substituted_through_a_cited_relation_stays_in_the_cone():
    """Regression for the enc-spring1-1 repro: k must feed the answer."""
    for use_solve in (False, True):
        t = Trace("q")
        t.unknown(ROOT, "F", "net", address="net(A)", ref="E8")
        t.unknown(ROOT, "f", "member", address="imp", ref="FS")
        t.contract(ROOT, "FS", "sum", source="x", binds="fs", relation="F = f")
        t.input(ROOT, "k", "value", "stiffness", value=20)
        t.contract(ROOT, "D", "dispatch", source="x", binds="sp", relation="f = k*0.1")
        t.derive(ROOT, "f = 2", from_relations=["sp"], binds="f")
        if use_solve:
            t.solve(ROOT, ["fs"], ["F"])
        else:
            t.derive(ROOT, "F = 2", from_relations=["fs"], binds="F")
        t.answer(["F"])
        led = t.ledger()
        assert [c["name"] for c in led["commitments"]] == ["k"]
        assert led["not_in_answer"] == []
        assert {r["ref"].split(" ")[0] for r in led["theory"]} >= {"FS", "D", "E8"}


def test_superfluous_citation_is_reported_and_its_premise_leaves_the_set():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "B", "recognition", "premise B")
    t.input(ROOT, "r1", "model", "x plus y", relation="x + y = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "x minus y", relation="x - y = 1", uses=["A"])
    t.input(ROOT, "r3", "model", "z five", relation="z = 5", uses=["B"])
    st = t.derive(ROOT, "x = 2", from_relations=["r3", "r1", "r2"], binds="x")
    assert st.check == "checked" and "follows from r1, r2" in st.detail and "cited but not needed: r3" in st.detail
    t.answer(["x"])
    names = {c["name"] for c in t.ledger()["commitments"]}
    assert names == {"A", "r1", "r2"}
    assert {c["name"] for c in t.ledger()["not_in_answer"]} == {"B", "r3"}


def test_v2r4_ties_go_to_the_first_cited_route():
    """V2R-4: v2.1 keeps a smallest subset and breaks ties toward the relations cited first.

    So the tracer's first-cited route is the one kept (v2 dropped it). Order
    still decides between equally small routes, by design.
    """
    def commitments(order):
        t = Trace("q")
        unknowns(t, ROOT, "x")
        t.input(ROOT, "A", "recognition", "premise A")
        t.input(ROOT, "B", "recognition", "premise B")
        t.input(ROOT, "rA", "model", "route A", relation="x = 3", uses=["A"])
        t.input(ROOT, "rB", "model", "route B", relation="2*x = 6", uses=["B"])
        t.derive(ROOT, "x = 3", from_relations=order, binds="x")
        t.answer(["x"])
        return {c["name"] for c in t.ledger()["commitments"]}

    assert commitments(["rA", "rB"]) == {"A", "rA"}
    assert commitments(["rB", "rA"]) == {"B", "rB"}


def test_smallest_subset_beats_an_irreducible_larger_one():
    """probes-8: with x + y = 5, y = 2 and x = 3, the single direct premise wins in either order."""
    for order in (["rx", "ry", "rxy"], ["rxy", "ry", "rx"]):
        t = Trace("q")
        unknowns(t, ROOT, "x", "y")
        t.input(ROOT, "rxy", "model", "sum", relation="x + y = 5")
        t.input(ROOT, "ry", "model", "y two", relation="y = 2")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3")
        st = t.derive(ROOT, "x = 3", from_relations=order, binds="x")
        assert st.detail.startswith("follows from rx ")
        t.answer(["x"])
        assert [c["name"] for c in t.ledger()["commitments"]] == ["rx"]


def _random_consistent_system(rng, n_rel=(1, 5)):
    n = rng.randint(1, 4)
    names = [f"v{i}" for i in range(n)]
    sol = {v: Fraction(rng.randint(-5, 5)) for v in names}
    rels = []
    for _ in range(rng.randint(*n_rel)):
        coeffs = {v: Fraction(rng.randint(-3, 3)) for v in names}
        const = -sum(coeffs[v] * sol[v] for v in names)
        rels.append(Form.of(coeffs, const))
    weights = [Fraction(rng.choice([0, 0, 1, -2, 3])) for _ in rels]
    claim = Form.of({}, Fraction(0))
    for w, r in zip(weights, rels):
        claim = claim + r.scale(w)
    return rels, claim


def test_needed_relations_is_a_smallest_subset_with_ties_to_the_first_cited():
    rng = random.Random(20261108)
    tried = 0
    for _ in range(300):
        rels, claim = _random_consistent_system(rng, (1, 7))
        if claim.is_zero():
            continue
        tried += 1
        keep = needed_relations(rels, claim)
        assert keep == sorted(keep) and entails([rels[i] for i in keep], claim)
        for size in range(1, len(keep) + 1):
            for combo in itertools.combinations(range(len(rels)), size):
                if size < len(keep) or combo < tuple(keep):
                    assert not entails([rels[j] for j in combo], claim), (combo, keep)
    assert tried > 100


def test_needed_relations_beyond_eight_is_greedy_from_the_end_and_still_irredundant():
    """v2.2 lowers the exhaustive threshold from 10 to 8 relations; beyond it the kept
    set is irredundant, not necessarily smallest (an open gap, see the end of the file)."""
    rng = random.Random(7)
    for _ in range(60):
        rels, claim = _random_consistent_system(rng, (9, 13))
        if claim.is_zero():
            continue
        keep = needed_relations(rels, claim)
        assert entails([rels[i] for i in keep], claim)
        for i in keep:
            assert not entails([rels[j] for j in keep if j != i], claim)
    x3 = Form.of({"x": Fraction(1)}, Fraction(-3))
    filler = [Form.of({f"y{i}": Fraction(1)}, Fraction(-i)) for i in range(10)]
    x6 = Form.of({"x": Fraction(2)}, Fraction(-6))
    assert needed_relations([x6] + filler + [x3], x3) == [0]  # the first-cited route survives


def test_v2r21_superfluous_nonlinear_citation_no_longer_blocks_the_check():
    """v2.2 notes a superfluous nonlinear citation as 'nonlinear citations not checked',
    separately from linear citations that are not needed."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "product", relation="y*z = 1")
    t.input(ROOT, "r3", "model", "double x", relation="2*x = 6")
    st = t.derive(ROOT, "x = 3", from_relations=["r2", "r1", "r3"], binds="x")
    assert st.check == "checked"
    assert st.detail == "follows from r1 (cited but not needed: r3) (nonlinear citations not checked: r2)"
    assert t.bindings["r2"].step not in st.deps and t.bindings["r3"].step not in st.deps
    t2 = Trace("q", strict=False)
    unknowns(t2, ROOT, "x", "y", "z")
    t2.input(ROOT, "r1", "model", "sum", relation="x + y = 3")
    t2.input(ROOT, "r2", "model", "product", relation="y*z = 1")
    st2 = t2.derive(ROOT, "x = 2", from_relations=["r1", "r2"])
    assert st2.check == "unchecked" and "nonlinear relations r2" in st2.detail
    t3 = Trace("q")
    unknowns(t3, ROOT, "x", "y", "z")
    t3.input(ROOT, "r1", "model", "sum", relation="x + y = 3")
    t3.input(ROOT, "r2", "model", "product", relation="y*z = 1")
    with pytest.raises(CheckError, match="unchecked"):
        t3.derive(ROOT, "x = 2", from_relations=["r1", "r2"])


def test_derive_uses_and_solve_uses_enter_the_cone():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "fact1", "recognition", "the string is taut")
    t.input(ROOT, "fact2", "completeness", "nothing else acts")
    t.input(ROOT, "r", "model", "x three", relation="x = 3")
    t.input(ROOT, "s", "model", "y four", relation="y = 4")
    t.derive(ROOT, "x = 3", from_relations=["r"], binds="x", uses=["fact1"])
    t.solve(ROOT, ["s"], ["y"], uses=["fact2"])
    t.answer(["x", "y"])
    assert {c["name"] for c in t.ledger()["commitments"]} == {"fact1", "fact2", "r", "s"}


def test_solve_keeps_only_the_relations_its_values_need():
    """regress-3 repro: a relation that is 0 = 0 after substitution, and its premises, leave the cone."""
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "r", relation="2*x = 6")
    t.input(ROOT, "paint", "recognition", "blocks are red")
    t.input(ROOT, "k", "value", "k", value=4)
    t.input(ROOT, "kr", "model", "irrelevant", relation="k = 4", uses=["paint"])
    st = t.solve(ROOT, ["r", "kr"], ["x"])
    assert st.kind == "solve" and "relations not needed for the fixed values: kr" in st.detail
    t.answer(["x"])
    assert [c["name"] for c in t.ledger()["commitments"]] == ["r"]


def test_v2r3_family_solve_keeps_only_what_the_fixed_value_needs():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "B", "recognition", "premise B")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "y and z", relation="y + z = 1", uses=["B"])
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y", "z"])
    assert "fixed anyway: x = 3" in st.detail and "not needed for the fixed values: r2" in st.detail
    t.answer(["x"])
    assert {c["name"] for c in t.ledger()["commitments"]} == {"A", "r1"}


def test_v21r6_unique_solve_provenance_is_per_value():
    """V21R-6 / V2R-3 fixed: solve() records one EXTERNAL report and one checked DERIVE per
    fixed value, each resting on its own smallest relation set. The report step feeds no
    answer; withdrawing a premise only y needs leaves x usable."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "B", "recognition", "premise B")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "y two", relation="y = 2", uses=["B"])
    n = len(t.steps)
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    assert st.detail == "unique: x = 3, y = 2" and st.op == "EXTERNAL" and st.index == n
    dx, dy = t.steps[n + 1], t.steps[n + 2]
    assert [(s.op, s.claim, s.check, s.binds) for s in (dx, dy)] == [
        ("DERIVE", "x = 3", "checked", ("x",)), ("DERIVE", "y = 2", "checked", ("y",))]
    assert t.value_step == {"x": dx.index, "y": dy.index}
    assert t.bindings["r2"].step not in dx.deps and t.bindings["r1"].step not in dy.deps
    t.answer(["x"], label="px")
    assert {c["name"] for c in t.ledger("px")["commitments"]} == {"A", "r1"}
    assert st.index not in t.cone("px")
    assert [s["step"] for s in t.ledger("px")["step_members"]] == [dx.id]
    t.withdraw(ROOT, "B", "B was wrong")
    assert t.derive(ROOT, "2*x = 6").check == "checked"
    t.answer(["x"], label="px2")
    with pytest.raises(TraceError, match="the value of 'y' rests on 'B', which was withdrawn"):
        t.answer(["y"])


def test_v21r6_each_value_keeps_its_own_smallest_set():
    """V21R-6 (second half) fixed: x needs only r3, y needs r1 and r2; an answer naming x
    rests on r3 alone and an answer naming y on r1 and r2."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "difference", relation="x - y = 1")
    t.input(ROOT, "r3", "model", "double x", relation="2*x = 6")
    n = len(t.steps)
    st = t.solve(ROOT, ["r1", "r2", "r3"], ["x", "y"])
    assert st.detail == "unique: x = 3, y = 2"
    assert [s.detail for s in t.steps[n + 1:]] == ["follows from r3", "follows from r1, r2"]
    t.answer(["x"], label="px")
    t.answer(["y"], label="py")
    assert [c["name"] for c in t.ledger("px")["commitments"]] == ["r3"]
    assert [c["name"] for c in t.ledger("py")["commitments"]] == ["r1", "r2"]


def test_v22_a_tainted_value_can_be_determined_again_by_solve_or_derive():
    """v2.2: a value resting on a withdrawn premise is visible nowhere, and the quantity may be
    determined again. The new answer rests only on the new account."""
    for route in ("solve", "derive"):
        t = Trace("q")
        unknowns(t, ROOT, "x")
        t.input(ROOT, "c", "completeness", "only the spring acts")
        t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
        t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
        t.withdraw(ROOT, "c", "the table pushes too")
        assert "x" not in t.known_values(ROOT) and t.value_visible(ROOT, "x") is None
        t.input(ROOT, "rx4", "model", "x four, revised account", relation="x = 4")
        if route == "solve":
            t.solve(ROOT, ["rx4"], ["x"])
        else:
            t.derive(ROOT, "x = 4", from_relations=["rx4"], binds="x")
        with pytest.raises(TraceError, match="already has a value"):
            t.derive(ROOT, "x = 4", from_relations=["rx4"], binds="x")
        t.answer(["x"])
        led = t.ledger()
        assert led["answer"] == "x = 4"
        assert [c["name"] for c in led["commitments"]] == ["rx4"]
        assert [c["name"] for c in led["withdrawn"]] == ["c"]
        assert Trace.replay(json.loads(t.to_json())).to_record() == t.to_record()


# ===========================================================================
# Ledger: mistakes, conflicts, the global check and warnings
# ===========================================================================


def test_ledger_separates_found_mistakes_from_premise_conflicts():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "x three", relation="x = 3")
    t.input(ROOT, "s", "model", "x four", relation="x = 4")
    slip = t.derive(ROOT, "2*x = 7", from_relations=["r"])
    clash = t.derive(ROOT, "x = 3", from_relations=["r", "s"])
    bare = t.derive(ROOT, "2 = 3")
    cons = t.consistency(ROOT, ["r", "s"])
    t.input(ROOT, "ry1", "model", "y one", relation="y = 1")
    t.input(ROOT, "ry2", "model", "y two", relation="y = 2")
    sv = t.solve(ROOT, ["ry1", "ry2"], ["y"])
    t.input(ROOT, "m", "value", "m", value=1)
    t.answer(["m"])
    led = t.ledger()
    assert [r["step"] for r in led["mistakes"]] == [slip.id, bare.id]
    assert [r["step"] for r in led["conflicts"]] == [clash.id, cons.id, sv.id]
    assert all(r["detail"].startswith("mistake") for r in led["mistakes"])
    assert all(r["detail"].startswith("conflict") for r in led["conflicts"])
    md = t.to_markdown()
    assert "### Found mistakes" in md and "### Conflicts" in md


def test_cited_relations_that_contradict_each_other_are_a_conflict():
    for strict in (True, False):
        t = Trace("q", strict=strict)
        unknowns(t, ROOT, "x")
        t.input(ROOT, "r1", "model", "x one", relation="x = 1")
        t.input(ROOT, "r2", "model", "x two", relation="x = 2")
        if strict:
            with pytest.raises(CheckError, match="conflict"):
                t.derive(ROOT, "x = 1", from_relations=["r1", "r2"])
            assert len(t.steps) == 3
        else:
            st = t.derive(ROOT, "x = 1", from_relations=["r1", "r2"], binds="x")
            assert st.check == "failed" and "conflict" in st.detail and "x" not in t.values


def test_cited_relation_that_contradicts_a_visible_value_is_a_conflict():
    """Regression for enc-spring2-7 and the enc-spring1-5 'junk' repro."""
    t = Trace("q", strict=False)
    t.input(ROOT, "m", "value", "m", value=2)
    unknowns(t, ROOT, "a")
    t.input(ROOT, "junk", "model", "unrelated", relation="m = 7")
    st = t.derive(ROOT, "m = 7", from_relations=["junk"])
    assert st.check == "failed" and st.detail.startswith("conflict")
    t.input(ROOT, "ra", "model", "a one", relation="a = 1")
    t.derive(ROOT, "a = 1", from_relations=["ra"], binds="a")
    t.answer(["a"])
    assert [c["step"] for c in t.ledger()["conflicts"]] == [st.id]
    assert t.ledger()["mistakes"] == []


def test_v2r1_contradiction_masked_by_a_hidden_value_is_refused_at_the_step():
    """V2R-1, v2.2: x's hidden value 5 would turn the check into a conflict with r (x = 7),
    so the derive itself is now a hidden lookup and records nothing."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")
    t.input(ROOT, "rx", "model", "x is five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(d1, "r", "model", "x is seven", relation="x = 7")
    t.input(d1, "r2", "model", "y is x plus one", relation="y = x + 1")
    before = counts(t)
    with pytest.raises(HiddenLookupError, match=r"\['x'\].*would change the verdict"):
        t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y")
    assert counts(t) == before


def test_v2r1_contradiction_made_before_the_value_existed_is_a_ledger_conflict():
    """V2R-1, the order the step check cannot see: D1 derives y = 8 from x = 7 before ROOT
    fixes x = 5. The global check at the answer reports both relations on the route."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")
    t.input(d1, "r", "model", "x is seven", relation="x = 7")
    t.input(d1, "r2", "model", "y is x plus one", relation="y = x + 1")
    assert t.derive(d1, "y = 8", from_relations=["r", "r2"], binds="y").check == "checked"
    t.input(ROOT, "rx", "model", "x is five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.answer(["x", "y"])
    led = t.ledger()
    # y = 8 was computed with x = 7, so at x = 5 both r and r2 are false.
    assert sorted(c["ref"] for c in led["conflicts"]) == ["r", "r2"]
    assert all("contradicted by the values determined in this trace" in c["detail"] for c in led["conflicts"])
    assert any(w.startswith("the answer rests on r,") for w in led["warnings"])


def test_v2r1_relation_reached_only_through_uses_is_checked_globally():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "bad", "model", "m is three", relation="m = 3")
    t.input(ROOT, "r", "model", "x is m", relation="x = m")
    t.derive(ROOT, "x = 2", from_relations=["r"], binds="x", uses=["bad"])
    t.answer(["x"])
    led = t.ledger()
    assert "bad" in [c["name"] for c in led["commitments"]]
    assert [c["ref"] for c in led["conflicts"]] == ["bad"]
    assert any("rests on bad" in w for w in led["warnings"])


def test_v21r12_global_check_reads_only_values_fixed_before_the_answer():
    """V21R-12 closed by v2.2: a value fixed after p1 no longer changes p1's ledger. A later
    answer resting on the same relation does see the conflict."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "x three", relation="x = 3")
    t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")
    t.derive(ROOT, "x = 3", from_relations=["r"], binds="x", uses=["s"])
    t.answer(["x"], label="p1")
    led_before = t.ledger("p1")
    assert led_before["conflicts"] == []
    t.input(ROOT, "ry", "model", "y seven", relation="y = 7")
    t.derive(ROOT, "y = 7", from_relations=["ry"], binds="y")
    assert t.ledger("p1")["conflicts"] == [] and t.ledger("p1")["warnings"] == led_before["warnings"]
    t.answer(["x"], label="p2")
    assert [c["ref"] for c in t.ledger("p2")["conflicts"]] == ["s"]


def test_v22_global_check_reports_joint_inconsistency():
    """probes-9 / fresh-18(d) closed: no single relation is contradicted, but r1 and r3 give
    y = 2 while r2 and r4 give y = 3; y is never determined. v2.3: the check names a minimal
    inconsistent subset (a deletion filter in citation order), r3, r4, not every open relation."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "r3", "model", "difference", relation="x - y = 1")
    t.derive(ROOT, "x = 3", from_relations=["r1", "r3"], binds="x")
    t.input(ROOT, "r2", "model", "y three", relation="y = 3")
    t.input(ROOT, "r4", "model", "z twice y", relation="z = 2*y")
    t.derive(ROOT, "z = 6", from_relations=["r2", "r4"], binds="z")
    t.answer(["x", "z"])
    led = t.ledger()
    assert len(led["conflicts"]) == 1
    row = led["conflicts"][0]
    assert row["ref"] == "r3, r4" and "jointly inconsistent" in row["detail"]
    assert "the answer rests on relations that are jointly inconsistent: r3, r4" in led["warnings"]
    md = t.to_markdown()
    assert "jointly inconsistent with the values determined in this trace" in md


def test_v22_global_check_keeps_a_relation_withdrawn_after_the_answer():
    """probes-5 closed: withdrawing a contradicted relation after p1 keeps its conflict in p1's
    ledger; an answer recorded after the withdrawal no longer rests on it."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "x seven", relation="x = 7")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(ROOT, "ry", "model", "y six", relation="y = 6")
    t.derive(ROOT, "y = 6", from_relations=["ry"], binds="y", uses=["r"])
    t.answer(["y"], label="p1")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r"]
    t.withdraw(ROOT, "r", "contradicted by rx")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r"]
    with pytest.raises(TraceError, match="rests on 'r'"):
        t.answer(["y"], label="p2")


def _p1_resting_on_s_with_x_fixed_before():
    """p1 answers y = 7 and rests on s: y = x + 1 through uses; x = 3 was fixed before p1
    from rx, which p1 does not rest on. s is registered before x has a value."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    t.input(ROOT, "ry", "model", "y seven", relation="y = 7")
    t.derive(ROOT, "y = 7", from_relations=["ry"], binds="y", uses=["s"])
    t.answer(["y"], label="p1")
    return t


def test_v22r4_pinned_withdrawal_after_the_answer_keeps_the_old_value_in_the_check():
    """V22R-4 (the part that works): rx withdrawn after p1 still counts for p1, since the
    rule drops only values resting on a premise withdrawn BEFORE the answer."""
    t = _p1_resting_on_s_with_x_fixed_before()
    assert t.bindings["rx"].step not in t.cone("p1")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["s"]
    t.withdraw(ROOT, "rx", "x was misread")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["s"]


def test_v22r4_redetermining_a_value_later_does_not_change_an_earlier_ledger():
    """V22R-4 fixed in v2.3: the global check reads each name's value history, so determining
    x again after rx is withdrawn keeps the value x had at p1, and p1's conflict stays."""
    t = _p1_resting_on_s_with_x_fixed_before()
    before = t.to_record()["ledgers"]["p1"]
    assert [c["ref"] for c in before["conflicts"]] == ["s"]
    t.withdraw(ROOT, "rx", "x was misread")
    t.input(ROOT, "rx6", "model", "x six, revised", relation="x = 6")
    t.derive(ROOT, "x = 6", from_relations=["rx6"], binds="x")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["s"]


def test_claim_that_is_zero_after_substitution_has_no_independent_content():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "a", "value", "a", value=1)
    t.input(ROOT, "f", "value", "f", value=2)
    unknowns(t, ROOT, "z")
    t.input(ROOT, "junk", "model", "unrelated", relation="z = 7")
    st = t.derive(ROOT, "f = m*a", from_relations=["junk"])
    assert st.check == "checked" and "holds identically" in st.detail and "no independent content" in st.detail
    assert "follows from" not in st.detail
    assert t.bindings["junk"].step not in st.deps


def test_inconsistent_solve_is_failed_listed_and_binds_nothing():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r1", "model", "one", relation="x + y = 1")
    t.input(ROOT, "r2", "model", "two", relation="x + y = 2")
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y"])
    assert st.check == "failed" and "inconsistent" in st.detail and st.binds == ()
    t.input(ROOT, "m", "value", "m", value=1)
    t.answer(["m"])
    led = t.ledger()
    assert [c["step"] for c in led["conflicts"]] == [st.id]
    assert [c["step"] for c in led["solve_reports"]] == [st.id]


def test_solve_family_fixes_what_it_determines_and_refuses_repeats_and_empty_unknowns():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", "z")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3")
    t.input(ROOT, "r2", "model", "y and z", relation="y + z = 1")
    with pytest.raises(TraceError, match="repeat"):
        t.solve(ROOT, ["r1", "r1"], ["x"])
    with pytest.raises(TraceError, match="repeat"):
        t.solve(ROOT, ["r1"], ["x", "x"])
    with pytest.raises(TraceError, match="consistency"):
        t.solve(ROOT, ["r1"], [])
    st = t.solve(ROOT, ["r1", "r2"], ["x", "y", "z"])
    assert "fixed anyway: x = 3" in st.detail and t.values == {"x": 3} and st.binds == ("x",)


def test_strict_uncheckable_derive_raises_lenient_cannot_bind():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "product", relation="x*y = 6")
    with pytest.raises(CheckError, match="nonlinear"):
        t.derive(ROOT, "x = 2", from_relations=["r"], binds="x")
    t2 = Trace("q", strict=False)
    unknowns(t2, ROOT, "x", "y")
    t2.input(ROOT, "r", "model", "product", relation="x*y = 6")
    st = t2.derive(ROOT, "x = 2", from_relations=["r"], binds="x")
    assert st.check == "unchecked" and "x" not in t2.values and "not determined" in st.detail


def test_lenient_answer_on_a_failed_named_relation_is_warned():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x three", relation="x = 3")
    bad = t.derive(ROOT, "x = 4", from_relations=["r"], name="r4")
    t.derive(ROOT, "x = 4", from_relations=["r4"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert any(bad.id in w and "failed" in w for w in led["warnings"])
    assert [r["step"] for r in led["mistakes"]] == [bad.id]
    assert [c["ref"] for c in led["conflicts"]] == ["r"]  # x = 4 now contradicts r: x = 3


def test_v2r2_answer_resting_on_an_unchecked_derive_is_warned():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "r", "model", "product", relation="x*y = 6")
    bogus = t.derive(ROOT, "x = 99", from_relations=["r"], name="bogus")
    assert bogus.check == "unchecked"
    t.derive(ROOT, "x = 99", from_relations=["bogus"], binds="x")
    t.answer(["x"])
    assert any(bogus.id in w and "could not be checked" in w for w in t.ledger()["warnings"])


def test_answer_on_an_unchecked_external_competence_is_not_warned():
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    ext = t.external(ROOT, "differentiation", "d/dt of the trajectory", binds="dv", relation="x = 2")
    t.derive(ROOT, "x = 2", from_relations=["dv"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert led["warnings"] == []
    assert [(s["step"], s["check"]) for s in led["step_members"]][0] == (ext.id, "unchecked")


# ===========================================================================
# consistency() and solve kinds
# ===========================================================================


def test_consistency_never_raises_on_a_conflict_even_in_strict_mode():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "a", "model", "a", relation="x = 1")
    t.input(ROOT, "b", "model", "b", relation="x = 2")
    st = t.consistency(ROOT, ["a", "b"], text="deliberate conflict")
    assert (st.op, st.kind, st.check) == ("EXTERNAL", "consistency", "failed") and st.binds == ()
    ok = t.consistency(ROOT, ["a"])
    assert ok.check == "checked" and ok.detail == "consistent"
    for bad in ([], ["a", "a"]):
        with pytest.raises(TraceError, match="distinct relations"):
            t.consistency(ROOT, bad)
    t.derive(ROOT, "x = 1", from_relations=["a"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert [r["step"] for r in led["conflicts"]] == [st.id]
    assert st.index not in t.cone() and ok.index not in t.cone()
    assert led["solve_reports"] == []


def test_v2r15_external_named_linear_solve_is_not_a_solve():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=1)
    ext = t.external(ROOT, "linear solve", "solved by hand elsewhere")
    assert ext.kind == "" and ext.check == "unchecked"
    t.answer(["m"])
    assert t.ledger()["solve_reports"] == []


# ===========================================================================
# Visibility, delivery and hidden lookups
# ===========================================================================


def test_delivery_comes_only_from_the_caller_and_never_into_root():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "one")
    d1a = t.demand(d1, "D1a", "grandchild")
    t.input(ROOT, "g", "value", "g", value=10)
    with pytest.raises(HiddenLookupError, match="caller"):
        t.deliver(d1a, "g")  # D1 does not see g yet
    with pytest.raises(TraceError, match="root"):
        t.deliver(ROOT, "g")
    t.deliver(d1, "g")
    with pytest.raises(TraceError, match="already visible"):
        t.deliver(d1a, "g")  # deliveries on the ancestor chain count
    assert t.derive(d1a, "g = 10").check == "checked"


def test_value_travels_only_if_the_caller_sees_it():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    d1 = t.demand(ROOT, "D1", "one")
    first = t.deliver(d1, "x")
    assert "=" not in first.text.split(",")[0]
    t.input(ROOT, "r", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    assert t.value_visible(d1, "x") is None
    with pytest.raises(HiddenLookupError):
        t.derive(d1, "x = 4")
    second = t.deliver(d1, "x")
    assert second.text.startswith("x = 4")
    assert t.derive(d1, "x = 4").check == "checked"


def test_deliver_of_a_determined_value_names_the_binding_and_the_value_step():
    """spring1-4 / spring2-8 fixed."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x four", relation="x = 4")
    fix = t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    dl = t.deliver(d, "x")
    decl = t.steps[t.bindings["x"].step]
    assert f"bound at {decl.id}, value fixed at {fix.id}" in dl.text
    assert fix.index in dl.deps
    # v2.2: a step using the delivered value rests on the binding and value steps, not the DELIVER.
    used = t.derive(d, "2*x = 8")
    assert used.deps == (decl.index, fix.index)
    t.answer(["x"])
    assert dl.index not in t.cone()


def test_v22_a_value_determined_again_must_be_delivered_again():
    """A carrying delivery of the old value does not carry the new one: the old delivery
    predates the new value step, so the new value is hidden in D until delivered."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
    t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    t.deliver(d, "x")
    assert t.known_values(d) == {"x": 3}
    t.withdraw(ROOT, "c", "the table pushes too")
    assert t.known_values(d) == {}
    t.input(ROOT, "rx5", "model", "x five, revised", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx5"], binds="x")
    assert t.value_visible(d, "x") is None
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d, "x = 5")
    again = t.deliver(d, "x")
    assert again.text.startswith("x = 5") and t.derive(d, "x = 5").check == "checked"


def test_deliver_names_the_caller_when_only_the_value_is_missing():
    """probes-12 fixed: HiddenLookupError names the caller."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    unknowns(t, d1a, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.solve(ROOT, ["rx"], ["x"])
    with pytest.raises(HiddenLookupError, match="caller 'D1'"):
        t.deliver(d1a, "x")
    t.deliver(d1, "x")
    assert t.value_visible(d1a, "x") is not None


def test_v2r10_deliver_many_is_all_or_nothing():
    t = Trace("q")
    d = t.demand(ROOT, "D1", "one")
    t.input(ROOT, "m", "value", "m", value=2)
    before = counts(t)
    with pytest.raises(TraceError):
        t.deliver_many(d, ["m", "nope"])
    with pytest.raises(TraceError, match="repeat"):
        t.deliver_many(d, ["m", "m"])
    assert counts(t) == before
    assert len(t.deliver_many(d, ["m"])) == 1


def test_v21r2_deliver_many_is_atomic_for_a_tainted_name():
    """V21R-2 fixed. Under v2.2 the relation r (registered from the withdrawn m) is the tainted
    name; x only has a tainted value, so x is delivered by name, without its value."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "g", "value", "g", value=3)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x is twice m", relation="x = 2*m")
    t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    t.withdraw(ROOT, "m", "misread")
    before = counts(t)
    for names in (["g", "r"], ["g", "m"], ["g", "x", "r"]):
        with pytest.raises(TraceError, match="withdrawn"):
            t.deliver_many(d, names)
        assert counts(t) == before
    steps = t.deliver_many(d, ["g", "x"])
    assert [s.text.split(",")[0] for s in steps] == ["g = 3", "x"]
    assert t.visible(d, "x") is not None and t.value_visible(d, "x") is None
    assert t.known_values(d) == {"g": 3}


def test_v21r13_deliver_many_refuses_a_string():
    """V21R-13 (note), v2.3: a str is refused instead of being iterated, so 'mg' no longer
    delivers m and g; nothing is recorded."""
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    for n in ("m", "g", "mg"):
        t.input(ROOT, n, "value", n, value=1)
    before = counts(t)
    with pytest.raises(TraceError, match=re.escape("deliver_many takes a list of names, not a string")):
        t.deliver_many(d, "mg")
    assert counts(t) == before


def test_deliver_through_one_level():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "g", "value", "g", value=1)
    steps = t.deliver_through(d, "g")
    assert [s.op for s in steps] == ["DELIVER"] and t.value_visible(d, "g") is not None
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(d, "g")


def test_v21r1_deliver_through_two_levels():
    """V21R-1 fixed: one DELIVER into the top frame of the path reaches every frame below."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    t.input(ROOT, "g", "value", "g", value=10)
    before = counts(t)
    steps = t.deliver_through(d1b, "g")
    assert counts(t) == (before[0] + 1, before[1] + 1)
    assert [(s.op, s.frame) for s in steps] == [("DELIVER", "D1")]
    assert all(t.value_visible(f, "g") is not None for f in (d1, d1a, d1b))
    assert t.derive(d1b, "2*g = 20").check == "checked"


def test_v21r1_deliver_through_goes_to_the_highest_frame_below_the_nearest_that_sees_the_value():
    """Two settings from the v2.1 findings: a mid-chain frame sees x by name only, and an
    unknown declared mid-chain has its value fixed at ROOT (probes-12). Either way the one
    DELIVER lands in D1, carrying the value."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    d1b = t.demand(d1a, "D1b", "c")
    unknowns(t, ROOT, "x")
    unknowns(t, d1a, "w")
    t.deliver(d1, "x")  # name only: no value yet
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.input(ROOT, "rw", "model", "w five", relation="w = 5")
    t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    t.solve(ROOT, ["rw"], ["w"])
    assert t.visible(d1b, "x") is not None  # by name, through the delivery into D1
    assert t.visible(d1b, "w") is None  # bound in D1a: visible there and above, not below
    for name in ("x", "w"):
        assert t.value_visible(d1b, name) is None
        steps = t.deliver_through(d1b, name)
        assert [(s.op, s.frame) for s in steps] == [("DELIVER", "D1")]
        assert steps[0].text.startswith(f"{name} = {t.values[name]}")
        assert t.value_visible(d1b, name) is not None
    assert t.derive(d1b, "x + w = 8").check == "checked"


def test_v21r15_deliver_through_reports_unbound_and_withdrawn_names_as_trace_errors():
    """fresh-17 / probes-13 fixed: not a HiddenLookupError. A name resting on a withdrawn
    premise is refused by the delivery it makes, atomically."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "a")
    d1a = t.demand(d1, "D1a", "b")
    t.input(ROOT, "c", "completeness", "only the spring")
    t.input(ROOT, "fact", "model", "rests on c", uses=["c"])
    t.withdraw(ROOT, "c", "the table pushes too")
    before = counts(t)
    for name, msg in (("nope", "not bound"), ("c", "was withdrawn"), ("fact", "rests on 'c'")):
        with pytest.raises(TraceError, match=msg) as info:
            t.deliver_through(d1a, name)
        assert not isinstance(info.value, HiddenLookupError)
        assert counts(t) == before
    t.input(ROOT, "m", "value", "m", value=1)
    with pytest.raises(TraceError, match="already visible at 'ROOT'"):
        t.deliver_through(ROOT, "m")


def test_sibling_value_reaches_a_frame_through_the_caller():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "one")
    d2 = t.demand(ROOT, "D2", "two")
    t.input(d1, "m", "value", "m", value=3)
    with pytest.raises(HiddenLookupError):
        t.derive(d2, "m = 3")
    t.deliver(d2, "m")
    assert t.derive(d2, "2*m = 6").check == "checked"


def test_hidden_value_in_a_failed_or_nonlinear_check_is_a_hidden_lookup():
    t = Trace("q")
    unknowns(t, ROOT, "x", "a")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "a")
    t.input(ROOT, "r", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    with pytest.raises(HiddenLookupError, match="not visible"):
        t.derive(d1, "x = 4")
    with pytest.raises(HiddenLookupError, match="not visible"):
        t.derive(d1, "x*a = 8")


def _slip_with_hidden_y(y_value, r2="y = 5"):
    """Lenient. y's value is fixed at ROOT and hidden in D1 (delivered by name only).
    D1 cites r: x = 3 and r2, and the tracer slips to x = 4."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x", "y", "z")
    d1 = t.demand(ROOT, "D1", "one")
    for n in ("x", "y", "z"):
        t.deliver(d1, n)
    t.input(ROOT, "ry", "model", "y at ROOT", relation=f"y = {y_value}")
    t.derive(ROOT, f"y = {y_value}", from_relations=["ry"], binds="y")
    t.input(d1, "r", "model", "x three", relation="x = 3")
    t.input(d1, "r2", "model", "r2 in D1", relation=r2)
    return t, d1


def test_v2r19_unrelated_hidden_value_no_longer_blocks_a_slip():
    """V2R-19 fixed in v2.2: y = 5 makes r2 (y = 5) true, so delivering y changes nothing and
    the slip is recorded as a found mistake at once, exactly as after a delivery."""
    t, d1 = _slip_with_hidden_y(5)
    st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("mistake: does not follow from r, r2")
    t.deliver(d1, "y")
    again = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert (again.check, again.detail) == (st.check, st.detail)


def test_v21r7_hidden_value_that_cannot_change_the_verdict_does_not_block_a_slip():
    """V21R-7 fixed: with r2: y = z (z free) no value of y changes the verdict on x = 4."""
    t, d1 = _slip_with_hidden_y(5, r2="y = z")
    st = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("mistake")
    assert t.value_visible(d1, "y") is None


def test_v21r7_hidden_value_does_not_block_an_unchecked_step():
    """fresh-10 / V21-9 fixed: the unchecked path applies the same rule. Delivering y = 5
    cannot make x*w = 6 linear, so the step is recorded as unchecked."""
    t, d1 = _slip_with_hidden_y(5, r2="x*z = 6")
    st = t.derive(d1, "x = 3", from_relations=["r2"])
    assert st.check == "unchecked" and "nonlinear relations r2" in st.detail
    t.input(d1, "ry5", "model", "y five in D1", relation="y = 5")
    st2 = t.derive(d1, "x = 3", from_relations=["r2", "ry5"])
    assert st2.check == "unchecked"


def test_v22r1_hidden_value_that_turns_a_mistake_into_a_conflict_is_a_hidden_lookup():
    """V22R-1 fixed in v2.3: _check_claim compares the verdict category, so a hidden y = 6 that
    would turn a found mistake into a conflict with r2 (y = 5) is a hidden lookup."""
    t, d1 = _slip_with_hidden_y(6)
    with pytest.raises(HiddenLookupError, match=r"\['y'\]"):
        t.derive(d1, "x = 4", from_relations=["r", "r2"])


def test_v22r1_the_slip_is_a_hidden_lookup_hidden_and_a_conflict_delivered():
    """V22R-1, v2.3: with y hidden the slip is refused (nothing recorded, no mistake filed);
    once y is delivered the same step is recorded once, as a conflict."""
    t, d1 = _slip_with_hidden_y(6)
    before = counts(t)
    with pytest.raises(HiddenLookupError, match=re.escape("values of ['y'] exist but are not visible at 'D1' and "
                                                          "would change the verdict; deliver them")):
        t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert counts(t) == before
    t.deliver(d1, "y")
    delivered = t.derive(d1, "x = 4", from_relations=["r", "r2"])
    assert delivered.check == "failed"
    assert delivered.detail == "conflict: the cited relations r, r2 contradict each other or the values visible here"
    t.input(ROOT, "m", "value", "m", value=1)
    t.answer(["m"])
    led = t.ledger()
    assert led["mistakes"] == []
    assert [r["step"] for r in led["conflicts"]] == [delivered.id]


def test_v22_hidden_value_that_would_turn_a_check_into_a_conflict_still_blocks():
    t, d1 = _slip_with_hidden_y(6)
    before = counts(t)
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d1, "x = 3", from_relations=["r", "r2"])
    assert counts(t) == before


def test_v2r20_hidden_values_in_solve_consistency_and_a_bound_right_side():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "y")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(d1, "r", "model", "y is x plus one", relation="y = x + 1")
    t.input(d1, "nl", "model", "product", relation="x*y = 6")
    before = counts(t)
    with pytest.raises(HiddenLookupError):
        t.solve(d1, ["r"], ["y"])
    with pytest.raises(HiddenLookupError):
        t.derive(d1, "y = x + 1", from_relations=["r"], binds="y")
    with pytest.raises(HiddenLookupError):
        t.consistency(d1, ["nl"])
    assert counts(t) == before


def test_v21r3_consistency_with_a_hidden_contradicting_value():
    """V21R-3 fixed: no more silent 'consistent'. A hidden value that would change the result
    is a hidden lookup; one that would not (x = z, or x = 5 itself) is not."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "z")
    d1 = t.demand(ROOT, "D1", "one")
    t.deliver(d1, "x")
    t.deliver(d1, "z")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", from_relations=["rx"], binds="x")
    t.input(d1, "r", "model", "x seven", relation="x = 7")
    t.input(d1, "rz", "model", "x is z", relation="x = z")
    t.input(d1, "r5", "model", "x five in D1", relation="x = 5")
    assert t.consistency(ROOT, ["r"]).check == "failed"  # at ROOT the value is visible
    before = counts(t)
    with pytest.raises(HiddenLookupError, match="would change the result"):
        t.consistency(d1, ["r"])
    assert counts(t) == before
    for rel in ("rz", "r5"):
        st = t.consistency(d1, [rel])
        assert (st.check, st.detail) == ("checked", "consistent")
    t.deliver(d1, "x")
    assert t.consistency(d1, ["r"]).check == "failed"


# ===========================================================================
# Withdrawal: taint and re-supply
# ===========================================================================


def test_withdrawal_taints_values_and_the_names_registered_from_the_premise():
    """v2.2 semantics. After m is withdrawn: m itself and r (registered from m) are refused
    everywhere; x's value (resting on m) is visible nowhere, but the name x stays usable, may
    be delivered by name and may be determined again. Earlier answers keep their sets.
    v2.3: a step whose verdict the stale value would change is refused until x is determined
    again (a TraceError, not a CheckError)."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "one")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "m", "value", "m", value=2)
    t.deliver(d1, "m")
    t.input(ROOT, "r", "model", "x is twice m", relation="x = 2*m")
    t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    t.answer(["x"], label="before")
    h_before = t.hypothesis_set("before")
    w = t.withdraw(ROOT, "m", "mass was misread")
    d2 = t.demand(ROOT, "D2", "two")
    assert t.value_visible(d1, "m") is None and "m" not in t.known_values(d1)
    assert t.value_visible(ROOT, "x") is None and t.known_values(ROOT) == {}
    refused = [
        (lambda: t.derive(d1, "m = 2"), "was withdrawn"),
        (lambda: t.deliver(d2, "m"), "was withdrawn"),
        (lambda: t.deliver(d2, "r"), "rests on 'm'"),
        (lambda: t.derive(ROOT, "x = 4", from_relations=["r"]), "rests on 'm'"),
        (lambda: t.reading(ROOT, "cites the law", uses=["r"]), "rests on 'm'"),
        (lambda: t.consistency(ROOT, ["r"]), "rests on 'm'"),
        (lambda: t.answer(["x"], label="after"), "the value of 'x' rests on 'm', which was withdrawn; "
                                                  "determine it again"),
        (lambda: t.withdraw(ROOT, "m", "again"), "already withdrawn"),
    ]
    for attempt, msg in refused:
        before = counts(t)
        with pytest.raises(TraceError, match=re.escape(msg)):
            attempt()
        assert counts(t) == before
    with pytest.raises(TraceError, match="INPUT"):
        t.withdraw(ROOT, "x", "an unknown is not a premise")
    # The name x is still usable: delivered by name, cited by a reading, given a new account.
    assert t.deliver(d2, "x").text.startswith("x, delivered from ROOT")
    t.reading(ROOT, "x is still the quantity asked for", uses=["x"])
    before = counts(t)
    with pytest.raises(TraceError, match=re.escape(  # the old value is stale: determine it again first
            "the step needs the value of x (rests on m), which rests on a withdrawn premise; "
            "determine it again first")) as exc:
        t.derive(ROOT, "x = 4")
    assert not isinstance(exc.value, CheckError) and counts(t) == before
    t.input(ROOT, "m2", "value", "m, read again", value=3)
    t.input(ROOT, "r2", "model", "x is twice m2", relation="x = 2*m2")
    t.derive(ROOT, "x = 6", from_relations=["r2"], binds="x")
    t.answer(["x"], label="after")
    assert {c["name"] for c in t.ledger("after")["commitments"]} == {"m2", "r2"}
    assert t.hypothesis_set("before") == h_before
    led = t.ledger("before")
    assert not any("withdrawn" in s for s in led["warnings"])
    assert [(c["name"], c["withdrawn_at"]) for c in led["withdrawn"]] == [("m", w.id)]


@pytest.mark.parametrize("strict", [False, True])
def test_v22r5_restating_a_withdrawn_value_asks_to_determine_it_again(strict):
    """V22R-5 (note), v2.3: a step that restates a value resting on a withdrawn premise is
    refused with a TraceError naming the withdrawal (not a CheckError, not a found mistake),
    in lenient and strict mode alike; nothing is recorded. The ledger lists x as undetermined
    with a note naming the premise, and answer() still names it."""
    t = Trace("q", strict=strict)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["c"])
    t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    t.withdraw(ROOT, "c", "the table pushes too")
    before = counts(t)
    with pytest.raises(TraceError, match=re.escape("the step needs the value of x (rests on c), which rests on a "
                                                   "withdrawn premise; determine it again first")) as exc:
        t.derive(ROOT, "x = 3")
    assert not isinstance(exc.value, CheckError) and counts(t) == before
    t.input(ROOT, "v", "value", "v", value=1)
    t.answer(["v"])
    led = t.ledger()
    assert led["mistakes"] == []
    assert [(u["name"], u["note"]) for u in led["undetermined"]] == [("x", "its value was withdrawn: it rested on c")]
    with pytest.raises(TraceError, match="rests on 'c', which was withdrawn"):
        t.answer(["x"])


def test_v21r13_a_premise_resting_on_a_withdrawn_one_can_be_withdrawn():
    """V21R-13 (4) fixed: withdrawing d, which rests on the withdrawn c, is recorded."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "complete")
    t.input(ROOT, "d", "model", "rests on c", uses=["c"])
    wc = t.withdraw(ROOT, "c", "drop")
    wd = t.withdraw(ROOT, "d", "also drop")
    assert wd.op == "WITHDRAW" and t.bindings["d"].withdrawn == wd.index
    t.input(ROOT, "v", "value", "v", value=1)
    t.answer(["v"])
    assert [(c["name"], c["withdrawn_at"]) for c in t.ledger()["withdrawn"]] == [("c", wc.id), ("d", wd.id)]
    assert Trace.replay(json.loads(t.to_json())).to_record() == t.to_record()


def _relation_registered(order):
    """s: y = x + 1 is registered before or after x = 3 is fixed from rx (resting on A)."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "A", "recognition", "premise A")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=["A"])
    if order == "before":
        t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")
    t.derive(ROOT, "x = 3", from_relations=["rx"], binds="x")
    if order == "after":
        t.input(ROOT, "s", "model", "y is x plus one", relation="y = x + 1")
    return t


def test_v22r2_a_relation_registered_after_a_value_does_not_rest_on_that_value():
    """V22R-2, v2.3: registering s depends only on the binding steps of the names it mentions,
    never on x's value step, so s is not tainted when A (behind x's value) is withdrawn, in
    either order; consistency() treats the withdrawn value as absent."""
    for order in ("before", "after"):
        t = _relation_registered(order)
        s_step = t.steps[t.bindings["s"].step]
        assert t.value_step["x"] not in s_step.deps
        t.withdraw(ROOT, "A", "A was wrong")
        st = t.consistency(ROOT, ["s"])
        assert (st.check, st.detail) == ("checked", "consistent")


def test_v22r2_taint_of_a_relation_does_not_depend_on_when_it_was_registered():
    """V22R-2 fixed in v2.3: a relation's deps no longer include the value steps of the names
    in its equation, so its taint does not depend on when it was registered."""
    outcomes = {}
    for order in ("before", "after"):
        t = _relation_registered(order)
        t.withdraw(ROOT, "A", "A was wrong")
        t.input(ROOT, "rx4", "model", "x four, revised", relation="x = 4")
        t.derive(ROOT, "x = 4", from_relations=["rx4"], binds="x")
        try:
            outcomes[order] = t.derive(ROOT, "y = 5", from_relations=["s"], binds="y").check
        except TraceError as exc:
            outcomes[order] = type(exc).__name__
    assert outcomes["before"] == outcomes["after"]


def test_v22r2_hypothesis_set_does_not_depend_on_when_a_relation_was_registered():
    """V22R-2 fixed in v2.3: an answer resting on s no longer gets rx and its premise A in its
    hypothesis set when s was registered after x was fixed; in both orders it is {ry, s}."""
    sets = {}
    for order in ("before", "after"):
        t = _relation_registered(order)
        t.input(ROOT, "ry", "model", "y four", relation="y = 4")
        t.derive(ROOT, "y = 4", from_relations=["ry"], binds="y", uses=["s"])
        t.answer(["y"])
        sets[order] = sorted(c["name"] for c in t.ledger()["commitments"])
    assert sets["before"] == ["ry", "s"]
    assert sets["after"] == sets["before"]


@pytest.mark.parametrize("order", ["after", "before"])
def test_v2r22_resupplied_withdrawn_premise_is_warned_as_such(order):
    """regress-5 / fresh-14 fixed: the warning fires whichever came first, says when the
    original was withdrawn, and no longer advises delivering it."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "the account is complete")
    if order == "after":
        w = t.withdraw(ROOT, "c", "test the account without it")
        t.input(ROOT, "c2", "completeness", "the account is complete")
        when = "was withdrawn"
    else:
        t.input(ROOT, "c2", "completeness", "the account is complete")
        w = t.withdraw(ROOT, "c", "test the account without it")
        when = "has since been withdrawn"
    t.input(ROOT, "v", "value", "v", value=1)
    t.answer(["v"])
    warnings = t.ledger()["warnings"]
    assert f"c2 repeats c word for word; c {when} at {w.id}, and c2 was not withdrawn with it" in warnings
    assert not any("deliver the original" in s for s in warnings)


def test_same_description_with_a_different_value_is_warned_for_values_only():
    """regress-1 and probes-14 fixed: the warning keys on the description of a value INPUT
    (any kind with a number); per-object relations sharing a description are not warned."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "b1")
    d2 = t.demand(ROOT, "D2", "b2")
    t.input(d1, "g", "value", "local free-fall acceleration", value="9.8")
    t.input(d2, "g2", "value/model", "local free-fall acceleration", value="9.81")
    unknowns(t, ROOT, "x", "f1", "f2")
    t.input(ROOT, "r", "model", "r", relation="x = g + g2")
    t.derive(ROOT, "x = 1961/100", from_relations=["r"], binds="x")
    t.input(ROOT, "w1", "model", "uniform-field weight", relation="f1 = -2*x")
    t.input(ROOT, "w2", "model", "uniform-field weight", relation="f2 = -3*x")
    t.derive(ROOT, "f1 = -1961/50", from_relations=["w1"], binds="f1")
    t.derive(ROOT, "f2 = -5883/100", from_relations=["w2"], binds="f2")
    t.answer(["f1", "f2"])
    warnings = t.ledger()["warnings"]
    assert "g2 has the same description as g but a different value" in warnings
    assert not any(w.startswith("w2 ") for w in warnings)


def test_v21r8_note_a_corrected_value_is_warned_without_mentioning_the_withdrawal():
    """V21R-8 (second half, still open, pinned): m2 corrects the withdrawn m."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass of A", value=2)
    t.withdraw(ROOT, "m", "misread")
    t.input(ROOT, "m2", "value", "mass of A", value=3)
    t.answer(["m2"])
    warnings = t.ledger()["warnings"]
    assert "m2 has the same description as m but a different value" in warnings
    assert not any("withdrawn" in w for w in warnings)


def test_v21r8_duplicate_of_a_live_resupply_is_flagged():
    """V21R-8, fixed in v2.3: re-supply checks compared only with the first INPUT of a description, so c3
    repeating the live c2 was told only that it repeats the withdrawn c. They now compare with the latest
    earlier copy that is still usable."""
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "complete")
    t.withdraw(ROOT, "c", "test without it")
    t.input(ROOT, "c2", "completeness", "complete")
    t.input(ROOT, "c3", "completeness", "complete")
    t.input(ROOT, "v", "value", "v", value=1)
    t.answer(["v"])
    assert "c3 repeats the INPUT c2 word for word; deliver the original instead of re-supplying it" \
        in t.ledger()["warnings"]


# ===========================================================================
# Several answers, labels and statuses
# ===========================================================================


def test_later_steps_never_enter_an_earlier_answer_or_change_its_set():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "c", "completeness", "complete")
    t.input(ROOT, "r", "model", "x one", relation="x = 1", uses=["c"])
    t.derive(ROOT, "x = 1", from_relations=["r"], binds="x")
    p1 = t.answer(["x"])
    h_before = t.hypothesis_set("p1")
    cone_before = t.cone("p1")
    d = t.demand(ROOT, "D1", "consequence")
    t.deliver(d, "x")
    t.input(ROOT, "s", "model", "y from x", relation="y = x + 1")
    t.derive(ROOT, "y = 2", from_relations=["s"], binds="y")
    t.derive(d, "x = 1")
    p2 = t.answer(["y", "x"], "second")
    t.withdraw(ROOT, "c", "dropped later")
    with pytest.raises(TraceError, match="withdrawn"):
        t.answer(["y"], label="p3")  # y rests on c through x
    assert t.cone("p1") == cone_before and max(cone_before) == p1.index
    assert t.hypothesis_set("p1") == h_before
    assert p2.index in t.cone() and t.ledger()["label"] == "p2"
    assert not any("withdrawn" in w for w in t.ledger("p2")["warnings"])  # recorded before the withdrawal
    with pytest.raises(TraceError, match="already used"):
        t.answer(["x"], label="p1")


@pytest.mark.parametrize("label", ["a\n# injected", "p 1", "p1\n", "*", "[x]", "a|b", "é"])
def test_v2r14_answer_labels_are_restricted(label):
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    with pytest.raises(TraceError, match="labels use"):
        t.answer(["m"], label=label)


def test_v2r13_default_label_is_the_first_free_p_n():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    assert t.answer(["m"], label="p2").tag == "p2"
    assert t.answer(["m"]).tag == "p1"
    assert t.answer(["m"]).tag == "p3"
    assert t.answer(["m"], label="ok-1.2_x").tag == "ok-1.2_x"


def test_v2r5_status_for_one_answer_stays_with_that_answer():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "k", "value", "k", value=3)
    t.answer(["m"], label="pm")
    t.answer(["k"], label="pk")
    t.annotate("k", "NEEDS", countermodel="k = 4 gives another prediction", answer="pk")
    assert not any("k is marked" in w for w in t.ledger("pm")["warnings"])
    assert t.ledger("pk")["commitments"][0]["status"] == "NEEDS"
    with pytest.raises(TraceError, match="no answer labelled"):
        t.annotate("k", "USES", answer="nope")


def test_atwood1_uses_for_p_does_not_prune_the_premise_from_another_answer():
    t = Trace("q")
    unknowns(t, ROOT, "x", "y")
    t.input(ROOT, "c", "model", "c", relation="x = 2")
    t.solve(ROOT, ["c"], ["x"])
    t.answer(["x"], label="p")
    t.input(ROOT, "k", "model", "k", relation="y = 3*x")
    t.solve(ROOT, ["k"], ["y"])
    t.answer(["y"], label="q2")
    t.annotate("c", "USES", note="relative to p only", answer="p")
    assert [c["name"] for c in t.ledger("p")["pruned"]] == ["c"]
    assert [c["name"] for c in t.ledger("q2")["pruned"]] == []
    assert "c" in [c["name"] for c in t.ledger("q2")["commitments"]]
    t.annotate("c", "NEEDS", countermodel="x = 3", answer="q2")
    t.annotate("c", "ENTAILED")  # default: applies where no own status exists
    assert t.ledger("p")["pruned"][0]["status"] == "USES"
    assert t.ledger("q2")["commitments"][0]["status"] == "NEEDS"


def test_v21r11_a_default_status_warns_only_if_the_premise_feeds_no_answer():
    """V21R-11 fixed: a default NEEDS on k (which feeds pk) is not warned in pm; a default on j
    (which feeds nothing) is warned everywhere; a status scoped to pm is warned in pm."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=2)
    t.input(ROOT, "k", "value", "k", value=3)
    t.input(ROOT, "j", "value", "j", value=4)
    t.answer(["m"], label="pm")
    t.answer(["k"], label="pk")
    t.annotate("k", "NEEDS", countermodel="k = 4")
    t.annotate("j", "REQUIRED")
    for label in ("pm", "pk"):
        warnings = t.ledger(label)["warnings"]
        assert not any(w.startswith("k is marked") for w in warnings)
        assert "j is marked REQUIRED but does not feed this answer" in warnings
    t.annotate("k", "NEEDS", countermodel="k = 4", answer="pm")
    assert "k is marked NEEDS but does not feed this answer" in t.ledger("pm")["warnings"]
    assert not any(w.startswith("k is marked") for w in t.ledger("pk")["warnings"])


def test_needs_on_a_non_world_input_is_warned_when_pruned():
    t = Trace("q")
    t.input(ROOT, "ax", "convention", "up is positive")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x one", relation="x = 1", uses=["ax"])
    t.derive(ROOT, "x = 1", from_relations=["r"], binds="x")
    t.answer(["x"])
    t.annotate("ax", "REQUIRED")
    led = t.ledger()
    assert [c["name"] for c in led["pruned"]] == ["ax"]
    assert any(w.startswith("ax is marked REQUIRED") and "not a member" in w for w in led["warnings"])


def test_pruning_by_kind_and_status_and_single_status_warning():
    t = Trace("q")
    unknowns(t, ROOT, "x")
    t.input(ROOT, "axis", "convention", "up is positive")
    t.input(ROOT, "sys", "choice/convention", "the system is A")
    t.input(ROOT, "rec", "recognition/model", "it is a spring")
    t.input(ROOT, "mv", "value/convention", "m", value=2)
    t.input(ROOT, "ent", "identity", "same body")
    t.input(ROOT, "r", "model", "law", relation="x = 2*mv", uses=["axis", "sys", "rec", "ent"])
    t.derive(ROOT, "x = 4", from_relations=["r"], binds="x")
    t.answer(["x"])
    t.annotate("ent", "ENTAILED")
    led = t.ledger()
    assert {c["name"] for c in led["pruned"]} == {"axis", "sys", "ent"}
    assert {c["name"] for c in led["commitments"]} == {"rec", "mv", "r"}
    status_warnings = [w for w in led["warnings"] if "no status" in w]
    assert len(status_warnings) == 1 and status_warnings[0].startswith("3 commitment(s)")
    members = [m["member"] for m in t.hypothesis_set()]
    assert not any("up is positive" in m or "same body" in m for m in members)


def test_unknown_labels_are_restricted():
    t = Trace("q")
    with pytest.raises(TraceError, match="CONTRACT, ENTRY or READING"):
        t.unknown(ROOT, "a", "acc", address="a", label="INPUT", ref="E8")
    with pytest.raises(TraceError, match="quote"):
        t.unknown(ROOT, "a", "acc", address="a", label="ENTRY", ref="E8")
    t.unknown(ROOT, "a", "acc", address="acc( A , t0 )", label="READING", unit="m/s^2")
    with pytest.raises(TraceError, match="address"):
        t.unknown(ROOT, "b", "acc", address="acc(A,t0)", label="READING")


# ===========================================================================
# Entries file and quotes
# ===========================================================================


@needs_entries
def test_load_entries_reads_every_ref_including_the_shared_heading():
    e = entries()
    expected = {f"K{i}" for i in range(1, 17)} | {f"E{i}" for i in range(1, 12)}
    assert set(e) == expected
    assert e["K16"] == e["E1"] and e["K16"].startswith("uniform-motion :=")
    assert e["E2"] != e["E1"]
    assert e["E8"] == ("inertial-acceleration-material-object := For one material-object, its "
                       "net-force-material-object divided by its inertial-mass-material-object.")


@needs_entries
@pytest.mark.parametrize("ref", [f"K{i}" for i in range(1, 17)] + [f"E{i}" for i in range(1, 12)])
def test_every_entry_body_verifies_with_its_original_line_breaks(ref):
    raw = raw_entry_blocks()[ref]
    t = Trace("q", entries=entries())
    st = t.entry(ROOT, ref, raw)
    assert st.op == "ENTRY" and st.ref == ref


@needs_entries
def test_misquotes_and_wrong_entries_are_refused():
    t = Trace("q", entries=entries())
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "E9", E8_RAW)
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "E8", "net force times mass, probably")
    with pytest.raises(TraceError, match="not in the supplied entries"):
        t.entry(ROOT, "E12", "anything at all")
    with pytest.raises(TraceError, match="not verbatim"):
        t.unknown(ROOT, "a", "acc", address="a", label="ENTRY", ref="E7", quote=E8_RAW)
    t.unknown(ROOT, "a", "acc", address="a", label="ENTRY", ref="E8", quote=E8_RAW)
    t.entry(ROOT, "E1", "It is a kinematic path-pattern, not yet a claim about why\nthe motion occurs.")
    assert "27 supplied entries" in t.to_markdown()


@needs_entries
@pytest.mark.parametrize("ref, quote", [
    ("E8", "ass"),
    ("E8", "a"),
    ("E8", "divided"),
    ("E8", "inertial-mass-material-object."),
    ("E8", "rce-material-object divided by"),
    ("E8", "or one material-object"),
    ("E8", "For one material"),
    ("E8", "object, its"),
    ("E8", "FOR one material-object"),
    ("E4", "without being a free"),
])
def test_v2r8_fragments_single_words_and_mid_word_cuts_are_refused(ref, quote):
    t = Trace("q", entries=entries())
    with pytest.raises(TraceError):
        t.entry(ROOT, ref, quote)


@needs_entries
@pytest.mark.parametrize("ref, quote", [
    ("E8", "divided by"),
    ("E8", "net-force-material-object divided by"),
    ("E8", "material-object, its"),
    ("E4", "without being a free-particle."),
    ("E4", "inertial-frame. But"),
])
def test_two_or_more_whole_words_verify(ref, quote):
    Trace("q", entries=entries()).entry(ROOT, ref, quote)


@needs_entries
@pytest.mark.parametrize("ref, quote", [
    ("E7", "inertial-acceleration-material-object :="),
    ("E8", "inertial-acceleration-material-object :="),
    ("E8", ":= For"),
    ("K1", "∈ R;"),       # '∈' has no word character
    ("K4", "+ λu"),       # '+' does not count; 'λu' does
    ("K13", "r2 -"),
])
def test_v21r9_punctuation_is_not_a_word(ref, quote):
    """V21R-9 fixed: a word must contain a word character, so ':=' and other punctuation do
    not count toward the two-word minimum and the bare headword line is refused."""
    t = Trace("q", entries=entries())
    with pytest.raises(TraceError, match="two whole words"):
        t.entry(ROOT, ref, quote)


@needs_entries
def test_v21r9_note_the_headword_plus_one_word_still_fits_two_entries():
    """V21R-9 (residue, note): 'headword := For' has two words and verifies under E7 and E8
    alike, so it does not say which of the two entries was applied."""
    t = Trace("q", entries=entries())
    for ref in ("E7", "E8"):
        t.entry(ROOT, ref, "inertial-acceleration-material-object := For")


@needs_entries
@pytest.mark.parametrize("ref, quote, ok", [
    ("K4", "u, with r0", False),          # 'u' follows 'λ' inside the token 'λu'
    ("K4", "form r0 + λ", False),         # cuts 'λu' after 'λ'
    ("K4", "λu, with", True),
    ("K4", "r0 + λu, with r0 fixed", True),
    ("K4", "and λ real.", True),
    ("K1", "modelled by t ∈ R;", True),
    ("K1", "by t ∈", True),
    ("K13", "r2 - r1", True),
    ("K13", "2 - r1", False),             # cuts 'r2'
    ("E10", "zero-zero pair", True),
    ("E10", "zero pair leaves", False),   # cuts the hyphenated word
])
def test_v22_quote_boundaries_are_unicode_aware(ref, quote, ok):
    """probes-12 / V21R-9 fixed: the word-boundary class is Unicode-aware, so a quote cannot
    start or end inside 'λu'. Checked against the real entries file."""
    t = Trace("q", entries=entries())
    if ok:
        assert t.entry(ROOT, ref, quote).ref == ref
    else:
        with pytest.raises(TraceError, match="not verbatim"):
            t.entry(ROOT, ref, quote)


def test_v2r7_empty_entries_are_refused_and_none_turns_checking_off():
    with pytest.raises(TraceError, match="pass None"):
        Trace("q", entries={})
    t = Trace("q", entries=None)
    t.entry(ROOT, "E8", "net force times mass, probably")  # checking is off, on purpose
    assert "verified against" not in t.to_markdown()


@pytest.mark.skipif(not CURRENT_STATE_MD.exists(), reason="CURRENT_STATE.md not present")
def test_v2r7_entries_loaded_from_the_wrong_file_are_refused():
    e = load_entries(str(CURRENT_STATE_MD))
    assert e == {}
    with pytest.raises(TraceError):
        Trace("q", entries=e)


@needs_entries
def test_v2r9_unknown_quote_only_with_label_entry():
    t = Trace("q", entries=entries())
    for label in ("CONTRACT", "READING"):
        with pytest.raises(TraceError, match="only an unknown introduced by ENTRY"):
            t.unknown(ROOT, "x", "x", address="x", label=label, ref="E8", quote="divided by its")
    assert "x" not in t.bindings


@needs_entries
@pytest.mark.parametrize("ref", ["K16 / E1", "K16/E1", "E1 / K16"])
def test_v2r18_combined_ref_as_written_in_the_source_is_accepted(ref):
    st = Trace("q", entries=entries()).entry(ROOT, ref, "A frame-indexed interval property of a point-particle")
    assert st.ref == ref


@needs_entries
def test_v21r5_combined_ref_with_an_unknown_part_is_refused():
    """V21R-5 fixed, on every step that takes a quote."""
    t = Trace("q", entries=entries())
    q = "divided by its inertial-mass-material-object."
    attempts = [
        lambda: t.entry(ROOT, "E8 / E99", q),
        lambda: t.demand(ROOT, "D", "d", ref="E8 / E99", quote=q),
        lambda: t.unknown(ROOT, "a", "a", address="a", label="ENTRY", ref="E8 / E99", quote=q),
    ]
    for attempt in attempts:
        before = counts(t)
        with pytest.raises(TraceError, match=r"not in the supplied entries \(E99\)"):
            attempt()
        assert counts(t) == before


@needs_entries
def test_v21r5_every_part_of_a_combined_ref_must_hold_the_quote():
    """V21R-5 (second half) fixed: 'E9 / E8' refuses a quote found only in E8, and accepts one
    that both entries contain."""
    t = Trace("q", entries=entries())
    assert "divided by" not in entries()["E9"]
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "E9 / E8", "divided by its inertial-mass-material-object.")
    assert t.entry(ROOT, "E9 / E8", "For one material-object, its").ref == "E9 / E8"
    assert t.entry(ROOT, "E3 / E5", "An inertial-frame is").ref == "E3 / E5"
    with pytest.raises(TraceError, match="not verbatim"):
        t.demand(ROOT, "D", "d", ref="E3 / E5", quote="the standard reference-frame")


@needs_entries
def test_demand_quote_is_verified_and_linked_to_the_latest_entry_step():
    t = Trace("q", entries=entries())
    t.entry(ROOT, "E8", "For one material-object, its net-force-material-object")
    e2 = t.entry(ROOT, "E8", "divided by its inertial-mass-material-object.")
    d = t.demand(ROOT, "D", "net force of A", ref="E8", quote="its net-force-material-object divided by")
    dem = t.steps[-1]
    assert dem.deps == (e2.index,) and dem.text.startswith("\u201cits net-force")
    with pytest.raises(TraceError, match="needs the entry ref"):
        t.demand(ROOT, "D2", "x", quote="divided by its")
    with pytest.raises(TraceError, match="not verbatim"):
        t.demand(ROOT, "D3", "x", ref="E8", quote="net force times mass")
    with pytest.raises(TraceError, match="two whole words"):
        t.demand(ROOT, "D4", "x", ref="E8", quote="divided")
    assert set(t.frames) == {ROOT, d}
    child = t.demand(d, "Dc", "child", ref="E8")
    assert t.steps[-1].deps == ()  # the ENTRY is in ROOT, not in the child's parent D
    assert child in t.frames


@needs_entries
def test_v21r10_note_demand_ref_alone_is_unchecked_and_the_link_reaches_no_cone():
    """V21R-10 (note): ref='E99' without a quote is accepted, and the DEMAND -> ENTRY link is a
    dependency of the DEMAND step only, which no step depends on."""
    t = Trace("q", entries=entries())
    t.demand(ROOT, "X", "some demand", ref="E99")
    e = t.entry(ROOT, "E8", "For one material-object, its net-force-material-object")
    d = t.demand(ROOT, "D", "net force", ref="E8", quote="divided by its")
    unknowns(t, d, "F")
    t.input(d, "rF", "model", "F two", relation="F = 2")
    t.derive(d, "F = 2", from_relations=["rF"], binds="F")
    t.answer(["F"])
    assert e.index not in t.cone()
    assert e.id in [r["step"] for r in t.ledger()["outside_answer"]]


# ===========================================================================
# Replay and markdown
# ===========================================================================


@needs_entries
@pytest.mark.parametrize("strict", [True, False])
def test_every_command_replays_including_the_v21_and_v22_commands(strict, tmp_path):
    t = Trace("q", {"ed": ""}, strict=strict, entries=entries())
    t.entry(ROOT, "E8", E8_RAW, text="")
    d = t.demand(ROOT, "D1", "acc", ref="E8", quote="divided by its inertial-mass-material-object.")
    t.demand(ROOT, "D2", "other", ref="")
    dd = t.demand(d, "D1a", "deep")
    ddd = t.demand(dd, "D1b", "deeper", ref="E9 / E8", quote="For one material-object, its")
    t.entry(d, "K16 / E1", "A frame-indexed interval property of a point-particle", text="")
    t.entry(d, "K4", "r0 + λu, with r0 fixed", text="")
    t.input(ROOT, "m", "value", "mass", value=Fraction(1, 3), unit="")
    t.input(ROOT, "g", "value", "g", value="0.30000000000000001")
    t.input(ROOT, "h", "haze", "haze", value=0)
    t.input(ROOT, "conv", "convention / choice", "axis up")
    t.input(ROOT, "rec", "recognition/model", "a spring", uses=[])
    t.deliver_many(d, ["m", "g", "h", "conv"], text="")
    t.unknown(d, "F", "net force", address="F(A)", label="ENTRY", ref="E8", quote=E8_RAW, unit="N")
    t.unknown(d, "a", "acc", address="a(A)", label="READING", uses=["conv"])
    t.contract(d, "FS", "sum", source="S", binds="fs", relation="F = 2*m + h", uses=[])
    t.reading(d, "law", binds="law", relation="a*m = F")
    t.derive(d, "F = 2/3", from_relations=["fs", "law"], binds="F", uses=["conv"], text="", tag="")
    t.solve(d, ["law"], ["a"], tag="", text="", uses=[])
    t.consistency(d, ["fs", "law"], text="", tag="", uses=[])
    t.deliver_through(dd, "a", text="")
    t.derive(dd, "a = 2")
    t.external(ROOT, "diff", "d/dt", relation="", binds="", uses=[])
    t.open(ROOT, "gap", uses=[])
    t.answer(["a"], "", label="")
    t.withdraw(ROOT, "rec", "not a spring after all")
    t.input(ROOT, "k", "value", "k", value=-2.5)
    t.deliver_through(ddd, "k", text="")  # two levels below the root
    t.answer(["k", "a"], "second")
    t.annotate("m", "ENTAILED", countermodel="", note="")
    t.annotate("g", "NEEDS", countermodel="g = 1", answer="p2")
    unknowns(t, ROOT, "z", "w", "u")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1")
    t.input(ROOT, "rz2", "model", "z two", relation="z = 2")
    t.consistency(ROOT, ["rz", "rz2"], text="deliberate conflict")
    if not strict:
        assert t.derive(ROOT, "z = 2", from_relations=["rz"], name="nz").check == "failed"
        assert t.derive(ROOT, "z = 3", from_relations=["rz"], binds="z").binds == ()
    # v2.2: a joint solve gives one DERIVE per value; a tainted value is determined again.
    t.input(ROOT, "cw", "completeness", "w account complete")
    t.input(ROOT, "rw", "model", "w and u", relation="w + u = 3", uses=["cw"])
    t.input(ROOT, "ru", "model", "u one", relation="u = 1")
    t.solve(ROOT, ["rw", "ru"], ["w", "u"])
    t.withdraw(ROOT, "cw", "account incomplete")
    t.withdraw(ROOT, "rw", "rests on cw")
    t.input(ROOT, "rw2", "model", "w five", relation="w = 5")
    t.derive(ROOT, "w = 5", from_relations=["rw2"], binds="w")
    t.answer(["w", "u"], label="p3")
    record = json.loads(json.dumps(t.to_record()))
    assert set(record["ledgers"]) == {"p1", "p2", "p3"} and record["entries"]
    assert record["ledgers"]["p1"]["conflicts"][0]["detail"].startswith("conflict")
    assert {c["name"] for c in record["ledgers"]["p3"]["commitments"]} == {"rw2", "ru"}
    again = Trace.replay(record)
    assert again.to_record() == t.to_record()
    assert {c["op"] for c in record["commands"]} >= {"deliver", "withdraw", "annotate", "solve", "external",
                                                     "consistency"}
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert main(["validate", str(path)]) == 0
    tampered = json.loads(json.dumps(record))
    tampered["entries"]["E8"] = "edited"
    with pytest.raises(TraceError, match="digest"):
        Trace.replay(tampered)


def test_replay_without_entries_passes_none():
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=1)
    t.entry(ROOT, "E8", "anything goes when checking is off")
    t.answer(["m"])
    record = json.loads(t.to_json())
    assert record["entries"] == {}
    again = Trace.replay(record)
    assert again.entries == {} and again.to_record() == t.to_record()


def test_markdown_escapes_every_free_text_field_in_tables_and_bullets():
    x = "a|b\r\nc\rd\n# e"
    t = Trace("Q" + x, {"k" + x: "v" + x})
    d = t.demand(ROOT, "D|1\n#", "demand" + x, ref="E8" + x)
    t.input(ROOT, "m", "value", "mass" + x, value=2, unit="kg" + x)
    t.deliver(d, "m", text="deliver" + x)
    t.input(d, "c", "recognition", "fact" + x)
    t.unknown(d, "y", "y" + x, address="addr" + x, ref="ref" + x, unit="u" + x)
    t.contract(d, "C" + x, "contract" + x, source="src" + x, binds="r", relation="y = 2*m")
    t.derive(d, "y = 4", from_relations=["r"], binds="y", tag="tag" + x, text="t" + x)
    t.reading(ROOT, "reading" + x)
    t.open(ROOT, "open" + x)
    t.input(ROOT, "w", "recognition", "withdrawn" + x)
    t.withdraw(ROOT, "w", "why" + x)
    t.annotate("m", "NEEDS", countermodel="cm" + x, note="n" + x)
    t.answer(["y"], "answer" + x, label="L1")
    lines = t.to_markdown().splitlines()
    pipe = re.compile(r"(?<!\\)\|")
    for line in lines:
        if line.startswith("|"):
            assert len(pipe.findall(line)) in (7, 8), line
    assert not any(ln.strip() in ("c", "d", "# e", "#") for ln in lines)
    assert not any(ln.startswith("#") and not ln.startswith(("# Hand", "## ", "### ")) for ln in lines)


def test_v21r4_ledger_survives_a_relation_that_divides_by_a_zero_value():
    """V21R-4 fixed: the relation is a conflict row, and the trace renders, saves and replays."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "m", value=0)
    unknowns(t, ROOT, "a", "F", "x")
    t.input(ROOT, "law", "model", "a = F/m", relation="a = F/m")
    t.input(ROOT, "rx", "model", "x one", relation="x = 1", uses=["law"])
    t.derive(ROOT, "x = 1", from_relations=["rx"], binds="x")
    t.answer(["x"])
    led = t.ledger()
    assert "law" in [c["name"] for c in led["commitments"]]
    assert [c["ref"] for c in led["conflicts"]] == ["law"]
    assert "cannot be evaluated" in led["conflicts"][0]["detail"] and "division by zero" in led["conflicts"][0]["detail"]
    assert "the answer rests on law, which the trace's own values make undefined" in led["warnings"]
    assert "### Conflicts" in t.to_markdown()
    assert Trace.replay(json.loads(t.to_json())).to_record() == t.to_record()


def test_v22_undefined_claim_or_relation_is_a_mistake_or_conflict_not_a_crash():
    """v2.2 _verdict: a claim that divides by a zero value is a found mistake; a cited relation
    that does is a conflict; consistency() records a conflict. Strict mode raises CheckError
    for the derive and records the consistency conflict."""
    for strict in (False, True):
        t = Trace("q", strict=strict)
        t.input(ROOT, "m", "value", "m", value=0)
        unknowns(t, ROOT, "a", "F")
        t.input(ROOT, "law", "model", "a = F/m", relation="a = F/m")
        cases = [(lambda: t.derive(ROOT, "a = 1/m"), "mistake: the claim cannot be evaluated"),
                 (lambda: t.derive(ROOT, "a = 2", from_relations=["law"]),
                  "conflict: relation law cannot be evaluated")]
        for make, prefix in cases:
            if strict:
                with pytest.raises(CheckError, match=re.escape(prefix)):
                    make()
            else:
                st = make()
                assert st.check == "failed" and st.detail.startswith(prefix) and "division by zero" in st.detail
        cons = t.consistency(ROOT, ["law"])
        assert cons.check == "failed" and cons.detail.startswith("conflict")


@pytest.mark.parametrize("claim", ["10 = (2*g*h)**0.5", "1 = h % 2"])
def test_v22r3_unsupported_syntax_in_a_true_claim_is_not_a_found_mistake(claim):
    """V22R-3 fixed in v2.3: only UndefinedValue makes a claim a mistake; a rational root is
    evaluated exactly and '%' is refused at entry, so neither true claim is a found mistake."""
    t = Trace("q", strict=False)
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "h", "value", "h", value=5)
    before = counts(t)
    try:
        st = t.derive(ROOT, claim)
    except TraceError as exc:  # refusing the syntax outright would also do
        assert not isinstance(exc, CheckError) and counts(t) == before
        return
    assert st.check != "failed"


def test_v22r3_a_square_root_relation_in_the_cone_is_not_a_conflict():
    """V22R-3 fixed in v2.3: v = (2*g*h)**0.5 with g = 10, h = 5 evaluates exactly to v = 10, so
    the global check no longer reports it as undefined."""
    t = Trace("q")
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "h", "value", "h", value=5)
    unknowns(t, ROOT, "v", "z")
    t.input(ROOT, "rel", "model", "free-fall speed from rest", relation="v = (2*g*h)**0.5")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1")
    t.derive(ROOT, "z = 1", from_relations=["rz"], binds="z", uses=["rel"])
    t.answer(["z"])
    led = t.ledger()
    assert led["conflicts"] == []
    assert not any("undefined" in w for w in led["warnings"])


def test_v22r3_a_square_root_claim_and_relation_check_and_unsupported_syntax_is_refused_at_entry():
    """V22R-3, v2.3: (2*g*h)**0.5 with g = 10, h = 5 is exactly 10, so the sqrt claim checks, a
    cited sqrt relation checks and its consistency check is consistent. An irrational root is
    unchecked, never a mistake. '%' is refused at entry, in a claim or a relation, and nothing
    is recorded."""
    t = Trace("q", strict=False)
    t.input(ROOT, "g", "value", "g", value=10)
    t.input(ROOT, "h", "value", "h", value=5)
    st = t.derive(ROOT, "10 = (2*g*h)**0.5")
    assert (st.check, st.detail) == ("checked", "identity once the visible values are substituted "
                                                "(no independent content)")
    unknowns(t, ROOT, "v")
    t.input(ROOT, "rel", "model", "free-fall speed from rest", relation="v = (2*g*h)**0.5")
    cited = t.derive(ROOT, "v = 10", from_relations=["rel"])
    assert (cited.check, cited.detail) == ("checked", "follows from rel")
    cons = t.consistency(ROOT, ["rel"])
    assert (cons.check, cons.detail) == ("checked", "consistent")
    irrational = t.derive(ROOT, "v = (2*h)**0.5")
    assert (irrational.check, irrational.detail) == ("unchecked", "nonlinear (an irrational power cannot be "
                                                                  "checked exactly); not checked")
    before = counts(t)
    refusal = re.escape("outside the checker's syntax (Mod) in 'h % 2'; use numbers, names, + - * / and ** "
                        "(a root is **0.5 or **(1/3))")
    with pytest.raises(TraceError, match=refusal):
        t.derive(ROOT, "1 = h % 2")
    with pytest.raises(TraceError, match=refusal):
        t.input(ROOT, "rm", "model", "v from h mod 2", relation="v = h % 2")
    assert counts(t) == before
    assert t.derive(ROOT, "v = 10", from_relations=["rel"], binds="v").check == "checked" and t.values["v"] == 10


def test_v22_failed_determination_binds_nothing():
    """regress-10 fixed: a failed derive(binds=) no longer lists x in binds, so the markdown
    shows no '=> x'. A name= relation is still bound (and listed) because it was registered."""
    t = Trace("q", strict=False)
    unknowns(t, ROOT, "x")
    t.input(ROOT, "r", "model", "x two", relation="x = 2")
    st = t.derive(ROOT, "x = 3", from_relations=["r"], binds="x")
    assert st.binds == () and st.detail.endswith("; x not determined") and "x" not in t.values
    named = t.derive(ROOT, "x = 3", from_relations=["r"], name="bad")
    assert named.binds == ("bad",) and t.bindings["bad"].sort == "relation"
    row = next(ln for ln in t.to_markdown().splitlines() if ln.startswith(f"| {st.id} "))
    assert "⇒" not in row


def _dense_solve(k, seed=1):
    rng = random.Random(seed)
    t = Trace("q")
    names = [f"x{i}" for i in range(k)]
    unknowns(t, ROOT, *names)
    sol = {n: rng.randint(-5, 5) for n in names}
    rels = []
    for j in range(k):
        co = {n: rng.randint(1, 4) for n in names}
        rhs = sum(co[n] * sol[n] for n in names)
        t.input(ROOT, f"r{j}", "model", f"r{j}", relation=" + ".join(f"{co[n]}*{n}" for n in names) + f" = {rhs}")
        rels.append(f"r{j}")
    return t, rels, names, sol


@pytest.mark.parametrize("k", [8, 10])
def test_v21_6_dense_solve_is_fast_enough(k):
    """fresh-4 fixed: the dense 10x10 solve took 12.6 s in v2.1. Measured on v2.2: about 1 s
    for k = 8 (the largest exhaustive case) and 0.3 s for k = 10 (greedy)."""
    t, rels, names, sol = _dense_solve(k)
    start = time.perf_counter()
    t.solve(ROOT, rels, names)
    assert time.perf_counter() - start < 6
    assert t.values == sol


# ===========================================================================
# Deliberately open gaps (documented, not failures)
#
# Out of reach by design in v2.2 and not tested beyond the pins below:
# * the observation side of a trial (only the prediction side of H is built);
# * the C3 budget;
# * editions (the edition mapping is recorded and digested, never checked);
# * explicit RETURN (results flow up implicitly; account scopes are frames);
# * conditional branches: sibling frames are not exclusive alternatives and
#   withdrawal is trace-wide (pinned below);
# * units (pinned below);
# * a minimum-size citation search beyond 8 relations (pinned below).
# ===========================================================================


def _citation_detail(junk):
    """Cite [rxy, ry, junk..., rx] to derive x = 3; rx alone suffices."""
    t = Trace("q")
    unknowns(t, ROOT, "x", "y", *[f"j{i}" for i in range(junk)])
    t.input(ROOT, "rxy", "model", "sum", relation="x + y = 5")
    t.input(ROOT, "ry", "model", "y two", relation="y = 2")
    for i in range(junk):
        t.input(ROOT, f"d{i}", "model", f"junk {i}", relation=f"j{i} = {i}")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    cites = ["rxy", "ry"] + [f"d{i}" for i in range(junk)] + ["rx"]
    return len(cites), t.derive(ROOT, "x = 3", from_relations=cites, binds="x").detail


def test_open_minimum_size_citation_search_stops_at_eight():
    """Open gap: up to 8 citations the smallest set ({rx}) is kept; at 9 the greedy pass keeps
    the irreducible but larger {rxy, ry}, so one more irrelevant citation changes H."""
    assert _citation_detail(5)[0] == 8 and _citation_detail(5)[1].startswith("follows from rx ")
    n, detail = _citation_detail(6)
    assert n == 9 and detail.startswith("follows from rxy, ry ")


def test_open_withdrawal_is_trace_wide_not_branch_local():
    """Former V2R-6, now a documented open gap (conditional branches)."""
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "main account")
    d2 = t.demand(ROOT, "D2", "diagnostic branch")
    t.input(ROOT, "c", "completeness", "the account is complete")
    t.deliver(d1, "c")
    t.deliver(d2, "c")
    t.withdraw(d2, "c", "the diagnostic branch drops completeness")
    with pytest.raises(TraceError, match="withdrawn"):
        t.reading(d1, "the main account still rests on completeness", uses=["c"])


def test_open_sibling_branches_are_not_exclusive():
    t = Trace("q")
    t.demand(ROOT, "Bin", "internal candidate")
    t.demand(ROOT, "Bout", "external candidate")
    t.input("Bin", "q_in", "model", "the push is internal")
    t.input("Bout", "q_out", "model", "the push is external")
    assert t.reading(ROOT, "both at once", uses=["q_in", "q_out"]).op == "READING"


def test_open_units_are_not_checked():
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2, unit="kg")
    t.input(ROOT, "L", "value", "length", value=3, unit="m")
    t.unknown(ROOT, "x", "a force", address="x", ref="C", unit="N")
    t.input(ROOT, "r", "model", "mass plus length", relation="x = m + L")
    assert t.derive(ROOT, "x = 5", from_relations=["r"], binds="x").check == "checked"
