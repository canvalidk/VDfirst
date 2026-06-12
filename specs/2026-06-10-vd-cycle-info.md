# Repository label

- Source file: `vd_cycle_info_spec (1).md`.
- Role: Cycle-information surfacing during trace work.
- Implementation status: Implemented (2026-06-10).
- Notes: Additive demand/REPL surface. The headword-identity decision
  is resolved: exact-string match (see §7).

---

# VD Simulator — Cycle Information Spec

*Scope: surfacing "you are going in circles" information to the user
during a trace. Additive to the existing `demand.py` / `repl.py`. No
behavioural change to existing operations.*

## 1. What "cycle" means here

There is no recursion to run away. `expand` is one user-driven
mutation, and `worklist` recomputes from the tree on every call. A
"cycle" is purely descriptive:

> **the headword at an open hole already appears as the headword of an
> open hole on an ancestor demand**, reached through the `parent` chain.

It is the "you're going in circles" signal, surfaced as information.
The user remains free to expand into it; nothing blocks. This realises
the agreed decision: track cycles to *inform* the user, never to
prevent the loop.

The repo already has everything needed to compute this:
`Demand.parent`, `Demand.headword_at(pos)`, `Demand.open_positions`.
No new state on `Demand`, no change to resolution logic, no change to
`is_resolved` or `worklist`.

## 2. Design constraints

1. **`demand.py` stays mechanical.** Per the mechanical/residual split
   and "read-only simulator over engine," cycle detection is a *read*
   over existing structure. It must not mutate `Demand`, must not touch
   `resolutions`, and must not affect `is_resolved` or `worklist`. It
   lives as a pure method computing on read — never a stored flag.

2. **Ancestor, not whole-tree.** The signal is "this headword is open
   *above me* on my current path." A sibling subtree containing the
   same open headword is reuse, not a circle. The walk is strictly
   `parent`-ward, not the full `worklist`. Keeps it O(depth).

3. **Headword identity is the match key.** A cycle is the same headword
   recurring on the path. Match on the exact string `headword_at(pos)`
   returns — no normalisation, no qualifier-stripping. Whether
   underscore-qualified variants (e.g. `canonical-force_acting-object`
   vs bare `acting-object`) should collapse to the same cycle is a
   separate tokeniser-level decision; default here is exact match,
   which is conservative and will not over-report.

4. **Open-hole match, not resolved.** Only ancestors with the headword
   *still open* count. If an ancestor already resolved that headword,
   there is no live circle. Match against the ancestor's
   `open_positions` only.

## 3. New code

### 3.1 `demand.py` — one pure method on `Demand`

```python
def ancestor_cycle(self, pos: int) -> Optional["Demand"]:
    """The nearest ancestor with this hole's headword still open.

    Returns the ancestor Demand whose own open holes include the
    headword demanded at `pos` here, walking parent-ward. None if no
    such ancestor exists. Pure read; mutates nothing.
    """
    self._check_position(pos)
    target = self.headword_at(pos)
    node = self.parent
    while node is not None:
        for open_pos in node.open_positions:
            if node.headword_at(open_pos) == target:
                return node
        node = node.parent
    return None
```

Rationale:

- **Method on `Demand`, not `Trace`** — needs only `parent` and the
  demand's own headwords, both intrinsic. Mirrors `children()`,
  `open_positions`, `text()`.
- **"Nearest" (return on first match)** — if the headword recurs at
  multiple depths, the closest closing ancestor is the relevant circle.
- **Returns the demand, not a bool** — lets the REPL show *where* the
  circle closes via existing `_location_tag` / `_breadcrumb`.
- **Reuses `_check_position`** — same `ValueError` on a bad position as
  every other positional method; no new error surface.

### 3.2 Optional companion — full path (hold back unless needed)

Only if the display wants to *show the loop* rather than just flag it:

```python
def cycle_path(self, pos: int) -> list["Demand"]:
    """Ancestors from self up to and including the cycle-closing
    ancestor, or [] if no cycle. Pure read."""
    closer = self.ancestor_cycle(pos)
    if closer is None:
        return []
    path = []
    node = self.parent
    while node is not None:
        path.append(node)
        if node is closer:
            break
        node = node.parent
    return path
```

Defer until the REPL display actually needs it. `ancestor_cycle` alone
covers the flag.

## 4. REPL surface

Both touch points are **additive** — no existing line changes, so no
existing `test_repl_trace.py` assertion breaks. Rule: only add lines,
and only conditionally.

### 4.1 `worklist` — mark cyclic holes

Current line format (from `test_repl_trace.worklist_line`):

```
{marker} [{index}] {tag:<12} pos {pos}  ->  {{{headword}}}
```

Append a suffix *only when* `ancestor_cycle(pos)` is non-None:

```
* [3] E22          pos 0  ->  {acting-object}  (cycle: open at E15)
```

In `cmd_worklist`, inside the existing loop, after computing
`headword`:

```python
suffix = ""
closer = demand.ancestor_cycle(pos)
if closer is not None:
    suffix = f"  (cycle: open at {self._location_tag(closer)})"
self.print_fn(
    f"{marker} [{index}] {tag:<12} pos {pos}  ->  "
    f"{{{headword}}}{suffix}"
)
```

**Non-interference:** every existing worklist test uses acyclic
entries, so `suffix` is `""` and output is byte-identical to the
current `worklist_line` helper.

### 4.2 `expand` — warn but proceed

`expand` does **not** refuse. It prints a notice *before* the existing
confirmation line when a cycle is present, then proceeds unchanged.

In `cmd_expand`, after `headword = active.headword_at(pos)`:

```python
closer = active.ancestor_cycle(pos)
if closer is not None:
    self.print_fn(
        f"note: '{headword}' is already open at "
        f"{self._location_tag(closer)}; expanding will revisit it."
    )
# ... unchanged: _pick_entry_index, analyse, resolve_expand, etc.
```

Additive: existing expand tests expand non-cyclic headwords, so the
notice never fires.

**Verify before implementing:** grep `test_repl_trace.py` and
`test_demand.py` for any fixture where an ancestor and descendant share
an open headword. If one exists, that test's expected output list needs
the new line added. (Known Newton fragments in the read tests are
acyclic, but confirm rather than assume.)

## 5. Out of scope (by decision)

- No blocking, no refusal, no `Halt` — consistent with the agreed
  decision.
- No new field on `Demand`, no `FORCING` state — the `parent` walk *is*
  the marker, computed on read. There is no marker to store because the
  structure already encodes it.
- No change to `worklist`, `is_resolved`, `children`, or any resolution
  method.
- No tokeniser-level headword-identity logic — exact-string match only.

## 6. Tests

```
test_ancestor_cycle_none_when_unique          # no shared headword up-chain
test_ancestor_cycle_finds_open_ancestor       # parent has it open -> parent
test_ancestor_cycle_skips_resolved_ancestor   # ancestor resolved it -> None
test_ancestor_cycle_returns_nearest           # two depths -> closer one
test_ancestor_cycle_ignores_siblings          # sibling subtree -> None
test_ancestor_cycle_bad_position_raises       # parity with _check_position
test_worklist_marks_cycle_suffix              # REPL line gets suffix
test_worklist_no_suffix_when_acyclic          # regression: exact old output
test_expand_warns_on_cycle_then_proceeds      # notice prints, expand happens
```

The two regression tests (`no_suffix_when_acyclic`, expand-acyclic)
lock in non-interference.

## 7. Open decision (blocks implementation)

The headword-identity question in §2.3. Default is exact-string match
(conservative, no false cycles). If underscore-qualified variants
should collapse to the same cycle, that changes the match key and must
be settled first, as it is a dependency.

**Resolved (2026-06-10): exact-string match.** Token Prop 3, the
active authoring guide, treats underscore-qualified names as atomic
tokens distinct from their bare forms ("underscore qualifier
overlap... is correct and intentional"). The cycle key follows
tokeniser identity: the demand graph already distinguishes
`canonical-force_acting-object` from `acting-object`, so collapsing
them in cycle reporting would assert an identity the tokeniser denies.
Implemented as exact match in `Demand.ancestor_cycle`.
