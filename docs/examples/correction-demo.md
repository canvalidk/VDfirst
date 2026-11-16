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
`acceleration_cart_0`. A value is never typed at a headword, so each of those
is expanded into its definition and the value (`2 kg`, `5 m/s^2`) replaces the
definition's text. Responses are scripted; the engine performs no arithmetic
checking.

In the text, a bare headword is still to be expanded and braces stand round one
that has been dealt with.

## Five stages

| Stage | Current render | Current support | History only |
|---|---|---|---|
| Inputs supplied | `{{2 kg} times {5 m/s^2}}` | P0 to P7 | none |
| Mistake recorded | `{12 N}` | P0 to P8 | none |
| Answer uses mistake | `Prediction: 12 N` | P0 to P9 | none |
| Calculation reopened | `{{2 kg} times {5 m/s^2}}` | P0 to P7 | P8, P9 |
| Corrected answer | `Prediction: 10 N` | P0 to P7, P11, P12 | P8, P9 |

P0 is the starting demand `force_cart_0`. P1 is the application of entry E0
with `p := cart` and `t := 0`; its evidence holds the entry as authored, the
bindings and the instantiated text. P2 to P4 are the mass: entry E1 applied,
its own headword left unexpanded, and its text replaced, recorded as "what is
meant by 'supplied {mass} of cart' is the same as what is meant by '2 kg'".
P5 to P7 are the acceleration in the same way.

The middle step is there because these two definitions name their own headword
("supplied mass of p"), which the engine reads as a demand. A definition with
no headword in its text needs only two steps.

P8 retains the exact mistaken pair. P9 records the report that consumed it.
Reopening the calculation clears both live overlays, leaving their events
intact. The correction P11 is a fresh response to the original product; P12
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
the others are commands. Each `expand` shows the definition's text and offers
to replace it: the first offer is declined with an empty line, and the next two
take the values. Disabling the other automatic offers makes this transcript
deterministic.

```text
set cleanup off
set reduce off
trace force_cart_0
expand

expand 0
2 kg
expand 1
5 m/s^2
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
