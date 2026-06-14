# Trace Proof Of Concept

## Purpose

The proof of concept should show that the simulator can produce traces where
the boundary between mechanical dictionary evaluation and human contribution is
visible.

The target is not a final LLM product and not a polished human interface. The
target is a working research instrument.

## Clarified Design Principles

Blockages are not part of the ideal design. They occur when the underlying
entries are not strong enough to let evaluation continue. In the simulator,
they may be useful as temporary diagnostics, but they should be treated more
like bugs or incomplete Newton code than as desired trace objects.

Human inputs should be generated lazily. Nothing should be supplied eagerly
just because a physicist would usually know it. The simulator should ask for a
human input only when the current demand chain requires it.

Degree-0 demands return through parked gates. When a child demand is complete,
the simulator leaves focus on the settled frame so the user can reduce, clean,
return, or move onward deliberately. Text crossing a frame boundary is a
human-ratified act, not a silent unwind.

## Target Trace Capabilities

The Level 2 trace direction suggests the simulator should eventually support:

- `EVAL` style events for attempted reductions;
- `DEMAND` style events for required definitions or subexpressions;
- explicit human-input prompts at suspension points;
- typed human inputs such as recognition, modelling, empirical, and
  closure-forced inputs;
- demanded-by attribution for every human input;
- return behaviour when a demand reaches degree 0;
- final trace output that includes both the answer and an audit ledger.

## Current Minimum Next Shape

A conservative next implementation target could be:

1. Add typed human-input records with demanded-by provenance.
2. Decide how much provenance belongs inline in `state`, `events`, or a richer
   audit view.
3. Add richer trace presentation such as `tree` or `show <headword>` if needed.
4. Use Newton/Atwood documents as reference examples, but keep the next code
   target small and testable.

## Non-Goals For The Simulator

- polished UX;
- computational efficiency;
- fully general symbolic physics solving;
- replacing the Newton branch's entry design;
- encoding unrevealed Theory assumptions prematurely.
