"""The hypothesis set of one issued result: a view over a prediction set.

Organizing layer. It reads what the production layer recorded and sorts the
steps one issued result rested on. It removes nothing from the record, checks
nothing, and gives no verdict.

For an issued result the view holds:

* the prediction p, which is the result itself;
* the theory side: the entry applications and recalls, each "according to"
  the dictionary, with whether the definition was the only one, forced by the
  form of the demand, or chosen by a person;
* the members: the failure of each thing a person contributed. A supplied
  input may be wrong, a substitution may not preserve meaning, a headword
  left as plain text may have needed its entry, and a definition a person
  chose may be the wrong one;
* the question, listed apart.

Every step the result *used* is here. Whether each was *needed* is not
decided: this is an upper bound on the set, not the set.

Prototype (12 November 2026). Which groups count as members is provisional;
see specs/2026-11-12-hypothesis-set-view.md, section 9.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from prediction_set import IssuedResult, Prediction, PredictionSet


MEMBER_KINDS = {
    "supplied_input": "commitment",
    "meaning_preservation": "substitution",
    "left_unexpanded": "reading",
}

MEMBER_KIND_DESCRIPTIONS = {
    "commitment": "something a person supplied from outside the dictionary may be wrong",
    "substitution": "a wording put in place of another may not mean the same",
    "reading": "a headword read as plain text may have needed its entry",
    "definition_choice": "a definition a person chose among several that fit may be the wrong one",
}


@dataclass(frozen=True)
class TheoryStep:
    """An entry applied or recalled on the way to the result."""

    id: str
    entry_index: int
    headword: str
    demand: str
    choice: str  # 'only' | 'forced' | 'judged'
    statement: str


@dataclass(frozen=True)
class Member:
    """One way the result could fail without the theory failing."""

    id: str
    kind: str
    statement: str
    of: str  # the recorded step this member is the failure of


@dataclass(frozen=True)
class HypothesisSet:
    issued_id: str
    demand: str
    result: str
    dictionary: str
    prediction: str
    theory: tuple[TheoryStep, ...]
    members: tuple[Member, ...]
    question: tuple[str, ...]
    entries_used: tuple[tuple[int, str], ...]
    steps_used: int
    steps_in_history: int
    record_complete: bool
    scope: str = "prediction side only; every step used, not pruned for need"
    limitations: tuple[str, ...] = (
        "The set holds every step the result used. A step used but not needed is still listed.",
        "The measurement side of a trial is not recorded, so its members are absent.",
        "Supplied inputs are one kind; a value, a recognition and a completeness claim are not told apart.",
        "No member has been tested and no verdict is given.",
    )

    def counts(self) -> dict[str, int]:
        out = {"theory": len(self.theory)}
        for member in self.members:
            out[member.kind] = out.get(member.kind, 0) + 1
        return out

    def to_dict(self) -> dict:
        data = asdict(self)
        data["counts"] = self.counts()
        return json.loads(json.dumps(data, ensure_ascii=False))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def render(self) -> str:
        """Plain text, grouped: prediction, theory side, members by kind."""
        lines = [
            f"Hypothesis set of {self.issued_id}: {self.result!r} for the demand {self.demand!r}",
            f"({self.scope})",
            "",
            f"p   {self.prediction}",
            "",
            f"Theory side, according to {self.dictionary!r}: {len(self.theory)} entry steps over "
            f"{len(self.entries_used)} entries",
        ]
        tally: dict[str, int] = {}
        for step in self.theory:
            tally[step.choice] = tally.get(step.choice, 0) + 1
        labels = {"only": "the only definition", "forced": "forced by the form of the demand",
                  "judged": "chosen by a person"}
        for choice in ("only", "forced", "judged"):
            if tally.get(choice):
                lines.append(f"    {tally[choice]:>3}  {labels[choice]}")
        for kind in MEMBER_KIND_DESCRIPTIONS:
            group = [member for member in self.members if member.kind == kind]
            if not group:
                continue
            lines += ["", f"Members: {kind} ({len(group)}): {MEMBER_KIND_DESCRIPTIONS[kind]}"]
            lines += [f"    not-{member.of:<4} {member.statement}" for member in group]
        lines += ["", "Question, listed apart: " + "; ".join(self.question)]
        if self.steps_in_history:
            lines.append(f"{self.steps_in_history} recorded steps are history for this result and are not in its set.")
        if not self.record_complete:
            lines.append("The record has gaps, so steps the result used may be missing here.")
        return "\n".join(lines)


def _choice(claim: Prediction) -> str:
    use = claim.evidence.entry
    if len(use.candidates) > 1:
        return "judged"
    return "forced" if len(use.clauses) > 1 else "only"


def _member_statement(claim: Prediction) -> str:
    change = claim.evidence
    if claim.kind == "supplied_input":
        return (f"The supplied response {change.response!r} is not appropriate for the demand "
                f"{change.stimulus!r}.")
    if claim.kind == "meaning_preservation":
        return (f"What is meant by {change.stimulus!r} is not the same as what is meant by "
                f"{change.response!r}.")
    return f"Reading {change.stimulus!r} as plain text, with no entry applied, loses what the result needs."


def build_hypothesis_set(prediction_set: PredictionSet, issued_id: str | None = None) -> HypothesisSet:
    """Sort the steps one issued result rested on. Default: the last result issued.

    Pure: the prediction set is not changed, and steps outside the result's
    support stay in it as recorded.
    """
    if not prediction_set.issued:
        raise ValueError("no result has been issued; issue one before asking for its hypothesis set")
    issued: IssuedResult
    if issued_id is None:
        issued = prediction_set.issued[-1]
    else:
        found = [item for item in prediction_set.issued if item.id == issued_id]
        if not found:
            raise ValueError(f"no issued result {issued_id!r}")
        issued = found[0]
    by_id = {claim.id: claim for claim in prediction_set.predictions}
    used = [by_id[claim_id] for claim_id in issued.prediction_ids if claim_id in by_id]

    theory: list[TheoryStep] = []
    members: list[Member] = []
    question: list[str] = []
    entries: dict[int, str] = {}
    dictionary = ""
    for claim in used:
        if claim.kind in ("entry_application", "entry_recall"):
            use = claim.evidence.entry
            dictionary = dictionary or use.dictionary
            entries[use.index] = use.headword
            choice = _choice(claim)
            theory.append(TheoryStep(claim.id, use.index, use.headword, use.call, choice, claim.statement))
            if choice == "judged":
                others = ", ".join(f"E{index}" for index in use.candidates if index != use.index)
                members.append(Member(
                    f"not-{claim.id}", "definition_choice",
                    f"Entry E{use.index} is not the definition to use for the demand {use.call!r}; "
                    f"one of {others} is.", claim.id,
                ))
        elif claim.kind == "normalization":
            question.append(claim.statement)
        else:
            members.append(Member(
                f"not-{claim.id}", MEMBER_KINDS[claim.kind], _member_statement(claim), claim.id,
            ))
    return HypothesisSet(
        issued_id=issued.id, demand=issued.demand, result=issued.result, dictionary=dictionary,
        prediction=issued.statement, theory=tuple(theory), members=tuple(members),
        question=tuple(question), entries_used=tuple(sorted(entries.items())),
        steps_used=len(used), steps_in_history=len(prediction_set.predictions) - len(used),
        record_complete=issued.dependency_selection_complete,
    )
