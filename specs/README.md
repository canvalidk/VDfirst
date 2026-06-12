# VDfirst Specs Archive

This folder stores the simulator specs used to guide implementation.
They are preserved as design/history documents, not as the sole source
of current behavior. When behavior and a spec differ, the tests and
current code are the implementation contract.

## Files

- `STATUS.md` - current maturity/status map for active and historical specs.
- `SPEC_TEMPLATE.md` - template for future specs.
- `2026-05-08-simulator-mvp.md` - base simulator inspection layer.
- `2026-05-12-simulator-repl.md` - phase 2 inspection REPL.
- `2026-05-12-simulator-demand.md` - phase 3 demand graph and trace state.
- `2026-05-12-simulator-intrace.md` - phase 4 trace-mode REPL commands.
- `2026-05-13-simulator-polish.md` - pre-handoff polish pass.
- `2026-05-28-lazy-vd-language-draft.md` - draft design for evolving
  the simulator toward lazy evaluator/programming-language behaviour.
- `2026-05-28-simulator-role-cleanup-segment-1.md` - manageable first
  cleanup spec for clarifying simulator command/function roles.
- `2026-05-28-trace-flatten-events-segment.md` - implemented segment
  adding trace-level `FLATTEN`, tokeniser escapes, and event history.
- `2026-06-10-vd-residual-cleanup.md` - draft backwards-pass residual
  prose cleanup spec for settled trace text.
- `2026-06-10-vd-reduction.md` - draft backwards-pass reduction overlay
  spec for settled demand nodes.
- `2026-06-10-vd-cycle-info.md` - draft trace cycle-information surface.
