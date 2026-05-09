"""
vd/definiens.py — the Definiens type.

A Definiens pairs a `Residual` with a parallel list of *headwords* — one
per hole in the residual, in position order. It is the natural output of
the tokeniser: the literal chunks of a definition become the residual's
latent strings; the headword references at each hole position become the
headwords list.

Definiens is the textual machinery used inside the simulator and produced
by the engine. The residual carries no semantics; the headwords list says
what each hole references. Separated cleanly, paired by position.

Invariant: len(headwords) == residual.order.

Filling consumes residual holes and headwords in lockstep:
  - Filling with a string (or order-0 Definiens) consumes one headword.
  - Filling with a higher-order Definiens splices its residual into the
    host's residual *and* its headwords into the host's headwords list at
    the same position. Order arithmetic on the residual carries through.

Bare Residuals are not accepted as fill values: they have no headwords
for their holes, so the parallel structure would break. Wrap in a
Definiens explicitly.

Importable by both engine.py and simulator.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Union

from residual import Residual


FillValue = Union[str, "Definiens"]


@dataclass
class Definiens:
    """A residual paired with the headwords its holes reference.

    Invariants:
      - len(headwords) == residual.order.
      - headwords are arbitrary strings (typically headword names).
    """

    residual: Residual
    headwords: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.headwords) != self.residual.order:
            raise ValueError(
                f"residual order {self.residual.order} requires "
                f"{self.residual.order} headwords, got {len(self.headwords)}"
            )

    # ── Properties ──────────────────────────────────────────────

    @property
    def order(self) -> int:
        return self.residual.order

    @property
    def is_done(self) -> bool:
        return self.residual.is_done

    @property
    def text(self) -> str:
        """Order-0 string. Raises if order > 0."""
        return self.residual.text

    # ── Fill ────────────────────────────────────────────────────

    def fill(self, values: dict[int, FillValue] | None = None) -> "Definiens":
        """Fill holes by position.

        - `values` maps position to either a string (consumes that
          headword, fills with the string) or a Definiens (splices the
          sub-Definiens in at that position).
        - Bare Residuals are rejected — wrap as Definiens.
        - Omitted positions pass through unfilled.
        - fill() / fill({}) is identity.
        """
        if values is None:
            values = {}

        # Reject bare Residuals (caller mistake).
        for p, v in values.items():
            if isinstance(v, Residual) and not isinstance(v, Definiens):
                raise TypeError(
                    f"position {p}: bare Residual not accepted; "
                    f"wrap in Definiens to supply headwords"
                )

        # Validate positions early (mirrors Residual's check).
        valid = range(self.order)
        unknown = [p for p in values if p not in valid]
        if unknown:
            if self.order == 0:
                raise ValueError(
                    f"definiens has no holes; got positions {sorted(unknown)}"
                )
            raise ValueError(
                f"unknown position(s) {sorted(unknown)}; "
                f"valid range: 0..{self.order - 1}"
            )

        # Coerce strings to order-0 Definiens for uniform handling.
        ds: dict[int, Definiens] = {
            p: v if isinstance(v, Definiens) else Definiens(Residual([v]), [])
            for p, v in values.items()
        }

        # Build new headwords list in lockstep with residual splice.
        new_headwords: list[str] = []
        for i in range(self.order):
            if i in ds:
                # Filled: this position's headword is consumed; the sub's
                # headwords (if any) take its place.
                new_headwords.extend(ds[i].headwords)
            else:
                # Unfilled: headword passes through.
                new_headwords.append(self.headwords[i])

        # Splice residuals using the same dict (extracting each sub's residual).
        residual_values: dict[int, str | Residual] = {
            p: d.residual for p, d in ds.items()
        }
        new_residual = self.residual.fill(residual_values)

        return Definiens(new_residual, new_headwords)

    def fill_list(self, values: list[FillValue | None]) -> "Definiens":
        """Fill by sequential position. Mirrors Residual.fill_list.

        - values[i] fills position i.
        - None entries skip.
        - Short list fills a prefix; long list raises.
        """
        if len(values) > self.order:
            raise ValueError(
                f"got {len(values)} values for definiens of order {self.order}"
            )
        return self.fill({i: v for i, v in enumerate(values) if v is not None})

    # ── Display ─────────────────────────────────────────────────

    def render(self, hole: Callable[[int, str], str] | None = None) -> str:
        """Render with each hole rendered by `hole(position, headword)`.

        Default placeholder shows the headword in braces, e.g.
            "{mass} + {mass}"
        which is the natural reading of a definiens.
        """
        if hole is None:
            hole = lambda i, h: f"{{{h}}}"
        return self.residual.render(lambda i: hole(i, self.headwords[i]))

    def __repr__(self) -> str:
        if self.is_done:
            return f"Definiens(text={self.residual.latent[0]!r})"
        return f"Definiens(order={self.order}, {self.render()!r})"
