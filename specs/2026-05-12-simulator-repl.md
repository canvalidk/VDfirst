# Repository label

- Source file: `simulator_repl_spec.md`.
- Role: Phase 2 REPL inspection-command spec.
- Implementation status: Implemented on `main`; later trace-mode specs
  add demand graph interaction.
- Notes: Preserved as historical design context. Current behavior is
  governed by code and tests.

---

# VD Simulator — REPL Spec (Phase 2)

*Author: Claude (committing to a design). To be filtered.*

## 1. Scope

Build the input loop that hosts the inspection commands. Three commands
wired up: `headwords`, `count`, `recall`. No trace state, no demand
graph — those are Phase 3+.

Deliverable: a new file `repl.py` with a `REPL` class, plus
`test_repl.py` covering the loop and the three commands.

## 2. Architecture

One class, `REPL`. Holds:

- `sim: Simulator` — the inspection oracle.
- `input_fn: Callable[[str], str]` — defaults to builtin `input`.
- `print_fn: Callable[..., None]` — defaults to builtin `print`.

Both hooks are mandatory. Every prompt and every output line goes
through `input_fn` / `print_fn`. **No bare `input()` or `print()`
calls anywhere in `repl.py`.** This is what makes the loop
driver-replayable.

## 3. Public API

```python
from typing import Callable
from simulator import Simulator

class REPL:
    def __init__(
        self,
        sim: Simulator,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[..., None] = print,
    ) -> None: ...

    def run(self) -> None:
        """Main loop. Returns when the user exits or EOF arrives."""

    def step(self) -> bool:
        """Read one input, dispatch, return True if the loop should
        continue, False on exit/EOF. For tests."""
```

`run()` is `while self.step(): pass`. Keep it that simple.

## 4. Loop semantics

Each `step()` does:

1. Read a line via `input_fn("> ")`.
2. If `EOFError` is raised — return `False` (clean exit).
3. If `KeyboardInterrupt` is raised — `print_fn()` a blank line,
   return `True` (loop again).
4. Strip whitespace. If empty — return `True`.
5. Partition on first space: `cmd, _, rest = line.partition(" ")`.
6. Lowercase `cmd`. Leave `rest` as-is (headwords may have case).
7. If `cmd in ("exit", "quit")` — return `False`.
8. If `cmd` is in the dispatch table — call the handler with `rest`,
   return `True`.
9. Otherwise — `print_fn(f"unknown command: {cmd}")`, return `True`.

The dispatch table maps command name → bound method:
`{"headwords": self.cmd_headwords, "count": self.cmd_count,
"recall": self.cmd_recall}`.

## 5. Commands

### `headwords`

- Argument ignored if present.
- Print each headword on its own line. `sim.all_headwords()` returns
  them sorted.
- Empty dictionary → print nothing. Don't print a blank line.

### `count`

- Argument ignored.
- One line: `<N> entries, <K> distinct headwords` where N is
  `sim.entry_count()` and K is `sim.headword_count()`.

### `recall <headword>`

- If `rest` is empty after strip — `print_fn("usage: recall <headword>")`
  and return.
- `idxs = sim.entry_indexes(rest)`.
- If empty — `print_fn(f"no entry for '{rest}'")` and return.
- If `len(idxs) == 1` — print `f"E{idxs[0]}: {sim.entry_text(idxs[0])}"`.
- If `len(idxs) > 1`:
  - Print `f"multiple entries for '{rest}':"`.
  - For each `i` in `idxs`: print `f"  E{i}: {sim.entry_text(i)}"`.
  - Sub-prompt: `pick = input_fn("pick E-number: ")`.
  - Parse `pick` as int. On `ValueError`, or if int not in `idxs` —
    `print_fn("invalid choice; aborted")` and return.
  - Otherwise — print `f"E{chosen}: {sim.entry_text(chosen)}"`.

## 6. Error model

| Source | Behaviour |
|---|---|
| Unknown command | Print rejection, continue. |
| Missing argument | Print usage, continue. |
| `IndexError` from simulator | Catch in handler, print the exception message, continue. |
| `EOFError` from `input_fn` | Exit cleanly. |
| `KeyboardInterrupt` | Print blank line, continue. |
| Any other exception | Let it propagate. Bugs should not be silently swallowed. |

The REPL never crashes on user input. Only on bugs.

## 7. Committed design choices

These were open; committing now, filter later.

**Multi-entry recall display.** Show full text for each entry, not a
prefix. Entries are typically one or two sentences; truncation hides
the information the user is choosing between.

**Case sensitivity.** Commands case-insensitive (`HEADWORDS` works).
Headword arguments case-sensitive (matching stored form). This means
`recall Force` and `recall force` are different queries.

**Prompt strings.** Main prompt: `"> "`. Sub-prompt: `"pick E-number: "`.
Hardcoded. No preference machinery yet.

**No `show` command in this phase.** `simulator_spec.md` §4.1 lists
`show <headword>` separately. Defer to Phase 2.5; `recall` covers the
same lookup path and `show` is just a presentation variant.

**No history, no readline integration.** Defer.

## 8. Test contract

`test_repl.py`. Fixtures: reuse `empty_sim`, `small_sim`,
`sim_with_redefines` from `test_simulator.py` (copy them in — don't
import across test files).

Add a driving helper:

```python
def drive(sim, inputs):
    """Run REPL against a fixed input list. Return captured output lines."""
    out = []
    it = iter(inputs)
    repl = REPL(
        sim,
        input_fn=lambda prompt: next(it),
        print_fn=lambda *args: out.append(" ".join(str(a) for a in args)),
    )
    repl.run()
    return out
```

When `it` is exhausted, `next(it)` raises `StopIteration`, which
should be caught and treated as EOF — **modify the helper or the REPL
to map `StopIteration` to `EOFError`** so tests don't need an explicit
`"exit"` line. (Recommend: handle in the helper. The REPL contract
stays "EOFError = exit"; the helper converts.)

**Loop mechanics:**

- One command, then exhausted input → loop runs once, exits cleanly.
- Empty lines are ignored (don't dispatch, don't error).
- Unknown command → `"unknown command: foo"` line, loop continues.
- `exit` / `quit` → clean exit.
- Whitespace-only input → ignored.

**`headwords`:**

- On `small_sim` → 3 lines, alphabetical: `force`, `mass`, `particle`.
- On `empty_sim` → no output.
- Argument silently ignored: `headwords whatever` works.
- `HEADWORDS` (uppercase) works.

**`count`:**

- On `small_sim` → `3 entries, 3 distinct headwords`.
- On `sim_with_redefines` → `5 entries, 3 distinct headwords`.
- On `empty_sim` → `0 entries, 0 distinct headwords`.

**`recall` single-entry:**

- `recall mass` on `small_sim` → `E0: numerical property of a particle`.
- `recall unknown` on `small_sim` → `no entry for 'unknown'`.
- `recall` (no arg) → `usage: recall <headword>`.
- `recall ""` (empty after strip) → same usage line.
- Case sensitivity: `recall Mass` on `small_sim` → no entry (stored is
  `mass`).

**`recall` multi-entry (on `sim_with_redefines`):**

- `recall mass` → header line + two entry lines + sub-prompt → user
  picks `0` → `E0: first definition`.
- Same setup, user picks `2` → `E2: second definition`.
- User picks `99` (not in idxs) → `invalid choice; aborted`.
- User types `xyz` (not an int) → `invalid choice; aborted`.

**Non-mutation:**

- After any session, `sim.entry_count()` and `sim.headword_count()`
  match pre-session values.

Estimate: ~25 tests.

## 9. Deferred

- `show <headword>` command — Phase 2.5.
- Trace bootstrap (`trace <text>`) — Phase 3.
- Demand-graph data structures — Phase 3.
- In-trace hole choices (EXPAND / RECALL / INJECT / SKIP) — Phase 4.
- Worklist / state / cancel — Phase 4.
- Compression at return — Phase 4.
- Command history, readline integration, prompt customisation — TBD.

## 10. Implementation notes for Claude Code

- Put `REPL` in `repl.py`. One class. ~80 lines including handlers.
- Run `pytest test_*.py` after; expected new total is roughly 145
  passing (120 baseline + ~25 new).
- Don't refactor `simulator.py`. The oracle stays as-is.
- The `StopIteration → EOFError` mapping for tests is annoying but
  correct. Alternative: tests always end their input list with `"exit"`.
  Either works; pick one and stick with it.
- Voice: when `print_fn` is invoked with multiple args, the default
  `print` joins with spaces. Tests should match this. The helper
  above does the same join.