# Trace-derived prediction candidates

Status: implemented first segment, extended by the correction/support segment.

The evaluator records what happened. `prediction_set.py` reads those records
and produces a separate, immutable set of claim candidates. Human categories
are supplied afterwards. Neither extraction nor classification changes the
trace or the dictionary.

## Try it

From the repository root, run `python prediction_demo.py`. The example expands
`mass` and `acceleration` into their definitions, replaces each definition's
text with a value (`2 kg`, `5 m/s^2`), and replaces `{2 kg} times {5 m/s^2}`
with `10 N`. A value is never given for a bare headword: it answers the wording
of one entry.

The export contains:

| ID | Kind | Author-supplied category | Recorded pair |
|---|---|---|---|
| P0 | normalization | (unclassified) | mass times acceleration → mass times acceleration |
| P1 | entry_application | (unclassified) | mass → what the balance reads |
| P2 | meaning_preservation | parameter input | what the balance reads → 2 kg |
| P3 | entry_application | (unclassified) | acceleration → the second derivative of position |
| P4 | meaning_preservation | parameter input | the second derivative of position → 5 m/s^2 |
| P5 | meaning_preservation | correct maths | {2 kg} times {5 m/s^2} → 10 N |

In these texts a bare headword is still to be expanded, and braces stand round
one that has been dealt with. See
`specs/2026-11-15-braces-and-replacement-at-expansion.md`.

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
classify P5 correct maths
classify P2 parameter input
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

Use `Trace.expand_node`, `Trace.recall_node`, `Trace.flatten_node`,
`Trace.reduce_node`, `Trace.unreduce_node`, `Trace.inject_node`,
`Trace.clean_node`, `Trace.clean_recall` and `Trace.set_braces_node` to mutate
and record together. `Trace.inject_node` takes only a fuller call of the
demanded headword; a value goes in with `Trace.expand_node(..., replacement=...)`.
The existing low-level `Demand` methods still work, but bypass evidence recording.

```python
from prediction_set import Classification, build_prediction_set

result = build_prediction_set(trace)
labelled = build_prediction_set(
    trace, {"P5": Classification("correct maths", "Check the units too.")}
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
Since schema 6 a supplied input is always a fuller call of the demanded
headword and keeps its appropriateness wording. A value is a replacement of a
definition's text, so it is listed as a meaning preservation, in the same
equality family as arithmetic; what tells the two apart is not recorded.

The set includes recorded history, including replaced or cleared reductions.
Schema version 2 added `current_prediction_ids`, `historical_prediction_ids`,
and `dependency_selection_complete`; version 3 lists every recorded step;
version 4 adds `issued`, the results declared as answers, each with the
candidates it rested on when issued; version 5 adds `evidence.entry.clauses`,
every entry of the stem, so a definition ruled out by the form of the demand
can be told apart from one a person passed over; version 6 adds no field and
marks the change of text convention (braces round a headword dealt with).
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
