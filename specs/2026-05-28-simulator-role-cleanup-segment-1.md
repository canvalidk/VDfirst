# Simulator Role Cleanup Segment 1

- Source: Code-branch design discussion, 2026-05-28.
- Role: Manageable first spec for cleaning up simulator command/function
  responsibilities.
- Status: Implemented for behavior-preserving role cleanup. Trace-level
  `FLATTEN` remains a future segment.
- Related draft: `2026-05-28-lazy-vd-language-draft.md`.

---

## 1. Purpose

Earlier simulator specs separated the jobs of the simulator commands more
cleanly. Later implementation blurred some roles, especially in the REPL,
where parsing, user prompting, dictionary lookup, trace mutation, and display
often happen in the same method.

This spec defines a small first cleanup segment. It should not redesign the
whole simulator. It should make the current operations easier to reason about
before stack/return behaviour and human-input auditing are added.

The segment focuses on:

- preserving `ANALYSE` as a pure string-to-`Definiens` operation;
- clarifying `RECALL` as a composed dictionary operation that may prompt for
  multi-entry headwords;
- clarifying `EXPAND` and `INJECT` as trace operations built from smaller
  primitives;
- placing future `FLATTEN` at the `Trace` layer, operating on the active node;
- keeping the REPL as the surface adapter rather than the semantic home.

## Implementation Note

Implemented on branch `codex-simulator-trace-poc` as a behaviour-preserving
REPL refactor:

- added a `RecalledEntry` result object;
- separated entry recall from trace mutation;
- extracted focused helpers for expand, in-trace recall, and inject;
- kept user-facing command output unchanged.

`FLATTEN` was intentionally not implemented in this segment.

## 2. Non-Goals

This segment does not implement the full lazy evaluator.

Out of scope:

- automatic degree-0 return/unwind;
- typed human-input audit tables;
- automatic entry selection;
- final LLM tool behaviour;
- major changes to Newton entries;
- tokeniser opacity/escaping implementation for `FLATTEN`.

## 3. Layer Roles

### 3.1 Analysis Layer

`ANALYSE(text)` has the cleanest current role and should stay that way:

```text
string + current headword set -> Definiens
```

It should:

- identify all headwords in position order;
- preserve repeated headwords;
- use existing longest-first boundary-respecting matching;
- return an order-0 `Definiens` when no headwords match;
- avoid mutating dictionary or trace state.

It should not:

- choose entries;
- expand definitions;
- ask the user questions;
- update a demand graph;
- decide which headwords are semantically important.

Current implementation status: `VDInstance.analyse` and
`Simulator.analyse` already mostly satisfy this role.

### 3.2 Dictionary Lookup Primitives

Small primitives should remain available under `Simulator`:

```text
entry_indexes(headword) -> list[int]
entry_text(index) -> str
entry_headword(index) -> str
```

These are low-level dictionary queries. They should remain read-only and
prompt-free.

### 3.3 RECALL

`RECALL` should remain a longer semantic operation. It is allowed to compose
lower-level primitives and ask the user to choose when a headword has multiple
entries.

Conceptual intent: `RECALL` is meant to mirror how people recall information
in their own minds. The user engages with a headword, candidate entries become
available, and one relevant content is brought into the current trace. This is
why `RECALL` can remain a meaningful composed operation rather than being
reduced to a bare lookup primitive.

Clean role:

```text
RECALL(headword) -> selected entry index + selected entry text
```

It may:

- call `entry_indexes(headword)`;
- report that no entry exists;
- automatically select the only entry;
- present multiple E-number choices;
- ask the user which E-number to use;
- return both the E-number and entry text.

It should not:

- analyse the recalled text;
- attach a child demand;
- fill a trace hole by itself;
- print trace state.

This keeps `RECALL` human-usable without forcing it to be microscopic.

### 3.4 Trace Operations

Trace operations may mutate the current `Trace`.

Candidate operations:

```text
trace.start(text)
trace.expand_active(pos, recalled_entry)
trace.recall_into_active(pos, recalled_entry)
trace.inject_active(pos, text)
trace.flatten_active()
trace.flatten_active_position(pos)
```

This naming is illustrative. The important point is that trace mutation should
have a semantic home outside REPL parsing.

### 3.5 REPL

The REPL should:

- parse command text;
- ask interactive questions when needed;
- call semantic operations;
- print results and errors.

The REPL should not be the only place where simulator semantics exist.

Some user-facing commands may stay mode-sensitive. For example, `recall` can
continue to mean "show me this entry" outside trace and "fill this active
trace hole with recalled text" inside trace. Internally those should call
separate semantic operations.

## 4. Command Role Definitions

### 4.1 `analyse <text>` (Potential Diagnostic Command)

The code already has `analyse`; the REPL does not currently expose it as a
top-level command. Adding a diagnostic command is optional for this segment.

If added, it should only print the produced `Definiens`:

```text
analyse force on particle
{force} on {particle}
headwords: force, particle
order: 2
```

It must not start a trace.

### 4.2 `recall <headword>`

Outside trace:

```text
RECALL(headword)
print selected E-number and text
```

Inside trace:

```text
pos = requested position or first open position
headword = active.headword_at(pos)
entry = RECALL(headword)
trace.recall_into_active(pos, entry)
```

The same user-facing command can remain, but the internal concerns should be
separated.

### 4.3 `expand [pos]`

Clean role:

```text
pos = requested position or first open position
headword = active.headword_at(pos)
entry = RECALL(headword)
definiens = ANALYSE(entry.text)
child = Demand(definiens, provenance=ExpandProvenance(entry.index))
attach child at active[pos]
make child active
```

`EXPAND` is a trace operation composed from `RECALL` and `ANALYSE`.

### 4.4 `inject [pos]`

Clean role:

```text
pos = requested position or first open position
text = user supplied string
definiens = ANALYSE(text)
child = Demand(definiens, provenance=InjectProvenance(text))
attach child at active[pos]
make child active
```

For now, `INJECT` remains a raw string escape hatch. Later typed human-input
commands may replace some uses of it.

### 4.5 `flatten`

`FLATTEN` belongs at the `Trace` layer. It should operate on the currently
active node in the current trace.

Clean role:

```text
trace.flatten_active()
```

Initial behaviour:

- find every open position on `trace.active`;
- replace each open headword hole with an inert literal equal to that
  position's headword string;
- leave already resolved positions alone;
- keep focus on the active node;
- record an event/audit record once that machinery exists.

The opacity mechanism is deferred. The command's role can be specified before
the tokeniser escape implementation is chosen.

## 5. First Refactor Shape

This segment can be implemented without changing user-facing behaviour, except
for any explicitly added diagnostic command.

Suggested code shape:

1. Introduce a small result object for recalled entries:

   ```python
   @dataclass(frozen=True)
   class RecalledEntry:
       index: int
       headword: str
       text: str
   ```

2. Extract low-level picking helper from `REPL._pick_entry_index` into a
   clearer recall path:

   ```text
   _recall_entry(headword) -> RecalledEntry | None
   ```

   This helper can remain on `REPL` for the first cleanup because it depends on
   `input_fn` and `print_fn`.

3. Extract trace mutation helpers that receive already-decided inputs:

   ```text
   _expand_active_with_entry(pos, recalled_entry)
   _recall_active_with_entry(pos, recalled_entry)
   _inject_active_with_text(pos, text)
   ```

4. Once stable, consider moving these helpers into a separate `trace_ops.py` or
   methods on `Trace`.

This staged approach avoids a large module split before the roles are tested.

## 6. Test Contract

Behaviour-preserving tests:

- inspection `recall <headword>` still prints a single entry;
- inspection `recall <headword>` still prompts on multiple entries;
- in-trace `recall` still fills the active hole and does not move focus;
- `expand` still selects an entry, analyses it, creates a child, and moves
  focus to the child;
- `inject` still analyses user text, creates a child, and moves focus to the
  child;
- `analyse` remains non-mutating.

New tests if `flatten` is implemented in this segment:

- `flatten` outside trace is rejected;
- `flatten` on active demand resolves all currently open positions;
- `flatten` leaves already resolved positions unchanged;
- `flatten` keeps focus on the same active demand;
- `flatten` on a demand with no open positions reports a no-op.

Opacity tests should wait until the escape/opaque-string design is chosen.

## 7. Open Questions

- Should trace mutation helpers live as `Trace` methods immediately, or should
  they first live as REPL-private helpers while the shape settles?
- Should a user-facing `analyse` command be added now for debugging?
- Should `RECALL` return a structured object even outside trace, or keep the
  current print-only inspection path?
- Should `FLATTEN` default to all open positions only, or support `flatten N`
  from the start?
