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
- render the active demand;
- list open holes across the tree;
- navigate with `up`, `back`, `goto`, and `go to`.

The trace currently builds and renders a tree. It does not yet fully behave
like an evaluator stack.

## Important Gap

When a child demand has order 0, the data model can render it recursively, but
the REPL does not automatically work its way back up the tree and continue the
parent evaluation. Adding this return/unwind behaviour is a likely simulator
milestone.

## Test Contract

The tests are the current implementation contract. `CLAUDE.md` says the
expected baseline is 220 passing tests via:

```powershell
pytest test_*.py
```

