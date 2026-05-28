# ADR 4: Blockages Are Entry Gaps

- Status: Accepted
- Date: 2026-05-28

## Context

Early Level 2 trace sketches included blocked states. The clarification is
that blockages are not an ideal part of the design. They occur because the
underlying Newton entries are not yet good enough to let evaluation continue.

## Decision

Treat blockages as temporary symptoms of incomplete entries or incomplete
simulator machinery, not as a core trace feature.

They may still be useful during development because they reveal where the
Newton program is incomplete.

## Consequences

The simulator may expose blockage-like failures while debugging, but roadmap
work should aim to remove them by improving entries, evaluation semantics, or
human-input generation.

Documentation should avoid presenting blockage as the intended final result.

## Links

- `../../specs/2026-05-28-lazy-vd-language-draft.md`

