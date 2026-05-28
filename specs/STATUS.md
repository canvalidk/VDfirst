# Spec Status

This file tracks which specs are active, historical, or only exploratory.

## Maturity Labels

- Sketch: rough idea, useful for thinking, allowed to be wrong.
- Draft: coherent proposal, not yet committed as an implementation target.
- Accepted: agreed target for upcoming implementation.
- Implemented: code and tests exist; tests are the current contract.
- Superseded: kept for history, no longer current.

## Active Specs

| Spec | Status | Role |
|---|---|---|
| `2026-05-28-lazy-vd-language-draft.md` | Draft | North-star design for lazy evaluator/programming-language behaviour. |

## Implemented Historical Specs

| Spec | Status | Role |
|---|---|---|
| `2026-05-08-simulator-mvp.md` | Implemented | Base simulator inspection layer. |
| `2026-05-12-simulator-repl.md` | Implemented | Phase 2 inspection REPL. |
| `2026-05-12-simulator-demand.md` | Implemented | Demand graph and trace state. |
| `2026-05-12-simulator-intrace.md` | Implemented | Trace-mode REPL commands. |
| `2026-05-13-simulator-polish.md` | Mostly implemented | Polish pass; some compression automation deferred. |
| `2026-05-28-simulator-role-cleanup-segment-1.md` | Implemented | Behaviour-preserving cleanup of recall/expand/inject roles. |

## Next Likely Spec Segments

- Trace-level `FLATTEN` implementation details.
- Degree-0 return/unwind semantics.
- Event history and audit records.
- Typed human-input commands.
