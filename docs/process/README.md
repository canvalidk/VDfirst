# Process

This folder describes how to keep the project understandable while it grows.

## Recommended Flow

```text
idea -> sketch -> draft spec -> accepted segment -> tests -> implementation -> docs update
```

## Rules Of Thumb

- Broad ideas should become north-star drafts, not immediate code tasks.
- Implementation work should come from small segment specs.
- Every spec needs a maturity status.
- Big design choices should get an ADR.
- Tests become the implementation contract once code lands.
- If Theory or Newton guidance is missing, write an open question rather than
  guessing deeply in code.

## Where Things Go

- Rough Code notes: `../../codex_context/notes/`
- Cross-branch reference summaries: `../../codex_context/references/`
- Implementation specs: `../../specs/`
- Presentable explanations and decisions: `../`
- Tests: repo-root `test_*.py`

