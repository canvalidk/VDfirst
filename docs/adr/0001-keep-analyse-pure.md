# ADR 1: Keep ANALYSE Pure

- Status: Accepted
- Date: 2026-05-28

## Context

The simulator needs commands with clean roles. `ANALYSE` is currently one of
the cleanest operations: it takes text and the current headword set, then
returns a `Definiens`.

## Decision

Keep `ANALYSE` as a pure string-to-`Definiens` operation. It should identify
headwords in position order and avoid dictionary mutation, trace mutation,
entry selection, expansion, or human prompting.

## Consequences

Higher-level commands such as `trace`, `expand`, and `inject` may call
`ANALYSE`, but they should not change what `ANALYSE` means.

This keeps the boundary between tokenisation and evaluation clear.

## Links

- `../../specs/2026-05-28-simulator-role-cleanup-segment-1.md`
- `../../test_engine_analyse.py`

