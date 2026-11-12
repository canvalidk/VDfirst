"""Adversarial review of handtrace.py v2.3 (round six).

Four reviewers probed the v2.3 changes (arithmetic and syntax, withdrawal
and value history, provenance and visibility, ledger and records); a
skeptic reran every finding and tried to refute it. The confirmed ones are
fixed and pinned here:

  F23-1  operand order decided undefined versus nonlinear: m*a/(t - 3) at t = 3 passed, m/(t - 3)*a was a conflict
  F23-2  consistency() depended on the order of its relations (conflict one way, refused the other)
  F23-3  a huge exponent raised OverflowError in the power guard, crashing derive, ledger and records
  F23-4  values over 4300 digits were accepted but could not be rendered or saved
  F23-5  input(value='2**0.5') raised Nonlinear, not TraceError, and the CLI died with a traceback
  F23-6  a value determined again elsewhere let a step in a frame that saw the withdrawn value become a mistake
  F23-7  the 'undetermined' note read the current value, naming the wrong premise and time
  F23-8  solve() and consistency() called a stale-value case 'nonlinear' without naming the withdrawn premise

Round seven reviewed the round-six fixes the same way and confirmed:

  F23-9   a zero factor inside a nonlinear divisor (1/(m*a*(t - 3)) at t = 3) was still called nonlinear
  F23-10  int and Fraction values of 3,901 to 3,914 digits were accepted but their records did not replay
  F23-11  the stale refusals of solve() and consistency() still depended on relation order, and consistency()
          tested withdrawn values differently from its own verdict rule
  (minor) an even root of a negative number with a huge exponent was called too large instead of undefined;
          0e5000 was refused; the parser's recursion depth had halved

An exhaustive property test checks that solve() and consistency() give the
same outcome for every order of every small set of relations.

Refuted (documented, not defects): the joint-conflict row names an
irreducible subset, not a smallest one (pinned; the spec now says
'minimal'); the record's 'values' keeps withdrawn values as history
(pinned); consistency() records 'consistent' where only a withdrawn value
would contradict (the value is simply absent there); pathological inputs
(about 1000-term claims, million-digit literals, roots of index > 64 of
negative numbers in lenient mode).
"""

import itertools
import json

import pytest

import handtrace
from handtrace import ROOT, CheckError, Trace, TraceError, UndefinedValue, parse_equation, parse_expression


def U(t, name, frame=ROOT):
    t.unknown(frame, name, name, address=f"({name})", label="READING")


def conflicts(t, label=None):
    return [c["ref"] for c in t.ledger(label)["conflicts"]]


# -- F23-1: operand order ----------------------------------------------------------------------------


def _law(rel, strict=True):
    t = Trace("q", strict=strict)
    t.input(ROOT, "t", "value", "elapsed time", value=3)
    for n in ("F", "m", "a"):
        U(t, n)
    t.input(ROOT, "r", "model", "law", relation=rel)  # undefined at t = 3 whatever m and a are
    t.input(ROOT, "rF", "model", "measured F", relation="F = 2")
    return t


@pytest.mark.parametrize("rel", ["F = m*a/(t - 3)", "F = m/(t - 3)*a", "F = (m*a)/(t - 3)", "F = m*a*(1/(t - 3))",
                                 "m*a/(t - 3) = F"])
def test_an_undefined_relation_is_a_conflict_whatever_the_operand_order(rel):
    t = _law(rel)
    with pytest.raises(CheckError, match="conflict: relation r cannot be evaluated"):
        t.derive(ROOT, "F = 2", binds="F", from_relations=["rF", "r"])
    t.derive(ROOT, "F = 2", binds="F", from_relations=["rF"], uses=["r"])
    t.answer(["F"])
    assert conflicts(t) == ["r"]


@pytest.mark.parametrize("claim", ["F = m*a/(t - 3)", "F = m/(t - 3)*a", "F = (2*t)**0.5/(t - 3)",
                                   "F = 1/(t - 3)*(2*t)**0.5", "m*a = 1/(t - 3)"])
def test_an_undefined_claim_is_a_found_mistake_whatever_the_operand_order(claim):
    t = _law("F = m*a", strict=False)
    st = t.derive(ROOT, claim)
    assert st.check == "failed" and st.detail.startswith("mistake: the claim cannot be evaluated"), st.detail


def test_undefined_wins_over_nonlinear_in_the_parser():
    vals = {"t": handtrace.Fraction(3)}
    for text in ("m*a/(t - 3)", "(2*t)**0.5/(t - 3)", "m*a + 1/(t - 3)", "1/(t - 3) + m*a"):
        with pytest.raises(UndefinedValue):
            parse_expression(text, vals)
    with pytest.raises(UndefinedValue):
        parse_equation("m*a = 1/(t - 3)", vals)
    with pytest.raises(handtrace.Nonlinear):
        parse_expression("m*a/(t - 2)", vals)  # defined, merely nonlinear


# -- F23-2: consistency() order ------------------------------------------------------------------------


def _consistency_trace():
    t = Trace("q")
    t.input(ROOT, "t", "value", "elapsed time", value=3)
    for n in ("F", "m", "a"):
        U(t, n)
    t.input(ROOT, "rn", "model", "open product", relation="F = m*a")
    t.input(ROOT, "ru", "model", "law", relation="F = 1/(t - 3)")
    t.input(ROOT, "r1", "model", "F one", relation="F = 1")
    t.input(ROOT, "r2", "model", "F two", relation="F = 2")
    return t


@pytest.mark.parametrize("rels", [["ru", "rn"], ["rn", "ru"], ["rn", "r1", "r2"], ["r1", "rn", "r2"]])
def test_consistency_is_a_conflict_in_any_order_when_some_relation_decides_it(rels):
    st = _consistency_trace().consistency(ROOT, rels)
    assert st.check == "failed" and st.detail.startswith("conflict"), st.detail


def test_consistency_still_refuses_when_only_nonlinear_relations_remain_undecided():
    t = _consistency_trace()
    with pytest.raises(TraceError, match="cannot check consistency"):
        t.consistency(ROOT, ["rn", "r1"])


@pytest.mark.parametrize("rels", [["rn", "ru"], ["ru", "rn"]])
def test_solve_refuses_an_undefined_relation_the_same_way_in_any_order(rels):
    t = _consistency_trace()
    with pytest.raises(UndefinedValue, match="relation ru cannot be evaluated"):
        t.solve(ROOT, rels, ["F", "m", "a"])


# -- F23-3 / F23-4: sizes ------------------------------------------------------------------------------


@pytest.mark.parametrize("claim", ["2**(10**400) = 1", "3**1e400 = 1", "2**1e309 = 1", "2**16000 = 0",
                                   "1e5000 = 0", "(1e3000)*(1e3000) = 0", "1/(1e3000)*1/(1e3000) = 0"])
def test_a_number_too_large_to_keep_is_unchecked_not_a_crash(claim):
    with pytest.raises(CheckError, match="too large to handle exactly"):
        Trace("q").derive(ROOT, claim)
    st = Trace("q", strict=False).derive(ROOT, claim)
    assert st.check == "unchecked" and "too large" in st.detail


def test_powers_of_one_are_exact_whatever_the_exponent():
    for claim in ("1**1e400 = 1", "(-1)**(10**400 + 1) = -1", "1**(10**400) = 1"):
        assert Trace("q").derive(ROOT, claim).check == "checked"


@pytest.mark.parametrize("value", ["2**16000", "1e5000", 10 ** 5000, handtrace.Fraction(1, 10 ** 5000),
                                   "2**(10**400)"],
                         ids=["str power", "str literal", "int", "Fraction", "str huge exponent"])
def test_a_supplied_value_too_large_to_record_is_refused(value):
    t = Trace("q")
    with pytest.raises(TraceError, match="too large"):
        t.input(ROOT, "N", "value", "a count", value=value)
    assert t.steps == [] or all(s.op != "INPUT" for s in t.steps)


def test_large_values_within_the_bound_render_and_replay():
    t = Trace("q")
    t.input(ROOT, "N", "value", "a count", value="2**12000")
    t.answer(["N"])
    rec = t.to_record()
    assert Trace.replay(json.loads(json.dumps(rec))).to_record()["sha256"] == rec["sha256"]
    assert len(t.to_markdown()) > 3600


def test_a_relation_whose_value_is_too_large_is_skipped_by_the_global_check():
    t = Trace("q")
    for n in ("N", "y", "w"):
        U(t, n)
    t.input(ROOT, "r", "model", "growth law", relation="y = 2**N")
    t.input(ROOT, "rN", "model", "count", relation="N = 1e400")
    t.derive(ROOT, "N = 1e400", binds="N", from_relations=["rN"])
    t.input(ROOT, "rw", "model", "w", relation="w = 5")
    t.derive(ROOT, "w = 5", binds="w", from_relations=["rw"], uses=["r"])
    t.answer(["w"])
    assert t.ledger()["conflicts"] == []
    t.to_markdown()
    t.to_record()


# -- F23-5: supplied values and the CLI -------------------------------------------------------------------


@pytest.mark.parametrize("value", ["2**0.5", "2**(1/3)", "x*y"])
def test_a_supplied_value_that_is_not_an_exact_rational_is_a_trace_error(value):
    with pytest.raises(TraceError, match="supplied value must be"):
        Trace("q").input(ROOT, "c", "value", "a constant", value=value)


def test_cli_reports_unreadable_and_invalid_records(tmp_path, capsys):
    assert handtrace.main(["validate", str(tmp_path / "missing.json")]) == 1
    assert "cannot read record" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert handtrace.main(["validate", str(bad)]) == 1
    assert "cannot read record" in capsys.readouterr().err
    t = Trace("q")
    t.input(ROOT, "c", "value", "a constant", value=2)
    t.answer(["c"])
    rec = t.to_record()
    rec["commands"][0]["args"]["value"] = "2**0.5"  # tampered, with a recomputed digest
    body = {k: v for k, v in rec.items() if k != "sha256"}
    rec["sha256"] = handtrace._digest(body)
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(rec), encoding="utf-8")
    assert handtrace.main(["validate", str(tampered)]) == 1
    assert "invalid record" in capsys.readouterr().err


# -- F23-6: what a frame has seen ----------------------------------------------------------------------


def _seen_then_redetermined(strict=False):
    t = Trace("q", strict=strict)
    d = t.demand(ROOT, "D", "d")
    U(t, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.deliver(d, "x")  # D works with x = 3
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    new = t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])  # not delivered into D
    return t, d, new


@pytest.mark.parametrize("strict", [False, True])
def test_a_frame_that_saw_a_withdrawn_value_is_told_so_after_a_redetermination_elsewhere(strict):
    t, d, new = _seen_then_redetermined(strict)
    n = len(t.steps)
    with pytest.raises(TraceError, match=r"the step needs the value of x \(rests on rx\), which rests on a "
                                         r"withdrawn premise; determine it again first \(a new value of x was "
                                         rf"determined at \{new.id}; deliver it\)") as exc:
        t.derive(d, "2*x = 6")
    assert not isinstance(exc.value, CheckError) and len(t.steps) == n
    t.deliver(d, "x")
    assert t.derive(d, "2*x = 8").check == "checked"


def test_a_frame_that_never_saw_the_old_value_is_not_refused():
    t = Trace("q", strict=False)
    U(t, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.withdraw(ROOT, "rx", "wrong")
    d = t.demand(ROOT, "D", "d")  # created after the withdrawal; x delivered by name only
    t.deliver(d, "x")
    st = t.derive(d, "2*x = 6")
    assert st.check == "failed" and st.detail.startswith("mistake: not an identity")


# -- F23-7: the undetermined note is read as of the answer --------------------------------------------------


def _note(t, label, name="x"):
    return next(u["note"] for u in t.ledger(label)["undetermined"] if u["name"] == name)


@pytest.mark.parametrize("order", [["P1", "P2"], ["P2", "P1"]])
def test_note_names_the_premise_withdrawn_before_the_answer_even_after_a_later_withdrawal(order):
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "P1", "recognition", "P1 holds")
    t.input(ROOT, "P2", "recognition", "P2 holds")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3", uses=order)
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "z", "value", "z", value=1)
    t.withdraw(ROOT, "P1", "P1 is wrong")
    t.answer(["z"], label="p1")
    assert _note(t, "p1") == "its value was withdrawn: it rested on P1"
    t.withdraw(ROOT, "P2", "P2 is wrong too")
    assert _note(t, "p1") == "its value was withdrawn: it rested on P1"


def test_note_for_the_value_an_answer_had_names_its_own_premise_not_a_later_one():
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "P", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["P"])
    t.answer(["x"], label="p1")
    w = t.withdraw(ROOT, "P", "wrong")
    t.input(ROOT, "Q", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["Q"])
    t.withdraw(ROOT, "Q", "wrong too")
    assert _note(t, "p1") == f"the value it had at this answer (3) was withdrawn after it (at {w.id}): it rested on P"


def test_note_when_the_quantity_had_no_value_at_the_answer():
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "z", "value", "z", value=1)
    t.answer(["z"], label="p1")
    t.input(ROOT, "P", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["P"])
    w = t.withdraw(ROOT, "P", "wrong")
    assert _note(t, "p1") == (f"it had no value at this answer; a value determined after this answer was withdrawn "
                              f"(at {w.id}): it rested on P")


def test_note_for_a_value_resting_on_two_premises_withdrawn_either_side_of_the_answer():
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "r1", "model", "the sum", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "the difference", relation="x - y = 1")
    t.derive(ROOT, "x = 3", from_relations=["r1", "r2"], binds="x")
    t.withdraw(ROOT, "r1", "the sum was misread")
    with pytest.raises(TraceError, match="rests on 'r1'"):
        t.answer(["x"], label="early")
    t.input(ROOT, "k", "value", "k", value=1)
    t.answer(["k"], label="p")
    t.withdraw(ROOT, "r2", "the difference was misread too")
    assert _note(t, "p") == "its value was withdrawn: it rested on r1"


# -- F23-8: solve and consistency name the withdrawn premise --------------------------------------------------


def _stale_product():
    t = Trace("q")
    for n in ("x", "y", "z"):
        U(t, n)
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y is x times z", relation="y = x*z")
    t.input(ROOT, "rz", "model", "z two", relation="z = 2")
    return t


def test_solve_and_consistency_name_the_withdrawn_premise_that_made_a_relation_linear():
    t = _stale_product()
    assert t.solve(ROOT, ["ry", "rz"], ["y", "z"]).detail.startswith("unique: y = 6, z = 2")
    t = _stale_product()
    t.withdraw(ROOT, "rx", "misread")
    n = len(t.steps)
    for call in (lambda: t.solve(ROOT, ["ry", "rz"], ["y", "z"]), lambda: t.solve(ROOT, ["ry"], ["y"]),
                 lambda: t.consistency(ROOT, ["ry", "rz"]),
                 lambda: t.derive(ROOT, "y = 6", from_relations=["ry", "rz"])):
        with pytest.raises(TraceError, match=r"the step needs the value of x \(rests on rx\)"):
            call()
    assert len(t.steps) == n


def test_solving_for_the_withdrawn_quantity_itself_is_not_refused_for_staleness():
    t = _stale_product()
    t.withdraw(ROOT, "rx", "misread")
    with pytest.raises(TraceError, match="cannot solve") as exc:
        t.solve(ROOT, ["ry", "rz"], ["x", "y", "z"])  # x is being determined again: nonlinear, not stale
    assert "withdrawn" not in str(exc.value)


# -- round seven -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("rel", ["F = 1/(m*a*(t - 3))", "F = m/(a*m*(t - 3))", "F = (m*a*(t - 3))**(-1)",
                                 "F = 2 + 1/(a*(t - 3)*m)"])
def test_f23_9_a_zero_factor_in_a_nonlinear_divisor_is_undefined(rel):
    test_an_undefined_relation_is_a_conflict_whatever_the_operand_order(rel)


def test_f23_9_a_product_with_a_zero_factor_is_zero():
    t = _law("F = m*a", strict=True)
    assert t.derive(ROOT, "m*a*(t - 3) = 0").detail.startswith("identity once the visible values are substituted")


@pytest.mark.parametrize("value", [10 ** 3905, handtrace.Fraction(1, 10 ** 3905), -(10 ** 3900), 2 ** 12999,
                                   handtrace.Fraction(2 ** 12999, 3)],
                         ids=["int 3906 digits", "Fraction 1/10**3905", "negative int", "2**12999", "Fraction"])
def test_f23_10_every_accepted_value_replays(value, tmp_path):
    t = Trace("q")
    t.input(ROOT, "N", "value", "a count", value=value)
    t.answer(["N"])
    rec = json.loads(json.dumps(t.to_record()))
    assert Trace.replay(rec).to_record()["sha256"] == rec["sha256"]
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    assert handtrace.main(["validate", str(path)]) == 0


def test_f23_10_literals_and_values_share_one_bound():
    assert Trace("q").derive(ROOT, f"{10 ** 3905} = 10**3905").check == "checked"
    assert Trace("q").derive(ROOT, "0e5000 = 0").check == "checked"
    with pytest.raises(TraceError, match="too large"):
        Trace("q").input(ROOT, "N", "value", "a count", value=10 ** 3920)


def test_minor_an_even_root_of_a_negative_number_is_undefined_whatever_the_exponent():
    st = Trace("q", strict=False).derive(ROOT, "(-3)**(30001/2) = 1")
    assert st.check == "failed" and "an even root of a negative number" in st.detail


def test_minor_the_parser_handles_long_hand_written_sums():
    assert Trace("q").derive(ROOT, "+".join(["1"] * 900) + " = 900").check == "checked"


def test_f23_11_consistency_names_a_withdrawn_value_that_would_decide_it_beside_a_nonlinear_relation():
    t = _stale_product()
    U(t, "F")
    U(t, "m")
    U(t, "a")
    t.input(ROOT, "r7", "model", "y seven", relation="y = 7")
    t.input(ROOT, "rn", "model", "open product", relation="F = m*a")
    assert t.consistency(ROOT, ["rn", "ry", "rz", "r7"]).detail.startswith("conflict")
    t.withdraw(ROOT, "rx", "misread")
    for rels in (["rn", "ry", "rz", "r7"], ["r7", "rz", "ry", "rn"]):
        with pytest.raises(TraceError, match=r"the step needs the value of x \(rests on rx\)"):
            t.consistency(ROOT, rels)


# An exhaustive order-independence check. Pool: t = 3 is given; x = 3 rests on rx, which may be withdrawn.
POOL = {
    "rn": "F = m*a",                 # nonlinear
    "ru": "F = 1/(t - 3)",           # undefined
    "ruz": "F = 1/(m*a*(t - 3))",    # undefined through a zero factor
    "r1": "F = 1",
    "r2": "F = 2",                   # contradicts r1
    "ry": "y = x*z",                 # linear only with x's value
    "rz": "z = 2",
    "r7": "y = 7",                   # contradicts ry and rz when x = 3
    "rux": "F = 1/(x - 3)",          # undefined only with x's value, nonlinear without it
}


def _pool_trace(withdrawn):
    t = Trace("q", strict=False)
    t.input(ROOT, "t", "value", "elapsed time", value=3)
    for n in ("x", "F", "m", "a", "y", "z"):
        U(t, n)
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    for name, rel in POOL.items():
        t.input(ROOT, name, "model", name, relation=rel)
    if withdrawn:
        t.withdraw(ROOT, "rx", "misread")
    return t


def _outcome(withdrawn, op, rels):
    t = _pool_trace(withdrawn)
    try:
        if op == "consistency":
            st = t.consistency(ROOT, rels)
            return ("recorded", st.detail.split(":")[0])
        unknowns = sorted({n for r in rels for n in handtrace.mentioned_names(POOL[r])} & {"F", "m", "a", "y", "z"})
        st = t.solve(ROOT, rels, unknowns)
        return ("recorded", st.detail.split(":")[0], tuple(sorted((k, t.values[k]) for k in unknowns
                                                                  if k in t.values)))
    except TraceError as exc:
        msg = str(exc)
        kind = ("withdrawn" if "withdrawn premise" in msg else "undefined" if isinstance(exc, UndefinedValue)
                else "nonlinear" if "nonlinear" in msg else "other")
        return ("refused", kind)


@pytest.mark.parametrize("withdrawn", [False, True], ids=["x visible", "x withdrawn"])
@pytest.mark.parametrize("op", ["consistency", "solve"])
def test_f23_11_outcomes_do_not_depend_on_the_order_of_relations(withdrawn, op):
    differing = []
    for size in (1, 2, 3):
        for subset in itertools.combinations(sorted(POOL), size):
            outcomes = {_outcome(withdrawn, op, list(perm)) for perm in itertools.permutations(subset)}
            if len(outcomes) > 1:
                differing.append((subset, sorted(outcomes)))
    assert differing == []
