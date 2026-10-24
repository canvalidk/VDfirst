"""Replay a scripted mistake and correction through parameterized headwords."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json

from demand import Demand, ExpandProvenance, InjectProvenance, Trace
from engine import VDInstance
from prediction_set import Classification, PredictionSet, build_prediction_set
from repl import REPL
from simulator import Simulator


DEMO_ENTRIES = (
    ("force_p_t", "mass_p times acceleration_p_t"),
    ("mass_p", "supplied mass of p"),
    ("acceleration_p_t", "supplied acceleration of p at t"),
)


@dataclass(frozen=True)
class DemoStage:
    title: str
    description: str
    prediction_set: PredictionSet


def build_demo_simulator() -> Simulator:
    dictionary = VDInstance("parameterized correction example")
    dictionary.append_many(DEMO_ENTRIES)
    return Simulator(dictionary)


def build_correction_demo() -> tuple[DemoStage, ...]:
    """Use real trace operations; responses are scripted, never computed."""
    sim = build_demo_simulator()
    trace = Trace.start(sim, "force_cart_0")
    call = trace.root.headword_at(0)
    index = sim.entry_indexes(call)[0]
    calculation = Demand(
        sim.analyse(sim.instantiated_entry_text(index, call)),
        provenance=ExpandProvenance(index),
    )
    trace.root.resolve_expand(0, calculation, index)
    trace.record_event("expand", f"E{index} for {call}")
    for pos, text in enumerate(("2 kg", "5 m/s^2")):
        child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
        trace.inject_node(calculation, pos, child, text, f"input for {call} at {pos}")

    stages = []

    def capture(title: str, description: str) -> None:
        candidates = build_prediction_set(trace)
        categories = {
            claim.id: Classification(
                "parameter input" if claim.kind == "supplied_input"
                else "calculation" if claim.evidence.before.address
                else "report wording"
            )
            for claim in candidates.predictions
        }
        stages.append(DemoStage(title, description, build_prediction_set(trace, categories)))

    capture("Inputs supplied", "The call supplies cart and time 0 to both demands.")
    trace.reduce_node(calculation, "12 N", "scripted arithmetic mistake")
    capture("Mistake recorded", "The scripted interpreter supplies 12 N for the product.")
    trace.reduce_node(trace.root, "Prediction: 12 N", "report the mistaken result")
    capture("Answer uses mistake", "The report inherits the calculation's recorded support.")

    trace.unreduce_node(calculation, "reopen the product for correction")
    capture(
        "Calculation reopened",
        "The original product is visible again; the dependent report is invalidated.",
    )
    trace.reduce_node(calculation, "10 N", "scripted corrected calculation")
    trace.reduce_node(trace.root, "Prediction: 10 N", "report the corrected result")
    capture(
        "Corrected answer",
        "The old calculation and report remain in history; current support uses the correction.",
    )
    return tuple(stages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--json", action="store_true", help="export every frozen stage")
    modes.add_argument("--interactive", action="store_true", help="open the example dictionary in the REPL")
    args = parser.parse_args()
    if args.interactive:
        REPL(build_demo_simulator()).run()
        return
    stages = build_correction_demo()
    if args.json:
        print(json.dumps({
            "demo": "parameterized mistake and correction",
            "scripted_responses": True,
            "dictionary": {"name": "parameterized correction example", "entries": DEMO_ENTRIES},
            "stages": [asdict(stage) for stage in stages],
        }, ensure_ascii=False, indent=2))
        return

    print("Parameterized mistake and correction")
    print("Interpreter responses are scripted; every claim remains unchecked.\n")
    for number, stage in enumerate(stages, 1):
        result = stage.prediction_set
        print(f"{number}. {stage.title}")
        print(f"   {stage.description}")
        print(f"   Result: {result.result}")
        print(f"   Current support: {', '.join(result.current_prediction_ids) or '(none)'}")
        print(f"   History only: {', '.join(result.historical_prediction_ids) or '(none)'}\n")
    print("Recorded claims:")
    final = stages[-1].prediction_set
    for claim in final.predictions:
        status = "current support" if claim.id in final.current_prediction_ids else "history only"
        print(
            f"  {claim.id} [{status}; {claim.classification.category}; {claim.verification}] "
            f"{claim.evidence.stimulus!r} -> {claim.evidence.response!r}"
        )


if __name__ == "__main__":
    main()
