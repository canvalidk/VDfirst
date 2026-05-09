#!/usr/bin/env python3
"""
vd_demo.py — Demonstrate the VD engine on the Newton instance.

Run:  python3 vd_demo.py
"""

import sys
sys.path.insert(0, '/home/claude')

from vd import (
    build_newton_instance,
    show_entry_table, show_decomposition,
    show_laws, show_houses, show_audit, show_headword,
    show_graph_stats, full_report, banner, C,
    draw_dependency_graph, draw_house, draw_house_chain,
)


def main():
    print(banner("Valid Dictionary Engine — Newton Demo"))

    # Build the instance
    vd = build_newton_instance()
    print(f"  Loaded: {vd.summary()}\n")

    # ── 1. Entry table ──
    print(show_entry_table(vd))

    # ── 2. Decomposition examples ──
    print("\n")
    print(banner("Example Decompositions"))

    # E12: chimney for Newton I (uniform motion scaffold)
    print(show_decomposition(vd, 11))  # 0-indexed

    # E15: triplet entry (inertial frame)
    print(show_decomposition(vd, 14))

    # E1: meaningfully defined (time)
    print(show_decomposition(vd, 0))

    # ── 3. Structural audit ──
    print("\n")
    print(show_audit(vd))

    # ── 4. Laws ──
    print("\n")
    print(show_laws(vd))

    # ── 5. Houses ──
    print("\n")
    print(show_houses(vd))

    # ── 6. Graph stats ──
    print("\n")
    print(show_graph_stats(vd))

    # ── 7. Headword deep dive ──
    print("\n")
    for hw in ["inertial frame", "net force", "acting force", "mechanically closed system"]:
        print(show_headword(vd, hw))
        print("\n")

    # ── 8. Generate graph images ──
    output_dir = "/mnt/user-data/outputs"

    print(banner("Generating Graphs"))

    path = draw_dependency_graph(vd, output_path=f"{output_dir}/vd_newton_graph", fmt="png")
    print(f"  Dependency graph: {path}")

    houses = vd.detect_houses()
    for i, house in enumerate(houses):
        path = draw_house(vd, house, output_path=f"{output_dir}/vd_house_{i+1}", fmt="png")
        print(f"  House {i+1}: {path}")

    path = draw_house_chain(vd, output_path=f"{output_dir}/vd_house_chain", fmt="png")
    print(f"  House chain: {path}")

    print(f"\n  {C.GREEN}All outputs written to {output_dir}/{C.RESET}")


if __name__ == "__main__":
    main()
