"""The reconciled Atwood trace (ATWOOD_WORKED_TRACE_2026-11-08.md) recorded with handtrace v2,
then compared row by row with its T§10 ledger.

Run from this directory:  python handtrace_example_atwood.py
Or as tests:              python -m pytest handtrace_example_atwood.py

What the encoding covers, in the source's order:

* T§1-T§6 up to the answer p = {a1, a2, T}. ENTRY quotes are verified by
  Trace(entries=load_entries(ENTRIES)).
* T§7-T§9 after the answer, as consequences: freedom (T§7.1), counterparts
  and the system (T§7.2), the mount load under Q1-Q7 (T§7.3, recorded as a
  second labelled answer 'mount' so its ledger can show what it rests on),
  system sums (T§7.4), the value lock (T§8), P1-P4 and the tolerance
  variant (T§9).
* T§10(b) statuses and countermodels as annotations.

Step order follows the source. Where the API needs a name bound before use,
the step text says "moved". Bracketed numbers [n] and tags (nN) are the
source's.

Gaps v2 leaves open here (recorded in step text, not as failing tests):
* names must be bound before use: [8]'s sum, g at [9], E-a/E-b, K-a to K-e
  and Q1 are moved;
* no shared-value naming: 'T1 = T2 =: T' needs a third unknown T and C-T9's
  relation T = T1;
* a delivery passes one level from the caller, so re-deliveries the source
  makes at a site ([9] m(B1), [14] R, [15] admissions, [16] g) land at the
  site's caller and reach its whole subtree;
* deliver() takes no uses, so W17 (persistence) reaches p only through C-ID;
* inequalities ([25] T > 0, (n20)'s corners), M-KIN as a relation between
  functions, and countermodels are text; this script re-solves the
  countermodels and the tolerance corners itself;
* one status per binding and answer: W7's conditional status and W8's
  ENTAILED clause are notes; the statuses are scoped to the answer p.
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

from handtrace import ROOT, Trace, TraceError, frac, load_entries, parse_equation, solve_linear

try:  # the tests below use pytest; the script runs without it
    import pytest
except ImportError:  # pragma: no cover
    pytest = None

ENTRIES = Path("C:/Users/canva/Documents/Amy hobby/VD instructions/codex VD newton/"
               "07_design_2_1/DESIGN_2_1_DRAFT_1_ENTRIES.md")

QUESTION = ("Two blocks, m1 = 3 kg and m2 = 5 kg, hang from a massless, inextensible string over a "
            "frictionless pulley fixed to a support. Supplied g = 9.8 m/s². Find the acceleration of "
            "each mass and the tension in the string.")

EDITION = {
    "D": "Design 2.1 Draft 1 entries K1-K16, E1-E11 (compiled 2026-05-20), VD-Newton HEAD 61afb9ec",
    "Force-Sum": "ratified names and minimum typed relation (07_design_2_1/CURRENT_STATE.md)",
    "contracts": "NEWTON_ENTRY_STRUCTURE_SYNTHESIS_2026-11-08.md, sha256 7ca588f2...af2af3",
    "source": "03_trace_and_evaluator/ATWOOD_WORKED_TRACE_2026-11-08.md, T§§0-10",
}

# Entry strings quoted verbatim (substrings of D's entry text; Trace verifies them).
Q = {
    "K1": "a time-value selects an instant",
    "K2": "an origin, basis vectors, and a clock",
    "K6": "A selected span of time from a start-time to an end-time over which a motion description "
          "is considered; it selects a span, not merely a duration.",
    "K7": "spatial extent and internal structure are neglected for the motion description",
    "K8": "a time-indexed map from selected time-values to displacement-vectors in that frame",
    "K10": "the derivative of that trajectory with respect to time at a selected time, when that "
           "derivative exists.",
    "K12": "equivalently, the second derivative of the trajectory, when defined.",
    "K16": "traces a straight path with constant velocity",
    "E4": "must exhibit uniform-motion when described in an inertial-frame",
    "E5": "Earth can be treated as an inertial reference-frame in ordinary circumstances, to the "
          "needed approximation.",
    "E5s": "to the needed approximation",
    "E6": "whose trajectory is not being influenced by any other object",
    "E7": "For a material-object with a trajectory described in an inertial-frame, the acceleration "
          "read from that trajectory at a selected time.",
    "E8": "For one material-object, its net-force-material-object divided by its "
          "inertial-mass-material-object.",
    "E9": "its inertial-mass-material-object times its inertial-acceleration-material-object",
    "E10": "the positive scalar that multiplies its inertial-acceleration-material-object to give its "
           "net-force-material-object.",
    "E10s": "the positive scalar",
    "E11": "For a material-object in an inertial-frame, its vector in newtons. There are exactly two "
           "ways to obtain this vector.",
}

# Source step numbers for the two block walks (T§2 and T§3).
STEP = {
    1: {"demand": 1, "target": 2, "mass": 3, "force": 4, "halt": 6, "iset": 7, "sum": 8, "grav": 9,
        "string": 10, "ret": 11},
    2: {"demand": 12, "target": 12, "mass": 13, "force": 14, "halt": 14, "iset": 15, "sum": 18, "grav": 16,
        "string": 17, "ret": 18},
}


# ---------------------------------------------------------------------------
# The trace up to the answer (T§1-T§6)
# ---------------------------------------------------------------------------


def walk_block(t: Trace, k: int, mass: int) -> None:
    """T§2 (k = 1, steps [1]-[11]) or T§3 (k = 2, steps [12]-[18])."""
    B, D, first, s = f"B{k}", f"D{k}", k == 1, STEP[k]
    weight = {1: "147/5", 2: "49"}[k]

    # [1] / [12] the demand, E8 and the qualified target
    t.demand(ROOT, D, f"inertial-acceleration-material-object({B}, t0, R)")
    why = {"t0": "an actual delivered by the normalization", "R": "an actual delivered by the normalization",
           "norm": "the normalization that states this demand", "axis": "the axis convention (ŷ-components)",
           "persist": "persistence, cited by C-ID at [15]"}
    for n in ("t0", "R", "norm", "axis") + (() if first else ("persist",)):
        t.deliver(D, n, text=f"[{s['demand']}] {why[n]}")
    t.entry(D, "E8", Q["E8"], binds=f"e8_{k}", uses=["t0", "R"],
            text=f"[{s['demand']}] exposes d{k}.1 net-force-material-object({B}, t0, R) and d{k}.2 "
                 f"inertial-mass-material-object({B}); E8 has no frame or time slot, so t0 and R are actuals "
                 "delivered by the normalization")
    t.entry(D, "K7", Q["K7"], binds=f"k7_{k}", text=f"[{s['target']}] quoted inside the target INPUT")
    t.input(D, f"pp{k}", "recognition/model", f"[{s['target']}] {B} is a material object represented by a "
            "point-particle (K7)", uses=[f"k7_{k}"])
    t.input(D, f"transl{k}", "model", f"[{s['target']}] {B} moves by translation only, so its string attachment "
            "point has its representative point's acceleration (the source states this in the same INPUT as "
            f"pp{k}; T§10(b) splits it off as W2)", uses=[f"pp{k}"])
    if first:
        t.open(D, "[2] there is no material-object headword; target construction (S§6) is supplied as "
               "recognition", uses=["pp1"])
    t.unknown(D, f"a{k}", f"ŷ-component of a({B}), the quantity {D} demands", address=f"a({B}, t0, R)",
              label="ENTRY", ref="E8", quote=Q["E8"], unit="m/s^2", uses=[f"e8_{k}", f"pp{k}", "norm", "axis"])

    # [3] / [13] inertial mass
    dm = t.demand(D, f"{D}.2", f"inertial-mass-material-object({B})", ref="E8")
    t.entry(dm, "E10", Q["E10"], binds=f"e10_{k}",
            text=f"[{s['mass']}] types the value; its procedure is not run: it needs a({B}), which is {D} itself")
    t.input(dm, f"m{k}", "value", f"[{s['mass']}] inertial mass of {B}, exact, bound at address m({B}); {mass} > 0",
            value=mass, unit="kg", uses=[f"e10_{k}"])

    # [4]-[6] / [14] net force
    df = t.demand(D, f"{D}.1", f"net-force-material-object({B}, t0, R)", ref="E8")
    t.entry(df, "E11", Q["E11"], binds=f"e11_{k}",
            text=f"[{s['force']}] exposes a frame demand: R must be an inertial-frame")
    if first:
        t.entry(df, "E5", Q["E5"], binds="e5", text="[5]")
        t.input(df, "rin", "recognition/model", "[5] R is fixed to an Earth-bound support in ordinary circumstances "
                "and is stipulated inertial, exactly: (i) R is inertial; (ii) the support is at rest in R; "
                "(iii) Earth's recoil is left out. An exactness idealisation (T§7.4)", uses=["e5", "e11_1", "R"])
    else:
        t.deliver(D, "rin", text="[14] re-delivered for the same R (C-ID). It lands at D2, the caller of d2.1: "
                  "a delivery passes from a frame's parent")
    t.open(df, f"[{s['halt']}] E11's two ways (supplied; inferred through Newton II, named only in the E11 pass, "
           f"outside D) are unavailable: no net force is supplied for {B}, and E9 would need a({B}), which is "
           f"{D} itself. The ENTRY route halts here.", uses=[f"e11_{k}"])
    t.contract(df, "C-BR", f"[{s['halt']}] net-force-material-object({B}) is the Force-Sum net-force({B}|t0,R); "
               "this takes S§5's reading of E11's count as NML2.1-scoped (a recorded choice)", source="S§5, S§8",
               binds=f"cbr{k}", uses=[f"e11_{k}", "rin"])
    t.contract(df, "C-FS", f"[{s['halt']}] net-force({B}|t0,R) = Σ impressed-force(i → {B}|t0,R) over "
               f"i ∈ interaction-set({B}|t0,R); exact, no haze term", source="ratified relation; S§8.1",
               binds=f"cfs{k}", uses=[f"cbr{k}"])
    if first:
        t.open(df, "[6] the edition is in tension over E11's count: read literally it excludes a sum; S§5 reads "
               "it as NML2.1-scoped and the E11 pass §5.6 expects a later force-sum entry", uses=["cbr1"])
    t.unknown(df, f"Fnet{k}", f"ŷ-component of net-force-material-object({B})", address=f"net-force({B}|t0,R)",
              label="ENTRY", ref="E11", quote=Q["E11"], unit="N", uses=[f"e11_{k}", "rin"])

    # [7] / [15] interaction set
    i = s["iset"]
    di = t.demand(df, f"{D}.1.I", f"interaction-set({B} | t0, R)", ref="C-FS")
    t.input(di, f"admG{k}", "recognition", f"[{i}] admit i_G{k}: gravity (producer mechanism), participants "
            f"{{Earth E, {B}}}; activation: {B} is a massive body in E's near-surface field, where the "
            "uniform-field model holds", uses=["t0"])
    t.input(di, f"admS{k}", "recognition", f"[{i}] admit i_S{k}: string attachment (constraint mechanism), "
            f"participants {{string σ, {B}}}, interface binding σ's end {k}; activation: {B} is attached to "
            f"end {k}, σ is intact and taut at t0, the segment above {B} is vertical", uses=["t0"])
    t.contract(di, "C-ADM", f"[{i}] in context (t0, R): admission commits the account to these activation "
               "conditions, under these bindings, at t0", source="S§2.1, S§9.2, S§12.2", binds=f"cadm{k}",
               uses=[f"admG{k}", f"admS{k}"])
    if first:
        t.open(di, "[7] no gravity or string headword carries the recognition document that would teach these "
               "verdicts; the verdicts are inputs", uses=["admG1", "admS1"])
    t.input(di, f"comp{k}", "completeness", f"[{i}] {B}'s membership is exactly complete in this model "
            "(S§11.1, claim 2): air drag, buoyancy and the blocks' mutual gravitation are stipulated absent",
            uses=[f"cadm{k}"])
    t.input(di, f"haze{k}", "haze", f"[{i}] H({B}) = 0, for the unkeyed omitted aggregate only", value=0, unit="N")
    if first:
        t.deliver("D3", "admS1", text="[7] D3 is bound once i_S1 is recognised")
        t.input("D3", "d3bind", "normalization", "[7] D3 := |f(i_S1 → B1 | t0, R)|", uses=["admS1"])
    else:
        for n in ("admG1", "admS1"):
            t.deliver(D, n, text="[15] for C-ID. It lands at D2: a delivery passes from a frame's parent")
        t.contract(di, "C-ID", "[15] i_G2 ≠ i_G1 and i_S2 ≠ i_S1: E and σ each take part in two encounters; a "
                   "(mechanism, recipient, context) key would merge each pair; the encounter addresses keep them "
                   "distinct (S§9.5)", source="S§4.4, S§6.3, S§9.5, S§12.2", binds="cid2",
                   uses=["admG1", "admS1", "admG2", "admS2", "persist"])
    sum_uses = [f"cfs{k}", f"comp{k}", f"haze{k}", f"cadm{k}"] + ([] if first else ["cid2"])
    if first:
        t.contract(df, "C-FS", "[8] Fnet(B1) = f(i_G1 → B1) + f(i_S1 → B1) over the two-member enumeration; "
                   "the completeness input at [7] licenses this sum as the net force, running out of rows does "
                   "not", source="S§8.1", binds="sumB1", uses=sum_uses)

    # [9] / [16] gravity member
    g_ = s["grav"]
    dg = t.demand(df, f"{D}.1.G", f"f(i_G{k} → {B})", ref="C-FS")
    if first:
        t.open(dg, "[9] no gravity headword")
    t.deliver(dg, f"admG{k}", text=f"[{g_}] the admitted interaction this member belongs to")
    t.unknown(dg, f"fG{k}", f"ŷ-component of f(i_G{k} → {B}); i_G{k} is a producer mechanism, so dispatch exposes "
              "a formula", address=f"(i_G{k}, {B}, t0)", ref="C-CM", unit="N", uses=[f"admG{k}"])
    if first:
        t.input(dg, "g", "value/model", "[9] g = 49/5 m/s², the supplied 9.8 taken as exact, read as the local "
                "free-fall acceleration, uniform over the region of motion (moved before the weight INPUT, whose "
                "relation mentions g)", value="9.8", unit="m/s^2")
    else:
        t.deliver(D, "g", text="[16] the same g at both blocks (W5). It lands at D2: a delivery passes from a "
                  "frame's parent")
    t.unknown(dg, f"mu{k}", f"{B}'s gravitational mass: an address created by the weight expression, forced by "
              "the kind (S§3.4); it supplies no value", address=f"μ({B})", ref="C-CM", unit="kg",
              uses=[f"admG{k}"])
    t.input(dg, f"w{k}", "model", f"[{g_}] near-surface uniform-field weight, i_G{k} a binary interaction with E: "
            f"f(i_G{k} → {B}) = −μ({B})·g ŷ" + ("" if first else "; the same g at both blocks"),
            relation=f"fG{k} = -mu{k}*g", uses=[f"admG{k}", "axis"])
    t.deliver(df, f"m{k}", text=f"[{g_}] binding re-delivered for P-EQV: m({B}) = {mass} kg. It lands at d{k}.1, "
              "the caller of this demand: a delivery straight to the weight slot is refused")
    t.input(dg, f"peqv{k}", "identity/model", f"[{g_}] P-EQV: μ({B}) is the quantity at address m({B})",
            relation=f"mu{k} = m{k}")
    t.derive(dg, f"fG{k} = -{mass}*49/5", from_relations=[f"w{k}", f"peqv{k}"], binds=f"fG{k}", tag=f"(n{k})",
             text=f"= −{weight} ŷ N")

    # [10] / [17] string member
    st = s["string"]
    ds = t.demand(df, f"{D}.1.S", f"f(i_S{k} → {B})", ref="C-FS")
    if first:
        t.open(ds, "[10] no string, tension or pulley headword")
    t.deliver(ds, f"admS{k}", text=f"[{st}] the admitted interaction this member belongs to")
    t.unknown(ds, f"T{k}", f"f(i_S{k} → {B}) = +T{k} ŷ; i_S{k} is a constraint mechanism, so dispatch returns an "
              "addressed unknown; not defaulted to zero", address=f"(i_S{k}, {B}, t0)", ref="C-CM", unit="N",
              uses=[f"admS{k}"])
    t.input(ds, f"pull{k}", "model", f"[{st}] a string only pulls, along its segment toward the pulley; the "
            f"segment above {B} is vertical, so the direction is +ŷ, T{k} ≥ 0", uses=[f"T{k}", f"admS{k}", "axis"])

    # [8]+[11] / [18] sum and partial return
    if not first:
        t.contract(df, "C-FS", "[18] Fnet(B2) = f(i_G2 → B2) + f(i_S2 → B2) over the two-member enumeration, "
                   "licensed by the completeness input at [15]", source="S§8.1", binds="sumB2", uses=sum_uses)
    t.external(df, "vector addition", f"[{s['sum']}] ŷ-components of the two-member sum"
               + (" (moved after [9]-[10]: the relation needs fG1 and T1 bound)" if first else ""),
               relation=f"Fnet{k} = fG{k} + T{k}", binds=f"sum{k}", uses=[f"sumB{k}", f"pull{k}", "axis"],
               tag=f"[{s['sum']}]")
    ret = f"[{s['ret']}] RETURN (partial)"
    t.derive(df, f"Fnet{k} = T{k} - {weight}", from_relations=[f"sum{k}"], name=f"retF{k}", tag=ret)
    t.entry(D, "E8", Q["E8"], binds=f"e8rel{k}", relation=f"a{k} = Fnet{k}/m{k}", uses=[f"e8_{k}"],
            text=f"{ret}: E8 applied to the returned d{k}.1 and d{k}.2")
    t.derive(D, f"a{k} = (T{k} - {weight})/{mass}", from_relations=[f"e8rel{k}", f"retF{k}"], name=f"reta{k}",
             tag=ret, text=f"PENDING on T{k}")


def to_answer(t: Trace) -> None:
    """T§1-T§6 and the answer p."""
    # T§1 normalization, frame and time
    t.entry(ROOT, "K1", Q["K1"], binds="t0", text="T§1 t0: a selected time")
    t.entry(ROOT, "K2", Q["K2"], binds="R", text="T§1 R: the reference-frame, fixed to the support, with a clock")
    t.input(ROOT, "axis", "convention", "T§1 R's origin at the pulley axle; x̂ horizontal in the string's plane, "
            "ŷ up; both blocks on the same ŷ axis; SI units (the quoting convention of W18 is stated only at "
            "T§7.2, after the answer)", uses=["R"])
    t.input(ROOT, "norm", "normalization", "T§1 D1, D2 := inertial-acceleration-material-object(Bk, t0, R) ('each "
            "mass' becomes two demands); D3 := 'the tension in the string', PENDING, the magnitude of the "
            "string's force on B1 at t0 (taking B1's end is a recorded choice); blocks B1, B2 kept apart from "
            "their mass addresses m(B1), m(B2)", uses=["t0", "R"])
    t.input(ROOT, "persist", "identity", "the same objects (B1, B2, E, σ, R, t0), masses, addresses and interactions "
            "are used throughout; nothing is re-identified (stated in T§9; recorded here so the re-delivery "
            "sites can cite it)")
    t.demand(ROOT, "D3", "'the tension in the string': PENDING description, the magnitude of the string's force "
             "on B1 at t0")

    walk_block(t, 1, 3)
    walk_block(t, 2, 5)

    # T§4 pending state
    t.solve(ROOT, ["reta1", "reta2"], ["a1", "a2", "T1", "T2"], tag="T§4 pending",
            text="EXTERNAL linear solve on the pending state (D3 = T1, PENDING)")

    # T§5.1 [19] equal magnitudes, at D3
    t.deliver_many("D3", ["T1", "T2"], text="[19] the member unknowns M-EQ relates")
    t.input("D3", "Ea", "model", "E-a: the string's mass is negligible (stated under 'What M-EQ needs'; moved "
            "before M-EQ so it can cite it)")
    t.input("D3", "Eb", "model", "E-b: no net tangential force from the pulley on the string (frictionless "
            "contact, or a freely turning pulley on a frictionless axle with negligible I/r²); reading the "
            "exercise's 'frictionless pulley' as also negligible inertia is a recorded normalization")
    t.input("D3", "meq", "model", "[19] M-EQ (model/idealisation): T1 = T2 =: T", relation="T1 = T2",
            uses=["Ea", "Eb"])
    t.unknown("D3", "T", "the one shared tension, T1 = T2 =: T; it answers D3", address="T(σ over the pulley, t0)",
              ref="C-T9", unit="N", uses=["meq", "d3bind"])
    t.contract("D3", "C-T9", "[19] carry one shared unknown T from here on", source="S§13 Trace 9", binds="t9",
               relation="T = T1", uses=["meq"])

    # T§5.2 [20]-[22] kinematic coupling at E7 (one site for both targets; the source has no DEMAND line)
    K = t.demand(ROOT, "D12.E7", "inertial-acceleration-material-object(Bk, t0, R), k = 1, 2, read through E7: "
                 "the site where a constraint on the motion can reach a1 and a2")
    t.deliver_many(K, ["t0", "R", "axis", "a1", "a2", "transl1", "transl2", "pull1", "pull2", "comp1", "comp2"],
                   text="[20] for the E7 site")
    t.deliver(K, "rin", text="[20] frame slot re-delivered (C-ID)")
    t.entry(K, "E7", Q["E7"], binds="e7", uses=["rin", "t0", "R"], text="[20]")
    t.entry(K, "K6", Q["K6"], binds="k6", text="[20]")
    t.entry(K, "K8", Q["K8"], binds="k8", text="[20]")
    t.input(K, "J", "model", "[20] J is an open time-interval (K6) containing t0; each Bk has a trajectory in R over "
            "J (K8); y_k(t) is the ŷ-component of Bk's attachment point", uses=["k6", "k8", "e7", "t0", "R"])
    t.entry(K, "K10", Q["K10"], binds="k10", text="[20]")
    t.entry(K, "K12", Q["K12"], binds="k12", text="[20]")
    for k in (1, 2):
        t.unknown(K, f"y{k}dd", f"y{k}''(t0), the K12 value; under translation it equals the second derivative "
                  f"of B{k}'s representative point", address=f"y{k}''(t0) in R", label="ENTRY", ref="K12",
                  quote=Q["K12"], unit="m/s^2", uses=["k10", "k12", "J", f"transl{k}"])
    premises = {"Ka": "K-a: the string is inextensible, so L is constant",
                "Kb": "K-b: the string is taut throughout J",
                "Kc": "K-c: the axle is at rest in R (pulley fixed to the support, at rest by [5])",
                "Kde": "K-d, K-e: constant wrap and rigid attachments"}
    for n, text in premises.items():
        t.input(K, n, "model", text + " (stated under 'What M-KIN needs'; moved before M-KIN so it can cite it)",
                uses={"Kb": ["J"], "Kc": ["rin"]}.get(n, []))
    t.input(K, "mkin", "model", "[21] M-KIN (model/idealisation): for all t in J, with the axle at y = 0, "
            "(0 − y1(t)) + (0 − y2(t)) + ℓ_arc = L, with L and ℓ_arc constant on J (a relation between "
            "functions on J, so recorded as a fact)", uses=["J", "Ka", "Kb", "Kc", "Kde", "pull1", "pull2", "axis"])
    t.input(K, "diff", "model", "[21] y1 and y2 are twice differentiable on J", uses=["J"])
    t.external(K, "differentiation", "[21] twice in t, on J. Input: y1(t) + y2(t) = ℓ_arc − L, constant on J",
               relation="y1dd + y2dd = 0", binds="dkin", uses=["mkin", "diff"], tag="[21]")
    for k in (1, 2):
        t.reading(K, f"[22] E7 and E8 are two definitions of one headword: for the same arguments (B{k}, t0, R) "
                  f"the K12/E7 value and the E8 unknown a{k} are one quantity. Support: S§5. Counter-weight: "
                  "S§4.1. Presupposes complete force accounts (W16)", binds=f"rd{k}", relation=f"a{k} = y{k}dd",
                  uses=["e7", f"comp{k}"])
    t.derive(K, "a1 + a2 = 0", from_relations=["rd1", "rd2", "dkin"], name="coup", tag="[22] hence")
    t.open(K, "[22] no entry, and no rule of the trace procedure, authorizes using both definitions at one site",
           uses=["rd1", "rd2"])
    t.contract(K, "C-T9", "[22] carry the coupling from here on", source="S§13 Trace 9", uses=["coup"])

    # T§6 [23] the solve: its inputs, the hand working (n3)-(n8), the EXTERNAL solve
    t.derive(ROOT, "3*a1 = T - 147/5", from_relations=["reta1", "t9"], name="r1", tag="[23] input")
    t.derive(ROOT, "5*a2 = T - 49", from_relations=["reta2", "meq", "t9"], name="r2", tag="[23] input")
    t.derive(ROOT, "a2 = -a1", from_relations=["coup"], name="r3", tag="[23] input")
    t.derive(ROOT, "-5*a1 = T - 49", from_relations=["r2", "r3"], name="n3", tag="(n3)")
    t.derive(ROOT, "T = 49 - 5*a1", from_relations=["n3"], name="n4", tag="(n4)")
    t.derive(ROOT, "3*a1 = 49 - 5*a1 - 147/5", from_relations=["r1", "n4"], name="n5", tag="(n5)")
    t.derive(ROOT, "8*a1 = 98/5", from_relations=["n5"], name="n5b", tag="(n5)")
    t.derive(ROOT, "a1 = (98/5)/8", from_relations=["n5b"], name="n6", tag="(n6)")
    t.derive(ROOT, "a2 = -49/20", from_relations=["r3", "n6"], name="n7", tag="(n7)")
    t.derive(ROOT, "T = 49 - 5*(49/20)", from_relations=["n4", "n6"], name="n8", tag="(n8)")
    t.solve(ROOT, ["r1", "r2", "r3"], ["a1", "a2", "T"], tag="[23]", uses=WORKING,
            text="EXTERNAL linear solve on the single ŷ axis; uses cites its displayed working (n3)-(n8)")

    # [24] return through C-FS and E8
    t.derive(ROOT, "T1 = 147/4", from_relations=["t9"], binds="T1", tag="[24]")
    t.derive(ROOT, "T2 = 147/4", from_relations=["meq"], binds="T2", tag="[24]")
    t.derive(ROOT, "Fnet1 = 147/4 - 147/5", from_relations=["sum1"], binds="Fnet1", tag="(n9)", text="7.35 N")
    t.derive(ROOT, "a1 = (147/20)/3", uses=["e8rel1"], tag="(n9)", text="E8 returns a(B1)")
    t.derive(ROOT, "Fnet2 = 147/4 - 49", from_relations=["sum2"], binds="Fnet2", tag="(n10)", text="−12.25 N")
    t.derive(ROOT, "a2 = (-49/4)/5", uses=["e8rel2"], tag="(n10)", text="E8 returns a(B2)")

    # [25] activation check
    t.contract(ROOT, "C-ADM", "[25] tautness at t0 is the T ≥ 0 regime; T = 147/4 > 0 is consistent (the "
               "inequality is checked by hand: the recorder checks equalities only); the check covers t0 only, "
               "tautness on J remains a premise (K-b)", source="S§2.1, S§9.2, S§12.2",
               uses=["T", "cadm1", "cadm2", "Kb"])
    t.derive(ROOT, "T = 2*m1*m2*g/(m1 + m2)", tag="(n11)", uses=["peqv1", "peqv2"],
             text="symbolic tension under P-EQV, checked at the values; positive for any positive masses")

    t.answer(["a1", "a2", "T"], "a(B1), a(B2) (ŷ-components) and T (D3) at t0 in R, according to D and the "
             "premises in T§10", label="p")


WORKING = ["n3", "n4", "n5", "n5b", "n6", "n7", "n8"]


# ---------------------------------------------------------------------------
# After the answer: T§7-T§9, as consequences
# ---------------------------------------------------------------------------


def consequences(t: Trace) -> None:
    adm = ["admG1", "admS1", "admG2", "admS2"]

    # T§7.1 activation and freedom
    t.entry(ROOT, "E4", Q["E4"], binds="e4", text="T§7.1 main route (S§14.1, a contradiction argument): suppose "
            "Bk were a free-particle throughout some interval around t0")
    t.entry(ROOT, "K16", Q["K16"], uses=["e4", "a1", "a2"], text="T§7.1 (K16/E1) uniform-motion is a "
            "constant-velocity pattern, so a(Bk) at t0 would be 0, contradicting a1 = 49/20 and a2 = −49/20 "
            "(the inequality is checked by hand). This route reuses the present account")
    t.entry(ROOT, "E6", Q["E6"], binds="e6", text="T§7.1 second route")
    t.reading(ROOT, "T§7.1 E6 reading (this trace's, not a synthesis section): an admitted interaction is an "
              "influence in E6's sense, so the admissions at [7] and [15] already exclude freedom",
              uses=["e6"] + adm)
    t.open(ROOT, "T§7.1 no entry or contract connects admission to E6's 'influence'")

    # T§7.2 counterparts and the system
    t.input(ROOT, "bn", "model", "T§7.2 i_G1, i_G2, i_S1, i_S2 are binary Newtonian interactions", uses=adm)
    t.input(ROOT, "cquote", "convention", "T§7.2 each interaction quotes its vector on the block; the other "
            "participant receives the negation (S§10.2). No entry installs this", uses=["axis"])
    t.input(ROOT, "sigma1", "model", "T§7.2 σ is one participant; 'end 1' and 'end 2' are interface bindings, not "
            "separate participants (the source's kind is 'representation', which is not an API kind; W19 files "
            "it under choice/model)")
    t.input(ROOT, "sysS", "choice", "T§7.2 S := exactly {B1, B2}; E ∉ S; σ ∉ S")
    t.contract(ROOT, "C-PAIR", "T§7.2 a counterpart exists for each of the four interactions",
               source="S§10.1, S§12.2", binds="cpair", uses=["bn"] + adm)
    t.contract(ROOT, "C-INC", "T§7.2 (full antecedent) each of the four interactions crosses S",
               source="S§10.4-10.5, S§12.2", binds="cinc", uses=["cpair", "sysS", "sigma1"])
    for i, force, recipient, value in (("G1", "fG1", "E", "147/5"), ("G2", "fG2", "E", "49"),
                                       ("S1", "T1", "σ end 1", "-147/4"), ("S2", "T2", "σ end 2", "-147/4")):
        t.unknown(ROOT, f"c{i}", f"ŷ-component of i_{i}'s counterpart, on {recipient}; C-ID keeps E's and σ's two "
                  "counterparts at distinct addresses", address=f"(i_{i}, {recipient}, t0)", ref="C-PAIR", unit="N",
                  uses=["cpair", "sigma1"])
        t.contract(ROOT, "C-PAIR", f"T§7.2 i_{i}'s counterpart is the negation of its force on the block (by the "
                   "quoting convention)", source="S§10.1, S§10.2", binds=f"pair{i}", relation=f"c{i} = -{force}",
                   uses=["cpair", "cquote"])
        t.derive(ROOT, f"c{i} = {value}", from_relations=[f"pair{i}"], binds=f"c{i}", tag="T§7.2 table")

    # T§7.3 the string is not a material object of E8-E10; the mount load under Q1-Q7
    t.entry(ROOT, "E10", Q["E10s"], uses=["Ea"], text="T§7.3 E10 excludes σ: under E-a σ's mass is treated as "
            "zero, and E10 makes inertial mass 'the positive scalar', so σ is not a target of E8-E10")
    t.open(ROOT, "T§7.3 σ's force balance has no entry route (E9 cannot divide by zero mass); the edition makes no "
           "provision for counterpart recipients that are not material objects with positive mass (G8)")
    qs = {"Q2": "(Q2) an addressed string-pulley contact interaction i_P",
          "Q3": "(Q3) an addressed pulley-mount interaction i_U",
          "Q4": "(Q4) the pulley has mass but its weight is neglected",
          "Q6": "(Q6) σ's interaction set is exactly {i_S1, i_S2, i_P}; the pulley's is exactly {i_P, i_U}, its "
                "weight neglected by Q4",
          "Q7": "(Q7) i_P and i_U are binary Newtonian, so C-PAIR gives their counterparts"}
    for n, text in qs.items():
        t.input(ROOT, n, "model", "T§7.3 " + text, uses={"Q6": ["Q2", "Q3", "Q4"], "Q7": ["Q2", "Q3"]}.get(n, []))
    t.unknown(ROOT, "fPs", "ŷ-component of f(i_P → σ)", address="(i_P, σ, t0)", ref="C-CM", unit="N", uses=["Q2"])
    t.unknown(ROOT, "fPp", "ŷ-component of i_P's counterpart, on the pulley", address="(i_P, pulley, t0)",
              ref="C-PAIR", unit="N", uses=["Q7"])
    t.unknown(ROOT, "fU", "ŷ-component of f(i_U → pulley)", address="(i_U, pulley, t0)", ref="C-CM", unit="N",
              uses=["Q3"])
    t.unknown(ROOT, "fUm", "ŷ-component of i_U's counterpart, on the mount: the mount load",
              address="(i_U, mount, t0)", ref="C-PAIR", unit="N", uses=["Q7"])
    t.input(ROOT, "Q1", "model", "T§7.3 (Q1) the massless-link rule: the net force on σ is zero, summed over "
            "Q6's set (Q1 is listed first in the source; moved after Q2-Q7, whose addresses it needs)",
            relation="cS1 + cS2 + fPs = 0", uses=["Q6"])
    t.entry(ROOT, "E9", Q["E9"], binds="e9", text="T§7.3 (Q5) E9 gives zero net force for a positive-mass pulley at "
            "zero acceleration")
    t.input(ROOT, "Q5", "model", "T§7.3 (Q5) the pulley's net force is zero: it is at rest (K-c) and has positive "
            "mass (E9)", relation="fPp + fU = 0", uses=["Q6", "Kc", "e9"])
    t.contract(ROOT, "C-PAIR", "T§7.3 (Q7) i_P's counterpart on the pulley", source="S§10.1, S§10.2",
               binds="pairP", relation="fPp = -fPs", uses=["Q7", "cquote"])
    t.contract(ROOT, "C-PAIR", "T§7.3 (Q7) i_U's counterpart on the mount", source="S§10.1, S§10.2",
               binds="pairU", relation="fUm = -fU", uses=["Q7", "cquote"])
    t.derive(ROOT, "fPs = 2*147/4", from_relations=["Q1"], binds="fPs", tag="(n12)",
             text="from Q1 and Q6 the pulley pushes σ upward with 2T = 147/2 N (73.5 N)")
    t.derive(ROOT, "fPp = -147/2", from_relations=["pairP"], binds="fPp", tag="(n12)",
             text="from Q7, i_P's counterpart pushes the pulley down by the same amount")
    t.derive(ROOT, "fU = 147/2", from_relations=["Q5"], binds="fU", tag="(n12)",
             text="from Q5 and Q6, i_U holds the pulley up")
    t.derive(ROOT, "fUm = -147/2", from_relations=["pairU"], binds="fUm", tag="(n12)",
             text="from Q7 the mount carries a 147/2 N load; without Q4, 147/2 N plus the pulley's weight")
    t.answer(["fUm"], "T§7.3 the mount load, a conditional consequence under Q1-Q7. Not an answer in the source: "
             "recorded as a labelled answer so its ledger shows what it rests on. Merging σ's two encounters "
             "under one key would predict T = 147/4 N instead of 2T", label="mount")

    # T§7.4 system sums, and what the exact frame stipulation costs
    t.derive(ROOT, "fG1 + T1 + fG2 + T2 = -49/10", tag="(n13)", uses=["sysS", "cinc"], text="T§7.4 forces on S, on ŷ")
    t.derive(ROOT, "m1*a1 + m2*a2 = -49/10", tag="(n14)", uses=["e9"], text="T§7.4 ENTRY E9 on each block; agrees "
             "with (n13) as an algebraic identity of the two block accounts, not Newton II for an 8 kg system "
             "(no entry, S§6.4)")
    t.derive(ROOT, "cG1 + cG2 + fUm = 49/10", tag="(n15)", uses=["Q6"],
             text="T§7.4 the load on Earth and the support, under Q1-Q7")
    t.entry(ROOT, "E5", Q["E5s"], uses=["rin"], text="T§7.4 a finite-mass Earth receiving +49/10 N recoils at about "
            "(49/10 N)/(5.97 × 10²⁴ kg) ≈ 8.2 × 10⁻²⁵ m/s² (approximate, not checked here): [5]'s exact "
            "stipulation is literally false, an exactness idealisation of that size")

    # T§8 value lock and the two masses
    t.contract(ROOT, "C-VL", "T§8 two routes to the member f(i_S1 → B1) at (i_S1, B1, t0): the mechanism route "
               "(the solve at [23]) and the remainder route (S§9.3) f(i_S1 → B1) = Fnet(B1) − H(B1) − "
               "f(i_G1 → B1), with H(B1) = 0 from [7]", source="S§2.1, S§9.3", binds="cvl",
               uses=["T1", "haze1", "fG1"])
    t.derive(ROOT, "m1*a1 = 147/20", tag="(n16)", uses=["e9"],
             text="net-force-material-object(B1) by E9; C-BR identifies it with the Force-Sum net force")
    t.derive(ROOT, "m1*a1 - haze1 - fG1 = T1", tag="(n17)", uses=["cvl", "cbr1"],
             text="remainder route 147/20 + 147/5 = 147/4, the mechanism value: the lock holds, but not "
                  "independently (a1 came from the same relations)")
    t.derive(ROOT, "m2*a2 - haze2 - fG2 = 147/4", tag="(n18)", uses=["e9", "cbr2"],
             text="on B2, −49/4 + 49 = 147/4; that this equals B1's value is M-EQ, not the value lock")
    t.open(ROOT, "T§8 an independent lock would need a trajectory measured through E7 under a declared estimation "
           "contract (S§7.3-7.4), or a measured mount load carried back through Q1-Q7. The P-EQV-free formulas "
           "for a1 and T are checked by this script at μ(B1) = 7/2, μ(B2) = 9/2, outside the trace")

    # T§9 persistence, the interval, tolerance
    t.input(ROOT, "P14", "identity", "T§9 (P1) mass persistence; (P2) the same account on J′: exactly two "
            "interactions per block, H = 0, no contact with the pulley or the floor, drag negligible as the "
            "speeds change; (P3) M-EQ and M-KIN hold on J′; (P4) g uniform over the heights swept, R stays "
            "inertial", uses=["persist"])
    t.open(ROOT, "T§9 interval claim (G10): given W1-W17 and P1-P4 on J′, a = 49/20 m/s² is constant on J′; "
           "recorded as text, not checked", uses=["P14", "a1"])
    t.contract(ROOT, "C-HZ", "T§9 tolerance variant, an illustration and not part of the result: unkeyed haze s_k "
               "on each block's account, |s_k| ≤ h; M-KIN kept exact", source="S§11.2", binds="chz")
    for n, text, address in (("a1v", "a1 in the variant", "a(B1, t0, R) in the C-HZ variant"),
                             ("T1v", "T1 in the variant", "(i_S1, B1, t0) in the C-HZ variant"),
                             ("T2v", "T2 in the variant", "(i_S2, B2, t0) in the C-HZ variant"),
                             ("dlt", "δ, the keyed neglected pulley term", "δ(pulley, t0) in the C-HZ variant"),
                             ("s1", "unkeyed haze on B1", "s(B1, t0) in the C-HZ variant"),
                             ("s2", "unkeyed haze on B2", "s(B2, t0) in the C-HZ variant")):
        t.unknown(ROOT, n, text, address=address, ref="C-HZ", uses=["chz"])
    t.input(ROOT, "dmeq", "model", "T§9 M-EQ replaced by a named, keyed, neglected pulley term T2 − T1 = δ, |δ| ≤ d "
            "(a mechanism relation, not haze; for a massive pulley with no slip and a frictionless axle, "
            "δ = (I/r²)·a1)", relation="T2v = T1v + dlt")
    t.contract(ROOT, "C-HZ", "T§9 B1's account with haze", source="S§11.2", binds="hz1",
               relation="3*a1v = T1v - 147/5 + s1", uses=["chz"])
    t.contract(ROOT, "C-HZ", "T§9 B2's account with haze, a2 = −a1 kept", source="S§11.2", binds="hz2",
               relation="-5*a1v = T2v - 49 + s2", uses=["chz"])
    variant = ["hz1", "hz2", "dmeq"]
    t.derive(ROOT, "a1v = (98/5 - dlt + s1 - s2)/8", from_relations=variant, name="n19a", tag="(n19)")
    t.derive(ROOT, "T1v = 147/4 - (3*dlt + 5*s1 + 3*s2)/8", from_relations=variant, name="n19b", tag="(n19)")
    t.derive(ROOT, "T2v = 147/4 + (5*dlt - 5*s1 - 3*s2)/8", from_relations=variant, name="n19c", tag="(n19)")
    t.input(ROOT, "h", "haze", "T§9 haze bound h = 1/10 N", value="1/10", unit="N")
    t.input(ROOT, "d", "value/model", "T§9 pulley-term bound d = 1/5 N", value="1/5", unit="N")
    corner = "half-width at the worst sign corner (deterministic, combined conservatively; the corner is by hand)"
    t.derive(ROOT, "(d + 2*h)/8 = 1/20", tag="(n20)", uses=["n19a"], text=f"a1 {corner}: a1 ∈ [12/5, 5/2] m/s²")
    t.derive(ROOT, "(3*d + 8*h)/8 = 7/40", tag="(n20)", uses=["n19b"], text=f"T1 {corner}: T1 ∈ [1463/40, 1477/40] N")
    t.derive(ROOT, "(5*d + 8*h)/8 = 9/40", tag="(n20)", uses=["n19c"], text=f"T2 {corner}: T2 ∈ [1461/40, 1479/40] N")


# ---------------------------------------------------------------------------
# T§10(b) statuses, with the source's countermodels (re-solved exactly below)
# ---------------------------------------------------------------------------

W5_CM = "Drop either interaction and a changes. A g that differs between the blocks changes a."
W16_CM = "CM6: an unlisted 1 N downward push on B1 gives 8a = 98/5 − 1, so a = 93/40."
CM3 = "CM3: reading g as a field strength in N/kg, μ(B2) = 6 kg with m(B2) = 5 kg gives 8a = 3·49/5, so a = 147/40."
ANNOTATIONS = {
    "pp1": ("REQUIRED", "", "W1: the precondition for E7-E10 to apply at all"),
    "pp2": ("REQUIRED", "", "W1"),
    "transl1": ("NEEDS", "A block rocking about a horizontal axis, centre of mass offset from the attachment: "
                "a1 + a2 = 0 fails for the representatives.", "W2"),
    "transl2": ("NEEDS", "as for B1 (W2)", "W2"),
    "m1": ("NEEDS", "CM1: m(B1) = 4 kg gives 9a = 49/5, so a = 49/45.", "W3"),
    "m2": ("NEEDS", "computed here, not in the source: m(B2) = 6 kg gives 9a = 147/5, so a = 49/15.", "W3"),
    "rin": ("NEEDS", "CM2: the support in a lift accelerating upward at 1 m/s² gives 8a = 2·(49/5 + 1), so "
            "a = 27/10.", "W4"),
    "admG1": ("NEEDS", W5_CM, "W5"), "admG2": ("NEEDS", W5_CM, "W5"),
    "w1": ("NEEDS", W5_CM, "W5"), "w2": ("NEEDS", W5_CM, "W5"),
    "g": ("NEEDS", "Changing g scales a.", "W6"),
    "peqv1": ("ENTAILED", "", "W7: by W5 ∧ W6 under the free-fall reading of g; NEEDS under a field-strength "
              "reading (" + CM3 + ")"),
    "peqv2": ("ENTAILED", "", "W7: by W5 ∧ W6 under the free-fall reading of g; NEEDS under a field-strength "
              "reading (" + CM3 + ")"),
    "admS1": ("REQUIRED", "", "W8; its 'taut at t0' clause is ENTAILED by W13"),
    "admS2": ("REQUIRED", "", "W8; its 'taut at t0' clause is ENTAILED by W13"),
    "pull1": ("NEEDS", "Angled segments change the ŷ-components.", "W9 (verticality); T ≥ 0 is used only at [25]"),
    "pull2": ("NEEDS", "Angled segments change the ŷ-components.", "W9 (verticality)"),
    "Ea": ("NEEDS", "A heavy chain: the two end forces differ.", "W10 (via M-EQ)"),
    "Eb": ("NEEDS", "CM4: I/r² = 1 kg gives 9a = 2·49/5, so a = 98/45. CM5: axle friction of 0.8 N at the rim "
           "gives a = 47/20 if B2 is descending at t0, 51/20 if ascending.", "W11 (via M-EQ)"),
    "meq": ("ENTAILED", "", "T§10(b) has no row for M-EQ: it is replaced by its premise set E-a ∧ E-b (W10, W11)"),
    "Ka": ("NEEDS", "An elastic cord at a changing stretch: in general a1 + a2 ≠ 0.", "W12 (via M-KIN)"),
    "Kb": ("REQUIRED", "", "W13 (via M-KIN): slack gives only an inequality"),
    "Kc": ("NEEDS", "An axle accelerating at A_P gives a1 + a2 = 2A_P.", "W14 (via M-KIN)"),
    "Kde": ("NEEDS", "An elastic hook at a changing stretch breaks the coupling.", "W15 (rigid attachments)"),
    "diff": ("REQUIRED", "", "W15 (differentiability)"),
    "mkin": ("ENTAILED", "", "T§10(b) has no row for M-KIN: it is replaced by K-a to K-e (W12-W15) with the "
             "vertical segments (W9)"),
    "comp1": ("NEEDS", W16_CM, "W16"), "haze1": ("NEEDS", W16_CM, "W16"),
    "comp2": ("NEEDS", "computed here, not in the source: an unlisted 1 N downward push on B2 gives "
              "8a = 98/5 + 1, so a = 103/40.", "W16"),
    "haze2": ("NEEDS", "as for comp2 (computed here)", "W16"),
    "persist": ("NEEDS", "Putting B2's mass into B1's account changes p.", "W17 (structural)"),
    "axis": ("USES", "", "W18: reversing the axis and the signs together leaves p physically unchanged"),
    "cquote": ("USES", "", "W18 (the quoting convention)"),
    "bn": ("USES", "", "W19: matters only in T§7"),
    "sigma1": ("USES", "", "W19: matters only in T§7"),
    "sysS": ("USES", "", "W19: matters only in T§7"),
}


def build() -> Trace:
    t = Trace(QUESTION, EDITION, entries=load_entries(str(ENTRIES)))
    to_answer(t)
    consequences(t)
    for name, (status, cm, note) in ANNOTATIONS.items():
        t.annotate(name, status, countermodel=cm, note=note, answer="p")  # T§10(b) is relative to p
    return t


# Each countermodel: the modified relations on one upward axis, and the value of a = a1 the source states.
COUNTERMODELS = {
    "CM1": (["4*a1 = T - 4*49/5", "5*a2 = T - 49", "a2 = -a1"], "49/45"),
    "CM2": (["3*a1 = T - 3*(49/5 + 1)", "5*a2 = T - 5*(49/5 + 1)", "a2 = -a1"], "27/10"),
    "CM3": (["3*a1 = T - 3*49/5", "5*a2 = T - 6*49/5", "a2 = -a1"], "147/40"),
    "CM4": (["3*a1 = T1 - 147/5", "5*a2 = T2 - 49", "T2 = T1 + 1*a1", "a2 = -a1"], "98/45"),
    "CM5 descending": (["3*a1 = T1 - 147/5", "5*a2 = T2 - 49", "T2 = T1 + 4/5", "a2 = -a1"], "47/20"),
    "CM5 ascending": (["3*a1 = T1 - 147/5", "5*a2 = T2 - 49", "T2 = T1 - 4/5", "a2 = -a1"], "51/20"),
    "CM6": (["3*a1 = T - 147/5 - 1", "5*a2 = T - 49", "a2 = -a1"], "93/40"),
    "m(B2) = 6 (here)": (["3*a1 = T - 147/5", "6*a2 = T - 6*49/5", "a2 = -a1"], "49/15"),
    "push on B2 (here)": (["3*a1 = T - 147/5", "5*a2 = T - 49 - 1", "a2 = -a1"], "103/40"),
}


def _solve(eqs: list[str]) -> dict[str, Fraction]:
    forms = [parse_equation(e)[0] for e in eqs]
    res = solve_linear(forms, sorted({n for f in forms for n in f.names()}))
    assert res["status"] == "unique", (eqs, res)
    return res["values"]


def check_countermodels() -> list[str]:
    out = []
    for cm, (eqs, stated) in COUNTERMODELS.items():
        a1 = _solve(eqs)["a1"]
        assert a1 == Fraction(stated) and a1 != Fraction(49, 20), (cm, a1)
        out.append(f"{cm}: a = {frac(a1)}")
    return out


def check_peqv_formulas() -> str:
    """T§8: without P-EQV, a1 = (μ2 − μ1)g/(m1 + m2) and T = g(m1μ2 + m2μ1)/(m1 + m2), at μ = 7/2, 9/2."""
    m1, m2, g, mu1, mu2 = Fraction(3), Fraction(5), Fraction(49, 5), Fraction(7, 2), Fraction(9, 2)
    v = _solve([f"3*a1 = T - (7/2)*(49/5)", f"5*a2 = T - (9/2)*(49/5)", "a2 = -a1"])
    assert v["a1"] == (mu2 - mu1) * g / (m1 + m2)
    assert v["T"] == g * (m1 * mu2 + m2 * mu1) / (m1 + m2)
    return f"P-EQV-free formulas at μ = 7/2, 9/2: a1 = {frac(v['a1'])}, T = {frac(v['T'])}"


def check_tolerance_corners() -> str:
    """T§9 (n20): the 8 sign corners of δ = ±d, s1 = ±h, s2 = ±h bound a1, T1, T2 exactly."""
    d, h = Fraction(1, 5), Fraction(1, 10)
    seen: dict[str, list[Fraction]] = {"a1": [], "T1": [], "T2": []}
    for sd, s1, s2 in product((1, -1), repeat=3):
        v = _solve([f"3*a1 = T1 - 147/5 + ({s1 * h})", f"-5*a1 = T2 - 49 + ({s2 * h})", f"T2 = T1 + ({sd * d})"])
        for k in seen:
            seen[k].append(v[k])
    stated = {"a1": ("12/5", "5/2"), "T1": ("1463/40", "1477/40"), "T2": ("1461/40", "1479/40")}
    for k, (lo, hi) in stated.items():
        assert (min(seen[k]), max(seen[k])) == (Fraction(lo), Fraction(hi)), (k, seen[k])
    return "tolerance corners: a1 ∈ [12/5, 5/2], T1 ∈ [1463/40, 1477/40], T2 ∈ [1461/40, 1479/40]"


def check_working_matches_solve(t: Trace) -> str:
    """The hand working (n6)-(n8) gives the values the EXTERNAL solve fixed."""
    for rel, name in (("n6", "a1"), ("n7", "a2"), ("n8", "T")):
        eq = t.bindings[rel].equation
        form, _ = parse_equation(eq, {})
        assert form.as_dict() == {name: 1} and -form.const == t.values[name], (rel, eq)
    return "hand working (n6)-(n8) equals the [23] solve"


# ---------------------------------------------------------------------------
# Comparison with T§10
# ---------------------------------------------------------------------------

# (row, premise, source kind, source status, source placement for p, tool rows)
# placement: 'member' (NEEDS/REQUIRED and feeds p), 'pruned' (feeds p, ENTAILED/USES), 'out' (does not feed p)
W_ROWS = [
    ("W1", "material objects as point-particles (K7)", "recognition/model", "REQUIRED", "member", ["pp1", "pp2"]),
    ("W2", "translation only", "model", "NEEDS", "member", ["transl1", "transl2"]),
    ("W3", "m(B1) = 3 kg, m(B2) = 5 kg", "value", "NEEDS", "member", ["m1", "m2"]),
    ("W4", "R exactly inertial (E5), support at rest, recoil left out", "recognition/model", "NEEDS", "member",
     ["rin"]),
    ("W5", "gravity admitted, binary with E, uniform-field weight, same g", "recognition/model", "NEEDS", "member",
     ["admG1", "admG2", "w1", "w2"]),
    ("W6", "g = 49/5 m/s², local free-fall", "value", "NEEDS", "member", ["g"]),
    ("W7", "P-EQV μ(Bk) = m(Bk)", "identity/model", "ENTAILED (free-fall) / NEEDS (field-strength)", "pruned",
     ["peqv1", "peqv2"]),
    ("W8", "string interactions admitted, active at t0", "recognition", "REQUIRED; taut clause ENTAILED by W13",
     "member", ["admS1", "admS2"]),
    ("W9", "string only pulls; segments vertical", "model", "NEEDS (verticality)", "member", ["pull1", "pull2"]),
    ("W10", "E-a negligible string mass", "model", "NEEDS (via M-EQ)", "member", ["Ea"]),
    ("W11", "E-b no net tangential pulley force (+ normalization)", "model", "NEEDS (via M-EQ)", "member", ["Eb"]),
    ("W12", "K-a inextensible", "model", "NEEDS (via M-KIN)", "member", ["Ka"]),
    ("W13", "K-b taut throughout open J ∋ t0", "model", "REQUIRED (via M-KIN)", "member", ["Kb"]),
    ("W14", "K-c axle at rest in R", "model", "NEEDS (via M-KIN)", "member", ["Kc"]),
    ("W15", "K-d, K-e; twice differentiable on J", "model", "NEEDS (rigid) / REQUIRED (differentiability)",
     "member", ["Kde", "diff"]),
    ("W16", "membership complete; H = 0", "completeness", "NEEDS", "member", ["comp1", "comp2", "haze1", "haze2"]),
    ("W17", "same objects, masses, addresses", "identity/persistence", "NEEDS (structural)", "member", ["persist"]),
    ("W18", "axis, units, quoting convention", "convention", "USES", "pruned", ["axis", "cquote"]),
    ("W19", "S = {B1, B2}; binary Newtonian; σ one participant", "choice/model", "USES (only T§7)", "out",
     ["bn", "sigma1", "sysS"]),
    ("W20", "Q1-Q7", "model", "not used for p", "out", ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]),
    ("W21", "P1-P4", "identity/persistence", "not used for p", "out", ["P14"]),
]

# Tool rows T§10(b) covers without a row of their own: (expected placement, why).
IMPLICIT = {
    "meq": ("pruned", "M-EQ, replaced in T§10(b) by its premise set W10 ∧ W11"),
    "mkin": ("pruned", "M-KIN, replaced in T§10(b) by W12-W15 with W9"),
    "dmeq": ("out", "T§9 tolerance variant, 'not part of the result'"),
    "h": ("out", "T§9 tolerance variant"),
    "d": ("out", "T§9 tolerance variant"),
}

KIND_ALIASES = {"persistence": "identity"}  # the API's 'identity' kind covers identity and persistence

SOURCE_THEORY_P = {"K1", "K2", "K6", "K8", "K10", "K12", "K7", "E5", "E7", "E8", "E10", "E11",
                   "C-FS", "C-BR", "C-ADM", "C-CM", "C-T9", "C-ID", "READING [22]"}
SOURCE_THEORY_CONSEQUENCES = {"E4", "K16", "E6", "E9", "C-PAIR", "C-INC", "C-VL", "C-HZ", "READING T§7.1"}
SOURCE_STEP_MEMBERS = ["(n1)", "(n2)", "(n3)", "(n4)", "(n5)", "(n6)", "(n7)", "(n8)", "(n9)", "(n10)", "(n11)",
                       "(n12)", "(n13)", "(n14)", "(n15)", "(n16)", "(n17)", "(n18)", "(n19)", "(n20)",
                       "[8]", "[18]", "[21]", "T§4 pending", "[23]"]


def _kinds(kind: str) -> set[str]:
    return {KIND_ALIASES.get(k, k) for k in kind.split("/") if k}


def _placements(led: dict) -> dict[str, tuple[str, dict]]:
    out = {c["name"]: ("member", c) for c in led["commitments"]}
    out.update({c["name"]: ("pruned", c) for c in led["pruned"]})
    out.update({c["name"]: ("out", c) for c in led["not_in_answer"]})
    return out


def _theory_key(row: dict) -> str:
    if row["op"] == "READING":
        return "READING " + row["text"].split()[0]
    return row["ref"].split(" ")[0].rstrip(",")


def disagreements(t: Trace) -> list[tuple[str, str]]:
    """Every remaining disagreement between the tool's ledger for p and T§10, as (key, detail)."""
    led = t.ledger(answer="p")
    rows = _placements(led)
    out: list[tuple[str, str]] = []
    mapped = set(IMPLICIT)
    for w, _prem, skind, sstat, splace, names in W_ROWS:
        mapped.update(names)
        tool_kinds: set[str] = set()
        for n in names:
            place, c = rows[n]
            tool_kinds |= _kinds(c["kind"])
            if place != splace:
                out.append((f"{w} {n} placement", f"tool: {place}; source: {splace} ({sstat})"))
            extra = _kinds(c["kind"]) - _kinds(skind)
            if extra:
                out.append((f"{w} {n} kind", f"tool kind {c['kind']}; source row kind {skind}"))
            if place == "member" and c["status"] == "NEEDS" and not c["countermodel"]:
                out.append((f"{w} {n} countermodel", "NEEDS without a countermodel"))
        missing = _kinds(skind) - tool_kinds
        if missing:
            out.append((f"{w} kind", f"no tool row carries the source kind(s) {sorted(missing)}"))
        if len(names) > 1:
            out.append((f"{w} split", f"one source row is {len(names)} tool rows: {', '.join(names)}"))
    for n, (expected, why) in IMPLICIT.items():
        place, _ = rows[n]
        if place != expected:
            out.append((f"{n} placement", f"tool: {place}; expected {expected} ({why})"))
    for n, (place, c) in rows.items():
        if n not in mapped:
            out.append((f"{n} no row", f"{c['step']} {n} ({c['kind']}) is '{place}' for p with status "
                                       f"'{c['status'] or 'none'}' and has no T§10(b) row: {c['content']}"))
    # (a) theory side
    in_p = {_theory_key(r) for r in led["theory"]}
    outside = {_theory_key(r) for r in led["outside_answer"] if r["op"] in ("ENTRY", "CONTRACT", "READING")}
    for k in sorted(SOURCE_THEORY_P - in_p):
        out.append((f"(a) {k} not in p", "the source lists it as required for p; the tool's cone does not reach it"))
    for k in sorted(in_p - SOURCE_THEORY_P):
        out.append((f"(a) {k} in p", "the tool's cone reaches it; the source does not list it as required for p"))
    for k in sorted(SOURCE_THEORY_CONSEQUENCES - outside):
        out.append((f"(a) {k} consequence", "the source lists it for consequences only; the tool has no such "
                                            "step outside p's cone"))
    for k in sorted(outside - in_p - SOURCE_THEORY_CONSEQUENCES):
        out.append((f"(a) {k} outside", "the tool has it outside p's cone only; the source lists it nowhere"))
    # (c) step members
    tags = {s["tag"] or s["op"] for s in led["step_members"]}
    for x in SOURCE_STEP_MEMBERS:
        if x not in tags:
            out.append((f"(c) {x}", "listed by the source as a step member; does not feed p in the tool"))
    for x in sorted(tags - set(SOURCE_STEP_MEMBERS)):
        out.append((f"(c) {x} tool", "feeds p in the tool; the source does not tag it"))
    return out


def compare(t: Trace) -> str:
    led = t.ledger(answer="p")
    rows = _placements(led)
    L = ["## Comparison with the source's T§10 (answer p)", "",
         "### (b) world premises, row by row", "",
         "| Row | Premise | Source kind | Source status | Tool rows: placement, kind, status | Source placement |",
         "|---|---|---|---|---|---|"]
    for w, prem, skind, sstat, splace, names in W_ROWS:
        cells = [f"{n}: {rows[n][0]}, {rows[n][1]['kind']}, {rows[n][1]['status'] or 'none'}" for n in names]
        L.append(f"| {w} | {prem} | {skind} | {sstat} | {'; '.join(cells)} | {splace} |")
    L += ["", "### Remaining disagreements", ""]
    L += [f"- **{k}**: {v}" for k, v in disagreements(t)] or ["- none"]
    h = t.hypothesis_set(answer="p")
    L += ["", "### Hypothesis set for p", "",
          f"- {len(h)} members: p, {sum(m['id'].startswith('A') for m in h)} negated commitments, "
          f"{sum(m['id'].startswith('M') for m in h)} step members",
          f"- pruned (feed p, not members): {', '.join(c['name'] for c in led['pruned'])}",
          f"- undetermined unknowns: {', '.join(u['name'] for u in led['undetermined'])}"]
    mount = t.ledger(answer="mount")
    p_names = {c["name"] for c in led["commitments"]}
    L += ["", "### The mount-load consequence", "",
          f"- commitments of 'mount' not in p: "
          f"{', '.join(c['name'] for c in mount['commitments'] if c['name'] not in p_names)}",
          f"- warnings: {'; '.join(mount['warnings'])}", ""]
    return "\n".join(L)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t = build()
    assert t.values["a1"] == Fraction(49, 20)
    assert t.values["a2"] == Fraction(-49, 20)
    assert t.values["T"] == Fraction(147, 4)
    again = Trace.replay(json.loads(t.to_json()))
    assert again.values == t.values
    print(t.to_markdown())
    print(compare(t))
    print("### Checks run by this script\n")
    quoted = sum(1 for c in t.commands if c["args"].get("quote"))
    print(f"- {quoted} ENTRY quotes verified verbatim by Trace against {ENTRIES.name}")
    print("- answer asserted: a1 = 49/20, a2 = -49/20, T = 147/4; the saved record replays exactly")
    print(f"- {check_working_matches_solve(t)}")
    print("- countermodels re-solved exactly: " + "; ".join(check_countermodels()))
    print(f"- {check_peqv_formulas()}")
    print(f"- {check_tolerance_corners()}")
    return 0


# ---------------------------------------------------------------------------
# Tests (python -m pytest handtrace_example_atwood.py)
# ---------------------------------------------------------------------------


def _need_entries():
    if not ENTRIES.exists():
        pytest.skip(f"entries file not found: {ENTRIES}")


def _xfail(reason: str):
    return pytest.mark.xfail(strict=True, reason=reason) if pytest else (lambda f: f)


def test_trace_answers_replays_and_renders():
    _need_entries()
    t = build()
    assert (t.values["a1"], t.values["a2"], t.values["T"]) == (Fraction(49, 20), Fraction(-49, 20), Fraction(147, 4))
    assert t.values["fUm"] == Fraction(-147, 2)
    assert Trace.replay(json.loads(t.to_json())).values == t.values
    md = t.to_markdown()
    assert "## Ledger for answer p" in md and "## Ledger for answer mount" in md
    led = t.ledger(answer="p")
    assert not led["conflicts"] and not led["withdrawn"]
    assert [r["step"] for r in led["solve_reports"]] == [s.id for s in t.steps if s.tag == "T§4 pending"]


def test_side_checks():
    _need_entries()
    t = build()
    check_countermodels()
    check_peqv_formulas()
    check_tolerance_corners()
    check_working_matches_solve(t)


def test_quotes_are_verified_against_the_entries():
    _need_entries()
    t = Trace("q", entries=load_entries(str(ENTRIES)))
    with pytest.raises(TraceError, match="verbatim"):
        t.entry(ROOT, "E8", "its net force divided by its mass")


def test_post_answer_steps_do_not_feed_p_and_the_mount_load_rests_on_q1_q7():
    _need_entries()
    t = build()
    p_idx = t.answers[0][1]
    assert all(i <= p_idx for i in t.cone("p"))
    p = _placements(t.ledger(answer="p"))
    mount = _placements(t.ledger(answer="mount"))
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"):
        assert p[q][0] == "out" and mount[q][0] == "member"
    # statuses are per binding, not per answer: the Q rows carry no status for 'mount'
    assert any("no status yet" in w and "Q1" in w for w in t.ledger(answer="mount")["warnings"])


def test_counterparts_on_sigma_keep_distinct_addresses():
    _need_entries()
    t = build()
    with pytest.raises(TraceError, match="address"):
        t.unknown(ROOT, "cS12", "σ's two counterparts merged under one key", address="(i_S1,σ end 1,t0)",
                  ref="C-PAIR")


def test_statuses_for_p_do_not_prune_premises_of_the_mount_answer():
    """T§10(b)'s statuses are scoped to p (annotate(answer='p')), so W19's USES does not prune bn and
    sigma1 from H(mount), which rests on them."""
    _need_entries()
    mount = _placements(build().ledger(answer="mount"))
    assert mount["bn"][0] == "member" and mount["sigma1"][0] == "member"


def test_delivery_lands_at_the_sites_caller():
    """Documented v2 rule (not a bug): a delivery passes one level, from the frame's parent.
    The source re-delivers m(B1) at the weight slot [9]; here it lands at d1.1 and reaches the
    sibling demands too, and a delivery straight to the slot is refused."""
    _need_entries()
    t = build()
    dm = next(s for s in t.steps if s.op == "DELIVER" and s.uses == ("m1",))
    assert dm.frame == "D1.1"
    assert t.value_visible("D1.1.S", "m1") is not None  # the string slot sees it as well
    with pytest.raises(TraceError, match="already visible"):
        t.deliver("D1.1.G", "m1")


# The disagreements with T§10 that remain under v2 (see the report). Pinned so a change shows up.
EXPECTED_DISAGREEMENTS = {
    "W1 split", "W2 split", "W3 split", "W5 split", "W7 split", "W8 split", "W9 split", "W15 split", "W16 split",
    "W18 split", "W19 split", "W20 split",
    "W6 g kind",
    "W16 haze1 kind", "W16 haze2 kind",
    "W18 cquote placement",
    "norm no row", "d3bind no row", "J no row",
    "(c) T§4 pending", "(c) (n9)", "(c) (n10)", "(c) (n11)", "(c) (n12)", "(c) (n13)", "(c) (n14)", "(c) (n15)",
    "(c) (n16)", "(c) (n17)", "(c) (n18)", "(c) (n19)", "(c) (n20)",
    "(c) [11] RETURN (partial) tool", "(c) [18] RETURN (partial) tool", "(c) [22] hence tool", "(c) [23] input tool",
}


def test_remaining_disagreements_with_t10():
    _need_entries()
    got = {k for k, _ in disagreements(build())}
    assert got == EXPECTED_DISAGREEMENTS, (sorted(got - EXPECTED_DISAGREEMENTS),
                                           sorted(EXPECTED_DISAGREEMENTS - got))


if __name__ == "__main__":
    raise SystemExit(main())
