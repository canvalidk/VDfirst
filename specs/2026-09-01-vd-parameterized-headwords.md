# VD Parameterized Headwords

- Date: 2026-09-01
- Status: Implemented prototype
- Branch: `codex/parameterized-headwords`
- Scope: underscore calls, flat partial instantiation, tokenizer and trace integration

## 1. Purpose

VD entries may describe parameterized symbols without adding primitive
interpretation. Expansion performs beta-like structural substitution and then
returns the resulting residual to the ordinary tokenizer. It does not perform
arithmetic, physics, delta reduction, or any other primitive semantic action.

This specification supersedes Token Prop 3's static underscore-qualifier rule
and its instruction to omit arguments from headwords. Other delimiter,
longest-first, and backtick-escape rules remain in force.

## 2. Signature and call syntax

Every underscore suffix is positional. It is never a static qualifier.

An entry headword declares a signature:

```text
force_p_t
```

```text
stem:     force
formals:  [p, t]
arity:    2
```

A residual may call the signature with zero through arity actuals:

```text
force
force_Earth
force_Earth_3
```

Each actual is currently one atomic underscore-separated value. Letters,
digits, and internal hyphens are accepted. Spaces, underscores inside one
actual, and nested residual expressions are deferred.

## 3. Temporary signature-identity rule

One exact stem has one formal list throughout a dictionary. The first entry
for `force` establishes its signature. Redefinitions must repeat the same
formal list.

Thus `force_p_t` followed by `force_p`, `force_object_time`, or bare `force`
as another entry is a definition/import error. The append is atomic and leaves
the dictionary unchanged.

This is a replaceable ambiguity band-aid, not a claim that arity overloading is
impossible or undesirable.

## 4. Flat partial instantiation

Given:

```text
force_p_t := inertial-mass_p multiply inertial-acceleration_p_t
```

the entry body instantiates as follows:

```text
force           -> inertial-mass_p multiply inertial-acceleration_p_t
force_Earth     -> inertial-mass_Earth multiply inertial-acceleration_Earth_t
force_Earth_3   -> inertial-mass_Earth multiply inertial-acceleration_Earth_3
```

Under-application is allowed. Supplied actuals bind the leftmost formals;
unsupplied formals remain visibly unchanged.

Over-application is an error. For example, `force_Earth_3_extra` reports that
three arguments were supplied to an arity-two stem and performs no trace or
dictionary mutation.

## 5. Substitution boundary and simultaneity

All supplied bindings are applied simultaneously in one token-aware pass.
Inserted actuals are not scanned again as formals during that pass.

```text
pair_x_y := x followed-by y
pair_y_Z -> y followed-by Z
```

A formal is replaceable when it is:

- a standalone prose atom; or
- a complete underscore argument segment of another call.

It is not replaced inside a larger alphanumeric or hyphen-glued atom.

```text
t          -> replace
velocity_t -> replace the argument segment
t_state    -> replace the argument segment
state      -> do not replace
state-t    -> do not replace
particle   -> do not replace
```

Backtick-escaped occurrences remain literal and are not substituted.

## 6. No closures or alpha-renaming yet

This operation is called **partial instantiation**, not lambda-calculus partial
application. Expansion does not return a closure and the remaining formals do
not retain hidden binder identity. After instantiation they are ordinary
visible residual symbols.

Consequently:

```text
pair_x_y := x followed-by y
pair_y   -> y followed-by y
```

No alpha-renaming is performed. Introducing arbitrary fresh visible symbols
would itself be a potentially meaningful intervention in VD. Genuine binding,
closures, alpha-equivalence, and capture avoidance are deferred until a use
case requires them.

## 7. Expansion and recall

Call resolution and instantiation happen before the chosen trace operation:

- `EXPAND` instantiates the selected entry, tokenizes the resulting residual,
  and creates the ordinary child demand. Inserted known headwords therefore
  become lazy demands but are not automatically expanded.
- `RECALL` stores the instantiated entry text literally, preserving RECALL's
  non-recursive behavior.
- Inspection `recall <call>` displays the instantiated entry text.

Example:

```text
velocity_t := velocity at time t
inertial-acceleration_t := derivative of velocity_t at time t

EXPAND inertial-acceleration_3
-> derivative of {velocity_3} at time 3
```

## 8. Structural identity

Stored entries and dependency-graph nodes retain authored signature identity.
A definition reference such as `force_Earth_3` records a structural dependency
on `force_p_t`. Runtime `Definiens` holes retain the canonical call spelling,
including supplied actuals, so later expansion can instantiate correctly.

Cycle notices remain conservative exact-call comparisons for now. Different
calls of one stem are not collapsed into one cycle identity.

## 9. Deferred decisions

- Multiple signatures or arities for one stem.
- Ambiguity resolution for bare calls under overloading.
- Arbitrary residuals or nested calls as argument values.
- Continued application of a partially instantiated result.
- Closures, hidden binder identity, alpha-renaming, and capture avoidance.
- A meaning for extra arguments beyond reporting an error.
- Whether parameter-name consistency can later relax to arity-only consistency.

The implementation isolates signatures, calls, and instantiation in
`application.py` so these decisions can be replaced without rewriting the
demand graph or expansion machinery.
