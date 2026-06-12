# ADR 5: No Severing

- Status: Accepted
- Date: 2026-06-11

## Context

The trace accumulates committed structure: expansions, recalls,
injections, flattened literals, reductions, cleanups. Several design
questions kept circling one issue — whether any command may destroy
committed structure, and what the simulator owes a user who changes
their mind.

The forcing case: `back` unresolved the *active* child, and since
navigation can move focus anywhere, `back` could sever an expansion
made arbitrarily many moves earlier — out-of-order undo, with
unexamined consequences for everything built on top of the severed
subtree (reductions cleared up the ancestor chain, settled frames
unsettling, gate decisions invalidated).

The project already assumes no mistakes by the user across the board.
If the user expands a node and later regrets it, that is not the
simulator's responsibility. If you make a mistake, start over.

## Decision

Committed trace structure is never destroyed at the command surface.

- No command unresolves, reparents, reorders, or deletes a committed
  resolution. `back` is removed rather than restricted; there is no
  undo command and there will be no undo stack.
- `flatten` applies to open (unexpanded) holes only. This was already
  enforced by construction — `resolve_literal` goes through the
  open-position check — and is now policy, not accident.
- Overlays remain togglable (`unreduce` clears a reduction) because
  overlays are not structure: the original is intact beneath, and
  clearing one destroys no decision record.
- The data-layer primitive `Demand.unresolve` remains, with its
  invariant maintenance and tests, as machinery for future deliberate
  use (e.g. trace restore). The principle governs the REPL surface,
  not the existence of the primitive.

The trace is thereby append-only in the same sense as the dictionary:
decisions are added, never removed. Mistake recovery is `cancel` and
start over.

## Consequences

Easier: every invariant can assume committed structure is permanent;
the address-decision log is strictly append-only and replay is exact;
no command needs to reason about partially-severed states; the code
stays small.

Harder: a misjudged expansion deep in a long trace costs a restart.
This is accepted deliberately — the cost of correct severing semantics
(ordering, cascade invalidation, audit of retractions) outweighs the
cost of retyping a trace, and the no-mistakes assumption is already
load-bearing elsewhere.

Constrained: any future undo proposal must be strictly most-recent
(temporal, one-deep) or arrive with a full severing semantics; nothing
in between.

## Links

- Related specs: `../../specs/2026-06-11-vd-degree0-return.md`,
  `../../specs/2026-06-10-vd-reduction.md` (§3 unresolve invariant)
- Related tests: `test_repl_trace.py` (flatten rejects resolved
  positions), `test_demand.py` (unresolve invariant tests)
- Related docs: `CLAUDE.md` (append-only log principle)
