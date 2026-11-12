# Workbench: flatten and issue

- Source: Can, 12 November 2026: the website's trace doer should write the better of the two VDfirst records. The engine's record was chosen over the hand-trace recorder's, because the doer drives the engine and the bridge was built for that.
- Role: fills the two gaps between the bridge protocol and what a doer needs. Extends `2026-10-24-trace-workbench.md` and `2026-11-11-record-every-step.md`.
- Status: Implemented prototype. The tests are the contract.
- Related files: `demand.py`, `prediction_set.py`, `workbench.py`, `test_workbench_record.py`, `test_prediction_set.py`
- Related ADRs: 5 (no severing).

---

## 1. Purpose

A doer on the website could expand, recall, supply an input, reduce, reopen and clean. It could not leave a headword unexpanded, although the engine and the REPL can, and it had no way to say "this is the answer". Without the second, a record has no fixed result: the result is whatever the root reads after the last command.

## 2. Scope

Production layer only, as in the 11 November segment: two more recorded steps, listed as recorded. No organizing, no testing.

## 3. Non-Goals

- Locking a trace after a result is issued, or forking a new record for a redo.
- A REPL `issue` command.
- Deciding whether an issued result still stands, is superseded, or was right.
- Input kinds, structured arguments, or choosing a definition by the form of an argument.

## 4. Current Behaviour

`flatten` exists on `Trace` for the active demand only and is not in the bridge protocol. A flattened hole is reported with `resolution: null`, which reads as open. There is no issue step.

## 5. Proposed Behaviour

1. **`flatten`** is a bridge command: `{operation: 'flatten', frame_id, position}`. One hole per command. It records the same `flatten` event and `left_unexpanded` candidate as the REPL's command. A flattened hole reports `resolution: 'flatten'` and no candidates.
2. **`issue`** is a bridge command: `{operation: 'issue', frame_id: 'F'}`. It is refused while the trace has open holes, and for any frame but the root. It records an `issue` event whose evidence holds the starting demand, the root result, and the event indexes that result rested on at that moment.
3. **Nothing is locked.** Commands recorded after an issue are allowed. A result reached by reopening and redoing is issued again and gets its own record; the earlier issue keeps what it froze.
4. **Issued results are listed apart from the candidates**, in `prediction_set.issued`. An issue asserts the result itself, which is the member a hypothesis set calls p; it is not one of the steps the result rests on, so it never appears in `predictions` or in current support.
5. **`schema_version` is 4.** Version 4 adds `issued`; everything else is as in version 3.

## 6. Data Model

- `prediction_set.IssuedResult(id, event_index, demand, result, statement, prediction_ids, dependency_selection_complete, evidence, verification)`. `id` is `I<event index>`. `prediction_ids` are the candidates the result rested on when issued. `statement` reads "The result R holds for the demand D in the recorded context."
- `PredictionSet.issued: tuple[IssuedResult, ...]`, in recorded order.
- Snapshot holes: `resolution` may be `'flatten'`.

## 7. Commands / API

- `Trace.flatten_node(node, positions, detail)`; `Trace.issue(detail)`.
- Bridge commands `flatten` and `issue`, as above. Each is one event and one snapshot, like every other command.

## 8. Test Contract

- `test_workbench_record.py`: flatten through the bridge, its hole state and its candidate; issue refused when incomplete or off the root; two issues around a redo keep separate, frozen support; an issue is not a candidate; replay validates.
- `test_prediction_set.py`: issue refused with open holes; an old-style issue event is reported; an issued result inherits gaps; `flatten_node` validates before recording.

## 9. Provisional Decisions

Prototype choices, to be thought about later. None is settled.

1. **An issue freezes and does not lock.** The 1 November ruling says a derivation as issued is fixed and a redo is a new one. Here both live in one record, told apart by their issue events. Forking a new record at the redo is the stricter reading.
2. **Issued results are a separate list, not candidates.** See §5.4.
3. **Only the root can be issued**, and only when complete. A partial or nested result cannot be an answer.
4. **`flatten` takes one hole per command** in the bridge, though the REPL can flatten several as one step.

## 10. For the website

What a client of the bridge needs to know, relative to the parked workbench branch:

- **Schema.** Accept `prediction_set.schema_version` 4. Versions 3 and 4 differ from 2 only by additions.
- **Candidate kinds.** `predictions[].kind` is one of `normalization`, `entry_application`, `entry_recall`, `left_unexpanded`, `supplied_input`, `meaning_preservation`. `prediction_set.KIND_DESCRIPTIONS` in the engine has a one-line description of each. Do not label by "supplied input, otherwise meaning preservation".
- **Entry evidence.** For the two entry kinds, `evidence.entry` holds `index`, `headword`, `definition`, `call`, `bindings`, `text`, `candidates` and `dictionary`. Other kinds have `entry: null`.
- **Every candidate id counts.** `P0` is the starting demand and is in current support from the first snapshot.
- **Hole states.** `holes[].resolution` is `expand`, `recall`, `inject`, `flatten` or `null`. Only `null` is open.
- **Commands.** `expand`, `recall`, `inject`, `flatten`, `reduce`, `reopen`, `clean`, `issue`. One event and one snapshot per command.
- **Derivations.** `prediction_set.issued` now supplies what `src/derivations.ts` reads off the export by hand: each issued result with the candidates it rested on. A redo shows as a second entry in `issued`, not as an edit of the first.
- **Events.** `events[].change` is present on every step event, including `trace`, `expand`, `recall`, `flatten`, `unreduce` and `issue`.
- **Engine fingerprint.** Records written before this change cannot be continued by this engine. Saved playback of them is unaffected.

## 11. Open Questions

- Whether the doer should also write input kinds, which the hand-trace recorder has and this record does not.
- Whether an issue should carry a tolerance, since the hypothesis-set work decides members "to within a stated precision".
- A REPL `issue` command, so the engine's own surface can do what the bridge can.
