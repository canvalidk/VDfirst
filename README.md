# VDfirst

Code-only repository for the Valid Dictionary (VD) engine.

## Contents

- Core engine: `engine.py`
- Residual machinery: `residual.py`, `definiens.py`
- Simulator inspection layer: `simulator.py`
- Newton case study: `newton.py`
- Display/visualisation helpers: `display.py`, `viz.py`, `vd_demo.py`
- Tests: `test_*.py`

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Tests

```powershell
pytest test_*.py
```

Expected baseline: 120 passing tests.
