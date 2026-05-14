# CLAUDE.md

Orientation for Claude working in this code repo.

## What this is

The Valid Dictionary (VD) engine is a research codebase for modelling
dictionary entries, headword-aware tokenisation, dependency graphs, and
law/house detection. Newton mechanics is the primary case study.

This repository is intentionally code-only. Broader theory notes, PDFs,
spreadsheets, and design archives live outside this repo. Treat this repo
as the implementation/test surface.

## Files

- `engine.py` - `VDInstance`, `Tokeniser`, `Entry`, dependency graph,
  three-cycle / law / house detection, structural audits, and
  `analyse(text) -> Definiens`.
- `residual.py` - `Residual` type. Positional latent strings + holes.
- `definiens.py` - `Definiens` type. `Residual` paired with parallel
  headwords. Tokeniser output and simulator-facing object.
- `simulator.py` - read-only inspection oracle over a `VDInstance`.
- `demand.py` - demand graph and trace state over immutable `Definiens`
  objects.
- `repl.py` - command loop for simulator inspection and trace commands.
- `run_repl.py` - launcher for the Newton simulator REPL.
- `newton.py` - Newton case study entries.
- `display.py`, `viz.py` - report rendering and graphviz output.
- `vd_demo.py` - demo entry point.
- `test_*.py` - unit tests. Treat tests as the API contract.

## Current State

- `Residual`, `Definiens`, `Tokeniser.analyse`, `VDInstance.analyse`,
  `Simulator` inspection primitives, demand graph state, trace
  bootstrap, and REPL trace commands are implemented.
- The REPL exposes `help`, `headwords`, `count`, `recall`, `trace`,
  `expand`, `inject`, `worklist`, `goto` / `go to`, `state`, `up`,
  `back`, and `cancel`.
- `run_repl.py` is the Newton simulator entry point.
- Expected test result: 220 passing tests.
- Next likely work: Design 2.1 interaction integration, richer trace
  presentation such as `tree` or `show <headword>`, and any automated
  compression-on-resolve UX if it is still wanted.

## Conventions

**Tests.** Run:

```powershell
pytest test_*.py
```

All tests are pure unit tests against in-process `VDInstance` objects.

**Imports.** The active test/run flow is flat-module style from the repo
root:

```python
from residual import Residual
from engine import VDInstance
```

Older presentation/demo modules may still have package-style imports.
Do not mix import styles within a module. If converting layout, convert it
deliberately across the repo.

**Mutation discipline.** `VDInstance` is mutable only through `append`,
`append_many`, and `retokenise`. Graph construction, law detection,
audits, and analyses are computed on read. `Residual`, `Definiens`, and
simulator outputs are immutable; `fill` returns new instances.

## Principles

**Append-only log.** Entries are added, never removed or edited in place.
Redefinition creates a new entry; the old one stays.

**Mechanical / residual split.** Tokenisation, graph construction, cycle
detection, law detection, degree computation, and audits do not take
human judgment as input. Human input belongs in the residual/simulator
layer.

**Wall principle.** Human inputs land at walls/peripheral entries, not at
triplets.

**Read-only simulator over engine.** `Simulator` must not mutate
`VDInstance`. Trace state belongs on the simulator side.

## Simulator Roadmap

1. Inspection primitives: done.
2. Input loop + REPL: done for inspection commands.
3. Demand graph + trace state: done in `demand.py`.
4. In-trace commands: `EXPAND`, `RECALL`, `INJECT`, navigation,
   worklist/state display, and `goto` are done. A named `SKIP` verb is
   not implemented; `goto` covers the user-level workflow for now.

Deferred design questions:

- Whether automatic compression-on-resolve belongs in Design 2.1.
- Whether a full `tree` command should display the demand graph.
- How much provenance should appear inline in `state`.
- Whether trace save/restore or multi-trace sessions are needed.

## Working Pattern

1. Start with `git status`.
2. Run tests before and after implementation.
3. Read tests before changing a module with an existing `test_*.py`.
4. Keep changes tightly scoped.
5. Add or update tests for new behavior.
