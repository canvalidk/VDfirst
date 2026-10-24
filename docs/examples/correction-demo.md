# Parameterized mistake and correction

The demo combines parameterized-headword instantiation with recorded prediction
claims and selection of current response support. It uses a small example
dictionary; it does not change any Newton dictionary.

```powershell
python correction_demo.py
python correction_demo.py --json > correction-stages.json
```

The dictionary contains:

```text
force_p_t := mass_p times acceleration_p_t
mass_p := supplied mass of p
acceleration_p_t := supplied acceleration of p at t
```

Expanding `force_cart_0` delivers the concrete calls `mass_cart` and
`acceleration_cart_0`. The example supplies `2 kg` and `5 m/s^2` at those
demands. Responses are scripted; the engine performs no arithmetic checking.

## Five stages

| Stage | Current render | Current support | History only |
|---|---|---|---|
| Inputs supplied | `2 kg times 5 m/s^2` | P2, P3 | none |
| Mistake recorded | `12 N` | P2, P3, P4 | none |
| Answer uses mistake | `Prediction: 12 N` | P2, P3, P4, P5 | none |
| Calculation reopened | `2 kg times 5 m/s^2` | P2, P3 | P4, P5 |
| Corrected answer | `Prediction: 10 N` | P2, P3, P7, P8 | P4, P5 |

P4 retains the exact mistaken pair. P5 records the report that consumed it.
Reopening the calculation clears both live overlays, leaving their events
intact. The correction P7 is a fresh response to the original product; P8
reports its result. Every claim, including the correction, is unchecked.

**Replacing an overlay has different provenance.** Going directly from
`12 N` to `10 N` records that those two expressions mean the same thing, and
continues to depend on the earlier claim. Use `unreduce` first to answer the
original product again.

The JSON contains frozen stages, full evidence, transitive event-index
dependencies, current IDs and historical IDs. IDs are local to each trace;
interactive IDs differ because navigation and return events also take indexes.

## Try the same process interactively

```powershell
python correction_demo.py --interactive
```

Enter the following lines. Lines such as `2 kg` and `12 N` answer prompts;
the others are commands. Disabling automatic offers makes this transcript
deterministic.

```text
set cleanup off
set reduce off
trace force_cart_0
expand
inject 0
2 kg
up
inject 1
5 m/s^2
up
reduce
12 N
reduce
Prediction: 12 N
predictions
down 0
unreduce
predictions
reduce
10 N
reduce
Prediction: 10 N
predictions
predictions json
```

`down 0` revisits the settled calculation without deleting its structure.
Reopening it invalidates the report that consumed its old response, so that
report cannot mask the new calculation. Independent sibling calculations stay
intact. Compression also preserves a child's recorded support.

The projection covers response lineage, rather than a minimal semantic proof.
Incomplete or bypassed recording is reported using
`dependency_selection_complete: false`; other claims are then left unassigned
rather than declared history-only. The full prediction-set disjunction,
semantic checks, and theory verdicts remain outside this demo.
