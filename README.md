# VDfirst

Code-only repository for the Valid Dictionary (VD) engine.

## Contents

- Core engine: `engine.py`
- Residual machinery: `residual.py`, `definiens.py`
- Simulator inspection layer: `simulator.py`
- REPL inspection and trace loop: `repl.py`
- Trace demand state: `demand.py`
- Trace-derived prediction candidates and classifications: `prediction_set.py`
- Newton case study: `newton.py`
- Display/visualisation helpers: `display.py`, `viz.py`, `vd_demo.py`
- Project documentation: `docs/`
- Specs archive: `specs/`
- Codex project context shelf: `codex_context/`
- Tests: `test_*.py`

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Running the simulator

```powershell
python run_repl.py
```

Type `help` in the REPL for the command list. Core commands include
`count`, `headwords`, `recall <headword>`, and `trace <text>`. In trace
mode use `expand`, `recall`, `inject`, `flatten`, `return`, `events`,
`worklist`, `goto N` / `go to N`, `state`, `up`, `onward`, and `cancel`.

Use `predictions` to inspect recorded meaning-preservation and supplied-input
claims. `classify P2 correct maths` or `classify P1 parameter input` attaches
your category; it does not verify the claim. `predictions json` prints the
structured export, including before/after evidence and trace addresses.

This first layer covers recorded history. It does not yet assemble the full
prediction-set disjunction or select which historical claims the current
answer depends on. See [the worked example](docs/examples/prediction-set.md).

For a self-contained example with two parameter inputs and one reduction:

```powershell
python prediction_demo.py
python prediction_demo.py > predictions.json
```

## Tests

```powershell
python -m pytest -q
```

Expected baseline: 332 passing tests.
