"""Fresh adversarial review of handtrace.py v2.2.

Passing tests document behaviour v2.2 gets right, and pin notes and
frictions (test_note_*). Genuine v2.2 bugs were xfail(strict=True); each
reason starts with its finding id (F22-n), ranked by severity. All are
fixed in v2.3 and their markers removed:

  F22-1  unsupported syntax (sqrt, %) is filed as a mistake or a conflict  (fixed in v2.3)
  F22-2  a relation registered after a value inherits that value's premises  (fixed in v2.3)
  F22-3  a claim that leans on a withdrawn value becomes a found mistake  (fixed in v2.3)
  F22-4  a hidden value can turn a conflict into a found mistake silently  (fixed in v2.3)
  F22-5  re-determination after an answer erases that answer's global conflict  (fixed in v2.3)
  F22-6  the ledger never shows that a value was withdrawn  (fixed in v2.3)
  F22-7  the re-supply warning advises delivering a tainted original  (fixed in v2.3)
  F22-8  quote boundaries: fragments after an apostrophe or a combining mark  (fixed in v2.3)

Areas: value-level taint and re-determination, stale deliveries, per-value
solve DERIVE steps, the hidden-verdict comparison, the global ledger check,
deliver_through / deliver_many, quotes, ledger warnings and the cost of a
500-step synthetic trace with withdrawals.
"""

import re
import time
import unicodedata

import pytest

from handtrace import (
    ROOT,
    CheckError,
    HiddenLookupError,
    Trace,
    TraceError,
    needed_relations,
    parse_equation,
)


def U(t, name, frame=ROOT):
    return t.unknown(frame, name, name, address=f"({name})", ref="t")


def warnings_of(t, label=None):
    return t.ledger(label)["warnings"]


# ---------------------------------------------------------------------------
# Value-level taint and re-determination
# ---------------------------------------------------------------------------


def _x_from_rx(strict=True):
    t = Trace("q", strict=strict)
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")  # registered before x has a value
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    return t


def test_withdrawal_hides_the_value_and_keeps_the_name():
    t = _x_from_rx()
    t.withdraw(ROOT, "rx", "wrong")
    assert t.value_visible(ROOT, "x") is None
    assert "x" not in t.known_values(ROOT)
    assert t.visible(ROOT, "x") is not None
    with pytest.raises(TraceError, match="rests on 'rx'"):
        t.answer(["x"])


def test_redetermination_by_derive_and_answer_rest_on_the_new_value():
    t = _x_from_rx()
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    st = t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    assert t.values["x"] == 4 and t.value_step["x"] == st.index
    t.derive(ROOT, "y = 8", binds="y", from_relations=["ry"])
    t.answer(["y"])
    names = [c["name"] for c in t.ledger()["commitments"]]
    assert "rx4" in names and "rx" not in names
    assert t.ledger()["conflicts"] == []


def test_redetermination_by_solve():
    t = _x_from_rx()
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx5", "model", "x five", relation="x = 5")
    t.solve(ROOT, ["rx5", "ry"], ["x", "y"])
    assert (t.values["x"], t.values["y"]) == (5, 10)
    t.answer(["x", "y"])


def test_a_premise_resting_on_a_withdrawn_one_can_be_withdrawn():
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "closed")
    t.input(ROOT, "m", "value", "mass", value=2, uses=["c"])
    t.withdraw(ROOT, "c", "no")
    t.withdraw(ROOT, "m", "also no")
    assert t.bindings["m"].withdrawn is not None


def test_stale_delivery_does_not_carry_the_redetermined_value():
    t = _x_from_rx(strict=False)
    d = t.demand(ROOT, "D", "d")
    dd = t.demand(d, "DD", "dd")
    t.deliver(d, "x")
    t.deliver(d, "ry")
    t.deliver(d, "y")
    assert t.value_visible(dd, "x") is not None
    t.withdraw(ROOT, "rx", "wrong")
    assert t.value_visible(dd, "x") is None
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    # The old DELIVER carried 3; it must not carry 4.
    assert t.value_visible(dd, "x") is None
    with pytest.raises(HiddenLookupError):
        t.derive(dd, "y = 8", binds="y", from_relations=["ry"])
    # deliver_through re-delivers into the highest frame below ROOT.
    out = t.deliver_through(dd, "x")
    assert [s.frame for s in out] == ["D"]
    t.derive(dd, "y = 8", binds="y", from_relations=["ry"])
    assert t.values["y"] == 8


def test_withdrawing_after_a_delivery_hides_the_delivered_value_everywhere():
    t = _x_from_rx()
    d = t.demand(ROOT, "D", "d")
    t.deliver(d, "x")
    t.withdraw(ROOT, "rx", "wrong")
    assert "x" not in t.known_values(d)
    # A name-only re-delivery is refused: the name is already there and there is no usable value.
    with pytest.raises(TraceError, match="already visible"):
        t.deliver(d, "x")


def test_relation_registered_after_a_value_survives_withdrawal_of_that_values_premise():
    """F22-2, fixed in v2.3: a relation INPUT depends only on the binding steps of its names."""
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")  # a model relation; it uses no value
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    t.derive(ROOT, "y = 8", binds="y", from_relations=["ry"])  # v2.2 raised TraceError: 'ry' rests on 'rx'


def test_the_order_of_registration_does_not_decide_whether_a_relation_survives():
    """F22-2, v2.3: a relation registered after x's value rests only on the binding steps of x and y, not on
    x's value step, so withdrawing the premise behind x's value leaves it deliverable (as when it is registered
    before x's value, see _x_from_rx)."""
    t = Trace("q")
    U(t, "x")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    U(t, "y")
    st = t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")
    assert t.value_step["x"] not in st.deps
    assert st.deps == (t.bindings["x"].step, t.bindings["y"].step)  # the binding steps only, not rx
    t.withdraw(ROOT, "rx", "wrong")
    d = t.demand(ROOT, "D", "d")
    out = t.deliver(d, "ry")
    assert out.op == "DELIVER" and out.uses == ("ry",) and out.deps == (st.index,)
    assert t.visible(d, "ry") is not None


def test_a_claim_leaning_on_a_withdrawn_value_is_refused_not_a_found_mistake():
    """F22-3, fixed in v2.3: the claim is refused with the withdrawn premise named and nothing is recorded."""
    t = _x_from_rx(strict=False)
    t.withdraw(ROOT, "rx", "wrong")
    n = len(t.steps)
    with pytest.raises(TraceError, match="rx"):
        t.derive(ROOT, "y = 6", from_relations=["ry"])  # v2.2 recorded: failed, 'mistake: does not follow from ry'
    assert len(t.steps) == n


STALE_X = ("the step needs the value of x (rests on rx), which rests on a withdrawn premise; "
           "determine it again first")


@pytest.mark.parametrize("strict", [False, True])
def test_a_claim_leaning_on_a_withdrawn_value_is_refused_in_both_modes(strict):
    """F22-3, v2.3: in lenient and strict mode alike, a claim that holds only with the withdrawn x = 3 raises a
    TraceError (not a CheckError) naming the withdrawn premise, records nothing and files no found mistake; solve
    names the withdrawal too."""
    t = _x_from_rx(strict=strict)
    t.withdraw(ROOT, "rx", "wrong")
    n, k = len(t.steps), len(t.commands)
    with pytest.raises(TraceError, match=re.escape(STALE_X)) as e:
        t.derive(ROOT, "2*x = 6")
    assert not isinstance(e.value, CheckError)
    with pytest.raises(TraceError, match=re.escape(STALE_X)) as e:
        t.solve(ROOT, ["ry"], ["y"])
    assert not isinstance(e.value, CheckError)
    assert (len(t.steps), len(t.commands)) == (n, k)
    t.input(ROOT, "g", "value", "g", value=1)
    t.answer(["g"])
    assert t.ledger()["mistakes"] == []


def test_ledger_lists_a_quantity_whose_value_was_withdrawn():
    """F22-6, fixed in v2.3."""
    t = _x_from_rx()
    t.input(ROOT, "g", "value", "g", value=1)
    t.withdraw(ROOT, "rx", "wrong")
    t.answer(["g"])
    assert "x" in [u["name"] for u in t.ledger()["undetermined"]]


def test_resupply_warning_does_not_advise_delivering_a_tainted_original():
    """F22-7, fixed in v2.3: the re-supply warning told the tracer to deliver a tainted original, which
    deliver() refuses. Here ry is tainted through its own premise c (uses=), and the warning says why it
    cannot be delivered."""
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "c", "completeness", "only the spring acts")
    t.input(ROOT, "rx", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x", uses=["c"])
    t.withdraw(ROOT, "c", "the table pushes too")
    t.input(ROOT, "ry2", "model", "y twice x", relation="y = 2*x")
    t.derive(ROOT, "y = 8", binds="y", from_relations=["ry2"])
    t.answer(["y"])
    d = t.demand(ROOT, "D", "d")
    with pytest.raises(TraceError, match="rests on 'c'"):
        t.deliver(d, "ry")
    w = warnings_of(t)
    assert not any("deliver the original" in x for x in w)
    assert "ry2 repeats ry word for word; ry rests on c, which was withdrawn, so it cannot be delivered" in w


def test_a_relation_registered_after_a_withdrawn_value_can_be_delivered_so_the_advice_stands():
    """The F22-7 reviewers' original setup. Since v2.3 registration rests only on names, so ry (registered
    after x's later-withdrawn value) is not tainted: deliver(ry) works and 'deliver the original' is sound."""
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y twice x", relation="y = 2*x")
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx4", "model", "x four", relation="x = 4")
    t.derive(ROOT, "x = 4", binds="x", from_relations=["rx4"])
    t.input(ROOT, "ry2", "model", "y twice x", relation="y = 2*x")
    t.derive(ROOT, "y = 8", binds="y", from_relations=["ry2"])
    t.answer(["y"])
    d = t.demand(ROOT, "D", "d")
    assert t.deliver(d, "ry").op == "DELIVER"
    assert "ry2 repeats the INPUT ry word for word; deliver the original instead of re-supplying it" \
        in warnings_of(t)


# ---------------------------------------------------------------------------
# Per-value solve DERIVE steps
# ---------------------------------------------------------------------------


def _joint_solve():
    t = Trace("q")
    for n in "xyz":
        U(t, n)
    t.input(ROOT, "A", "recognition", "A holds")
    t.input(ROOT, "B", "recognition", "B holds")
    t.input(ROOT, "r1", "model", "x three", relation="x = 3", uses=["A"])
    t.input(ROOT, "r2", "model", "y four", relation="y = 4", uses=["B"])
    t.input(ROOT, "r3", "model", "sum", relation="x + y = 7")
    st = t.solve(ROOT, ["r1", "r2", "r3"], ["x", "y"], tag="S")
    return t, st


def test_solve_returns_the_report_and_records_one_derive_per_value():
    t, st = _joint_solve()
    assert st.op == "EXTERNAL" and st.kind == "solve"
    derives = t.steps[st.index + 1:]
    assert [(s.op, s.claim, s.check, s.detail) for s in derives] == [
        ("DERIVE", "x = 3", "checked", "follows from r1"),
        ("DERIVE", "y = 4", "checked", "follows from r2"),
    ]
    assert t.value_step == {"x": st.index + 1, "y": st.index + 2}
    assert "relations not needed for the fixed values: r3" in st.detail


def test_answer_naming_x_rests_only_on_xs_relations_and_survives_ys_withdrawal():
    t, _ = _joint_solve()
    t.answer(["x"], label="px")
    assert [c["name"] for c in t.ledger("px")["commitments"]] == ["A", "r1"]
    t.withdraw(ROOT, "B", "y wrong")
    t.derive(ROOT, "2*x = 6")
    t.answer(["x"], label="px2")
    with pytest.raises(TraceError, match="rests on 'B'"):
        t.answer(["y"])


def test_solve_derives_render_and_replay():
    t, st = _joint_solve()
    t.answer(["x", "y"])
    md = t.to_markdown()
    assert "| `x = 3` — value fixed by the linear solve [9] ⇒ x = 3 | r1 | checked: follows from r1 |" in md
    Trace.replay(t.to_record())


def test_solve_in_a_family_derives_only_the_fixed_values():
    t = Trace("q")
    for n in "xyzw":
        U(t, n)
    t.input(ROOT, "r1", "model", "a", relation="x + y + z = 6")
    t.input(ROOT, "r2", "model", "b", relation="y + z = 3")
    t.input(ROOT, "r3", "model", "c", relation="w = 2*z")
    st = t.solve(ROOT, ["r1", "r2", "r3"], ["x", "y", "z", "w"])
    assert st.detail.startswith("underdetermined") and "fixed anyway: x = 3" in st.detail
    assert "relations not needed for the fixed values: r3" in st.detail
    assert [(s.claim, s.detail) for s in t.steps[st.index + 1:]] == [("x = 3", "follows from r1, r2")]
    t.answer(["x"])
    assert t.ledger()["solve_reports"][0]["step"] == st.id


def test_the_solve_report_step_is_not_listed_outside_an_answer_its_values_feed():
    """v2.3: the EXTERNAL report is not in the answer's cone (its per-value DERIVE steps are), and it is no
    longer listed among 'other steps that do not feed the answer' while any of those DERIVE steps is in the
    cone. Its binds still name the values that the DERIVE steps fix."""
    t, st = _joint_solve()
    t.answer(["x", "y"])
    cone = t.cone()
    assert st.index not in cone
    assert {st.index + 1, st.index + 2} <= cone  # the per-value DERIVE steps x = 3, y = 4
    assert st.id not in [r["step"] for r in t.ledger()["outside_answer"]]
    assert st.binds == ("x", "y")


def test_note_beyond_eight_citations_the_direct_relation_is_reported_as_not_needed():
    """Greedy provenance (from the end) keeps rxy, ry for x and calls rx 'not needed', though rx alone is the
    smallest set. The solve docstring says 'a smallest set'."""
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    rels = []
    t.input(ROOT, "rxy", "model", "sum", relation="x + y = 7")
    t.input(ROOT, "ry", "model", "y", relation="y = 4")
    rels += ["rxy", "ry"]
    for i in range(6):
        U(t, f"j{i}")
        t.input(ROOT, f"jr{i}", "model", f"junk {i}", relation=f"j{i} = {i}")
        rels.append(f"jr{i}")
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    rels.append("rx")
    st = t.solve(ROOT, rels, ["x", "y"] + [f"j{i}" for i in range(6)])
    assert st.detail.endswith("(relations not needed for the fixed values: rx)")
    assert t.steps[t.value_step["x"]].detail == "follows from rxy, ry"


def test_needed_relations_is_exhaustive_up_to_eight():
    forms = [parse_equation(e)[0] for e in ["x + y = 7", "y = 4"] + [f"j{i} = {i}" for i in range(5)] + ["x = 3"]]
    claim = parse_equation("x = 3")[0]
    assert needed_relations(forms, claim) == [7]  # 8 relations: exhaustive, smallest
    forms9 = forms[:-1] + [parse_equation("j9 = 9")[0], forms[-1]]
    assert needed_relations(forms9, claim) == [0, 1]  # 9 relations: greedy, not smallest


# ---------------------------------------------------------------------------
# Hidden values: the verdict comparison
# ---------------------------------------------------------------------------


def _hidden_y(y_value, strict=False):
    t = Trace("q", strict=strict)
    d = t.demand(ROOT, "D", "d")
    U(t, "y")
    t.deliver(d, "y")  # name only: y has no value yet
    t.input(ROOT, "ry", "model", "y", relation=f"y = {y_value}")
    t.derive(ROOT, f"y = {y_value}", binds="y", from_relations=["ry"])
    U(t, "x", d)
    t.input(d, "r", "model", "x3", relation="x = 3")
    t.input(d, "r2", "model", "y5", relation="y = 5")
    return t, d


def test_an_unrelated_hidden_value_does_not_block_a_found_mistake():
    t, d = _hidden_y(5)
    st = t.derive(d, "x = 4", from_relations=["r", "r2"])
    assert st.check == "failed" and st.detail.startswith("mistake: does not follow from r, r2")


def test_a_hidden_value_that_changes_the_status_blocks_the_step():
    t, d = _hidden_y(5)
    t.input(d, "rxy", "model", "x from y", relation="x = y - 2")
    with pytest.raises(HiddenLookupError, match="would change the verdict"):
        t.derive(d, "x = 3", from_relations=["rxy"])


def test_a_hidden_value_that_turns_a_mistake_into_a_conflict_is_not_silent():
    """F22-4, fixed in v2.3: the verdict category (mistake vs conflict) is compared, not only the check word."""
    t, d = _hidden_y(6)
    n = len(t.steps)
    try:
        t.derive(d, "x = 4", from_relations=["r", "r2"])
    except HiddenLookupError:
        return
    st = t.steps[n]
    assert not st.detail.startswith("mistake"), st.detail


def test_note_the_same_step_with_the_value_delivered_is_a_conflict():
    """F22-4 contrast: delivering y first turns the very same derive into a conflict. v2.3: without the
    delivery the hidden y = 6 would change the verdict category, so the step raises HiddenLookupError and
    records nothing (v2.2 filed it silently as a found mistake)."""
    t = Trace("q", strict=False)
    d = t.demand(ROOT, "D", "d")
    U(t, "y")
    t.input(ROOT, "ry", "model", "y six", relation="y = 6")
    t.derive(ROOT, "y = 6", binds="y", from_relations=["ry"])
    t.deliver(d, "y")
    U(t, "x", d)
    t.input(d, "r", "model", "x3", relation="x = 3")
    t.input(d, "r2", "model", "y5", relation="y = 5")
    st = t.derive(d, "x = 4", from_relations=["r", "r2"])
    assert st.detail.startswith("conflict: the cited relations r, r2")
    lt, ld = _hidden_y(6)
    n, k = len(lt.steps), len(lt.commands)
    with pytest.raises(HiddenLookupError, match=re.escape(
            "values of ['y'] exist but are not visible at 'D' and would change the verdict; deliver them")):
        lt.derive(ld, "x = 4", from_relations=["r", "r2"])
    assert (len(lt.steps), len(lt.commands)) == (n, k)


def test_consistency_raises_when_a_hidden_value_would_change_the_result():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    U(t, "x")
    t.deliver(d, "x")
    t.input(ROOT, "rx", "model", "x5", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx"])
    t.input(d, "r", "model", "x7", relation="x = 7")
    with pytest.raises(HiddenLookupError, match="would change"):
        t.consistency(d, ["r"])
    t.input(d, "r5", "model", "x5 again", relation="x = 5")
    assert t.consistency(d, ["r5"]).detail == "consistent"  # the hidden value agrees: no lookup


# ---------------------------------------------------------------------------
# Unevaluable versus unsupported (F22-1)
# ---------------------------------------------------------------------------


def _pendulum(strict=False):
    t = Trace("q", strict=strict)
    for n in "TLg":
        U(t, n)
    t.input(ROOT, "rL", "model", "L one", relation="L = 1")
    t.input(ROOT, "rg", "model", "g four", relation="g = 4")
    t.derive(ROOT, "L = 1", binds="L", from_relations=["rL"])
    t.derive(ROOT, "g = 4", binds="g", from_relations=["rg"])
    t.input(ROOT, "per", "model", "small-angle pendulum period", relation="T = 2*(L/g)**0.5")
    return t


def test_division_by_zero_after_substitution_is_a_mistake_or_a_conflict():
    t = Trace("q", strict=False)
    for n in "aFx":
        U(t, n)
    t.input(ROOT, "m", "value", "mass", value=0)
    t.input(ROOT, "law", "model", "second law", relation="a = F/m")
    st = t.derive(ROOT, "a = 1", from_relations=["law"])
    assert st.check == "failed" and st.detail.startswith("conflict: relation law cannot be evaluated")
    st = t.derive(ROOT, "x = 1/m")
    assert st.check == "failed" and st.detail.startswith("mistake: the claim cannot be evaluated")


def test_a_sqrt_relation_cited_in_a_derive_is_not_a_premise_conflict():
    """F22-1, fixed in v2.3: a rational root is evaluated exactly, so T = 2*(1/4)**0.5 = 1 checks."""
    t = _pendulum()
    try:
        st = t.derive(ROOT, "T = 1", from_relations=["per"])
    except CheckError:
        raise AssertionError("CheckError")
    except TraceError:
        return
    assert st.check != "failed", st.detail


def test_a_superfluous_unsupported_citation_does_not_fail_a_correct_derive():
    """F22-1, v2.3: unsupported syntax ('%') is refused at registration and records nothing, so it can never be
    cited; a superfluous NONLINEAR citation is merely noted on a checked derive."""
    t = Trace("q", strict=False)
    U(t, "x")
    U(t, "y")
    n, k = len(t.steps), len(t.commands)
    with pytest.raises(TraceError, match=re.escape(
            "outside the checker's syntax (Mod) in 'x % 2'; use numbers, names, + - * / and ** "
            "(a root is **0.5 or **(1/3))")):
        t.input(ROOT, "rmod", "model", "parity", relation="y = x % 2")
    assert (len(t.steps), len(t.commands)) == (n, k) and "rmod" not in t.bindings
    t.input(ROOT, "rsq", "model", "square", relation="y = x*x")
    t.input(ROOT, "rx", "model", "x", relation="x = 3")
    st = t.derive(ROOT, "x = 3", from_relations=["rx", "rsq"])
    assert (st.check, st.detail) == ("checked", "follows from rx (nonlinear citations not checked: rsq)")


def test_consistency_of_a_sqrt_relation_is_not_a_conflict():
    """F22-1, fixed in v2.3."""
    t = _pendulum(strict=True)
    try:
        st = t.consistency(ROOT, ["per"])
    except TraceError:
        return
    assert st.check != "failed", st.detail


def test_the_global_check_does_not_flag_a_sqrt_relation():
    """F22-1, fixed in v2.3."""
    t = Trace("q")
    for n in "vz":
        U(t, n)
    t.input(ROOT, "g", "value", "g", value="9.8")
    t.input(ROOT, "h", "value", "drop height", value=5)
    t.input(ROOT, "en", "model", "energy balance", relation="v = (2*g*h)**0.5")
    t.input(ROOT, "rz", "model", "z one", relation="z = 1", uses=["en"])
    t.derive(ROOT, "z = 1", binds="z", from_relations=["rz"])
    t.answer(["z"])
    assert t.ledger()["conflicts"] == [], t.ledger()["conflicts"]


@pytest.mark.parametrize("claim", ["7 % 4 = 3", "x = 2**0.5", "x = 7 // 2"])
def test_unsupported_syntax_in_a_claim_is_not_a_found_mistake(claim):
    """F22-1, fixed in v2.3: '%' and '//' are refused at entry; an irrational power is 'unchecked'."""
    t = Trace("q", strict=False)
    U(t, "x")
    try:
        st = t.derive(ROOT, claim)
    except TraceError:
        return
    assert st.check != "failed", st.detail


# ---------------------------------------------------------------------------
# Global ledger check
# ---------------------------------------------------------------------------


def test_global_check_ignores_values_resting_on_premises_withdrawn_before_the_answer():
    t = Trace("q")
    U(t, "x")
    U(t, "z")
    t.input(ROOT, "r", "model", "x five", relation="x = 5")
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rz", "model", "z two", relation="z = 2", uses=["r"])
    t.derive(ROOT, "z = 2", binds="z", from_relations=["rz"])
    t.answer(["z"])
    assert t.ledger()["conflicts"] == []


def test_global_check_keeps_a_relation_withdrawn_after_the_answer():
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "r", "model", "x seven", relation="x = 7")
    t.input(ROOT, "rx", "model", "x five", relation="x = 5")
    t.derive(ROOT, "x = 5", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y", relation="y = 6", uses=["r"])
    t.derive(ROOT, "y = 6", binds="y", from_relations=["ry"])
    t.answer(["y"], label="p1")
    t.withdraw(ROOT, "r", "contradicted")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r"]


def test_global_check_reports_an_undefined_relation_and_a_joint_inconsistency():
    t = Trace("q")
    for n in "aFxyz":
        U(t, n)
    t.input(ROOT, "m", "value", "mass", value=0)
    t.input(ROOT, "law", "model", "second law", relation="a = F/m")
    t.input(ROOT, "rx", "model", "x one", relation="x = 1", uses=["law"])
    t.derive(ROOT, "x = 1", binds="x", from_relations=["rx"])
    t.answer(["x"], label="pd")
    assert "cannot be evaluated" in t.ledger("pd")["conflicts"][0]["detail"]
    t.to_markdown()
    t2 = Trace("q")
    for n in "xyz":
        U(t2, n)
    t2.input(ROOT, "r1", "model", "a", relation="x + y = 5")
    t2.input(ROOT, "r3", "model", "b", relation="x - y = 1")
    t2.derive(ROOT, "x = 3", binds="x", from_relations=["r1", "r3"])
    t2.input(ROOT, "r2", "model", "c", relation="y = 3")
    t2.input(ROOT, "r4", "model", "d", relation="z = 2*y")
    t2.derive(ROOT, "z = 6", binds="z", from_relations=["r2", "r4"])
    t2.answer(["x", "z"])
    assert "jointly inconsistent" in t2.ledger()["conflicts"][0]["detail"]


def test_global_check_ignores_values_fixed_after_the_answer():
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "r1", "model", "a", relation="x + y = 5")
    t.input(ROOT, "r2", "model", "b", relation="x - y = 1")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["r1", "r2"])
    t.answer(["x"], label="p1")
    t.input(ROOT, "ry", "model", "y", relation="y = 3")
    t.derive(ROOT, "y = 3", binds="y", from_relations=["ry"])
    assert t.ledger("p1")["conflicts"] == []


def _conflict_then_redetermine():
    t = Trace("q")
    U(t, "x")
    U(t, "y")
    t.input(ROOT, "r7", "model", "x seven", relation="x = 7")  # registered before x has a value
    t.input(ROOT, "rx", "model", "x three", relation="x = 3")
    t.derive(ROOT, "x = 3", binds="x", from_relations=["rx"])
    t.input(ROOT, "ry", "model", "y one", relation="y = 1", uses=["r7"])
    t.derive(ROOT, "y = 1", binds="y", from_relations=["ry"])
    t.answer(["y"], label="p1")
    return t


def test_withdrawal_after_the_answer_keeps_its_global_conflict():
    t = _conflict_then_redetermine()
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r7"]
    t.withdraw(ROOT, "rx", "wrong")
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r7"]


def test_redetermination_after_an_answer_keeps_that_answers_global_conflict():
    """F22-5, fixed in v2.3: the global check reads each name's value history, so re-determining x after p1
    keeps x = 3 (fixed before p1, withdrawn after it) in p1's check."""
    t = _conflict_then_redetermine()
    t.withdraw(ROOT, "rx", "wrong")
    t.input(ROOT, "rx7", "model", "x seven again", relation="x = 7")
    t.derive(ROOT, "x = 7", binds="x", from_relations=["rx7"])
    assert [c["ref"] for c in t.ledger("p1")["conflicts"]] == ["r7"]


# ---------------------------------------------------------------------------
# deliver_through and deliver_many
# ---------------------------------------------------------------------------


def _chain():
    t = Trace("q")
    a = t.demand(ROOT, "A", "a")
    b = t.demand(a, "B", "b")
    c = t.demand(b, "C", "c")
    return t, a, b, c


def test_deliver_through_three_levels_makes_one_delivery_into_the_top_frame():
    t, a, b, c = _chain()
    t.input(ROOT, "g", "value", "g", value=10)
    n = len(t.steps)
    out = t.deliver_through(c, "g")
    assert len(out) == 1 and out[0].frame == "A" and len(t.steps) == n + 1
    assert t.known_values(c) == {"g": 10}
    with pytest.raises(TraceError, match="already visible"):
        t.deliver_through(c, "g")


def test_deliver_through_skips_a_frame_that_sees_only_the_name():
    t, a, b, c = _chain()
    U(t, "x")
    t.deliver(a, "x")  # name only
    t.input(ROOT, "rx", "model", "x", relation="x = 2")
    t.derive(ROOT, "x = 2", binds="x", from_relations=["rx"])
    out = t.deliver_through(c, "x")
    assert out[0].frame == "A" and t.value_visible(c, "x") is not None


def test_deliver_through_where_the_target_declared_the_unknown():
    t, a, b, c = _chain()
    U(t, "x", b)
    t.input(ROOT, "rx", "model", "x", relation="x = 2")
    t.solve(ROOT, ["rx"], ["x"])
    out = t.deliver_through(b, "x")
    assert out[0].frame == "A" and t.value_visible(b, "x") is not None


def test_deliver_through_errors_record_nothing():
    t, a, b, c = _chain()
    t.input(ROOT, "cmp", "completeness", "closed")
    t.input(ROOT, "m", "value", "m", value=1, uses=["cmp"])
    t.input(ROOT, "w", "completeness", "to withdraw")
    t.withdraw(ROOT, "w", "no")
    t.withdraw(ROOT, "cmp", "no")
    n = len(t.steps)
    with pytest.raises(TraceError) as e1:
        t.deliver_through(c, "nope")
    with pytest.raises(TraceError) as e2:
        t.deliver_through(c, "w")
    with pytest.raises(TraceError) as e3:
        t.deliver_through(c, "m")
    assert not any(isinstance(e.value, HiddenLookupError) for e in (e1, e2, e3))
    assert len(t.steps) == n


def test_deliver_many_is_all_or_nothing_for_a_tainted_name():
    t = Trace("q")
    d = t.demand(ROOT, "D", "d")
    t.input(ROOT, "c", "completeness", "c")
    t.input(ROOT, "m", "value", "m", value=2, uses=["c"])
    t.input(ROOT, "g", "value", "g", value=1)
    t.withdraw(ROOT, "c", "no")
    n, k = len(t.steps), len(t.commands)
    with pytest.raises(TraceError, match="rests on 'c'"):
        t.deliver_many(d, ["g", "m"])
    assert (len(t.steps), len(t.commands)) == (n, k)


def test_deliver_many_of_a_name_with_a_withdrawn_value_delivers_the_name_only():
    t = _x_from_rx()
    d = t.demand(ROOT, "D", "d")
    t.withdraw(ROOT, "rx", "wrong")
    (st,) = t.deliver_many(d, ["x"])
    assert t.deliveries[d]["x"][-1].carries_value is False
    assert "x = 3" not in st.text


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


E8 = ("inertial-acceleration-material-object := For one material-object, its net-force-material-object divided "
      "by its inertial-mass-material-object.")
ENTRIES = {
    "E8": E8,
    "K16": "uniform-motion := A frame-indexed motion with constant velocity.",
    "E1": "uniform-motion := A frame-indexed motion with constant velocity.",
    "K4": "line := r0 + λu, with r0 fixed",
    "A": "the object's inertial mass is fixed",
    "C": unicodedata.normalize("NFD", "the café is open"),
}


def _entry(ref, quote):
    Trace("q", entries=ENTRIES).entry(ROOT, ref, quote)


@pytest.mark.parametrize("ref,quote", [
    ("E8", "divided by its"),
    ("K16 / E1", "A frame-indexed motion"),
    ("E8", "For one material-object"),
])
def test_quotes_that_verify(ref, quote):
    _entry(ref, quote)


@pytest.mark.parametrize("ref,quote,msg", [
    ("E8 / E99", "divided by its", "not in the supplied entries"),
    ("K16 / E8", "divided by its", "not verbatim"),
    ("E8", "inertial-acceleration-material-object :=", "two whole words"),
    ("E8", ":= For", "two whole words"),
    ("K4", "u, with r0", "not verbatim"),  # Unicode boundary: λ is a letter
    ("E8", "rce-material-object divided", "not verbatim"),
])
def test_quotes_that_are_refused(ref, quote, msg):
    with pytest.raises(TraceError, match=msg):
        _entry(ref, quote)


@pytest.mark.parametrize("ref,quote", [
    ("A", "s inertial mass"),  # the 's' of object's
    ("C", "the cafe"),  # NFD 'café': the combining acute (category Mn) is not \w
])
def test_word_fragments_at_odd_boundaries_are_refused(ref, quote):
    """F22-8, fixed in v2.3: an apostrophe before or a combining mark after the quote is not a word boundary."""
    with pytest.raises(TraceError):
        _entry(ref, quote)


def test_note_combined_ref_cosmetics():
    """A trailing slash and a repeated part are accepted and stored as written."""
    t = Trace("q", entries=ENTRIES)
    assert t.entry(ROOT, "E8 /", "divided by its").ref == "E8 /"
    t.entry(ROOT, "E8 / E8", "divided by its")
    # An NFC quote of an NFD entry is refused (no normalisation).
    with pytest.raises(TraceError, match="not verbatim"):
        t.entry(ROOT, "C", unicodedata.normalize("NFC", "the café is"))


# ---------------------------------------------------------------------------
# Ledger warnings and smaller items
# ---------------------------------------------------------------------------


def test_copy_made_before_the_withdrawal_is_flagged():
    t = Trace("q")
    t.input(ROOT, "c", "completeness", "only spring")
    t.input(ROOT, "c2", "completeness", "only spring")
    t.withdraw(ROOT, "c", "no")
    t.input(ROOT, "m", "value", "m", value=1, uses=["c2"])
    t.answer(["m"])
    w = warnings_of(t)
    assert any("c has since been withdrawn" in x for x in w)
    assert not any("deliver the original" in x for x in w)


def test_default_needs_warns_only_when_it_feeds_no_answer_and_scoped_status_warns_for_its_answer():
    t = Trace("q")
    for nm in "mkj":
        t.input(ROOT, nm, "value", nm, value=1)
    t.answer(["m"], label="pm")
    t.answer(["k"], label="pk")
    t.annotate("k", "NEEDS", countermodel="k = 4")
    t.annotate("j", "NEEDS", countermodel="j = 4")
    w = warnings_of(t, "pm")
    assert not any(x.startswith("k is marked") for x in w)
    assert any(x.startswith("j is marked NEEDS but does not feed") for x in w)
    t.annotate("k", "NEEDS", countermodel="k = 4", answer="pm")
    assert any(x.startswith("k is marked NEEDS but does not feed") for x in warnings_of(t, "pm"))


def test_same_description_warning_is_for_value_inputs_only():
    t = Trace("q")
    t.input(ROOT, "g", "value", "local g", value="9.8")
    for k in (1, 2):
        U(t, f"f{k}")
        t.input(ROOT, f"w{k}", "model", "uniform-field weight", relation=f"f{k} = -{k}*g")
    t.input(ROOT, "g2", "value/model", "local g", value="9.81")
    t.answer(["g"])
    w = warnings_of(t)
    assert not any("w2 has the same description" in x for x in w)
    assert any("g2 has the same description as g but a different value" in x for x in w)


def test_corrections_draw_a_different_value_note_and_third_copies_are_compared_with_the_live_copy():
    """V21R-8 leftovers. Still a note: a corrected value after withdrawal draws a bare 'different value'
    warning. Fixed in v2.3: a third copy is compared with the latest usable copy c2, not the withdrawn c."""
    t = Trace("q")
    t.input(ROOT, "m", "value", "mass", value=2)
    t.withdraw(ROOT, "m", "misread")
    t.input(ROOT, "m2", "value", "mass", value=3)
    t.input(ROOT, "c", "completeness", "only spring")
    t.input(ROOT, "c2", "completeness", "only spring")
    t.withdraw(ROOT, "c", "no")
    t.input(ROOT, "c3", "completeness", "only spring")
    t.answer(["m2"])
    w = warnings_of(t)
    assert "m2 has the same description as m but a different value" in w
    assert "c3 repeats the INPUT c2 word for word; deliver the original instead of re-supplying it" in w
    assert not any(x.startswith("c3 repeats c ") for x in w)


def test_a_failed_derive_binds_only_its_relation_name():
    t = Trace("q", strict=False)
    U(t, "x")
    t.input(ROOT, "r", "model", "x two", relation="x = 2")
    st = t.derive(ROOT, "x = 3", from_relations=["r"], binds="x", name="rbad")
    assert st.check == "failed" and st.binds == ("rbad",) and "x" not in t.values
    assert "⇒ rbad |" in [ln for ln in t.to_markdown().splitlines() if ln.startswith(f"| {st.id}")][0]


def test_answer_names_the_withdrawn_premise_of_a_tainted_value():
    t, _ = _joint_solve()
    t.withdraw(ROOT, "B", "y wrong")
    with pytest.raises(TraceError, match="the value of 'y' rests on 'B'"):
        t.answer(["y"])


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def _synthetic(n_target=500, chains=4, max_wd=10):
    t = Trace("synthetic")
    t.demand(ROOT, "D1", "sub")
    t.demand("D1", "D1a", "subsub")
    for c in range(chains):
        t.input(ROOT, f"k{c}", "value", f"offset {c}", value=c + 1)
        U(t, f"u{c}_0")
        t.input(ROOT, f"base{c}", "model", f"base {c}", relation=f"u{c}_0 = {c}")
        t.derive(ROOT, f"u{c}_0 = {c}", binds=f"u{c}_0", from_relations=[f"base{c}"])
        t.deliver_through("D1a", f"k{c}")
    vals = {c: c for c in range(chains)}
    last = {c: 0 for c in range(chains)}
    i = nans = nwd = 0
    while len(t.steps) < n_target:
        i += 1
        for c in range(chains):
            j = last[c] + 1
            U(t, f"u{c}_{j}")
            t.input(ROOT, f"r{c}_{j}", "model", f"step {c} {j}", relation=f"u{c}_{j} = u{c}_{j - 1} + k{c}")
            vals[c] += c + 1
            t.derive(ROOT, f"u{c}_{j} = {vals[c]}", binds=f"u{c}_{j}", from_relations=[f"r{c}_{j}"])
            last[c] = j
        nans += 1
        t.answer([f"u{c}_{last[c]}" for c in range(chains)], label=f"a{nans}")
        if i % 2 == 0 and nwd < max_wd:
            c = nwd % chains
            j = last[c]
            t.withdraw(ROOT, f"r{c}_{j}", "wrong step")
            nwd += 1
            t.input(ROOT, f"r{c}_{j}b", "model", f"step {c} {j} revised", relation=f"u{c}_{j} = u{c}_{j - 1} + k{c}")
            t.derive(ROOT, f"u{c}_{j} = {vals[c]}", binds=f"u{c}_{j}", from_relations=[f"r{c}_{j}b"])
    return t


def test_a_500_step_trace_with_withdrawals_ledgers_and_renders_quickly():
    t0 = time.perf_counter()
    t = _synthetic()
    t1 = time.perf_counter()
    led = t.ledger()
    t2 = time.perf_counter()
    md = t.to_markdown()
    t3 = time.perf_counter()
    rec = t.to_record()
    Trace.replay(rec)
    t4 = time.perf_counter()
    assert len(t.steps) >= 500 and len(t.answers) >= 30
    assert sum(b.withdrawn is not None for b in t.bindings.values()) == 10
    assert led["conflicts"] == [] and led["mistakes"] == []
    assert "## Ledger for answer a1" in md
    print(f"build {t1 - t0:.2f}s ledger {t2 - t1:.3f}s markdown {t3 - t2:.2f}s record+replay {t4 - t3:.2f}s")
    assert t2 - t1 < 2 and t3 - t2 < 20 and t4 - t3 < 30


def test_note_dense_eight_by_eight_solve_is_the_slow_spot():
    """Exhaustive search up to 8 relations: a dense 8x8 solve takes about 1.1 s here, a 9x9 about 0.2 s."""
    import random
    rnd = random.Random(1)
    t = Trace("q")
    names = [f"x{i}" for i in range(8)]
    for nm in names:
        U(t, nm)
    for i in range(8):
        lhs = " + ".join(f"{rnd.randint(1, 9)}*{nm}" for nm in names)
        t.input(ROOT, f"r{i}", "model", f"rel {i}", relation=f"{lhs} = {rnd.randint(1, 50)}")
    t0 = time.perf_counter()
    st = t.solve(ROOT, [f"r{i}" for i in range(8)], names)
    assert st.detail.startswith("unique") and time.perf_counter() - t0 < 20
