# Repository label

- Source file: `simulator_spec.md`.
- Role: Base simulator/MVP inspection-layer spec.
- Implementation status: Implemented on `main`; later REPL, demand, and
  trace specs extend this design.
- Notes: Preserved as historical design context. Current behavior is
  governed by code and tests.

---

# VD Simulator — Specification

*Author: Claude (committing to a design). To be filtered.*

## 1. Purpose

The simulator is the human-facing interface to a Valid Dictionary
instance. It does two things:

1. **Inspection** — query the dictionary's contents.
2. **Tracing** — walk through a definition recursively, with the
   human supplying residual-layer judgments at the boundary.

These share data structures but not state. Inspection is read-only and
side-effect-free. Tracing builds and mutates a graph.

## 2. Data model

The simulator manipulates two types from elsewhere in the system:

- **Residual** (`vd/residual.py`) — neutral textual machinery: latent
  strings + holes by position. Nothing else.
- **Definiens** (`vd/definiens.py`) — a Residual paired with a list of
  headwords parallel to its holes. This is what the tokeniser produces
  and what the simulator passes around.

The simulator's own central type is the **demand graph**: a directed
tree of demand nodes. Each node carries a Definiens. Edges represent
"this demand was spawned to fill that hole in its parent."

A demand is *open* if its Definiens has order > 0 (holes remain) or if
any of its children are open. A demand is *resolved* when its
Definiens reaches order 0 by filling all holes — directly via the
user, or transitively via children resolving and folding their text up.

## 3. Engine interface

The engine is a read-only oracle. The simulator depends on these
capabilities and nothing else from it. Status as of writing:

- `list_headwords() -> list[str]` — dictionary-wide headword list.
  *Status: TBD (need to check engine.py).*
- `entry_count() -> int` — total entries.
  *Status: TBD.*
- `entries_for(headword) -> list[Entry]` — all entries with this
  headword, in dictionary order. Each Entry exposes its E-number and
  raw definition text.
  *Status: TBD.*
- `analyse(text) -> Definiens` — ordered tokenisation of arbitrary
  text against the current headword set. Latents are the literal
  chunks; headwords are the references at each hole position.
  *Status: missing. The current `tokenise_definition` returns sets and
  discards order. To be added.*

No engine call mutates dictionary state.

## 4. User-facing operations

The user has access to **inspection commands** (always available) and,
when inside an active trace, **hole choices** at each open hole.

### 4.1 Inspection commands

Always available. Do not touch graph state.

- `headwords` — list all headwords.
- `count` — entry count and headword count.
- `show <headword>` — list the entries for a headword (E-numbers +
  short identifiers). If only one entry, show it directly.
- `recall <headword>` — return the text of an entry. If multiple
  entries, prompt the user to pick by E-number.

`recall` is the inspection version of the internal RECALL primitive.
It returns text and stops. It does not start a trace.

### 4.2 Trace bootstrap

`trace <text>` starts a new trace.

- The text is `analyse`d into a Definiens.
- A root demand node is created with that Definiens.
- The simulator enters trace mode: the prompt changes; the worklist of
  open demands is shown; the user is offered hole choices.

The text can be a single headword (resulting Definiens has one hole)
or arbitrary free text (Definiens may have several holes, or none if
no headwords matched).

### 4.3 Hole choices

When the user is inside a trace and addresses an open hole, the
options are:

- **EXPAND** — spawn a child demand. The simulator recalls the
  headword's entry (prompting the user to pick if multiple), analyses
  the entry's text into a Definiens, and creates a child demand node
  carrying it. The child becomes the active context.

- **RECALL** (in-trace) — fill the hole with the recalled text as a
  literal, no recursion. If the headword has multiple entries, the
  user picks. The hole closes; the parent's Definiens advances by one
  position toward order 0.

- **INJECT** — the user types replacement text. The text is analysed
  into a Definiens; that Definiens fills the hole. Headwords inside
  the injected text become new open holes on the parent (because
  fill of higher-order Definiens is order-additive).

- **SKIP** — leave the hole open and address a different one. The
  worklist will surface it again later.

EXPAND and INJECT are the two graph-creating moves. EXPAND uses the
dictionary's content; INJECT uses the user's. RECALL and SKIP do not
create children.

### 4.4 Trace control

- `cancel` — abort the current expansion subtree. All descendants of
  the current node are discarded; the parent's hole returns to open.
- `cancel trace` — abort the entire trace; discard the graph.
- `up` — move the active context to the parent.
- `down <position>` — move the active context to the child at that
  hole position.
- `worklist` — show all open demands in the current trace.
- `state` — show the current node's Definiens, rendered.

## 5. Internal primitives

Used by the simulator to implement the operations above. Not directly
exposed to the user.

- **RECALL**(headword) → text. Calls `entries_for`. If one entry,
  returns its text. If multiple, prompts the user; returns the chosen
  entry's text. Returns nothing else.
- **ANALYSE**(text) → Definiens. Calls `engine.analyse`. Pure.
- **EXPAND-headword**(headword) → child demand. RECALL + ANALYSE, then
  create a node carrying the resulting Definiens.
- **EXPAND-text**(text) → fills hole. ANALYSE, then fill the parent
  hole with the resulting Definiens.

EXPAND-headword and EXPAND-text are the only operations that mutate
the graph. The dispatch between them happens at the surface: EXPAND
on a hole uses the hole's headword (EXPAND-headword); INJECT uses the
user's text (EXPAND-text).

## 6. Resolution and compression

When a child demand reaches order 0, its Definiens has a `text`. That
text needs to fold up into the parent's hole. Two choices, presented
to the user at resolution time:

- **Paste raw** — the parent's hole is filled with the child's full
  resolved text.
- **Compress** — the parent's hole is filled with a compressed form
  (the headword name itself, or a user-supplied abbreviation). The
  full subtree remains in the graph as provenance.

This is the only place the user makes a decision *about how the trace
records itself*. All other choices are about content.

## 7. Bunch / session lifecycle

A session opens with no active trace. The user runs inspection
commands or starts a trace with `trace <text>`. While a trace is
active, inspection commands stay available and do not affect trace
state.

A trace ends when:

- the root demand resolves (success), or
- the user runs `cancel trace` (abandonment), or
- the user starts a new trace (the previous one is discarded; future
  spec may add save/restore).

## 8. Open questions

These are explicitly not committed. Each requires a decision before
its part of the simulator can be built.

1. **Trace-architecture judgments.** Free-particle identification,
   dispatch resolution, closure judgments — these are residual-layer
   inputs that don't fit cleanly into "fill a hole with text." They
   may need their own choice category at certain hole types, gated by
   the headword being expanded. Out of scope for the v1 simulator;
   in scope for the eventual logic tracker.

2. **Multi-entry RECALL prompt.** When `entries_for(h)` returns
   several entries, what does the chooser show? Just E-numbers? A
   short identifier? The first line of each definition? Pending UX.

3. **Inject and provenance.** When the user injects free text, the
   resulting Definiens has no link to a dictionary entry. The graph
   should record "this came from user injection" so audits can find
   residual-layer interventions. Format TBD.

4. **Save/restore traces.** Out of scope for v1. Listed so it doesn't
   get forgotten.

5. **Worklist ordering.** Open demands could be presented oldest-first,
   newest-first, or by depth. v1 default unspecified.

6. **Multi-trace sessions.** v1 assumes one active trace at a time.
   Multiple parallel traces are deferable.