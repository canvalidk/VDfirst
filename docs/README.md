# VD Project Documentation

This directory is for presentable project documentation: the material that
should help a new reader understand what the project is, how the Code branch is
being built, and why major design choices were made.

It is separate from:

- `specs/`: implementation-target specs and historical simulator specs.
- `codex_context/`: quick onboarding notes for Codex while working in this
  repository.
- `newton.py`: the current code copy of the Newton entries.

## Structure

- `ROADMAP.md` - current build path from simulator cleanup toward trace proof
  of concept.
- `decision-history/` - chronological question-and-answer records, including
  temporary choices that must be revisited.
- `adr/` - architecture decision records for durable design choices.
- `examples/` - golden examples and trace sketches.
- `glossary/` - living terms shared between Theory, Newton, and Code.
- `process/` - workflows for turning ideas into specs, tests, and code.

## Reader Path

For a new technical reader:

1. Read the top-level `README.md`.
2. Read `ROADMAP.md`.
3. Read `glossary/README.md`.
4. Skim `adr/`.
5. Then read the active spec listed in `../specs/STATUS.md`.

## Rule

Docs here should explain stable direction and decisions. Rough ideas belong in
`codex_context/notes/` or in a spec marked `Sketch` or `Draft`.
