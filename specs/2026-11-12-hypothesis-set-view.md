# The hypothesis set of an issued result

- Source: Can, 12 November 2026 ("Yes, build that"). First piece of the organizing layer named on 11 November: producing the set faithfully is kept apart from organizing it and from testing it.
- Role: a view over the prediction set. Reads `2026-11-11-record-every-step.md`, `2026-11-12-workbench-flatten-and-issue.md` and `2026-11-12-structured-arguments.md`.
- Status: Implemented prototype. The tests are the contract.
- Related files: `hypothesis_set.py`, `member_list_demo.py`, `test_hypothesis_set.py`
- Related ADRs: none.

---

## 1. Purpose

The prediction set lists every recorded step in the order recorded. An issued result names the steps it rested on. Nothing yet said, for one result, which of those steps are the theory, which are things a person contributed, and what the result itself claims. That sorting is what the hypothesis-set paper calls H = {p, the failures of the commitments}.

## 2. Scope

For one issued result, sort the steps it rested on into:

| Part | From | Is it a member? |
|---|---|---|
| p | the issued result's own statement | yes: it is the prediction |
| Theory side | entry applications and recalls | no; each is "according to" the dictionary |
| Commitment | a supplied input | yes: it may be wrong |
| Substitution | a reduction or a wording cleanup | yes: it may not preserve meaning |
| Reading | a headword left as plain text | yes: it may have needed its entry |
| Definition choice | an entry a person chose among several that fit | yes: it may be the wrong one |
| Question | the starting demand | listed apart |

Each theory step says how its definition came to be used: `only` (one definition exists), `forced` (the form of the demand ruled the others out) or `judged` (a person chose).

## 3. Non-Goals

- Changing or pruning the record. The view is a pure function of a `PredictionSet`.
- Deciding need. Every step the result used is listed; a step used but not needed stays.
- Member states, tests or a verdict.
- The measurement side of a trial.
- Putting the view into the workbench record or the bridge.

## 4. Current Behaviour

No such view. The hand-trace recorder has its own ledger over its own record.

## 5. Proposed Behaviour

1. `build_hypothesis_set(prediction_set, issued_id=None)` returns the view for one issued result, by default the last. It refuses when nothing has been issued or the id is unknown.
2. Only steps in the result's frozen support are sorted. Steps that are history for that result are counted, not listed.
3. A redo has its own set. The set of the earlier result still holds the mistaken substitution; the set of the later one does not.
4. A member's statement is the failure of its step: "The supplied response … is not appropriate for the demand …", "What is meant by … is not the same as what is meant by …".
5. If the result's support has gaps, the view says steps may be missing.
6. `render()` gives plain text; `to_dict()` and `to_json()` give data with counts per part.

## 6. Data Model

- `TheoryStep(id, entry_index, headword, demand, choice, statement)`.
- `Member(id, kind, statement, of)`; `id` is `not-<step id>`, `of` the step it is the failure of; `kind` in `commitment`, `substitution`, `reading`, `definition_choice`.
- `HypothesisSet(issued_id, demand, result, dictionary, prediction, theory, members, question, entries_used, steps_used, steps_in_history, record_complete, scope, limitations)`.

## 7. Commands / API

`hypothesis_set.build_hypothesis_set`; `python member_list_demo.py --hypotheses`.

## 8. Test Contract

`test_hypothesis_set.py`: the member-list scene sorts into p, 13 theory steps (3 only, 10 forced), 9 commitments and 10 substitutions; every used step lands in exactly one place; the view changes nothing in the record; a redo has its own set and the mistake stays out of it; a judged choice and a headword left as text are members; no issued result gives no set, and gaps are reported.

## 9. Provisional Decisions

Prototype choices, to be thought about later. None is settled.

1. **Entry applications are theory side and produce no member.** This follows the 5 November trace-to-set record. The paper also counts "each step was carried out correctly" among the commitments; a mechanical entry step could be given such a member.
2. **A judged definition choice is a member; a forced one is not.**
3. **The question is listed apart**, neither theory nor member, after the hand recorder's provisional treatment of normalization.
4. **A headword left as plain text is a member**, of kind `reading`.
5. **Used, not needed.** The set is an upper bound. In the member-list scene the system total would not need the spring between the blocks, and this view cannot say so.
6. **The view lives outside the record.** The website would have to call it or have it added to snapshots.

## 10. Open Questions

- Input kinds. All commitments are one kind until the engine records what a supplied input is.
- Need, by removal or countermodel, which the hand recorder checks and this view does not.
- Whether the view belongs in the bridge's snapshots.
