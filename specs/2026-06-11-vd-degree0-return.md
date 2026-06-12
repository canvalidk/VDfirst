# VD Simulator — Degree-0 Return (Parked Gates and `onward`)

- Source: design session 2026-06-11 (chat); successor to the
  "automatic degree-0 return" roadmap item.
- Role: evaluator-stack semantics for the backwards pass — what
  happens when a frame reaches degree 0.
- Status: Implemented (2026-06-11)
- Related files: `demand.py`, `repl.py`, `test_demand.py`,
  `test_repl_trace.py`, `test_repl.py`
- Related ADRs: `../docs/adr/0005-no-severing.md`

---

## 1. Purpose

The render recursion already returns *values* up the tree
automatically: parents render via `child.text()`. Control, however,
stays parked wherever the user last acted, and the original roadmap
sketch ("automatic unwind") would have popped focus silently. That
design was wrong by the project's own split: the pop carries *text*
across a frame boundary, and text crossing a boundary is residual
territory. An unevaluated "5*7 + 3" escaping its frame unreduced
compounds into grammar mess at every level above.

So degree-0 return is **prompted, not silent**. What is automatic is
the *initiation*: when a frame hits degree 0, the simulator leaves the
user standing on it — the parked focus *is* the gate. What is never
automatic is the passage: the human ratifies the returned form
(reduce), tidies it (clean), or moves on. Sending text up through a
frame boundary is a human act.

## 2. Scope

- The parked-gate protocol (mostly codifying current behaviour).
- `reduce` pops one frame on success.
- A new routing verb `onward`.
- `Demand.degree` as a counting property.
- Removal of `back` (per ADR 5).

## 3. Non-Goals

- No silent multi-frame auto-pop. Frame passage is human-paced.
- No `down` command; no navigation into resolved subtrees.
- No undo of any kind (ADR 5).
- No change to the on-settle offer machinery or its defaults; offers
  remain policy-gated sugar over the same gate moments. Whether
  accepted offers should also move focus is left to use (§9).
- No hint line printed on settle; parked focus plus `state` carries
  the information.

## 4. Current Behaviour

- After a resolution, focus already parks at the deepest affected
  frame: recall and flatten leave focus on the acted-on node; expand
  and inject move focus into the new child. A settled node holds
  focus until the user types `return`, `up`, or `goto`.
- `return` moves to the parent iff the active node is resolved, and
  records an event.
- `back` unresolves the active child — out-of-order severing,
  removed by ADR 5.
- Degree exists only as the boolean `is_resolved`.

## 5. Proposed Behaviour

1. **Parked gate (codified).** On settle, focus stays at the deepest
   newly-settled frame. This is the return gate: `reduce`, `tidy`,
   and `state` operate there; nothing blocks; nothing prompts.
2. **The settle wave.** Any resolution can settle a chain of
   ancestors at once (completion propagating, never severing). Gates
   conceptually exist for every newly settled frame; the user steps
   through them with `return`, each parent rendering with the child's
   reduction already folded in.
3. **`reduce` pops one frame.** A successful manual `reduce` is the
   ratified passage — there is no reason to idle on a node that has
   served its purpose. After `reduced.`, focus moves to the parent
   (matching `return`'s print and event). At root, focus stays.
   `fold` and accepted offers do not move focus.
4. **`onward`.** Leaves the backwards flow: from the active node,
   walk parent-ward while frames are resolved; land on the deepest
   unresolved ancestor (or root, if the trace is complete). Refused
   with `already at open work` when the active node is unresolved.
   Records an `onward` event. (`next` is reserved for later.)
5. **`back` is removed.** Dispatch entry, command, help lines, and
   its tests go. The hole-command refusal becomes
   `no open holes; use 'up' or 'onward'`.

## 6. Data Model

One pure property on `Demand`:

```python
@property
def degree(self) -> int:
    """Open holes in this demand's subtree, computed on read."""
    total = len(self.open_positions)
    for child in self.children().values():
        total += child.degree
    return total
```

`degree == 0` iff `is_resolved` for resolution-consistent trees.
Reductions and cleanups never affect it. Surfacing `degree` in
`state` is deferred (§9) to keep this segment's output changes
confined to the commands it owns.

## 7. Commands / API

- `onward` — trace-only. Walk and landing as §5.4. Confirmation:
  `onward to <tag>.`
- `reduce` — unchanged interaction, then pops one frame: prints
  `returned to parent.` and records the `return` event, exactly as
  the manual verb does.
- `return` — unchanged; now understood as manual gate-stepping.
- `back` — removed.
- Help: `back` line removed; `onward` added
  (`"leave settled frames for the deepest open ancestor"`).

Consequence recorded: after `reduce` pops, the reduced node is no
longer reachable for `unreduce` (no downward navigation). Under the
no-mistakes assumption this is accepted; re-ratification is not a
supported workflow. `unreduce` remains for nodes still in focus
(root, or re-reduction at the same sitting before popping).

## 8. Test Contract

```
# data layer
test_degree_counts_open_holes_in_subtree
test_degree_zero_iff_resolved
test_degree_ignores_reduction_overlays

# repl
test_onward_routes_to_deepest_unresolved_ancestor
test_onward_refused_when_active_has_open_work
test_onward_outside_trace_is_rejected
test_onward_on_complete_trace_lands_at_root
test_onward_records_event
test_reduce_pops_one_frame_on_success         # focus at parent after
test_reduce_failure_does_not_pop              # rejection/abort hold focus
test_hole_command_message_names_onward        # 'up' or 'onward'

# removals / rewrites
back tests deleted; reduce-focus assertions rewritten for the pop;
EXPECTED_HELP updated in both help-asserting test files.
```

## 9. Open Questions

1. Whether accepted on-settle offers should also pop focus, unifying
   offers with the gate completely. Decide by use.
2. Whether `state` shows `degree: N`. Cheap, but touches every
   state-block assertion; defer to its own small segment.
3. Whether `onward` should land on the next open *hole* (worklist
   semantics) rather than the deepest unresolved ancestor (stack
   semantics). Stack semantics chosen: scheduling stays human
   (`goto`); `onward` only leaves dead frames.
