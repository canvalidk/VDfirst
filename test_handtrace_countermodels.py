"""Checked statuses: check_countermodel, check_entailed and annotate(..., check=).

A status's countermodel is checked by rebuilding the answer from its premise
relations and supplied values, applying the countermodel, and solving
exactly. The Atwood countermodels of T§10(b) are reproduced from the
recorded premises alone.
"""

import json

import pytest

import handtrace_example_atwood as atwood
from handtrace import ROOT, Trace, TraceError


def U(t, name, frame=ROOT):
    t.unknown(frame, name, name, address=f"({name})", label="READING")


def lever():
    """F = k*x with k supplied; x fixed by a measured relation; answer F."""
    t = Trace("q")
    for n in ("F", "x"):
        U(t, n)
    t.input(ROOT, "k", "value", "spring constant", value=20, unit="N/m")
    t.input(ROOT, "rec", "recognition", "the body is a linear spring")
    t.input(ROOT, "hooke", "model", "Hooke's law", relation="F = k*x", uses=["rec"])
    t.input(ROOT, "ext", "model", "measured extension", relation="x = 1/10")
    t.input(ROOT, "conv", "convention", "extension positive outward", uses=["ext"])
    t.derive(ROOT, "x = 1/10", binds="x", from_relations=["ext"])
    t.derive(ROOT, "F = 2", binds="F", from_relations=["hooke"], uses=["conv"])
    t.answer(["F"], label="p")
    return t


# -- verdicts -----------------------------------------------------------------------------------------------


def test_a_changed_value_refutes_p():
    r = lever().check_countermodel("k", answer="p", replace={"k": 30})
    assert r["verdict"] == "refutes p" and r["detail"] == "F = 3 (was 2)" and r["violates"] is True
    assert r["outside"] == {}


def test_a_changed_relation_refutes_p_and_violates_the_premise():
    r = lever().check_countermodel("hooke", answer="p", replace={"hooke": "F = k*x + 1"})
    assert r["summary"] == "refutes p: F = 3 (was 2)" and r["violates"] is True


def test_a_countermodel_that_leaves_the_premise_true_is_flagged():
    r = lever().check_countermodel("hooke", answer="p", replace={"hooke": "F = x*k"})
    assert r["verdict"] == "p still follows" and r["violates"] is False


def test_dropping_a_precondition_leaves_p_open():
    r = lever().check_countermodel("rec", answer="p", drop_dependents=True)
    assert r["verdict"] == "p does not follow" and r["detail"] == "F left open" and r["changed"] == ["hooke"]


def test_an_added_quantity_is_free_unless_given_a_value():
    t = lever()
    free = t.check_countermodel("hooke", answer="p", replace={"hooke": "F = k*x + c"})
    assert free["verdict"] == "p does not follow"
    fixed = t.check_countermodel("hooke", answer="p", replace={"hooke": "F = k*x + c"}, values={"c": "1/2"})
    assert fixed["summary"] == "refutes p: F = 5/2 (was 2)"


def test_an_inconsistent_countermodel_is_no_world():
    r = lever().check_countermodel("hooke", answer="p", add=["x = 1/5"])
    assert r["verdict"] == "inconsistent"


def test_changing_a_relation_that_does_not_rest_on_the_premise_is_flagged():
    r = lever().check_countermodel("rec", answer="p", replace={"ext": "x = 1/5"})
    assert r["verdict"] == "refutes p" and r["outside"] == {"ext": ["ext"]}


def test_names_must_be_premises_of_the_answer():
    t = lever()
    with pytest.raises(TraceError, match="not a premise relation or supplied value"):
        t.check_countermodel("k", answer="p", replace={"x": 3})  # x is derived, not supplied
    with pytest.raises(TraceError, match="constrain it with add="):
        t.check_countermodel("k", answer="p", values={"x": 3})
    with pytest.raises(TraceError, match="not bound by an INPUT"):
        t.check_countermodel("F", answer="p")


def test_entailed_checks_the_premise_follows_from_the_others():
    t = lever()
    t.input(ROOT, "dup", "model", "x again, from a second reading", relation="10*x = 1")
    U(t, "y")
    t.input(ROOT, "ry", "model", "y", relation="y = 1")
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"], uses=["dup"])
    t.answer(["F", "y"], label="q")
    assert t.check_entailed("dup", answer="q")["verdict"] == "entailed"
    assert t.check_entailed("dup", answer="q", by=["ext"])["summary"] == "entailed by ext"
    assert t.check_entailed("dup", answer="q", by=["ry"])["verdict"] == "not entailed"
    assert t.check_entailed("rec", answer="q")["verdict"] == "cannot check"


def test_a_recorded_root_makes_a_changed_square_inconsistent():
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "rx", "model", "x", relation="x*x = 4")
    t.external(ROOT, "root extraction", "the positive root", relation="x = 2", binds="sq", uses=["rx"])
    t.derive(ROOT, "x = 2", binds="x", from_relations=["sq"])
    t.answer(["x"], label="p")
    assert t.check_countermodel("rx", answer="p", replace={"rx": "x*x = 9"})["verdict"] == "inconsistent"
    r = t.check_countermodel("rx", answer="p", replace={"rx": "x*x = 9"}, remove=["sq"], add=["x = 3"])
    assert r["summary"] == "refutes p: x = 3 (was 2)"


def test_a_baseline_that_does_not_reproduce_p_cannot_be_checked():
    t = Trace("q", strict=False)
    U(t, "x")
    t.input(ROOT, "rx", "model", "x", relation="x*x = 4")
    st = t.derive(ROOT, "x = 2", from_relations=["rx"], name="root")  # unchecked: nonlinear citation
    assert st.check == "unchecked"
    t.derive(ROOT, "x = 2", binds="x", from_relations=["root"])
    t.answer(["x"], label="p")
    r = t.check_countermodel("rx", answer="p", replace={"rx": "x*x = 9"})
    assert r["verdict"] == "cannot check" and "do not reproduce the answer" in r["detail"]
    t.annotate("rx", "NEEDS", countermodel="x*x = 9", answer="p", check={"replace": {"rx": "x*x = 9"}})
    assert any(w.startswith("the check of rx could not be made") for w in t.ledger("p")["warnings"])


# -- annotate(..., check=) -----------------------------------------------------------------------------------


def test_checked_statuses_are_shown_and_warned_about():
    t = lever()
    t.annotate("k", "NEEDS", countermodel="a stiffer spring", answer="p", check={"replace": {"k": 30}})
    t.annotate("conv", "USES", answer="p", check={})
    t.annotate("ext", "NEEDS", countermodel="the same reading twice", answer="p",
               check={"replace": {"ext": "x = 1/10"}})
    t.annotate("hooke", "ENTAILED", answer="p", check={"entailed_by": ["ext"]})
    led = t.ledger("p")
    k = next(c for c in led["commitments"] if c["name"] == "k")
    assert k["check"] == "refutes p: F = 3 (was 2)"
    w = led["warnings"]
    assert "the check of ext does not support NEEDS: p still follows" in w
    assert "the countermodel for ext leaves ext true, so it is not a countermodel to it" in w
    assert "the check of hooke does not support ENTAILED: not entailed by ext" in w
    assert not any(x.startswith("the check of k") or x.startswith("the check of conv") for x in w)
    md = t.to_markdown()
    assert "a stiffer spring [check: refutes p: F = 3 (was 2)]" in md


def test_checked_statuses_need_an_answer_and_well_formed_checks():
    t = lever()
    with pytest.raises(TraceError, match="needs answer="):
        t.annotate("k", "NEEDS", countermodel="x", check={"replace": {"k": 3}})
    with pytest.raises(TraceError, match="malformed check"):
        t.annotate("k", "NEEDS", countermodel="x", answer="p", check={"swap": {"k": 3}})
    with pytest.raises(TraceError, match="only entailed_by"):
        t.annotate("k", "ENTAILED", answer="p", check={"replace": {"k": 3}})


def test_checked_statuses_replay():
    t = lever()
    t.annotate("k", "NEEDS", countermodel="a stiffer spring", answer="p", check={"replace": {"k": "30"}})
    t.annotate("hooke", "ENTAILED", answer="p", check={"entailed_by": ["ext"]})
    rec = json.loads(t.to_json())
    assert Trace.replay(rec).to_record()["sha256"] == rec["sha256"]


def test_unchecked_annotations_keep_old_records_valid():
    t = lever()
    t.annotate("k", "NEEDS", countermodel="a stiffer spring", answer="p")
    led = t.ledger("p")
    assert "check" not in next(c for c in led["commitments"] if c["name"] == "k")


# -- the Atwood countermodels of T§10(b), from the recorded premises ----------------------------------------


@pytest.fixture(scope="module")
def at():
    return atwood.build()


@pytest.mark.parametrize("premise,spec,a1", [
    ("m1", {"replace": {"m1": 4}}, "49/45"),                                                       # CM1
    ("rin", {"replace": {"e8rel1": "a1 = Fnet1/m1 - 1", "e8rel2": "a2 = Fnet2/m2 - 1"}}, "27/10"),  # CM2
    ("Eb", {"replace": {"meq": "T2 = T1 + 1*a1"}}, "98/45"),                                        # CM4
    ("Eb", {"replace": {"meq": "T2 = T1 + 4/5"}}, "47/20"),                                         # CM5 descending
    ("Eb", {"replace": {"meq": "T2 = T1 - 4/5"}}, "51/20"),                                         # CM5 ascending
    ("comp1", {"replace": {"sum1": "Fnet1 = fG1 + T1 - 1"}}, "93/40"),                              # CM6
    ("m2", {"replace": {"m2": 6}}, "49/15"),
    ("comp2", {"replace": {"sum2": "Fnet2 = fG2 + T2 - 1"}}, "103/40"),
])
def test_the_source_countermodels_are_reproduced(at, premise, spec, a1):
    r = at.check_countermodel(premise, answer="p", **spec)
    assert r["verdict"] == "refutes p" and r["detail"].startswith(f"a1 = {a1} (was 49/20)") and r["outside"] == {}


def test_p_eqv_is_not_entailed_by_the_recorded_weight_and_g(at):
    assert at.check_entailed("peqv1", answer="p", by=["w1", "g"])["verdict"] == "not entailed"
    cm3 = at.check_countermodel("peqv2", answer="p", replace={"peqv2": "mu2 = 6"})
    assert cm3["summary"].startswith("refutes p: a1 = 147/40 (was 49/20)")


# -- final review of the checker -------------------------------------------------------------------------------


def _root_trace():
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "rx", "model", "x", relation="x*x = 4")
    t.external(ROOT, "root extraction", "the positive root", relation="x = 2", binds="sq", uses=["rx"])
    t.derive(ROOT, "x = 2", binds="x", from_relations=["sq"])
    t.answer(["x"], label="p")
    return t


def test_a_premise_is_not_entailed_by_what_was_produced_from_it():
    """A relation produced from the premise (here an EXTERNAL root of it) cannot show it is entailed:
    otherwise ENTAILED would prune a needed premise on a circular argument."""
    t = _root_trace()
    assert t.check_entailed("rx", answer="p")["verdict"] == "cannot check"
    with pytest.raises(TraceError, match="rests on 'rx'"):
        t.check_entailed("rx", answer="p", by=["sq"])
    t.annotate("rx", "ENTAILED", answer="p", check={"entailed_by": []})
    assert any(w.startswith("the check of rx could not be made") for w in t.ledger("p")["warnings"])


def test_a_relation_that_merely_mentions_a_value_may_entail_it():
    t = lever()
    t.input(ROOT, "meas", "model", "measured force", relation="F = 2")
    t.derive(ROOT, "F = 2", uses=["meas"])
    U(t, "z")
    t.input(ROOT, "rz", "model", "z", relation="z = 1")
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"], uses=["meas"])
    t.answer(["F", "z"], label="q")
    assert t.check_entailed("k", answer="q", by=["hooke", "ext", "meas"])["verdict"] == "entailed"


def test_a_nonlinear_citation_that_may_fix_the_premise_cannot_be_checked():
    t = Trace("q")
    for n in ("v", "h"):
        U(t, n)
    t.input(ROOT, "g", "value", "g", value="49/5")
    t.input(ROOT, "en", "model", "energy", relation="v = (2*g*h)**0.5")  # stays nonlinear even with v known
    t.input(ROOT, "rv", "model", "speed", relation="v = 14")
    t.input(ROOT, "rh", "model", "height", relation="h = 10")
    t.derive(ROOT, "v = 14", binds="v", from_relations=["rv"], uses=["en"])
    t.derive(ROOT, "h = 10", binds="h", from_relations=["rh"])
    t.answer(["v", "h"], label="p")
    r = t.check_entailed("rh", answer="p", by=["en", "rv", "g"])
    assert r["verdict"] == "cannot check" and "en" in r["detail"]
    t2 = Trace("q")  # by contrast, v*v = 2*g*h becomes linear in h once v is fixed, and does entail it
    for n in ("v", "h"):
        U(t2, n)
    t2.input(ROOT, "g", "value", "g", value="49/5")
    t2.input(ROOT, "en", "model", "energy", relation="v*v = 2*g*h")
    t2.input(ROOT, "rv", "model", "speed", relation="v = 14")
    t2.input(ROOT, "rh", "model", "height", relation="h = 10")
    t2.derive(ROOT, "v = 14", binds="v", from_relations=["rv"], uses=["en"])
    t2.derive(ROOT, "h = 10", binds="h", from_relations=["rh"])
    t2.answer(["v", "h"], label="p")
    assert t2.check_entailed("rh", answer="p", by=["en", "rv", "g"])["verdict"] == "entailed"


def test_countermodel_equations_take_quantities_only():
    t = lever()
    with pytest.raises(TraceError, match="not a quantity"):
        t.check_countermodel("hooke", answer="p", replace={"hooke": "F = k*x + ext"})
    with pytest.raises(TraceError, match="not a quantity"):
        t.check_countermodel("k", answer="p", add=["rec = 3"])
    with pytest.raises(TraceError, match="must be names"):
        t.check_countermodel("k", answer="p", values={"2c": 1})


def test_a_countermodel_value_too_large_to_keep_cannot_be_checked():
    t = lever()
    r = t.check_countermodel("hooke", answer="p", replace={"hooke": "F = k*x + c"},
                             add=["c = 2**12000*d", "d = 2**12000"])  # the solve, not the parser, makes c huge
    assert r["verdict"] == "cannot check" and "too large" in r["detail"]


def test_p_still_follows_names_nonlinear_relations_it_did_not_check():
    t = Trace("q")
    for n in ("x", "y"):
        U(t, n)
    t.input(ROOT, "rx", "model", "x", relation="x = 4")
    t.input(ROOT, "ry", "model", "y", relation="y*y = x")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx"], uses=["ry"])
    t.answer(["x"], label="p")
    r = t.check_countermodel("ry", answer="p", replace={"ry": "y*y = -1"})
    assert r["summary"] == "p still follows: nonlinear relations not checked: ry"

