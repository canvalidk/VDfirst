# Glossary

This is a living glossary for Code-facing work. Theory may later replace or
refine these definitions.

## ANALYSE

The operation that takes text and the current headword set, then returns a
`Definiens` whose holes correspond to headword matches in position order.

## Definiens

A `Residual` paired with a parallel list of headwords, one per hole.

## Demand

A trace node containing a `Definiens` plus resolutions for its original holes.

## FLATTEN

Proposed trace-level operation that resolves open holes on the active demand as
inert literal headword strings.

Initial implementation: flattened literals display normally, and
`escaped_text()` emits them with backticks so later analysis does not detect
them as headwords.

## Trace Event

A small recorded trace/evaluator event. The first implementation records trace
start, expand, recall, inject, and flatten events. This is a precursor to the
future human-input audit ledger.

## Human Input

A human contribution requested by the evaluator because the current demand
cannot be mechanically supplied by the entries alone.

## RECALL

Composed dictionary operation that resolves a headword to a selected entry
index and entry text, possibly asking the user to choose among multiple
entries.

Design intent: recall should preserve the shape of a person engaging with a
headword in thought: candidate meanings become available, one is selected, and
its content is brought into the current context.

## Residual

Literal text segments with positional holes between them. It does not know
which headwords the holes refer to.

## Simulator

The research instrument currently being built in Code. Its job is to prove the
trace architecture, not to be the final polished LLM-facing product.

## Trace

The demand tree and active evaluation context produced while exploring or
evaluating text through the simulator.
