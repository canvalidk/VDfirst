# Roadmap

This roadmap is for the Code branch. It is intentionally modest: the simulator
comes first, and the later LLM-facing Newton tool comes after the trace
architecture has proven itself.

## North Star

Build a simulator that can show VD entries behaving like a lazy program:
definitions are expanded on demand, completed subcomputations return up the
tree, and human inputs are recorded with demanded-by provenance.

The simulator is a research instrument. It may be clunky. It should be
inspectable, testable, and honest about what the code can currently do.

## Current Phase

Phase 1: simulator trace proof-of-concept hardening.

Goals:

- keep spec status clear;
- keep broad design separate from small implementation segments;
- keep the REPL aligned with committed trace semantics;
- preserve the no-severing rule for committed trace structure;
- make backward-pass actions auditable enough for research use;
- avoid baking unstable Theory/Newton assumptions into code too early.

Active spec:

- none accepted yet for the next segment.

Recently implemented:

- `../specs/2026-05-28-simulator-role-cleanup-segment-1.md`
- `../specs/2026-05-28-trace-flatten-events-segment.md`
- `../specs/2026-06-10-vd-cycle-info.md`
- `../specs/2026-06-10-vd-reduction.md`
- `../specs/2026-06-10-vd-residual-cleanup.md`
- `../specs/2026-06-11-vd-degree0-return.md`

North-star draft:

- `../specs/2026-05-28-lazy-vd-language-draft.md`

## Planned Segments

1. Human-input audit.
   Add typed human inputs and demanded-by attribution.

2. Rich trace presentation.
   Add commands such as `tree` or `show <headword>` if they become useful
   for reading settled traces.

3. Newton proof trace.
   Use improved Newton entries to generate a convincing trace for one selected
   mechanics problem.

4. Compression-on-resolve.
   Decide whether automatic compression belongs in Design 2.1, or whether the
   current explicit reduction/cleanup flow is the right boundary.

## Later Product Direction

After the simulator proof of concept, the same machinery may become an
LLM-facing Newton abacus: a tool an LLM operates to solve mechanics questions
with faster structured reasoning and explicit assumption accounting.
