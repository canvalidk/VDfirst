# Record every step

- Source: Can's direction of 11 November 2026: "We want the original code to save every logical step correctly. If that means we get a monster hypothesis list, that's fine." Producing the hypothesis set faithfully is to be kept apart from organizing it and from testing it.
- Role: the production layer of the prediction set. It extends `2026-10-20-prediction-set-segment.md` and `2026-10-24-prediction-correction.md`.
- Status: Implemented. The tests are the contract.
- Related files: `demand.py`, `simulator.py`, `prediction_set.py`, `repl.py`, `workbench.py`, `correction_demo.py`, `test_prediction_set.py`, `test_correction_demo.py`, `test_demand.py`, `test_workbench_record.py`
- Related ADRs: 5 (no severing).

---

## 1. Purpose

Before this segment only three operations left structured evidence: supplying an input, a reduction and a wording cleanup. Starting a trace, applying an entry, recalling an entry's text, leaving a headword unexpanded and reopening a reduction were logged as one line of text. So the prediction set could not say which entries a result rested on, which definition was chosen when several were available, or what was asked.

Every step that changes what a trace says now carries the same frozen evidence, and every such step is listed.

## 2. Scope

Three layers are kept apart. This segment is the first only.

1. **Production.** Record each step with its evidence and list it. Nothing is pruned, grouped or judged.
2. **Organization.** Views over the list: theory side against commitments, current against history, needed against used. Not in this segment, apart from the existing current/history selection.
3. **Testing.** Member states and verdicts. Not in this segment.

## 3. Non-Goals

- Deciding which candidates are members of a hypothesis set. An entry application is listed as a step of the derivation; whether it counts as theory side or as a step-correctness member is for the organizing layer.
- Splitting one recorded response into several claims. One response was given, so one record is faithful.
- Checking any candidate. Every candidate stays `unchecked`.
- The observation side of a trial, recognition, and tolerance.
- Changes to the workbench record's shape or protocol version.

## 4. Current Behaviour

See §1. `claim_support` treated a hole filled by a direct `resolve_expand`, `resolve_recall` or `resolve_literal` call as fully supported, because those operations produced no candidates.

## 5. Proposed Behaviour

1. **Starting a trace** records the text asked and how the dictionary reads it (the root render with its holes). Its event index is in the support of every later result.
2. **Applying an entry** (`Trace.expand_node`) and **recalling its text** (`Trace.recall_node`) record an `EntryUse`: the entry as authored, the demand it answered, the formal/actual pairs the call supplied, the instantiated text, and every entry index that defines the call. The methods instantiate and analyse the text themselves, so the evidence is what was inserted. An index that does not define the call is refused and nothing is recorded.
3. **Leaving headwords unexpanded** (`flatten`) records which headwords, at which positions. One command over several holes is one step.
4. **Reopening** records what was set aside and the event indexes it rested on. It asserts nothing, so it has no candidate.
5. **Event kinds, detail strings and event counts are unchanged.** Existing events gain `change`; no events are added.
6. **A hole filled without a recorded step is a gap.** Direct `resolve_*` calls, and events of the kinds above recorded with no evidence, leave `dependency_selection_complete` false. So does a trace assembled without `Trace.start`, which has no record of what was asked.
7. **The projection lists every recorded step** in recorded order, one candidate each, with ids `P<event index>` as before.

| Event | Candidate kind | Statement |
|---|---|---|
| `trace` | `normalization` | The demand ... states what is asked in the recorded context. |
| `expand` | `entry_application` | According to D, entry En defines H as ...; with p := a that gives ... for the demand ... |
| `recall` | `entry_recall` | As above, and: its text is inserted as it stands, without further expansion. |
| `flatten` | `left_unexpanded` | The headword ... is left as plain text here; no entry is applied to it. |
| `inject` | `supplied_input` | unchanged |
| `reduce`, `clean` | `meaning_preservation` | unchanged |

When several entries define the call, the entry statement ends "chosen over En, ...".

## 6. Data Model

- `demand.EntryUse(index, headword, definition, call, bindings, text, candidates, dictionary)`, frozen.
- `demand.TraceChange` gains `entry: EntryUse | None`.
- `prediction_set.STEP_KINDS` maps event kinds to candidate kinds; `KIND_DESCRIPTIONS` describes each kind.
- `PredictionSet.schema_version` is 3. The fields are those of version 2; `predictions` now holds candidates of all six kinds, and evidence may carry `entry`.

## 7. Commands / API

- `Trace.expand_node(sim, node, pos, index, detail)`, `Trace.recall_node(sim, node, pos, index, detail, compressed=False)`.
- `Simulator.entry_use(index, call)`.
- `Trace.start`, `Trace.flatten_active`, `Trace.flatten_active_position` and `Trace.unreduce_node` keep their signatures and now record evidence.
- The REPL's `expand` and `recall`, and the workbench's `expand` and `recall` commands, go through the recorded methods. No command changes.

## 8. Test Contract

- `test_prediction_set.py`: every step kind listed once in recorded order; a choice among several definitions on record; multi-hole flatten as one step; refusals record nothing; reopening keeps evidence and adds no candidate; old-style events of every kind are reported and never reconstructed; a trace without a recorded question is incomplete; the REPL's expand, recall and flatten reach the list.
- `test_correction_demo.py`: the question and the entry application in the demo, with bindings and statement; holes filled without a recorded step leave a gap; the earlier support tests, renumbered for the recorded entry steps.
- `test_demand.py`: evidence on start and flatten events, with details and counts unchanged.
- `test_workbench_record.py`: entry evidence and reopening evidence in saved records; replay still validates.

## 9. Provisional Decisions

This is a prototype. Can accepted the five choices below on 11 November 2026 as good enough for now, and asked that they be marked for later thought. None is settled.

1. **One list.** Entry applications and the starting demand sit in the same list as inputs and reductions, told apart by kind. The alternative is a second list for the theory side, since the 5 November trace-to-set record says an entry application "contributes no member".
2. **Reopening is recorded but not listed.** It withdraws a response and asserts nothing. If it carries a claim, such as "the earlier response was a mistake", it should get a candidate.
3. **The wording of the four new statements** (§5). The normalization statement is the weakest: the engine sees the demand, not the wording it came from.
4. **A choice among several definitions is folded into the entry step** ("chosen over En"). Applying an entry is mechanical; choosing it is a person's judgement, and it is the selection function the December notes left open. In a law-house every law headword has two definitions, so the choice will arise on most steps of a Newton trace. It may deserve its own candidate.
5. **A hole filled without a recorded step counts as a gap.** This is the only change that makes earlier behaviour stricter.

## 10. Open Questions

- **Kinds as an organizing vocabulary.** The hand-trace recorder sorts INPUTs into nine kinds. `supplied_input` here is still one kind.
- **Normalization.** The engine sees the starting demand, not the wording it normalizes. The workbench record holds the wording as `question.context`; the trace does not.
- **Entry choice as its own candidate.** The choice among several definitions is inside the entry candidate's evidence and statement. It may deserve a separate candidate.
- **Website.** The VD-website workbench branch accepts schema version 2 only and labels every candidate as a supplied input or a meaning preservation. It needs an update before it can read records from this engine.
