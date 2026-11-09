"""Record a VD trace by hand, step by step, without executable entries.

The dictionary is cited, never executed. The tracer declares each step; this
module keeps the books the way the engine would:

* every step carries a label (ENTRY, INPUT, CONTRACT, READING, DERIVE,
  EXTERNAL, OPEN) and the names it uses and binds;
* no hidden lookup: a step may use a name, or a value, only where it is
  visible. A binding is visible in the frame where it was made and in every
  frame above it (results flow up to callers). It reaches other frames only
  by DELIVER, which passes it from a caller down to the frame it calls and
  copies the original qualifications;
* every DERIVE claim is checked with exact rational arithmetic, either as an
  identity or as a linear consequence of the relations it cites. Cited
  relations that contradict the visible values are a conflict, not a pass;
* an EXTERNAL linear solve reports a unique solution, a family (fixing the
  unknowns it can), or an inconsistency;
* each answer's ledger sorts the steps that feed it into theory-side items,
  world commitments and step members (the hypothesis-set sort of the
  5 November trace-to-set record), and lists everything else separately.

Nothing here certifies physics, recognition or meaning. Checks cover exact
arithmetic and bookkeeping only. The hypothesis set produced is the
prediction side of a trial; the observation side is not modelled.
Standard library only; Python 3.10+.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import keyword
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Mapping, Sequence

FORMAT = "vd-hand-trace"
VERSION = 1

LABELS = ("ENTRY", "INPUT", "CONTRACT", "READING", "DERIVE", "EXTERNAL", "OPEN")
STRUCTURAL = ("DEMAND", "DELIVER", "WITHDRAW", "ANSWER")

INPUT_KINDS = {
    "recognition": "a verdict that something in the scene is of a kind or satisfies a condition",
    "model": "a modelling or idealisation commitment, including supplied ideal model relations",
    "value": "a supplied number",
    "completeness": "a claim that an account or membership is complete within a scope",
    "identity": "an identity or persistence commitment (same object, address or mass)",
    "convention": "a choice of axis, sign, unit or quoting convention (not a claim about the world)",
    "normalization": "a reading of the wording of the question or exercise",
    "choice": "a tracer's choice that is not a claim about the world (e.g. a chosen system)",
    "haze": "a stipulation about unkeyed omitted influence",
}
NON_WORLD_KINDS = ("convention", "choice")
VALUE_KINDS = ("value", "haze")

STATUSES = ("NEEDS", "REQUIRED", "ENTAILED", "USES")
PRUNED_STATUSES = ("ENTAILED", "USES")

ROOT = "ROOT"


class TraceError(ValueError):
    """A step was malformed or broke a bookkeeping rule."""


class HiddenLookupError(TraceError):
    """A step used a name or value that was not delivered to its frame."""


class CheckError(TraceError):
    """An arithmetic claim failed or could not be checked (strict mode)."""


class UndefinedValue(TraceError):
    """An expression is undefined at the given values (a division by zero)."""


# ---------------------------------------------------------------------------
# Exact linear forms
# ---------------------------------------------------------------------------


class Nonlinear(Exception):
    """An expression is not linear in its unknown names."""


@dataclass(frozen=True)
class Form:
    """sum(coeff * name) + const, with exact rational coefficients."""

    coeffs: tuple[tuple[str, Fraction], ...] = ()
    const: Fraction = Fraction(0)

    @staticmethod
    def of(coeffs: Mapping[str, Fraction], const: Fraction) -> "Form":
        items = tuple(sorted((n, Fraction(c)) for n, c in coeffs.items() if c != 0))
        return Form(items, Fraction(const))

    @staticmethod
    def constant(value: Fraction) -> "Form":
        return Form((), Fraction(value))

    @staticmethod
    def name(name: str) -> "Form":
        return Form(((name, Fraction(1)),), Fraction(0))

    def as_dict(self) -> dict[str, Fraction]:
        return dict(self.coeffs)

    def is_constant(self) -> bool:
        return not self.coeffs

    def is_zero(self) -> bool:
        return not self.coeffs and self.const == 0

    def names(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.coeffs)

    def __add__(self, other: "Form") -> "Form":
        d = self.as_dict()
        for n, c in other.coeffs:
            d[n] = d.get(n, Fraction(0)) + c
        return Form.of(d, self.const + other.const)

    def __neg__(self) -> "Form":
        return Form.of({n: -c for n, c in self.coeffs}, -self.const)

    def __sub__(self, other: "Form") -> "Form":
        return self + (-other)

    def scale(self, k: Fraction) -> "Form":
        return Form.of({n: c * k for n, c in self.coeffs}, self.const * k)

    def __mul__(self, other: "Form") -> "Form":
        if self.is_constant():
            return other.scale(self.const)
        if other.is_constant():
            return self.scale(other.const)
        raise Nonlinear("product of two non-constant terms")

    def __truediv__(self, other: "Form") -> "Form":
        if not other.is_constant():
            raise Nonlinear("division by a non-constant term")
        if other.const == 0:
            raise UndefinedValue("division by zero")
        return self.scale(1 / other.const)

    def render(self) -> str:
        parts = []
        for n, c in self.coeffs:
            if c == 1:
                parts.append(n)
            elif c == -1:
                parts.append(f"-{n}")
            else:
                parts.append(f"{frac(c)}*{n}")
        if self.const != 0 or not parts:
            parts.append(frac(self.const))
        return " + ".join(parts).replace("+ -", "- ")


def frac(x: Fraction) -> str:
    """Render a rational exactly: 3, -147/5."""
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_name(name: str) -> None:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name) or keyword.iskeyword(name) \
            or name in ("True", "False", "None"):
        raise TraceError(f"names must be identifiers that are not Python keywords: {name!r}")


def _parse_tree(text: str) -> ast.Expression:
    if "#" in text:
        raise TraceError(f"'#' is not allowed in an expression: {text!r}")
    try:
        return ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise TraceError(f"cannot parse expression {text!r}: {exc.msg}") from None


_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Add, ast.Sub,
                  ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)


def check_syntax(tree: ast.AST, text: str) -> None:
    """Refuse anything outside the checker's arithmetic: numbers, names, + - * / and ** (any exponent)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitXor):
            raise TraceError(f"outside the checker's syntax ('^') in {text!r}; write powers with **")
        if not isinstance(node, _ALLOWED_NODES):
            raise TraceError(f"outside the checker's syntax ({type(node).__name__}) in {text!r}; "
                             "use numbers, names, + - * / and ** (a root is **0.5 or **(1/3))")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool)
                                               or not isinstance(node.value, (int, float))):
            raise TraceError(f"outside the checker's syntax (constant {node.value!r}) in {text!r}")


def mentioned_names(text: str) -> tuple[str, ...]:
    """Every identifier in an expression or equation, in order of first mention.

    Also refuses syntax outside the checker's arithmetic, so it never enters a record.
    """
    out: list[str] = []
    sides = split_claim(text) if "=" in text.replace("==", "=") else (text,)
    for side in sides:
        tree = _parse_tree(side)
        check_syntax(tree, side)
        found = sorted((n.lineno, n.col_offset, n.id) for n in ast.walk(tree) if isinstance(n, ast.Name))
        for _, _, nid in found:
            if nid not in out:
                out.append(nid)
    return tuple(out)


# Every exact number the checker keeps stays below Python's default limit on int-to-str conversion
# (4300 digits, about 14 284 bits), so every accepted value can be rendered and saved.
_MAX_BITS = 13_000
_TOO_BIG = "a number too large to handle exactly"


def _too_big(x: Fraction) -> bool:
    return max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > _MAX_BITS


def _bounded(f: Form) -> Form:
    """f itself, or Nonlinear when one of its numbers is too large to keep exactly."""
    if _too_big(f.const) or any(_too_big(c) for _, c in f.coeffs):
        raise Nonlinear(_TOO_BIG)
    return f


def _literal(literal: str, value) -> Fraction:
    """A numeric literal read exactly from its source text, refusing sizes beyond the bound up front."""
    # Pre-checks only keep Fraction() cheap and under Python's 4300-digit parsing limit; the exact bound
    # is _bounded's (13 000 bits), the same as for supplied values, so every accepted value replays.
    text = literal.replace("_", "")
    if len(text) > 4200:
        raise Nonlinear(_TOO_BIG)
    m = re.fullmatch(r"([0-9.]*)[eE]([+-]?[0-9]+)", text)
    if m and abs(int(m.group(2))) > 4000 and m.group(1).strip("0.") != "":
        raise Nonlinear(_TOO_BIG)
    if m and m.group(1).strip("0.") == "":
        return Fraction(0)
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return Fraction(value)


def _iroot(n: int, k: int) -> int:
    """The integer k-th root of n >= 0, rounded down."""
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + k - 1) // k)
    while True:
        y = ((k - 1) * x + n // x ** (k - 1)) // k
        if y >= x:
            return x
        x = y


def _power(base: Fraction, exp: Fraction) -> Fraction:
    """base ** exp exactly. Raises UndefinedValue (0 to a negative power, an even root of a negative
    number) or Nonlinear (an irrational result, or one too large to compute exactly)."""
    num, den = exp.numerator, exp.denominator
    if base == 0:
        if exp < 0:
            raise UndefinedValue("division by zero")
        return Fraction(0) if exp > 0 else Fraction(1)
    if base < 0 and den % 2 == 0:
        raise UndefinedValue("an even root of a negative number")
    size = max(abs(base.numerator).bit_length(), base.denominator.bit_length())
    if den > 64 or (size - 1) * abs(num) > _MAX_BITS * den:  # a lower bound on the result's size
        raise Nonlinear(_TOO_BIG)
    sign = 1
    if den != 1:
        if base < 0:
            sign, base = -1, -base
        rn, rd = _iroot(base.numerator, den), _iroot(base.denominator, den)
        if rn ** den != base.numerator or rd ** den != base.denominator:
            raise Nonlinear("an irrational power cannot be checked exactly")
        base = Fraction(rn, rd) * sign
    out = base ** num
    if _too_big(out):
        raise Nonlinear(_TOO_BIG)
    return out


def parse_expression(text: str, values: Mapping[str, Fraction] | None = None) -> tuple[Form, tuple[str, ...]]:
    """Parse an arithmetic expression into an exact linear Form.

    Names found in values are replaced by their constants. Returns the Form
    and every name mentioned. Numeric literals are read exactly from their
    source text (9.8 is 49/5; 2.94e1 is 147/5). A power needs a constant base
    and exponent; a fractional exponent is exact when the root is rational
    ((1/4)**0.5 is 1/2) and Nonlinear otherwise. Raises Nonlinear when the
    expression is not linear in its remaining names, UndefinedValue for a
    division by zero or an even root of a negative number, TraceError for
    syntax outside the checker's arithmetic.
    """
    values = values or {}
    source = text.strip()
    tree = _parse_tree(source)
    names: list[str] = []

    def walk(node: ast.AST) -> Form:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            literal = ast.get_source_segment(source, node) or repr(node.value)
            return _bounded(Form.constant(_literal(literal, node.value)))
        if isinstance(node, ast.Name):
            if node.id not in names:
                names.append(node.id)
            if node.id in values:
                return Form.constant(values[node.id])
            return Form.name(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            inner = walk(node.operand)
            return -inner if isinstance(node.op, ast.USub) else inner
        if isinstance(node, ast.BinOp):
            # Walk both sides even if one is nonlinear, so operand order never hides an undefined part:
            # undefined wins over nonlinear. A product with a zero factor is zero wherever it is defined,
            # so a zero divisor such as m*a*(t - 3) at t = 3 is recognised whatever the factor order.
            pending: Nonlinear | None = None
            try:
                left = walk(node.left)
            except Nonlinear as exc:
                pending, left = exc, None
            try:
                right = walk(node.right)
            except Nonlinear as exc:
                pending, right = pending or exc, None
            op = node.op
            if pending is not None:
                if isinstance(op, ast.Mult) and any(f is not None and f.is_zero() for f in (left, right)):
                    return Form.constant(Fraction(0))
                if isinstance(op, ast.Div) and right is not None and right.is_zero():
                    raise UndefinedValue("division by zero")
                raise pending
            if isinstance(op, ast.Add):
                return _bounded(left + right)
            if isinstance(op, ast.Sub):
                return _bounded(left - right)
            if isinstance(op, ast.Mult):
                return _bounded(left * right)
            if isinstance(op, ast.Div):
                return _bounded(left / right)
            if isinstance(op, ast.Pow):
                if not (left.is_constant() and right.is_constant()):
                    raise Nonlinear("power of a non-constant term")
                return Form.constant(_power(left.const, right.const))
        raise TraceError(f"unsupported syntax in {text!r}")

    return walk(tree), tuple(names)


def split_claim(text: str) -> tuple[str, str]:
    """Split 'lhs = rhs' (or 'lhs == rhs') into its two sides."""
    s = text.replace("==", "=")
    parts = s.split("=")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise TraceError(f"a claim needs exactly one '=': {text!r}")
    return parts[0].strip(), parts[1].strip()


def parse_equation(text: str, values: Mapping[str, Fraction] | None = None) -> tuple[Form, tuple[str, ...]]:
    """Parse 'lhs = rhs' into the Form lhs - rhs (meaning Form == 0)."""
    lhs, rhs = split_claim(text)
    try:
        left, ln = parse_expression(lhs, values)
    except Nonlinear as exc:  # the right side may still be undefined, which wins
        parse_expression(rhs, values)
        raise exc from None
    right, rn = parse_expression(rhs, values)
    return _bounded(left - right), tuple(dict.fromkeys(ln + rn))


def _rref(rows: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[int]]:
    """Reduced row echelon form over the rationals; returns rows and pivot columns."""
    m = [list(r) for r in rows]
    pivots: list[int] = []
    if not m:
        return m, pivots
    r = 0
    for c in range(len(m[0])):
        pivot = next((i for i in range(r, len(m)) if m[i][c] != 0), None)
        if pivot is None:
            continue
        m[r], m[pivot] = m[pivot], m[r]
        pv = m[r][c]
        m[r] = [x / pv for x in m[r]]
        for i in range(len(m)):
            if i != r and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[r])]
        pivots.append(c)
        r += 1
        if r == len(m):
            break
    return m, pivots


def _vectors(forms: Sequence[Form]) -> tuple[list[str], list[list[Fraction]]]:
    names = sorted({n for f in forms for n in f.names()})
    rows = []
    for f in forms:
        d = f.as_dict()
        rows.append([d.get(n, Fraction(0)) for n in names] + [f.const])
    return names, rows


def consistent(relations: Sequence[Form]) -> bool:
    """True when the relations == 0 have a common solution."""
    if not relations:
        return True
    names, rows = _vectors(relations)
    _, pivots = _rref(rows)
    return len(names) not in pivots


def entails(relations: Sequence[Form], claim: Form) -> bool:
    """True when claim == 0 is a linear combination of the relations == 0.

    For consistent relations this is exactly linear consequence.
    Callers should check consistency first: from inconsistent relations
    everything is a combination.
    """
    if claim.is_zero():
        return True
    if not relations:
        return False
    _, rows = _vectors(list(relations) + [claim])
    base = rows[:-1]
    return len(_rref(rows)[1]) == len(_rref(base)[1])


def needed_relations(relations: Sequence[Form], claim: Form, *, exhaustive_up_to: int = 8) -> list[int]:
    """Indices of a smallest subset of relations that entails claim.

    Up to exhaustive_up_to relations, subsets are tried by size and, within a
    size, in citation order, so the result is a minimum-size subset that
    prefers the relations cited first. Beyond that a greedy pass drops
    relations from the end of the citation list. The relations are assumed
    consistent; claim must be entailed by all of them.
    """
    k = len(relations)
    if claim.is_zero():
        return []
    if k <= exhaustive_up_to:
        for size in range(1, k + 1):
            for combo in itertools.combinations(range(k), size):
                if entails([relations[j] for j in combo], claim):
                    return list(combo)
        return list(range(k))
    keep = list(range(k))
    for i in reversed(range(k)):
        trial = [j for j in keep if j != i]
        if entails([relations[j] for j in trial], claim):
            keep = trial
    return keep


def solve_linear(relations: Sequence[Form], unknowns: Sequence[str]) -> dict:
    """Solve relations == 0 for the listed unknowns, exactly.

    Returns {'status': 'unique' | 'family' | 'inconsistent', 'rank': int,
    'values': {name: Fraction}, 'free': [names]}. For a family, values holds
    the unknowns the relations fix anyway; free holds the free unknowns.
    """
    cols = list(unknowns)
    if len(set(cols)) != len(cols):
        raise TraceError("unknowns must not repeat")
    rows = []
    for f in relations:
        d = f.as_dict()
        extra = [n for n in d if n not in cols]
        if extra:
            raise TraceError(f"relation mentions names that are neither visible values nor listed unknowns: {extra}")
        rows.append([d.get(n, Fraction(0)) for n in cols] + [-f.const])
    n = len(cols)
    if not rows:
        return {"status": "unique" if n == 0 else "family", "rank": 0, "values": {}, "free": cols}
    m, pivots = _rref(rows)
    if n in pivots:
        return {"status": "inconsistent", "rank": len([p for p in pivots if p < n]), "values": {}, "free": []}
    values: dict[str, Fraction] = {}
    for i, p in enumerate(pivots):
        if all(m[i][j] == 0 for j in range(n) if j != p):
            values[cols[p]] = m[i][n]
    free = [cols[j] for j in range(n) if j not in pivots]
    status = "unique" if len(pivots) == n else "family"
    return {"status": status, "rank": len(pivots), "values": values, "free": free}


# ---------------------------------------------------------------------------
# Dictionary entries (for quote verification)
# ---------------------------------------------------------------------------


_ENTRY_HEAD = re.compile(r"^#{2,4}\s*\[([^\]]+)\]")


def load_entries(path: str) -> dict[str, str]:
    """Read an entries file in the Design 2.1 layout into {ref: definition text}.

    Each entry is a heading like '### [E8] headword' or '### [K16 / E1] ...'
    followed by a fenced text block. Every ref in the brackets maps to that text.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out: dict[str, str] = {}
    refs: list[str] = []
    buf: list[str] | None = None
    for line in lines:
        head = _ENTRY_HEAD.match(line)
        if head:
            refs = [r.strip() for r in head.group(1).split("/") if r.strip()]
            continue
        if line.strip().startswith("```"):
            if buf is None:
                buf = []
            else:
                text = " ".join(" ".join(buf).split())
                for r in refs:
                    out[r] = text
                buf, refs = None, []
            continue
        if buf is not None:
            buf.append(line)
    return out


def _squash(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Trace records
# ---------------------------------------------------------------------------


@dataclass
class Frame:
    id: str
    parent: str | None
    text: str
    step: int | None  # the DEMAND step that opened it (None for the root)


@dataclass
class Binding:
    name: str
    sort: str  # 'value' | 'unknown' | 'fact' | 'relation'
    frame: str
    step: int
    text: str = ""
    unit: str = ""
    address: str = ""
    equation: str = ""  # relations only: 'lhs = rhs'
    withdrawn: int | None = None  # step index of its WITHDRAW, if any


@dataclass
class Step:
    index: int
    frame: str
    op: str  # one of LABELS or STRUCTURAL
    text: str = ""
    ref: str = ""
    kind: str = ""
    uses: tuple[str, ...] = ()
    binds: tuple[str, ...] = ()
    claim: str = ""
    check: str = "n/a"  # 'checked' | 'failed' | 'unchecked' | 'n/a'
    detail: str = ""
    deps: tuple[int, ...] = ()
    tag: str = ""

    @property
    def id(self) -> str:
        return f"[{self.index + 1}]"


@dataclass
class _Delivery:
    step: int
    carries_value: bool


class Trace:
    """A hand trace: frames, ordered steps, bindings, values and ledgers.

    Every public method appends one step (or raises and changes nothing) and
    records its arguments, so a saved record replays exactly.
    """

    def __init__(self, question: str, edition: Mapping | None = None, *, strict: bool = True,
                 entries: Mapping[str, str] | None = None):
        if not str(question).strip():
            raise TraceError("a trace needs a question")
        self.question = question
        self.edition = dict(edition or {})
        self.strict = strict
        if entries is not None and not entries:
            raise TraceError("entries were supplied but are empty; pass None to turn quote checking off")
        self.entries = {str(k): _squash(str(v)) for k, v in (entries or {}).items()}
        self.frames: dict[str, Frame] = {ROOT: Frame(ROOT, None, question, None)}
        self.steps: list[Step] = []
        self.bindings: dict[str, Binding] = {}
        self.values: dict[str, Fraction] = {}
        self.value_step: dict[str, int] = {}
        self.value_history: dict[str, list[tuple[Fraction, int]]] = {}
        self.solve_children: dict[int, list[int]] = {}
        self.deliveries: dict[str, dict[str, list[_Delivery]]] = {}
        self.annotations: dict[str, dict] = {}
        self.answers: list[tuple[str, int]] = []  # (label, step index)
        self.commands: list[dict] = []

    # -- frames and visibility ------------------------------------------------

    def _ancestors(self, frame: str) -> list[str]:
        out: list[str] = []
        f: str | None = frame
        while f is not None:
            out.append(f)
            f = self.frames[f].parent
        return out

    def _in_subtree(self, frame: str, top: str) -> bool:
        """True when frame is top or lies below it."""
        return top in self._ancestors(frame)

    def _require_frame(self, frame: str) -> None:
        if frame not in self.frames:
            raise TraceError(f"unknown frame {frame!r}")

    def _chain_deliveries(self, frame: str, name: str) -> list[_Delivery]:
        out: list[_Delivery] = []
        for anc in self._ancestors(frame):
            out.extend(self.deliveries.get(anc, {}).get(name, []))
        return out

    def visible(self, frame: str, name: str) -> int | None:
        """The step that makes name visible at frame, or None.

        A name is visible where it was bound, in every frame above that
        (results flow up), and in any frame it was delivered into and below.
        A withdrawn name is visible nowhere.
        """
        b = self.bindings.get(name)
        if b is None or b.withdrawn is not None:
            return None
        if self._in_subtree(b.frame, frame):
            return b.step
        vs = self.value_step.get(name)
        if vs is not None and self._in_subtree(self.steps[vs].frame, frame):
            return vs
        dels = self._chain_deliveries(frame, name)
        return dels[-1].step if dels else None

    def value_visible(self, frame: str, name: str) -> int | None:
        """The step that makes name's value visible at frame, or None.

        A value that rests on a withdrawn premise is visible nowhere; the name
        stays usable and the quantity may be determined again.
        """
        if name not in self.values or self.visible(frame, name) is None:
            return None
        origin = self.value_step[name]
        if self._rests_on_withdrawn(origin):
            return None
        if self._in_subtree(self.steps[origin].frame, frame):
            return origin
        carrying = [d for d in self._chain_deliveries(frame, name) if d.carries_value and d.step > origin]
        return carrying[-1].step if carrying else None

    def known_values(self, frame: str) -> dict[str, Fraction]:
        """The values a step at frame may use."""
        return {n: v for n, v in self.values.items() if self.value_visible(frame, n) is not None}

    def _set_value(self, name: str, value: Fraction, step: int) -> None:
        self.values[name] = value
        self.value_step[name] = step
        self.value_history.setdefault(name, []).append((value, step))

    def _value_from_step(self, name: str, step: int) -> Fraction | None:
        for v, s in self.value_history.get(name, []):
            if s == step:
                return v
        return None

    def _usable_value(self, name: str) -> bool:
        return name in self.values and not self._rests_on_withdrawn(self.value_step[name])

    def _check_visible(self, frame: str, names: Iterable[str], *, with_values: bool = True) -> list[int]:
        """Refuse names not visible at frame; return the steps the names rest on, plus (with_values) the
        steps behind their visible values. Steps that only register or mention names pass with_values=False,
        so they do not inherit the premises of a value they never use."""
        deps: list[int] = []
        missing: list[str] = []
        for n in names:
            b = self.bindings.get(n)
            if b is None:
                raise TraceError(f"{n!r} is not bound anywhere in this trace")
            if b.withdrawn is not None:
                raise TraceError(f"{n!r} was withdrawn at {self.steps[b.withdrawn].id} and cannot be used")
            if self.visible(frame, n) is None:
                missing.append(n)
                continue
            gone = self._rests_on_withdrawn(b.step)
            if gone:
                raise TraceError(f"{n!r} rests on {gone!r}, which was withdrawn at "
                                 f"{self.steps[self.bindings[gone].withdrawn].id}; it cannot be used now")
            deps.append(b.step)
            if with_values and self.value_visible(frame, n) is not None:
                deps.append(self.value_step[n])
        if missing:
            where = ", ".join(
                f"{n} (bound at {self.steps[self.bindings[n].step].id} in frame {self.bindings[n].frame})"
                for n in missing)
            raise HiddenLookupError(f"hidden lookup at frame {frame!r}: {where}. Deliver it into this frame first.")
        return deps

    def _hidden_values(self, frame: str, names: Iterable[str]) -> list[str]:
        """Names visible at frame whose usable value exists but is not visible there."""
        return [n for n in dict.fromkeys(names) if self._usable_value(n) and self.visible(frame, n) is not None
                and self.value_visible(frame, n) is None]

    def _rests_on_withdrawn(self, index: int, before: int | None = None) -> str:
        """Name of a withdrawn INPUT that step index depends on, or ''.

        With before, only withdrawals recorded before that step count.
        """
        withdrawn = {b.step: b.name for b in self.bindings.values()
                     if b.withdrawn is not None and (before is None or b.withdrawn < before)}
        if not withdrawn:
            return ""
        key = (index, before, len(withdrawn))
        cache = self.__dict__.setdefault("_taint_cache", {})
        if key in cache:
            return cache[key]
        seen: set[int] = set()
        stack = [index]
        found = ""
        while stack and not found:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            if i in withdrawn:
                found = withdrawn[i]
                break
            stack.extend(self.steps[i].deps)
        cache[key] = found
        return found

    def _withdrawn_premises(self, index: int, before: int | None = None) -> list[str]:
        """Every withdrawn INPUT that step index depends on, earliest withdrawal first (so messages and
        notes do not depend on search order). With before, only withdrawals before that step count."""
        withdrawn = {b.step: b for b in self.bindings.values()
                     if b.withdrawn is not None and (before is None or b.withdrawn < before)}
        seen: set[int] = set()
        stack = [index]
        found = []
        while stack and withdrawn:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            if i in withdrawn:
                found.append(withdrawn[i])
            stack.extend(self.steps[i].deps)
        return [b.name for b in sorted(found, key=lambda b: b.withdrawn)]

    # -- plumbing -------------------------------------------------------------

    def _record(self, method: str, **args) -> None:
        self.commands.append({"op": method, "args": _jsonable(args)})

    def _new_step(self, **kw) -> Step:
        step = Step(index=len(self.steps), **kw)
        self.steps.append(step)
        return step

    def _validate_new_names(self, names: Iterable[str]) -> None:
        for n in names:
            _check_name(n)
            if n in self.bindings:
                raise TraceError(f"{n!r} is already bound at {self.steps[self.bindings[n].step].id}")

    def _bind(self, name: str, sort: str, frame: str, step: int, **kw) -> None:
        self.bindings[name] = Binding(name, sort, frame, step, **kw)

    def _quantities_only(self, names: Iterable[str]) -> None:
        for n in names:
            b = self.bindings.get(n)
            if b is not None and b.sort in ("fact", "relation"):
                raise TraceError(f"{n!r} is a {b.sort}, not a quantity; it cannot appear in arithmetic")

    def _relation(self, name: str) -> Binding:
        b = self.bindings.get(name)
        if b is None or b.sort != "relation":
            raise TraceError(f"{name!r} is not a relation")
        return b

    def _relation_form(self, name: str, values: Mapping[str, Fraction]) -> Form:
        try:
            return parse_equation(self._relation(name).equation, values)[0]
        except Nonlinear as exc:
            raise Nonlinear(f"relation {name} is nonlinear with the values visible here ({exc})") from None
        except UndefinedValue as exc:
            raise UndefinedValue(f"relation {name} cannot be evaluated with these values ({exc})") from None

    def _relation_names(self, rels: Iterable[str]) -> list[str]:
        names: list[str] = []
        for r in rels:
            for n in mentioned_names(self._relation(r).equation):
                if n not in names:
                    names.append(n)
        return names

    @staticmethod
    def _parse_kind(kind: str) -> str:
        parts = [p.strip() for p in str(kind).split("/") if p.strip()]
        if not parts or any(p not in INPUT_KINDS for p in parts):
            raise TraceError(f"INPUT kind must be one of {sorted(INPUT_KINDS)} (or several joined by '/'), "
                             f"not {kind!r}")
        return "/".join(parts)

    # -- public step API --------------------------------------------------------

    def demand(self, parent: str, frame: str, text: str, *, ref: str = "", quote: str = "") -> str:
        """Open a demand frame under parent.

        ref names the entry that exposed the demand; it is linked to the latest
        ENTRY step with that ref in the parent frame, if there is one. quote,
        if given, is verified like an ENTRY quote.
        """
        self._require_frame(parent)
        if not str(frame).strip() or frame in self.frames:
            raise TraceError(f"frame id {frame!r} is empty or already used")
        if not str(text).strip():
            raise TraceError("a demand needs text")
        if quote:
            if not str(ref).strip():
                raise TraceError("a quoted demand needs the entry ref")
            self._verify_quote(ref, quote)
        deps: tuple[int, ...] = ()
        if ref:
            linked = [st.index for st in self.steps if st.op == "ENTRY" and st.frame == parent and st.ref == ref]
            if linked:
                deps = (linked[-1],)
        body = text if not quote else "\u201c" + quote + "\u201d \u2014 " + text
        st = self._new_step(frame=parent, op="DEMAND", text=body, ref=ref, binds=(), tag=frame, deps=deps)
        self.frames[frame] = Frame(frame, parent, text, st.index)
        self._record("demand", parent=parent, frame=frame, text=text, ref=ref, quote=quote)
        return frame

    def entry(self, frame: str, ref: str, quote: str, *, text: str = "", uses: Sequence[str] = (),
              binds: str = "", relation: str = "") -> Step:
        """Apply a dictionary entry, quoting its string verbatim."""
        if not str(ref).strip():
            raise TraceError("an ENTRY needs the entry number (ref)")
        if not str(quote).strip():
            raise TraceError("an ENTRY must quote the entry string it applies")
        self._verify_quote(ref, quote)
        return self._labelled("ENTRY", frame, text, ref=ref, quote=quote, uses=uses, binds=binds,
                              relation=relation)

    def _verify_quote(self, ref: str, quote: str) -> None:
        if not self.entries:
            return
        refs = [r.strip() for r in str(ref).split("/") if r.strip()]
        missing = [r for r in refs if r not in self.entries]
        if not refs or missing:
            raise TraceError(f"entry {ref!r} is not in the supplied entries ({', '.join(missing) or ref})")
        q = _squash(quote)
        if len([w for w in q.split() if re.search(r"\w", w)]) < 2:
            raise TraceError("an entry quote must contain at least two whole words")
        pattern = re.compile(r"(?<![\w'\u2019-])" + re.escape(q) + r"(?![\w'\u2019-])")

        def found(text: str) -> bool:
            for m in pattern.finditer(text):
                nxt = text[m.end():m.end() + 1]
                if not nxt or not unicodedata.combining(nxt):
                    return True
            return False

        if not all(found(self.entries[r]) for r in refs):
            raise TraceError(f"the quote is not verbatim (as whole words) from entry {ref}")

    def contract(self, frame: str, ref: str, text: str, *, source: str, uses: Sequence[str] = (),
                 binds: str = "", relation: str = "") -> Step:
        """Invoke a proposed connection (theory side). source must cite where it is proposed."""
        if not str(ref).strip():
            raise TraceError("a CONTRACT needs an id (ref)")
        if not str(source).strip():
            raise TraceError("a CONTRACT must cite its source")
        return self._labelled("CONTRACT", frame, text, ref=ref, source=source, uses=uses, binds=binds,
                              relation=relation)

    def reading(self, frame: str, text: str, *, uses: Sequence[str] = (), binds: str = "",
                relation: str = "") -> Step:
        """Record an interpretation that no entry or cited source states."""
        return self._labelled("READING", frame, text, uses=uses, binds=binds, relation=relation)

    def open(self, frame: str, text: str, *, uses: Sequence[str] = ()) -> Step:
        """Record a remaining gap. OPEN steps bind nothing."""
        return self._labelled("OPEN", frame, text, uses=uses)

    def input(self, frame: str, name: str, kind: str, text: str, *, value: str | int | Fraction | None = None,
              unit: str = "", relation: str = "", uses: Sequence[str] = ()) -> Step:
        """Supply scenario content and bind name to it: a value, a relation, or a fact.

        kind is one of INPUT_KINDS, or several joined by '/' (e.g.
        'recognition/model'). Numbers need a kind including 'value' or 'haze'.
        Supplied ideal model relations are INPUTs of kind 'model' (pass
        relation='lhs = rhs'), not CONTRACTs.
        """
        kind = self._parse_kind(kind)
        if value is not None and relation:
            raise TraceError("an INPUT binds a value or a relation, not both")
        if value is not None and not any(k in VALUE_KINDS for k in kind.split("/")):
            raise TraceError("an INPUT that supplies a number needs kind 'value' (or 'haze')")
        if not name:
            raise TraceError("an INPUT must bind a name")
        return self._labelled("INPUT", frame, text, kind=kind, binds=name, value=value, unit=unit,
                              relation=relation, uses=uses)

    def _labelled(self, op: str, frame: str, text: str, *, ref: str = "", quote: str = "", source: str = "",
                  kind: str = "", uses: Sequence[str] = (), binds: str = "", value=None, unit: str = "",
                  relation: str = "") -> Step:
        self._require_frame(frame)
        if op != "ENTRY" and not str(text).strip():
            raise TraceError(f"{op} needs text")
        if op == "OPEN" and (binds or relation):
            raise TraceError("an OPEN step binds nothing")
        if binds:
            self._validate_new_names([binds])
        if relation and not binds:
            raise TraceError("a relation needs a name (binds=...)")
        if relation:
            split_claim(relation)
        rel_names = list(mentioned_names(relation)) if relation else []
        self._quantities_only(rel_names)
        if op == "INPUT" and kind.split("/") == ["value"] and value is None and not relation:
            raise TraceError("an INPUT of kind 'value' must supply value=")
        names = list(dict.fromkeys(list(uses) + rel_names))
        deps = self._check_visible(frame, names, with_values=False)
        frac_value = _to_fraction(value) if value is not None else None
        body = text
        if op == "ENTRY":
            body = "“" + quote + "”" + (" — " + text if text else "")
        refs = ref
        if op == "CONTRACT":
            refs = f"{ref} ({source})"
        st = self._new_step(frame=frame, op=op, text=body, ref=refs, kind=kind, uses=tuple(names),
                            binds=(binds,) if binds else (), claim=relation, deps=tuple(sorted(set(deps))))
        if binds:
            if relation:
                self._bind(binds, "relation", frame, st.index, text=text, equation=relation)
            elif frac_value is not None:
                self._bind(binds, "value", frame, st.index, text=text, unit=unit)
                self._set_value(binds, frac_value, st.index)
            else:
                self._bind(binds, "fact", frame, st.index, text=text, unit=unit)
        args: dict = {"frame": frame, "text": text, "uses": list(uses)}
        if op == "ENTRY":
            args.update(ref=ref, quote=quote, binds=binds, relation=relation)
        elif op == "INPUT":
            args.update(name=binds, kind=kind, value=None if value is None else str(value), unit=unit,
                        relation=relation)
        elif op == "CONTRACT":
            args.update(ref=ref, source=source, binds=binds, relation=relation)
        elif op == "READING":
            args.update(binds=binds, relation=relation)
        self._record(op.lower(), **args)
        return st

    def unknown(self, frame: str, name: str, text: str, *, address: str, label: str = "CONTRACT",
                ref: str = "", quote: str = "", unit: str = "", uses: Sequence[str] = ()) -> Step:
        """Declare an addressed unknown quantity, e.g. a constraint force T1.

        address names the quantity and what it belongs to, e.g.
        'T(i_S1, B1, t0)'. Addresses are compared without whitespace; two
        unknowns may not share one. The introducing label is CONTRACT (needs
        ref, its source), ENTRY (needs ref and a verbatim quote) or READING.
        A quantity demanded by the question is introduced by READING or ENTRY;
        cite the normalization INPUT in uses.
        """
        self._require_frame(frame)
        if label not in ("CONTRACT", "ENTRY", "READING"):
            raise TraceError("an unknown is introduced by a CONTRACT, ENTRY or READING step; "
                             "cite any INPUT it rests on in uses")
        if label in ("CONTRACT", "ENTRY") and not str(ref).strip():
            raise TraceError(f"an unknown introduced by {label} must cite its ref")
        if label == "ENTRY":
            if not str(quote).strip():
                raise TraceError("an unknown introduced by ENTRY must quote the entry string")
            self._verify_quote(ref, quote)
        elif str(quote).strip():
            raise TraceError("only an unknown introduced by ENTRY carries a quote")
        if not str(address).strip():
            raise TraceError("an unknown needs an address")
        if not str(text).strip():
            raise TraceError("an unknown needs text")
        key = re.sub(r"\s+", "", address)
        for b in self.bindings.values():
            if b.sort == "unknown" and re.sub(r"\s+", "", b.address) == key and not self._rests_on_withdrawn(b.step):
                raise TraceError(f"address {address!r} is already used by {b.name!r}; "
                                 "distinct quantities need distinct addresses")
        self._validate_new_names([name])
        deps = self._check_visible(frame, uses, with_values=False)
        body = f"unknown {name} at {address}: {text}"
        if quote:
            body = "“" + quote + "” — " + body
        st = self._new_step(frame=frame, op=label, text=body, ref=ref, uses=tuple(uses), binds=(name,),
                            deps=tuple(sorted(set(deps))))
        self._bind(name, "unknown", frame, st.index, text=text, address=address, unit=unit)
        self._record("unknown", frame=frame, name=name, text=text, address=address, label=label, ref=ref,
                     quote=quote, unit=unit, uses=list(uses))
        return st

    def _delivery_plan(self, frame: str, name: str) -> tuple[str, bool]:
        """Check that name can be delivered into frame now. Returns (caller, carries_value)."""
        self._require_frame(frame)
        if frame == ROOT:
            raise TraceError("nothing can be delivered into the root; results flow up to it")
        b = self.bindings.get(name)
        if b is None:
            raise TraceError(f"{name!r} is not bound anywhere in this trace")
        if b.withdrawn is not None:
            raise TraceError(f"{name!r} was withdrawn at {self.steps[b.withdrawn].id} and cannot be delivered")
        gone = self._rests_on_withdrawn(b.step)
        if gone:
            raise TraceError(f"{name!r} rests on {gone!r}, which was withdrawn; it cannot be delivered")
        caller = self.frames[frame].parent
        assert caller is not None
        if self.visible(caller, name) is None:
            raise HiddenLookupError(f"{name!r} is not visible at the caller {caller!r}; deliver it there first "
                                    "(or use deliver_through)")
        carries = self.value_visible(caller, name) is not None
        name_here = self.visible(frame, name) is not None
        value_here = self.value_visible(frame, name) is not None
        if name_here and (value_here or not self._usable_value(name)):
            raise TraceError(f"{name!r} is already visible at {frame!r}; no delivery needed")
        if name_here and not carries:
            raise HiddenLookupError(f"the value of {name!r} is not visible at the caller {caller!r} either; "
                                    "deliver the value there first (or use deliver_through)")
        return caller, carries

    def deliver(self, frame: str, name: str, *, text: str = "") -> Step:
        """Pass an existing binding from the caller (frame's parent) down into frame.

        The caller must see the name; the value travels only if the caller
        sees the value too. A delivery is visible in frame and below. The
        original qualifications are copied in.
        """
        caller, carries = self._delivery_plan(frame, name)
        b = self.bindings[name]
        deps = [b.step] + ([self.value_step[name]] if carries else [])
        origin = self.steps[b.step]
        quals = b.text or origin.text
        if carries:
            unit = (" " + b.unit) if b.unit else ""
            head = f"{name} = {frac(self.values[name])}{unit}"
            vstep = self.value_step[name]
            source = f"bound at {origin.id}" + ("" if vstep == b.step else f", value fixed at {self.steps[vstep].id}")
        elif b.sort == "relation":
            head, source = f"{name}: {b.equation}", f"bound at {origin.id}"
        else:
            head, source = name, f"bound at {origin.id}"
        body = f"{head}, delivered from {caller} ({source}) with its qualifications: {quals}"
        if text:
            body += " \u2014 " + text
        st = self._new_step(frame=frame, op="DELIVER", text=body, ref=origin.id, uses=(name,),
                            deps=tuple(sorted(set(deps))))
        self.deliveries.setdefault(frame, {}).setdefault(name, []).append(_Delivery(st.index, carries))
        self._record("deliver", frame=frame, name=name, text=text)
        return st

    def deliver_many(self, frame: str, names: Sequence[str], *, text: str = "") -> list[Step]:
        """deliver() each name into frame; checks them all first, so it is all or nothing."""
        if isinstance(names, str):
            raise TraceError("deliver_many takes a list of names, not a string")
        names = list(names)
        if len(set(names)) != len(names):
            raise TraceError("names must not repeat")
        for n in names:
            self._delivery_plan(frame, n)
        return [self.deliver(frame, n, text=text) for n in names]

    def deliver_through(self, frame: str, name: str, *, text: str = "") -> list[Step]:
        """Deliver name from the nearest frame above that sees it (with its
        value, if it has a usable one) into the highest frame on the path down
        to frame. One DELIVER step: a delivery is visible in its frame and
        everything below it."""
        self._require_frame(frame)
        b = self.bindings.get(name)
        if b is None:
            raise TraceError(f"{name!r} is not bound anywhere in this trace")
        if b.withdrawn is not None:
            raise TraceError(f"{name!r} was withdrawn at {self.steps[b.withdrawn].id} and cannot be delivered")
        want_value = self._usable_value(name)

        def sees(f: str) -> bool:
            return self.visible(f, name) is not None and (not want_value or self.value_visible(f, name) is not None)

        if sees(frame):
            raise TraceError(f"{name!r} is already visible at {frame!r}; no delivery needed")
        path = self._ancestors(frame)
        for i in range(1, len(path)):
            if sees(path[i]):
                return [self.deliver(path[i - 1], name, text=text)]
        raise HiddenLookupError(f"{name!r} is not visible{' with its value' if want_value else ''} in any frame "
                                f"above {frame!r}")

    def withdraw(self, frame: str, name: str, text: str) -> Step:
        """Withdraw a premise (an INPUT binding). It cannot be used afterwards.

        Earlier steps stay as history. Answers recorded later that still rest
        on it are flagged in their ledger.
        """
        self._require_frame(frame)
        b = self.bindings.get(name)
        if b is None or self.steps[b.step].op != "INPUT":
            raise TraceError(f"{name!r} is not bound by an INPUT step")
        if b.withdrawn is not None:
            raise TraceError(f"{name!r} is already withdrawn")
        if not str(text).strip():
            raise TraceError("a withdrawal needs a reason")
        if self.visible(frame, name) is None:
            raise HiddenLookupError(f"{name!r} is not visible at {frame!r}; withdraw it where it is visible")
        st = self._new_step(frame=frame, op="WITHDRAW", text=text, ref=self.steps[b.step].id, uses=(name,),
                            deps=(b.step,))
        b.withdrawn = st.index
        self.__dict__.pop("_taint_cache", None)
        self._record("withdraw", frame=frame, name=name, text=text)
        return st

    def derive(self, frame: str, claim: str, *, from_relations: Sequence[str] = (), binds: str = "",
               name: str = "", tag: str = "", text: str = "", uses: Sequence[str] = ()) -> Step:
        """Record one arithmetic or algebraic step and check it exactly.

        Without from_relations the claim must be an identity once the visible
        values are substituted. With from_relations it must be a linear
        consequence of the cited relations, which must not contradict each
        other or the visible values. Only a smallest sufficient set of cited
        relations is recorded as provenance; superfluous citations are
        reported. A value that exists but is not visible here blocks the step
        (HiddenLookupError) only if it would change the verdict. binds names a
        declared unknown that the claim determines: the claim must read
        'binds = <constant>' and cite its relations; a value resting on a
        withdrawn premise may be determined again. name registers the claim as
        a relation. uses may cite further facts the step relies on. In strict
        mode a failed or uncheckable claim raises CheckError; in lenient mode
        it is recorded (a failure is a found mistake), determines nothing, and
        is flagged if an answer rests on it.
        """
        self._require_frame(frame)
        if name:
            self._validate_new_names([name])
        claim_names = list(mentioned_names(claim))
        self._quantities_only(claim_names)
        rels = list(dict.fromkeys(from_relations))
        for r in rels:
            self._relation(r)
        if binds:
            b = self.bindings.get(binds)
            if b is None or b.sort != "unknown":
                raise TraceError(f"binds must name a declared unknown, not {binds!r}")
            if self._usable_value(binds):
                raise TraceError(f"{binds!r} already has a value (from {self.steps[self.value_step[binds]].id})")
            if not rels:
                raise TraceError("a determined value must cite the relations it follows from")
            if split_claim(claim)[0].strip() != binds:
                raise TraceError(f"to determine {binds!r} the claim must read '{binds} = ...'")
        rel_names = self._relation_names(rels)
        all_names = list(dict.fromkeys(claim_names + rel_names))
        self._check_visible(frame, list(dict.fromkeys(claim_names + rels + list(uses))))
        self._check_visible(frame, rel_names)
        known = self.known_values(frame)
        check, detail, used_rels = self._check_claim(frame, claim, rels, known, all_names,
                                                     redetermining=binds)
        value = None
        if binds and check == "checked":
            rhs = split_claim(claim)[1]
            try:
                rf, _ = parse_expression(rhs, known)
            except Nonlinear:
                raise TraceError("the determined value must be a constant expression") from None
            if not rf.is_constant():
                self._raise_if_hidden(frame, rf.names())
                stale = [e for e in self._stale_values(frame, rf.names()) if e[0] != binds]
                if stale:
                    self._raise_stale(stale)
                raise TraceError(f"the right side still depends on {list(rf.names())}; it is not a value")
            value = rf.const
        if check != "checked" and self.strict:
            raise CheckError(f"{tag or 'derive'} at {frame}: {claim!r} {check}: {detail}")
        if check != "checked" and binds:
            detail += f"; {binds} not determined"
        dep_names = list(dict.fromkeys(claim_names + used_rels + self._relation_names(used_rels) + list(uses)))
        deps = self._check_visible(frame, dep_names)
        bound = tuple(x for x in ((binds if value is not None else ""), name) if x)
        st = self._new_step(frame=frame, op="DERIVE", text=text, ref=tag, claim=claim,
                            uses=tuple(dict.fromkeys(claim_names + rels + list(uses))), binds=bound, check=check,
                            detail=detail, deps=tuple(sorted(set(deps))), tag=tag)
        if value is not None:
            self._set_value(binds, value, st.index)
        if name:
            self._bind(name, "relation", frame, st.index, text=claim, equation=claim)
        self._record("derive", frame=frame, claim=claim, from_relations=rels, binds=binds, name=name, tag=tag,
                     text=text, uses=list(uses))
        return st

    def _raise_if_hidden(self, frame: str, residual_names: Iterable[str]) -> None:
        hidden = self._hidden_values(frame, residual_names)
        if hidden:
            raise HiddenLookupError(f"values of {hidden} exist but are not visible at {frame!r}; deliver them")

    def _verdict(self, claim: str, rels: Sequence[str], values: Mapping[str, Fraction]) -> tuple[str, str, list[str]]:
        """The check of claim against rels with the given values (no visibility logic)."""
        try:
            form, _ = parse_equation(claim, values)
        except Nonlinear as exc:
            return "unchecked", f"nonlinear ({exc}); not checked", list(rels)
        except UndefinedValue as exc:
            return "failed", f"mistake: the claim cannot be evaluated with these values ({exc})", []
        linear: list[tuple[str, Form]] = []
        skipped: list[str] = []
        for r in rels:
            try:
                linear.append((r, parse_equation(self._relation(r).equation, values)[0]))
            except Nonlinear:
                skipped.append(r)
            except UndefinedValue as exc:
                return "failed", f"conflict: relation {r} cannot be evaluated with these values ({exc})", [r]
        forms = [f for _, f in linear]
        if forms and not consistent(forms):
            return ("failed", f"conflict: the cited relations {', '.join(r for r, _ in linear)} contradict each "
                    "other or the values visible here", [r for r, _ in linear])
        try:
            pure = parse_equation(claim)[0].is_zero()
        except (Nonlinear, UndefinedValue):
            pure = False
        if form.is_zero():
            if pure:
                note = "identity"
            elif rels:
                note = ("holds identically once the visible values are substituted; the cited relations add "
                        "nothing (no independent content)")
            else:
                note = "identity once the visible values are substituted (no independent content)"
            return "checked", note, []
        if not rels:
            return "failed", f"mistake: not an identity: lhs - rhs = {form.render()}", []
        if forms and entails(forms, form):
            keep = needed_relations(forms, form)
            used = [linear[i][0] for i in keep]
            detail = "follows from " + ", ".join(used)
            extra = [r for r, _ in linear if r not in used]
            if extra:
                detail += f" (cited but not needed: {', '.join(extra)})"
            if skipped:
                detail += f" (nonlinear citations not checked: {', '.join(skipped)})"
            return "checked", detail, used
        if skipped:
            return ("unchecked", f"needs the nonlinear relations {', '.join(skipped)}, which cannot be checked with "
                    "the values visible here", list(rels))
        return "failed", f"mistake: does not follow from {', '.join(rels)} (lhs - rhs = {form.render()})", list(rels)

    def _check_claim(self, frame: str, claim: str, rels: Sequence[str], known: Mapping[str, Fraction],
                     names: Sequence[str], *, redetermining: str = "") -> tuple[str, str, list[str]]:
        verdict = self._verdict(claim, rels, known)
        kind = _category(verdict)
        hidden = self._hidden_values(frame, names)
        if hidden:
            full = {**known, **{h: self.values[h] for h in hidden}}
            if _category(self._verdict(claim, rels, full)) != kind:
                raise HiddenLookupError(f"values of {hidden} exist but are not visible at {frame!r} and would change "
                                        "the verdict; deliver them")
        stale = [e for e in self._stale_values(frame, names) if e[0] != redetermining]
        if stale and kind != "checked":
            with_stale = {**known, **{n: v for n, v, _ in stale}}
            if _category(self._verdict(claim, rels, with_stale)) != kind:
                self._raise_stale(stale)
        return verdict

    def _seen_entry(self, frame: str, name: str) -> tuple[Fraction, int] | None:
        """The latest value of name that frame has seen (bound in its subtree, or carried in by a
        delivery into its chain), as (value, step), whether or not it is still usable."""
        hist = self.value_history.get(name)
        if not hist or self.visible(frame, name) is None:
            return None
        carried = [d.step for d in self._chain_deliveries(frame, name) if d.carries_value]
        for v, at in reversed(hist):
            if self._in_subtree(self.steps[at].frame, frame) or any(d > at for d in carried):
                return v, at
        return None

    def _stale_values(self, frame: str, names: Iterable[str]) -> list[tuple[str, Fraction, int]]:
        """(name, value, step) for each name whose value, as last seen at frame, rests on a withdrawn
        premise, and which has no usable value visible at frame."""
        out = []
        for n in dict.fromkeys(names):
            if self.value_visible(frame, n) is not None:
                continue
            seen = self._seen_entry(frame, n)
            if seen is not None and self._rests_on_withdrawn(seen[1]):
                out.append((n, seen[0], seen[1]))
        return out

    def _raise_stale(self, stale: Sequence[tuple[str, Fraction, int]]) -> None:
        why = ", ".join(f"{n} (rests on {self._withdrawn_premises(at)[0]})" for n, _, at in stale)
        fresh = [n for n, _, _ in stale if self._usable_value(n)]
        hint = "".join(f" (a new value of {n} was determined at {self.steps[self.value_step[n]].id}; deliver it)"
                       for n in fresh)
        raise TraceError(f"the step needs the value of {why}, which rests on a withdrawn premise; "
                         f"determine it again first{hint}")

    def _raise_if_stale_linearises(self, frame: str, rels: Sequence[str], known: Mapping[str, Fraction], *,
                                   exempt: Sequence[str] = ()) -> None:
        """Refuse naming the withdrawn premise when the withdrawn values would make nonlinear relations
        checkable (linear or undefined)."""
        stale = [e for e in self._stale_values(frame, self._relation_names(rels)) if e[0] not in exempt]
        if not stale:
            return
        with_stale = {**known, **{n: v for n, v, _ in stale}}
        undefined = nonlinear = False
        for r in rels:  # every relation, so the order of rels does not matter
            try:
                parse_equation(self._relation(r).equation, with_stale)
            except Nonlinear:
                nonlinear = True
            except UndefinedValue:
                undefined = True
        if undefined or not nonlinear:
            self._raise_stale(stale)

    def _solve_forms(self, frame: str, rels: Sequence[str], unknowns: Sequence[str]) -> list[Form]:
        rel_names = self._relation_names(rels)
        known = self.known_values(frame)
        forms: list[Form] = []
        nonlinear: Nonlinear | None = None
        for r in rels:  # an undefined relation raises whatever its position; nonlinear ones are reported after
            try:
                forms.append(self._relation_form(r, known))
            except Nonlinear as exc:
                nonlinear = nonlinear or exc
        if nonlinear is not None:
            self._raise_if_hidden(frame, rel_names)
            self._raise_if_stale_linearises(frame, rels, known, exempt=unknowns)
            raise TraceError(f"cannot solve: {nonlinear}") from None
        for r, f in zip(rels, forms):
            stray = [n for n in f.names() if n not in unknowns]
            if stray:
                self._raise_if_hidden(frame, stray)
                stale = self._stale_values(frame, stray)
                if stale:
                    self._raise_stale(stale)
                raise TraceError(f"relation {r} mentions {stray}, which are neither visible values nor listed unknowns")
        return forms

    def solve(self, frame: str, relations: Sequence[str], unknowns: Sequence[str], *, tag: str = "",
              text: str = "linear solve", uses: Sequence[str] = ()) -> Step:
        """EXTERNAL exact linear solve.

        Records one EXTERNAL report step, then one checked DERIVE step per
        unknown the relations fix ('x = value'), whose provenance is a smallest
        set of relations that fixes that unknown. So an answer naming x rests
        only on x's relations. Reports a family with its rank and free
        unknowns, or an inconsistency (a conflict, listed in the ledger).
        Returns the report step.
        """
        self._require_frame(frame)
        rels = list(relations)
        unk = list(unknowns)
        if not unk:
            raise TraceError("solve needs unknowns; use consistency() to check relations without unknowns")
        if len(set(rels)) != len(rels) or len(set(unk)) != len(unk):
            raise TraceError("relations and unknowns must not repeat")
        for r in rels:
            self._relation(r)
        for u in unk:
            b = self.bindings.get(u)
            if b is None or b.sort != "unknown":
                raise TraceError(f"{u!r} is not a declared unknown")
            if self._usable_value(u):
                raise TraceError(f"{u!r} already has a value")
        rel_names = self._relation_names(rels)
        deps = self._check_visible(frame, list(dict.fromkeys(rels + unk + rel_names + list(uses))))
        forms = self._solve_forms(frame, rels, unk)
        result = solve_linear(forms, unk)
        big = [k for k, v in result["values"].items() if _too_big(v)]
        if big:
            raise TraceError(f"cannot solve: the values of {big} are too large to record exactly")
        per_value: dict[str, tuple[list[str], list[int]]] = {}
        if result["status"] != "inconsistent":
            for k, v in result["values"].items():
                rels_k = [rels[i] for i in needed_relations(forms, Form.of({k: Fraction(1)}, -v))]
                names_k = list(dict.fromkeys(rels_k + self._relation_names(rels_k) + list(uses)))
                per_value[k] = (rels_k, self._check_visible(frame, names_k))
        used = list(dict.fromkeys(r for rk, _ in per_value.values() for r in rk))
        fixed = ", ".join(f"{k} = {frac(v)}" for k, v in result["values"].items())
        if result["status"] == "unique":
            detail = "unique: " + fixed
        elif result["status"] == "family":
            detail = (f"underdetermined: {len(forms)} relations in {len(unk)} unknowns, rank {result['rank']}; "
                      f"free: {', '.join(result['free'])}")
            if fixed:
                detail += f"; fixed anyway: {fixed}"
        else:
            detail = "conflict: inconsistent, the relations have no common solution"
        unneeded = [r for r in rels if r not in used]
        if unneeded and per_value:
            detail += f" (relations not needed for the fixed values: {', '.join(unneeded)})"
        st = self._new_step(frame=frame, op="EXTERNAL", text=text, ref="linear solve", kind="solve",
                            uses=tuple(rels + unk + list(uses)), binds=tuple(result["values"]),
                            check="failed" if result["status"] == "inconsistent" else "checked", detail=detail,
                            deps=tuple(sorted(set(deps))), tag=tag)
        for k, v in result["values"].items():
            rels_k, deps_k = per_value[k]
            vs = self._new_step(frame=frame, op="DERIVE", text=f"value fixed by the linear solve {st.id}", ref=tag,
                                claim=f"{k} = {frac(v)}", uses=tuple(rels_k), binds=(k,), check="checked",
                                detail="follows from " + ", ".join(rels_k), deps=tuple(sorted(set(deps_k))), tag=tag)
            self._set_value(k, v, vs.index)
            self.solve_children.setdefault(st.index, []).append(vs.index)
        self._record("solve", frame=frame, relations=rels, unknowns=unk, tag=tag, text=text, uses=list(uses))
        return st

    def consistency(self, frame: str, relations: Sequence[str], *, text: str = "consistency check",
                    tag: str = "", uses: Sequence[str] = ()) -> Step:
        """EXTERNAL check that the relations have a common solution with the values
        visible here. An inconsistency is recorded as a conflict and never
        raises, so a deliberate conflict can be recorded in strict mode. A
        hidden value that would change the result raises HiddenLookupError."""
        self._require_frame(frame)
        rels = list(relations)
        if not rels or len(set(rels)) != len(rels):
            raise TraceError("consistency needs distinct relations")
        for r in rels:
            self._relation(r)
        rel_names = self._relation_names(rels)
        deps = self._check_visible(frame, list(dict.fromkeys(rels + rel_names + list(uses))))
        known = self.known_values(frame)

        def result(values: Mapping[str, Fraction]) -> bool | None:
            """False (a conflict) if any relation is undefined or the linear ones are inconsistent; None
            (refused) if some relation is nonlinear and nothing else decides; True otherwise."""
            forms, nonlinear = [], False
            for r in rels:
                try:
                    forms.append(parse_equation(self._relation(r).equation, values)[0])
                except Nonlinear:
                    nonlinear = True
                except UndefinedValue:
                    return False
            if forms and not consistent(forms):
                return False
            return None if nonlinear else True

        ok = result(known)
        hidden = self._hidden_values(frame, rel_names)
        if hidden and result({**known, **{h: self.values[h] for h in hidden}}) != ok:
            raise HiddenLookupError(f"values of {hidden} exist but are not visible at {frame!r} and would change "
                                    "the result; deliver them")
        if ok is None:
            stale = self._stale_values(frame, rel_names)
            if stale and result({**known, **{n: v for n, v, _ in stale}}) is not None:
                self._raise_stale(stale)  # the withdrawn values would decide this check
            raise TraceError("cannot check consistency: the relations are nonlinear with the values visible here")
        detail = "consistent" if ok else (f"conflict: {', '.join(rels)} contradict each other or the values "
                                          "visible here")
        st = self._new_step(frame=frame, op="EXTERNAL", text=text, ref="consistency check", kind="consistency",
                            uses=tuple(rels + list(uses)), check="checked" if ok else "failed", detail=detail,
                            deps=tuple(sorted(set(deps))), tag=tag)
        self._record("consistency", frame=frame, relations=rels, text=text, tag=tag, uses=list(uses))
        return st

    def external(self, frame: str, competence: str, text: str, *, uses: Sequence[str] = (),
                 relation: str = "", binds: str = "", tag: str = "") -> Step:
        """Record a named external competence whose output is NOT checked here
        (e.g. differentiation). Its output may be registered as a relation."""
        self._require_frame(frame)
        if not str(competence).strip() or not str(text).strip():
            raise TraceError("an EXTERNAL step needs a competence name and text")
        if relation and not binds:
            raise TraceError("a relation needs a name (binds=...)")
        if binds and not relation:
            raise TraceError("an EXTERNAL step binds only a relation")
        if binds:
            self._validate_new_names([binds])
        if relation:
            split_claim(relation)
        rel_names = list(mentioned_names(relation)) if relation else []
        self._quantities_only(rel_names)
        names = list(dict.fromkeys(list(uses) + rel_names))
        deps = self._check_visible(frame, names, with_values=False)
        st = self._new_step(frame=frame, op="EXTERNAL", text=text, ref=competence, uses=tuple(names),
                            binds=(binds,) if binds else (), claim=relation, check="unchecked",
                            detail="output of an external competence; not checked here",
                            deps=tuple(sorted(set(deps))), tag=tag)
        if binds:
            self._bind(binds, "relation", frame, st.index, text=relation, equation=relation)
        self._record("external", frame=frame, competence=competence, text=text, uses=list(uses),
                     relation=relation, binds=binds, tag=tag)
        return st

    def answer(self, names: Sequence[str], text: str = "", *, label: str = "") -> Step:
        """Record an answer at the root. Every name must have a value visible there.

        A trace may have several answers; label distinguishes them (default:
        the first free p1, p2, ...). Labels use letters, digits, '_', '-', '.'.
        Steps recorded after an answer cannot feed it.
        """
        if not names:
            raise TraceError("an answer needs at least one name")
        used = {lb for lb, _ in self.answers}
        if label:
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+", label):
                raise TraceError(f"answer labels use letters, digits, '_', '-' or '.': {label!r}")
            if label in used:
                raise TraceError(f"answer label {label!r} is already used")
        else:
            label = next(f"p{i}" for i in itertools.count(1) if f"p{i}" not in used)
        deps = self._check_visible(ROOT, names)
        for n in names:
            if self.value_visible(ROOT, n) is None:
                if n in self.values:
                    gone = self._rests_on_withdrawn(self.value_step[n])
                    if gone:
                        raise TraceError(f"the value of {n!r} rests on {gone!r}, which was withdrawn; determine it again")
                raise TraceError(f"{n!r} has no value visible at the root")
        parts = []
        for n in names:
            unit = self.bindings[n].unit
            parts.append(f"{n} = {frac(self.values[n])}{(' ' + unit) if unit else ''}")
        st = self._new_step(frame=ROOT, op="ANSWER", text=text, ref=label, uses=tuple(names),
                            detail=", ".join(parts), deps=tuple(sorted(set(deps))), tag=label)
        self.answers.append((label, st.index))
        self._record("answer", names=list(names), text=text, label=label)
        return st

    def annotate(self, name: str, status: str, *, countermodel: str = "", note: str = "",
                 answer: str = "", check: Mapping | None = None) -> None:
        """Attach a NEEDS/REQUIRED/ENTAILED/USES status to an INPUT's binding.

        Need is relative to a prediction: pass answer=label to annotate for
        one answer only; without it the status applies to every answer that
        has no status of its own for this premise. NEEDS requires a
        countermodel: a world where every other premise holds and the
        prediction fails. ENTAILED and USES prune the premise from that
        answer's hypothesis set.

        check= makes the status checked, against answer= (required). For
        NEEDS, REQUIRED and USES it is a countermodel in the form
        check_countermodel takes (replace=, remove=, add=, values=,
        drop_dependents=); for ENTAILED it is {'entailed_by': [names]} (see
        check_entailed). The result is kept with the annotation, shown in the
        ledger, and warned about when it does not support the status:
        NEEDS and REQUIRED need 'refutes p' or 'p does not follow', ENTAILED
        needs 'entailed', USES needs 'p still follows'.
        """
        b = self.bindings.get(name)
        if b is None or self.steps[b.step].op != "INPUT":
            raise TraceError(f"{name!r} is not bound by an INPUT step")
        if status not in STATUSES:
            raise TraceError(f"status must be one of {STATUSES}")
        if status == "NEEDS" and not str(countermodel).strip():
            raise TraceError("a NEEDS status requires a countermodel")
        if answer and answer not in {lb for lb, _ in self.answers}:
            raise TraceError(f"no answer labelled {answer!r}")
        result = None
        if check is not None:
            if not answer:
                raise TraceError("a checked status needs answer=: need is relative to one prediction")
            spec = dict(check)
            try:
                if status == "ENTAILED":
                    extra = set(spec) - {"entailed_by"}
                    if extra:
                        raise TraceError(f"an ENTAILED check takes only entailed_by=, not {sorted(extra)}")
                    result = self.check_entailed(name, answer=answer, by=spec.get("entailed_by", ()))
                else:
                    result = self.check_countermodel(name, answer=answer, **spec)
            except TypeError as exc:
                raise TraceError(f"malformed check for {name}: {exc}") from None
            result["supports"] = _supports(status, result["verdict"])
        entry = {"status": status, "countermodel": countermodel, "note": note}
        if result is not None:
            entry["check"] = result
        self.annotations.setdefault(name, {})[answer or "*"] = entry
        args = dict(name=name, status=status, countermodel=countermodel, note=note, answer=answer)
        if check is not None:
            args["check"] = dict(check)
        self._record("annotate", **args)

    # -- checked countermodels -------------------------------------------------

    def _premise_system(self, answer: str) -> tuple[dict[str, str], dict[str, Fraction]]:
        """The answer's premise relations (bound by INPUT, ENTRY, CONTRACT, READING or EXTERNAL; DERIVE
        relations are consequences and are recomputed) and its supplied INPUT values, as of the answer."""
        idx = self._answer_index(answer)
        cone = self.cone(answer)
        rels: dict[str, str] = {}
        vals: dict[str, Fraction] = {}
        for b in self.bindings.values():
            if b.step not in cone or (b.withdrawn is not None and b.withdrawn < idx):
                continue
            st = self.steps[b.step]
            if b.sort == "relation" and st.op in ("INPUT", "ENTRY", "CONTRACT", "READING", "EXTERNAL"):
                rels[b.name] = b.equation
            elif b.sort == "value" and st.op == "INPUT":
                v = self._value_from_step(b.name, st.index)
                if v is not None:
                    vals[b.name] = v
        return rels, vals

    def _answer_targets(self, answer: str) -> dict[str, Fraction]:
        idx = self._answer_index(answer)
        out = {}
        for n in self.steps[idx].uses:
            earlier = [v for v, at in self.value_history.get(n, []) if at < idx]
            out[n] = earlier[-1]
        return out

    def _premises_of(self, name: str) -> set[str]:
        """The INPUT premises in the dependency closure of name's binding step (name itself if an INPUT)."""
        seen: set[int] = set()
        stack = [self.bindings[name].step]
        out: set[str] = set()
        while stack:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            st = self.steps[i]
            if st.op == "INPUT":
                out.add(st.binds[0])
            stack.extend(st.deps)
        return out

    def _check_premise(self, premise: str, answer: str) -> Binding:
        b = self.bindings.get(premise)
        if b is None or self.steps[b.step].op != "INPUT":
            raise TraceError(f"{premise!r} is not bound by an INPUT step")
        if b.step not in self.cone(answer):
            raise TraceError(f"{premise!r} does not feed answer {answer!r}")
        return b

    def check_countermodel(self, premise: str, *, answer: str, replace: Mapping[str, object] | None = None,
                           remove: Sequence[str] = (), add: Sequence[str] = (),
                           values: Mapping[str, object] | None = None, drop_dependents: bool = False) -> dict:
        """Check a countermodel to premise for answer, exactly. Records nothing.

        The answer is rebuilt from its premise relations and supplied values
        (relations bound by DERIVE are consequences and are left out). The
        rebuilt system must reproduce the answer. The countermodel then
        changes it: replace= gives a premise relation a new equation or a
        supplied value a new value; remove= drops relations or values; add=
        adds equations (new names are new quantities, free unless values=
        gives them a value); drop_dependents=True drops every premise
        relation and value that rests on the premise (the test for a
        precondition: without it the relations it licenses do not apply).

        Verdicts: 'refutes p' (consistent, and some answer quantity is fixed
        to another value: p fails in every such world), 'p does not follow'
        (consistent, nothing fixed otherwise, something left open: p fails in
        some such world), 'p still follows', 'inconsistent' (no such world),
        'cannot check' (the recorded premises do not reproduce p, or
        nonlinear relations keep the question open).

        Also reported: 'outside' lists changed relations or values that do
        not rest on the premise (a countermodel should keep every other
        premise), and 'violates' says whether the countermodel makes the
        premise false (True, False, or None when that is not decidable here,
        as for a premise with no relation or value).
        """
        b = self._check_premise(premise, answer)
        rels, vals = self._premise_system(answer)
        targets = self._answer_targets(answer)
        base = _evaluate(rels, vals)
        base_verdict, base_detail = _judge(base, targets)
        result = {"premise": premise, "answer": answer, "outside": {}, "violates": None, "changed": []}
        if base_verdict != "p still follows":
            return {**result, "verdict": "cannot check",
                    "detail": f"the recorded premise relations do not reproduce the answer ({base_verdict}: "
                              f"{base_detail})", "summary": "cannot check: the premises do not reproduce p"}
        replace = dict(replace or {})
        values = dict(values or {})
        remove = list(remove)
        add = [str(e) for e in add]
        for n in list(replace) + remove:
            if n not in rels and n not in vals:
                raise TraceError(f"{n!r} is not a premise relation or supplied value of answer {answer!r}")
        for n in values:
            if n in self.bindings:
                raise TraceError(f"values= names new quantities; {n!r} exists, so constrain it with add=")
            if not n.isidentifier():
                raise TraceError(f"values= keys must be names, not {n!r}")
        new_rels = {k: v for k, v in rels.items() if k not in remove}
        new_vals = {k: v for k, v in vals.items() if k not in remove}
        for n, v in replace.items():
            if n in rels:
                eq = str(v)
                split_claim(eq)
                self._quantities_only(mentioned_names(eq))
                new_rels[n] = eq
            else:
                new_vals[n] = _to_fraction(v)
        changed = list(dict.fromkeys(list(replace) + remove))
        if drop_dependents:
            for n in list(new_rels) + list(new_vals):
                if n == premise or premise in self._premises_of(n):
                    new_rels.pop(n, None)
                    new_vals.pop(n, None)
                    changed.append(n)
        for i, eq in enumerate(add, 1):
            split_claim(eq)
            self._quantities_only(mentioned_names(eq))
            new_rels[f"(added {i})"] = eq
        for n, v in values.items():
            new_vals[n] = _to_fraction(v)
        world = _evaluate(new_rels, new_vals)
        verdict, detail = _judge(world, targets)
        outside = {c: sorted(self._premises_of(c)) for c in dict.fromkeys(changed)
                   if c != premise and premise not in self._premises_of(c)}
        violates = self._violates(premise, b, rels, vals, new_rels, new_vals, world)
        summary = f"{verdict}: {detail}" if detail else verdict
        return {**result, "verdict": verdict, "detail": detail, "summary": summary, "outside": outside,
                "violates": violates, "changed": list(dict.fromkeys(changed))}

    def _violates(self, premise, b, rels, vals, new_rels, new_vals, world) -> bool | None:
        if premise in vals:
            if premise not in new_vals:
                return None
            return new_vals[premise] != vals[premise]
        if premise in rels:
            if new_rels.get(premise) == rels[premise]:
                return False
            if world["status"] != "consistent":
                return None
            with_it = _evaluate({**new_rels, "(premise)": rels[premise]}, new_vals)
            if with_it["status"] != "consistent":
                return True
            try:
                form = parse_equation(rels[premise], world["known"])[0]
            except (Nonlinear, UndefinedValue):
                return None
            if form.is_zero() or (world["forms"] and entails(world["forms"], form)):
                return False
            return None
        return None

    def check_entailed(self, premise: str, *, answer: str, by: Sequence[str] = ()) -> dict:
        """Check that premise's relation or value follows from other premises of answer. Records nothing.

        by= names the premise relations and supplied values that entail it
        (default: all the others). Verdicts: 'entailed', 'not entailed' (the
        recorded relations leave it open or contradict it), 'cannot check'
        (the premise carries no relation or value, or nonlinear relations
        keep it open).
        """
        self._check_premise(premise, answer)
        rels, vals = self._premise_system(answer)
        result = {"premise": premise, "answer": answer, "outside": {}, "violates": None, "changed": []}
        if premise not in rels and premise not in vals:
            return {**result, "verdict": "cannot check", "detail": f"{premise} carries no relation or value",
                    "summary": f"cannot check: {premise} carries no relation or value"}
        by = list(by)
        for n in by:
            if n not in rels and n not in vals:
                raise TraceError(f"{n!r} is not a premise relation or supplied value of answer {answer!r}")
            if n == premise:
                raise TraceError("a premise cannot entail itself")
            if self._licensed_by(n, premise):
                raise TraceError(f"{n!r} rests on {premise!r}, so it cannot show that {premise!r} is entailed")
        use_rels = {k: v for k, v in rels.items()
                    if k != premise and (not by or k in by) and not self._licensed_by(k, premise)}
        use_vals = {k: v for k, v in vals.items()
                    if k != premise and (not by or k in by) and not self._licensed_by(k, premise)}
        world = _evaluate(use_rels, use_vals)
        cited = ", ".join(by) if by else "the other premises"
        if world["status"] != "consistent":
            return {**result, "verdict": "cannot check", "detail": f"{cited} are {world['status']}",
                    "summary": f"cannot check: {cited} are {world['status']}"}
        if premise in vals:
            ok = world["known"].get(premise) == vals[premise]
        else:
            try:
                form = parse_equation(rels[premise], world["known"])[0]
            except Nonlinear:
                return {**result, "verdict": "cannot check", "detail": f"{premise} stays nonlinear",
                        "summary": f"cannot check: {premise} stays nonlinear"}
            except UndefinedValue:
                ok = False
            else:
                ok = form.is_zero() or bool(world["forms"]) and entails(world["forms"], form)
        if ok:
            return {**result, "verdict": "entailed", "detail": f"by {cited}", "summary": f"entailed by {cited}"}
        if world["nonlinear"]:
            nl = ", ".join(world["nonlinear"])
            return {**result, "verdict": "cannot check", "detail": f"the nonlinear relations {nl} may fix it",
                    "summary": f"cannot check: the nonlinear relations {nl} may fix it"}
        return {**result, "verdict": "not entailed", "detail": f"{cited} leave it open",
                "summary": f"not entailed by {cited}"}

    def _licensed_by(self, name: str, premise: str) -> bool:
        """Whether name's binding rests on premise other than by merely mentioning it as a quantity: the
        circularity test for ENTAILED. A relation that only mentions a supplied value (F = k*x for the value
        k) does not rest on k in this sense; one registered with uses=[k], or resting on a relation that
        rests on k, does."""
        target = self.bindings[premise].step
        b = self.bindings[name]
        root = b.step
        mentioned = set(mentioned_names(b.equation)) if b.sort == "relation" and b.equation else set()
        skip = {self.bindings[m].step for m in mentioned if m in self.bindings and m == premise}
        seen: set[int] = set()
        stack = [d for d in self.steps[root].deps if d not in skip]
        while stack:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            if i == target:
                return True
            stack.extend(self.steps[i].deps)
        return False

    @staticmethod
    def _check_warnings(nm: str, status: str, chk: dict) -> list[str]:
        out = []
        if chk["supports"] is False:
            out.append(f"the check of {nm} does not support {status}: {chk['summary']}")
        elif chk["supports"] is None:
            out.append(f"the check of {nm} could not be made: {chk['detail']}")
        for c, prem in chk["outside"].items():
            out.append(f"the countermodel for {nm} also changes {c}, which does not rest on {nm} (it rests on "
                       f"{', '.join(prem) or 'no INPUT'})")
        if chk["violates"] is False:
            out.append(f"the countermodel for {nm} leaves {nm} true, so it is not a countermodel to it")
        return out

    def _annotation(self, name: str, label: str) -> dict:
        per = self.annotations.get(name, {})
        return per.get(label) or per.get("*") or {}

    # -- analysis ---------------------------------------------------------------

    def _answer_index(self, answer: str | None) -> int:
        if not self.answers:
            raise TraceError("no answer recorded yet")
        if answer is None:
            return self.answers[-1][1]
        for lb, idx in self.answers:
            if lb == answer:
                return idx
        raise TraceError(f"no answer labelled {answer!r}")

    def cone(self, answer: str | None = None) -> set[int]:
        """Indices of every step an answer depends on, including the answer."""
        start = self._answer_index(answer)
        cache = self.__dict__.setdefault("_cone_cache", {})
        if start in cache:
            return set(cache[start])
        seen: set[int] = set()
        stack = [start]
        while stack:
            i = stack.pop()
            if i not in seen:
                seen.add(i)
                stack.extend(self.steps[i].deps)
        cache[start] = frozenset(seen)
        return seen

    def _input_content(self, st: Step) -> str:
        nm = st.binds[0]
        if st.claim:
            return f"{st.claim} ({st.text})"
        v = self._value_from_step(nm, st.index)
        if v is not None:
            unit = self.bindings[nm].unit
            return f"{nm} = {frac(v)}{(' ' + unit) if unit else ''} ({st.text})"
        return st.text

    def ledger(self, answer: str | None = None) -> dict:
        """Sort the trace for one answer's hypothesis-set work (default: the last answer).

        theory:         ENTRY / CONTRACT / READING steps that feed the answer.
        commitments:    INPUT steps that feed the answer and are members of H.
        pruned:         INPUT steps that feed the answer but are not members:
                        status ENTAILED or USES for this answer, or only
                        non-world kinds (convention, choice).
        step_members:   DERIVE / EXTERNAL steps that feed the answer.
        not_in_answer:  INPUT steps that never feed the answer.
        outside_answer: other labelled steps that do not feed the answer.
        mistakes:       failed arithmetic checks (found mistakes).
        conflicts:      contradictions among premises: cited relations that
                        contradict each other or the visible values, failed
                        solves and consistency checks, and relations in the
                        answer's provenance that the trace's determined values
                        contradict (a global bookkeeping check).
        Feeding the answer is necessary for a premise to be needed, not
        sufficient; statuses refine it by countermodel.
        """
        idx = self._answer_index(answer)
        cone = self.cone(answer)
        ans = self.steps[idx]
        label = ans.tag
        out: dict = {"label": label, "answer": ans.detail, "theory": [], "commitments": [], "pruned": [],
                     "step_members": [], "not_in_answer": [], "outside_answer": [], "open": [], "mistakes": [],
                     "conflicts": [], "unchecked": [], "solve_reports": [], "withdrawn": [], "undetermined": [],
                     "warnings": []}
        unannotated: list[str] = []
        seen_inputs: dict[tuple, list[str]] = {}
        seen_values: dict[str, tuple[str, str]] = {}
        all_cones = {lb: self.cone(lb) for lb, _ in self.answers}
        for st in self.steps:
            row = {"step": st.id, "op": st.op, "ref": st.ref, "text": st.text}
            if st.op == "OPEN":
                out["open"].append(row)
            if st.check == "failed":
                key = "mistakes" if st.detail.startswith("mistake") else "conflicts"
                out[key].append({**row, "claim": st.claim, "detail": st.detail})
                if st.index in cone:
                    out["warnings"].append(f"the answer rests on {st.id}, whose check failed")
            elif st.check == "unchecked":
                out["unchecked"].append({**row, "claim": st.claim, "detail": st.detail})
                if st.index in cone and st.op == "DERIVE":
                    out["warnings"].append(f"the answer rests on {st.id}, which could not be checked")
            if st.op == "EXTERNAL" and st.kind == "solve" and not st.detail.startswith("unique"):
                out["solve_reports"].append({**row, "detail": st.detail})
            if st.op == "INPUT":
                nm = st.binds[0]
                b = self.bindings[nm]
                ann = self._annotation(nm, label)
                item = {**row, "name": nm, "kind": st.kind, "relation": st.claim, "content": self._input_content(st),
                        "status": ann.get("status", ""), "countermodel": ann.get("countermodel", ""),
                        "note": ann.get("note", "")}
                chk = ann.get("check")
                if chk is not None:
                    item["check"] = chk["summary"]
                    if st.index in cone and label == chk["answer"]:
                        out["warnings"].extend(self._check_warnings(nm, ann["status"], chk))
                own = self._value_from_step(nm, st.index)
                own_value = own is not None
                vtxt = frac(own) if own_value else ""
                key = (st.kind, _squash(st.text), st.claim, vtxt)
                if key in seen_inputs:
                    # compare with the latest earlier INPUT of this description that is still usable, if any
                    usable = [n for n in seen_inputs[key] if self.bindings[n].withdrawn is None
                              and not self._rests_on_withdrawn(self.bindings[n].step)]
                    first = usable[-1] if usable else seen_inputs[key][0]
                    fb = self.bindings[first]
                    if fb.withdrawn is not None:
                        when = "was withdrawn" if fb.withdrawn < st.index else "has since been withdrawn"
                        out["warnings"].append(f"{nm} repeats {first} word for word; {first} {when} at "
                                               f"{self.steps[fb.withdrawn].id}, and {nm} was not withdrawn with it")
                    elif self._rests_on_withdrawn(fb.step):
                        out["warnings"].append(f"{nm} repeats {first} word for word; {first} rests on "
                                               f"{self._rests_on_withdrawn(fb.step)}, which was withdrawn, so it "
                                               "cannot be delivered")
                    else:
                        out["warnings"].append(f"{nm} repeats the INPUT {first} word for word; deliver the original "
                                               "instead of re-supplying it")
                elif own_value:
                    vkey = _squash(st.text)
                    if vkey in seen_values and seen_values[vkey][1] != vtxt:
                        out["warnings"].append(f"{nm} has the same description as {seen_values[vkey][0]} but a "
                                               "different value")
                seen_inputs.setdefault(key, []).append(nm)
                if own_value:
                    seen_values.setdefault(_squash(st.text), (nm, vtxt))
                if b.withdrawn is not None:
                    out["withdrawn"].append({**item, "withdrawn_at": self.steps[b.withdrawn].id})
                    if st.index in cone and b.withdrawn < idx:
                        out["warnings"].append(f"the answer rests on {nm}, withdrawn at {self.steps[b.withdrawn].id}")
                if st.index in cone:
                    non_world = all(k in NON_WORLD_KINDS for k in st.kind.split("/"))
                    if item["status"] in PRUNED_STATUSES or non_world:
                        item["why_pruned"] = (f"status {item['status']}" if item["status"] in PRUNED_STATUSES
                                              else f"kind {st.kind} is not a claim about the world")
                        if non_world and item["status"] in ("NEEDS", "REQUIRED"):
                            out["warnings"].append(f"{nm} is marked {item['status']} but its kind {st.kind} is not a "
                                                   "claim about the world, so it is not a member")
                        out["pruned"].append(item)
                    else:
                        out["commitments"].append(item)
                        if not item["status"]:
                            unannotated.append(nm)
                else:
                    out["not_in_answer"].append(item)
                    if item["status"] in ("NEEDS", "REQUIRED"):
                        scoped = label in self.annotations.get(nm, {})
                        if scoped or not any(st.index in c for c in all_cones.values()):
                            out["warnings"].append(f"{nm} is marked {item['status']} but does not feed this answer")
            elif st.op in ("ENTRY", "CONTRACT", "READING"):
                (out["theory"] if st.index in cone else out["outside_answer"]).append(row)
            elif st.op in ("DERIVE", "EXTERNAL"):
                if st.kind == "solve" and any(c in cone for c in self.solve_children.get(st.index, [])):
                    continue  # its per-value DERIVE steps carry the answer's provenance
                if st.index in cone:
                    out["step_members"].append({**row, "claim": st.claim, "check": st.check, "tag": st.tag})
                else:
                    out["outside_answer"].append({**row, "claim": st.claim})
        # Global bookkeeping (not a step, so not a lookup): with the values fixed before this answer that rest on
        # no premise withdrawn before it, is any relation the answer rests on contradicted, alone or jointly?
        as_of: dict[str, Fraction] = {}
        for n, hist in self.value_history.items():
            for v, at in reversed(hist):
                if at < idx:
                    if not self._rests_on_withdrawn(at, before=idx):
                        as_of[n] = v
                    break
        joint: list[tuple[str, Form]] = []
        for b in self.bindings.values():
            if b.sort != "relation" or b.step not in cone:
                continue
            if b.withdrawn is not None and b.withdrawn < idx:
                continue
            if self.steps[b.step].check == "failed" or self._rests_on_withdrawn(b.step, before=idx):
                continue
            row = {"step": self.steps[b.step].id, "op": self.steps[b.step].op, "ref": b.name, "text": b.text,
                   "claim": b.equation}
            try:
                f = parse_equation(b.equation, as_of)[0]
            except Nonlinear:
                continue
            except UndefinedValue as exc:
                out["conflicts"].append({**row, "detail": f"conflict: {b.name} cannot be evaluated with the values "
                                                          f"determined in this trace ({exc})"})
                out["warnings"].append(f"the answer rests on {b.name}, which the trace's own values make undefined")
                continue
            if f.is_constant() and f.const != 0:
                out["conflicts"].append({**row, "detail": f"conflict: {b.name} is contradicted by the values "
                                                          f"determined in this trace (lhs - rhs = {f.render()})"})
                out["warnings"].append(f"the answer rests on {b.name}, which the trace's own values contradict")
            elif not f.is_zero():
                joint.append((b.name, f))
        if joint and not consistent([f for _, f in joint]):
            core = list(joint)
            for item in list(core):
                trial = [x for x in core if x is not item]
                if trial and not consistent([f for _, f in trial]):
                    core = trial
            names_j = ", ".join(n for n, _ in core)
            out["conflicts"].append({"step": "", "op": "", "ref": names_j, "text": "", "claim": "",
                                     "detail": f"conflict: the relations {names_j}, which this answer rests on, are "
                                               "jointly inconsistent with the values determined in this trace"})
            out["warnings"].append(f"the answer rests on relations that are jointly inconsistent: {names_j}")
        for b in self.bindings.values():
            if b.sort == "unknown" and not self._usable_value(b.name):
                entry = {"name": b.name, "address": b.address, "step": self.steps[b.step].id, "note": ""}
                entry["note"] = self._undetermined_note(b.name, idx)
                out["undetermined"].append(entry)
        if unannotated:
            out["warnings"].append(f"{len(unannotated)} commitment(s) have no status yet: {', '.join(unannotated)}")
        return out

    def hypothesis_set(self, answer: str | None = None) -> list[dict]:
        """The prediction side of H for one answer: {p} + one negated
        commitment per member INPUT + one 'this step went wrong' member per
        answer-feeding DERIVE/EXTERNAL step. Observation members are not
        modelled."""
        led = self.ledger(answer)
        idx = self._answer_index(answer)
        members = [{"id": "p", "member": f"the prediction holds: {led['answer']}", "from": self.steps[idx].id}]
        for i, c in enumerate(led["commitments"], 1):
            members.append({"id": f"A{i}", "member": f"not ({c['content']})", "from": c["step"], "kind": c["kind"],
                            "status": c["status"]})
        for i, s in enumerate(led["step_members"], 1):
            members.append({"id": f"M{i}", "member": f"step {s['step']} went wrong: {s['claim'] or s['text']}",
                            "from": s["step"], "check": s["check"]})
        return members

    # -- output -------------------------------------------------------------------

    def _undetermined_note(self, name: str, idx: int) -> str:
        """Why an unknown without a usable value has none, read against the answer at step idx."""
        hist = self.value_history.get(name, [])
        if not hist:
            return ""
        earlier = [(v, at) for v, at in hist if at < idx]
        if earlier:
            v0, at0 = earlier[-1]
            pre = self._withdrawn_premises(at0, before=idx)
            if pre:
                return f"its value was withdrawn: it rested on {pre[0]}"
            post = self._withdrawn_premises(at0)
            if post:
                when = self.steps[self.bindings[post[0]].withdrawn].id
                return (f"the value it had at this answer ({frac(v0)}) was withdrawn after it (at {when}): "
                        f"it rested on {post[0]}")
        cur = self._withdrawn_premises(self.value_step[name])
        if not cur:
            return ""
        when = self.steps[self.bindings[cur[0]].withdrawn].id
        lead = "it had no value at this answer; " if not earlier else ""
        return f"{lead}a value determined after this answer was withdrawn (at {when}): it rested on {cur[0]}"

    def _bind_note(self, st: Step) -> str:
        parts = []
        for n in st.binds:
            v = self._value_from_step(n, st.index)
            if v is not None:
                unit = self.bindings[n].unit
                parts.append(f"{n} = {frac(v)}{(' ' + unit) if unit else ''}")
            else:
                parts.append(n)
        return ", ".join(parts)

    def to_markdown(self) -> str:
        lines = ["# Hand trace", "", f"**Question.** {_md(self.question)}", ""]
        if self.edition:
            lines += ["**Edition.** " + _md("; ".join(f"{k}: {v}" for k, v in self.edition.items())), ""]
        if self.entries:
            lines += [f"**Entry quotes verified against** {len(self.entries)} supplied entries.", ""]
        lines += ["## Steps", "", "| Step | Frame | Label | Ref / kind | Content | Uses | Check |",
                  "|---|---|---|---|---|---|---|"]
        for st in self.steps:
            content = st.text
            if st.op == "DEMAND":
                content = f"opens {st.tag}: {st.text}"
            if st.claim:
                content = f"`{st.claim}`" + ((" — " + st.text) if st.text else "")
            if st.binds:
                content += " ⇒ " + self._bind_note(st)
            check = "" if st.check == "n/a" else st.check
            if st.detail and st.op in ("DERIVE", "EXTERNAL", "ANSWER"):
                check = f"{check}: {st.detail}" if check else st.detail
            lines.append(f"| {st.id} | {_md(st.frame)} | {st.op} | {_md(st.kind or st.ref)} | {_md(content)} | "
                         f"{_md(', '.join(st.uses))} | {_md(check)} |")
        for label, _ in self.answers:
            led = self.ledger(label)
            lines += ["", f"## Ledger for answer {label}", "", f"**Answer:** {_md(led['answer'])}", "",
                      "### World commitments that feed the answer (members)", "",
                      "| Step | Name | Kind | Status | Countermodel | Content |", "|---|---|---|---|---|---|"]
            for c in led["commitments"]:
                cm = c["countermodel"] + (f" [check: {c['check']}]" if c.get("check") else "")
                lines.append(f"| {c['step']} | {_md(c['name'])} | {c['kind']} | {c['status']} | "
                             f"{_md(cm.strip())} | {_md(c['content'])} |")
            sections = [
                ("Pruned premises (feed the answer, not members)",
                 [f"{c['step']} {c['name']}: {c['content']} ({c['why_pruned']})"
                  + (f" [check: {c['check']}]" if c.get("check") else "") for c in led["pruned"]]),
                ("Theory side that feeds the answer", [f"{t['step']} {t['op']} {t['ref']}: {t['text']}"
                                                       for t in led["theory"]]),
                ("Step members (metalinguistic)", [f"{s['step']} {s['tag'] or s['op']}: {s['claim'] or s['text']} "
                                                   f"({s['check']})" for s in led["step_members"]]),
                ("Inputs that do not feed the answer", [f"{c['step']} {c['name']} ({c['kind']}): {c['content']}"
                                                        for c in led["not_in_answer"]]),
                ("Other steps that do not feed the answer", [f"{r['step']} {r['op']} {r['ref']}: "
                                                             f"{r.get('claim') or r['text']}"
                                                             for r in led["outside_answer"]]),
                ("Open items", [f"{r['step']}: {r['text']}" for r in led["open"]]),
                ("Found mistakes", [f"{r['step']}: {r.get('claim') or r['text']} — {r['detail']}"
                                    for r in led["mistakes"]]),
                ("Conflicts", [f"{r['step']}: {r.get('claim') or r['text']} — {r['detail']}"
                               for r in led["conflicts"]]),
                ("Unchecked steps", [f"{r['step']}: {r.get('claim') or r['text']} — {r['detail']}"
                                     for r in led["unchecked"]]),
                ("Solves that were not unique", [f"{r['step']}: {r['detail']}" for r in led["solve_reports"]]),
                ("Withdrawn premises", [f"{c['step']} {c['name']} (withdrawn at {c['withdrawn_at']}): {c['content']}"
                                        for c in led["withdrawn"]]),
                ("Undetermined unknowns", [f"{u['name']} at {u['address']} (declared {u['step']})" + (f"; {u['note']}" if u.get("note") else "")
                                           for u in led["undetermined"]]),
                ("Warnings", led["warnings"]),
            ]
            for title, rows in sections:
                if title == "Warnings" and not rows:
                    continue
                lines += ["", f"### {title}", ""]
                lines += [f"- {_md(r)}" for r in rows] or ["- none"]
            lines += ["", f"### Hypothesis set for {label} (prediction side only)", ""]
            lines += [f"- **{m['id']}** {_md(m['member'])}" for m in self.hypothesis_set(label)]
        lines += ["", "Checks cover exact arithmetic and bookkeeping only. A countermodel marked [check: ...] was "
                      "re-solved from the recorded premises; physics, recognition, meaning and unmarked countermodels "
                      "are not checked, and the observation side of a trial is not modelled.", ""]
        return "\n".join(lines)

    def to_record(self) -> dict:
        body = {
            "format": FORMAT,
            "version": VERSION,
            "question": self.question,
            "edition": _jsonable(self.edition),
            "entries": dict(sorted(self.entries.items())),
            "strict": self.strict,
            "commands": self.commands,
            "steps": [_step_json(s) for s in self.steps],
            "values": {k: frac(v) for k, v in sorted(self.values.items())},
            "ledgers": {lb: _jsonable(self.ledger(lb)) for lb, _ in self.answers},
        }
        body["sha256"] = _digest(body)
        return body

    def to_json(self) -> str:
        return json.dumps(self.to_record(), indent=2, ensure_ascii=False)

    @classmethod
    def replay(cls, record: Mapping) -> "Trace":
        """Rebuild a trace from a saved record and check it reproduces exactly.

        This checks consistency and the digest, not physics or authorship.
        """
        if record.get("format") != FORMAT or record.get("version") != VERSION:
            raise TraceError("not a vd-hand-trace record of a supported version")
        body = {k: v for k, v in record.items() if k != "sha256"}
        if _digest(body) != record.get("sha256"):
            raise TraceError("record digest does not match its contents")
        t = cls(record["question"], record.get("edition") or {}, strict=bool(record.get("strict", True)),
                entries=record.get("entries") or None)
        for cmd in record["commands"]:
            op = cmd.get("op")
            if op not in _REPLAYABLE:
                raise TraceError(f"unknown command {op!r}")
            try:
                getattr(t, op)(**dict(cmd["args"]))
            except TypeError as exc:
                raise TraceError(f"command {op} has malformed arguments: {exc}") from None
        again = t.to_record()
        for key in ("steps", "values", "ledgers"):
            if again[key] != record[key]:
                raise TraceError(f"replay did not reproduce the recorded {key}")
        return t


_REPLAYABLE = {"demand", "entry", "contract", "reading", "open", "input", "unknown", "deliver", "withdraw",
               "derive", "solve", "consistency", "external", "answer", "annotate"}


def _evaluate(rels: Mapping[str, str], vals: Mapping[str, Fraction]) -> dict:
    """Solve a relation system to a fixpoint: substitute the known values, solve the linear relations,
    substitute what they fix into the nonlinear ones, repeat. Returns status ('consistent',
    'inconsistent' or 'undefined'), the known values, the final linear forms and the relations still
    nonlinear."""
    known = dict(vals)
    while True:
        forms, nonlinear = [], []
        for n, eq in rels.items():
            try:
                forms.append(parse_equation(eq, known)[0])
            except Nonlinear:
                nonlinear.append(n)
            except UndefinedValue:
                return {"status": "undefined", "known": known, "forms": [], "nonlinear": nonlinear, "why": n}
        if forms and not consistent(forms):
            return {"status": "inconsistent", "known": known, "forms": forms, "nonlinear": nonlinear, "why": ""}
        names = sorted({x for f in forms for x in f.names()})
        fixed = solve_linear(forms, names)["values"] if names else {}
        new = {k: v for k, v in fixed.items() if k not in known}
        big = [k for k, v in new.items() if _too_big(v)]
        if big:
            return {"status": "too large", "known": known, "forms": forms, "nonlinear": nonlinear,
                    "why": ", ".join(big)}
        if not new:
            return {"status": "consistent", "known": known, "forms": forms, "nonlinear": nonlinear, "why": ""}
        known.update(new)


def _judge(world: dict, targets: Mapping[str, Fraction]) -> tuple[str, str]:
    if world["status"] == "too large":
        return "cannot check", f"the values of {world['why']} are too large to keep exactly"
    if world["status"] == "undefined":
        return "inconsistent", f"relation {world['why']} is undefined in this world"
    if world["status"] == "inconsistent":
        return "inconsistent", "the changed relations have no common solution"
    differ = [f"{q} = {frac(world['known'][q])} (was {frac(v)})" for q, v in targets.items()
              if q in world["known"] and world["known"][q] != v]
    free = [q for q in targets if q not in world["known"]]
    nl = f"; nonlinear relations not checked: {', '.join(world['nonlinear'])}" if world["nonlinear"] else ""
    if differ:
        return "refutes p", ", ".join(differ) + nl
    if free:
        if world["nonlinear"]:
            return "cannot check", f"{', '.join(free)} left open, and nonlinear relations remain{nl}"
        return "p does not follow", f"{', '.join(free)} left open"
    return ("p still follows", nl[2:]) if nl else ("p still follows", "")


def _supports(status: str, verdict: str) -> bool | None:
    if verdict == "cannot check":
        return None
    if status in ("NEEDS", "REQUIRED"):
        return verdict in ("refutes p", "p does not follow")
    if status == "ENTAILED":
        return verdict == "entailed"
    return verdict == "p still follows"


def _category(verdict: tuple[str, str, list[str]]) -> str:
    """checked, unchecked, mistake or conflict."""
    check, detail, _ = verdict
    if check == "failed":
        return "conflict" if detail.startswith("conflict") else "mistake"
    return check


def _to_fraction(value) -> Fraction:
    if isinstance(value, bool):
        raise TraceError("a value cannot be a boolean")
    if isinstance(value, Fraction):
        out = value
    elif isinstance(value, int):
        out = Fraction(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise TraceError(f"a value must be finite, not {value!r}")
        out = Fraction(repr(value))
    elif isinstance(value, str):
        try:
            form, names = parse_expression(value)
        except Nonlinear as exc:
            raise TraceError(f"a supplied value must be an exact rational constant: {value!r} ({exc})") from None
        if names or not form.is_constant():
            raise TraceError(f"a supplied value must be a constant: {value!r}")
        out = form.const
    else:
        raise TraceError(f"unsupported value {value!r}")
    if _too_big(out):
        raise TraceError(f"a supplied value is too large to record exactly (more than {_MAX_BITS} bits)")
    return out


def _jsonable(x):
    if isinstance(x, Fraction):
        return frac(x)
    if isinstance(x, Mapping):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x


def _step_json(s: Step) -> dict:
    return {"id": s.id, "frame": s.frame, "op": s.op, "text": s.text, "ref": s.ref, "kind": s.kind,
            "uses": list(s.uses), "binds": list(s.binds), "claim": s.claim, "check": s.check,
            "detail": s.detail, "deps": [f"[{d + 1}]" for d in s.deps], "tag": s.tag}


def _digest(body: Mapping) -> str:
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _md(text) -> str:
    s = str(text).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return s.replace("|", "\\|")


def main(argv: Sequence[str] | None = None) -> int:
    """python handtrace.py validate|render RECORD.json"""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in ("validate", "render"):
        print("usage: python handtrace.py validate|render RECORD.json", file=sys.stderr)
        return 2
    try:
        with open(args[1], encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"cannot read record: {exc}", file=sys.stderr)
        return 1
    try:
        trace = Trace.replay(record)
    except (TraceError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
        print(f"invalid record: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args[0] == "validate":
        print(f"ok: {len(trace.steps)} steps replayed; digest {record['sha256'][:12]}")
    else:
        print(trace.to_markdown())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
