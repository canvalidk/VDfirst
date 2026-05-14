# VDfirst

Code-only repository for the Valid Dictionary (VD) engine.

## Contents

- Core engine: `engine.py`
- Residual machinery: `residual.py`, `definiens.py`
- Simulator inspection layer: `simulator.py`
- REPL inspection and trace loop: `repl.py`
- Trace demand state: `demand.py`
- Newton case study: `newton.py`
- Display/visualisation helpers: `display.py`, `viz.py`, `vd_demo.py`
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
mode use `expand`, `recall`, `inject`, `worklist`, `goto N` / `go to N`,
`state`, `up`, `back`, and `cancel`.

## Tests

```powershell
pytest test_*.py
```

Expected baseline: 220 passing tests.
