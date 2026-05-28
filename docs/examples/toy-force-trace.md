# Toy Force Trace

- Status: Sketch
- Purpose: Minimal example for explaining current trace machinery.

## Dictionary

```text
E0 mass         -> 2 kg
E1 acceleration -> 5 m/s^2
E2 force        -> mass times acceleration
```

## Current Simulator Shape

```text
trace force

at: root
{force}
open positions: 0
```

```text
expand

at: E2 @ parent pos 0
{mass} times {acceleration}
open positions: 0, 1
```

```text
recall 0

at: E2 @ parent pos 0
2 kg times {acceleration}
open positions: 1
```

## Why This Example Matters

This shows the current tree-building behaviour clearly:

- `ANALYSE` turns headwords into holes.
- `EXPAND` creates a child demand.
- in-trace `RECALL` fills one active hole.
- the current simulator can render through children but does not yet perform
  automatic degree-0 return as an evaluator stack.

## Future Golden Version

Once return semantics exist, this example should show the evaluator working
back up to the root and producing:

```text
2 kg times 5 m/s^2
```

