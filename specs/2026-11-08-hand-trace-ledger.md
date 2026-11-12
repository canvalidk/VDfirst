# Hand-trace recorder and ledger

- Source: Can's request of 8 November 2026 for "a program that might help make traces easier to produce and track step by step as the code would do but without entries".
- Role: a recorder for traces worked by hand while the entries are unfinished. The dictionary is cited, never executed.
- Status: Implemented (v2.4: checked statuses added to v2.3, which followed seven adversarial review rounds). The tests are the contract.
- Related files:
  - `handtrace.py`
  - `test_handtrace.py`, `test_handtrace_regressions.py`, `test_handtrace_probes.py`, `test_handtrace_v2_review.py`,
    `test_handtrace_v21_review.py`, `test_handtrace_v22_review.py`, `test_handtrace_v23_review.py`,
    `test_handtrace_countermodels.py`
  - `handtrace_example_spring_single.py`, `handtrace_example_spring_two.py`, `handtrace_example_atwood.py`
    (with `handtrace_example_atwood_statuses.py`), `handtrace_example_atwood_cc.py`,
    `handtrace_example_atwood_compare.py`
- Related ADRs: none. The module is independent of `engine.py`, `demand.py` and the workbench record.

---

## 1. Purpose

Hand traces such as the spring and Atwood traces of 8 November are written in prose. Each one needed adversarial review to catch bookkeeping errors:

- bindings imported by reference;
- arithmetic substitutions left unrecorded;
- adding the two block relations instead of subtracting them on a single upward axis;
- ideal model relations labelled as contracts;
- NEEDS statuses with no countermodel;
- unused premises counted as members.

Those errors are mechanical. A recorder can refuse them while the trace is written, and can produce the ledger and the prediction side of the hypothesis set from the record.

## 2. Scope

- **Frames and steps.** A trace is a tree of demand frames plus an ordered list of steps. The labels are those of the 8 November synthesis (§13): ENTRY, INPUT, CONTRACT, DERIVE and OPEN, with EXTERNAL (S§3.3) and READING (an interpretation of the entries that no entry or cited source states). DEMAND, DELIVER, WITHDRAW and ANSWER are structural.
- **ENTRY steps quote their entry string.** If the trace is given the entries, for example via `load_entries` on `DESIGN_2_1_DRAFT_1_ENTRIES.md`, every quote is verified:
  - verbatim, ignoring whitespace;
  - at least two whole words, matched at word boundaries (an apostrophe, a hyphen or a combining accent does not count as a boundary);
  - for a combined ref such as `K16 / E1`, in every part.

  A demand can cite the entry that exposed it (`demand(..., ref=, quote=)`).
- **INPUT kinds:**
  - recognition;
  - model, which covers supplied ideal model relations;
  - value;
  - completeness;
  - identity;
  - convention;
  - normalization (a reading of the question's wording);
  - choice;
  - haze.

  Kinds can be combined with `/`.
- **Bindings** are exact values, addressed unknowns, named facts, and named relations. Unknown addresses must be distinct; they are compared without whitespace.
- **No hidden lookup (S§3.3, S§12.1).** A name or value is visible where it was bound, and in every frame above that, because results flow up to callers. It reaches any other frame only by DELIVER:
  - A delivery passes the binding from the caller (the frame's parent) to the frame it calls, and is visible there and below.
  - The caller must see the name, and the value travels only if the caller sees the value too.
  - The original qualifications are copied in automatically.
  - `deliver_many` delivers several names, all or nothing. `deliver_through` makes one delivery from the nearest frame that sees the name.

  A name used without being visible is refused. So is a value hidden behind a visible name, but only when that value would change the kind of verdict the step gets (checked, unchecked, found mistake or conflict).
- **Registration does not depend on order.** A step that registers a relation, an input, an unknown or a reading depends on the names it mentions, not on the values those names have when it is registered. Steps that substitute values (DERIVE, the values of a solve, consistency checks, answers, deliveries that carry a value) depend on the steps behind those values. So a relation's provenance does not change if it is written before or after a value it mentions is fixed.
- **Arithmetic.** Claims and relations are written with numbers, names, `+ - * /` and `**`. Anything else (`%`, `//`, `^`, function calls) is refused when it is written, so it never enters a record. Integer powers are exact. A fractional power is exact when its root is rational, so `(2*g*h)**0.5` with `2*g*h = 100` is 10. An irrational power, like any other nonlinear expression, leaves the step unchecked. Division by zero and an even root of a negative number are undefined: a claim that is undefined at the visible values is a found mistake, and a cited relation that is undefined there is a conflict. Undefined wins over nonlinear whatever the order of operands or relations, and a product with a zero factor is zero, so `1/(m*a*(t - 3))` at t = 3 is undefined. Exact numbers are kept below about 13,000 bits (3,900 digits), so every accepted value can be rendered and saved; a larger number leaves the step unchecked, and a larger supplied value is refused.
- **Exact checks on every DERIVE.** A claim with no cited relations must be an identity once the visible values are substituted. A claim with cited relations must be a linear consequence of them.
  - **Contradictions are conflicts.** If the cited relations contradict each other or the visible values, the step is recorded as a conflict, not a pass.
  - **No vacuous passes.** A claim that is zero after substitution is reported as having no independent content.
  - **Minimal provenance.** Only the cited relations the claim actually needs are recorded as its provenance.
  - **Strict and lenient modes.** In strict mode (the default), a failed or uncheckable step raises an error. In lenient mode it is recorded, and a failure is a found mistake.
- **Linear solve.** An EXTERNAL linear solve fixes every unknown the relations determine.
  - It reports a unique solution, a family (with its rank and free unknowns), or an inconsistency. An inconsistency is a conflict.
  - Each fixed value gets its own checked DERIVE step. That step's provenance is a smallest set of relations fixing that value, so an answer naming x rests only on x's relations. The report step names what it fixed; when its values feed an answer it is not listed as a step outside that answer.
  - `consistency()` records a deliberate consistency check, which never raises.
- **Answers.** A trace can have several answers. Steps recorded after an answer cannot feed it; they are consequences.
- **Withdrawal.** `withdraw` withdraws a premise. Earlier steps remain as history.
  - The premise cannot be used or delivered again. Neither can any binding registered from it.
  - Any value resting on it becomes visible nowhere. The quantity's name stays usable, and the quantity can be determined again.
  - A step whose verdict would be different with the withdrawn value is refused, naming the withdrawn premise. It is not recorded as a found mistake, because the tracer made no slip. Determining that quantity again is exempt. The value checked is the one the step's frame last saw, so a value determined again elsewhere and not delivered does not hide the withdrawal; the refusal then says where the new value is. A solve or consistency check that only the withdrawn value would make checkable is refused the same way.
  - A declared address whose declaration rests on the withdrawn premise is released, so a new unknown may take it.
  - Answers recorded earlier keep their history.
- **Ledger.** Each answer has a ledger built from its provenance cone: every step it depends on. The ledger sorts the trace into these sections:
  - theory side (ENTRY, CONTRACT and READING steps that feed the answer);
  - world commitments, which are the members;
  - pruned premises: status ENTAILED or USES, or only non-world kinds. The non-world kinds are convention, choice and, provisionally (decided 10 November 2026), normalization: a normalization fixes what is asked, not how the world is;
  - step members (DERIVE and EXTERNAL steps that feed the answer);
  - inputs that do not feed the answer;
  - other steps that do not feed the answer;
  - open items;
  - found mistakes (failed arithmetic);
  - conflicts between premises. These include a global check, made when the ledger is built. For each quantity it uses the last value fixed before the answer that rests on no premise withdrawn before the answer, so determining a value again later does not change an earlier answer's ledger. It flags any relation the answer rests on that the values contradict or make undefined. It then checks the remaining relations together; if they are jointly inconsistent, it names a minimal inconsistent subset: each relation in it is needed for the contradiction, though a smaller inconsistent subset may exist elsewhere;
  - unchecked steps;
  - solves that were not unique;
  - withdrawn premises;
  - undetermined unknowns, including those whose value was withdrawn. The note reads the value as of the answer: withdrawn before it (naming the premise withdrawn first), the answer's own value withdrawn after it, or a value determined only after the answer;
  - warnings (missing statuses, answers resting on a failed step or a withdrawn premise, premises supplied twice word for word, NEEDS on a premise that does not feed the answer).
- **Checked statuses.** `annotate(..., answer=, check=)` checks a status mechanically against one answer. The answer is rebuilt from its premise relations (bound by INPUT, ENTRY, CONTRACT, READING or EXTERNAL; relations registered by DERIVE are consequences and are recomputed) and its supplied values, and the rebuilt system must reproduce the answer.
  - For NEEDS, REQUIRED and USES the check is a countermodel: a premise relation or value replaced, relations or values removed, equations added (new names are new quantities), or, for a precondition, everything resting on the premise dropped. It is solved exactly to a fixpoint and reported as *refutes p*, *p does not follow*, *p still follows* or *inconsistent*. NEEDS and REQUIRED need the first two; USES needs the third.
  - For ENTAILED the check is that the premise's relation or value follows from named other premises. A relation produced from the premise (registered with it in its `uses=`, directly or through other relations) does not count, so the argument cannot be circular; merely mentioning a supplied value does not make a relation rest on it here. When nonlinear relations might settle the question, the verdict is *cannot check*.
  - Each check also says whether the countermodel falsifies the premise, and lists any changed relation that does not rest on the premise: a countermodel must keep every other premise. The ledger shows the result beside the countermodel and warns when it does not support the status.
- **Hypothesis set.** It is the prediction side of the sort in `hypothesis_sets_from_traces`: `{p}` + one negated member commitment per answer-feeding INPUT + one "this step went wrong" member per answer-feeding DERIVE or EXTERNAL step.
- **Output.**
  - Markdown.
  - A JSON record that stores every command with all of its arguments, plus the entries, steps, values and per-answer ledgers, under a SHA-256 digest.
  - Exact replay.
  - A command-line interface: `python handtrace.py validate|render RECORD.json`.

## 3. Non-Goals

- Executing entries, or tokenising definitions.
- Checking recognition, meaning or physics. Statuses are supplied by the tracer. A countermodel's arithmetic is checked when it is given as a check; whether it describes a possible world is the tracer's claim.
- Nonlinear algebra and inequalities. They are recorded as text or as unchecked steps.
- Units checking. Units are carried as text.
- Deciding need. The provenance cone is an upper bound on the needed premises (C1 of the 5 November record). Statuses refine it.
- The observation side of a trial (C2). Every hypothesis set produced is labelled "prediction side only".

## 4. Current Behaviour

Before this module, hand traces lived only as Markdown documents. The engine's prediction-set layer covers engine-driven traces, recording supplied inputs and meaning-preservation claims.

## 5. Proposed Behaviour

See §2. The tests define the details. The worked examples encode the three hand traces of 8 November:

- the spring with one object;
- the spring with two objects, which uses multiple answers, a conflict and a withdrawal;
- the reconciled Atwood trace, with its entries verified.

## 6. Data Model

- `Frame(id, parent, text, step)`.
- `Step(index, frame, op, text, ref, kind, uses, binds, claim, check, detail, deps, tag)`. Here `deps` holds the steps that made each used name or value visible. An answer's cone is the transitive closure of `deps`.
- `Binding(name, sort, frame, step, text, unit, address, equation, withdrawn)`, where `sort` is `value`, `unknown`, `fact` or `relation`.
- The record:

  ```json
  {format: "vd-hand-trace", version: 1, question, edition, entries, strict,
   commands, steps, values, ledgers, sha256}
  ```

  `sha256` hashes every other field as sorted-key, compact, non-ASCII-escaped UTF-8 JSON.

## 7. Commands / API

`Trace(question, edition=None, *, strict=True, entries=None)` has the following methods.

**Building the trace**

- `demand(parent, frame, text, ref=)`
- `entry(frame, ref, quote, text=, uses=, binds=, relation=)`
- `input(frame, name, kind, text, value=|relation=, unit=, uses=)`
- `contract(frame, ref, text, source=, uses=, binds=, relation=)`
- `reading(frame, text, uses=, binds=, relation=)`
- `open(frame, text, uses=)`
- `unknown(frame, name, text, address=, label=, ref=, quote=, unit=, uses=)`
- `deliver(frame, name, text=)`, `deliver_many(frame, names)`, `deliver_through(frame, name)`
- `withdraw(frame, name, text)`

**Checking and solving**

- `derive(frame, claim, from_relations=, binds=, name=, tag=, text=, uses=)`
- `solve(frame, relations, unknowns, tag=, text=, uses=)`, `consistency(frame, relations, text=, tag=, uses=)`
- `external(frame, competence, text, uses=, relation=, binds=, tag=)`

**Answers and analysis**

- `answer(names, text=, label=)`
- `annotate(name, status, countermodel=, note=, answer=, check=)`, where `answer=` scopes a status to one answer and `check=` checks it
- `check_countermodel(premise, answer=, replace=, remove=, add=, values=, drop_dependents=)`, `check_entailed(premise, answer=, by=)`
- `cone(answer=)`, `ledger(answer=)`, `hypothesis_set(answer=)`

**Output**

- `to_markdown()`, `to_record()`, `to_json()`
- `Trace.replay(record)`
- `load_entries(path)`

## 8. Test Contract

`test_handtrace.py` covers:

- exact parsing, entailment and solving;
- the Atwood solve and its four-unknown pending state;
- hidden-lookup refusal and delivery;
- the visibility of values as distinct from names;
- strict and lenient failures, including the add-versus-subtract slip;
- the rules for determined values;
- distinct addresses;
- the enforcement of kinds and labels;
- ledger sorting, unused inputs and statuses;
- the hypothesis set;
- replay, the digest and the command line.

The other test files work as follows:

- `test_handtrace_regressions.py` reintroduces the errors the reviews found.
- `test_handtrace_probes.py`, `test_handtrace_v2_review.py`, `test_handtrace_v21_review.py`, `test_handtrace_v22_review.py` and `test_handtrace_v23_review.py` hold adversarial edge cases written by independent reviewers in successive rounds. Any genuine open bug there is `xfail(strict=True)` with its reason; a fixed bug's test runs as an ordinary test.

## 9. Open Questions

- **Explicit RETURN.** Results currently flow up to every caller without a step. The theory review pointed out that S§3.2 has a sub-demand return its answer. Requiring a RETURN step would be more faithful but more verbose. It would not by itself have caught the case behind the objection: "the same g at both blocks" is a premise the tracer has to state.
- **Conditional branches and case splits.** The two-object spring trace keeps internal and external candidates open, and the synthesis's Trace 5 does the same. Branch-local premises need a scope that is discharged when the branches rejoin (S§12.3).
- **The observation side (C2).** A second derivation, from the scene to the observed value, with its own members.
- **The shared approximation budget (C3).** Model INPUTs could carry tolerance shares, checked against a declared ε. This would need inequalities and interval arithmetic.
- **The entry cut and editions (C5, C7).** Which results carry over when an edition changes which premises are entries.
- **Structured addresses.** An address made of interaction, source, target, frame and instant would let the activation and value locks (S§9.2–9.3) be checked rather than asserted.
- **Units.** Dimension checking.
- **Countermodels beyond linear algebra.** A countermodel is checked only when it can be stated as changed equations over the recorded quantities. Countermodels for premises with no relation (recognition, completeness) are checked through the relations they license, which the tracer names.
- **Export.** Records could be exported to the engine's prediction-set schema or to the workbench record, so the website can show hand traces.
- **Statuses.** Whether the hypothesis-set paper should adopt REQUIRED and ENTAILED.
- **Irrational values.** A power with an irrational result is unchecked. Checking it would need exact algebraic numbers or an interval check against a stated tolerance, which belongs with C3.
- **Minimal citations beyond 8.** A smallest set of citations is found exhaustively up to 8 cited relations, preferring those cited first. Beyond that a greedy pass finds an irreducible set, but not necessarily the smallest one.
- **Demand links.** A DEMAND step links to the entry that exposed it, but values found inside the frame do not depend on the DEMAND step. So the exposing entry appears in an answer's theory side only if some step cites it.
