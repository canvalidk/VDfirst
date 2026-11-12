# VDfirst

Code-only repository for the Valid Dictionary (VD) engine.

## Contents

- Core engine: `engine.py`
- Parameterized headword calls/instantiation: `application.py`
- Residual machinery: `residual.py`, `definiens.py`
- Simulator inspection layer: `simulator.py`
- REPL inspection and trace loop: `repl.py`
- Trace demand state: `demand.py`
- Trace-derived prediction candidates and classifications: `prediction_set.py`
- Portable live-workbench records and replay: `workbench.py`
- Local website bridge: `workbench_server.py`
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
`worklist`, `goto N` / `go to N`, `state`, `up`, `onward`, `reduce`,
`unreduce`, `fold`, `tidy`, `set`, and `cancel`.
Use `down <pos>` to revisit a settled child calculation for inspection or
correction.

Use `predictions` to inspect recorded meaning-preservation and supplied-input
claims. `classify P2 correct maths` or `classify P1 parameter input` attaches
your category; it does not verify the claim. `predictions json` prints the
structured export, including before/after evidence and trace addresses.

The projection retains history and selects recorded claims supporting the
current result. The full prediction-set disjunction and semantic checking
remain deferred. See [the worked example](docs/examples/prediction-set.md).

For a self-contained example with two parameter inputs and one reduction:

```powershell
python prediction_demo.py
python prediction_demo.py > predictions.json
```

For a parameterized call with a deliberately mistaken response, a dependent
report, and a correction that keeps the earlier evidence:

```powershell
python correction_demo.py
python correction_demo.py --json > correction-stages.json
python correction_demo.py --interactive
```

The demo distinguishes current support from history at each stage. Interpreter
responses are scripted and every claim stays unchecked. See the
[correction walkthrough](docs/examples/correction-demo.md) for REPL instructions.

## Website workbench and saved records

In this checkout, start the local bridge:

```powershell
python workbench_server.py --port 8765
```

In the VD-website checkout with the workbench changes, run `pnpm dev` and open
**03 Workbench**. Start `force_cart_0`, choose an open hole and definition,
expand it, supply inputs, and record interpreter responses. Reductions can
be reopened without deleting structure or evidence. The root result, current
support, history and exact events update after each operation.

**Download full record** saves the exact dictionary, question/context,
commands, stable frame/event identities, and every result/prediction snapshot.
**Open saved record** displays a local file without an engine connection.
Choose **Validate with local engine** to replay it before continuing. This
checks consistency and digests, not arithmetic, meaning or authorship. All
scientific claims remain unchecked and full prediction coverage stays partial.

The bridge is stateless and binds only `127.0.0.1`. It serves no files, stores
no sessions, and accepts no supplied code. Vite proxies its relative
`/api/workbench` routes. Default website origins are localhost/127.0.0.1 on
ports 5173 and 5174; add `--allow-origin http://127.0.0.1:PORT` for another
local port. Restart the bridge after engine source changes. A different engine
fingerprint prevents continuation of an old record; offline playback remains
available.

For a complete scripted saved-record example:

```powershell
python workbench_demo.py > saved-trace.json
```

The small Python API is `start_record`, `apply_command`, and `validate_record`
from `workbench.py`. See [the versioned record contract](specs/2026-10-24-trace-workbench.md).

## Tests

```powershell
python -m pytest -q
```

Expected baseline: 523 passing tests.
