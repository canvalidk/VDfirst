"""Hand trace: one spring acting on one object (a_A = +1 m/s^2, f = +2 N).

Encodes codex VD newton/03_trace_and_evaluator/
SPRING_SINGLE_OBJECT_WORKED_TRACE_2026-11-08.md with the handtrace API (v2).
Every ENTRY quote, including the headwords quoted when unknowns are declared,
is verified against 07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md through
Trace(..., entries=load_entries(ENTRIES)).

The steps follow the source's order. The answer is recorded where the source
boxes it, after step 4. The source's 'Consequences carried by the same
account' (the -2 N counterpart, the open system, the value lock and the
independent E7/E9 route) and 'What remains to implement' come after it, as
consequences: steps after an answer cannot feed it.

Places where the API forced a choice are marked "API:" below.

    python handtrace_example_spring_single.py           # prints markdown and checks the numbers
    python -m pytest -q handtrace_example_spring_single.py
"""

from __future__ import annotations

import json
import os
import sys
from fractions import Fraction
from pathlib import Path

from handtrace import ROOT, HiddenLookupError, Trace, TraceError, load_entries

# Set VD_ENTRIES to the entries file; without it the quotes are not verified.
ENTRIES = Path(os.environ.get("VD_ENTRIES", "C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/"
                                           "07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md"))
FORCE_SUM = "07_design_2_1/CURRENT_STATE.md, 'Ratified Force-Sum Triplet Names - 2026-08-26'"
PROPOSED = "proposed connection (source trace, 'Status of the operations')"

QUESTION = "What is A's acceleration at instant t0?"
EDITION = {
    "dictionary": "Design 2.1 Draft 1 (DESIGN_2_1_DRAFT_1_ENTRIES.md)",
    "source trace": "SPRING_SINGLE_OBJECT_WORKED_TRACE_2026-11-08.md",
    "VD-Newton HEAD": "61afb9ecf6f17a89ca6425e7e7642d6761531b05",
}

# Verbatim, including the hard line break in the entries file (quotes are
# compared whitespace-normalised).
E8 = ("For one material-object, its net-force-material-object divided by\n"
      "its inertial-mass-material-object.")
E8_HEAD = "inertial-acceleration-material-object"  # E8's headword: the demanded quantity
E8_NET = "net-force-material-object"               # the first quantity E8 demands


def build() -> Trace:
    t = Trace(QUESTION, EDITION, entries=load_entries(str(ENTRIES)) if ENTRIES.exists() else None)

    # -- Question and supplied scene: model-wide stipulations, supplied with the question.
    # The scene's per-object items (mass, spring, interaction, values, activation,
    # completeness) are supplied where the trace first uses them, as the source's
    # "Supplied mass" and "Supplied complete membership" lines do.
    t.input(ROOT, "q_norm", "normalization",
            "the question asks for inertial-acceleration-material-object(A, t0, R); the conclusion concerns "
            "this instant, a constant acceleration over a later interval is not asserted")
    t.input(ROOT, "model1d", "model", "ideal one-dimensional model")
    t.input(ROOT, "R_inertial", "model", "R is a supplied inertial frame")
    t.input(ROOT, "axis", "convention", "rightward positive along the single axis of R")
    t.input(ROOT, "exact", "model", "all numerical quantities are exact stipulations")
    t.input(ROOT, "H", "haze", "haze is stipulated to be H = 0", value=0)
    t.input(ROOT, "A_body", "recognition/model", "target A is a material object, represented as a point body")

    # -- 1. Normalize the question and enter E8.
    d1 = t.demand(ROOT, "D1", "inertial-acceleration-material-object(A, t0, R)")
    # API: a delivery passes from the caller to the frame it calls, so scene items reach
    # D1.1 and D1.2 by being delivered into D1 (deliveries on the ancestor chain count).
    t.deliver_many(d1, ["q_norm", "R_inertial", "A_body", "model1d", "exact"])
    t.unknown(d1, "a_A", "the demanded inertial-acceleration-material-object(A, t0, R)",
              address="inertial-acceleration(A, t0, R)", label="ENTRY", ref="E8", quote=E8,
              unit="m/s^2", uses=["q_norm", "R_inertial", "A_body"])
    # API: E8's relation needs F_A and m_A bound first, so E8 is quoted here on entry
    # (binding nothing; the ledger lists it outside the answer) and again on return in step 4.
    t.entry(d1, "E8", E8, text="enter E8: it demands A's net force and A's inertial mass")
    d11 = t.demand(d1, "D1.1", "E8: demand net-force-material-object(A, t0, R)", ref="E8")
    d12 = t.demand(d1, "D1.2", "E8: demand inertial-mass-material-object(A)", ref="E8")
    t.input(d12, "m_A", "value",
            "inertial mass of A, supplied independently (not recovered by dividing by the acceleration "
            "being sought)", value=2, unit="kg", uses=["exact"])

    # -- 2. Resolve the force account.
    t.unknown(d11, "F_A", "the demanded net-force-material-object(A, t0, R)",
              address="net-force(A, t0, R)", label="ENTRY", ref="E8", quote=E8, unit="N")
    t.input(d11, "s_id", "identity", "spring s: explicit acting ID")
    t.input(d11, "i_s_id", "identity", "i_s: the identified spring interaction (through s) contributing to A",
            uses=["s_id"])
    t.input(d11, "support", "recognition", "the other participant of i_s is a support to A's right",
            uses=["i_s_id"])
    t.input(d11, "activation", "recognition",
            "spring s is attached, intact, and within the stipulated Hookean regime", uses=["s_id"])
    t.contract(d11, "C-member", "recognition to attributed membership: i_s is admitted to interaction-set(A) "
               "and keeps its connection to spring s", source=PROPOSED, binds="member_is",
               uses=["activation", "i_s_id"])
    t.input(d11, "complete", "completeness",
            "supplied complete membership: interaction-set(A) = {i_s}; i_s is the only interaction "
            "contributing to A in this model", uses=["member_is"])
    t.deliver(d1, "H", text="for the force account in D1.1")
    t.contract(d11, "C-activation-lock", "activation lock: admitting i_s commits the account to its activation "
               "conditions holding, with the original participant bindings (s, A, support)",
               source=PROPOSED, binds="act_lock", uses=["member_is", "activation", "support"])
    t.unknown(d11, "f_sA", "impressed-force(i_s -> A), the admitted member's contribution",
              address="impressed-force(i_s -> A, t0, R)", ref="Force-Sum", unit="N", uses=["member_is"])
    # API: no set or sum construct; the one-member instance is written out by hand. H = 0 is
    # recorded as a number but, as in the source, is not written as a term of the sum.
    t.contract(d11, "Force-Sum", "net-force(p | C) = sum of impressed-force(i -> p | C) for i in "
               "interaction-set(p | C); ratified relation, final entry cut unfinished; instance for "
               "interaction-set(A) = {i_s}", source=FORCE_SUM, binds="forcesum", relation="F_A = f_sA",
               uses=["complete", "H", "model1d"])
    t.open(d11, "the recognition document that would teach a reader to supply the scene verdict is not "
                "written; the verdict is an explicit input", uses=["activation"])

    # -- 3. Resolve the member's force expression.
    t.input(d11, "quote_conv", "convention", "quote this interaction's force on A (target-directed)")
    t.deliver(d1, "axis", text="for the spring expression in D1.1")
    t.input(d11, "k", "value", "stiffness of s", value=20, unit="N/m", uses=["exact", "s_id"])
    t.input(d11, "e", "value", "extension of s (stretched)", value="0.1", unit="m", uses=["exact", "s_id"])
    # API: the source calls this a "declared model contract" and lists spring dispatch among the
    # proposed connections; the handtrace docstring files supplied ideal model relations as INPUT
    # model. Filed as the source files it (finding enc-spring1-6, still open).
    t.contract(d11, "C-spring-dispatch", "the stretched spring pulls A rightward toward the support: "
               "f(i_s -> A) = +k e; dispatch exposes it for the same s, i_s, target, frame and instant",
               source=PROPOSED, binds="spring", relation="f_sA = k*e",
               uses=["act_lock", "s_id", "support", "axis", "quote_conv", "model1d"])
    t.derive(d11, "f_sA = 2", from_relations=["spring"], binds="f_sA", tag="multiplication",
             text="+k e = +(20)(0.1) = +2 N")

    # -- 4. Return through Force-Sum and E8.
    # Written as the source writes it (F_net,A = +2 N): the value of f_sA substituted into
    # Force-Sum carries the spring route into the answer's cone.
    t.derive(d11, "F_A = 2", from_relations=["forcesum"], binds="F_A", tag="summation",
             text="one member: F_net,A = +2 N")
    t.entry(d1, "E8", E8, text="return through E8", binds="e8", relation="a_A = F_A / m_A",
            uses=["A_body", "model1d"])
    t.derive(d1, "a_A = 1", from_relations=["e8"], binds="a_A", tag="division",
             text="F_net,A / m_A = (+2 N)/(2 kg) = +1 m/s^2")

    t.answer(["a_A"], "1 m/s^2 to the right (rightward positive), at instant t0")

    # -- Consequences carried by the same account (after the answer, as in the source).
    # Pairing: the -2 N reciprocal contribution belongs to the support's account.
    # API: no 'account' scope; a demand frame stands in for the support's account. The
    # counterpart bound there flows up to ROOT but is not visible in A's frames D1, D1.1.
    s = t.demand(ROOT, "S", "consequence, not demanded by the question: the support's account of i_s at t0")
    t.deliver(s, "f_sA")
    t.input(s, "recip_model", "model",
            "the model licenses representing the spring's reciprocal contribution on the support, "
            "neglecting spring inertia")
    t.unknown(s, "f_sS", "impressed-force(i_s -> support): a term of the support's account, not a second "
              "term in A's", address="impressed-force(i_s -> support, t0, R)", ref="C-pairing", unit="N",
              uses=["recip_model"])
    t.contract(s, "C-pairing", "reciprocal participant consequence of the admitted interaction",
               source=PROPOSED, binds="pair", relation="f_sS = -f_sA", uses=["recip_model"])
    t.derive(s, "f_sS = -2", from_relations=["pair"], binds="f_sS", tag="counterpart",
             text="-2 N on the support")

    # Open system: the system consisting only of A.
    t.input(ROOT, "sys_A", "choice", "the system consists only of A")
    t.reading(ROOT, "i_s crosses the boundary of the system {A} and its counterpart is outside; the open "
                    "system still supports the acceleration prediction because its external influence is "
                    "specified", uses=["sys_A", "f_sA", "f_sS", "a_A"])

    # Value lock: f(i_s -> A) = k e (spring route) = m_A a_A (net-force route, no other terms).
    t.contract(d1, "C-value-lock", "value lock: the same identified contribution f(i_s -> A) = k e (spring "
               "route) = m_A a_A (net-force route, no other terms)", source=PROPOSED, binds="vlock",
               relation="f_sA = m_A*a_A", uses=["act_lock", "complete"])
    # Checking the lock with the acceleration just predicted is the reuse the source warns
    # against: v2 reports it as holding identically, with no independent content.
    # API: the note depends on citing the relations; the same claim with no from_relations
    # is reported as a plain 'identity', like 2*3 = 6.
    t.derive(d1, "k*e = m_A*a_A", from_relations=["spring", "vlock"], tag="value lock (reuse)",
             text="(20)(0.1) = (2)(1): both routes give 2 N")
    t.open(d1, "an independently supplied trajectory could constrain a_A through E7, then net force through "
               "E9; disagreement with the spring route under the exact premises would make this account "
               "incompatible. None is supplied, and reusing the predicted a_A is not an independent check",
           uses=["vlock"])

    # The trace does not identify a spring from a number: s_id, i_s_id, activation and the
    # admitted membership are recorded before the force is evaluated (checked in the tests).

    # -- What remains to implement.
    t.open(ROOT, "still to implement: recognition content, its route to attributed membership, concrete force "
                 "dispatch, the entry-supported route from the admitted interaction to its counterpart, and a "
                 "warrant for completeness beyond enumeration when no exercise stipulates it",
           uses=["activation", "member_is", "spring", "pair", "complete"])
    return t


# -- checks ---------------------------------------------------------------------------------------


def _step(t: Trace, **match):
    return next(s for s in t.steps if all(getattr(s, k) == v for k, v in match.items()))


def test_source_numbers():
    t = build()
    v = t.values
    assert v["a_A"] == 1                                      # a = +1 m/s^2
    assert v["f_sA"] == 2 and v["F_A"] == 2                   # f(i_s -> A) = F_net,A = +2 N
    assert v["k"] == 20 and v["e"] == Fraction(1, 10) and v["k"] * v["e"] == 2
    assert v["m_A"] == 2 and v["H"] == 0
    assert v["f_sS"] == -2                                    # counterpart on the support
    assert all(s.check == "checked" for s in t.steps if s.op in ("DERIVE", "EXTERNAL"))
    assert t.ledger()["answer"] == "a_A = 1 m/s^2"


def test_entry_quotes_are_verified():
    if not ENTRIES.exists():
        import pytest
        pytest.skip(f"entries file not found: {ENTRIES}")
    t = build()
    assert set(t.entries) >= {"E7", "E8", "E9"}
    quoted = [s for s in t.steps if s.op == "ENTRY"]
    assert len(quoted) == 4 and all(s.ref == "E8" for s in quoted)
    try:
        t.entry("D1", "E8", "net force times mass, probably")
    except TraceError as exc:
        assert "verbatim" in str(exc)
    else:
        raise AssertionError("a misquote of E8 was accepted")


def test_consequences_follow_the_answer_in_source_order():
    t = build()
    ans = _step(t, op="ANSWER").index
    order = [_step(t, tag="counterpart").index,                       # pairing, -2 N
             _step(t, op="READING").index,                            # open system
             _step(t, op="CONTRACT", ref=f"C-value-lock ({PROPOSED})").index,
             _step(t, tag="value lock (reuse)").index,
             _step(t, op="OPEN", frame="D1").index,                   # independent E7/E9 route
             _step(t, op="OPEN", frame=ROOT).index]                   # what remains
    assert ans < order[0] and order == sorted(order)
    assert ans == _step(t, tag="division").index + 1                  # boxed right after step 4
    cone = t.cone()
    assert not any(i in cone for i in order)


def test_summation_as_written_keeps_the_spring_route():
    led = build().ledger()
    fed = {c["name"] for c in led["commitments"]}
    assert {"k", "e", "m_A", "H", "s_id", "i_s_id", "support", "activation", "complete", "exact", "q_norm",
            "model1d", "R_inertial", "A_body"} == fed
    assert {c["name"] for c in led["pruned"]} == {"axis", "quote_conv"}  # conventions are not members
    assert [s["tag"] for s in led["step_members"]] == ["multiplication", "summation", "division"]
    theory = " ".join(r["ref"] for r in led["theory"])
    for ref in ("C-member", "C-activation-lock", "Force-Sum", "C-spring-dispatch", "E8"):
        assert ref in theory


def test_ledger_lists_the_consequences_outside_the_answer():
    t = build()
    led = t.ledger()
    assert {c["name"] for c in led["not_in_answer"]} == {"recip_model", "sys_A"}
    outside = {(r["op"], r["ref"].replace(f" ({PROPOSED})", "")) for r in led["outside_answer"]}
    assert {("ENTRY", "E8"), ("CONTRACT", "C-pairing"), ("CONTRACT", "C-value-lock"), ("READING", ""),
            ("DERIVE", "counterpart"), ("DERIVE", "value lock (reuse)")} <= outside
    for key in ("conflicts", "unchecked", "solve_reports", "withdrawn", "undetermined"):
        assert led[key] == [], key
    assert len(led["open"]) == 3
    assert len(led["warnings"]) == 1 and led["warnings"][0].startswith("14 commitment(s) have no status yet")
    h = t.hypothesis_set()
    assert len(h) == 1 + 14 + 3 and h[0]["member"] == "the prediction holds: a_A = 1 m/s^2"


def test_value_lock_reuse_has_no_independent_content():
    st = _step(build(), tag="value lock (reuse)")
    assert st.check == "checked" and "no independent content" in st.detail


def test_counterpart_is_in_the_support_account_not_in_A():
    t = build()
    assert t.visible("D1", "f_sS") is None and t.visible("D1.1", "f_sS") is None
    assert t.value_visible(ROOT, "f_sS") is not None
    try:
        t.derive("D1.1", "F_A = f_sA + f_sS")
    except HiddenLookupError:
        pass
    else:
        raise AssertionError("A's account could use the support's counterpart")


def test_spring_identified_before_its_force_is_evaluated():
    t = build()
    force = _step(t, tag="multiplication").index
    for name in ("s_id", "i_s_id", "activation", "member_is", "act_lock"):
        assert t.bindings[name].step < force, name


def test_record_replays():
    t = build()
    again = Trace.replay(json.loads(t.to_json()))
    assert again.values == t.values and again.to_record()["sha256"] == t.to_record()["sha256"]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(build().to_markdown())
    for check in (test_source_numbers, test_entry_quotes_are_verified,
                  test_consequences_follow_the_answer_in_source_order,
                  test_summation_as_written_keeps_the_spring_route,
                  test_ledger_lists_the_consequences_outside_the_answer,
                  test_value_lock_reuse_has_no_independent_content,
                  test_counterpart_is_in_the_support_account_not_in_A,
                  test_spring_identified_before_its_force_is_evaluated, test_record_replays):
        if check is test_entry_quotes_are_verified and not ENTRIES.exists():
            continue
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
