# ADR 2: RECALL Is A Composed Operation

- Status: Accepted
- Date: 2026-05-28

## Context

Some cleanup designs would make every operation tiny. But `RECALL` naturally
does several things: find entries for a headword, handle absent entries, choose
among multiple entries, and return the selected text.

There is also a conceptual reason to keep `RECALL` as a meaningful operation:
it is meant to mirror how people recall information in their own minds. A
person engages with a headword, finds candidate meanings or memories, selects
the relevant one, and brings that content into the current thought. The
simulator's recall operation should preserve some of that shape rather than
collapsing it into a bare dictionary lookup.

## Decision

Allow `RECALL` to remain a longer semantic operation that composes smaller
dictionary primitives and may prompt for multi-entry choice.

The smaller primitives should still exist:

- `entry_indexes(headword)`
- `entry_text(index)`
- `entry_headword(index)`

## Consequences

`RECALL` remains human-usable and maps cleanly to the simulator workflow.
It also keeps room for future designs where headword engagement, candidate
selection, and recalled content are important parts of the trace.

`EXPAND` can be understood as `RECALL + ANALYSE + attach child`.

In-trace recall can be understood as `RECALL + fill active hole with literal
entry text`.

## Links

- `../../specs/2026-05-28-simulator-role-cleanup-segment-1.md`
- `../../repl.py`
