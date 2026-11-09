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
- Hand-trace recorder: `handtrace.py`, with worked examples
  `handtrace_example_*.py` (independent of the engine)
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
`worklist`, `goto N` / `go to N`, `state`, `up`, `back`, and `cancel`.

## Hand traces

`handtrace.py` records a trace worked by hand while the entries are
unfinished: demand frames, labelled steps (ENTRY, INPUT, CONTRACT,
READING, DERIVE, EXTERNAL, OPEN), exact arithmetic checks, a no-hidden-
lookup rule, withdrawals, and per-answer ledgers and hypothesis sets.
It cites the dictionary and never executes it. See
`specs/2026-11-08-hand-trace-ledger.md`.

```powershell
python handtrace_example_atwood.py            # print the Atwood trace and its ledger
python handtrace.py validate RECORD.json      # check a saved record's digest and replay it
python handtrace.py render RECORD.json        # print a saved record as Markdown
pytest test_handtrace*.py handtrace_example_*.py
```

## Tests

```powershell
pytest test_*.py
```

Expected baseline: 244 passing tests.
