"""Print an example prediction set: two values and a reduction."""

from demand import Trace
from engine import VDInstance
from prediction_set import Classification, build_prediction_set
from simulator import Simulator


def main() -> None:
    dictionary = VDInstance("prediction example")
    dictionary.append_many([
        ("mass", "what the balance reads"),
        ("acceleration", "the second derivative of position"),
    ])
    sim = Simulator(dictionary)
    trace = Trace.start(sim, "mass times acceleration")
    # Each value replaces the text of the definition its headword expands into.
    for pos, text in enumerate(("2 kg", "5 m/s^2")):
        entry = sim.entry_indexes(trace.root.headword_at(pos))[0]
        trace.expand_node(sim, trace.root, pos, entry, f"parameter at {pos}", replacement=text)
    trace.reduce_node(trace.root, "10 N", "evaluate the product")

    # These labels are supplied by this example's author, not inferred.
    annotations = {
        "P2": Classification("parameter input", "Mass supplied for the example."),
        "P4": Classification("parameter input", "Acceleration supplied for the example."),
        "P5": Classification("correct maths", "Product and unit conversion to check."),
    }
    print(build_prediction_set(trace, annotations).to_json())


if __name__ == "__main__":
    main()
