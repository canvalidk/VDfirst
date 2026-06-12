# Repository label

- Source file: `vd_reduction_spec.md`.
- Role: Backwards-pass reduction overlay spec for settled demand nodes.
- Implementation status: Implemented (2026-06-10). Decisions taken at
  implementation are recorded in §13.
- Notes: Companion to `2026-06-10-vd-residual-cleanup.md`; open
  decisions are preserved from the source spec.

---

# VD Simulator — Reduction Spec (Backwards Pass)

*Scope: the second half of the backwards pass — replacing the rendered
text of a settled subtree with a human-supplied equivalent form
("5 * 3" → "15"), as an overlay the parent's render picks up
automatically. Additive to `demand.py` / `repl.py`. Companion to the
residual cleanup spec: the two operations share the settled frontier
and interleave there. Status: V1, six decisions committed (vetoable),
four open.*

## 1. What reduction is

The forward pass builds the tree: the user is repeatedly offered open
headwords and expands them, unfolding definitions root-down. The
backwards pass is the human responding to the rendered text. It splits
into exactly two operations:

- **Cleanup** (its own spec) edits the prose *between* holes. Cosmetic;
  structure-preserving by construction.
- **Reduction** (this spec) replaces the rendered text of a whole
  settled node with a shorter equivalent. "5 * 3" → "15".

Reduction is the human executing a residual operator. The `*` in
"5 * 3" is residual-layer machinery the simulator deliberately refuses
to evaluate; reduction is the moment the human evaluates it and records
the outcome. The same primitive covers non-arithmetic collapses — a
meta-typing check resolving to its verdict, a conditional clause
collapsing to its outcome. One operation, whatever the operator.

Why cleanup cannot do this: "5 * 3" lives as
[resolved hole]·[latent " * "]·[resolved hole] — a span *crossing hole
boundaries*. Cleanup's structural guarantee (headwords never in the
input) makes that span unrepresentable in its input by construction.
The property that makes cleanup safe makes it incapable of producing
"15". Hence a second primitive.

## 2. Design: whole-node overlay

> **The unit of reduction is one `Demand` node. The user replaces the
> node's entire rendered text with a supplied string. Nothing finer,
> and nothing is destroyed.**

- **Node granularity.** Sub-node spans would need an addressing scheme
  over rendered text, wrecking the positional stability the demand
  graph is built on. The whole-node render is already a stable,
  nameable thing.
- **Overlay, not mutation.** The subtree beneath is untouched. The
  reduced form is toggleable; the original render is always
  recoverable by clearing it.
- **Order-0 by fiat.** Reduced text is never `analyse`d. No holes can
  spawn from it; the graph cannot grow. Same unrepresentability shape
  as cleanup §2.

**Propagation is free.** Parents render via `child.text()` live, so a
reduction is visible at every ancestor immediately. "Then that goes
backwards into F = 15" requires no backward write — the rendering
recursion already is the backward channel. The backwards pass writes
overlays; the render carries them up.

## 3. Data model

One new field on `Demand`:

```python
@dataclass
class Demand:
    ...
    reduced: Optional[str] = None
```

`text()` short-circuits on it:

```python
def text(self) -> str:
    if self.reduced is not None:
        return self.reduced
    # ... existing rendering unchanged ...
```

Mutators, mirroring `set_compression`:

```python
def set_reduction(self, text: str) -> None:
    if not self.is_resolved:
        raise ValueError(
            "cannot reduce: demand subtree is not fully resolved"
        )
    self.reduced = text

def clear_reduction(self) -> None:
    self.reduced = None
```

**Precedence is emergent, not new logic.** The committed ordering —
`compressed` > child's `reduced` > child's full render — falls out of
the existing call structure: `_render_position` checks the parent's
`compressed` flag *before* ever calling `child.text()`; the `reduced`
check lives inside `text()`. `_render_position` is untouched.
Rationale for the ordering: compression is the parent's rendering
choice about its own hole; reduction is the child's claim about its
own content; the outer choice masks the inner.

**Invariant: `reduced is not None` implies `is_resolved`.** Enforced
at both mutation points. `set_reduction` gates on `is_resolved`
(above). `unresolve` clears `reduced` on the node and every ancestor —
any node whose `is_resolved` goes False holds an equivalence claim
about a render that no longer exists, so the claim is dropped:

```python
def unresolve(self, pos: int) -> None:
    # ... existing pop / orphan logic unchanged ...
    node = self
    while node is not None:
        node.reduced = None
        node = node.parent
```

This is the **one change to an existing method**. Under the current
command set the clause is nearly unreachable (`back` is the only
unresolve path, and there is no downward navigation into resolved
subtrees), but the invariant is kept defensively for future commands.
No existing test sets `reduced`, so existing behaviour is byte-
identical.

Reduction does **not** enter `is_resolved`, `worklist`, `children`, or
`open_positions`. Like `cleaned`, it is metadata over the residual
layer.

## 4. Gate: `is_resolved`, the strong reading

`reduce` is permitted only when the node's `is_resolved` is True — no
open holes anywhere in the subtree. This is deliberately stricter than
cleanup's provisional `is_settled_text` (own holes settled, deeper
descendants may be open). Reducing "5 * {a}" is meaningless; reducing
a node whose *deeper* descendants are open is equally incoherent for
an equivalence claim, in a way that merely grammatical cleanup is not.
Cleanup tidies prose-in-progress; reduction asserts a finished value.

## 5. Guard: headword scan, shared with cleanup

Identical to cleanup §3, for the identical reason: a headword token in
reduced text would be dead text — headword-shaped, untracked, breaking
the premise that a headword-shaped string in the render *is* a tracked
reference.

- Reduced text is scanned with `headword_tokens_in(s)`; an unescaped
  headword token is rejected with the same message shape as cleanup's.
- Exact-token, not concept-level: "net force" (space) passes,
  `net-force` (hyphen) is blocked.
- Same interim escape stance: hard-reject until the tokeniser enforces
  escaping generally.

The helper is specified once, in the cleanup spec; whichever feature
lands first builds it.

## 6. Targets, and the boundary with cleanup

Reduction targets **`Demand` nodes**: the root, expand children, and
inject children.

**Recalled holes are excluded.** A recall stores order-0 text on the
parent (`RecallResolution.text`) with no child node. Cleanup already
owns that surface as its single-string case; "reducing" it would be
the same rewrite with a second record type. One mechanism per surface.

**Order-0 nodes are an honest overlap.** For an order-0 expand or
inject child, cleanup (single-slot edit) and reduction (whole-node
overlay) can rewrite the same string. They differ in record, not
capability: cleanup says *"the original prose, made grammatical"* and
edits the latent in place; reduction says *"I claim this shorter form
is equivalent"* and overlays it, original underneath, toggleable.
Convention: grammar fixes → clean; equivalence collapse → reduce. Not
enforced; the differing records make the choice auditable either way.

**Masking.** A reduced node's latents and descendants are invisible in
every render. Therefore cleanup sweeps and auto-offers skip any target
at or beneath a reduced node (a one-line amendment to the cleanup
spec). A *manual* clean aimed beneath a reduced ancestor proceeds, but
prints: `note: this prose is masked by a reduction at <tag>`.

## 7. Triggers: auto-offer, manual command, sweep

### 7.1 Auto-offer on settle

A single resolution can settle a *chain* of nodes: a recall can settle
the active node, thereby its parent, and so on upward; an order-0
expand or inject child settles instantly and can cascade the same way.
After any successful resolution, the REPL computes the newly-settled
chain (walk from the resolution's owner upward while `is_resolved`)
and offers `reduce` on each, deepest-first.

```
reduce_policy in { on_settle, off }     # default on_settle
```

A separate setting from cleanup's `trigger_policy`; the two fire at
the same moments but toggle independently. Where both fire on the same
node: **reduce is offered first**; accepting it suppresses the cleanup
offer for that node (its latents are now masked); skipping it lets the
cleanup offer proceed. This ordering is a committed default, but the
combined choreography — like cleanup's own trigger question — is
deliberately left to be settled by use.

When the final resolution completes the trace, the offers fire
*before* the completion announcement, so `trace complete.` prints the
post-reduction root render. The endgame line is "F = 15", not the
unreduced sprawl.

### 7.2 Manual `reduce`

Acts on the **active node** — the first command in the simulator whose
operand is the node itself rather than a position, which is correct,
because the unit of the operation is the node.

### 7.3 Sweep — provisionally `fold`

The backwards pass as a command. Walks the scope in **post-order DFS**
(children before parent, left-to-right), offering `reduce` at each
`is_resolved`, unreduced `Demand` node; skips reduced nodes and
everything beneath them. Default scope: the whole tree.

Post-order matters for reading, not for settledness (reduction never
changes `is_resolved`): each node is offered with its descendants'
reductions already folded into its render, so the parent is seen as
"15 …", never "5 * 3 …".

This command also closes a real gap: `worklist` lists open holes only,
so once a subtree settles there is **no navigation surface** to reach
it. The forward pass is `worklist` + `expand`, unfolding root-down;
the backwards pass is `fold` + `reduce`, folding leaves-up. `reduce`
is to `fold` as `clean` is to `tidy`.

A repeated `fold` re-offers anything unreduced (mirrors cleanup's
default stance on skipped-vs-edited).

### 7.4 REPL surface

Additive; no existing line changes.

```
trace> reduce
current render:
  5 * 3
replacement (empty to abort):
  15
reduced.
```

- **Refusals:** `node is not fully resolved` (open holes or open
  descendants); headword rejection mirroring cleanup's message; empty
  input → `reduce aborted: no text` (matches inject's abort wording).
- **`unreduce`** — clears the overlay, prints `unreduced.`; on an
  unreduced node: `node is not reduced`.
- **`state`** — when the active node carries a reduction, one
  additional line after the text: `(reduced)`. A peek-at-original
  command is deferred; `unreduce` + re-`reduce` is the workaround.
- **`set reduce <on_settle|off>`** — sets `reduce_policy`. Whether
  this shares a settings surface with cleanup's `set cleanup` is a
  naming question (§11).
- `worklist` never shows resolved nodes, so it needs no change.

## 8. Addressability (storage deferred)

Every node has a stable address: the sequence of original hole
positions from the root (`[]` = root; `[0, 1]` = the child at pos 1 of
the child at pos 0). Stable because resolutions are keyed by
**original** position — positions never shift — and the demand graph
is a tree, not a DAG. The human layer of a trace therefore serialises
as records keyed by address: reductions as (path, text); cleanups as
(path, slot index) or (path, recall position); compressions as
(path, pos). Recovery is replay over the rebuilt structural tree —
"all the edits in all the same places" was quietly pre-paid by the
Phase-3 commitment to immutable Definiens and original-position keys.

The serialisation format and recovery procedure are a **separate
spec**. This section only establishes that the addresses exist and are
stable.

## 9. What this was verified against the live code

- The `text()` / `_render_position` call structure — the parent checks
  `compressed` before calling `child.text()` — which is what makes the
  precedence ordering emergent rather than new logic (`demand.py`).
- Recall stores text on the parent's resolution with no child node —
  the basis for excluding recalls in §6 (`demand.py`; the same fact
  cleanup §4 rests on).
- `worklist` lists open holes only, hence no navigation surface to
  settled nodes — the reason `fold` must exist (`demand.py` /
  `repl.py`).
- Inject's empty-input abort wording, matched in §7.4 (`repl.py`).

## 10. Out of scope (by decision)

- **No sub-node spans.** The unit is the whole node render.
- **No `analyse` on reduced text; no holes from reduction.** The graph
  cannot grow through the backwards pass.
- **No equivalence checking.** The simulator does not verify that
  5 * 3 = 15. The human is the evaluator; the claim is recorded, not
  audited. A future checker reads (render, reduced) pairs — evaluator
  territory, not simulator territory.
- **No reduction of recalled holes** (§6).
- **No render snapshot at reduce time** in V1 (open, §11.3).
- **No serialisation** (§8).

## 11. Open decisions

1. **`fold` scope variants** — whole-tree only at V1, or also
   `active` / `active_subtree` like `tidy`? Leaning whole-tree only;
   the typical fold moment is trace-complete.
2. **Combined offer choreography** — reduce-then-clean per settled
   node is the committed default; the real answer comes from use.
3. **Render snapshot** — store the render the user reduced against,
   for audit? Without it, the recoverable "original" can drift from
   the seen-at-reduce-time text only via a manual clean beneath a
   reduced ancestor (allowed, but flagged with a note, §6). Leaning
   no: keep the data thin, accept the flagged edge.
4. **Names** — `fold` vs `backpass` vs `reduceall`; and whether
   `set reduce` / `set cleanup` merge into one settings surface.

## 12. Tests

```
# data layer
test_set_reduction_overrides_text
test_set_reduction_rejects_open_hole              # ValueError
test_set_reduction_rejects_open_descendant        # strong gate
test_reduced_propagates_to_parent_render
test_compression_masks_child_reduction            # precedence
test_clear_reduction_restores_full_render
test_unresolve_clears_reduction_up_chain          # invariant
test_reduction_does_not_affect_is_resolved
test_reduction_does_not_affect_worklist

# repl
test_reduce_on_settled_active_node
test_reduce_refused_when_unsettled
test_reduce_rejects_headword_token
test_reduce_empty_input_aborts
test_unreduce_clears_overlay
test_unreduce_refused_when_not_reduced
test_state_marks_reduced_node
test_fold_offers_post_order
test_fold_skips_beneath_reduced_node
test_settle_cascade_offers_deepest_first
test_completion_announces_reduced_root            # "F = 15" endgame
test_existing_output_unchanged_when_unreduced     # regression lock
```

## 13. Resolutions (2026-06-10, at implementation)

1. **`escaped_text` honours reductions.** The short-circuit lives in
   `_render`, so both render pathways show the overlay. Precedent: the
   escaped pathway already honours the compression overlay
   (`compressed` is checked before the escaped branch). Safe for
   re-analysis because the headword guard keeps reduced text
   token-free.
2. **`flatten` triggers settle-offers.** Any resolution that settles
   nodes fires the offer chain; flatten can complete a trace, and the
   §7.1 endgame promise requires it.
3. **Offers are prompt-only.** The on-settle offer is carried in the
   input prompt (showing breadcrumb and current render); EOF or empty
   input skips silently. This is what reconciles the default
   `on_settle` policy with the §12 regression lock: printed output is
   byte-identical unless an offer is accepted, which prints
   `reduced.`.
4. **`fold` keeps its name**; whole-tree scope only at V1; a guard
   rejection during a sweep counts as a skip (re-run `fold` to retry).
5. **No render snapshot** (§11.3): data stays thin.
6. **`set reduce <on_settle|off>`** is its own setting and is
   available outside traces, so the policy can be preset.
7. **`reduce` and `unreduce` record trace events** — every human
   decision lands in the event history, per the address-decision audit
   principle.
8. **The headword guard reuses `sim.analyse(text).headwords`.** The
   tokeniser already masks backtick escapes, so the escape valve is
   live now rather than the interim hard-reject.
