# Repository label

- Source file: `simulator_demand_spec.md`.
- Role: Phase 3 demand graph and trace-state spec.
- Implementation status: Implemented on `main` in `demand.py` and tests.
- Notes: Preserved as historical design context. Current behavior is
  governed by code and tests.

---

# VD Simulator — Demand Graph & Trace State Spec (Phase 3)

*Author: Claude (committing to a design). To be filtered.*

## 1. Scope

The data layer for the trace. Two new types — `Demand` and `Trace` —
plus their operations. No user-facing I/O, no REPL wiring — that's
Phase 4. Pure data and pure functions over it.

Deliverable: `demand.py` containing both types, plus `test_demand.py`.
The REPL stays untouched; Phase 4 will wire it in.

## 2. Architectural commitment

**Demand `Definiens` is immutable; resolutions are stored separately.**

The spec wording (`simulator_spec.md` §4.3) reads as if filling a hole
advances the parent's `Definiens` toward order 0 by mutation. We do
not implement it that way. Each `Demand` carries an immutable
`Definiens` set at creation. Resolutions live in a separate
`dict[int, Resolution]` keyed by **original position** in that
Definiens. Positions never shift; children never need re-keying.

Rationale:

- EXPAND, RECALL, INJECT become structurally uniform — each is a
  decision recorded against an original position. Only the value
  type differs.
- SKIP collapses to "no entry in `resolutions` for that position" —
  no special state.
- Cancel collapses to "remove that key from `resolutions`" — the
  subtree it pointed to becomes garbage.
- The display layer renders by walking original positions and asking
  "is this resolved? if so, how?" — no surprise about which holes are
  current.

The cost: rendering the current state of a partially-resolved Demand
requires walking the resolutions dict, not just calling
`definiens.render()`. Acceptable; it's a display concern.

## 3. Types

### 3.1 `Resolution`

Tagged union (use dataclasses, not strings, to keep the type system
honest):

```python
@dataclass(frozen=True)
class RecallResolution:
    """User chose RECALL: hole filled with literal text from a
    dictionary entry."""
    text: str
    source_index: int  # E-number the text came from
    compressed: bool = False  # paste-raw vs compress-as-headword

@dataclass(frozen=True)
class InjectResolution:
    """User chose INJECT: hole filled with a child demand whose
    Definiens came from user-supplied text."""
    child: "Demand"

@dataclass(frozen=True)
class ExpandResolution:
    """User chose EXPAND: hole filled with a child demand whose
    Definiens came from a dictionary entry."""
    child: "Demand"
    source_index: int  # E-number of the expanded entry
```

`InjectResolution` and `ExpandResolution` differ only in provenance.
The child Demand handles the recursion uniformly; the resolution type
records which surface command produced it.

### 3.2 `Demand`

```python
@dataclass
class Demand:
    definiens: Definiens                # immutable, set at creation
    resolutions: dict[int, Resolution]  # keyed by original position
    parent: Optional["Demand"]          # None for the root
    provenance: "Provenance"            # how this Demand was created
```

Provenance is its own small union:

```python
@dataclass(frozen=True)
class RootProvenance:
    """Demand created by `trace <text>` — root of the tree."""
    text: str  # the user's original input

@dataclass(frozen=True)
class ExpandProvenance:
    """Demand created by EXPAND on a parent hole."""
    source_index: int

@dataclass(frozen=True)
class InjectProvenance:
    """Demand created by INJECT on a parent hole."""
    text: str  # the user's injected text
```

The `_index` fields in resolutions duplicate the child's provenance.
That's deliberate redundancy — resolutions are about "what was chosen
at this hole"; provenance is about "how this Demand came into being."
They happen to agree for EXPAND/INJECT, but the two questions are
separate.

### 3.3 `Trace`

```python
@dataclass
class Trace:
    root: Demand
    active: Demand  # current navigation focus
```

`active` starts at `root` and can move via `up`/`down`. The `Trace`
holds no other state; everything else is derived from walking the
tree.

## 4. Demand operations

All methods are on `Demand` and operate on `self.resolutions`. They
do not return new Demands — Demand is mutable in the resolutions
dict only. Definiens stays frozen.

```python
def resolve_recall(
    self, pos: int, text: str, source_index: int,
    compressed: bool = False,
) -> None: ...

def resolve_expand(
    self, pos: int, child: "Demand", source_index: int,
) -> None: ...

def resolve_inject(
    self, pos: int, child: "Demand",
) -> None: ...

def unresolve(self, pos: int) -> None:
    """Remove a resolution. Used by cancel."""

def headword_at(self, pos: int) -> str:
    """The headword from the original Definiens at this position."""
```

All `resolve_*` methods:
- Raise `ValueError` if `pos` is out of range for `self.definiens.order`.
- Raise `ValueError` if `pos` is already resolved.
- For `expand`/`inject`: set `child.parent = self`.

`unresolve`:
- Raises `KeyError` if `pos` isn't currently resolved.
- Clears the entry. If it was an Expand/Inject, the child's `parent`
  is set to `None` (it's now an orphan, suitable for GC).

### Queries

```python
@property
def open_positions(self) -> list[int]:
    """Positions in the original Definiens not yet resolved.
    Sorted ascending."""

@property
def is_resolved(self) -> bool:
    """All original positions are resolved AND every child Demand
    is itself resolved. Recursive."""

def text(self) -> str:
    """Render the current state.

    Each original position is replaced by:
      - the recall text (compressed → headword name; raw → text)
      - the child's recursive text(), if resolved
      - "{headword}" placeholder, if still open

    Leaves the Definiens object itself untouched."""

def children(self) -> dict[int, "Demand"]:
    """All child Demands keyed by their hole position. Inject and
    Expand resolutions; not Recall."""
```

## 5. Trace operations

```python
@classmethod
def start(cls, sim: Simulator, text: str) -> "Trace":
    """Bootstrap a trace from user text.
    - Calls sim.analyse(text) to get a Definiens.
    - Creates a root Demand with RootProvenance.
    - Sets active = root."""

def up(self) -> None:
    """Move active to active.parent. Raises ValueError if active is
    the root."""

def down(self, pos: int) -> None:
    """Move active to the child at position `pos`. Raises ValueError
    if no child exists at that position (i.e., the position is open
    or resolved by RECALL, not by EXPAND/INJECT)."""

@property
def worklist(self) -> list[tuple[Demand, int]]:
    """Flatten all open positions across the whole tree.
    Each entry is (demand, position). Order: depth-first, left-to-right.
    Default ordering — see open question §10."""

@property
def is_complete(self) -> bool:
    """root.is_resolved."""
```

`cancel` at the trace level isn't a method on `Trace` — it's handled
at the REPL layer by walking up to the appropriate node and calling
`unresolve`. Keep the data layer thin.

## 6. Compression

`RecallResolution.compressed` is a per-position boolean. When `text()`
walks the resolutions:

- `compressed=False`: substitute the recalled raw text.
- `compressed=True`: substitute the headword name (from
  `demand.headword_at(pos)`).

Compression is decided at resolve time. Changing it later requires
unresolve + resolve. Acceptable for v1.

Expand and Inject children do not carry a top-level compression flag —
their text comes from recursing into `child.text()`, which itself
compresses internally per the child's choices.

## 7. Errors

All raised exceptions use Python's standard types:

- `ValueError` — invalid arguments (out-of-range position,
  double-resolution, navigating up from root, navigating down at an
  open position).
- `KeyError` — `unresolve` on a position that isn't resolved.
- `RuntimeError` — invariant violation (a position appears resolved
  but its resolution type is unknown; should never fire). Treat as a
  bug, not user error.

No silent failures. The REPL layer catches and translates.

## 8. Committed design choices

These are open questions in `simulator_spec.md` §8 and CLAUDE.md.
Committing now; filter later.

**Demand mutation model.** Resolutions dict, immutable Definiens.
See §2 for full argument.

**Provenance.** Tagged union per §3. Records `source_index` for
Expand and full original `text` for Root and Inject. Audits can
distinguish dictionary-sourced from user-injected content
unambiguously.

**Worklist ordering.** Depth-first, left-to-right. Same order a
naive recursive descent would produce. If the user wants a different
order, that's a Phase 4 display concern.

**Tree, not DAG.** Two demands cannot share a child. If the same
headword is expanded twice in different positions, two independent
Demand subtrees are created. Sharing would complicate cancel and
provenance for marginal benefit.

**Recall stores text at resolve time.** If the dictionary entry is
later re-defined (a new entry appended for the same headword), the
already-resolved RecallResolution keeps the old text. The trace is a
snapshot of the dictionary's state at trace time, not a live view.
This matches the append-only commitment — the old entry is still
there at its old E-number; the resolution points to it.

## 9. Test contract

`test_demand.py`. No fixtures shared with other tests; build small
Demands directly. Some tests will need a Simulator for `Trace.start`,
but most can construct Demands from hand-built Definiens.

**Construction:**
- A Demand with order-0 Definiens is immediately `is_resolved`.
- A Demand with order > 0 has `open_positions == [0, 1, ..., n-1]`.
- `headword_at(pos)` returns the correct headword.

**Recall resolution:**
- After `resolve_recall(0, "text", source_index=5)`, position 0 is no
  longer open.
- `text()` substitutes the raw text.
- With `compressed=True`, `text()` substitutes the headword name.
- Double resolve at same position → `ValueError`.
- Out-of-range position → `ValueError`.

**Expand resolution:**
- After `resolve_expand(0, child, source_index=3)`, `children()[0]` is
  the child.
- Child's `parent` is set to the host.
- `is_resolved` of host is False until child is resolved.
- After child resolves, host `is_resolved` is True (if it has no
  other open positions).
- `text()` of host recurses into child.

**Inject resolution:**
- Same as Expand but `provenance` on the child is `InjectProvenance`.
- Distinguishable from Expand at the resolution-type level.

**Unresolve:**
- `unresolve(pos)` clears a resolution.
- For Expand/Inject, the child's `parent` is set to `None`.
- Unresolving an open position → `KeyError`.

**Mixed:**
- A Demand with multiple holes can have different resolution types
  at different positions.
- `text()` correctly renders mixed open/resolved state with
  `{headword}` placeholders for open positions.
- Skipping (never resolving) a position leaves it open; the Demand
  is not `is_resolved`.

**Trace:**
- `Trace.start(sim, text)` produces a root with `RootProvenance`.
- `active` starts at `root`.
- `up` from root → `ValueError`.
- `down` to an unresolved position → `ValueError`.
- `down` to an Expand/Inject child works; `up` returns.
- `worklist` lists all open positions across the tree, DFS order.
- `is_complete` is True iff the root is resolved.

**End-to-end:**
- Bootstrap a trace on the small fixture sim, expand a hole, resolve
  the child, confirm parent recursive `text()` reflects it.
- Walk down/up, confirm `active` moves.
- Cancel by `unresolve`ing at the parent, confirm child is orphaned
  and parent's hole is open again.

Estimate: ~35-40 tests.

## 10. Deferred / open

- **`Resolution` for SKIP.** Currently "no entry in the dict." If
  Phase 4 wants to distinguish "user skipped this" from "never
  considered," add `SkipResolution` and have the REPL record it.
- **Save / restore traces.** Out of scope.
- **Trace serialisation.** Out of scope.
- **Read-only views.** A `frozen` flag on `Trace` for completed
  traces? Phase 5+.
- **Definiens equality.** Two recall resolutions of the same text
  from the same source — are they "the same"? Currently no, because
  RecallResolution is frozen dataclass and equality is structural.
  Fine for now.

## 11. Implementation notes for Claude Code

- File: `demand.py`. ~250 lines including docstrings.
- Tests: `test_demand.py`. Probably ~250 lines too.
- Run `pytest test_*.py` after; new total roughly 180 (current 120 +
  ~25 REPL + ~35 demand). If the REPL spec hasn't been built yet,
  the total will be 120 + ~35.
- Don't refactor existing code. `simulator.py`, `engine.py`,
  `residual.py`, `definiens.py` all stay as-is.
- Use `dataclasses` aggressively. The Resolution and Provenance
  unions are small frozen dataclasses; Demand and Trace are mutable
  dataclasses. No abstract base classes needed — duck-typing via
  `isinstance` checks on the union members is fine.
- The `text()` method on Demand is the trickiest. Walk through it
  carefully: for each position in the original Definiens, decide
  what string to substitute. Then build the result by interleaving
  the latents.