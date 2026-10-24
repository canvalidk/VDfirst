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
class ArgumentSnapshot:
    """One delivered argument as it appeared when a change was made."""

    position: int
    headword: str
    text: str
    resolution: str
    source_index: Optional[int]


@dataclass(frozen=True)
class NodeSnapshot:
    """Copied context, independent of later edits and rendering choices."""

    address: tuple[int, ...]
    render: str
    latents: tuple[str, ...]
    headwords: tuple[str, ...]
    arguments: tuple[ArgumentSnapshot, ...]
    provenance: str
    source_index: Optional[int]
    source_text: Optional[str]
    reduction: Optional[str]


@dataclass(frozen=True)
class TraceChange:
    """Evidence for a response, not a certificate of equivalence."""

    stimulus: str
    response: str
    before: NodeSnapshot
    after: NodeSnapshot
    position: Optional[int] = None
    dependencies: tuple[int, ...] = ()
    dependencies_complete: bool = True


@dataclass(frozen=True)
class TraceEvent:
    """One recorded trace/evaluator event."""

    kind: str
    detail: str
    change: Optional[TraceChange] = None


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


@dataclass(frozen=True)
class _ClaimSupport:
    """Recorded response lineage; completeness says nothing about correctness."""

    event_indexes: tuple[int, ...] = ()
    complete: bool = True


def _combine_support(
    *supports: _ClaimSupport, event_index: Optional[int] = None,
) -> _ClaimSupport:
    indexes = {index for support in supports for index in support.event_indexes}
    if event_index is not None:
        indexes.add(event_index)
    return _ClaimSupport(tuple(sorted(indexes)), all(s.complete for s in supports))


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
    _prose_support: _ClaimSupport = field(
        default_factory=_ClaimSupport, init=False, repr=False,
    )
    _resolution_support: dict[int, _ClaimSupport] = field(
        default_factory=dict, init=False, repr=False,
    )
    _reduction_support: _ClaimSupport = field(
        default_factory=lambda: _ClaimSupport(complete=False), init=False, repr=False,
    )

    def __post_init__(self) -> None:
        for pos in self.resolutions:
            self._check_position(pos)
        if self.cleaned:
            self._prose_support = _ClaimSupport(complete=False)
        for pos in self.cleaned_recalls:
            self._resolution_support[pos] = _ClaimSupport(complete=False)

    def claim_support(self, *, underlying: bool = False) -> _ClaimSupport:
        """Select recorded support for the current value, including consumed claims.

        Compression is a display choice and keeps a child's obligations.
        An overlay carries the lineage of the stimulus it actually consumed.
        Unrecorded response mutations leave an explicit completeness gap.
        """
        if self.reduced is not None and not underlying:
            return self._reduction_support
        supports = [self._prose_support]
        for pos, resolution in self.resolutions.items():
            default = _ClaimSupport(complete=not isinstance(resolution, InjectResolution))
            supports.append(self._resolution_support.get(pos, default))
            if isinstance(resolution, (ExpandResolution, InjectResolution)):
                supports.append(resolution.child.claim_support())
        return _combine_support(*supports)

    def _clear_reductions_upward(self) -> None:
        node = self
        while node is not None:
            node.reduced = None
            node._reduction_support = _ClaimSupport()
            node = node.parent

    def _invalidate_consumers(self) -> None:
        if self.parent is not None:
            self.parent._clear_reductions_upward()

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
        self._resolution_support.pop(pos, None)
        if isinstance(resolution, (ExpandResolution, InjectResolution)):
            resolution.child.parent = None

        self._clear_reductions_upward()

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
        self._reduction_support = _ClaimSupport(complete=False)
        self._invalidate_consumers()

    def clear_reduction(self) -> None:
        """Remove the reduction overlay, restoring the full render."""

        had_reduction = self.reduced is not None
        self.reduced = None
        self._reduction_support = _ClaimSupport()
        if had_reduction:
            self._invalidate_consumers()

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
        self._prose_support = _ClaimSupport(complete=False)
        if self.reduced is None:
            self._invalidate_consumers()

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
        self._resolution_support[pos] = _ClaimSupport(complete=False)
        if self.reduced is None:
            self._invalidate_consumers()

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

    def record_event(
        self, kind: str, detail: str, change: Optional[TraceChange] = None,
    ) -> TraceEvent:
        """Append one trace event."""

        event = TraceEvent(kind=kind, detail=detail, change=change)
        self.events.append(event)
        return event

    def address_of(self, node: Demand) -> tuple[int, ...]:
        """Locate a member by original hole positions, using identity."""
        path = []
        seen = set()
        while node is not self.root:
            if id(node) in seen or node.parent is None:
                raise ValueError("demand is not attached to this trace")
            seen.add(id(node))
            parent = node.parent
            pos = next(
                (pos for pos, child in parent.children().items() if child is node),
                None,
            )
            if pos is None:
                raise ValueError("demand is not attached to this trace")
            path.append(pos)
            node = parent
        return tuple(reversed(path))

    def snapshot(self, node: Demand) -> NodeSnapshot:
        """Freeze the local residue, delivered arguments and provenance."""
        return NodeSnapshot(
            address=self.address_of(node),
            render=node.text(),
            latents=tuple(node.definiens.residual.latent),
            headwords=tuple(node.definiens.headwords),
            arguments=tuple(
                ArgumentSnapshot(
                    pos, node.headword_at(pos), node._render_position(pos),
                    type(resolution).__name__,
                    getattr(resolution, "source_index", None),
                )
                for pos, resolution in sorted(node.resolutions.items())
            ),
            provenance=type(node.provenance).__name__,
            source_index=getattr(node.provenance, "source_index", None),
            source_text=getattr(node.provenance, "text", None),
            reduction=node.reduced,
        )

    def reduce_node(self, node: Demand, text: str, detail: str) -> TraceEvent:
        """Apply and record an evaluator response with its exact stimulus."""
        before = self.snapshot(node)
        support = node.claim_support()
        node.set_reduction(text)
        node._reduction_support = _combine_support(support, event_index=len(self.events))
        return self.record_event(
            "reduce", detail,
            TraceChange(
                before.render, text, before, self.snapshot(node),
                dependencies=support.event_indexes, dependencies_complete=support.complete,
            ),
        )

    def unreduce_node(self, node: Demand, detail: str) -> TraceEvent:
        """Reopen the original expression and invalidate consumers, keeping history."""
        self.address_of(node)
        if node.reduced is None:
            raise ValueError("node is not reduced")
        node.clear_reduction()
        return self.record_event("unreduce", detail)

    def inject_node(
        self, node: Demand, pos: int, child: Demand, text: str, detail: str,
    ) -> TraceEvent:
        """Record supplied text before its child is evaluated or cleaned."""
        before = self.snapshot(node)
        stimulus = node.headword_at(pos)
        node.resolve_inject(pos, child)
        node._resolution_support[pos] = _ClaimSupport((len(self.events),))
        return self.record_event(
            "inject", detail,
            TraceChange(stimulus, text, before, self.snapshot(node), pos),
        )

    def clean_node(
        self, node: Demand, latents: list[str], detail: str,
    ) -> TraceEvent:
        """Record a residual wording edit, even beneath a reduction."""
        before = self.snapshot(node)
        support = node.claim_support(underlying=True)
        node.set_latents(latents)
        node._prose_support = _combine_support(support, event_index=len(self.events))
        after = self.snapshot(node)
        return self.record_event(
            "clean", detail,
            TraceChange(
                _snapshot_prose(before), _snapshot_prose(after), before, after,
                dependencies=support.event_indexes, dependencies_complete=support.complete,
            ),
        )

    def clean_recall(
        self, node: Demand, pos: int, text: str, detail: str,
    ) -> TraceEvent:
        """Record the actual recalled text, even when its display is folded."""
        before = self.snapshot(node)
        resolution = node.resolutions.get(pos)
        if not isinstance(resolution, RecallResolution):
            raise ValueError(f"position {pos} is not a recall")
        stimulus = resolution.text
        support = node.claim_support(underlying=True)
        node.clean_recall_text(pos, text)
        node._resolution_support[pos] = _combine_support(support, event_index=len(self.events))
        return self.record_event(
            "clean", detail,
            TraceChange(
                stimulus, text, before, self.snapshot(node), pos,
                dependencies=support.event_indexes, dependencies_complete=support.complete,
            ),
        )

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


def _snapshot_prose(snapshot: NodeSnapshot) -> str:
    """Render residual prose with its recorded arguments, ignoring overlay."""
    arguments = {arg.position: arg.text for arg in snapshot.arguments}
    parts = [snapshot.latents[0]]
    for pos, headword in enumerate(snapshot.headwords):
        parts.extend((arguments.get(pos, "{" + headword + "}"), snapshot.latents[pos + 1]))
    return "".join(parts)


def _escape_literal(text: str) -> str:
    """Escape literal text for the tokeniser's backtick rule."""

    return "`" + text.replace("`", "") + "`"


def _format_positions(positions: list[int]) -> str:
    return ", ".join(str(pos) for pos in positions)


def _format_position_event(positions: list[int]) -> str:
    if len(positions) == 1:
        return f"active position {positions[0]}"
    return f"active positions {_format_positions(positions)}"
