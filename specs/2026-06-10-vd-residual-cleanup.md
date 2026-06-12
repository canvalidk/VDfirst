# Repository label

- Source file: `vd_residual_cleanup_spec.md`.
- Role: Residual prose cleanup spec for settled trace text.
- Implementation status: Implemented (2026-06-10). Decisions taken at
  implementation are recorded in §11.
- Notes: Companion to `2026-06-10-vd-reduction.md`.

---

# VD Simulator — Residual Cleanup Spec

*Scope: a trace operation that lets the user clean up the prose
(residual) around a resolved hole without disturbing any headword
structure, offered automatically (opt-out) at settled resolutions and
available manually (opt-in) as a sweep. Additive to the existing
`demand.py` / `repl.py`. Cannot change the demand graph's structure —
by construction, not by check.*

## 1. The problem this solves

In Design 2 the trace renders prose by substituting entry text into
holes. The grammar breaks at **seams** — the join between a parent
latent string and a child's resolved text. Observed in the Sun–Earth
run: `point-particle` resolved to "An idealised object whose spatial
extent and internal structure are neglected.", which the parent spliced
as "For a An idealised object…". Left unchecked across many
resolutions, the rendered prose grows ungrammatical and eventually
unreadable.

The fix is to let the user rewrite the **residual** (the latent strings)
around the headwords, periodically, so the mess never accumulates beyond
one resolution-worth before it can be flattened.

## 2. Design: edit latents directly, headwords never in the input

The earlier approach (take a whole free-text string, re-`analyse` it,
reject if the headword list changed) is **abandoned**. It let words that
happen to be headwords leak into prose and become new holes, and it
forced the user to reproduce the entire headword skeleton — including
duplicates and order — in their rewrite. Several real entries repeat
headwords (e.g. E14 has `uniform-motion` three times), making that
burden severe.

Instead:

> **Cleanup edits the latent strings directly, one per gap. The
> headwords are never part of the input — they are fixed dividers
> between the editable gaps.**

A residual of order *n* has *n+1* latent strings around *n* headword
holes. Cleanup presents those *n+1* slots and takes back *n+1*
replacement strings. The headwords cannot be touched because they are
never handed to the user.

This makes the structural guarantee *unrepresentable-otherwise*, not
merely checked:

- Headword count, order, and multiplicity are structurally untouchable —
  the headword list is never reconstructed from input.
- No `analyse` is run on the input, so no headword-word can be
  tokenised into a new hole. The graph cannot grow.
- "No structural change" (§9) is therefore a **guarantee**, not an
  invariant that must be verified after the fact.

Slot count scales with headword density automatically:

- **Order-0 text** (e.g. the `point-particle` recall — pure prose, no
  holes) is **one editable string**. The user rewrites freely.
- **Order-*n* text** (e.g. an expanded E24, four headwords) is **five
  editable gaps** around four pinned, untouchable headwords.

Empty latents are still presented as editable gaps (a leading/trailing
"" around a headword at the very start/end of the text). This is
intended — sometimes the grammar fix is adding a word before a leading
headword.

## 3. The one check that remains: no headword-words in prose

Structure cannot change (§2). But there is a separate, semantic concern:
a user could type a headword *word* into a gap as ordinary prose — e.g.
cleaning the `point-particle` recall to "An idealised **point-particle**
with negligible size." Because cleanup never analyses the input, that
string stays **dead text**: not a hole, no resolution, not in any
worklist, invisible to the graph. Structurally harmless.

But it is semantically harmful. The VD's premise is that a
headword-shaped string in the rendered text *is* a tracked reference. A
dead headword-word looks identical to a real one while being untracked,
so a later reader (human, future analyser, the evaluator) can no longer
trust that a headword-shaped token corresponds to an edge. The rendered
text and the graph would silently disagree.

So cleanup keeps **one** guard — lighter than the abandoned one, and
different in purpose:

> **Each supplied latent is scanned for headword tokens. An unescaped
> headword token is rejected.** This protects against tracked tokens
> leaking into prose as dead text. It is *not* a structural check.

```
clean(target, new_latents):
    assert len(new_latents) == target.order + 1          # arity, not semantics
    for s in new_latents:
        hits = headword_tokens_in(s)                     # see notes
        if hits:
            reject(f"{sorted(hits)} are headwords; cleanup edits "
                   f"non-headword prose only. To use the word "
                   f"literally, escape it; to reference it, expand.")
            return UNCHANGED
    target.set_latents(new_latents)                      # see §4 for the two targets
    target.cleaned = True
    return CLEANED
```

Notes on the check:

- **`headword_tokens_in(s)`** reuses the tokeniser's headword-matching
  (the machinery behind `tokenise_definition`), restricted to the
  headword set — *not* `analyse`, since no position-slicing or Definiens
  is needed. Just: which headword tokens occur in this string.
- **Exact-token, not concept-level** (documented property, Issue F). The
  hyphen/underscore discipline means "net force" (space) is *not* the
  headword `net-force` (hyphen), so a user may write the concept in
  ordinary prose freely; only the canonical hyphenated/underscored token
  is blocked. This is the intended consequence of the token conventions,
  not a leak.
- **Escape valve.** An escaped headword token (backtick-style, per the
  rule ledger's stubbed escape mechanism) means "the word, not the
  reference" and is allowed through as deliberate prose. Until the
  tokeniser actually enforces escaping, the interim behaviour is a hard
  reject of any unescaped headword token (see §10.3).
- **The arity `assert` is structural, not a user-facing guard** — it can
  only fail on a programming error (wrong slot count passed), never on
  user content. User content failures go through the headword scan only.

## 4. Two targets: where the prose actually lives (Issue H)

The prose to be cleaned lives in **two different places** depending on
how the hole was resolved. `clean()` dispatches on which:

- **Expanded hole** → expanding creates a child `Demand`; the entry
  prose lives in that **child's** `definiens.latent`. Cleanup edits the
  child node's latents. This is the order-*n* slot-list case.
- **Recalled hole** → recall creates **no child**; it stores the entry
  text as a string in `RecallResolution.text` on the **parent's**
  resolution dict. Cleanup edits that string. Since recall text carries
  no tracked sub-holes, this is always the **order-0, single-string**
  case.
- **Injected hole** → inject creates a child `Demand` from the injected
  text (`InjectProvenance`); its latents live in that child, like
  expand. Slot-list form per its order (usually order 0 for a typed-in
  value).

So `target` in §3 is either a `Demand` (expand/inject child) or a
`RecallResolution` (recall). `target.order` is `definiens.order` for a
`Demand` and `0` for a `RecallResolution`; `target.set_latents` writes
`definiens` (rebuilt with the original headwords) for a `Demand` and
`.text = new_latents[0]` for a `RecallResolution`.

This is the gap the earlier draft missed: it assumed a single target
(`node.definiens`), which is wrong precisely for the recall case that
motivated the whole feature.

```
def clean_target_for(parent, pos):
    res = parent.resolutions[pos]
    if isinstance(res, RecallResolution):
        return RecallTarget(res)        # order 0, edits res.text
    if isinstance(res, (ExpandResolution, InjectResolution)):
        return NodeTarget(res.child)    # order n, edits child.definiens.latent
    raise RuntimeError(...)
```

Both targets run the identical §3 headword scan; they differ only in
arity and in which field `set_latents` writes.

## 5. New node state

One new field, on whatever holds editable prose:

```
cleaned: bool = False     # has this target's prose been edited?
```

- On a `Demand`: a normal field.
- On a `RecallResolution`: the resolution is `frozen=True`, so `cleaned`
  is tracked **beside** it (e.g. a `set[int]` of cleaned recall
  positions on the parent `Demand`, keyed by hole position) rather than
  mutated on the frozen record. Implementation detail; the spec only
  requires that "has this recall text been cleaned?" is answerable.

Set `True` by `clean()` on success. Drives the sweep (§6.2) so it knows
what it has already offered. Does **not** enter `is_resolved` or any
structural computation — it is metadata over the residual layer only.

## 6. Two triggers, one primitive

### 6.1 Auto-prompt (opt-out, default on)

After a resolution, the REPL offers cleanup on the just-resolved target.
The user edits or presses through; the cheap default is **skip** (leave
prose as-is, do not set `cleaned`). The opportunity arriving every time
is what bounds the mess.

**Whether the prompt fires is a swappable setting** — an empirical
question (cleaning an expand child's prose may be premature, since its
holes will fill beneath it), deliberately left to trial-and-error:

```
trigger_policy in {
    on_settled_only,     # fire after recall / inject only      (default)
    on_every_resolution, # fire after expand too
    off,                 # no auto-prompt; manual command only
}
```

`on_settled_only` is the default: auto-offer cleanup only when the
resolution produces settled prose (recall, inject), where the text is in
final shape. Expanded nodes are cleaned later — via the manual sweep, or
once their subtree completes. This is the instinct, not a commitment;
the setting exists so the answer can be found by use. The primitive is
identical across all three settings; only the firing predicate differs.

### 6.2 Manual sweep (opt-in, always available)

A command — provisionally `tidy` — the user invokes whenever they want.
Default target: **all settled, uncleaned prose in the current subtree**
(the active node's descendants, plus the active node), offered one at a
time.

```
tidy(scope = active_subtree):
    targets = [ t for t in walk_prose(scope)
                if t.is_settled_text and not t.cleaned ]
    for t in targets:
        offer clean(t, ...)        # user edits or skips each
```

- **`walk_prose`** visits both kinds of target: each `Demand`'s own
  latents, and each `RecallResolution.text` hanging off resolved
  positions.
- **`is_settled_text`** — see §10.1 (open). Provisionally: a target
  whose own holes are all resolved by recall/inject (no open holes, no
  expand children still resolving beneath it). Order-0 targets (all
  recalls, most injects) are trivially settled.
- **Scope variants**: `active`, `active_subtree` (default), `all`. Start
  with `active` and `active_subtree`; add `all` if wanted.
- The `cleaned` flag lets a repeated sweep skip what it already offered,
  so `tidy` does not re-pester. (Open: distinguish skipped vs edited —
  §10.2. Default no; a sweep re-offers anything not `cleaned`.)

## 7. REPL surface

Additive. Existing commands and output lines unchanged.

- **Auto-prompt** — after a resolution (per `trigger_policy`), show the
  target's current latents as *n+1* labelled gaps with the headwords
  pinned as fixed dividers between them; invite an edit per gap; empty
  input on a gap = keep that gap. On submit, call `clean()`; on
  rejection (headword-word in a gap), show the §3 message and re-offer.
- **`tidy [scope]`** — runs the §6.2 sweep, presenting each target in the
  same gap-wise form.
- **`set cleanup <policy>`** — sets `trigger_policy`
  (`on_settled_only` | `on_every_resolution` | `off`).

Non-interference: no existing line format changes; `worklist`, `state`,
`expand`, `recall`, `inject` render exactly as before — none reads
`cleaned`, and editing latents leaves holes, headwords, and resolutions
untouched.

## 8. What this run-verified against the live code

- The headword scan distinguishes hyphenated tokens from spaced prose
  ("net-force" flagged, "net force" not) — confirmed via `analyse`.
- Recall stores text on `RecallResolution.text` with no child; expand
  stores prose on a child `Demand`'s definiens — confirmed against
  `demand.py`, and is the basis for §4's two-target dispatch.
- A node's own latents are unaffected by descendant resolution (only the
  live-rendered `text()` changes) — which is why the earlier
  reopen-instrumentation could not fire and has been cut (was §7).

## 9. Out of scope (by decision)

- **No structural change.** Guaranteed by §2 (headwords never in input),
  not merely checked. Cleanup cannot open, close, reorder, reparent, or
  add holes. Structural change is expand/inject/unresolve.
- **No graph growth via prose.** The §3 scan prevents headword-words
  entering prose as dead text; no `analyse` is run on input, so prose can
  never spawn holes.
- **No seam-level edit.** The unit is one target's latents, not the join
  between two nodes. A seam is fixed by editing the latents on one side.
- **No equation-operability.** Design 2/2.1 prose hygiene, not the
  evaluator's equation-operable entries. Cleanup makes prose read; it
  does not make it computable.
- **No headword-identity logic.** The scan matches headword tokens
  exactly as the tokeniser does; underscore-glued tokens are atomic.

## 10. Open decisions

1. **`is_settled_text` exact definition** — "all own holes resolved by
   recall/inject" vs "subtree fully resolved." The former lets a target
   be cleaned while deeper descendants are still open; the latter waits.
   Leaning former (more opportunities, finer grain). Confirm before
   building.
2. **Skipped vs edited distinction** (§6.2) — whether a sweep re-offers
   skipped targets. Default no; revisit by use.
3. **Escape enforcement timing** (§3) — honour backtick-escape for
   deliberate headword-words now, or hard-reject all headword-words until
   the tokeniser enforces escaping generally. Interim: hard-reject.
4. **Command name** — `tidy` vs `grammar` vs other. `clean` is taken by
   the primitive. `tidy` provisional.

## 11. Resolutions (2026-06-10, at implementation)

1. **`is_settled_text` = the node's own holes are all resolved**, by
   any resolution type; deeper descendants may still be open (the
   §10.1 lean — finer grain). Cost accepted: a deep change can
   re-break a cleaned seam; the sweep will not re-offer it, but
   `tidy active` will (see 2).
2. **No skipped-vs-edited distinction.** A sweep re-offers anything
   not `cleaned`. `tidy active` is the manual override: aimed at a
   node, it re-offers even cleaned and masked targets.
3. **Escape valve live.** The headword scan reuses
   `sim.analyse(text).headwords`; the tokeniser already masks
   backtick spans, so escaped headword-words pass as deliberate prose
   — no interim hard-reject.
4. **Name `tidy`**, scopes `active | subtree (default) | all`.
5. **Auto-offers are prompt-only** (same rationale as reduction §13.3:
   reconciles the default-on policy with the no-output-change lock).
   EOF or empty keeps. Recall → always offered (text is order-0);
   inject → only when the child settles; expand → only under
   `on_every_resolution`. Default policy `on_settled_only`.
6. **Choreography**: reduce offers fire first; cleanup offers are
   suppressed when the target sits at or beneath a reduced node.
   Sweep scopes skip masked subtrees silently; `tidy active` proceeds
   with the §6 masked-note.
7. **V1 limitation**: empty input keeps a gap, so a latent cannot be
   interactively blanked to "".
8. **Data layer on `Demand`**: `set_latents` (arity-checked, rebuilds
   the Definiens with original headwords, marks `cleaned`) and
   `clean_recall_text` (rebuilds the frozen record, tracks the
   position in `cleaned_recalls` per §5). Both paths record `clean`
   trace events with the location tag (plus position for recalls).
