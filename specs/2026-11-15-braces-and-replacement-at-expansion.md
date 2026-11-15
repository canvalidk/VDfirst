# Braces in the text of a trace, and values that go in through a definition

- Source: Can, 15 November 2026 ("Yes, build it"), after a discussion the same day. His statements are quoted in §1 as typed.
- Role: changes how the text of a trace reads and how a value enters it. Extends `2026-05-28-trace-flatten-events-segment.md`, `2026-06-10-vd-reduction.md`, `2026-11-11-record-every-step.md` and `2026-11-12-structured-arguments.md`.
- Status: Implemented prototype. The tests are the contract.
- Related files: `demand.py`, `repl.py`, `workbench.py`, `prediction_set.py`, `correction_demo.py`, `member_list_demo.py`, `prediction_demo.py`, `workbench_demo.py`, `test_braces_and_replacement.py`
- Related ADRs: 5 (no severing).

---

## 1. Purpose

> if the trace process isn't done carefully, the text can get out of hand. There is 2 reasons for this. Number one, just like lambda calc, the order of expansion and reduction matters. Number 2, its unclear where 1 definition begins and another ends.

The engine kept the boundaries in its tree of demands and lost them in the text. Expanding net force inside acceleration, with nothing reduced yet, read:

```text
haze_A plus contribution_A divided by inertial-mass_A
```

A reader takes that as haze plus (contribution over mass). The engine accepted a response to that text and quoted it in the prediction set. The scripted demos avoided it only by reducing children before parents. So the two reasons are one: the order mattered because the boundary was lost.

> for every expansion, there will be 1 {} placed before the text is replaced an simply stays there as text. It wont do anything functionally.

> So only inactive headwords have braces around them. "mass" still needs expanding. "{mass}" doesn't. And if someone wants to get rid of the {} in the text, they at any time can do it.

The second problem is what a value answers. A person could type `5 m/s^2` straight at the headword `acceleration`, and the prediction set then held "the supplied response '5 m/s^2' is appropriate for the demand 'acceleration'": a claim about a name that may have several definitions. He wants the value to answer the wording of one definition, "second derivative of particle p means 5", and closed the direct route ("We close this one: 'Typing a value straight at a headword.'").

The third point is about a headword left unexpanded:

> it would be improper to do algebra with mass * acceleration. Using {mass} * {acceleration} would act like differentiating the type from the instance.

## 2. Scope

1. **The convention.** In the text of a trace:

   | Text | State |
   |---|---|
   | `net-force` | still to be expanded |
   | `{mass times acceleration}` | expanded: one pair of braces round the definition's text |
   | `{mass}` | left unexpanded on purpose |

   A brace means the headword has been dealt with, by expanding it or by choosing not to. The braces are plain text. Nothing reads them.
2. **Taking braces out.** A person may take a pair out, or put it back, at any time. It is a recorded wording edit.
3. **A value replaces a definition's text.** At expansion the person may replace the definition's text before it goes in. Headwords still in that text are recorded as left unexpanded.
4. **No value at a headword.** Supplied text at a headword must be a fuller call of that same headword. Anything else is refused.
5. **Responses may keep a headword left unexpanded.** A response to a reduction may name a headword that the replaced text shows in braces, by writing it in braces as it stood.

## 3. Non-Goals

- Forcing an order of reduction. A parent can still be reduced over children that are expanded and not reduced.
- Live instances. A `{mass}` in a response is text: it cannot be expanded later, and two mentions of it are not tied to one value.
- A way to pass a result as an argument, arithmetic in an argument, or a conditional inside a definition.
- Rewording any dictionary. The demo dictionaries are unchanged, apart from the two entries of `prediction_demo.py`.
- The VD-website Workshop. §11 lists what it must handle.
- The hypothesis-set view (draft PR 7). §10 says what it loses.

## 4. Current Behaviour

Before this segment:

- an open headword printed as `{net-force}`; an expanded one printed as its definition's text with nothing round it; a flattened one printed bare;
- `inject` took any text at an open headword, a value included;
- a reduction was accepted only on a demand with no open headwords, so a definition that still held headwords could not be replaced until each was expanded, recalled or flattened;
- the REPL offered a reduction straight after an expansion when the definition had no headwords;
- the REPL refused a response that named any headword; the bridge did not check.

## 5. Proposed Behaviour

### The text

1. A position that has not been filled prints its bare headword.
2. A position filled by an expansion, by a recall or by leaving the headword unexpanded prints in one pair of braces. When the demand inside is reduced, the braces stay round the new text.
3. A position filled by a supplied call prints without braces. The call is itself a headword still to be expanded, and it gets its braces when it is.
4. A compressed position prints its headword in braces.
5. The root's own text has no outer braces. A root that is one headword, once expanded, prints `{...}`, and so does a result issued from it.

### Taking braces out

6. `Trace.set_braces_node(node, pos, shown, detail)` hides or shows the braces of one filled position. It is recorded as a `clean` event, so the prediction set lists "what is meant by the text with the braces is the same as what is meant by the text without". A reduction that had consumed the text is reopened, as for any wording edit.
7. A position still to be expanded, a supplied call, a pair already in the asked-for state and a position out of range are refused, and nothing is recorded.
8. The engine does not read braces. A headword left unexpanded stays dealt with when its braces are out; the text then shows a bare headword that needs nothing.

### A value replaces a definition's text

9. `Trace.expand_node(..., replacement=text)` applies the entry, leaves every headword still in its text unexpanded, and replaces the text. These are three recorded steps of kinds that already exist: `expand`, `flatten`, `reduce`. With no headwords in the text there is no middle step.
10. The stimulus of the replacement is the definition's text as it then reads, for example `the acceleration of a {point-particle} as measured in an {inertial-frame}`. That is what the prediction set quotes.
11. A replacement that is empty, or that names a headword other than as in §5.14, is refused before anything is recorded.

### No value at a headword

12. `Trace.inject_node` takes the supplied text only when it is one call of the demanded headword and nothing else, different from the demand and with no fewer arguments. The list of members and the next value of a counter still go in this way. A value, prose, the demand itself and a call of another headword are refused.
13. The demos and tests that typed values at headwords now expand the headword and replace the definition's text.

### Responses

14. `split_response(sim, allowed, text)` sorts the headwords a response names into those it carries over (allowed ones written in braces exactly as they stood) and all others. `Demand.instances()` gives the allowed ones: the headwords left unexpanded that the demand's text shows in braces, or, for a reduced demand, the ones its response carried over.
15. The REPL refuses a response with any other headword, as it did before. The bridge still accepts such a response as plain text, as it did before, and now also records what was carried.

### The REPL

16. `expand` shows the definition's text and offers to replace it before it goes in. An empty answer expands as before. With a replacement the focus stays where it was, since there is nothing to do inside the replaced text.
17. The definition just offered is not offered again as an on-settle reduction. Ancestors that have become settled are still offered.
18. `set replace <on_expand|off>` switches the offer. The default is `on_expand`.
19. `unbrace <pos>` and `brace <pos>` act on a filled position of the active demand.
20. `inject` prints the refusal of §5.12. A supplied call has no prose, so it is followed by no reduce or cleanup offer.
21. The worklist prints open headwords bare.

### The bridge

22. A new command `braces` takes `position` and `shown`.
23. Each hole of a frame has `braced`: whether the text shows braces round that position.
24. There is no compound command. The bridge keeps one recorded step per command, so a client sends a replacement as `expand`, one `flatten` per headword in the text, then `reduce`.
25. `inject` is refused for anything but a fuller call, through §5.12.

## 6. Data Model

- `Demand.unbraced: set[int]`, positions whose braces a person took out.
- `Demand.reduced_instances: tuple[str, ...]`, the headwords a reduction's response carried over.
- `Demand.set_braces(pos, shown)`, `Demand.instances()`.
- `Trace.set_braces_node`, `Trace.expand_node(..., replacement=None)`, `Trace.reduce_node(..., instances=())`.
- `demand.split_response(sim, allowed, text) -> (carried, others)`.
- `PredictionSet.schema_version` is 6. No field is added. The text in `result`, in statements and in evidence follows the convention of §2, so `{x}` no longer means an open headword. `supplied_input` candidates are now always fuller calls.
- Bridge: `holes[].braced`; command `{"operation": "braces", "frame_id", "position", "shown"}`.

## 7. Commands / API

REPL: `unbrace <pos>`, `brace <pos>`, `set replace <on_expand|off>`; `expand` gains its offer; `inject` takes a fuller call only. Bridge: `braces`. No command was removed.

## 8. Test Contract

`test_braces_and_replacement.py`:

- the three states of a headword in the text; recalled text and reduced results keep their braces; the nested-definition case of §1; a supplied call has no braces;
- braces taken out and put back as recorded edits, with their statements; the four refusals; a headword left unexpanded stays dealt with when its braces are out; taking braces out reopens a consuming reduction;
- a replacement at expansion as three recorded steps, with the definition's wording in the statement; no middle step without headwords; refused replacements record nothing;
- a replacement and a later response may keep a headword in braces, and may not name it bare or name another; a reduction drops what it does not carry, and reopening restores it;
- the REPL offer, asked once, refused, switched off; `unbrace` and `brace`;
- the bridge's `braced` flag, its `braces` command, its refusals, and a value sent as `expand` then `reduce`.

Earlier test files were moved to the convention in two ways. An expectation was rewritten mechanically only where the old and the new text were identical with every brace removed. Everything else was changed by hand: tests that typed a value at a headword now use the new path or assert the refusal, and event and candidate numbers moved because a value is now two or three steps. The scripted REPL tests that predate the offer run with `replace_policy` off; one of them (`test_parameterized_repl_records_candidates_and_correction`) and the interactive demo run with it on.

## 9. Provisional Decisions

Prototype choices, to be thought about later. None is settled.

1. **Braces are drawn when the text is printed, not stored in it.** The engine knows the state of each position and prints accordingly. So a pair can be taken out per position; the braces cannot be edited as loose characters.
2. **Recalled text gets one pair of braces, and the headwords spelled inside it stay bare.** They are plain text there, not demands, so they read as "still to be expanded" although nothing can expand them. This is the one place the printed text breaks the convention.
3. **A supplied call has no braces**, because it is still to be expanded.
4. **Taking braces out is a wording edit.** It is listed as a meaning preservation and reopens reductions that consumed the text.
5. **A replacement at expansion is three existing steps, not a new kind of step.** The record and the bridge are unchanged in shape.
6. **"Fuller call" is checked by headword and number of arguments only.** `mass_cart` supplied for `mass` is taken; so is `contribution_A_1` for `contribution_A_m`. The engine does not check that the supplied call agrees with the arguments the demand already had.
7. **The starting step no longer marks the headwords it found in its text.** It used to record `find force` read as `find {force}`. Both now read `find force`; the headwords found are in `evidence.before.headwords`.
8. **The bridge stays permissive about headwords in a response**, as before. Only the REPL refuses.
9. **One offer in the REPL.** The offer at expansion takes the place of the on-settle offer for that definition, and with a replacement the focus does not move into the child.
10. **`schema_version` 6 with no new field.** The number changes because the meaning of braces in every quoted text changed.
11. **`prediction_demo.py` has new wording for its two entries** ("what the balance reads", "the second derivative of position"), so that the small example shows a value answering a definition's wording with nothing else in the way.

## 10. Open Questions

- **A definition that is one headword.** `impressed-force_A:x_p := action-force_x`, once expanded, prints `{action-force_spring:s1}` with the inner headword still to be expanded. A headword left unexpanded prints the same. The engine knows which is which; the text does not show it. The same definitions give doubled braces once the inside is worked out: `{{20 N}} plus {-123/5 N}`.
- **Definitions that name their own headword.** `mass_p := supplied mass of p` was never expanded while values were typed at `mass_cart`. Now it is, and the engine reads the word `mass` in it as a demand. A replacement records it as left unexpanded, so the statement reads "what is meant by 'supplied {mass} of cart' is the same as what is meant by '2 kg'". Whether such entries should be reworded, or the word escaped, is a question for whoever writes the dictionary.
- **Telling a value from arithmetic.** Both are now a replacement of text and are listed as `meaning_preservation`. The hypothesis-set view (draft PR 7) sorts commitments from substitutions by operation, so after this segment it would file every value as a substitution, and only supplied calls would remain commitments. "A demand with nothing filled in" is close to a tell and not exact: "the zero vector" replaced by "0 N" is such a demand and needs nothing from the scene.
- **The entry step is not among a replacement's dependencies.** A reduction of an expanded demand lists the steps inside the definition's text. The entry step belongs to the position it filled, one level up, and is in the support of the whole result. This was so before; it shows more now that a value is such a reduction.
- **Order of reduction.** Braces make it visible that a parent was reduced over unreduced children; they do not stop it. Forcing innermost-first would stop a definition with a condition in it from collapsing before its unused branch is worked out.
- **Live instances.** Whether a `{mass}` should stay expandable after algebra has been done round it, and whether two mentions should share one value. This is the same question as results used as arguments (`2026-11-12-structured-arguments.md` §10).
- **Braces and sets.** A trained reader may take `{5 N}` for a set. The braces are part of what the reader is shown.
- **`tidy`** still prints `{headword}` as the marker between the gaps it lists. That listing is of a definition's own slots, not of the text of the trace, and was left alone.

## 11. For the website

- Accept `schema_version` 6. In every `render`, statement and evidence text, `{...}` now marks a headword that has been dealt with; an open headword is bare.
- `holes[].braced` says whether the text shows braces round a position. Build the text from `latents` and `holes` as before and add the braces from this flag, or use `render`.
- New command `braces` (`position`, `shown`). It is recorded as a `clean` event.
- `inject` now takes a fuller call of the demanded headword only. A value is sent as `expand`, one `flatten` per headword in the instantiated definition, then `reduce` on the child frame. The page can offer that as one action, using `candidates[].instantiated_definition` to show the text before it goes in.
- Records made by an earlier engine stay readable and cannot be continued (the engine fingerprint changed). Their text follows the old convention.
- `tests/fixtures/workbench-*.json` need regenerating.
