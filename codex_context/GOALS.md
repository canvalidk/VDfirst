# Goals

## Project-Level Direction

VD is being developed across Theory, Newton, and Code. The long-term
direction includes an LLM-compatible Newton tool: a domain-specific
"abacus" that helps an LLM solve mechanics questions faster and with full
assumption accounting.

The simulator is not that final product. It is the research instrument used
to prove that the trace architecture works.

## Immediate Code Goal

Finalize a simulator proof of concept that can support convincing traces.
For now, correctness of the conceptual machinery matters more than speed,
interface polish, or a fully general Newton solver.

The simulator should eventually demonstrate:

- entry-driven expansion of definitions;
- lazy demand propagation;
- degree-0 return behaviour up the demand tree;
- typed human inputs generated only when demanded;
- audit records for human inputs;
- Newton entries improving until the trace can solve representative Newton
  problems from the VD structure.

## Current Working Hypothesis

The existing implementation has useful bones:

- `engine.py` builds the dictionary, tokenises definitions, and analyses text.
- `residual.py` and `definiens.py` represent text with headword holes.
- `demand.py` stores the trace tree and per-position resolutions.
- `simulator.py` is a read-only oracle over a VD instance.
- `repl.py` exposes inspection and trace commands.
- `newton.py` is the current Newton case study.

The likely next design step is not a polished UI. It is adding evaluation
stack semantics and audit-worthy human input records to the simulator.

## Long-Term Product Possibility

The future LLM-facing tool should let an LLM operate the VD machinery rather
than merely ask it for answers. The engine should hold the demand structure,
entry provenance, trace state, and assumption ledger; the LLM can supply
interpretive and modelling judgments at explicit handoff points.

