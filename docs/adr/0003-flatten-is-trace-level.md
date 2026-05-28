# ADR 3: FLATTEN Is Trace-Level

- Status: Proposed
- Date: 2026-05-28

## Context

`FLATTEN` is meant to take the current node and replace open headword holes
with the strings of those headwords while preventing those strings from being
detected again as headwords later.

This is not just a text transformation. It acts on the currently active trace
node and should eventually leave history/audit evidence.

## Decision

Treat `FLATTEN` as a Trace-layer operation:

```text
trace.flatten_active()
```

It should operate on `trace.active`, leave already resolved positions alone,
and keep focus on the same active node.

## Consequences

The command can use trace context, active demand state, and future event/audit
machinery.

The opacity mechanism remains undecided. The trace-level role can be settled
before choosing backtick escaping, opaque spans, or another representation.

## Links

- `../../specs/2026-05-28-lazy-vd-language-draft.md`
- `../../specs/2026-05-28-simulator-role-cleanup-segment-1.md`

