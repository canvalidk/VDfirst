"""
vd/newton.py — The Newtonian Mechanics VD Instance (v0.6)

Entries from VD_Newton_v0_4.pdf Design 2 (E1..E45), rewritten with
tokeniser-compatible headword conventions:

  - Hyphen glues compound names: `point-particle`, `inertial-frame`
  - Underscore attaches qualifiers: `canonical-force_acting-object`
  - Pipe marks plurals: `acting-force|s` matches headword `acting-force`
  - Arguments dropped from headwords: `net force(p,t)` → `net-force`
  - References are opt-in: hyphenated = reference, spaced = prose

Section tags are carried as metadata for display, not as VD-core data.

Changes in v0.6 (from v0.5):
  - NEW E37: mechanical-composition_point-particle (ownership inversion)
  - REVISED E38 (old E37): paired-particle_acting-object redefined as
    back-reference derived from mechanical-composition
  - All subsequent entry numbers shifted by +1
  - Acting-object ownership bug resolved (see vd_acting_object_fix.md)
"""

try:
    from vd.engine import VDInstance
except ModuleNotFoundError:
    from engine import VDInstance

# Section metadata for display purposes
SECTIONS = {
    'scaffold':       (0, 13),   # E1-E14: non-law kinematics scaffold
    'newton_I':       (14, 16),  # E15-E17: Newton I triplet
    'newton_I_walls': (17, 19),  # E18-E20: Newton I walls + Newton II chimney
    'newton_II':      (20, 22),  # E21-E23: Newton II triplet
    'force_sum':      (23, 25),  # E24-E26: Force sum triplet
    'meta_typing_ch': (26, 26),  # E27: Meta-typing chimney
    'meta_typing':    (27, 29),  # E28-E30: Meta-typing triplet
    'action_react':   (30, 32),  # E31-E33: Action-reaction triplet
    'acting_obj':     (33, 35),  # E34-E36: Acting object triplet
    'mech_comp':      (36, 37),  # E37-E38: Mechanical composition + paired particle
    'non_law_2':      (38, 39),  # E39-E40: Non-law entries
    'closure':        (40, 42),  # E41-E43: Closure triplet
    'closure_walls':  (43, 44),  # E44-E45: Closure walls / residual
}

# ── Design 2 entries (E1..E45) ──────────────────────────────────────
#
# Tokeniser conventions:
#   `-`  inside a headword glues words into one atomic token
#   `_`  attaches a qualifier (subscript)
#   `|`  in definitions is a delimiter — write `headword|s` for plural
#   Unhyphenated multi-word phrases are NOT headword references
#
# In triplet entries, all formula shorthand is replaced by the actual
# headword so the tokeniser picks up the edges needed for 3-cycles.
# Casual shorthand (p, t, m, a) in non-triplet entries is left as-is;
# shorthand entries can be added later.

NEWTON_ENTRIES = [
    # ── 2.1 Kinematics scaffold (non-law) ──────────────────────────

    # E1
    ("time",
     "A real parameter t in R used to order events; differences delta t = t2 - t1 are durations."),

    # E2
    ("reference-frame",
     "A convention for assigning spatial coordinates and a time coordinate to events: an origin, a set of basis vectors, and a clock."),

    # E3
    ("point-particle",
     "An idealised object whose spatial extent and internal structure are neglected."),

    # E4
    ("position",
     "The location of a point-particle at time t in a reference-frame, represented by a vector r(t) in R^3."),

    # E5
    ("displacement",
     "The change in position: delta r = r(t2) - r(t1)."),

    # E6
    ("velocity",
     "v(t) = dr/dt."),

    # E7
    ("speed",
     "The scalar magnitude of velocity: speed(t) = ||v(t)||."),

    # E8
    ("acceleration",
     "a(t) = dv/dt = d^2 r/dt^2."),

    # E9
    ("trajectory",
     "The map t -> r(t) giving the position of a point-particle over some interval I subset R."),

    # E10
    ("straight-line",
     "A set of points {r0 + lambda u : lambda in R} for fixed r0 in R^3 and nonzero direction u in R^3."),

    # E11
    ("path-length",
     "For a differentiable trajectory from t1 to t2, the arc length is s = integral of ||v(t)|| dt."),

    # E12
    ("relative-position",
     "For two point-particle|s in the same reference-frame, the relative-position is r12(t) = r2(t) - r1(t)."),

    # E13
    ("relative-velocity",
     "For two point-particle|s in the same reference-frame, the relative-velocity is v12(t) = v2(t) - v1(t) = dr12/dt."),

    # E14 — chimney for Newton I
    ("uniform-motion",
     "The state of being either stationary or moving along a straight-line with constant speed. "
     "Equivalently, a point-particle is in uniform-motion on an interval I if its velocity is constant "
     "throughout I; i.e. for all t1, t2 in I, v(t1) = v(t2). A point-particle is in uniform-motion at "
     "time t0 if there exists epsilon > 0 such that it is in uniform-motion on (t0 - epsilon, t0 + epsilon)."),

    # ── 2.2 Newton I triplet ───────────────────────────────────────
    # Trio: {uniform-motion, inertial-frame, free-particle}
    # November: uniform-motion (PD from E14)
    # Winter: inertial-frame, free-particle

    # E15 — November redefine
    ("uniform-motion",
     "The state of motion exhibited by a free-particle when described in an inertial-frame."),

    # E16 — Winter 1
    ("inertial-frame",
     "A reference-frame in which every free-particle exhibits uniform-motion."),

    # E17 — Winter 2
    ("free-particle",
     "A point-particle that, when described in an inertial-frame, exhibits uniform-motion."),

    # ── 2.3 Newton I walls + Newton II chimney ─────────────────────

    # E18 — wall for inertial-frame
    ("inertial-frame",
     "A reference-frame standard for Newtonian analysis of motion; historically, a Galilean reference frame."),

    # E19 — wall for free-particle
    ("free-particle",
     "A point-particle not subject to external influence relevant to its motion."),

    # E20 — chimney for Newton II
    ("inertial-acceleration",
     "The acceleration of a point-particle as measured in an inertial-frame."),

    # ── 2.4 Newton II triplet ──────────────────────────────────────
    # Trio: {inertial-acceleration, net-force, inertial-mass}
    # November: inertial-acceleration (PD from E20)
    # Winter: net-force, inertial-mass

    # E21 — November redefine
    ("inertial-acceleration",
     "For a point-particle, inertial-acceleration equals net-force divided by inertial-mass: a = F/m."),

    # E22 — Winter 1
    ("net-force",
     "The vector quantity satisfying net-force = inertial-mass times inertial-acceleration for a point-particle."),

    # E23 — Winter 2
    ("inertial-mass",
     "The positive scalar coefficient m such that net-force = m times inertial-acceleration for a point-particle."),

    # ── 2.5 Force Sum triplet ──────────────────────────────────────
    # Trio: {net-force, interacting-forces-set, acting-force}
    # November: net-force (PD from E22)
    # Winter: interacting-forces-set, acting-force

    # E24 — November redefine
    ("net-force",
     "net-force on particle p at time t is the vector sum of the acting-force element|s "
     "in the interacting-forces-set for p at t."),

    # E25 — Winter 1
    ("interacting-forces-set",
     "The set of acting-force element|s taken to be acting on particle p at time t, "
     "whose vector sum is the net-force on p at t."),

    # E26 — Winter 2
    ("acting-force",
     "A vector force-contribution that appears as an element of some interacting-forces-set "
     "and thereby contributes to the net-force."),

    # ── 2.6 Meta-typing chimney ────────────────────────────────────

    # E27 — chimney for meta-typing
    ("raw-class",
     "An abstract object-type."),

    # ── 2.6 Meta-typing triplet ────────────────────────────────────
    # Trio: {raw-class, class-specific-features, instance-of}
    # November: raw-class (PD from E27)
    # Winter: class-specific-features, instance-of

    # E28 — November redefine
    ("raw-class",
     "An abstract object-type specified by class-specific-features; an object x is treated as "
     "an instance-of the raw-class when it is recognized as possessing the class-specific-features."),

    # E29 — Winter 1
    ("class-specific-features",
     "The set of features that specify a raw-class C; these features are whatever a modeler must "
     "recognize x as having in order to treat x as an instance-of C."),

    # E30 — Winter 2
    ("instance-of",
     "x is treated as an instance of a raw-class C when x is recognized as possessing the "
     "class-specific-features of C."),

    # ── 2.7 Action-Reaction triplet ────────────────────────────────
    # Trio: {acting-force, canonical-force_acting-object, reaction-force_acting-object}
    # November: acting-force (PD from E26)
    # Winter: canonical-force_acting-object, reaction-force_acting-object

    # E31 — November redefine
    ("acting-force",
     "An acting-force is a force-contribution that is either a canonical-force_acting-object "
     "or a reaction-force_acting-object."),

    # E32 — Winter 1
    ("canonical-force_acting-object",
     "A canonical-force_acting-object is an acting-force designated as canonical; the "
     "corresponding reaction-force_acting-object is the acting-force defined as the negative of it."),

    # E33 — Winter 2
    ("reaction-force_acting-object",
     "A reaction-force_acting-object is an acting-force defined as the negative of "
     "canonical-force_acting-object."),

    # ── 2.8 Acting Object triplet ──────────────────────────────────
    # Trio: {canonical-force_acting-object, acting-object, activation-condition_acting-object}
    # November: canonical-force_acting-object (PD from E32)
    # Winter: acting-object, activation-condition_acting-object

    # E34 — acting-object (first definition; Winter 1)
    ("acting-object",
     "An acting-object is an object equipped with both an activation-condition_acting-object "
     "and a corresponding canonical-force_acting-object."),

    # E35 — activation-condition (first definition; Winter 2)
    ("activation-condition_acting-object",
     "If a point-particle fulfills the activation-condition_acting-object of an acting-object, "
     "the canonical-force_acting-object of that acting-object will be an acting-force on the point-particle."),

    # E36 — canonical-force redefine (November redefine)
    ("canonical-force_acting-object",
     "The canonical-force_acting-object is the acting-force that an acting-object exerts on a "
     "point-particle that fulfills the activation-condition_acting-object."),

    # ── 2.8b Mechanical composition + paired particle ──────────────
    # Ownership inversion: particles HAVE acting-objects (composition).
    # Paired-particle is the back-reference derived from composition.

    # E37 — mechanical-composition (NEW in v0.6)
    ("mechanical-composition_point-particle",
     "The mechanical-composition_point-particle of a point-particle is the set of "
     "acting-object|s that the point-particle has. When a point-particle serves as the "
     "representative, or centre of mass, of a body, all acting-object|s of that body are "
     "included in the mechanical-composition_point-particle of that point-particle."),

    # E38 — paired-particle (REVISED in v0.6, was E37)
    ("paired-particle_acting-object",
     "The paired-particle_acting-object of an acting-object is the point-particle whose "
     "mechanical-composition_point-particle includes that acting-object. The acting-object "
     "is modelled as located at the position of its paired-particle_acting-object."),

    # ── 2.9 Non-law ────────────────────────────────────────────────

    # E39 (was E38)
    ("mechanical-system",
     "An arbitrary subset of particles selected by the observer for analysis."),

    # E40 (was E39) — chimney for Closure
    ("interaction-candidate",
     "For a particle p in a mechanical-system S at time t, an interaction-candidate is any "
     "acting-force in the interacting-forces-set for p at t."),

    # ── 2.10 Mechanical Closure triplet ────────────────────────────
    # Trio: {interaction-candidate, interaction-pair, mechanically-closed-system}
    # November: interaction-candidate (PD from E40)
    # Winter: interaction-pair, mechanically-closed-system

    # E41 (was E40) — November redefine
    ("interaction-candidate",
     "An interaction-candidate is an elementary force-unit, every one of which must be able to "
     "be placed in an interaction-pair for the mechanical-system to be a mechanically-closed-system."),

    # E42 (was E41) — Winter 1
    ("interaction-pair",
     "An interaction-pair is the form into which each interaction-candidate is placed in a "
     "mechanically-closed-system."),

    # E43 (was E42) — Winter 2
    ("mechanically-closed-system",
     "A mechanically-closed-system is a mechanical-system in which every interaction-candidate "
     "can be placed in an interaction-pair."),

    # ── 2.11 Non-law (walls + residual) ────────────────────────────

    # E44 (was E43) — wall for interaction-pair
    ("interaction-pair",
     "Two interaction-candidate|s form an interaction-pair when they correspond to the same "
     "acting-object, one being the canonical-force_acting-object associated with that acting-object "
     "and the other being the reaction-force_acting-object associated with that acting-object, "
     "the latter exerted on the paired-particle_acting-object."),

    # E45 (was E44) — wall/residual for mechanically-closed-system
    ("mechanically-closed-system",
     "A mechanically-closed-system is a mechanical-system whose future behaviour is determined "
     "by the equations produced from the interactions internal to it."),
]


def build_newton_instance() -> VDInstance:
    """Build and return the complete Newton VD instance."""
    vd = VDInstance(name="Newton Mechanics v0.6")
    vd.append_many(NEWTON_ENTRIES)
    return vd
