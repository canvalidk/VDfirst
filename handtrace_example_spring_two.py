"""Hand trace: two moving objects, one spring, a missing contribution (handtrace v2).

Source: codex VD newton/03_trace_and_evaluator/
SPRING_TWO_OBJECTS_MISSING_FORCE_WORKED_TRACE_2026-11-08.md

    python handtrace_example_spring_two.py           # prints the markdown trace
    python -m pytest -q handtrace_example_spring_two.py

One trace answers the source's four questions in the source's order:

* Q1  spring-only predictions aA0 = 1, aB0 = -2/3 m/s^2 (answer "Q1"). It
      rests on the completeness hypothesis.
* Q2  E9 on B's trajectory input gives F_B = -3 N. The spring-only Force-Sum
      for B is checked against it by an exact solve, which reports an
      inconsistency (a conflict, listed in every ledger). The completeness
      premise is then withdrawn with withdraw(), and the revised account
      gives the remainder R_B = -1 N (answer "Q2").
* Q3  The two candidates are alternatives, so Q3 gets one conditional
      prediction per branch: aA_int = 3/2 (answer "Q3-internal") and
      aA_ext = 1 (answer "Q3-external"). A single answer naming both would
      put two exclusive branch hypotheses in one hypothesis set.
* Q4  A's trajectory input gives F_A = 2 N. The internal candidate's
      prediction is inconsistent with it (a second conflict) and the external
      one is compatible. The system sum and pair cancellation give the
      required external resultant F_ext = -1 N (answer "Q4").
§5 (R_A = 0 and the open items) is recorded after the answers, as
consequences that cannot feed them.

Net force on A and on B is one addressed quantity per body. The spring-only
account never gives it a value (Q1's claims about it are named relations),
so the trajectory side can fix it later, and each conflict is a solve over
one quantity, not an identity premise between two names.

What the recorder still cannot say (the test_open_* tests pin it down):

* the internal and external candidates are alternatives: nothing makes the
  two branch frames exclusive, both branch hypotheses can be used together
  at the root, and the refuted branch has no status;
* withdrawal disables only the INPUT name: relations and values derived from
  it stay citable, and only answers that rest on it are flagged;
* a predicted value cannot be retracted, so predictions of one quantity
  under different accounts need distinct, qualified addresses;
* units are carried, not checked; the observation side of each trial is not
  modelled.
"""

from __future__ import annotations

import json
import os
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from handtrace import ROOT, HiddenLookupError, Trace, TraceError, load_entries

# Set VD_ENTRIES to the entries file; without it the quotes are not verified.
ENTRIES = Path(os.environ.get("VD_ENTRIES", "C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/"
                                           "07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md"))

EDITION = {
    "entries": "Design 2.1 Draft 1, E7-E9 (DESIGN_2_1_DRAFT_1_ENTRIES.md)",
    "Force-Sum": "ratified relation, CURRENT_STATE.md (2026-08-26)",
    "connections": "NEWTON_ENTRY_STRUCTURE_SYNTHESIS_2026-11-08 sections 8-12 (proposals)",
    "source": "SPRING_TWO_OBJECTS_MISSING_FORCE_WORKED_TRACE_2026-11-08.md",
}
QUESTION = ("Q1 spring-only accelerations of A and B; Q2 what must change when B's independent "
            "acceleration disagrees; Q3 can the missing influence be internal or external; "
            "Q4 what makes an external contribution necessary")

E7 = ("For a material-object with a trajectory described in an inertial-frame, the acceleration "
      "read from that trajectory at a selected time.")
E8 = ("For one material-object, its net-force-material-object divided by its "
      "inertial-mass-material-object.")
E9 = ("For one material-object, its inertial-mass-material-object times its "
      "inertial-acceleration-material-object.")

FS = "CURRENT_STATE.md, ratified Force-Sum"
PAIR = "synthesis 10.1-10.2, proposed pairing connection"
REM = "synthesis 8.5, remainder invariant (proposal)"
CANCEL = "synthesis 10.5, stipulated Newtonian binary pairing"

LABELS = ["Q1", "Q2", "Q3-internal", "Q3-external", "Q4"]


def entries() -> dict[str, str] | None:
    """The Design 2.1 entries, so ENTRY quotes are verified verbatim (None if the file is absent)."""
    return load_entries(str(ENTRIES)) if ENTRIES.exists() else None


# -- the trace ------------------------------------------------------------------------------------


def scene(t: Trace) -> None:
    """Supplied scene, the initial hypothesis, and the spring pair (retained throughout)."""
    t.input(ROOT, "inertial_R", "model", "supplied inertial frame R; ideal one-dimensional model; all values "
            "concern the same instant t0 and are exact stipulations")
    t.input(ROOT, "axis", "convention", "rightward positive along the line of A and B")
    t.input(ROOT, "H", "haze", "haze H = 0: no unkeyed omitted influence (stipulated)", value=0, unit="N")
    t.input(ROOT, "rec_A", "recognition/model", "A is a material point-body target, left of B")
    t.input(ROOT, "rec_B", "recognition/model", "B is a movable material point-body target")
    t.input(ROOT, "m_A", "value", "inertial mass of A", value=2, unit="kg")
    t.input(ROOT, "m_B", "value", "inertial mass of B", value=3, unit="kg")
    t.input(ROOT, "id_mB", "identity/model", "B's supplied mass is the mass of the represented target "
            "under this approximation")
    t.input(ROOT, "rec_s", "recognition/model", "spring s (acting ID), carried by B and attached to A; "
            "attached, intact, and in the stipulated Hookean regime")
    t.input(ROOT, "inter_s", "recognition", "interaction i_s, with A and B as its represented participants")
    t.input(ROOT, "k", "value", "stiffness of s", value=20, unit="N/m")
    t.input(ROOT, "e", "value", "extension of s", value="0.1", unit="m")
    t.input(ROOT, "carrier", "model", "the model licenses treating the reciprocal spring contribution as a "
            "force on B; spring inertia is neglected (explicit component-to-carrier premise)")
    t.input(ROOT, "S", "choice", "chosen system S = {A, B} exactly, under this body representation")
    t.input(ROOT, "complete", "completeness", "initial hypothesis: i_s is the complete interaction account, "
            "interaction-set(A) = interaction-set(B) = {i_s}")

    t.unknown(ROOT, "f_sA", "impressed-force(i_s -> A)", address="impressed-force(i_s, A, t0, R)", ref=FS,
              unit="N")
    t.input(ROOT, "hooke", "model", "spring expression, quoted on A", relation="f_sA = k*e",
            uses=["rec_s", "inter_s", "rec_A", "axis", "inertial_R"])
    t.derive(ROOT, "f_sA = 20*0.1", from_relations=["hooke"], binds="f_sA", tag="spring on A")
    t.unknown(ROOT, "f_sB", "impressed-force(i_s -> B)", address="impressed-force(i_s, B, t0, R)", ref=PAIR,
              unit="N")
    t.contract(ROOT, "C-PAIR", "pairing consequence for the known interaction i_s", source=PAIR,
               binds="pair_s", relation="f_sB = -f_sA", uses=["inter_s", "carrier"])
    t.derive(ROOT, "f_sB = -2", from_relations=["pair_s"], binds="f_sB", tag="pairing")
    t.reading(ROOT, "A and B are inside S, so the i_s pair is internal; B's contribution is required without "
              "a second observation; the original spring activation bindings are retained (role reversal does "
              "not ask B to qualify as the nonowner attachment target)", uses=["S", "rec_A", "rec_B", "pair_s"])
    t.reading(ROOT, "one occurrence of i_s in each participant's target-specific account; its two opposite "
              "contributions are not two forces to add on either single target", uses=["pair_s"])


def q1(t: Trace) -> None:
    """Spring-only account under the completeness hypothesis. F_A and F_B get no value here."""
    d = t.demand(ROOT, "Q1", "Q1: what accelerations does a spring-only account predict for A and B?")
    t.deliver_many(d, ["f_sA", "f_sB", "m_A", "m_B", "H", "complete", "rec_A", "rec_B", "id_mB", "inertial_R"])
    for x, f, m, net, acc in (("A", "f_sA", "m_A", "2", "2/2"), ("B", "f_sB", "m_B", "-2", "-2/3")):
        t.unknown(d, f"F_{x}", f"net-force({x}) at t0 in R", address=f"net-force({x}, t0, R)", ref=FS, unit="N")
        t.contract(d, "C-FS", f"Force-Sum over the complete set {{i_s}} for {x} (haze H = 0)", source=FS,
                   binds=f"fs_{x}", relation=f"F_{x} = {f}", uses=["complete", "H", f"rec_{x}"])
        t.derive(d, f"F_{x} = {net}", from_relations=[f"fs_{x}"], name=f"F{x}_so", tag=f"Force-Sum {x}",
                 text=f"spring-only claim, kept as a named relation; F_{x} itself stays without a value")
        t.unknown(d, f"a{x}0", f"acceleration of {x} predicted by the spring-only account",
                  address=f"inertial-acceleration({x}, t0, R) | spring-only account", label="ENTRY", ref="E8",
                  quote=E8, unit="m/s^2")
        t.entry(d, "E8", E8, binds=f"e8_{x}0", relation=f"a{x}0 = F_{x} / {m}",
                uses=[f"rec_{x}", "inertial_R"] + (["id_mB"] if x == "B" else []))
        t.derive(d, f"a{x}0 = {acc}", from_relations=[f"F{x}_so", f"e8_{x}0"], binds=f"a{x}0", tag=f"E8 {x}")
    t.reading(d, "the full initial account is interaction-closed because its stipulated complete inventory "
              "contains only this internal pair; one internal pair alone would not prove closure",
              uses=["complete"])


def q2(t: Trace) -> None:
    """B's trajectory input, the conflict, the withdrawal and the remainder R_B."""
    d = t.demand(ROOT, "Q2", "Q2: B's independently determined acceleration disagrees; what must change in "
                 "that account?")
    t.deliver_many(d, ["axis", "inertial_R", "rec_B", "id_mB", "m_B", "f_sB", "H", "F_B", "fs_B", "complete"])
    t.input(d, "aB_traj", "value", "B's acceleration at t0 from an independently determined trajectory (exact "
            "ideal input, not a noisy measurement passed through the mass estimator)", value=-1, unit="m/s^2",
            uses=["axis", "inertial_R"])
    t.entry(d, "E7", E7, text="aB_traj is the acceleration read from B's supplied trajectory in R at t0",
            uses=["aB_traj", "rec_B", "inertial_R"], binds="e7_B")
    t.entry(d, "E9", E9, binds="e9_B", relation="F_B = m_B * aB_traj", uses=["e7_B", "rec_B", "id_mB"])
    t.derive(d, "F_B = 3*(-1)", from_relations=["e9_B"], binds="F_B", tag="E9 B")
    t.consistency(d, ["fs_B"], tag="conflict B", uses=["complete"],
            text="consistency check: the spring-only Force-Sum for B (-2 N) against the trajectory-side net "
                 "force of B (-3 N)")
    t.reading(d, "the spring-only account and the trajectory input cannot both hold with the retained premises; "
              "the discrepancy alone does not show that completeness, rather than another premise, was wrong",
              uses=["fs_B", "F_B"])
    t.withdraw(d, "complete", "explicitly withdrawn for a missing-interaction investigation (a chosen "
               "diagnostic branch); mass, frame, trajectory input, spring recognition, identity and expression "
               "are provisionally retained")
    t.unknown(d, "R_B", "unaccounted aggregate on B", address="remainder(B, t0, R)", ref=REM, unit="N")
    t.contract(d, "C-REM", "revised force account for B, completeness withdrawn", source=REM, binds="rev_B",
               relation="F_B = f_sB + R_B", uses=["H"])
    t.derive(d, "R_B = -3 - (-2)", from_relations=["rev_B"], binds="R_B", tag="remainder B")
    t.reading(d, "R_B is an unaccounted aggregate: it does not establish one unique interaction or identify an "
              "acting kind", uses=["R_B"])
    t.reading(d, "the known spring force cannot quietly become -3 N while its stiffness, extension, attribution "
              "and convention are retained", uses=["f_sB", "F_B"])


BRANCHES = (
    ("int", "internal", "q_in", "candidate: q is A, inside S; add +1 N to A's account",
     "F_A = f_sA + f_jq", "(2 + 1)/2"),
    ("ext", "external", "q_out", "candidate: q lies outside S; j crosses the boundary and supplies no "
                                 "contribution on A", "F_A = f_sA", "2/2"),
)


def q3(t: Trace) -> None:
    """The one-addition candidate j and its internal / external branches (sibling frames)."""
    d = t.demand(ROOT, "Q3", "Q3: can the missing influence be internal or external?")
    t.deliver_many(d, ["R_B", "f_sA", "m_A", "rec_A", "F_A", "H", "inertial_R"])
    t.input(d, "one_add", "completeness", "minimal candidate (provisional): one additional binary interaction "
            "j supplies the entire R_B on B, and j is the only addition", uses=["R_B"])
    t.unknown(d, "f_jB", "impressed-force(j -> B)", address="impressed-force(j, B, t0, R)", ref=FS, unit="N")
    t.contract(d, "C-FS", "j supplies the entire remainder on B", source=FS, binds="fs_jB",
               relation="f_jB = R_B", uses=["one_add"])
    t.derive(d, "f_jB = -1", from_relations=["fs_jB"], binds="f_jB", tag="j on B")
    t.unknown(d, "f_jq", "impressed-force(j -> q), q the other participant of j",
              address="impressed-force(j, q, t0, R)", ref=PAIR, unit="N")
    t.contract(d, "C-PAIR", "reciprocal contribution of the binary interaction j", source=PAIR,
               binds="pair_j", relation="f_jq = -f_jB", uses=["one_add"])
    t.derive(d, "f_jq = 1", from_relations=["pair_j"], binds="f_jq", tag="j on q")
    t.reading(d, "j is a provisional interaction address, not an observed acting-object ID", uses=["f_jB"])
    t.open(d, "j's mechanism and recognition content remain unknown; the candidate must still satisfy those "
           "obligations as well as the numerical constraint", uses=["f_jq"])
    for tag, word, hyp, text, rel, acc in BRANCHES:
        b = t.demand(d, f"Q3{tag}", f"{word} branch (an alternative, not a simultaneous assignment): {text}")
        t.deliver_many(b, ["one_add"] + (["f_jq"] if tag == "int" else []))
        t.input(b, hyp, "recognition", text)
        t.contract(b, "C-FS", f"A's account if j is the only addition ({word} candidate)", source=FS,
                   binds=f"fs_A{tag}", relation=rel, uses=["one_add", hyp, "H", "rec_A"])
        t.unknown(b, f"aA_{tag}", f"acceleration of A predicted by the {word} candidate",
                  address=f"inertial-acceleration(A, t0, R) | {word} candidate", label="ENTRY", ref="E8",
                  quote=E8, unit="m/s^2")
        t.entry(b, "E8", E8, binds=f"e8_A{tag}", relation=f"aA_{tag} = F_A / m_A", uses=["rec_A", "inertial_R"])
        t.derive(b, f"aA_{tag} = {acc}", from_relations=[f"fs_A{tag}", f"e8_A{tag}"], binds=f"aA_{tag}",
                 tag=f"a_A {word}")
    t.reading(d, "both branches remain possible from B's information alone; they are alternatives, not "
              "simultaneous assignments of q to two locations; the residual has not established that S is open",
              uses=["aA_int", "aA_ext"])
    t.reading(d, "the A predictions depend on the explicit one-addition hypothesis, not on every completion with "
              "several missing interactions", uses=["one_add"])


def q4(t: Trace) -> None:
    """A's trajectory input, the two branch checks and the required external resultant."""
    d = t.demand(ROOT, "Q4", "Q4: what additional information makes an external contribution necessary?")
    t.deliver_many(d, ["axis", "inertial_R", "rec_A", "rec_B", "m_A", "F_A", "F_B", "S", "carrier",
                       "aA_int", "e8_Aint", "aA_ext", "e8_Aext"])
    t.input(d, "aA_traj", "value", "A's acceleration at t0 from an independently supplied trajectory (exact "
            "ideal input)", value=1, unit="m/s^2", uses=["axis", "inertial_R"])
    t.entry(d, "E7", E7, text="aA_traj is the acceleration read from A's supplied trajectory in R at t0",
            uses=["aA_traj", "rec_A", "inertial_R"], binds="e7_A")
    t.entry(d, "E9", E9, binds="e9_A", relation="F_A = m_A * aA_traj", uses=["e7_A", "rec_A"])
    t.derive(d, "F_A = 2*1", from_relations=["e9_A"], binds="F_A", tag="E9 A")
    for tag, word in (("int", "internal"), ("ext", "external")):
        t.consistency(d, [f"e8_A{tag}"], tag=f"{word} candidate vs A's input", uses=["aA_traj"],
                text=f"consistency check: the {word} candidate's prediction for A against A's trajectory-side "
                     "net force")
    t.reading(d, "the minimal internal candidate is incompatible with A's input; the external one remains "
              "compatible, but compatibility does not identify its source or prove it is the only possible "
              "explanation", uses=["aA_int", "aA_ext"])
    t.unknown(d, "F_sum", "sum of the member net forces of S", address="member-sum(net-force, S, t0, R)",
              label="READING", unit="N")
    t.reading(d, "system sum over the represented bodies of S (E9 on each body)", binds="sum_S",
              relation="F_sum = F_A + F_B", uses=["S"])
    t.derive(d, "F_sum = 2*1 + 3*(-1)", from_relations=["sum_S"], binds="F_sum", tag="system sum")
    t.unknown(d, "F_ext", "net external contribution on S", address="external-resultant(S, t0, R)", ref=CANCEL,
              unit="N")
    t.contract(d, "C-CANCEL", "every internal pair cancels in the system sum; S contains exactly the represented "
               "bodies A and B", source=CANCEL, binds="cancel_S", relation="F_ext = F_sum",
               uses=["S", "carrier", "rec_A", "rec_B"])
    t.derive(d, "F_ext = -1", from_relations=["cancel_S"], binds="F_ext", tag="external resultant")
    t.reading(d, "does not depend on j being a unique real interaction: several external contributions could "
              "have this resultant, and additional internal interactions could exist while cancelling",
              uses=["F_ext"])


def remains(t: Trace) -> None:
    """Section 5, recorded after every answer: consequences that cannot feed them."""
    d = t.demand(ROOT, "S5", "section 5: what remains unknown (consequences recorded after the answers)")
    t.deliver_many(d, ["F_A", "f_sA", "H"])
    t.unknown(d, "R_A", "A's remaining aggregate", address="remainder(A, t0, R)", ref=REM, unit="N")
    t.contract(d, "C-REM", "revised force account for A", source=REM, binds="rev_A", relation="F_A = f_sA + R_A",
               uses=["H"])
    t.derive(d, "R_A = 2*1 - 2", from_relations=["rev_A"], binds="R_A", tag="remainder A")
    t.reading(d, "R_A = 0 does not prove A has no additional interactions (contributions could cancel there); "
              "a zero system resultant in another experiment would not prove that no external interaction "
              "crosses the boundary", uses=["R_A"])
    t.open(d, "the mechanism, number and identity of the external sources, their individual force laws and "
           "their recognition conditions")
    t.open(d, "entry connections still needed: recognition -> attributed membership; component -> carrier; "
           "admitted interaction -> paired membership; completeness claims -> permitted alternatives")


def build(*, strict: bool = True) -> Trace:
    """The whole source trace: four questions, five labelled answers, then section 5."""
    t = Trace(QUESTION, EDITION, strict=strict, entries=entries())
    scene(t)
    q1(t)
    t.answer(["aA0", "aB0"], "spring-only predictions under the completeness hypothesis", label="Q1")
    q2(t)
    t.answer(["R_B"], "with the completeness claim withdrawn, B's account needs an unaccounted aggregate",
             label="Q2")
    q3(t)
    t.answer(["aA_int"], "conditional prediction: if j's counterpart is A (inside S) and j is the only addition",
             label="Q3-internal")
    t.answer(["aA_ext"], "conditional prediction: if j's counterpart lies outside S and j is the only addition",
             label="Q3-external")
    q4(t)
    t.answer(["F_sum", "F_ext"], "with A's trajectory input the two-body resultant is nonzero, so a net "
             "external contribution is required", label="Q4")
    remains(t)
    return t


# -- helpers for the tests ------------------------------------------------------------------------


def tagged(t: Trace, tag: str):
    return next(s for s in t.steps if s.tag == tag)


def step_cone(t: Trace, index: int) -> set[int]:
    seen: set[int] = set()
    stack = [index]
    while stack:
        i = stack.pop()
        if i not in seen:
            seen.add(i)
            stack.extend(t.steps[i].deps)
    return seen


def inputs_of(t: Trace, indices) -> set[str]:
    return {t.steps[i].binds[0] for i in indices if t.steps[i].op == "INPUT"}


def names(rows) -> set[str]:
    return {r["name"] for r in rows}


SPRING = {"k", "e", "hooke", "rec_s", "inter_s"}


# -- the source's numbers -------------------------------------------------------------------------


def test_source_numbers():
    t = build()
    v = t.values
    assert v["f_sA"] == 2 and v["f_sB"] == -2                   # spring force on A; its counterpart on B
    assert v["aA0"] == 1 and v["aB0"] == F(-2, 3)               # initial accelerations
    assert v["F_B"] == -3 and v["R_B"] == -1                    # B net force from the trajectory; remainder
    assert v["f_jB"] == -1 and v["f_jq"] == 1                   # one-addition candidate j
    assert v["aA_int"] == F(3, 2) and v["aA_ext"] == 1          # single internal / external candidate
    assert v["F_A"] == 2 and v["F_sum"] == -1 and v["F_ext"] == -1   # two-body resultant; external
    assert v["R_A"] == 0                                        # A's remaining aggregate
    assert v["k"] * v["e"] == 2 and v["H"] == 0


def test_one_trace_answers_every_question():
    t = build()
    assert [lb for lb, _ in t.answers] == LABELS
    got = {lb: t.ledger(lb)["answer"] for lb in LABELS}
    assert got == {"Q1": "aA0 = 1 m/s^2, aB0 = -2/3 m/s^2", "Q2": "R_B = -1 N",
                   "Q3-internal": "aA_int = 3/2 m/s^2", "Q3-external": "aA_ext = 1 m/s^2",
                   "Q4": "F_sum = -1 N, F_ext = -1 N"}
    assert t.ledger()["label"] == "Q4"  # the default is the last answer


def test_every_derive_checks_without_superfluous_citations():
    t = build()
    derives = [s for s in t.steps if s.op == "DERIVE"]
    assert derives and all(s.check == "checked" for s in derives)
    assert not any("not needed" in s.detail or "holds identically" in s.detail for s in derives)


def test_entry_quotes_are_verified_against_the_entries_file():
    if not ENTRIES.exists():
        pytest.skip("Design 2.1 entries file not available")
    t = build()
    assert {"E7", "E8", "E9"} <= set(t.entries)
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E9", "For one material-object, its mass times its acceleration.")
    with pytest.raises(TraceError, match="quote"):
        t.unknown(ROOT, "x", "x", address="(x)", label="ENTRY", ref="E8")


# -- Q1: provenance through substituted values (the v1 cone bug is fixed) ------------------------


def test_q1_rests_on_completeness_and_the_whole_spring_route():
    led = build().ledger("Q1")
    members = names(led["commitments"])
    # The claims are written with literal numbers (F_A = 2); k and e still reach the cone.
    assert {"complete", "carrier", "H", "m_A", "m_B", "id_mB", "rec_A", "rec_B", "inertial_R"} | SPRING <= members
    assert names(led["pruned"]) == {"axis"}
    assert {"aB_traj", "aA_traj", "one_add", "S"} <= names(led["not_in_answer"])


# -- Q2: the conflict, the withdrawal and the remainder -------------------------------------------


def test_conflict_with_b_trajectory_is_recorded_as_a_conflict():
    t = build()
    st = tagged(t, "conflict B")
    assert st.op == "EXTERNAL" and st.check == "failed" and st.detail.startswith("conflict")
    # Its premises: the withdrawn completeness claim, the spring route and B's trajectory side.
    assert {"complete", "aB_traj", "m_B", "carrier"} | SPRING <= inputs_of(t, step_cone(t, st.index))
    for lb in LABELS:
        led = t.ledger(lb)
        assert st.id in [r["step"] for r in led["conflicts"]]
        assert st.id not in [r["step"] for r in led["solve_reports"]]  # a consistency check is not a solve
        assert not any("whose check failed" in w for w in led["warnings"])  # no answer rests on it


def test_completeness_is_withdrawn_and_unusable_afterwards():
    t = build()
    w = next(s for s in t.steps if s.op == "WITHDRAW")
    assert w.frame == "Q2" and w.uses == ("complete",) and w.index > tagged(t, "conflict B").index
    for lb in LABELS:
        assert [c["name"] for c in t.ledger(lb)["withdrawn"]] == ["complete"]
    with pytest.raises(TraceError, match="withdrawn"):
        t.reading(ROOT, "uses the withdrawn premise", uses=["complete"])
    with pytest.raises(TraceError, match="withdrawn"):
        t.deliver("Q4", "complete")
    with pytest.raises(TraceError, match="already withdrawn"):
        t.withdraw(ROOT, "complete", "again")


def test_q1_answer_keeps_its_premise_and_later_answers_do_not_rest_on_it():
    t = build()
    q1 = t.ledger("Q1")
    assert "complete" in names(q1["commitments"])  # recorded before the withdrawal: history, not an error
    assert not any("withdrawn" in w for w in q1["warnings"])
    for lb in LABELS[1:]:
        led = t.ledger(lb)
        assert "complete" not in names(led["commitments"]) and "complete" in names(led["not_in_answer"])
        assert not any("withdrawn" in w for w in led["warnings"])


def test_a_prediction_resting_on_the_withdrawn_premise_cannot_be_restated():
    """v2.1: withdrawal retracts consequences; aB0 rests on 'complete'."""
    t = build()
    with pytest.raises(TraceError, match="withdrawn"):
        t.answer(["aB0"], "the spring-only prediction restated after the withdrawal", label="late")


def test_withdrawal_needs_the_premise_visible_where_it_is_withdrawn():
    t = Trace(QUESTION, EDITION, entries=entries())
    scene(t)
    q1(t)
    d = t.demand(ROOT, "X", "a frame that was never given the premise")
    with pytest.raises(HiddenLookupError):
        t.withdraw(d, "complete", "not visible here")
    with pytest.raises(TraceError, match="INPUT"):
        t.withdraw(ROOT, "fs_B", "a CONTRACT relation is not a premise to withdraw")
    t.withdraw(ROOT, "complete", "the root sees every binding")


def test_q2_remainder_rests_on_b_trajectory_and_the_spring_not_on_completeness():
    led = build().ledger("Q2")
    assert names(led["commitments"]) == {"aB_traj", "m_B", "id_mB", "rec_A", "rec_B", "inertial_R", "H",
                                         "carrier"} | SPRING
    assert names(led["pruned"]) == {"axis"}
    assert "C-REM" in " ".join(r["ref"] for r in led["theory"])


# -- Q3: one conditional prediction per branch -----------------------------------------------------


def test_each_branch_answer_rests_on_its_own_hypothesis_only():
    t = build()
    inner, outer = t.ledger("Q3-internal"), t.ledger("Q3-external")
    assert {"one_add", "q_in", "aB_traj"} <= names(inner["commitments"])
    assert {"one_add", "q_out"} <= names(outer["commitments"])
    # v2.3: the external prediction aA_ext = f_sA / m_A never uses R_B's value (one_add names R_B but
    # does not substitute it), so B's trajectory is not a member there: any aB_traj gives aA_ext = 1.
    # The internal prediction uses f_jq = -f_jB = -R_B, so it does rest on aB_traj.
    assert "aB_traj" not in names(outer["commitments"])
    assert "q_out" not in names(inner["commitments"]) and "q_in" not in names(outer["commitments"])
    assert "complete" not in names(inner["commitments"]) | names(outer["commitments"])
    assert any(m["member"].startswith("not (candidate: q is A") for m in t.hypothesis_set("Q3-internal"))


def test_a_branch_frame_cannot_see_a_value_fixed_later_elsewhere():
    t = build()
    # F_A was delivered into Q3 without a value; Q4 fixed it later. Q3int sees the name, not the value.
    assert t.visible("Q3int", "F_A") is not None and t.value_visible("Q3int", "F_A") is None
    with pytest.raises(HiddenLookupError, match="F_A"):
        t.derive("Q3int", "F_A = 2")
    with pytest.raises(HiddenLookupError):
        t.deliver("Q3int", "F_B")  # the caller Q3 never saw F_B
    with pytest.raises(TraceError, match="root"):
        t.deliver(ROOT, "F_B")


# -- Q4: branch checks and the external resultant ------------------------------------------------


def test_a_input_refutes_the_internal_candidate_and_leaves_the_external_one():
    t = build()
    inner, outer = tagged(t, "internal candidate vs A's input"), tagged(t, "external candidate vs A's input")
    assert inner.check == "failed" and inner.detail.startswith("conflict")
    assert outer.check == "checked" and outer.detail == "consistent"
    assert {"q_in", "one_add", "aA_traj"} <= inputs_of(t, step_cone(t, inner.index))
    assert inner.id in [r["step"] for r in t.ledger("Q4")["conflicts"]]


def test_external_resultant_needs_only_frame_mass_trajectory_and_representation():
    t = build()
    led = t.ledger("Q4")
    assert names(led["commitments"]) == {"aA_traj", "aB_traj", "m_A", "m_B", "id_mB", "rec_A", "rec_B",
                                         "inertial_R", "carrier"}
    assert {c["name"]: c["why_pruned"] for c in led["pruned"]} == {
        "axis": "kind convention is not a claim about the world",
        "S": "kind choice is not a claim about the world"}
    # Not the spring, not completeness, not the one-addition candidate or its branches.
    assert not ({"complete", "one_add", "q_in", "q_out", "H"} | SPRING) & names(led["commitments"])
    members = " ".join(m["member"] for m in t.hypothesis_set("Q4"))
    assert "chosen system" not in members and "rightward positive" not in members


def test_section_5_consequences_follow_the_answers_and_feed_none():
    t = build()
    st = tagged(t, "remainder A")
    assert st.index > max(i for _, i in t.answers)
    assert all(st.index not in t.cone(lb) for lb in LABELS)
    assert st.id in [r["step"] for r in t.ledger("Q4")["outside_answer"]]
    assert len(t.ledger("Q4")["open"]) == 3


# -- fixed v1 findings, now ordinary behaviour -----------------------------------------------------


def test_a_contradicted_relation_no_longer_certifies_a_claim():
    """The spring-only Force-Sum fs_B is contradicted by F_B = -3 (recorded by the Q2 consistency
    check) and, after the withdrawal, it rests on a withdrawn premise and cannot be cited at all."""
    t = build()
    with pytest.raises(TraceError, match="withdrawn"):
        t.derive(ROOT, "F_B = -2", from_relations=["fs_B"])
    lenient = Trace(QUESTION, EDITION, strict=False, entries=entries())
    scene(lenient)
    q1(lenient)
    lenient.answer(["aA0", "aB0"], "spring-only predictions", label="Q1")
    lenient.input(ROOT, "FBm", "value", "trajectory-side net force on B (test)", value=-3, unit="N")
    lenient.input(ROOT, "fixFB", "model", "test: net force of B equals the trajectory-side value",
                  relation="F_B = FBm")
    st = lenient.derive(ROOT, "F_B = -3", from_relations=["fs_B", "fixFB"], tag="cites contradictory relations")
    assert st.check == "failed" and "contradict" in st.detail
    assert st.id in [r["step"] for r in lenient.ledger("Q1")["conflicts"]]


def test_haze_carries_its_number():
    t = build()
    assert t.bindings["H"].sort == "value" and t.values["H"] == 0
    assert next(s for s in t.steps if s.binds == ("H",)).kind == "haze"


def test_status_warning_is_one_summary_line():
    t = build()
    for lb in LABELS:
        assert len([w for w in t.ledger(lb)["warnings"] if "no status yet" in w]) == 1


def test_record_replays_and_renders():
    t = build()
    again = Trace.replay(json.loads(t.to_json()))
    assert again.values == t.values and [lb for lb, _ in again.answers] == LABELS
    assert set(t.to_record()["ledgers"]) == set(LABELS)
    md = t.to_markdown()
    for text in [f"## Ledger for answer {lb}" for lb in LABELS] + ["WITHDRAW", "### Withdrawn premises",
                                                                   "conflict", "| DELIVER |"]:
        assert text in md


# -- what remains open in v2 (documented, deliberately not failing) -------------------------------


def test_open_branches_are_not_exclusive_alternatives():
    """Q3's candidates are alternatives. No branch construct exists yet (spec section 9): branch
    results flow up unconditionally, and the root accepts both branch hypotheses at once."""
    t = build()
    t.reading(ROOT, "treats both candidate locations of q as facts at once",
              uses=["q_in", "q_out", "aA_int", "aA_ext", "fs_Aint", "fs_Aext"])
    led = t.ledger("Q4")
    assert "branches" not in led and "q_in" in names(led["not_in_answer"])  # refuted, but no status


def test_withdrawal_retracts_consequences():
    """Relations whose provenance includes the withdrawn premise cannot be used afterwards, and values
    resting on it are visible nowhere (the names stay usable). Earlier answers keep their history."""
    t = build()
    # v2.2: the name aB0 stays usable, but its value rests on 'complete' and is visible nowhere.
    assert t.value_visible(ROOT, "aB0") is None and "aB0" not in t.known_values(ROOT)
    # v2.3: the claim would check with the withdrawn value, so the refusal names the premise
    # instead of recording a mistake.
    with pytest.raises(TraceError, match="rests on a withdrawn premise"):
        t.derive(ROOT, "aB0 = -2/3")
    with pytest.raises(TraceError, match="withdrawn"):
        t.derive("Q1", "F_B = -2", from_relations=["fs_B"], tag="after the withdrawal")
    assert "complete" in names(t.ledger("Q1")["commitments"])


def test_open_one_quantity_under_several_accounts_needs_qualified_addresses():
    """A predicted value cannot be retracted, so each account's prediction of A's acceleration is a
    separate unknown with a qualified address. Addresses compare without whitespace."""
    t = build()
    addresses = sorted(b.address for b in t.bindings.values() if b.address.startswith("inertial-acceleration(A"))
    assert addresses == ["inertial-acceleration(A, t0, R) | external candidate",
                         "inertial-acceleration(A, t0, R) | internal candidate",
                         "inertial-acceleration(A, t0, R) | spring-only account"]
    with pytest.raises(TraceError, match="address"):
        t.unknown(ROOT, "aA_any", "acceleration of A", address="inertial-acceleration(A,t0,R)|spring-only account",
                  label="READING")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t = build()
    test_source_numbers()
    print(t.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
