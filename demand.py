"""Demand graph and trace state for simulator traces.

The engine produces immutable Definiens objects: literal text with
headword holes. A Demand records how a human resolves those original
holes while leaving the Definiens itself untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from definiens import Definiens
from residual import Residual


@dataclass(frozen=True)
class TraceEvent:
    """One recorded trace/evaluator event."""

    kind: str
    detail: str


@dataclass(frozen=True)
class RootProvenance:
    """Demand created by trace bootstrap."""

    text: str


@dataclass(frozen=True)
class ExpandProvenance:
    """Demand created by expanding a dictionary entry."""

    source_index: int


@dataclass(frozen=True)
class InjectProvenance:
    """Demand created from user-supplied text."""

    text: str


Provenance = Union[RootProvenance, ExpandProvenance, InjectProvenance]


@dataclass(frozen=True)
class RecallResolution:
    """A hole filled with literal text from a dictionary entry."""

    text: str
    source_index: int
    compressed: bool = False


@dataclass(frozen=True)
class ExpandResolution:
    """A hole filled by a child demand from a dictionary entry."""

    child: "Demand"
    source_index: int
    compressed: bool = False


@dataclass(frozen=True)
class InjectResolution:
    """A hole filled by a child demand from user-supplied text."""

    child: "Demand"
    compressed: bool = False
    abbreviation: Optional[str] = None


@dataclass(frozen=True)
class LiteralResolution:
    """A hole filled with literal text.

    `inert=True` means the text should be escaped if exported for later
    analysis, so it will not be recognised as a headword again.
    """

    text: str
    inert: bool = False
    source: str = "literal"


Resolution = Union[
    RecallResolution,
    ExpandResolution,
    InjectResolution,
    LiteralResolution,
]


@dataclass
class Demand:
    """One demanded Definiens plus decisions for its original holes."""

    definiens: Definiens
    resolutions: dict[int, Resolution] = field(default_factory=dict)
    parent: Optional["Demand"] = None
    provenance: Provenance = field(default_factory=lambda: RootProvenance(""))
    reduced: Optional[str] = None
    cleaned: bool = False
    cleaned_recalls: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        for pos in self.resolutions:
            self._check_position(pos)

    def _check_position(self, pos: int) -> None:
        if pos < 0 or pos >= self.definiens.order:
            if self.definiens.order == 0:
                raise ValueError(
                    f"demand has no holes; got position {pos}"
                )
            raise ValueError(
                f"position {pos} out of range; valid: "
                f"0..{self.definiens.order - 1}"
            )

    def _check_open_position(self, pos: int) -> None:
        self._check_position(pos)
        if pos in self.resolutions:
            raise ValueError(f"position {pos} is already resolved")

    def resolve_recall(
        self,
        pos: int,
        text: str,
        source_index: int,
        compressed: bool = False,
    ) -> None:
        """Resolve a hole by recalling dictionary entry text."""

        self._check_open_position(pos)
        self.resolutions[pos] = RecallResolution(
            text=text,
            source_index=source_index,
            compressed=compressed,
        )

    def resolve_expand(
        self,
        pos: int,
        child: "Demand",
        source_index: int,
        compressed: bool = False,
    ) -> None:
        """Resolve a hole by expanding into a dictionary-sourced child."""

        self._check_open_position(pos)
        child.parent = self
        self.resolutions[pos] = ExpandResolution(
            child=child,
            source_index=source_index,
            compressed=compressed,
        )

    def resolve_inject(
        self,
        pos: int,
        child: "Demand",
        compressed: bool = False,
        abbreviation: Optional[str] = None,
    ) -> None:
        """Resolve a hole by expanding into a user-supplied child."""

        self._check_open_position(pos)
        child.parent = self
        self.resolutions[pos] = InjectResolution(
            child=child,
            compressed=compressed,
            abbreviation=abbreviation,
        )

    def resolve_literal(
        self,
        pos: int,
        text: str,
        inert: bool = False,
        source: str = "literal",
    ) -> None:
        """Resolve a hole with literal text."""

        self._check_open_position(pos)
        self.resolutions[pos] = LiteralResolution(
            text=text,
            inert=inert,
            source=source,
        )

    def unresolve(self, pos: int) -> None:
        """Remove a resolution, orphaning any child subtree."""

        if pos not in self.resolutions:
            raise KeyError(pos)

        resolution = self.resolutions.pop(pos)
        if isinstance(resolution, (ExpandResolution, InjectResolution)):
            resolution.child.parent = None

        node = self
        while node is not None:
            node.reduced = None
            node = node.parent

    def set_compression(
        self,
        pos: int,
        compressed: bool,
        abbreviation: Optional[str] = None,
    ) -> None:
        """Replace a resolved position's rendering choice."""

        self._check_position(pos)
        if pos not in self.resolutions:
            raise KeyError(pos)

        resolution = self.resolutions[pos]
        if isinstance(resolution, RecallResolution):
            self.resolutions[pos] = RecallResolution(
                text=resolution.text,
                source_index=resolution.source_index,
                compressed=compressed,
            )
        elif isinstance(resolution, ExpandResolution):
            self.resolutions[pos] = ExpandResolution(
                child=resolution.child,
                source_index=resolution.source_index,
                compressed=compressed,
            )
        elif isinstance(resolution, InjectResolution):
            self.resolutions[pos] = InjectResolution(
                child=resolution.child,
                compressed=compressed,
                abbreviation=abbreviation,
            )
        elif isinstance(resolution, LiteralResolution):
            self.resolutions[pos] = resolution
        else:
            raise RuntimeError(f"unknown resolution type: {resolution!r}")

    def set_reduction(self, text: str) -> None:
        """Overlay a human-supplied equivalent for this node's render."""

        if not self.is_resolved:
            raise ValueError(
                "cannot reduce: demand subtree is not fully resolved"
            )
        self.reduced = text

    def clear_reduction(self) -> None:
        """Remove the reduction overlay, restoring the full render."""

        self.reduced = None

    def set_latents(self, new_latents: list[str]) -> None:
        """Replace this demand's latent strings, preserving headwords."""

        expected = self.definiens.order + 1
        if len(new_latents) != expected:
            raise ValueError(
                f"expected {expected} latents, got {len(new_latents)}"
            )
        self.definiens = Definiens(
            Residual(list(new_latents)),
            self.definiens.headwords,
        )
        self.cleaned = True

    def clean_recall_text(self, pos: int, text: str) -> None:
        """Rewrite the stored text of a recalled hole."""

        self._check_position(pos)
        if pos not in self.resolutions:
            raise KeyError(pos)
        resolution = self.resolutions[pos]
        if not isinstance(resolution, RecallResolution):
            raise ValueError(f"position {pos} is not a recall")
        self.resolutions[pos] = RecallResolution(
            text=text,
            source_index=resolution.source_index,
            compressed=resolution.compressed,
        )
        self.cleaned_recalls.add(pos)

    def headword_at(self, pos: int) -> str:
        """Return the original headword demanded at this hole."""

        self._check_position(pos)
        return self.definiens.headwords[pos]

    def ancestor_cycle(self, pos: int) -> Optional["Demand"]:
        """The nearest ancestor with this hole's headword still open.

        Returns the ancestor Demand whose own open holes include the
        headword demanded at `pos` here, walking parent-ward. None if no
        such ancestor exists. Pure read; mutates nothing.
        """

        self._check_position(pos)
        target = self.headword_at(pos)
        node = self.parent
        while node is not None:
            for open_pos in node.open_positions:
                if node.headword_at(open_pos) == target:
                    return node
            node = node.parent
        return None

    @property
    def open_positions(self) -> list[int]:
        """Original hole positions that do not yet have resolutions."""

        return [
            pos for pos in range(self.definiens.order)
            if pos not in self.resolutions
        ]

    @property
    def degree(self) -> int:
        """Open holes in this demand's subtree, computed on read."""

        total = len(self.open_positions)
        for child in self.children().values():
            total += child.degree
        return total

    @property
    def is_resolved(self) -> bool:
        """True when all holes and descendant demands are resolved."""

        if self.open_positions:
            return False

        for resolution in self.resolutions.values():
            if isinstance(resolution, (RecallResolution, LiteralResolution)):
                continue
            if isinstance(resolution, (ExpandResolution, InjectResolution)):
                if not resolution.child.is_resolved:
                    return False
                continue
            raise RuntimeError(f"unknown resolution type: {resolution!r}")

        return True

    def children(self) -> dict[int, "Demand"]:
        """Child demands keyed by original hole position."""

        children: dict[int, Demand] = {}
        for pos, resolution in self.resolutions.items():
            if isinstance(resolution, (ExpandResolution, InjectResolution)):
                children[pos] = resolution.child
            elif not isinstance(
                resolution,
                (RecallResolution, LiteralResolution),
            ):
                raise RuntimeError(f"unknown resolution type: {resolution!r}")
        return children

    def text(self) -> str:
        """Render the current demand without mutating its Definiens."""

        return self._render(escaped=False)

    def escaped_text(self) -> str:
        """Render with inert literal resolutions escaped for re-analysis."""

        return self._render(escaped=True)

    def _render(self, escaped: bool) -> str:
        if self.reduced is not None:
            return self.reduced
        parts = [self.definiens.residual.latent[0]]
        for pos in range(self.definiens.order):
            parts.append(self._render_position(pos, escaped=escaped))
            parts.append(self.definiens.residual.latent[pos + 1])
        return "".join(parts)

    def _render_position(self, pos: int, escaped: bool = False) -> str:
        if pos not in self.resolutions:
            return "{" + self.headword_at(pos) + "}"

        resolution = self.resolutions[pos]
        if isinstance(resolution, RecallResolution):
            if resolution.compressed:
                return self.headword_at(pos)
            return resolution.text
        if isinstance(resolution, ExpandResolution):
            if resolution.compressed:
                return self.headword_at(pos)
            if escaped:
                return resolution.child.escaped_text()
            return resolution.child.text()
        if isinstance(resolution, InjectResolution):
            if resolution.compressed:
                return resolution.abbreviation or self.headword_at(pos)
            if escaped:
                return resolution.child.escaped_text()
            return resolution.child.text()
        if isinstance(resolution, LiteralResolution):
            if escaped and resolution.inert:
                return _escape_literal(resolution.text)
            return resolution.text

        raise RuntimeError(f"unknown resolution type: {resolution!r}")


@dataclass
class Trace:
    """A tree of demands plus the current navigation focus."""

    root: Demand
    active: Demand
    events: list[TraceEvent] = field(default_factory=list)

    @classmethod
    def start(cls, sim, text: str) -> "Trace":
        """Bootstrap a trace by analysing user text through a Simulator."""

        root = Demand(
            sim.analyse(text),
            provenance=RootProvenance(text),
        )
        trace = cls(root=root, active=root)
        trace.record_event("trace", f"started from {text!r}")
        return trace

    def record_event(self, kind: str, detail: str) -> TraceEvent:
        """Append one trace event."""

        event = TraceEvent(kind=kind, detail=detail)
        self.events.append(event)
        return event

    def up(self) -> None:
        """Move active focus to the parent demand."""

        if self.active.parent is None:
            raise ValueError("already at root")
        self.active = self.active.parent

    def down(self, pos: int) -> None:
        """Move active focus to a child demand at position."""

        children = self.active.children()
        if pos not in children:
            raise ValueError(f"no child at position {pos}")
        self.active = children[pos]

    def flatten_active(self) -> list[int]:
        """Flatten every open position on the active demand."""

        positions = list(self.active.open_positions)
        for pos in positions:
            self.active.resolve_literal(
                pos,
                self.active.headword_at(pos),
                inert=True,
                source="flatten",
            )
        if positions:
            self.record_event(
                "flatten",
                _format_position_event(positions),
            )
        return positions

    def flatten_active_position(self, pos: int) -> list[int]:
        """Flatten one open position on the active demand."""

        self.active.resolve_literal(
            pos,
            self.active.headword_at(pos),
            inert=True,
            source="flatten",
        )
        self.record_event("flatten", f"active position {pos}")
        return [pos]

    @property
    def worklist(self) -> list[tuple[Demand, int]]:
        """Open positions across the tree, depth-first left-to-right."""

        out: list[tuple[Demand, int]] = []

        def walk(demand: Demand) -> None:
            for pos in demand.open_positions:
                out.append((demand, pos))
            for pos in sorted(demand.children()):
                walk(demand.children()[pos])

        walk(self.root)
        return out

    @property
    def is_complete(self) -> bool:
        return self.root.is_resolved


def _escape_literal(text: str) -> str:
    """Escape literal text for the tokeniser's backtick rule."""

    return "`" + text.replace("`", "") + "`"


def _format_positions(positions: list[int]) -> str:
    return ", ".join(str(pos) for pos in positions)


def _format_position_event(positions: list[int]) -> str:
    if len(positions) == 1:
        return f"active position {positions[0]}"
    return f"active positions {_format_positions(positions)}"
