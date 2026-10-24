"""A read-only projection of recorded trace responses into claim candidates.

This first layer covers meaning-preservation and supplied-input obligations.
It does not decide equivalence, observational fidelity, or theory failure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Mapping

from demand import Trace, TraceChange


@dataclass(frozen=True)
class Classification:
    """A reader's label. 'correct maths' is a category, not a verdict."""

    category: str = "unclassified"
    note: str = ""

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("classification needs a nonempty category")


@dataclass(frozen=True)
class Prediction:
    id: str
    event_index: int
    operation: str
    kind: str
    statement: str
    evidence: TraceChange
    classification: Classification
    verification: str = "unchecked"


@dataclass(frozen=True)
class PredictionSet:
    """An immutable partial set derived from the recorded history.

    result is the current render; it may still contain unresolved holes.
    Current support follows the recorded operations that produced the result.
    History is retained separately, including reopened or superseded work.
    """

    result: str
    trace_complete: bool
    predictions: tuple[Prediction, ...]
    unrecorded_events: tuple[int, ...]
    schema_version: int = 2
    scope: str = "recorded trace history"
    coverage_complete: bool = False
    limitations: tuple[str, ...] = (
        "Only recorded reductions, cleanup edits and supplied inputs are covered.",
        "Current support is recorded response lineage, not a proof or a minimal semantic dependency set.",
        "Equivalence criteria and input fidelity require human interpretation.",
        "This is not the full disjunction of alternatives and gives no theory verdict.",
        "Direct Demand mutations bypass recording; use the Trace recording methods.",
    )
    current_prediction_ids: tuple[str, ...] = ()
    historical_prediction_ids: tuple[str, ...] = ()
    dependency_selection_complete: bool = False

    def to_dict(self) -> dict:
        """Return a fresh JSON-compatible object."""
        return json.loads(self.to_json())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def build_prediction_set(
    trace: Trace,
    classifications: Mapping[str, Classification] | None = None,
) -> PredictionSet:
    """Extract without modifying trace state or guessing semantic categories.

    P<n> refers to event index n within this trace, so unrelated navigation
    events do not renumber earlier claims. Annotations belong to this trace.
    Missing legacy evidence is reported, never reconstructed from current text.
    """
    annotations = classifications or {}
    predictions = []
    unrecorded = []
    for index, event in enumerate(trace.events):
        if event.kind not in ("reduce", "clean", "inject"):
            continue
        change = event.change
        if change is None:
            unrecorded.append(index)
            continue
        claim_id = f"P{index}"
        if event.kind == "inject":
            kind = "supplied_input"
            statement = (
                f"The supplied response {change.response!r} is appropriate "
                f"for the demand {change.stimulus!r} in the recorded context."
            )
        else:
            kind = "meaning_preservation"
            statement = (
                f"What is meant by {change.stimulus!r} is the same as "
                f"what is meant by {change.response!r} in the recorded context."
            )
        predictions.append(Prediction(
            id=claim_id, event_index=index, operation=event.kind,
            kind=kind, statement=statement, evidence=change,
            classification=annotations.get(claim_id, Classification()),
        ))
    unknown = set(annotations) - {claim.id for claim in predictions}
    if unknown:
        raise ValueError(f"unknown prediction IDs: {', '.join(sorted(unknown))}")
    support = trace.root.claim_support()
    claim_ids = {claim.id for claim in predictions}
    current_ids = tuple(
        f"P{index}" for index in support.event_indexes if f"P{index}" in claim_ids
    )
    selection_complete = (
        support.complete and not unrecorded
        and len(current_ids) == len(support.event_indexes)
    )
    historical_ids = tuple(
        claim.id for claim in predictions if claim.id not in current_ids
    ) if selection_complete else ()
    return PredictionSet(
        result=trace.root.text(), trace_complete=trace.is_complete,
        predictions=tuple(predictions), unrecorded_events=tuple(unrecorded),
        current_prediction_ids=current_ids, historical_prediction_ids=historical_ids,
        dependency_selection_complete=selection_complete,
    )
