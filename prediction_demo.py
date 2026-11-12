"""Print an example prediction set: two supplied parameters and a reduction."""

from demand import Demand, InjectProvenance, Trace
from engine import VDInstance
from prediction_set import Classification, build_prediction_set
from simulator import Simulator


def main() -> None:
    dictionary = VDInstance("prediction example")
    dictionary.append_many([
        ("mass", "supplied mass"),
        ("acceleration", "supplied acceleration"),
    ])
    sim = Simulator(dictionary)
    trace = Trace.start(sim, "mass times acceleration")
    for pos, text in enumerate(("2 kg", "5 m/s^2")):
        child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
        trace.inject_node(trace.root, pos, child, text, f"parameter at {pos}")
    trace.reduce_node(trace.root, "10 N", "evaluate the product")

    # These labels are supplied by this example's author, not inferred.
    annotations = {
        "P1": Classification("parameter input", "Mass supplied for the example."),
        "P2": Classification("parameter input", "Acceleration supplied for the example."),
        "P3": Classification("correct maths", "Product and unit conversion to check."),
    }
    print(build_prediction_set(trace, annotations).to_json())


if __name__ == "__main__":
    main()
