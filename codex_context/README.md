# Codex Context Shelf

This directory is the Code-branch onboarding shelf for the VD project.
It is meant to help Codex get back up to speed quickly without treating
these notes as the Theory or Newton source of truth.

The project currently has three active branches of work:

- Theory: foundational philosophy and conceptual design.
- Newton: the VD entries and domain content for Newtonian mechanics.
- Code: the simulator, engine, trace machinery, tests, and implementation
  surface in this repository.

The current Code goal is the simulator proof of concept: make traces real
enough to show lazy demand propagation, human inputs, return behaviour, and
auditability. Computational efficiency and polished UX are secondary for the
simulator.

## How To Reload Context

When returning to the project, read in this order:

1. `../README.md` and `../CLAUDE.md` for the current repo map.
2. `../docs/ROADMAP.md` for the current build path.
3. `../specs/STATUS.md` for active specs and maturity labels.
4. `GOALS.md` for the project direction as understood by Code.
5. `CODE_ARCHITECTURE.md` for the current implementation model.
6. `TRACE_POC.md` for the near-term simulator target.
7. `OPEN_QUESTIONS.md` for places where Theory/Newton guidance is needed.
8. `references/README.md` and any files added under `references/`.

## Maintenance Rule

Keep these files short and practical. If a Theory or Newton document is
authoritative, link or summarize it here instead of copying it wholesale.
When implementation changes the actual behaviour, update the relevant note.
