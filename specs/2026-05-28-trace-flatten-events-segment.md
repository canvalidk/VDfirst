# Trace FLATTEN And Events Segment

- Source: `2026-05-28-lazy-vd-language-draft.md`.
- Role: Implemented segment taking two small lazy-language ideas into the
  simulator.
- Status: Implemented on `codex-simulator-trace-poc`.
- Related files: `engine.py`, `demand.py`, `repl.py`,
  `test_engine_analyse.py`, `test_demand.py`, `test_repl.py`,
  `test_repl_trace.py`.

---

## 1. Purpose

This segment implements two manageable pieces from the lazy VD language draft:

- trace-level `FLATTEN`;
- a first trace event history;
- a manual `return` command for resolved active demands.

It does not implement degree-0 automatic return, typed human-input audit
records, or full evaluator stepping.

## 2. Implemented Behaviour

### Backtick Escapes

The tokeniser now treats text inside backticks as literal. Escaped text remains
in the latent output but is hidden from headword matching.

Example:

```text
analyse `mass` times force
```

renders as:

```text
mass times {force}
```

### Literal Resolutions

`Demand` now supports `LiteralResolution`. A literal resolution can be marked
`inert=True`, which means `Demand.escaped_text()` emits it with backticks so
later analysis will not re-detect it as a headword.

### Trace-Level FLATTEN

`Trace.flatten_active()` resolves every open position on the active demand as
an inert literal equal to the corresponding headword.

`Trace.flatten_active_position(pos)` resolves one open position.

The REPL exposes:

```text
flatten
flatten all
flatten N
```

Display remains normal:

```text
mass times acceleration
```

Escaped export preserves opacity:

```text
`mass` times `acceleration`
```

### Trace Events

`Trace` now records a small event list. The first events are:

- trace start;
- expand;
- recall;
- inject;
- flatten.

The REPL exposes:

```text
events
```

This is not the final human-input audit system. It is a lightweight event
history that future audit records can build on.

### Manual Return

The REPL exposes:

```text
return
```

If the active demand is resolved and has a parent, `return` moves focus to the
parent and records a return event. This is a manual foothold for evaluator-stack
unwind behaviour, not automatic lazy evaluation yet.

## 3. Test Contract

Tests cover:

- escaped headwords do not become holes;
- literal resolutions render normally and export with escapes;
- `flatten` outside trace is rejected;
- `flatten`, `flatten all`, and `flatten N` operate on the active demand;
- `flatten` leaves already resolved positions unchanged;
- flattened escaped text can be analysed without re-opening headwords;
- trace events are recorded and displayed.
- `return` moves from a resolved child to its parent and records an event.

## 4. Deferred

- official Theory meaning of `FLATTEN`;
- richer event schema;
- typed human-input audit records;
- degree-0 automatic return/unwind;
- UI decisions for whether escaped internals should ever be shown directly.
