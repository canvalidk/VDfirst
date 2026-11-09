"""Tests for the hand-trace recorder. Tests are the API contract."""

import json
from fractions import Fraction

import pytest

from handtrace import (
    INPUT_KINDS,
    ROOT,
    CheckError,
    Form,
    HiddenLookupError,
    Nonlinear,
    Trace,
    TraceError,
    entails,
    main,
    parse_equation,
    parse_expression,
    solve_linear,
)


# -- exact arithmetic --------------------------------------------------------


def test_decimal_literals_are_exact():
    form, names = parse_expression("9.8")
    assert form.const == Fraction(49, 5) and names == ()


def test_linear_form_and_substitution():
    form, names = parse_expression("3*a - T + 147/5", {"T": Fraction(1)})
    assert names == ("a", "T")
    assert form.as_dict() == {"a": 3}
    assert form.const == Fraction(147, 5) - 1


def test_product_of_unknowns_is_nonlinear_until_values_arrive():
    with pytest.raises(Nonlinear):
        parse_expression("m*g")
    form, _ = parse_expression("m*g", {"m": Fraction(3), "g": Fraction(49, 5)})
    assert form.const == Fraction(147, 5)


def test_division_by_zero_and_bad_syntax():
    with pytest.raises(TraceError):
        parse_expression("1/0")
    with pytest.raises(TraceError):
        parse_expression("sqrt(2)")
    with pytest.raises(TraceError):
        parse_equation("a = b = c")


def test_entailment_is_linear_span():
    r1, _ = parse_equation("3*a = T - 147/5")
    r2, _ = parse_equation("-5*a = T - 49")
    good, _ = parse_equation("8*a = 98/5")
    bad, _ = parse_equation("8*a = 98")
    assert entails([r1, r2], good)
    assert not entails([r1, r2], bad)
    assert not entails([], good)


def test_solve_unique_family_inconsistent():
    r1, _ = parse_equation("3*a = T - 147/5")
    r2, _ = parse_equation("-5*a = T - 49")
    out = solve_linear([r1, r2], ["a", "T"])
    assert out["status"] == "unique"
    assert out["values"] == {"a": Fraction(49, 20), "T": Fraction(147, 4)}
    family = solve_linear([r1], ["a", "T"])
    assert family["status"] == "family" and family["rank"] == 1
    clash, _ = parse_equation("3*a = T")
    clash2, _ = parse_equation("3*a = T + 1")
    assert solve_linear([clash, clash2], ["a", "T"])["status"] == "inconsistent"


# -- building traces ------------------------------------------------------------


E8 = ("For one material-object, its net-force-material-object divided by its "
      "inertial-mass-material-object.")


def atwood(strict=True, deliver_g=True):
    """A compact Atwood trace on one upward axis."""
    t = Trace("Atwood: accelerations and tension", {"name": "Design 2.1 Draft 1"}, strict=strict)
    for k, m in ((1, 3), (2, 5)):
        d = t.demand(ROOT, f"D{k}", f"inertial-acceleration-material-object(B{k}, t0, R)")
        t.entry(d, "E8", E8)
        t.input(d, f"m{k}", "value", f"inertial mass of B{k}", value=m, unit="kg")
        if k == 1:
            t.input(d, "g", "value", "local free-fall acceleration", value="9.8", unit="m/s^2")
        elif deliver_g:
            t.deliver(d, "g")
        t.input(d, f"peqv{k}", "identity", f"the gravitational mass of B{k} is m(B{k})")
        t.unknown(d, f"fG{k}", f"weight on B{k}", address=f"(i_G{k}, B{k}, t0)", ref="C-CM, S§9.4")
        t.input(d, f"w{k}", "model", "uniform-field weight", relation=f"fG{k} = -m{k}*g", uses=[f"peqv{k}"])
        t.derive(d, f"fG{k} = {-m * Fraction(49, 5)}", from_relations=[f"w{k}"], binds=f"fG{k}", tag=f"weight{k}")
        t.unknown(d, f"T{k}", f"string force on B{k}", address=f"(i_S{k}, B{k}, t0)", ref="C-CM, S§9.4")
        t.unknown(d, f"a{k}", f"acceleration of B{k}", address=f"a(B{k}, t0, R)", label="ENTRY", ref="E8",
                  quote=E8, unit="m/s^2")
        t.contract(d, "C-FS", "net force is the sum of the members", source="S§8.1", binds=f"law{k}",
                   relation=f"m{k}*a{k} = fG{k} + T{k}")
    return t


def finish(t):
    t.input(ROOT, "meq", "model", "ideal string over an ideal pulley: equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "length constraint differentiated twice", relation="a1 + a2 = 0",
               binds="kin")
    t.solve(ROOT, ["law1", "law2", "meq", "kin"], ["a1", "a2", "T1", "T2"], tag="solve")
    t.answer(["a1", "a2", "T1"], "accelerations and tension")
    return t


def test_atwood_solves_exactly():
    t = finish(atwood())
    assert t.values["a1"] == Fraction(49, 20)
    assert t.values["a2"] == Fraction(-49, 20)
    assert t.values["T1"] == Fraction(147, 4)


def test_pending_state_reports_four_unknowns_two_relations():
    t = atwood()
    st = t.solve(ROOT, ["law1", "law2"], ["a1", "a2", "T1", "T2"], tag="pending")
    assert "underdetermined" in st.detail and "rank 2" in st.detail
    assert "a1" not in t.values


def test_hidden_lookup_is_refused_until_delivered():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "first")
    d2 = t.demand(ROOT, "D2", "second")
    t.input(d1, "g", "value", "local g", value="9.8")
    with pytest.raises(HiddenLookupError, match="g"):
        t.derive(d2, "-5*g = -49")
    st = t.deliver(d2, "g")
    assert "local g" in st.text and "49/5" in st.text
    assert t.derive(d2, "-5*g = -49").check == "checked"


def test_results_flow_up_but_not_sideways():
    t = Trace("q")
    d1 = t.demand(ROOT, "D1", "first")
    d11 = t.demand(d1, "D1a", "child")
    t.input(d11, "m", "value", "mass", value=3)
    assert t.derive(d1, "2*m = 6").check == "checked"  # parent sees child's result
    d2 = t.demand(ROOT, "D2", "sibling")
    with pytest.raises(HiddenLookupError):
        t.derive(d2, "m = 3")


def test_values_determined_above_need_delivery_below():
    t = finish(atwood())
    # a1 was determined at the root; frame D1 may not use that value without delivery
    t2 = atwood()
    t2.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t2.external(ROOT, "differentiation", "coupling", relation="a1 + a2 = 0", binds="kin")
    t2.solve(ROOT, ["law1", "law2", "meq", "kin"], ["a1", "a2", "T1", "T2"])
    assert t2.value_visible("D1", "a1") is None
    with pytest.raises(TraceError):
        t2.deliver("D1", "m1")  # already visible there
    t2.deliver("D1", "a1")
    assert t2.value_visible("D1", "a1") is not None
    assert t.values["T1"] == t.values["T2"]


def test_wrong_arithmetic_raises_in_strict_mode():
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=3)
    with pytest.raises(CheckError):
        t.derive(ROOT, "m*2 = 7")
    assert len(t.steps) == 1  # nothing recorded


def test_wrong_arithmetic_is_a_found_mistake_in_lenient_mode():
    t = atwood(strict=False)
    t.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "coupling", relation="a1 + a2 = 0", binds="kin")
    t.derive(ROOT, "3*a1 + 5*a1 = 98/5", from_relations=["law1", "law2", "meq", "kin"], name="n5")
    bad = t.derive(ROOT, "2*a1 + 5*a1 = 98/5", from_relations=["law1", "law2", "meq", "kin"], tag="slip")
    assert bad.check == "failed"
    t.solve(ROOT, ["law1", "law2", "meq", "kin"], ["a1", "a2", "T1", "T2"])
    t.answer(["a1"])
    led = t.ledger()
    assert [f["step"] for f in led["mistakes"]] == [bad.id]
    assert led["conflicts"] == []


def test_add_versus_subtract_slip_is_caught():
    """On one upward axis the two relations must be subtracted, not added."""
    t = atwood()
    t.input(ROOT, "meq", "model", "equal tensions", relation="T1 = T2")
    t.external(ROOT, "differentiation", "coupling", relation="a1 + a2 = 0", binds="kin")
    with pytest.raises(CheckError):
        t.derive(ROOT, "(3 + 5)*a1 = 147/5 + 49", from_relations=["law1", "law2", "meq", "kin"])
    ok = t.derive(ROOT, "(3 + 5)*a1 = 49 - 147/5", from_relations=["law1", "law2", "meq", "kin"])
    assert ok.check == "checked"


def test_determined_values_must_cite_relations_and_read_name_equals():
    t = Trace("q")
    t.unknown(ROOT, "x", "a quantity", address="(x)", ref="test")
    with pytest.raises(TraceError, match="cite"):
        t.derive(ROOT, "x = 3", binds="x")
    t.input(ROOT, "r", "model", "relation", relation="2*x = 6")
    with pytest.raises(TraceError, match="must read"):
        t.derive(ROOT, "6 = 2*x", binds="x", from_relations=["r"])
    t.derive(ROOT, "x = 3", binds="x", from_relations=["r"])
    assert t.values["x"] == 3


def test_unknown_addresses_must_be_distinct():
    t = Trace("q")
    t.unknown(ROOT, "T1", "string force", address="(i_S1, B1, t0)", ref="C-CM")
    with pytest.raises(TraceError, match="address"):
        t.unknown(ROOT, "T2", "string force", address="(i_S1, B1, t0)", ref="C-CM")


def test_input_kinds_and_labels_are_enforced():
    t = Trace("q")
    with pytest.raises(TraceError, match="kind"):
        t.input(ROOT, "x", "assumption", "something")
    with pytest.raises(TraceError, match="kind 'value'"):
        t.input(ROOT, "x", "model", "a number", value=3)
    with pytest.raises(TraceError, match="source"):
        t.contract(ROOT, "C-X", "a connection", source="")
    with pytest.raises(TraceError, match="quote"):
        t.entry(ROOT, "E8", "")
    assert "normalization" in INPUT_KINDS and "model" in INPUT_KINDS


def test_facts_and_relations_cannot_enter_arithmetic():
    t = Trace("q")
    t.input(ROOT, "taut", "recognition", "the string is taut")
    with pytest.raises(TraceError, match="not a quantity"):
        t.derive(ROOT, "taut = 1")


def test_ledger_sorts_by_answer_provenance():
    t = finish(atwood())
    t.annotate("m1", "NEEDS", countermodel="m1 = 4 kg gives a = 49/45")
    led = t.ledger()
    names = [c["name"] for c in led["commitments"]]
    assert {"m1", "m2", "g", "peqv1", "peqv2", "w1", "w2", "meq"} <= set(names)
    assert any(s["op"] == "EXTERNAL" for s in led["step_members"])
    assert any(t_["ref"].startswith("C-FS") for t_ in led["theory"])
    assert any("no status" in w for w in led["warnings"])


def test_unused_inputs_are_not_members():
    t = atwood()
    t.input(ROOT, "paint", "recognition", "the blocks are painted red")
    finish(t)
    led = t.ledger()
    assert "paint" in [c["name"] for c in led["not_in_answer"]]
    members = " ".join(m["member"] for m in t.hypothesis_set())
    assert "painted" not in members


def test_marking_an_unused_input_needs_raises_a_warning():
    t = atwood()
    t.input(ROOT, "paint", "recognition", "the blocks are painted red")
    finish(t)
    t.annotate("paint", "NEEDS", countermodel="none really")
    assert any("paint" in w for w in t.ledger()["warnings"])


def test_needs_requires_a_countermodel():
    t = finish(atwood())
    with pytest.raises(TraceError, match="countermodel"):
        t.annotate("m1", "NEEDS")
    t.annotate("m1", "REQUIRED")


def test_hypothesis_set_shape():
    t = finish(atwood())
    h = t.hypothesis_set()
    assert h[0]["id"] == "p"
    assert any(m["member"].startswith("not (m1 = 3 kg") for m in h)
    assert any(m["id"].startswith("M") for m in h)


def test_answer_rules():
    t = atwood()
    with pytest.raises(TraceError):
        t.answer(["a1"])  # no value yet
    finish(t)
    late = t.input(ROOT, "x", "recognition", "a consequence recorded after the answer")
    assert late.index not in t.cone()
    assert "x" in [c["name"] for c in t.ledger()["not_in_answer"]]


def test_record_replays_and_detects_tampering(tmp_path):
    t = finish(atwood())
    t.annotate("m1", "NEEDS", countermodel="m1 = 4 kg gives a = 49/45")
    record = t.to_record()
    again = Trace.replay(json.loads(json.dumps(record)))
    assert again.values == t.values
    tampered = json.loads(json.dumps(record))
    tampered["steps"][0]["text"] = "edited"
    with pytest.raises(TraceError, match="digest"):
        Trace.replay(tampered)
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert main(["validate", str(path)]) == 0
    assert main(["render", str(path)]) == 0
    assert main(["nonsense"]) == 2


def test_markdown_mentions_labels_and_ledger():
    md = finish(atwood()).to_markdown()
    for word in ("ENTRY", "INPUT", "CONTRACT", "DERIVE", "EXTERNAL", "DELIVER", "Hypothesis set",
                 "not checked"):
        assert word in md
