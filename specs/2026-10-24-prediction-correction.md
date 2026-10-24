# Parameterized prediction traces and correction support

Status: Implemented.

## Scope

Combine `codex/parameterized-headwords` and `codex/prediction-set-layer` in
VDfirst, and demonstrate a recorded mistake and correction. No Newton entries
or VD-Newton files are changed. The engine's parameter grammar and its
mechanical/interpretive boundary are preserved.

## Contract

1. A parameterized call instantiates before lazy tokenization, as previously
   specified. Prediction evidence preserves the resulting concrete demands
   and rendered arguments.
2. Each recorded reduction carries the transitive event indexes of the
   responses it consumed. A response to an existing overlay inherits that
   overlay's support, including the earlier reduction claim.
3. Reopening an overlay exposes its underlying expression. Its old claims
   remain in history. A fresh response to that expression has fresh support.
4. Reopening or replacing a child response clears consuming overlays on its
   ancestor chain. An unmasked source wording edit does the same. Independent
   sibling reductions remain intact.
5. Cleanup under a node's own overlay preserves that overlay. Its claim becomes
   current when the edited underlying expression is exposed. Compression is
   a display choice and retains the child's support.
6. Current support is conservative recorded response lineage. It does not
   establish semantic necessity, correctness, or a complete prediction set.
7. Legacy events without evidence and unrecorded response mutations leave an
   explicit selection gap. The projection makes no history-only assignments
   while the selection is incomplete. Low-level Demand mutation remains
   available, with recorded Trace methods the supported evidence path.
8. Schema version 2 adds `current_prediction_ids`, `historical_prediction_ids`,
   and `dependency_selection_complete`. Frozen evidence adds transitive
   `dependencies` event indexes and `dependencies_complete`. IDs retain their
   original trace-local event indexes.
9. `predictions` displays current/history/unknown support separately from
   reader classification. Every claim remains unchecked.
10. `down <pos>` navigates to an existing child, including a settled child.
    `unreduce` records the reopening. Neither command severs trace structure
    or removes historical events (ADR 5).

## Demo

`correction_demo.py` supplies an example dictionary and instantiates
`force_cart_0`. It records two inputs, an intentionally mistaken `12 N`
response and a dependent report, reopens the product, and records `10 N` and
a new report. Text output distinguishes current support from history;
`--json` exports frozen stages; `--interactive` opens the same dictionary in
the REPL. The numerical responses are scripted, not evaluated or certified.

## Verification

The combined pre-demo baseline passed 383 tests. `test_correction_demo.py`
covers concrete argument evidence, frozen earlier stages, transitive support,
replacement versus reopening, ancestor invalidation, independent siblings,
masked and compressed work, unrecorded mutations, REPL navigation/correction,
and all three demo modes. Existing evaluator and prediction tests remain the
compatibility contract.

## Deferred

Semantic checking, equality criteria and tolerances, admission/dossier reuse,
other prediction families, full disjunction assembly, trace persistence, and
the website adapter remain separate work.
