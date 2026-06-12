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
| `2026-05-28-trace-flatten-events-segment.md` | Implemented | Trace-level `FLATTEN`, backtick escapes, first event history, and manual return. |
| `2026-06-10-vd-cycle-info.md` | Implemented | Trace cycle information without blocking expansion; exact-string match key. |
| `2026-06-10-vd-reduction.md` | Implemented | Backwards-pass reduction overlays plus reduce/unreduce/fold REPL surface; resolutions in spec §13. |
| `2026-06-10-vd-residual-cleanup.md` | Implemented | Residual prose cleanup: gap-wise latent edits, tidy sweep, prompt-only offers; resolutions in spec §11. |
| `2026-06-11-vd-degree0-return.md` | Implemented | Degree-0 return: parked gates, reduce pops a frame, `onward`, `back` removed per ADR 5. |

## Next Likely Spec Segments

- Automatic degree-0 return/unwind semantics.
- Richer audit records.
- Typed human-input commands.
