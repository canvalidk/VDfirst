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

Phase 0: documentation scaffolding and role cleanup.

Goals:

- keep spec status clear;
- keep broad design separate from small implementation segments;
- clean the roles of `ANALYSE`, `RECALL`, `EXPAND`, and `INJECT`;
- establish trace-level `FLATTEN`, first event history, and manual return;
- avoid baking unstable Theory/Newton assumptions into code too early.

Active spec:

- none accepted yet for the next segment.

Recently implemented:

- `../specs/2026-05-28-simulator-role-cleanup-segment-1.md`
- `../specs/2026-05-28-trace-flatten-events-segment.md`

North-star draft:

- `../specs/2026-05-28-lazy-vd-language-draft.md`

## Planned Segments

1. Role cleanup segment 1.
   Clarify command/function responsibilities while preserving behaviour.

2. Trace-level `FLATTEN`.
   Add a trace operation that turns open active-node headwords into inert
   literals. Initial version implemented with backtick escapes.

3. Degree-0 return.
   Add evaluator-stack behaviour so completed child demands work back up to
   the parent. Manual `return` is implemented; automatic unwind is deferred.

4. Event history.
   Record evaluator actions such as trace start, expand, recall, inject,
   flatten, return, and completion. Initial trace/expand/recall/inject/flatten
   and return version implemented.

5. Human-input audit.
   Add typed human inputs and demanded-by attribution.

6. Newton proof trace.
   Use improved Newton entries to generate a convincing trace for one selected
   mechanics problem.

## Later Product Direction

After the simulator proof of concept, the same machinery may become an
LLM-facing Newton abacus: a tool an LLM operates to solve mechanics questions
with faster structured reasoning and explicit assumption accounting.
