"""Drive the contribution recursion over a member-named list through the engine.

Scene, one vertical axis, upward positive:

    ceiling -- spring s1 -- block A -- spring s2 -- block B

with near-surface gravity on both blocks. s1 is carried by the ceiling and s2
by A, so the lists are

    A: [A:spring:s1,R:spring:s2,A:gravity:A]      B: [A:spring:s2,A:gravity:B]

``A:x`` is the action of acting-object x and ``R:x`` its reaction. The same
scene was first recorded by hand (VD-docs inbox, 12 November 2026:
``handtrace_probe_member_list.py``), where building the remaining list, the
empty-or-not split and the action-or-reaction dispatch were readings the
recorder could not check. Here each is an entry application whose choice of
definition is forced by the form of the argument.

The dictionary below is a prototype for exercising the engine. Its wording is
not proposed entry text. Every response is scripted; nothing is computed or
checked by the engine.
"""

from __future__ import annotations

import argparse
import json

from demand import Demand, InjectProvenance, Trace
from engine import VDInstance
from hypothesis_set import build_hypothesis_set
from prediction_set import PredictionSet, build_prediction_set
from simulator import Simulator


DEMO_ENTRIES = (
    ("inertial-acceleration_p", "net-force_p divided by inertial-mass_p"),
    ("net-force_p", "haze_p plus contribution_p"),
    ("contribution_p_[]", "the zero vector"),
    ("contribution_p_[m|rest]", "impressed-force_m_p plus contribution_p_rest"),
    ("impressed-force_A:x_p", "action-force_x"),
    ("impressed-force_R:x_p", "reaction-force_x"),
    ("reaction-force_x", "the negative of action-force_x"),
    ("action-force_spring:s", "the negative of stiffness_s times displacement_s"),
    ("action-force_gravity:q", "the negative of gravitational-mass_q times field-strength"),
    ("haze_p", "supplied haze on p"),
    ("inertial-mass_p", "supplied inertial mass of p"),
    ("stiffness_s", "supplied stiffness of s"),
    ("displacement_s", "supplied displacement of the other participant of s from its relaxed position"),
    ("gravitational-mass_q", "supplied gravitational mass of q"),
    ("field-strength", "supplied local field strength"),
)

MEMBERS = {
    "A": "[A:spring:s1,R:spring:s2,A:gravity:A]",
    "B": "[A:spring:s2,A:gravity:B]",
}

# What a person supplies at each demand the dictionary leaves to them.
SUPPLIED = {
    "haze_A": "0 N", "haze_B": "0 N",
    "inertial-mass_A": "2 kg", "inertial-mass_B": "1 kg",
    "stiffness_s1": "20 N/m", "displacement_s1": "-1 m",
    "stiffness_s2": "10 N/m", "displacement_s2": "-1/2 m",
    "gravitational-mass_A": "2 kg", "gravitational-mass_B": "1 kg",
    "field-strength": "49/5 m/s^2",
}

# Scripted interpreter responses, keyed by the exact wording they answer.
RESPONSES = {
    "the negative of 20 N/m times -1 m": "20 N",
    "the negative of 10 N/m times -1/2 m": "5 N",
    "the negative of 5 N": "-5 N",
    "the negative of 2 kg times 49/5 m/s^2": "-98/5 N",
    "the negative of 1 kg times 49/5 m/s^2": "-49/5 N",
    "the zero vector": "0 N",
    "-98/5 N plus 0 N": "-98/5 N",
    "-49/5 N plus 0 N": "-49/5 N",
    "-5 N plus -98/5 N": "-123/5 N",
    "20 N plus -123/5 N": "-23/5 N",
    "5 N plus -49/5 N": "-24/5 N",
    "0 N plus -23/5 N": "-23/5 N",
    "0 N plus -24/5 N": "-24/5 N",
    "-23/5 N divided by 2 kg": "-23/10 m/s^2",
    "-24/5 N divided by 1 kg": "-24/5 m/s^2",
}


def build_demo_simulator() -> Simulator:
    dictionary = VDInstance("member-list prototype")
    dictionary.append_many(DEMO_ENTRIES)
    return Simulator(dictionary)


def trace_object(sim: Simulator, obj: str, members: str | None = None) -> Trace:
    """Answer inertial-acceleration_<obj> with scripted inputs and responses."""
    members = MEMBERS[obj] if members is None else members
    trace = Trace.start(sim, f"inertial-acceleration_{obj}")

    def settle(node: Demand) -> None:
        for pos in range(node.definiens.order):
            call = node.headword_at(pos)
            if call == f"contribution_{obj}":
                # The list is what a person supplies: which members act on obj.
                text = f"contribution_{obj}_{members}"
                child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
                trace.inject_node(node, pos, child, text, f"the members acting on {obj}")
            elif call in SUPPLIED:
                text = SUPPLIED[call]
                child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
                trace.inject_node(node, pos, child, text, f"supplied {call}")
            else:
                answering = sim.entry_indexes(call)
                if len(answering) != 1:
                    raise ValueError(f"{call!r} is answered by {len(answering)} entries; the demo expects one")
                trace.expand_node(sim, node, pos, answering[0], f"E{answering[0]} for {call}")
            settle(node.children()[pos])
        wording = node.text()
        if wording in RESPONSES:
            trace.reduce_node(node, RESPONSES[wording], "scripted response")

    settle(trace.root)
    trace.issue(f"the inertial acceleration of {obj}")
    return trace


def forced_by_form(result: PredictionSet) -> list[str]:
    """Ids of the entry applications where form left exactly one definition."""
    return [
        claim.id for claim in result.predictions
        if claim.kind == "entry_application"
        and len(claim.evidence.entry.clauses) > 1
        and claim.evidence.entry.candidates == (claim.evidence.entry.index,)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="export both prediction sets")
    parser.add_argument("--steps", action="store_true", help="print every recorded step for A")
    parser.add_argument("--hypotheses", action="store_true", help="print the hypothesis set of A's issued result")
    args = parser.parse_args()
    sim = build_demo_simulator()
    results = {obj: build_prediction_set(trace_object(sim, obj)) for obj in ("A", "B")}
    if args.hypotheses:
        print(build_hypothesis_set(results["A"]).render())
        return
    if args.json:
        print(json.dumps({
            "demo": "member-named list through the contribution recursion",
            "scripted_responses": True,
            "dictionary": {"name": sim.instance.name, "entries": DEMO_ENTRIES},
            "prediction_sets": {obj: result.to_dict() for obj, result in results.items()},
        }, ensure_ascii=False, indent=2))
        return
    print("Member-named list through the contribution recursion")
    print("Responses are scripted; every recorded step remains unchecked.\n")
    for obj, result in results.items():
        kinds: dict[str, int] = {}
        for claim in result.predictions:
            kinds[claim.kind] = kinds.get(claim.kind, 0) + 1
        issued = result.issued[-1]
        print(f"{obj}: {issued.result}   (list {MEMBERS[obj]})")
        print(f"   steps by kind: {kinds}")
        print(f"   entry applications forced by the form of the argument: {len(forced_by_form(result))}")
        print(f"   every step recorded: {result.dependency_selection_complete}\n")
    if args.steps:
        for claim in results["A"].predictions:
            print(f"{claim.id} [{claim.kind}] {claim.statement}")


if __name__ == "__main__":
    main()
