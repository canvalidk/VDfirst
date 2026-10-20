# Prediction set: recorded responses and classification

Status: Implemented.

## Scope

Implement the mechanical bridge from trace responses to inspectable prediction
candidates. Preserve the evaluator's existing behavior and its event indexes.
Do not decide semantic equivalence or input fidelity.

## Contract

1. Reduction records the exact rendered stimulus before replacement, including
   a previous overlay if it is being replaced.
2. Injection records the demanded headword and raw supplied response before
   subsequent evaluation or cleanup.
3. Cleanup records changed prose as a separate substitution. Latent cleanup
   records the underlying prose with delivered arguments, even under an overlay;
   recall cleanup records actual recalled text even when compressed.
4. Context is copied into frozen snapshots: original-hole address, latents,
   headwords, delivered argument renders and source indexes, provenance, render,
   and reduction. No snapshot holds a mutable Demand or Definiens reference.
5. Each existing event may carry structured evidence. Existing detail strings
   and event counts are preserved.
6. A pure projection emits meaning-preservation candidates for reductions and
   cleanup, and provisional supplied-input appropriateness candidates for
   injections. Old events lacking evidence are reported, not reconstructed.
7. Classification is a separate reader-supplied annotation. Categories are
   open strings; “correct maths” never changes verification from “unchecked”.
8. IDs refer to event indexes within one trace. JSON exports include evidence,
   annotations, schema version, current result, evaluation completion and limits.
9. The projection explicitly describes history and partial coverage. It does
   not treat retained historical claims as current dependencies, or produce a
   complete OR formula or theory verdict.

## Surface

- `prediction_set.build_prediction_set(trace, classifications=None)`.
- Immutable `PredictionSet`, `Prediction`, and `Classification`.
- Trace recording methods for reduction, injection and both cleanup forms.
- REPL `predictions [json]` and `classify <id> <category>`.
- Runnable `prediction_demo.py`.

## Verification

`test_prediction_set.py` covers exact stimuli, repeated reductions, immutable
context, repeated occurrences, raw injection, masked and compressed cleanup,
classification without certification, partial/legacy traces, invalid IDs,
failed operations, all REPL reduction/cleanup entry points, and annotation
reset between traces. Existing evaluator tests remain the behavior contract.

## Deferred

Full disjunction assembly, current-result dependency selection, semantic check
results and equality criteria, observation/witness fidelity, refusal dossiers,
automatic category suggestions, and trace save/restore are outside this segment.
