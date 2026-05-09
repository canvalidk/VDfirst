"""
vd/residual.py — the Residual type.

A residual is a partially-evaluated textual fragment: n+1 *latent* strings
with n *holes* between them. Its order is n. Order 0 means no holes —
the residual is effectively a string.

Holes are addressed by position (0, 1, ..., n-1). Residuals carry no
metadata about what each hole references; that is the caller's
responsibility (e.g. a parallel mapping in a dependency graph).

`fill` is the only structural operation. It substitutes positions with
other residuals (or bare strings, coerced to order-0 residuals) and
returns a new Residual. Order 0 is the base case.

The representation is eagerly flat: filling a host with a sub-residual
merges the sub's latent strings into the host's. After fill, the
positions in the result are renumbered: positions before the filled hole
keep their numbers, the sub's holes occupy the next len(sub) positions,
and host positions after the filled hole shift accordingly.

Importable by both engine.py and simulator.py; depends on neither.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Union


FillValue = Union[str, "Residual"]


@dataclass
class Residual:
    """A residual: n+1 latent strings with n holes between them.

    Invariant: latent is non-empty.
    """

    latent: list[str]

    def __post_init__(self) -> None:
        if not self.latent:
            raise ValueError("residual needs at least one latent string")

    # ── Properties ──────────────────────────────────────────────

    @property
    def order(self) -> int:
        """Number of holes."""
        return len(self.latent) - 1

    @property
    def is_done(self) -> bool:
        """True when fully filled (no holes remain)."""
        return self.order == 0

    @property
    def text(self) -> str:
        """The single latent string of an order-0 residual.

        Raises ValueError if order > 0.
        """
        if not self.is_done:
            raise ValueError(
                f"text requires order 0, got order {self.order}"
            )
        return self.latent[0]

    # ── Fill ────────────────────────────────────────────────────

    def fill(self, values: dict[int, FillValue] | None = None) -> "Residual":
        """Fill holes by position.

        - `values` is a dict mapping position (0-indexed) to fill value.
        - Bare strings are coerced to order-0 residuals.
        - Omitted positions pass through unfilled.
        - fill() or fill({}) is identity.
        - Positions outside [0, order) raise ValueError.

        Returns a new Residual of order:
            self.order - len(values) + sum(v.order for v in values.values())
        """
        if values is None:
            values = {}

        # Validate positions.
        valid = range(self.order)
        unknown = [p for p in values if p not in valid]
        if unknown:
            if self.order == 0:
                raise ValueError(
                    f"residual has no holes; got positions {sorted(unknown)}"
                )
            raise ValueError(
                f"unknown position(s) {sorted(unknown)}; "
                f"valid range: 0..{self.order - 1}"
            )

        # Coerce bare strings to order-0 residuals.
        rs: dict[int, Residual] = {
            p: v if isinstance(v, Residual) else Residual([v])
            for p, v in values.items()
        }

        # Splice. Walk the host's holes in position order; for each hole,
        # either merge in the sub-residual or carry the hole through.
        new_latent: list[str] = [self.latent[0]]
        for i in range(self.order):
            host_right = self.latent[i + 1]
            if i in rs:
                sub = rs[i]
                # First sub-latent fuses to the open right edge.
                new_latent[-1] = new_latent[-1] + sub.latent[0]
                # Remaining sub-latents append.
                for j in range(sub.order):
                    new_latent.append(sub.latent[j + 1])
                # Host's right-side latent fuses on.
                new_latent[-1] = new_latent[-1] + host_right
            else:
                # Unfilled: hole carries through.
                new_latent.append(host_right)

        return Residual(new_latent)

    def fill_list(self, values: list[FillValue | None]) -> "Residual":
        """Fill holes by sequential position, taking each list index as
        the target position.

        - `values[i]` fills position i.
        - `None` entries skip that position (pass through unfilled).
        - A list shorter than `order` fills a prefix; remaining positions
          pass through unfilled.
        - A list longer than `order` raises ValueError.
        - fill_list([]) is identity.

        Equivalent to:
            fill({i: v for i, v in enumerate(values) if v is not None})
        """
        if len(values) > self.order:
            raise ValueError(
                f"got {len(values)} values for residual of order {self.order}"
            )
        return self.fill({i: v for i, v in enumerate(values) if v is not None})

    # ── Display ─────────────────────────────────────────────────

    def render(self, hole: Callable[[int], str] | None = None) -> str:
        """Render the residual as a string.

        `hole(i)` produces the placeholder text for the hole at position i.
        Default shows the position itself, e.g. `"{0} + {1}"`.

        For order 0, returns the single latent string regardless of `hole`.
        """
        if hole is None:
            hole = lambda i: f"{{{i}}}"
        parts = [self.latent[0]]
        for i in range(self.order):
            parts.append(hole(i))
            parts.append(self.latent[i + 1])
        return "".join(parts)

    def __repr__(self) -> str:
        if self.is_done:
            return f"Residual(text={self.latent[0]!r})"
        return f"Residual(order={self.order}, {self.render()!r})"
