# VD Lazy Programming Language Draft

- Source: Code-branch design discussion, 2026-05-28.
- Role: Draft spec for evolving the simulator toward a lazy VD
  programming-language proof of concept.
- Status: Draft. Not yet an implementation contract.
- Related files: `engine.py`, `residual.py`, `definiens.py`, `demand.py`,
  `simulator.py`, `repl.py`, `newton.py`.

---

## 1. Purpose

The simulator should evolve from a trace-tree inspector into a minimal lazy
evaluator for VD entries. The goal is not speed, polish, or a final
LLM-facing product. The goal is to prove that VD entries can behave like a
program: demanded definitions expand, degree-0 values return, and human inputs
are requested only when the current evaluation genuinely needs them.

This draft focuses on the Code branch. It is intentionally conservative about
Theory and Newton commitments that have not yet been handed over.

## 2. Current Behaviour

The current simulator can:

- analyse text into a `Definiens`;
- start a trace from text;
- expand a hole into a child demand;
- recall a dictionary entry as literal text;
- inject user text as a child demand;
- show the active demand;
- list open holes across the tree;
- navigate by `up`, `back`, `goto`, and `go to`.

This is enough to build a demand tree. It is not yet enough to behave like a
lazy evaluator.

The missing piece is stack semantics. When a child demand reaches degree 0,
the simulator should treat it as a returned value and work back up the tree,
continuing the parent evaluation.

## 3. Design Commitments

### 3.1 Blockages Are Not The Ideal

Blockages are not a core feature of the final design. They occur when the
current Newton entries are not yet good enough to continue evaluation.

During simulator development, a blockage can be useful because it exposes a
gap in the entries. But conceptually it should be treated like an incomplete
program or a bug in the Newton branch, not like a desired trace endpoint.

### 3.2 Lazy Demand

Human inputs must be generated lazily. The simulator should not ask for data,
recognition, modelling choices, or constraints merely because a physicist
would usually know them. It should ask only when the current evaluation path
demands them.

### 3.3 Return On Degree 0

A demand with degree 0 is complete. Once active evaluation reaches a degree-0
demand, the evaluator should return that value to the parent demand.

This makes the trace behave more like lazy functional evaluation:

1. Evaluate a demanded expression.
2. If it contains demanded headwords, expand the next demanded headword.
3. If the child has demands, descend.
4. If the child reaches degree 0, return its value.
5. Substitute the returned value into the parent.
6. Continue until the root reaches degree 0.

The existing `Demand.text()` can render recursively through child
resolutions, but the REPL does not yet perform this active return/unwind
control flow.

## 4. Evaluation Terms

These names are for simulator design. They need not become class names exactly.

### Expression

A `Definiens` currently plays the role of an expression: literal text plus
ordered headword holes.

### Demand

A `Demand` is an expression together with the choices already made for its
original holes. It is the natural evaluation frame.

### Value

A value is an order-0 `Definiens` or another explicitly terminal object. It
can be returned to a parent demand.

### Evaluation Stack

The active path from root to the currently evaluated demand is the evaluation
stack. The current implementation stores this as parent pointers in a tree, but
does not yet drive evaluation as a stack.

### Human Input

A human input is a typed contribution requested by the evaluator because the
entries cannot mechanically supply the needed value or judgment at that point.
The trace should record its kind, content, and demanded-by provenance.

## 5. Proposed Evaluator Loop

The simulator should eventually support a control loop equivalent to:

```text
while root is not complete:
  active = current frame

  if active has an open demanded headword:
    evaluate or request a choice for that headword
    continue

  if active is degree 0:
    return active to parent
    continue

  if active requires a human input:
    ask for typed human input
    record audit event
    continue
```

The exact scheduling policy can remain simple. For the proof of concept, use
left-to-right demand order unless a command explicitly chooses another
position.

## 6. Return Semantics

When a child demand is complete:

1. The child produces a terminal rendering.
2. The parent position that spawned the child is considered resolved.
3. Evaluation focus moves back to the parent.
4. The parent continues with its next open demanded position.

Open question: should the simulator automatically continue after returning, or
should it return one frame and wait for the next REPL command? For the research
simulator, a single-step mode may be useful:

- `step`: perform one evaluator action.
- `run`: continue until completion, human input, or error.

This would keep the mechanics inspectable while still allowing full execution.

## 7. Human Input Audit

The Level 2 trace direction requires human inputs to be first-class audit
records, not merely injected text.

Candidate audit fields:

- id: stable event number in the trace;
- kind: recognition, modelling, empirical, closure-forced, or another Theory
  branch category;
- prompt: the question the evaluator asked;
- response: what the human supplied;
- demanded_by: entry number, chain, diagnostic, or evaluation frame that made
  the input necessary;
- target: expression, headword, position, or object being resolved;
- result: value or judgment added back into evaluation.

This can initially coexist with `inject`. In the long run, typed human input
commands may replace many uses of raw `inject`.

## 8. FLATTEN

### 8.1 Motivation

Sometimes evaluation should stop expanding the headwords in the current node
and treat them as literal strings. The proposed command is:

```text
flatten
```

`FLATTEN` takes the active node and replaces every open headword hole at that
node with the string of that headword. The replacement must be inert: if the
resulting text is analysed later, those inserted strings must not be detected
as headwords again.

In other words, `FLATTEN` turns open headword demands into escaped literals.

### 8.2 User-Level Behaviour

Given an active demand rendering:

```text
{mass} times {acceleration}
open positions: 0, 1
```

Running:

```text
flatten
```

should produce a degree-0 local value equivalent to:

```text
mass times acceleration
open positions: none
```

But the inserted `mass` and `acceleration` must be opaque to later headword
analysis.

### 8.3 Scope

`FLATTEN` acts on the active demand's open positions.

It should not:

- recursively flatten child demands;
- erase existing child provenance;
- change already resolved positions except through normal rendering;
- delete audit history.

If the active demand has no open positions, `flatten` is a no-op or a status
message: `no open holes to flatten`.

### 8.4 Data Semantics

In current terms, flattening a demand means resolving every open position with
an inert literal equal to `demand.headword_at(pos)`.

This suggests a new resolution type:

```python
@dataclass(frozen=True)
class FlattenResolution:
    text: str
```

or a more general literal resolution:

```python
@dataclass(frozen=True)
class LiteralResolution:
    text: str
    inert: bool = False
    source: str = "flatten"
```

The second form may be more useful if other simulator commands also need
literal terminal values.

### 8.5 Opacity Requirement

The hard part is not replacing the text. The hard part is making the inserted
headword text non-detectable in later analysis.

Current code has a tokeniser comment mentioning a future backtick escaping
mechanism, but escaping is not enforced. `FLATTEN` should therefore not rely on
an escaping feature until that feature exists.

Possible implementations:

1. Tokeniser escape syntax.
   Add an official escape form, such as backticks, and make `Tokeniser.analyse`
   ignore headwords inside escaped spans.

2. Opaque text segments.
   Extend `Residual` or `Definiens` so latent text can carry opacity metadata.
   Analysis would preserve opaque spans instead of treating everything as a
   plain string.

3. Render-only escaping.
   Store a private sentinel around flattened terms internally, strip or style
   it for display, and teach analysis to ignore sentinel spans.

For the proof of concept, option 1 is probably simplest if Theory accepts a
surface escape syntax. Option 2 is cleaner but deeper.

### 8.6 Display

Flattened literals should display as normal text. The user should not have to
see escape markers unless explicitly inspecting raw trace internals.

Example display:

```text
mass times acceleration
open positions: none
```

Possible debug display:

```text
`mass` times `acceleration`
```

or:

```text
[flat:mass] times [flat:acceleration]
```

### 8.7 Audit

`FLATTEN` is a human/evaluator choice and should be auditable.

Candidate audit record:

```text
kind: flatten
target: active demand E2
positions: 0, 1
response: mass, acceleration treated as inert literals
demanded_by: user command / evaluator simplification
```

Open question: should flatten be classified as a human input, a control-flow
command, or a definitional/evaluation operation? It has consequences for
meaning, so it should at least appear in trace history.

## 9. Command Sketch

Near-term simulator commands could include:

```text
step                  perform one evaluator action
run                   evaluate until complete or waiting for input
flatten [pos|all]     make open headword(s) in active demand inert literals
return                manually return a complete active demand to parent
audit                 show human/evaluator inputs
events                show evaluator events
```

For the first implementation, `flatten` without arguments can mean all open
positions on the active demand. A positional form can be added once the broad
semantics are stable:

```text
flatten 0
flatten all
```

## 10. Test Contract Draft

Potential tests once implementation begins:

- flatten outside trace is rejected;
- flatten on an active demand with two open holes resolves both;
- flattened demand has no open positions;
- flattened terms render as normal text;
- flattened terms do not become headword holes if the text is analysed again;
- flatten records a trace event or audit record;
- flatten does not affect already resolved child demands;
- a degree-0 child returns to its parent;
- after returning, evaluation continues to the next open position;
- root completion prints or exposes the final value.

## 11. Deferred Questions

- What is the official Theory meaning of flattening?
- Is flatten a human modelling choice, a syntactic escape, or an evaluator
  control operation?
- Should opacity be visible in saved traces?
- Should escaped spans survive export to final academic trace reports?
- Should the evaluator support both manual stepping and automatic running from
  the beginning?
- How should multiple entries for a headword be selected in automatic run mode?
- How much of this belongs in the simulator versus the future LLM-facing
  Newton abacus?

