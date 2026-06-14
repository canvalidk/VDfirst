# Code Architecture Notes

## Current Repository Role

This repo is the Code branch. It is intentionally code-only. Broader Theory
notes, Newton design documents, PDFs, and spreadsheets may live outside this
repository and should be routed through `references/` when they become needed
for implementation.

## Core Layers

`VDInstance` in `engine.py` is the mutable dictionary log. Entries are
append-only. Downstream graph construction, tokenisation, law/house detection,
and analysis are computed from that log.

`Residual` in `residual.py` stores literal text segments with positional holes.
It does not know about headwords.

`Definiens` in `definiens.py` pairs a `Residual` with the headwords that fill
the residual holes. This is the object produced by ordered analysis.

`Simulator` in `simulator.py` is a read-only interface over a `VDInstance`.
It provides counts, headword lists, entry lookup, and `analyse`.

`Demand` and `Trace` in `demand.py` store the trace tree. A `Demand` has an
immutable `Definiens` plus a mutable map of resolutions keyed by original hole
position.

`REPL` in `repl.py` is the current human-facing simulator loop. It owns active
trace state and mutates the `Trace`.

## Current Trace Behaviour

The trace can:

- start from arbitrary text;
- expand a hole into a child demand using a dictionary entry;
- recall a dictionary entry as literal text;
- inject user text as a child demand;
- flatten open holes into inert literal text;
- record trace events;
- surface ancestor-cycle information without blocking expansion;
- reduce settled demand nodes with a render overlay;
- clean settled residual prose without changing headword structure;
- render the active demand;
- list open holes across the tree;
- navigate with `up`, `return`, `onward`, `goto`, and `go to`.

Committed trace structure is append-only at the REPL surface. `back` was
removed under ADR 5; mistake recovery is `cancel` and restart, not severing a
committed child.

## Important Gap

Degree-0 return is implemented as parked gates rather than silent unwind:
focus stays at the deepest settled frame, `reduce` ratifies and pops one
frame, and `onward` leaves settled frames for the deepest open ancestor.
Future work is richer trace presentation and typed human-input audit records,
not automatic severing or silent multi-frame return.

## Test Contract

The tests are the current implementation contract. `CLAUDE.md` says the
expected baseline is 313 passing tests via:

```powershell
pytest test_*.py
```
