# Repository label

- Source file: `simulator_intrace_spec.md`.
- Role: Phase 4 in-trace command and trace-mode REPL spec.
- Implementation status: Implemented on `main` with later polish updates.
- Notes: A named `SKIP` command is not implemented; `goto` / `go to`
  covers the current user-level workflow. Current behavior is governed
  by code and tests.

---

# VD Simulator — In-Trace Commands & Trace Mode Spec (Phase 4)

*Author: Claude (committing to a design). Highly speculative — see §2.
To be filtered.*

## 1. Scope

Wire the demand graph from Phase 3 into the REPL from Phase 2. Add
trace mode: prompt change, in-trace command set, hole choices,
navigation, cancellation, completion. The user can run a full
end-to-end trace from `trace <text>` to root resolution.

Deliverable: changes to `repl.py` (new commands, mode flag, dispatch
gating) and a new `test_repl_trace.py`. The data layer (Phase 3) is
not modified — Phase 4 is REPL wiring only.

## 2. Status warning

Neither Phase 2 nor Phase 3 was visible in project knowledge when this
was drafted. The signatures and behaviours below assume Phase 2 and
Phase 3 were implemented as specced. If Claude Code deviated — and
some deviations are likely, since specs always miss something —
several things here will need adjustment:

- Method names on `Demand` / `Trace` may differ.
- The `Resolution` union may have different fields (see §7 — a Phase 3
  gap was identified during this draft).
- The REPL's dispatch table mechanism may not match.

Treat this as a draft to filter, not as a buildable contract. After
Phase 2 and 3 are realised, re-read this against the actual code and
revise before handing to Claude Code.

## 3. State model

Trace state lives on the REPL, not the Simulator:

```python
class REPL:
    sim: Simulator
    trace: Optional[Trace]   # None outside trace mode
    # input_fn, print_fn as before
```

The Simulator stays read-only. The REPL is the only place that
mutates a Trace.

Mode is derived: `self.trace is None` → outside trace, else inside.
No separate flag.

## 4. Command set

Three groups, gated by mode (§5):

### Always available

- `headwords` — Phase 2, unchanged.
- `count` — Phase 2, unchanged.
- `recall <headword>` — Phase 2 inspection version, *unchanged
  outside trace*. Inside trace, see §6.
- `exit` / `quit` — Phase 2, unchanged.

### Outside trace only

- `trace <text>` — bootstrap. Calls `Trace.start(sim, text)`,
  assigns to `self.trace`, transitions to trace mode.

### Inside trace only

Hole choices (operate on a position in `trace.active`):

- `expand [pos]` — EXPAND. If `pos` omitted, defaults to the smallest
  open position. The hole's headword is recalled (sub-prompt for
  E-number if multiple entries), analysed into a Definiens, made
  into a child Demand. Child becomes the new `active`.
- `recall [pos]` — in-trace RECALL. Same headword lookup as
  inspection `recall`, but fills the hole with the literal text via
  `Demand.resolve_recall`. Does *not* move `active`. (Name collision
  with inspection mode — see §5.)
- `inject [pos]` — INJECT. Prompts for replacement text, analyses
  into a Definiens, creates child Demand, becomes new `active`.
- `skip [pos]` — SKIP. No data change; advisory. Prints "skipped",
  loop continues. (See §11 — debatable whether worth its own command
  vs just typing nothing.)

Navigation:

- `up` — move active to active.parent. Refused at root with
  "already at root".
- `down <pos>` — move active to the child at position `pos`.
  Refused with "no child at position N" if the position is open or
  resolved by RECALL.
- `state` — print active demand's `text()`. Section §8 for format.
- `worklist` — list all open `(demand, pos)` pairs across the tree.
- `path` — print the chain from root to active (E-numbers and
  headwords). Useful for "where am I?"

Termination:

- `cancel` — unresolve the parent's pointer to active, drop active's
  subtree. Move active to parent. Refused at root.
- `cancel trace` — discard the whole trace, return to outside-trace
  mode.
- `finish` — only allowed if `trace.is_complete`. Prints final
  rendering, exits trace mode. (Without `finish`, completion just
  announces but stays in trace mode so the user can review.)

## 5. Mode discipline

Dispatch gating happens in the REPL before the command runs:

| State | Commands allowed |
|---|---|
| Outside trace | `headwords`, `count`, `recall`, `trace`, `exit` |
| Inside trace, root active | All but `up`, `cancel`, `down` (if no children) |
| Inside trace, non-root active | All in-trace commands |

Unknown commands are rejected at the top of dispatch (Phase 2 already).
Wrong-mode commands print:

- Outside trace: `"not in a trace; use 'trace <text>' to start one"`.
- Inside trace: `"<command> only valid outside a trace; use 'cancel trace' first"`.

**The `recall` name collision.** Same keyword, contextual behaviour
(committed earlier this session). Outside trace: inspection — prints
the entry text and stops. Inside trace: hole fill — modifies the
active demand. The user knows which mode they're in (prompt shows
it); the keyword carries the user's intent ("show me / use this
entry's text") and the mode picks the verb.

## 6. Hole choices — detail

Each in-trace command resolves to:

1. Identify position `pos` (argument or default to
   `min(active.open_positions)`).
2. If `pos` not open → `"position N is already resolved"`, return.
3. If no open positions and no `pos` given → `"no open holes; use
   'up' or 'cancel'"`, return.
4. Determine headword: `hw = active.headword_at(pos)`.
5. Branch by command.

**`expand`:**

- `idxs = sim.entry_indexes(hw)`.
- If empty → `"no entry for '<hw>'"`, return.
- If multi → sub-prompt for E-number (same flow as Phase 2 multi-recall).
- `text = sim.entry_text(idx)`.
- `definiens = sim.analyse(text)`.
- Create child `Demand(definiens, {}, parent=active,
  provenance=ExpandProvenance(idx))`.
- `active.resolve_expand(pos, child, source_index=idx)`.
- `self.trace.active = child`. (REPL moves focus.)
- Print `f"expanded E{idx} at position {pos}; now at child."`

**`recall` (in-trace):**

- Same lookup as inspection `recall` for E-number resolution.
- `text = sim.entry_text(idx)`.
- `active.resolve_recall(pos, text, source_index=idx)`.
- *Do not* move active. The hole closes in place.
- Print `f"recalled E{idx} at position {pos}."`
- If `active.is_resolved` becomes True → see §9.

**`inject`:**

- Sub-prompt: `"text: "` via `input_fn`. Read a line.
- If empty → `"inject aborted: no text"`, return.
- `definiens = sim.analyse(text)`.
- Create child Demand with `InjectProvenance(text)`.
- `active.resolve_inject(pos, child)`.
- `self.trace.active = child`.
- Print confirmation. If the child's definiens has order 0 (no
  headwords in the injected text), the child immediately resolves —
  see §9.

**`skip`:**

- Print `f"skipped position {pos}."`
- No state change. The position remains in `open_positions`.
- (Debatable — see §11.)

## 7. Compression-at-return (gap forwarded to Phase 3)

When a child Demand becomes `is_resolved`, the REPL must ask the user
how the parent's hole renders it: paste raw, or compress?

**Phase 3 has a gap here.** I put `compressed: bool` only on
`RecallResolution`. `ExpandResolution` and `InjectResolution` need
it too — same field, same semantics:

- `compressed=False`: parent's hole renders as the child's full
  recursive `text()`.
- `compressed=True`: parent's hole renders as the headword name (for
  Expand) or a user-supplied abbreviation (for Inject).

The Phase 3 spec needs this addition. Make a note to revise it.

REPL flow at child resolution:

1. The hole-filling command (`recall` in-trace, or `expand`/`inject`
   when the child later resolves) detects the resolution.
2. Sub-prompt: `"paste (r)aw or (c)ompress?"` via `input_fn`.
3. If `c`: for Recall, set `compressed=True` and we're done. For
   Expand, set `compressed=True` on the parent's ExpandResolution.
   For Inject, sub-prompt for abbreviation text.
4. The choice is recorded; rendering reflects it from then on.

This means resolution is a *two-prompt* operation, not one. The
first prompt picks the verb (expand/recall/inject); the second picks
the rendering. Earlier sessions noted compression is expected to
fire on "almost every return," so this isn't optional UX.

If this complexity is unwanted in v1, the alternative is: always
paste raw, never prompt. Compression becomes a Phase 5 feature.
Easier to build but doesn't match the simulator_session notes.

**Recommendation: build with compression. The compression prompt is
the residual layer's main artefact; cutting it makes the simulator
significantly less of what it's supposed to be.**

## 8. State display

`state` prints `active.text()` plus a header line:

```
active: <headword> [E<source-or-root>]  pos <path-from-root>
<rendered text>
open positions: 0, 2
```

`path` prints the route from root → active:

```
E5: force
  ↳ E12: net-force [pos 0]
    ↳ E18: vector-sum [pos 1]   ← active
```

`worklist` prints, depth-first:

```
trace open positions:
  E12: net-force [pos 0]: {acting-object}
  E18: vector-sum [pos 1]: {component}     ← active
  E18: vector-sum [pos 2]: {component}     ← active
  ...
```

Output formats are advisory — Claude Code should pick something
consistent and tests should assert structural properties (lines
present, key tokens) rather than exact strings.

## 9. Completion

After any in-trace command that resolves something, check
`self.trace.is_complete`. If True:

```
trace complete.
<root.text()>
use 'finish' to exit trace mode, or 'cancel trace' to discard.
```

Stay in trace mode. The user can navigate around the resolved tree
to review.

`finish` then prints the final text once more (or just confirms) and
sets `self.trace = None`.

`cancel trace` always works regardless of completion state.

## 10. Committed design choices

Filter as needed.

**Same `recall` keyword inside and outside trace.** Discussed and
agreed earlier this session.

**Position defaults to smallest open.** Most natural for left-to-right
reading. Always overridable.

**`active` follows EXPAND and INJECT, not RECALL.** RECALL resolves
in place; the user is still working at the same level. EXPAND and
INJECT create a new context the user wants to dig into.

**Two-prompt resolution (verb, then compression).** Per §7 — needed
to match the residual layer's role.

**`finish` is explicit, completion doesn't auto-exit.** Lets the
user review the resolved tree.

**`skip` is a real command.** Pro: makes the user's intent visible
in the log; future audit/replay can see "user considered this and
chose to skip." Con: redundant with just typing nothing. Keeping it
for the audit story.

**No `unskip`.** A position never goes from "skipped" to "I changed
my mind" — they just resolve it normally. The skip command is
declarative, not stateful.

## 11. Test contract

`test_repl_trace.py`. Reuse the `drive` helper from `test_repl.py`.
The Phase 2 helper handles input/output capture; this file adds
trace scenarios.

**Bootstrap:**

- `trace mass` on small sim → enters trace mode, active is root.
- `trace <text>` with no matching headwords → root has order-0
  Definiens, immediately `is_complete`.
- `trace` (no arg) → usage error.

**Hole-choice mechanics (against a sim with multi-headword entries):**

- `expand` → recalls entry, analyses, becomes child active.
- `expand` with multi-entry headword → sub-prompt for E-number.
- `recall` → fills in place, active doesn't move.
- `inject` → sub-prompt for text, becomes child active.
- `skip` → no state change.
- All four → "position N already resolved" if tried on a closed hole.
- All four → "no open holes" if active has none.

**Compression sub-prompt:**

- After `recall` → asked raw/compress.
- `c` → resolution.compressed is True; state shows headword.
- `r` → resolution.compressed is False; state shows entry text.
- After `expand` where the child immediately has order-0 Definiens
  (entry text contained no headwords) → child resolves → compression
  prompt fires for the parent's hole.

**Navigation:**

- `up` at root → refused.
- `up` after expand → returns to parent.
- `down 0` to an expanded position → moves into child.
- `down 0` to a recalled or open position → refused.

**Cancel and completion:**

- `cancel` at root → refused.
- `cancel` after expand → unresolves parent's pointer, returns to
  parent, hole is open again.
- `cancel trace` → exits trace mode regardless of state.
- Full resolution of all holes → "trace complete" announced.
- `finish` after completion → exits.
- `finish` before completion → refused.

**Mode discipline:**

- `expand` outside trace → "not in a trace".
- `trace foo` inside trace → "trace only valid outside; use cancel
  trace first".
- `recall` works in both modes with correct semantics.
- `headwords` / `count` work in both modes (inspection always
  available).

**End-to-end:**

- Bootstrap on `trace force`, expand through one level, recall a
  leaf, compress, observe the parent text() updates, finish.
- Same but with inject mid-trace.
- Same but with cancel of a subtree, then re-expand differently.

Estimate: ~40-50 tests.

## 12. Deferred / open

- **Worklist display format.** Currently advisory. Pick once Phase 4
  is real and see what's readable.
- **Save / restore traces.** Out of scope.
- **Trace history command.** A `history` showing all decisions made
  in time order. Useful for audit; defer.
- **Provenance display in state.** Right now `state` shows the
  active demand's text but not its provenance. Probably want both,
  but format is undecided.
- **Multi-trace.** Only one trace at a time. Multi-trace would let a
  user run two parallel investigations; not in v1.

## 13. Forwarded issues for Phase 3 revision

If Phase 3 hasn't been built yet, fold these in before handing it
to Claude Code:

1. **Add `compressed: bool = False` to `ExpandResolution` and
   `InjectResolution`.** Same semantics as on `RecallResolution`.
2. **Add `abbreviation: Optional[str] = None` to `InjectResolution`.**
   When compression is requested on an inject, this is what the
   compressed form renders as. (Headword isn't available for inject.)
3. **`Demand.text()` must respect compression on all three resolution
   types.** Phase 3 spec mentioned this only for Recall.

If Phase 3 is already built and Claude Code didn't include those
fields, they need to be added before Phase 4 can be built. Small
change but a real one — touches the Resolution dataclasses, `text()`,
and any tests that exercise compression.

## 14. Implementation notes for Claude Code

- File changes: edit `repl.py`, add `test_repl_trace.py`.
- Roughly: REPL gains ~150 lines of new command handlers and a
  trace state field. Tests are ~300 lines.
- Run `pytest test_*.py` after; expected new total in the
  ~200-220 range.
- Don't refactor existing code. The Phase 2 commands stay as-is
  except that `recall` becomes mode-aware.
- The two-prompt resolution flow is the trickiest part. Make a
  helper: `_prompt_compression(default_label: str) -> tuple[bool,
  Optional[str]]` that handles the raw/compress sub-prompt and
  returns `(compressed, abbreviation)`.
- Order of operations matters when checking completion after a
  resolution: resolve first, *then* check `trace.is_complete`. The
  REPL flow should be: command logic → data mutation → completion
  check → announce.