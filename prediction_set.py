"""A read-only projection of every recorded trace step into claim candidates.

Production only: one candidate per recorded step, in the order recorded.
Nothing is pruned, grouped or judged here. Sorting the list (theory side
against commitments, current against history, needed against used) and
testing its members are separate layers that read this output.
It does not decide equivalence, observational fidelity, or theory failure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Mapping

from demand import EntryUse, Trace, TraceChange


# The kind of candidate each recorded event kind produces. A reopening carries
# evidence too, but it sets a response aside and asserts nothing, so it has no
# candidate; navigation events are not steps.
STEP_KINDS = {
    "trace": "normalization",
    "expand": "entry_application",
    "recall": "entry_recall",
    "flatten": "left_unexpanded",
    "inject": "supplied_input",
    "reduce": "meaning_preservation",
    "clean": "meaning_preservation",
}

KIND_DESCRIPTIONS = {
    "normalization": "the starting demand states what is asked",
    "entry_application": "a dictionary entry was applied to a demand, which continues as a child demand",
    "entry_recall": "a dictionary entry's text was inserted for a demand as it stands",
    "left_unexpanded": "a headword was left as plain text, with no entry applied",
    "supplied_input": "a response was supplied for a demand from outside the dictionary",
    "meaning_preservation": "one wording was replaced by another said to mean the same",
}


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
    predictions holds one candidate per recorded step, of every kind.
    Current support follows the recorded steps that produced the result.
    History is retained separately, including reopened or superseded work.
    """

    result: str
    trace_complete: bool
    predictions: tuple[Prediction, ...]
    unrecorded_events: tuple[int, ...]
    schema_version: int = 3
    scope: str = "recorded trace history"
    coverage_complete: bool = False
    limitations: tuple[str, ...] = (
        "Every recorded step is listed: the starting demand, entry applications and recalls, "
        "headwords left unexpanded, supplied inputs, reductions and cleanup edits.",
        "The list is unsorted and unpruned; which candidates are theory-side, needed or members is not decided here.",
        "Current support is recorded step lineage, not a proof or a minimal semantic dependency set.",
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


def _entry_statement(use: EntryUse, recalled: bool) -> str:
    statement = (
        f"According to {use.dictionary!r}, entry E{use.index} defines "
        f"{use.headword!r} as {use.definition!r}"
    )
    if use.bindings:
        pairs = ", ".join(f"{formal} := {actual}" for formal, actual in use.bindings)
        statement += f"; with {pairs} that gives {use.text!r} for the demand {use.call!r}"
    elif use.call != use.headword:
        statement += f"; it answers the demand {use.call!r}"
    others = [index for index in use.candidates if index != use.index]
    if others:
        statement += "; chosen over " + ", ".join(f"E{index}" for index in others)
    statement += "."
    if recalled:
        statement += " Its text is inserted as it stands, without further expansion."
    return statement


def _statement(kind: str, change: TraceChange) -> str:
    if kind == "normalization":
        return f"The demand {change.stimulus!r} states what is asked in the recorded context."
    if kind in ("entry_application", "entry_recall"):
        return _entry_statement(change.entry, recalled=kind == "entry_recall")
    if kind == "left_unexpanded":
        already = {argument.position for argument in change.before.arguments}
        left = [repr(argument.headword) for argument in change.after.arguments
                if argument.position not in already]
        if len(left) == 1:
            return f"The headword {left[0]} is left as plain text here; no entry is applied to it."
        return (f"The headwords {', '.join(left)} are left as plain text here; "
                "no entry is applied to them.")
    if kind == "supplied_input":
        return (
            f"The supplied response {change.response!r} is appropriate "
            f"for the demand {change.stimulus!r} in the recorded context."
        )
    return (
        f"What is meant by {change.stimulus!r} is the same as "
        f"what is meant by {change.response!r} in the recorded context."
    )


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
    started = False
    for index, event in enumerate(trace.events):
        kind = STEP_KINDS.get(event.kind)
        if kind is None:
            continue
        change = event.change
        if change is None or (kind in ("entry_application", "entry_recall") and change.entry is None):
            unrecorded.append(index)
            continue
        started = started or kind == "normalization"
        claim_id = f"P{index}"
        predictions.append(Prediction(
            id=claim_id, event_index=index, operation=event.kind,
            kind=kind, statement=_statement(kind, change), evidence=change,
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
    # The starting demand must itself be a recorded step: a trace assembled
    # without Trace.start has no record of what was asked.
    selection_complete = (
        started and support.complete and not unrecorded
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
