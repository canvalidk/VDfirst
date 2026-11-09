"""The coupled-constraint Atwood trace (ATWOOD_COUPLED_CONSTRAINT_WORKED_TRACE_2026-11-08.md, "the CC
document") recorded with handtrace, so that its ledger can be compared by name with the reconciled
encoding (handtrace_example_atwood.py, "the companion").

Run from this directory:  python handtrace_example_atwood_cc.py
Or as tests:              python -m pytest handtrace_example_atwood_cc.py

What the encoding covers, in the CC document's order (§n are its sections):

* §1-§6 up to the answer p = {a1, a2, T}: body A is index 1 (3 kg), body B index 2 (5 kg), so a_A,
  a_B, T_A, T_B, m_A, m_B are a1, a2, T1, T2, m1, m2 as in the companion.
* §7, §8, §10 and §11 after the answer, as consequences: the value lock, the P-EQV formulas, pairing
  and the system sum, the residual check, the remaining entry-facing questions. §8's counterpart table
  is a second labelled answer, 'pairing'. §9 (comparison with the v3 trace) has no steps.
* Statuses only where the CC document states one (see ANNOTATIONS). The CC uses no status words; it
  says C_T and C_L follow from what each needs (§5) and P-EQV from the weight model on §2's reading of
  g (§7), so all four are ENTAILED. §10's four counterexample worlds and §7's field-strength example
  are re-run by the checker as finite-model checks (check_countermodel), not as statuses.

Recording choices (the CC document is pseudocode and leaves these open):

* §2's "one supplied inertial frame R" is one INPUT named R (the frame and its inertial claim);
  "the same instant t0 within an interval where ... hold" is t0 (a choice) and J (the regime claim).
* Labels: the CC's FORCE-SUM label is recorded as CONTRACT ref 'Force-Sum' (the recorder has no
  FORCE-SUM label). Steps the CC states without a label are READING (an interpretation) or OPEN (a
  gap); unknowns the CC introduces without an entry or contract are introduced by READING. OPEN here
  is the recorder's "remaining gap", wider than the CC's OPEN (a step no entry or contract yet
  authorizes): only §5's "from trajectory to E8" carries the CC's label. One exception: what the CC
  presents as a proposed connection without the label is a CONTRACT, as the CC's own definition has it
  (§2: "a proposed connection that an eventual entry route must expose"): §5's two endpoint-force
  responses ("Proposed endpoint-force response"), §7's value lock (the user's, which §7 says a
  constraint mechanism "fits") and §8's "proposed binary pairing contract". Checks the CC performs
  and passes (§6's nonnegative tension) and its remarks on them (§7's internal consistency) are
  READINGs, not OPENs.
* §2's string/pulley row is one INPUT (spc). §5's needs are INPUTs under the companion's names (Ea, Eb,
  Ka, Kb, Kc, diff). That they restate spc's clauses, and so cite spc, is this recording's reading:
  the CC says only "The string/pulley relations are separate ideal-mechanism inputs (§5)". Vertical
  segments, constant wrap and rigid attachments are one §5 bullet, so one INPUT (Kvde).
* C_T is the companion's meq (same relation T1 = T2, same needs). C_L is an INPUT relation
  a1 + a2 = 0, as the CC labels it; its length form and differentiation are its text.
* Moves (the API binds names before use): C_T is recorded after "What C_T needs"; C_L after its needs
  and after §5's OPEN block, whose reading it rests on as written in a_A, a_B.
* §5's OPEN says "Under translation, an attachment point has its body's acceleration"; translation is
  recorded as a premise (transl1, transl2).
* §6's "T = T_A = T_B" and "a = a_A = -a_B" are notation, recorded as convention INPUTs T := T_A and
  a := a_A; the other halves then follow from C_T and C_L. Defining them by both ends would restate
  C_T and C_L, and §10's worlds without them would become inconsistent.
* The answer p names a1, a2 and T; the CC returns T_A = T_B = 36.75 N, which are T1 and T2.
* A demand frame creates no dependency, so the two §5 endpoint-force responses reach p only because
  this recording cites them at the §6 step that uses C_T and C_L (the bundle they demanded); the CC's
  §6 makes no such citation. The citation also puts sigma1, which the responses use, in p's cone
  (pruned, a choice); without it sigma1 is out, as in the companion (build(cite_responses=False)).
* §4's "+T_A upward" cites §1's normalization (ideal), the only premise stating vertical segments
  before §5.
* §4's "two relations in four unknowns" is checked by an EXTERNAL solve that is this recording's
  check of the CC's count, not a CC step.
* §7's remainders bind Fnet1 = 7.35 and Fnet2 = -12.25 (m_A a_A and m_B a_B, the CC's "target's net
  force", through E8).
* Inequalities (T_A, T_B >= 0) are text: the recorder checks equalities only.

What the recording exposed (pinned by the tests below):

* The answer is the CC's: a1 = 49/20, a2 = -49/20, T = 147/4; §10's four worlds and §7's field-strength
  example reproduce exactly as finite-model checks (CC §10: "checks of this finite symbolic model").
* C_T and C_L are ENTAILED (CC §5: E-a and E-b give the common tension; tautness and inextensibility
  keep L constant), as the companion records M-EQ and M-KIN. The check by the other premises does not
  confirm it ('not entailed'), because their needs (Ea, Eb, Ka-Kc, Kvde, diff, the reading) carry no
  relation; the ledger warning is the record. For the same reason §10's worlds, which remove C_T or C_L
  as a unit, also falsify the conjunction of those needs without the checker seeing it.
* P-EQV's ENTAILED (on §2's free-fall reading of g) does not check: the reading is text in g's INPUT.
* C_L is labelled INPUT but written in the E8 unknowns: it contains the differentiation (an EXTERNAL
  step member in the companion) and rests on the reading that §5 flags OPEN only after displaying it.
* The force accounts N_A, N_B need vertical segments for +T_A upward. The CC states verticality in §1's
  idealization list, but neither §2's inputs table nor any §5 needs list except C_L's names it, so a
  verticality failure implicates the force accounts as well as C_L.
* On this recording's reading that §5's needs restate §2's row (so cite spc), C_T and C_L share spc
  (and §1's ideal, through it), although §5 says they rest on different premises; without that reading
  they share nothing. The same reading makes H(p) count the same commitments twice: 'not spc' beside
  'not Ea' ... 'not Kc'.
* One Fnet(A) serves as E8's net force and the Force-Sum net force with no stated identification (the
  companion's C-BR); E11 is never cited. §2 names "E9 for net force" and the CC's sources say "E8/E9
  used above", but no CC step names E9; this recording applies it where the CC computes net force as m·a
  (§7's "target's net force").
* μ_A, μ_B stay undetermined, as in the companion: P-EQV fixes them, but no step binds them (the CC
  applies P-EQV inside the weight values, §4's −m_A g, and states no μ value in the trace itself).
"""

from __future__ import annotations

import json
import os
import re
import sys
from fractions import Fraction
from pathlib import Path

from handtrace import ROOT, Trace, TraceError, load_entries

try:  # the tests below use pytest; the script runs without it
    import pytest
except ImportError:  # pragma: no cover
    pytest = None

# Set VD_ENTRIES to the entries file; without it the quotes are not verified.
ENTRIES = Path(os.environ.get("VD_ENTRIES", "C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/"
                                           "07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md"))

QUESTION = ("An Atwood machine: two masses m₁ = 3 kg and m₂ = 5 kg are connected by a massless, inextensible "
            "string over a frictionless pulley. Find the acceleration of each mass and the tension in the string. "
            "(The v3 exercise as quoted in CC §1; g = 9.8 m/s² as in its calculation.)")

EDITION = {
    "D": "Design 2.1 Draft 1 entries, VD-Newton HEAD 61afb9ec; the CC's sources say 'E7–E11 checked; E8/E9 used "
         "above'",
    "entries cited": "this recording cites E8 (§3), K12 and E7 (§5's OPEN, named by the CC), and E9 at §7's m·a; "
                     "no CC step names E9, "
                     "which §2 names 'for net force'",
    "Force-Sum": "ratified member/value relation (07_design_2_1/CURRENT_STATE.md); its full entry cut is unfinished",
    "context": "synthesis snapshot canvalidk/VD-docs@dcbbe698: NEWTON_ENTRY_STRUCTURE_SYNTHESIS_2026-11-08.md "
               "§§8-14 and the acting-object architecture consolidation",
    "source": "03_trace_and_evaluator/ATWOOD_COUPLED_CONSTRAINT_WORKED_TRACE_2026-11-08.md §§1-11, as revised on "
              "8 November 2026 with four points from the companion audit trace",
}

# Entry strings quoted verbatim (the same strings as handtrace_example_atwood.Q; Trace verifies them).
# The CC document names K12 and E7 without quoting them; the quotes are supplied by this recording.
Q = {
    "E9": "its inertial-mass-material-object times its inertial-acceleration-material-object",
    "E7": "For a material-object with a trajectory described in an inertial-frame, the acceleration "
          "read from that trajectory at a selected time.",
    "E8": "For one material-object, its net-force-material-object divided by its "
          "inertial-mass-material-object.",
    "K12": "equivalently, the second derivative of the trajectory, when defined.",
}

BODIES = ((1, "A", 3, "29.4"), (2, "B", 5, "49"))  # index, body, mass in kg, weight m·g in N as the CC writes it


# ---------------------------------------------------------------------------
# §1-§6: the trace up to the answer
# ---------------------------------------------------------------------------


def scope_and_inputs(t: Trace) -> None:
    """§1 the question and its idealizations; §2 the scope and the inputs table."""
    t.input(ROOT, "ideal", "normalization", "§1 the v3 exercise is read as the standard ideal Atwood model, its "
            "implicit idealizations made explicit: the pulley is fixed, its rotational inertia is neglected, the "
            "string is taut and remains attached, its free segments are vertical, and the mechanism has no "
            "relevant friction or other resistance. Negligible pulley inertia is stipulated, not inferred from a "
            "frictionless bearing; equal tension is a stated ideal-mechanism input whose VD entry derivation is "
            "unfinished (§5)")

    # §2 preamble
    t.input(ROOT, "R", "recognition/model", "§2 R: one supplied inertial frame for all vectors (no entry is cited; "
            "no Earth-bound support, at-rest or recoil clause is stated)")
    t.input(ROOT, "axis", "convention", "§2 upward positive for both bodies, in R; numerical coefficients carry the "
            "supplied SI units (said at §4)", uses=["R"])
    t.input(ROOT, "t0", "choice", "§2 t0: all values refer to the same instant")
    t.input(ROOT, "J", "model", "§2 t0 lies within an interval where the stated geometry and taut-string regime hold",
            uses=["t0"])
    t.input(ROOT, "haze", "haze", "§2 haze is H = 0, one stipulation for both accounts", value=0, unit="N")

    # §2 inputs table, row by row
    for k, B, _, _ in BODIES:
        t.input(ROOT, f"pp{k}", "recognition/model", f"§2 material target {B}, a body named apart from its numerical "
                "mass, represented as a point body (no entry is cited)")
    for k, B, mass, _ in BODIES:
        t.input(ROOT, f"m{k}", "value", f"§2 supplied inertial mass m_{B} = {mass} kg, an exact stipulation, not "
                "estimated from the acceleration sought (E10's positive-material-mass requirement is not applied "
                "to the massless string)", value=mass, unit="kg", uses=[f"pp{k}"])
    t.input(ROOT, "g", "value/model", "§2 g = 9.8 m/s², exact, the same at both targets, read as the local "
            "free-fall acceleration (moved before the weight relations, which mention it)", value="9.8",
            unit="m/s^2")
    for k, B, _, _ in BODIES:
        t.unknown(ROOT, f"mu{k}", f"μ_{B}, {B}'s gravitational mass, an address the gravity model opens; no entry "
                  "has it (§7)", address=f"μ({B})", label="READING", unit="kg", uses=[f"pp{k}"])
        t.unknown(ROOT, f"fG{k}", f"upward component of the gravity contribution f_g on {B}",
                  address=f"(i_g{B}, {B}, t0)", label="READING", unit="N", uses=[f"pp{k}", "t0"])
        t.input(ROOT, f"w{k}", "model", f"§2 gravity model on {B}: f_g = −μ g with the same g at both targets; "
                "supplied concrete force content, not derived from E8 or E9", relation=f"fG{k} = -mu{k}*g",
                uses=["axis"])
    for k, B, _, _ in BODIES:
        t.input(ROOT, f"peqv{k}", "identity/model", f"§2 P-EQV: μ_{B} = m_{B}, the gravitational mass in the weight "
                "is the supplied inertial mass (§7); a separate premise, not part of the weight law",
                relation=f"mu{k} = m{k}")
    t.input(ROOT, "ids", "identity", "§2 source and mechanism identities: Earth E; string s; ideal mechanism M "
            "comprising the declared string/pulley arrangement")
    t.input(ROOT, "attach", "recognition/model", "§2 A and B attach to the two ends of s and remain in the stated "
            "regime", uses=["ids", "pp1", "pp2", "J", "ideal"])
    for k, B, _, _ in BODIES:
        t.input(ROOT, f"comp{k}", "completeness", f"§2 {B}'s only modeled contributions are its gravity interaction "
                "and its string interaction; stipulated for the exercise (a matching sum will not prove it)",
                uses=[f"pp{k}"])
    t.input(ROOT, "spc", "model", "§2 string/pulley conditions: massless inextensible string; fixed ideal pulley "
            "with negligible inertia and friction; taut admissible configuration and motion. The CC says only "
            "'The string/pulley relations are separate ideal-mechanism inputs (§5)'; that E-a, E-b and C_L's needs "
            "restate these clauses, and so cite this row, is this recording's reading", uses=["ids", "ideal"])
    t.input(ROOT, "sysS", "choice", "§2 chosen system for the later closure question: S = {A, B}; Earth and string "
            "are outside S", uses=["pp1", "pp2", "ids"])


def normalize(t: Trace) -> None:
    """§3: three demands; E8 at the two acceleration demands; T_A and T_B at the tension demand."""
    t.input(ROOT, "norm", "normalization", "§3 the requested outputs become three demands: "
            "inertial-acceleration-material-object(A, t0, R), the same for B, and the tension of string s in the "
            "stated mechanism M. The last initially exposes two end-force magnitudes T_A and T_B; there is no "
            "shared scalar T yet, and their equality needs a relation", uses=["pp1", "pp2", "ids", "t0", "R"])
    for k, B, _, _ in BODIES:
        t.demand(ROOT, f"D{B}", f"inertial-acceleration-material-object({B}, t0, R)")
    t.demand(ROOT, "DT", "tension of string s in the stated mechanism M")
    t.deliver("DT", "norm", text="§3 the normalization that states this demand")
    for k, B, _, _ in BODIES:
        t.unknown("DT", f"T{k}", f"T_{B}, the end-force magnitude at {B}'s attachment, exposed by the tension demand; "
                  "its upward contribution on the block is +T_" + B, address=f"(i_s{B}, {B}, t0)", label="READING",
                  unit="N", uses=["norm"])
    for k, B, _, _ in BODIES:
        D = f"D{B}"
        t.deliver_many(D, [f"pp{k}", "R", "t0", "axis", "norm"], text="§3 the body idealization and the "
                       "inertial-frame commitment are delivered at this call; there is no need to assert that the "
                       "body is free")
        t.entry(D, "E8", Q["E8"], binds=f"e8_{k}", uses=["t0", "R"], text=f"§3 E8 supplies a_{B} = F_net,{B}/m_{B}. "
                "E7 gives a trajectory-side route if trajectories are supplied; the requested route is force-based "
                "prediction")
        t.unknown(D, f"a{k}", f"upward component of a({B}), the quantity {D} demands", address=f"a({B}, t0, R)",
                  label="ENTRY", ref="E8", quote=Q["E8"], unit="m/s^2", uses=[f"e8_{k}", f"pp{k}", "norm", "axis"])
        t.unknown(D, f"Fnet{k}", f"upward component of F_net,{B}, E8's net-force-material-object({B}); §4 writes "
                  f"the same Fnet({B}) for the Force-Sum net force", address=f"net-force({B}, t0, R)", label="ENTRY",
                  ref="E8", quote=Q["E8"], unit="N", uses=[f"e8_{k}", "t0", "R"])
        t.deliver(D, f"m{k}", text="§3 the supplied inertial mass (§2), for E8's denominator")
        t.entry(D, "E8", Q["E8"], binds=f"e8rel{k}", relation=f"a{k} = Fnet{k}/m{k}", uses=[f"e8_{k}"],
                text=f"§3 E8 for {B}")


def force_accounts(t: Trace) -> None:
    """§4: the interaction table, memberships, Force-Sum expansions, the return through E8."""
    for k, B, _, w in BODIES:
        t.derive(ROOT, f"fG{k} = -{w}", from_relations=[f"w{k}", f"peqv{k}"], binds=f"fG{k}", tag="§4 table",
                 text=f"i_g{B}: participants Earth E and {B}; contribution on {B}, upward component −m_{B} g = −{w} N "
                      "(the table applies P-EQV)")
    t.input(ROOT, "sigma1", "choice", "§4 the same physical string participates at two distinct interfaces; its "
            "identity links the mechanism description and does not merge i_sA and i_sB. A bounded representation "
            "choice for the trace, not a final decision about acting-object instance granularity", uses=["ids"])
    for k, B, _, w in BODIES:
        D = f"D{B}"
        t.deliver_many(D, ["ids", "attach", f"comp{k}", "haze", "ideal", f"fG{k}", f"T{k}"],
                       text=f"§4 for {B}'s force account")
        t.input(D, f"mem{k}", "recognition", f"§4 supplied membership interaction-set({B}) = {{i_g{B}, i_s{B}}}: "
                f"i_g{B} with participants Earth E and {B}; i_s{B} with string s at {B}'s attachment and {B}",
                uses=["ids", "attach"])
        t.contract(D, "Force-Sum", f"§4 (FORCE-SUM) Fnet({B}) = impressed-force(i_g{B} → {B}) + impressed-force(i_s{B} "
                   f"→ {B}) over the supplied membership, H = 0. The string member is +T_{B} upward; the CC gives no "
                   "premise for that direction here, so it is recorded as resting on §1's vertical free segments "
                   f"(ideal). The CC writes one Fnet({B}) for this sum and for E8's net force without stating the "
                   "identification", source="ratified Force-Sum relation (07_design_2_1/CURRENT_STATE.md); its full "
                   "entry cut is unfinished", binds=f"sum{k}", relation=f"Fnet{k} = fG{k} + T{k}",
                   uses=[f"mem{k}", f"comp{k}", "haze", "axis", "ideal"])
        t.derive(D, f"Fnet{k} = -{w} + T{k}", from_relations=[f"sum{k}"], name=f"retF{k}", tag="§4")
    t.reading(ROOT, "§4 the contributions are admitted before their tension values are known; inclusion commits the "
              "account to the applicable activation conditions: the attributed string attachments must be active in "
              "the declared regime (stated without a label or a citation)", binds="cadm",
              uses=["mem1", "mem2", "attach"])
    for k, B, mass, w in BODIES:
        D = f"D{B}"
        t.derive(D, f"a{k} = (T{k} - {w})/{mass}", from_relations=[f"e8rel{k}", f"retF{k}"], name=f"reta{k}",
                 tag="§4 return through E8")
        t.derive(D, f"{mass}*a{k} = T{k} - {w}", from_relations=[f"reta{k}"], name=f"N_{B}", tag=f"N_{B}",
                 text="numerical coefficients carry the supplied SI units")
    t.solve(ROOT, ["N_A", "N_B"], ["a1", "a2", "T1", "T2"], tag="§4 pending",
            text="this recording's check of §4's count, not a CC step (the CC states the count and runs no solve): "
                 "two relations in four unknowns, useful symbolic results that do not yet answer the question")


def mechanism(t: Trace) -> None:
    """§5: the endpoint-force responses, then the relations M supplies, with what each needs."""
    t.demand("DA", "DA.sA", "impressed-force(i_sA → A), the string member of A's account", ref="Force-Sum")
    t.deliver("DA", "sigma1", text="§5 the two interfaces stay distinct")
    t.deliver("DA.sA", "mem1", text="§5 the membership this member belongs to")
    src = ("CC §5, a proposal developing the managed acting-object architecture consolidation's attributed symbolic "
           "output for constraint mechanisms (CC §9)")
    t.contract("DA.sA", "endpoint-force response", "§5 proposed endpoint-force response: expression +T_A·up(R); "
               "subject i_sA acting on A at t0; linked mechanism M with supplied participants A, B and string s; "
               "demanded relations: the applicable ideal-mechanism relations (INPUT, below). Notation for the "
               "required connection; no final headword or law-house placement is chosen", source=src,
               binds="resp1", uses=["T1", "mem1", "ids", "sigma1"])
    t.demand("DB", "DB.sB", "impressed-force(i_sB → B), the string member of B's account", ref="Force-Sum")
    t.deliver("DB", "sigma1", text="§5 the two interfaces stay distinct")
    t.deliver("DB.sB", "mem2", text="§5 the membership this member belongs to")
    t.contract("DB.sB", "endpoint-force response", "§5 corresponding second-end response: expression +T_B·up(R); "
               "subject i_sB acting on B at t0; linked mechanism: the same M", source=src, binds="resp2",
               uses=["T2", "mem2", "ids", "sigma1"])
    M = t.demand("DA.sA", "M", "the applicable ideal-mechanism relations of M, demanded by A's endpoint-force "
                 "response; B's response links the same M")

    # Equal-tension relation
    t.deliver_through(M, "spc", text="§5 the §2 row whose clauses, on this recording's reading, the needs below "
                      "restate")
    t.input(M, "Ea", "model", "§5 (E-a) the string's mass is negligible; each hanging segment then carries one "
            "tension, and its end force equals it (what C_T needs; stated after C_T)", uses=["spc"])
    t.input(M, "Eb", "model", "§5 (E-b) the pulley exerts no net force along the string: frictionless contact, or "
            "a freely turning pulley of negligible inertia I/r² on a frictionless axle (what C_T needs). E-a alone "
            "is not enough: zero net force on a massless string fixes only the pulley's push on it, at T_A + T_B, "
            "and leaves T_A − T_B free", uses=["spc"])
    t.deliver_through(M, "T2", text="§5 the other end's magnitude, which C_T relates")
    t.input(M, "meq", "model", "§5 C_T, INPUT (ideal model relation): for the stipulated ideal string and pulley, M "
            "supplies T_A = T_B, with T_A, T_B ≥ 0 (text: the recorder checks equalities only). Recorded after its "
            "needs (moved). With E-a and E-b, T is the common tension of the two hanging segments; a single tension "
            "along the wrapped arc as well needs E-b's frictionless-contact branch. C_T does not need tautness (a "
            "slack string gives 0 = 0), inextensibility or a fixed support. It is not Newton III pairing between A "
            "and B, and it is not derived by dividing by the string's zero mass", relation="T1 = T2",
            uses=["Ea", "Eb"])
    t.open(M, "§5 a derivation of the ideal constraint relations within the full Newton dictionary remains work to "
           "do; 'infinite acceleration from F/0' is not an entry-supported substitute", uses=["meq"])

    # Fixed-length relation: its needs, the OPEN block, then C_L (moved after both)
    t.deliver_through(M, "J", text="§5 the regime interval")
    t.input(M, "Ka", "model", "§5 C_L needs an inextensible string (with tautness, L stays constant)", uses=["spc"])
    t.input(M, "Kb", "model", "§5 C_L needs a string that stays taut throughout an open interval around t0 (a value "
            "of the length at t0 alone does not fix a second derivative); a slack string would not impose C_L on "
            "the bodies' instantaneous motions", uses=["spc", "J"])
    t.input(M, "Kc", "model", "§5 C_L needs an axle at rest in R: moving geometry would change C", uses=["spc", "R"])
    t.input(M, "Kvde", "model", "§5 C_L needs vertical segments, a constant wrap, and rigid attachments (one bullet "
            "in the CC)", uses=["ideal", "attach"])
    t.input(M, "diff", "model", "§5 C_L needs trajectories that are twice differentiable", uses=["J"])
    t.entry(M, "K12", Q["K12"], binds="k12", text="§5 OPEN: differentiating gives second derivatives of the "
            "attachment trajectories, kinematic accelerations in the sense of K12 (named, not quoted, by the CC)")
    t.entry(M, "E7", Q["E7"], binds="e7", uses=["R", "t0"], text="§5 OPEN: and in the sense of E7, the "
            "trajectory-side definition (named, not quoted, by the CC)")
    t.deliver_through(M, "pp2", text="§5 for B's translation premise")
    for k, B, _, _ in BODIES:
        t.input(M, f"transl{k}", "model", f"§5 OPEN: under translation, an attachment point has its body's "
                f"acceleration; {B} is taken to translate (the CC states the condition; recording it as a premise "
                "is a choice)", uses=[f"pp{k}"])
    t.open(M, "§5 OPEN, from trajectory to E8: using these values as the E8 unknowns a_A, a_B identifies two "
           "definitions of inertial-acceleration-material-object (E7, trajectory-side; E8, force-side) for the same "
           "arguments. No entry, and no rule of the trace procedure, yet authorizes doing that at one site; the "
           "synthesis (§4.1) says that selecting a definition at a trace site 'remains an explicit execution issue'",
           uses=["e7", "k12"])
    for n in ("a1", "a2", "comp2"):
        t.deliver_through(M, n, text="§5 for the reading")
    t.reading(M, "§5 the step is taken here as a reading: for the same arguments (A or B, t0, R) the K12/E7 second "
              "derivative of the attachment trajectory and the E8 unknown are one quantity. Applied to these "
              "accounts it presupposes that both force accounts are complete", binds="rdE",
              uses=["e7", "k12", "a1", "a2", "transl1", "transl2", "comp1", "comp2"])
    t.input(M, "C_L", "model", "§5 C_L, INPUT (ideal model relation): for this fixed geometry, with y_A, y_B the "
            "upward coordinates of the attachment points, the string length has the form L = C − y_A − y_B, C "
            "holding fixed geometric terms including the fixed wrapped portion; tautness and inextensibility keep L "
            "constant; differentiating twice over the regime interval gives a_A + a_B = 0. Kinematic and separate "
            "from C_T; it does not need a massless string or a frictionless pulley, so C_T and C_L rest on different "
            "premises and a failed prediction can implicate one set without the other. Displayed in §5 before its "
            "needs and the OPEN block; moved after them so it can cite them, since as written in a_A, a_B it rests "
            "on the reading", relation="a1 + a2 = 0", uses=["Ka", "Kb", "Kc", "Kvde", "diff", "rdE", "axis"])
    t.open(ROOT, "§5 the bundle a_A, a_B, T_A, T_B with N_A, N_B, C_T, C_L and the regime checks (T_A, T_B ≥ 0; "
           "the supplied attachments, geometry and model conditions remain applicable) is returned to the caller. "
           "Had only A's acceleration been requested, the mechanism relation would expose "
           "dependence on B's motion, a reason to demand B's account; a future implementation must support this "
           "dependency without endlessly expanding the same pending demand", uses=["meq", "C_L"])


def solve_and_answer(t: Trace, cite_responses: bool = True) -> None:
    """§6: introduce T and a, subtract, return to all original demands; the answer p.

    cite_responses: this recording cites the two §5 endpoint-force responses at the step that uses C_T and
    C_L (the CC's §6 does not); False leaves the citation out, to show what it changes in p's ledger.
    """
    t.unknown(ROOT, "T", "the common magnitude T = T_A = T_B, introduced only now; it answers the tension demand",
              address="T(s in M, t0)", label="READING", unit="N", uses=["norm", "meq"])
    t.unknown(ROOT, "a", "the common magnitude a = a_A = −a_B", address="a(A = −B, t0, R)", label="READING",
              unit="m/s^2", uses=["C_L"])
    t.input(ROOT, "defT", "convention", "§6 notation T := T_A; T = T_B then follows by C_T. Defining T by one end is "
            "a recorded choice: defining it by both would restate C_T. Equality of the force magnitudes does not "
            "merge their interaction identities", relation="T = T1")
    t.input(ROOT, "defa", "convention", "§6 notation a := a_A; a = −a_B then follows by C_L (a recorded choice, as "
            "for T)", relation="a = a1")
    t.derive(ROOT, "3*a = T - 29.4", from_relations=["N_A", "defT", "defa"], name="nA6", tag="§6",
             text="the delivered bundle is received explicitly; no tension is retrieved through hidden trace memory")
    t.derive(ROOT, "-5*a = T - 49", from_relations=["N_B", "meq", "C_L", "defT", "defa"], name="nB6", tag="§6",
             uses=["resp1", "resp2"] if cite_responses else [],
             text="C_T and C_L reach the solve as the relations the two endpoint-force responses demanded (§5); "
                  "citing the responses here is this recording's choice" if cite_responses else "")
    t.derive(ROOT, "8*a = 19.6", from_relations=["nA6", "nB6"], name="n8a", tag="§6",
             text="subtract the second equation from the first")
    t.derive(ROOT, "a = 2.45", from_relations=["n8a"], binds="a", tag="§6", text="m/s²")
    t.derive(ROOT, "T = 3*(2.45) + 29.4", from_relations=["nA6"], binds="T", tag="§6", text="= 36.75 N")
    ret = "§6 return"
    t.derive(ROOT, "a1 = 2.45", from_relations=["defa"], binds="a1", tag=ret,
             text="acceleration(A, t0, R) = +2.45 m/s² up(R)")
    t.derive(ROOT, "a2 = -2.45", from_relations=["C_L", "defa"], binds="a2", tag=ret,
             text="acceleration(B, t0, R) = −2.45 m/s² up(R)")
    t.derive(ROOT, "T1 = 36.75", from_relations=["defT"], binds="T1", tag=ret)
    t.derive(ROOT, "T2 = 36.75", from_relations=["meq", "defT"], binds="T2", tag=ret, text="T_A = T_B = 36.75 N")
    t.reading(ROOT, "§6 the tension is positive (36.75 N), so the solution passes the nonnegative-tension check: a "
              "check the CC performs and passes, recorded as a reading (the inequality is checked by hand; the "
              "recorder checks equalities only). This necessary check does not independently prove attachment, "
              "tautness, completeness or correct model recognition; the prediction applies while the stipulated "
              "regime holds, and no initial positions or velocities were invented", uses=["T", "cadm", "meq"])
    t.answer(["a1", "a2", "T"], "§6 a(A), a(B) (upward components) and the common tension T at t0 in R, under the "
             "ideal-model premises; the CC returns T_A = T_B = T", label="p")


# ---------------------------------------------------------------------------
# After the answer: §7, §8, §10, §11
# ---------------------------------------------------------------------------


def consequences(t: Trace) -> None:
    # §7 the value lock at both interfaces
    t.contract(ROOT, "value lock", "§7 each tension is also the remainder left by removing the other contribution "
               "from its target's net force: the acting-force expression at each endpoint, its Force-Sum member and "
               "its inverse remainder refer to the same target-specific quantity; the mechanism additionally "
               "constrains the two quantities to have equal magnitudes. Recorded as a CONTRACT without a CC label: "
               "a proposed connection (the CC's §2 definition) whose source is the user", source="the user's value "
               "lock, as applied in CC §7", binds="vlock", uses=["T1", "T2", "sum1", "sum2"])
    for k, B, mass, w in BODIES:
        lock = f"§7 lock {B}"
        net = {1: "7.35", 2: "-12.25"}[k]
        t.derive(ROOT, f"T{k} = m{k}*a{k} - fG{k}", tag=lock, uses=["vlock", f"e8rel{k}"],
                 text=f"T_{B} = m_{B} a_{B} − (−m_{B} g)")
        t.entry(ROOT, "E9", Q["E9"], binds=f"e9rel{k}", relation=f"Fnet{k} = m{k}*a{k}", uses=[f"pp{k}"],
                text=f"{lock}: E9 gives {B}'s net force as m·a (§2 names E9 'for net force'; the CC computes it here)")
        t.derive(ROOT, f"Fnet{k} = {net}", from_relations=[f"e9rel{k}"], binds=f"Fnet{k}", tag=lock,
                 text=f"the first remainder term: m_{B} a_{B} = {net} N is {B}'s net force, the CC's \"target's net "
                      "force\" (E9)")
        t.derive(ROOT, f"{net} + {w} = 36.75", tag=lock)
    t.reading(ROOT, "§7 those equalities were used to obtain the solution, so substituting back checks internal "
              "consistency, not independent empirical confirmation; independently supplied trajectories, with their "
              "measurement uncertainties, could test whether the same relations remain compatible", uses=["vlock"])
    t.reading(ROOT, "§7 this is how a constraint mechanism fits the user's force lock: its acting-force expression "
              "can be an addressed unknown whose value is jointly constrained. It need not be an independently "
              "evaluable formula like ke before it is admitted", uses=["vlock", "resp1", "resp2"])

    # §7 the mass in the weight: "without that identification, the same relations give" (so no P-EQV is cited)
    same = ["w1", "w2", "sum1", "sum2", "e8rel1", "e8rel2", "meq", "C_L", "defT"]
    t.derive(ROOT, "a1 = (mu2 - mu1)*g/(m1 + m2)", from_relations=same, tag="§7 P-EQV",
             text="without P-EQV the same relations give this. The recorder checks it at the visible values, which "
                  "already apply P-EQV through fG1, fG2 (μ = m); the tests check it at other μ through "
                  "check_countermodel")
    t.derive(ROOT, "T = g*(m1*mu2 + m2*mu1)/(m1 + m2)", from_relations=same, tag="§7 P-EQV",
             text="as for a_A: checked here at the visible values only")
    t.reading(ROOT, "§7 when P-EQV follows: if g is read as the local free-fall acceleration (§2's reading), a body "
              "in free fall has m g = μ g, so μ = m, and P-EQV follows from the weight model. If g is read as a "
              "field strength in N/kg, P-EQV is an independent premise; for example μ_B = 6 kg with m_B = 5 kg gives "
              "a_A = 147/40 m/s²", uses=["g", "w1", "w2", "peqv1", "peqv2"])
    t.open(ROOT, "§7 the unit does not decide between the readings (m/s² and N/kg are the same unit). No entry "
           "mentions gravity, so P-EQV has no home in the entries; a future gravity entry must decide whether to "
           "cite E10's inertial mass or open a separate address", uses=["peqv1", "peqv2", "g"])

    # §8 pairing and the separate closure question
    src = "CC §8, 'the proposed binary pairing contract' (no section cited)"
    t.contract(ROOT, "pairing", "§8 under the proposed binary pairing contract each contribution on a block has a "
               "required counterpart; their locations follow from the supplied participants", source=src,
               binds="cpair", uses=["mem1", "mem2", "ids", "sigma1"])
    for i, force, recipient, value in (("G1", "fG1", "Earth E", "29.4"), ("G2", "fG2", "Earth E", "49"),
                                       ("S1", "T1", "string s at A's interface", "-36.75"),
                                       ("S2", "T2", "string s at B's interface", "-36.75")):
        body = "A" if i.endswith("1") else "B"
        inter = f"i_{i[0].lower()}{body}"
        t.unknown(ROOT, f"c{i}", f"upward component of {inter}'s counterpart, on {recipient}",
                  address=f"({inter}, {recipient}, t0)", ref="pairing", unit="N", uses=["cpair"])
        t.contract(ROOT, "pairing", f"§8 {inter}'s counterpart is the negation of its contribution on {body}",
                   source=src, binds=f"pair{i}", relation=f"c{i} = -{force}", uses=["cpair"])
        t.derive(ROOT, f"c{i} = {value}", from_relations=[f"pair{i}"], binds=f"c{i}", tag="§8 table",
                 uses=["sysS"], text="recipient inside S = {A, B}? No")
    t.answer(["cG1", "cG2", "cS1", "cS2"], "§8 the counterparts of the four block contributions under the proposed "
             "pairing contract, for the separate closure question; a second result, labelled apart from p",
             label="pairing")
    t.reading(ROOT, "§8 equal tension does not turn the two block-side string forces into a reciprocal pair. The "
              "system is interaction-open; its two target accounts can nevertheless be complete for the stated model "
              "and sufficient for prediction: the missing values were supplied by relations belonging to the external "
              "mechanism, and openness did not forbid solving them. There is no need to expand the system to Earth and "
              "the support to answer the posed question", uses=["cpair", "sysS", "meq"])
    t.derive(ROOT, "Fnet1 + Fnet2 = 2*T - (m1 + m2)*g", from_relations=["sum1", "sum2"], tag="§8 system",
             text="the elimination of T at §6 subtracted the two upward-coordinate equations; it is not cancellation "
                  "of an internal force pair. The actual total force on S is the sum")
    t.derive(ROOT, "2*T - (m1 + m2)*g = 73.5 - 78.4", tag="§8 system")
    t.derive(ROOT, "73.5 - 78.4 = -4.9", tag="§8 system")
    t.derive(ROOT, "m1*a1 + m2*a2 = 3*(2.45) + 5*(-2.45)", tag="§8 system", text="agrees with the force sum")
    t.derive(ROOT, "3*(2.45) + 5*(-2.45) = -4.9", tag="§8 system")

    # §10 the exact checks the CC reports (its counterexample worlds are finite-model checks: CC_WORLDS below)
    t.consistency(ROOT, ["N_A", "N_B", "meq", "C_L"], tag="§10",
                  text="§10 all four solved relations have zero residual")

    # §11 remaining entry-facing work
    for n, q in enumerate((
            "how a concrete string-force entry exposes its addressed unknown and the applicable mechanism relations",
            "how two endpoint interactions connect to the same mechanism without merging them or borrowing context "
            "invisibly",
            "where the equal-tension and fixed-length relations live in the dictionary, and how their "
            "recognition/regime requirements are exposed",
            "how an implementation retains pending quantities, collects coupled relations and invokes a declared "
            "solving competence",
            "what entry route supplies or warrants per-body membership/completeness when an exercise does not "
            "stipulate it",
            "where P-EQV lives: a gravity entry must cite E10's inertial mass or open a separate gravitational-mass "
            "address",
            "what authorizes using a trajectory-side (E7) acceleration as the force-side (E8) unknown for the same "
            "arguments at one trace site"), 1):
        t.open(ROOT, f"§11.{n} {q}")


# ---------------------------------------------------------------------------
# Statuses: only where the CC document states one
# ---------------------------------------------------------------------------

RELATION_NOTE = ("The CC uses no status words; it says {rel} follows from what it needs: {quote} ({where}). Those "
                 "needs ({needs}) carry no relation here, so the check by the other premises cannot confirm the "
                 "entailment; its warning is the record of that. §10's worlds without {rel} are finite-model checks "
                 "(CC §10: 'These are checks of this finite symbolic model'), run in the tests, not countermodels to "
                 "this status; they remove {rel} as a unit, so they also falsify the conjunction of its needs. "
                 "{companion}")
PEQV_NOTE = ("§7: on §2's reading of g (local free-fall acceleration) P-EQV follows from the weight model; on a "
             "field-strength reading it is an independent premise (NEEDS: μ_B = 6 kg with m_B = 5 kg gives "
             "a_A = 147/40 m/s²). The free-fall reading is text in g's INPUT, not a recorded relation, so the "
             "entailment cannot be checked from the recorded premises.")

# name: (status, countermodel, check spec, note). An empty entailed_by checks against all the other premises.
ANNOTATIONS = {
    "meq": ("ENTAILED", "", {"entailed_by": []},
            RELATION_NOTE.format(rel="C_T", quote="'With E-a and E-b, T is the common tension of the two hanging "
                                 "segments'", where="CC §5, line 154, after 'What C_T needs', lines 145-148",
                                 needs="Ea, Eb", companion="The companion records M-EQ (meq) ENTAILED likewise.")),
    "C_L": ("ENTAILED", "", {"entailed_by": []},
            RELATION_NOTE.format(rel="C_L", quote="'Tautness and inextensibility require L to remain constant. "
                                 "Differentiating twice over the regime interval gives: ... C_L'",
                                 where="CC §5, line 168, with 'What C_L needs', lines 176-182, and the reading of "
                                       "line 195",
                                 needs="Ka, Kb, Kc, Kvde, diff, transl1, transl2, the reading rdE",
                                 companion="The companion records M-KIN (mkin) ENTAILED likewise and derives the "
                                           "coupling (coup).")),
    "peqv1": ("ENTAILED", "", {"entailed_by": ["w1", "g"]}, PEQV_NOTE),
    "peqv2": ("ENTAILED", "", {"entailed_by": ["w2", "g"]}, PEQV_NOTE),
}


def build(cite_responses: bool = True) -> Trace:
    """The recording; cite_responses=False drops this recording's citation of the §5 responses at §6."""
    t = Trace(QUESTION, EDITION, entries=load_entries(str(ENTRIES)) if ENTRIES.exists() else None)
    scope_and_inputs(t)
    normalize(t)
    force_accounts(t)
    mechanism(t)
    solve_and_answer(t, cite_responses)
    consequences(t)
    for name, (status, cm, check, note) in ANNOTATIONS.items():
        t.annotate(name, status, countermodel=cm, note=note, answer="p", check=check)
    return t


# ---------------------------------------------------------------------------
# Names: every INPUT here, against the companion's bindings
# ---------------------------------------------------------------------------

# cc_name: (companion name(s) or None, relation, reason). Several companion names are joined by '+'.
# same: the same claim; split: the CC states as its own premise what the companion states inside other(s);
# merged: one CC premise states what the companion states in several (wholly or in part);
# different: the companion has a counterpart stated differently; new: the companion has none.
NAME_MAP = {
    "ideal": (None, "new", "§1 reads the v3 wording as the standard ideal model and lists its idealizations; the "
              "companion's only such reading ('frictionless pulley' as negligible inertia) sits inside Eb"),
    "R": ("rin", "different", "one supplied inertial frame, no entry cited; the companion binds R by ENTRY K2 and "
          "stipulates it inertial in rin via E5, with support-at-rest and recoil clauses"),
    "axis": ("axis", "different", "upward positive for both bodies, SI units, and no origin; the companion's axis "
             "also fixes R's origin at the pulley axle and puts both blocks on one ŷ axis, which its mkin uses"),
    "t0": ("t0", "different", "a choice with no entry; the companion binds t0 by ENTRY K1"),
    "J": ("J", "different", "an interval around t0 on which the geometry and taut-string regime hold, at §2; the "
          "companion's J is an open interval (K6) with trajectories in R (K8), at the E7 site"),
    "haze": ("haze1+haze2", "merged", "one H = 0 for both accounts"),
    "pp1": ("pp1", "same", "A as a point body; the CC cites no K7 and states both bodies in one row"),
    "pp2": ("pp2", "same", "B as a point body; the CC cites no K7 and states both bodies in one row"),
    "m1": ("m1", "same", "3 kg, exact"),
    "m2": ("m2", "same", "5 kg, exact"),
    "g": ("g", "same", "9.8 m/s² exact, the same at both targets, read as the local free-fall acceleration"),
    "w1": ("w1", "same", "fG1 = −μ1 g; the CC does not say near-surface uniform field or binary with E"),
    "w2": ("w2", "same", "fG2 = −μ2 g; the CC does not say near-surface uniform field or binary with E"),
    "peqv1": ("peqv1", "same", "μ_A = m_A"),
    "peqv2": ("peqv2", "same", "μ_B = m_B"),
    "ids": (None, "new", "Earth E, string s and mechanism M as declared identities; the companion's persist is about "
            "not re-identifying objects"),
    "attach": ("admS1+admS2", "split", "attachment of both ends, persisting in the regime, as its own input; the "
               "companion has 'attached to end k' inside admS1/admS2. It says nothing of rigidity: rigid attachment "
               "(the companion's Kde) is in §5's bullet, Kvde"),
    "comp1": ("comp1", "same", "A's account is exactly {gravity, string}; the CC states both bodies in one row"),
    "comp2": ("comp2", "same", "B's account is exactly {gravity, string}; the CC states both bodies in one row"),
    "spc": ("Ea+Eb+Ka+Kb+Kc", "merged", "§2's summary row. That §5 restates its clauses as Ea, Eb, Ka, Kb, Kc, which "
            "cite it, is this recording's reading; the CC says only that the string/pulley relations are separate "
            "ideal-mechanism inputs (§5)"),
    "sysS": ("sysS", "same", "S = {A, B}; stated at §2 for the later closure question, the companion's at T§7.2"),
    "norm": ("norm", "different", "the tension demand is the tension of s in M, exposing T_A and T_B with no shared "
             "T; the companion's D3 is B1's end force (a recorded choice)"),
    "sigma1": ("sigma1", "same", "one string at two distinct interfaces; kind choice ('a bounded representation "
               "choice') at §4, before the answer; the companion's is kind model, at T§7.2. It feeds p here only "
               "through this recording's citation of the §5 responses at §6"),
    "mem1": ("admG1+admS1", "merged", "one supplied membership for A; the companion admits each interaction with its "
             "activation conditions"),
    "mem2": ("admG2+admS2", "merged", "one supplied membership for B; the companion admits each interaction with its "
             "activation conditions"),
    "Ea": ("Ea", "same", "negligible string mass"),
    "Eb": ("Eb", "same", "no net pulley force along the string (frictionless contact, or negligible I/r² on a "
           "frictionless axle); the companion's normalization note is §1's ideal here"),
    "meq": ("meq+pull1+pull2", "merged", "C_T: the same relation T1 = T2 with the same needs; it also carries "
            "T_A, T_B ≥ 0, which the companion puts in pull1/pull2"),
    "Ka": ("Ka", "same", "inextensible string"),
    "Kb": ("Kb", "same", "taut throughout an open interval around t0"),
    "Kc": ("Kc", "same", "axle at rest in R"),
    "Kvde": ("Kde+pull1+pull2", "merged", "vertical segments with constant wrap and rigid attachments, one bullet; "
             "the companion puts verticality in pull1/pull2"),
    "diff": ("diff", "same", "trajectories twice differentiable"),
    "transl1": ("transl1", "same", "A translates; the CC states it as a condition inside §5's OPEN"),
    "transl2": ("transl2", "same", "B translates; the CC states it as a condition inside §5's OPEN"),
    "C_L": ("coup", "different", "the relation a1 + a2 = 0 as an INPUT; in the companion it is the DERIVE coup [22] "
            "from M-KIN (mkin, an INPUT fact), the EXTERNAL differentiation dkin and the READINGs rd1, rd2"),
    "defT": ("t9", "different", "notation T := T_A at §6; the companion carries T by CONTRACT C-T9 (T = T1) at [19]"),
    "defa": (None, "new", "the common a = a_A; the companion has none"),
}
RELATIONS = ("same", "split", "merged", "different", "new")


def input_names(t: Trace) -> list[str]:
    return [n for n, b in t.bindings.items() if t.steps[b.step].op == "INPUT"]


def _placements(led: dict) -> dict[str, str]:
    out = {c["name"]: "member" for c in led["commitments"]}
    out.update({c["name"]: "pruned" for c in led["pruned"]})
    out.update({c["name"]: "out" for c in led["not_in_answer"]})
    return out


def compare_with_companion(t: Trace) -> str:
    import handtrace_example_atwood as companion
    c = companion.build()
    mine, theirs = _placements(t.ledger("p")), _placements(c.ledger("p"))
    L = ["## Name map and placements for p (CC → companion)", "",
         "| CC input | CC placement | Companion | Relation | Companion placement | Reason |",
         "|---|---|---|---|---|---|"]
    for n, (cn, rel, why) in NAME_MAP.items():
        place = "; ".join(f"{x}: {theirs.get(x, 'not an INPUT')}" for x in cn.split("+")) if cn else ""
        L.append(f"| {n} | {mine[n]} | {cn or ''} | {rel} | {place} | {why} |")
    shared = sorted(n for n in mine if n in theirs)
    L += ["", "### Same names, compared (with the NAME_MAP relation: only 'same' rows state the same claim)", ""]
    L += [f"- {n} ({NAME_MAP[n][1]}): CC {mine[n]}, companion {theirs[n]}" for n in shared]
    differ = placement_differences(mine, theirs)
    L += ["", "Placements that differ under the same name: "
              + ("; ".join(f"{n}: {PLACEMENT_NOTES.get(n, 'no recorded reason')}" for n in differ) or "none")]
    L += ["", f"- companion inputs with no CC input of that name: "
              f"{', '.join(sorted(n for n in theirs if n not in mine))}", ""]
    return "\n".join(L)


# Why a same-named input sits differently in the two ledgers for p.
PLACEMENT_NOTES = {
    "sigma1": "a recording effect, not a CC/companion difference. sigma1 reaches p only through the §5 endpoint-force "
              "responses, which this recording cites at §6 (nB6); the CC's §6 makes no such citation, and without it "
              "sigma1 is out, as in the companion (build(cite_responses=False))",
}


def placement_differences(mine: dict[str, str], theirs: dict[str, str]) -> list[str]:
    return sorted(n for n in mine if n in theirs and mine[n] != theirs[n])


# ---------------------------------------------------------------------------
# Finite-model checks the CC states with numbers, run by the checker (not statuses)
# ---------------------------------------------------------------------------

# §10's worlds: "Two finite counterexamples also check the role of the missing relations ... These are checks
# of this finite symbolic model." Each removes C_T or C_L as a unit (so it also falsifies the conjunction of
# that relation's §5 needs, which carry no relation here) and keeps the other three solved relations.
# (label, premise, spec, expected verdict, the CC's values for the changed answer quantities)
CC_WORLDS = [
    ("§10 C_T world 1", "meq", {"remove": ["meq"], "add": ["a1 = 0", "a2 = 0", "T1 = 29.4", "T2 = 49"]},
     "refutes p", {"a1": "0", "a2": "0", "T": "29.4"}),
    ("§10 C_T world 2", "meq", {"remove": ["meq"], "add": ["a1 = 1", "a2 = -1", "T1 = 32.4", "T2 = 44"]},
     "refutes p", {"a1": "1", "a2": "-1", "T": "32.4"}),
    ("§10 without C_T", "meq", {"remove": ["meq"]}, "p does not follow", {}),
    ("§10 C_L world T = 35", "C_L", {"remove": ["C_L"], "add": ["T1 = 35", "T2 = 35", "a1 = 28/15", "a2 = -14/5"]},
     "refutes p", {"a1": "28/15", "a2": "-14/5", "T": "35"}),
    ("§10 C_L world T = 40", "C_L", {"remove": ["C_L"], "add": ["T1 = 40", "T2 = 40", "a1 = 53/15", "a2 = -9/5"]},
     "refutes p", {"a1": "53/15", "a2": "-9/5", "T": "40"}),
    ("§10 without C_L", "C_L", {"remove": ["C_L"]}, "p does not follow", {}),
    ("§7 field strength μ_B = 6", "peqv2", {"replace": {"peqv2": "mu2 = 6"}}, "refutes p", {"a1": "147/40"}),
]


def checked_values(result: dict) -> dict[str, Fraction]:
    """The changed answer values in a check_countermodel result ('q = v (was w)')."""
    return {q: Fraction(v) for q, v in re.findall(r"(\w+) = (-?[\d/]+) \(was", result["detail"])}


def check_cc_worlds(t: Trace) -> list[str]:
    out = []
    for label, premise, spec, verdict, stated in CC_WORLDS:
        r = t.check_countermodel(premise, answer="p", **spec)
        got = checked_values(r)
        assert r["verdict"] == verdict and r["outside"] == {}, (label, r)
        assert all(got[q] == Fraction(v) for q, v in stated.items()), (label, got)
        out.append(f"{label}: {r['summary']}")
    return out


def check_peqv_formulas(t: Trace, mu1: str = "7/2", mu2: str = "9/2") -> str:
    """§7: a_A = (μ_B − μ_A) g/(m_A + m_B), T = g (m_A μ_B + m_B μ_A)/(m_A + m_B), at μ other than m."""
    r = t.check_countermodel("peqv1", answer="p", replace={"peqv1": f"mu1 = {mu1}", "peqv2": f"mu2 = {mu2}"})
    v = checked_values(r)
    m1, m2, g, u1, u2 = Fraction(3), Fraction(5), Fraction("9.8"), Fraction(mu1), Fraction(mu2)
    assert v["a1"] == (u2 - u1) * g / (m1 + m2) and v["T"] == g * (m1 * u2 + m2 * u1) / (m1 + m2), v
    return f"P-EQV-free formulas at μ_A = {mu1}, μ_B = {mu2}: {r['detail']}"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t = build()
    assert (t.values["a1"], t.values["a2"], t.values["T"]) == (Fraction(49, 20), Fraction(-49, 20), Fraction(147, 4))
    again = Trace.replay(json.loads(t.to_json()))
    assert again.values == t.values
    print(t.to_markdown())
    print(compare_with_companion(t))
    print("### Checks run by this script\n")
    quoted = sum(1 for c in t.commands if c["args"].get("quote"))
    print(f"- {quoted} ENTRY quotes " + (f"verified verbatim against {ENTRIES.name}" if t.entries
                                         else "not verified (entries file not found)"))
    print("- answer asserted: a1 = 49/20, a2 = -49/20, T = 147/4; the saved record replays exactly")
    print("- §10's worlds and §7's example, as finite-model checks (CC §10: 'These are checks of this finite "
          "symbolic model'), not statuses:")
    for line in check_cc_worlds(t):
        print(f"  - {line}")
    print(f"- {check_peqv_formulas(t)}")
    return 0


# ---------------------------------------------------------------------------
# Tests (python -m pytest handtrace_example_atwood_cc.py)
# ---------------------------------------------------------------------------


if pytest:
    @pytest.fixture(scope="module")
    def cc():
        return build()


def test_answer_values_replay_and_render(cc):
    assert (cc.values["a1"], cc.values["a2"], cc.values["T"]) == (Fraction(49, 20), Fraction(-49, 20),
                                                                  Fraction(147, 4))
    assert cc.values["T1"] == cc.values["T2"] == Fraction(147, 4) and cc.values["a"] == Fraction(49, 20)
    assert Trace.replay(json.loads(cc.to_json())).values == cc.values
    assert "## Ledger for answer p" in cc.to_markdown()
    led = cc.ledger("p")
    assert not led["conflicts"] and not led["withdrawn"]
    # §7's remainders bind the net forces (m_A a_A, m_B a_B); μ stays undetermined, as in the companion:
    # P-EQV fixes it, but no step binds it
    assert (cc.values["Fnet1"], cc.values["Fnet2"]) == (Fraction(147, 20), Fraction(-49, 4))
    assert [u["name"] for u in led["undetermined"]] == ["mu1", "mu2"]


def test_pairing_is_a_second_answer_that_rests_on_p_and_the_pairing_contract(cc):
    assert [cc.values[n] for n in ("cG1", "cG2", "cS1", "cS2")] == [Fraction(147, 5), Fraction(49),
                                                                     Fraction(-147, 4), Fraction(-147, 4)]
    led = cc.ledger("pairing")
    assert any(r["ref"].startswith("pairing") for r in led["theory"])
    pruned = {c["name"] for c in led["pruned"]}
    assert {"sysS", "sigma1"} <= pruned and "sysS" not in {c["name"] for c in cc.ledger("p")["pruned"]}


def test_section4_pending_state_is_underdetermined(cc):
    """§4: 'two relations in four unknowns ... do not yet answer the numerical question'."""
    rep = next(s for s in cc.steps if s.tag == "§4 pending" and s.op == "EXTERNAL")
    assert rep.detail.startswith("underdetermined: 2 relations in 4 unknowns, rank 2")
    assert rep.text.startswith("this recording's check of §4's count, not a CC step")
    assert [r["step"] for r in cc.ledger("p")["solve_reports"]] == [rep.id]


def test_name_map_covers_every_input_and_names_real_companion_bindings(cc):
    import handtrace_example_atwood as companion
    comp = companion.build()
    assert set(NAME_MAP) == set(input_names(cc))
    for n, (cn, rel, why) in NAME_MAP.items():
        assert rel in RELATIONS and why
        assert (cn is None) == (rel == "new"), n
        for x in (cn or "").split("+") if cn else []:
            assert x in comp.bindings, (n, x)
        if rel == "same":
            assert cn == n and comp.steps[comp.bindings[n].step].op == "INPUT", n


def test_the_cc_finite_model_checks_and_field_strength_example_are_reproduced(cc):
    """§10's four worlds, as finite-model checks (not statuses): each refutes p with the CC's numbers."""
    worlds = [w for w in CC_WORLDS if w[0].startswith("§10 C_")]
    assert len(worlds) == 4 and all(w[3] == "refutes p" for w in worlds)
    check_cc_worlds(cc)  # asserts each verdict and the CC's stated values
    assert all("check" not in a.get("p", {}) or a["p"]["status"] == "ENTAILED" for a in cc.annotations.values())
    check_peqv_formulas(cc)
    check_peqv_formulas(cc, "4", "4")  # equal gravitational masses: no acceleration


def test_checked_statuses(cc):
    """The CC's statuses: C_T and C_L follow from their needs (§5), P-EQV from the weight model (§7)."""
    led = cc.ledger("p")
    pruned = {c["name"]: c for c in led["pruned"]}
    members = {c["name"] for c in led["commitments"]}
    for n in ("meq", "C_L", "peqv1", "peqv2"):
        assert pruned[n]["status"] == "ENTAILED" and pruned[n]["why_pruned"] == "status ENTAILED", n
    assert {"Ea", "Eb", "Ka", "Kb", "Kc", "Kvde", "diff"} <= members  # the needs stay in H(p)
    assert pruned["meq"]["check"] == pruned["C_L"]["check"] == "not entailed by the other premises"
    assert "line 154" in pruned["meq"]["note"] and "line 168" in pruned["C_L"]["note"]
    w = led["warnings"]
    # Finding, pinned: the needs of C_T and C_L carry no relation, so the recorded premises do not entail them.
    for n in ("meq", "C_L"):
        assert f"the check of {n} does not support ENTAILED: not entailed by the other premises" in w
    # Finding, pinned: P-EQV's ENTAILED rests on the free-fall reading of g, which is text, not a relation.
    for k in (1, 2):
        assert f"the check of peqv{k} does not support ENTAILED: not entailed by w{k}, g" in w


def test_needs_premises_carry_no_relation_so_the_entailment_and_the_worlds_cannot_see_them(cc):
    """Finding, pinned: §5 says E-a and E-b suffice for C_T, but they are facts, so the checker can neither
    confirm the entailment from them nor see that §10's world without C_T falsifies them too. The same
    holds for C_L and its needs."""
    with pytest.raises(TraceError, match="not a premise relation or supplied value"):
        cc.check_entailed("meq", answer="p", by=["Ea", "Eb"])
    with pytest.raises(TraceError, match="not a premise relation or supplied value"):
        cc.check_entailed("C_L", answer="p", by=["Ka", "Kb", "Kc", "Kvde", "diff"])
    assert cc.check_entailed("meq", answer="p")["verdict"] == "not entailed"
    assert cc.check_entailed("C_L", answer="p")["verdict"] == "not entailed"
    r = cc.check_countermodel("Ea", answer="p", drop_dependents=True)
    # defT goes too: it mentions T, whose declaration cites C_T ('the common magnitude')
    assert r["verdict"] == "p does not follow" and r["changed"] == ["meq", "defT"]


def own_premises(t: Trace, relation: str, quantities: list[str]) -> set[str]:
    """The premises of a relation, less those it reaches only through the quantities it mentions."""
    return t._premises_of(relation) - set().union(*(t._premises_of(q) for q in quantities))


def test_ct_and_cl_share_premises_only_through_this_recordings_reading_of_the_section2_row(cc):
    """Finding, pinned and conditional: on this recording's reading that §5's needs restate §2's row (so
    cite spc), C_T and C_L share spc and, through it, §1's ideal; without that reading they share nothing."""
    ct, cl = own_premises(cc, "meq", ["T1", "T2"]), own_premises(cc, "C_L", ["a1", "a2"])
    assert ct == {"meq", "Ea", "Eb", "spc", "ideal"}
    assert cl == {"C_L", "Ka", "Kb", "Kc", "Kvde", "diff", "transl1", "transl2", "comp1", "comp2", "J", "attach",
                  "spc", "ideal"}
    assert ct & cl == {"spc", "ideal"}
    through_spc = cc._premises_of("spc")
    assert through_spc == {"spc", "ids", "ideal"} and not (ct - through_spc) & cl
    assert "this recording's reading" in cc.steps[cc.bindings["spc"].step].text
    # the same reading puts spc in H(p) beside the §5 needs that restate it
    members = {c["name"] for c in cc.ledger("p")["commitments"]}
    assert {"spc", "Ea", "Eb", "Ka", "Kb", "Kc"} <= members


def test_force_accounts_rest_on_verticality_only_through_section1(cc):
    """Finding, pinned: the +T_A upward direction at §4 has no listed premise in the CC; recorded via §1."""
    assert "ideal" in cc._premises_of("sum1") and "Kvde" not in cc._premises_of("sum1")


def test_quotes_are_verified_against_the_entries():
    if not ENTRIES.exists():
        pytest.skip(f"entries file not found: {ENTRIES}")
    import handtrace_example_atwood as companion
    assert all(companion.Q[k] == v for k, v in Q.items())
    t = Trace("q", entries=load_entries(str(ENTRIES)))
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E7", "the acceleration read from the trajectory")


def test_the_section6_citation_of_the_responses_is_what_puts_sigma1_in_ps_cone(cc):
    """The only same-name placement difference from the companion comes from this recording's citation of
    the §5 endpoint-force responses at §6, which the CC does not make."""
    import handtrace_example_atwood as companion
    theirs = _placements(companion.build().ledger("p"))
    assert placement_differences(_placements(cc.ledger("p")), theirs) == ["sigma1"]
    bare = build(cite_responses=False)
    assert (bare.values["a1"], bare.values["T"]) == (cc.values["a1"], cc.values["T"])
    led = bare.ledger("p")
    assert _placements(led)["sigma1"] == "out" and not placement_differences(_placements(led), theirs)
    assert not any(r["ref"].startswith("endpoint-force response") for r in led["theory"])
    assert sum(r["ref"].startswith("endpoint-force response") for r in cc.ledger("p")["theory"]) == 2


def test_labels_and_the_recorded_passages(cc):
    """CONTRACT for what the CC presents as a proposed connection; READING for a check it passes and its
    remark on the lock; OPEN only for gaps. The two passages the first recording omitted are present."""
    ops = {b: cc.steps[cc.bindings[b].step].op for b in ("resp1", "resp2", "vlock", "cpair")}
    assert set(ops.values()) == {"CONTRACT"}
    for start in ("§6 the tension is positive", "§7 those equalities were used"):
        assert [s.op for s in cc.steps if s.text.startswith(start)] == ["READING"], start
    assert any(s.op == "READING" and "fits the user's force lock" in s.text for s in cc.steps)
    assert any(s.op == "OPEN" and "geometry and model conditions remain applicable" in s.text for s in cc.steps)
    assert "'E7–E11 checked; E8/E9 used above'" in EDITION["D"] and "K12 and E7" in EDITION["entries cited"]


def test_peqv_free_formulas_cite_no_peqv(cc):
    """§7: 'Without that identification, the same relations give' the formulas, so they cite no P-EQV."""
    steps = [s for s in cc.steps if s.tag == "§7 P-EQV" and s.op == "DERIVE"]
    assert len(steps) == 2
    for s in steps:
        assert not {"peqv1", "peqv2"} & set(s.uses) and s.detail.startswith("follows from w1, w2"), s.detail


def test_main_runs(capsys):
    assert main() == 0
    out = capsys.readouterr().out
    assert "## Name map and placements for p" in out and "§10 C_T world 1: refutes p" in out
    assert "Placements that differ under the same name: sigma1: a recording effect" in out


if __name__ == "__main__":
    raise SystemExit(main())
