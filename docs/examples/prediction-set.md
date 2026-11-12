# Trace-derived prediction candidates

Status: implemented first segment, extended by the correction/support segment.

The evaluator records what happened. `prediction_set.py` reads those records
and produces a separate, immutable set of claim candidates. Human categories
are supplied afterwards. Neither extraction nor classification changes the
trace or the dictionary.

## Try it

From the repository root, run `python prediction_demo.py`. The example supplies
`2 kg` for `mass`, supplies `5 m/s^2` for `acceleration`, and replaces
`2 kg times 5 m/s^2` with `10 N`.

The export contains:

| ID | Kind | Author-supplied category | Recorded pair |
|---|---|---|---|
| P0 | normalization | (unclassified) | mass times acceleration → {mass} times {acceleration} |
| P1 | supplied_input | parameter input | mass → 2 kg |
| P2 | supplied_input | parameter input | acceleration → 5 m/s^2 |
| P3 | meaning_preservation | correct maths | 2 kg times 5 m/s^2 → 10 N |

Every claim is **unchecked**. “Correct maths” names what the claim concerns;
it does not assert that the computation has passed a check. The same machinery
would faithfully record an incorrect answer.

Each record includes the original stimulus and response, the node's address,
local latent strings, headwords, rendered delivered arguments, entry indexes
where available, and before/after renders. Later edits cannot change this
stored evidence.

## In the REPL

After a trace has some responses, use:

```text
predictions
classify P2 correct maths
classify P1 parameter input
predictions json
```

Use the IDs actually printed for your trace. `P<n>` uses the zero-based event
index shown by `events`, so navigation can leave gaps. IDs are local to a trace.
Categories can contain spaces and are freely chosen; reclassifying replaces
the current label. Starting a new trace clears the labels.

The JSON contains the current rendered result and whether all trace holes
are resolved. Those fields describe evaluation state, not correctness.
`predictions json` prints the full JSON to the console; the demo can also be
redirected to a file as shown in the root README.

## Programmatic use

Use `Trace.reduce_node`, `Trace.unreduce_node`, `Trace.inject_node`,
`Trace.clean_node`, and `Trace.clean_recall` to mutate and record together.
The existing low-level `Demand` methods still work, but bypass evidence recording.

```python
from prediction_set import Classification, build_prediction_set

result = build_prediction_set(trace)
labelled = build_prediction_set(
    trace, {"P2": Classification("correct maths", "Check the units too.")}
)
json_text = labelled.to_json()
```

An unknown classification ID raises `ValueError`. Legacy reduction, injection
or cleanup events without structured evidence appear in `unrecorded_events`;
the extractor does not guess their source text from today's render.

## Boundary of this segment

Every step that changes what the trace says is listed: the starting demand
(`normalization`), entry applications and recalls (`entry_application`,
`entry_recall`), headwords left unexpanded (`left_unexpanded`), supplied
inputs, reductions and cleanup wording changes. An entry candidate's evidence
holds the entry as authored, the parameter bindings, the instantiated text and
every entry index that defines the call. The list is unsorted and unpruned:
organizing it and testing its members are separate layers. Cleanup
gets its own meaning-preservation claim, including when an overlay hides the
edited prose. The equality criterion remains a matter of interpretation.
Supplied inputs provisionally get an appropriateness obligation; that wording
does not settle whether injection ultimately belongs in the same equality family.

The set includes recorded history, including replaced or cleared reductions.
Schema version 2 added `current_prediction_ids`, `historical_prediction_ids`,
and `dependency_selection_complete`; version 3 lists every recorded step;
version 4 adds `issued`, the results declared as answers, each with the
candidates it rested on when issued.
These fields select recorded step lineage
for the current result; they do not decide semantic necessity or correctness.
A replacement made directly on an existing overlay consumes its earlier
claim. To correct the original calculation, first use `unreduce`.

Unrecorded response mutations, holes filled by direct `resolve_*` calls, or
legacy events leave selection incomplete;
in that case the export does not assert that other claims are history-only.
Compression retains the underlying child's support. Cleanup beneath an
overlay becomes current when that overlay is reopened.

The `coverage_complete` field is always false: the projection omits recognition,
scene-to-sheet fidelity, missing-object alternatives, and other
families needed for a full prediction-set disjunction. No red/green verdict,
automatic correctness check, or logical OR is inferred from this list.

The [correction walkthrough](correction-demo.md) demonstrates current support
and retained history with parameterized calls. Next research-facing choices
are the interpretation/checking interface and which additional families to emit.
