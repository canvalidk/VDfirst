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
- `repl.py` - command loop for read-only simulator inspection commands.
- `newton.py` - Newton case study entries.
- `display.py`, `viz.py` - report rendering and graphviz output.
- `vd_demo.py` - demo entry point.
- `test_*.py` - unit tests. Treat tests as the API contract.

## Current State

- `Residual`, `Definiens`, `Tokeniser.analyse`, `VDInstance.analyse`,
  `Simulator` inspection primitives, and the phase-2 inspection REPL are
  implemented.
- Expected test result: 145 passing tests.
- Next likely work: trace bootstrap and demand graph design, or a
  phase-2.5 presentation command such as `show <headword>`.

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
2. Input loop + REPL: done for `headwords`, `count`, and `recall`.
3. Demand graph + trace state: not yet committed.
4. In-trace commands: `EXPAND`, `RECALL`, `INJECT`, `SKIP`, navigation,
   worklist/state display.

Open design questions should be surfaced before implementation:

- Does `RECALL` keep one keyword with context-sensitive behaviour inside
  and outside trace mode?
- Should demand graph resolution mutate parent `Definiens`, or store
  resolutions separately by original hole position?
- How should injected free text record provenance?
- What should multi-entry `RECALL` show when a headword has several
  entries?
- What is the default worklist ordering?

## Working Pattern

1. Start with `git status`.
2. Run tests before and after implementation.
3. Read tests before changing a module with an existing `test_*.py`.
4. Keep changes tightly scoped.
5. Add or update tests for new behavior.
