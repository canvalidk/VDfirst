# Repository label

- Source file: `simulator_polish_spec.md`.
- Role: Pre-handoff simulator polish pass.
- Implementation status: Mostly implemented on `main` in merge commit
  `72b7732` (`Merge simulator polish`).
- Notes: `compress` / `uncompress` were intentionally deferred during
  implementation. Console output was kept ASCII-only, and `go to N` was
  added as an alias for `goto N`.

---

# VD Simulator — Polish Pass Spec

**Status:** Proposed. Pre-handoff polish ahead of Design 2.1 integration.
**Scope:** No architectural changes. Surface-area additions exposing
existing `Demand` / `Trace` methods, UX normalisation, docs sweep.
**Touches:** `repl.py`, `test_repl.py`, `test_repl_trace.py`,
`run_repl.py`, `CLAUDE.md`, `README.md`, `simulator.py` (docstring only).

---

## 0. Context

The simulator MVP is functionally complete: inspection primitives, trace
bootstrap, expand/recall/inject/back/cancel, immutable `Definiens`,
read-only `Simulator` discipline. Open work on this pass is QoL only.

Three tiers, executed in order:

1. **Missing surface area.** Methods exist on `Demand` / `Trace` but no
   REPL command exposes them. The most common user workflows (compress
   on return, navigate non-stack-order through the worklist) are
   unreachable.
2. **UX polish.** Long output, missing context cues, drifted message
   wording.
3. **Docs.** Module docstrings, `CLAUDE.md`, `README.md` all carry stale
   "forthcoming" or "next likely" claims.

Out of scope: trace save/restore, multi-trace sessions, a full `tree`
rendering, inline provenance display in `state` beyond the breadcrumb.
These are deferred to Design 2.1+.

---

## Tier 1 — Missing Surface Area

### 1.1 `help`

**Syntax.** `help`

**Behavior.** Print all known commands grouped into two sections:
*always available* and *trace-only*. Within each section, alphabetical.
One line per command: name, one-clause description.

**Layout (illustrative).**

```
always available:
  count                    entry and headword counts
  exit, quit               leave the REPL
  headwords                list all headwords
  help                     this list
  recall <headword>        show a dictionary entry (or fill a hole in trace)
  trace <text>             start a new trace

trace-only:
  back                     undo the active child, return to its parent
  cancel                   abandon the entire trace
  compress <pos> [abbr]    render position N as headword/abbreviation
  expand [pos]             expand an open hole into a dictionary entry
  goto N                   move active focus to worklist entry N
  inject [pos]             fill an open hole with user-supplied text
  state                    show the active demand
  uncompress <pos>         render position N as full text
  up                       move active focus to the parent demand
  worklist                 list all open holes across the tree
```

**Edge cases.** None. Pure print.

**Files.** `repl.py` (`cmd_help`, dispatch entry).

**Tests.**

- `help` outside trace prints both sections.
- `help` inside trace prints both sections (content does not change).

`help <cmd>` for per-command detail is deferred.

---

### 1.2 `worklist`

**Syntax.** `worklist`

**Behavior.** Trace-only. Lists every open hole across the demand tree,
depth-first left-to-right (matches `Trace.worklist`). Each line:

```
[N] <location-tag>  pos P  →  {headword}
```

Where:

- `N` is a zero-based handle for `goto`. Stable within one `worklist`
  invocation; not stable across mutations.
- `<location-tag>` describes the demand that owns this open hole:
  - root demand: `root`
  - `ExpandResolution` child: `E<source_index>`
  - `InjectResolution` child: `injected`
- `pos P` is the local position of the open hole on that demand.
- `{headword}` is the headword demanded at the hole.

Mark the currently active demand with a leading `*` on those of its
lines:

```
  [0] root         pos 2  →  {m}
* [1] E22          pos 0  →  {acting-force}
* [2] E22          pos 1  →  {interacting-forces-set}
```

Empty worklist: print `no open holes; trace is complete.`

**Edge cases.**

- Worklist is computed each call; tree mutations between calls renumber.
  Document this in the docstring.
- A demand can have multiple open holes — multiple lines, all marked
  active if it is the active demand.

**Files.** `repl.py` (`cmd_worklist`, dispatch entry). A small helper
for the location tag, sourced from each demand's `provenance`.

**Tests.**

- `worklist` outside trace refused with existing "not in a trace" line.
- Root-only trace with one open hole: one line, marked active.
- After two `expand`s and a `up`, worklist shows all open holes; active
  marker on whichever is active.
- Order matches `Trace.worklist` (depth-first left-to-right).
- Order-0 root (no holes) prints `no open holes; trace is complete.`

---

### 1.3 `goto N`

**Syntax.** `goto N`

**Behavior.** Trace-only. Move `trace.active` to the demand owning
worklist entry `N` (zero-based, indexed into the current `Trace.worklist`).

Print confirmation: `moved to <location-tag>.` using the same tag
scheme as `worklist`. If `goto` targets the demand already active,
still print `moved to <tag>.` (no special case; the move is a no-op
but the message is honest about where you are).

**Edge cases.**

- No argument: `usage: goto N`
- Non-integer argument: `invalid index`
- Out of range: `index N out of range; worklist has K entries` where K
  is `len(trace.worklist)`.
- Worklist is empty (trace complete): `no open holes`.

**Files.** `repl.py` (`cmd_goto`, dispatch entry).

**Tests.**

- `goto` outside trace refused.
- `goto` with no arg shows usage.
- `goto 0` from root with one hole stays at root.
- After `expand` deepens the tree, `goto 0` returns to root if root's
  hole is still index 0.
- `goto 99` refused with range message.
- `goto abc` refused with "invalid index".
- Round-trip: `goto N` then `expand` operates on the demand goto'd to,
  using that demand's local positions.

---

### 1.4 `compress <pos>` / `compress <pos> <abbr>` / `uncompress <pos>`

**Syntax.**

- `compress <pos>` — mark position `pos` on the active demand as
  compressed; no abbreviation.
- `compress <pos> <abbr>` — same, with abbreviation. Only meaningful
  for `InjectResolution`; for Recall/Expand the abbreviation is stored
  but ignored on render (consistent with `Demand.set_compression`).
- `uncompress <pos>` — mark position as not compressed; abbreviation
  (if any) dropped.

**Behavior.** Trace-only. Acts on the active demand. Position must
already be resolved. Updates the resolution via
`Demand.set_compression`.

Print confirmation: `compressed position P.` /
`compressed position P as <abbr>.` / `uncompressed position P.`

**Edge cases.**

- Position not resolved (still open): `position P is not resolved`.
- Position out of range: existing range-error message from
  `Demand._check_position`.
- No argument: `usage: compress <pos> [abbr]` /
  `usage: uncompress <pos>`.
- Non-integer pos: `invalid position` (matches existing).

**Files.** `repl.py` (`cmd_compress`, `cmd_uncompress`, dispatch
entries).

**Tests.**

- `compress` / `uncompress` outside trace refused.
- `compress` with no args shows usage.
- `compress` on open position rejected.
- `compress 0` on a recalled position: subsequent `state` renders
  position 0 as `{headword}` instead of the text.
- `compress 0 alias` on an injected position: subsequent `state`
  renders position 0 as `alias`.
- `compress 0 alias` on a recalled position: stored but rendered as
  `{headword}` (abbreviation ignored for non-inject — match existing
  `_render_position` behaviour).
- `uncompress 0` reverts the rendering.
- `compress` then `compress` again is idempotent; `compress` after
  `uncompress` re-compresses correctly.

**Note.** The session notes call compression "expected to fire on
almost every return." This command exposes the ability but does not
automate it. Automated compression-prompt at child resolution is
deferred — that's an interaction-design decision belonging to Design
2.1.

---

## Tier 2 — UX Polish

### 2.1 Truncate multi-entry pick prompt

**Where.** `REPL._pick_entry_index`.

**Behavior.** When listing multiple entries for the user to pick, show
at most ~60 characters of the definition text, with `…` if truncated.
Existing format otherwise unchanged.

```
multiple entries for 'mass':
  E0: A scalar property of a point-particle measuring its inertia, p…
  E2: The positive scalar coefficient m such that net-force = m time…
```

**Edge cases.** Threshold constant in code (`PICK_PREVIEW_WIDTH = 60`).
Truncation by character count, not word boundary — keep it dumb.

**Files.** `repl.py`. No changes to `_pick_entry_index`'s control flow,
only the format string.

**Tests.**

- New fixture with a definition longer than 60 chars. Assert truncation
  marker present in output.
- Existing tests with short definitions remain unchanged.

---

### 2.2 Startup banner

**Where.** `run_repl.py`, not `REPL.run()`. Keeping `REPL` banner-free
preserves the test discipline (no startup output to filter).

**Behavior.** Before calling `REPL(...).run()`, print one line:

```
<instance_name> — <entry_count> entries, <headword_count> distinct headwords. type 'help' for commands.
```

Pull `instance_name` from `VDInstance.name`, counts from the
`Simulator`.

**Edge cases.** None. The launcher is the launcher.

**Files.** `run_repl.py`.

**Tests.** Not test-targeted; `run_repl.py` is the launcher and isn't
tested as a unit. If a smoke test is wanted, defer.

---

### 2.3 State breadcrumb

**Where.** `REPL.cmd_state`.

**Behavior.** Prefix the existing `state` output with a one-line
breadcrumb identifying the active demand:

```
at: root
{net-force} = {inertial-mass} × {inertial-acceleration}
open positions: 0, 1, 2
```

Or for a non-root active demand:

```
at: E22 @ parent pos 1
…
```

`at: injected @ parent pos 0` for inject children. The `@ parent pos P`
clause tells you which hole on the parent spawned this demand — useful
for orientation when the user has done several expands.

**Edge cases.**

- Root demand: just `at: root`.
- Non-root demand: find which position on `active.parent` resolves to
  `active`. (Loop over `parent.children()`.) Use the resolution type
  to determine `E<idx>` vs `injected`.

**Files.** `repl.py` (`cmd_state`, small helper shared with
`worklist`'s tag formatter — extract once).

**Tests.**

- `state` at root prefixed with `at: root`.
- `state` after `expand 0` prefixed with `at: E<idx> @ parent pos 0`.
- `state` after `inject 0` prefixed with `at: injected @ parent pos 0`.
- Existing `state` tests updated to expect the breadcrumb line.

---

### 2.4 Message wording audit

**Where.** All `cmd_*` and helper methods in `repl.py`.

**Rule.** Apply consistently:

- **Action confirmations** (something happened): lowercase, end with
  period. Examples: `moved up.`, `trace started.`, `compressed
  position 0.`
- **Refusals and status displays**: lowercase, no trailing period.
  Examples: `invalid position`, `already at root`, `open positions: 0`.

**Behavior.** Audit existing messages against this rule; rewrite any
drift. Most messages already conform. Known minor cases:

- `usage: trace <text>` (status, no period — keep)
- `unknown command: foo` (refusal, no period — keep)
- `not in a trace; use 'trace <text>' to start one` (refusal, no
  period — keep)

I do not expect this audit to change many strings. Its main value is
codifying the rule in a comment at the top of `repl.py` so subsequent
edits stay aligned. The bulk of the diff is the breadcrumb (2.3)
touching `state`'s expected output.

**Files.** `repl.py`. Update any matching test expectations.

**Tests.** Adjust as needed where strings change. Most tests untouched.

---

## Tier 3 — Docs Sweep

### 3.1 `CLAUDE.md` Current State

**Current.**

> Next likely work: trace bootstrap and demand graph design, or a
> phase-2.5 presentation command such as `show <headword>`.

**Update.** Reflect that trace bootstrap and the demand graph are now
implemented (`demand.py`, `Trace`, REPL trace commands). Add post-polish
expected test count once it lands. Mention `run_repl.py` as the entry
point.

Also update the Simulator Roadmap section: items 1 and 2 are done;
item 3 (demand graph + trace state) is done; item 4 (`EXPAND`,
`RECALL`, `INJECT`, `SKIP`, navigation, worklist/state display) is
done modulo `SKIP` — which `goto` subsumes for the user-level
workflow. Note this.

**Files.** `CLAUDE.md`.

---

### 3.2 `README.md` command set

**Current.** Lists files. Says nothing about how to use the simulator.

**Update.** Add a short "Running the simulator" section pointing at
`run_repl.py`. List the command set at high level (or point at `help`).
Keep terse.

**Files.** `README.md`.

---

### 3.3 `simulator.py` docstring drift

**Current.**

> The REPL (forthcoming) does dispatch, prompts, and trace state. This
> file is the data layer it queries.

**Update.** REPL exists. Reword the second paragraph to refer to it as
present-tense.

**Files.** `simulator.py` (docstring only).

---

## Deferred

Called out so they aren't lost between this pass and Design 2.1:

- **Automated compression-prompt at child resolution.** Session notes
  expect it. Belongs to the interaction design of trace return, not to
  the present surface-area pass.
- **`tree` command.** Full demand-tree rendering. Requires a rendering
  choice that may collide with Design 2.1.
- **Inline provenance in `state` beyond breadcrumb.** Same reason.
- **Trace save/restore, multi-trace sessions.** Already deferred in the
  simulator spec.
- **Help per command (`help <cmd>`).** Useful but not blocking.
- **Worklist filtering / sorting controls.** Defer until usage shows a
  need.
- **`SKIP` as a named verb.** Subsumed by `goto` for v1; revisit if
  user friction emerges.

---

## Order of execution

1. Tier 1.1 `help` (smallest, lowest risk; opens up discoverability for
   the rest).
2. Tier 1.2 `worklist` (precondition for `goto`).
3. Tier 1.3 `goto` (depends on `worklist`).
4. Tier 1.4 `compress` / `uncompress`.
5. Tier 2.3 `state` breadcrumb (the helper from 1.2's location-tag
   formatter is reusable here).
6. Tier 2.1 multi-entry truncation.
7. Tier 2.2 startup banner.
8. Tier 2.4 message audit.
9. Tier 3.1–3.3 docs sweep.

Each step lands with its tests green before the next begins.

---

## Open questions

- **Compression-on-resolve UX.** The session notes call for compression
  to fire on child resolution. The present spec exposes `compress` as
  a manual command only. When Design 2.1 wires up the automatic prompt,
  the manual `compress` stays available as the retrospective tool.
  Confirm this is the intended split.
- **Worklist re-indexing.** `goto N` references the worklist as of its
  most recent invocation. If the user does `worklist`, then `expand`,
  then `goto 1`, the indices may now refer to different demands. The
  current spec accepts this and treats `goto N` as a one-shot —
  document the caveat in the `goto` docstring. Alternative (deferred):
  indices that survive mutations (e.g. content-addressed by demand
  identity).