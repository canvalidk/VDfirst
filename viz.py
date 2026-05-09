"""
vd/viz.py — VD Graph Visualization

Draws dependency graphs, highlights triplets/houses, and produces
publication-quality figures.
"""

from __future__ import annotations
import graphviz
import networkx as nx
from pathlib import Path
from vd.engine import VDInstance, C


def draw_dependency_graph(
    vd: VDInstance,
    output_path: str = "vd_graph",
    fmt: str = "png",
    highlight_laws: bool = True,
    highlight_houses: bool = False,
    show_entry_indices: bool = True,
    title: str | None = None,
    rankdir: str = "TB",
) -> str:
    """
    Draw the dependency graph using Graphviz.

    Nodes are headwords. Edges are definition-references.
    Laws are highlighted with coloured clusters.

    Returns the path to the rendered file.
    """
    G = vd.graph
    laws = vd.detect_laws() if highlight_laws else []
    houses = vd.detect_houses() if highlight_houses else []

    # Build colour map for law membership
    law_colours = [
        "#E8D5B7",  # warm sand
        "#B7D5E8",  # cool blue
        "#D5E8B7",  # soft green
        "#E8B7D5",  # rose
        "#D5B7E8",  # lavender
        "#E8E0B7",  # cream
    ]

    node_law_map = {}  # headword -> list of law indices
    for i, law in enumerate(laws):
        for hw in law['trio']:
            node_law_map.setdefault(hw, []).append(i)

    # Graphviz dot
    dot = graphviz.Digraph(
        name=title or f"VD: {vd.name}",
        format=fmt,
        engine="dot",
    )
    dot.attr(
        rankdir=rankdir,
        bgcolor="white",
        fontname="Helvetica",
        label=title or f"Dependency Graph: {vd.name}",
        labelloc="t",
        fontsize="16",
        pad="0.5",
    )
    dot.attr("node", fontname="Helvetica", fontsize="10", style="filled")
    dot.attr("edge", color="#666666", arrowsize="0.6")

    # Collect entry-index labels per headword
    hw_entries = {}
    for e in vd.entries:
        hw_entries.setdefault(e.headword, []).append(e.index)

    # Add nodes
    added_nodes = set()
    for node in G.nodes():
        if node in added_nodes:
            continue

        # Entry indices label
        indices = hw_entries.get(node, [])
        idx_label = ",".join(f"E{i}" for i in indices)
        label = f"{node}\\n[{idx_label}]" if show_entry_indices else node

        # Determine node style
        entries_for_node = vd.entry_by_headword(node)
        is_grounded = any(e.is_meaningfully_defined for e in entries_for_node)

        if node in node_law_map:
            # Part of a law
            law_idx = node_law_map[node][0]
            fill = law_colours[law_idx % len(law_colours)]
            shape = "box"
            # Check if it's an anchor
            is_anchor = any(
                laws[li]['anchor'] == node for li in node_law_map[node]
            )
            if is_anchor:
                shape = "hexagon"
        elif is_grounded:
            fill = "#F0F0F0"
            shape = "ellipse"
        else:
            fill = "#FFFFFF"
            shape = "ellipse"

        dot.node(
            node,
            label=label,
            fillcolor=fill,
            shape=shape,
            penwidth="1.5" if node in node_law_map else "1.0",
        )
        added_nodes.add(node)

    # Add edges
    for u, v in G.edges():
        # Highlight intra-law edges
        is_law_edge = False
        edge_colour = "#999999"
        for i, law in enumerate(laws):
            if u in law['trio'] and v in law['trio']:
                is_law_edge = True
                edge_colour = "#CC4444"
                break

        dot.edge(
            u, v,
            color=edge_colour,
            penwidth="2.0" if is_law_edge else "1.0",
            style="bold" if is_law_edge else "solid",
        )

    # Render
    out = dot.render(output_path, cleanup=True)
    return out


def draw_house(
    vd: VDInstance,
    house: dict,
    output_path: str = "vd_house",
    fmt: str = "png",
) -> str:
    """
    Draw a single six-entry house showing the chimney-triplet-walls structure.
    """
    law = house['law']
    anchor = law['anchor']
    c1 = house['wall_1']['headword']
    c2 = house['wall_2']['headword']

    dot = graphviz.Digraph(
        name=f"House: {anchor}",
        format=fmt,
        engine="dot",
    )
    dot.attr(
        rankdir="TB",
        bgcolor="white",
        fontname="Helvetica",
        label=f"Six-Entry House: {anchor} law",
        labelloc="t",
        fontsize="14",
    )
    dot.attr("node", fontname="Helvetica", fontsize="9")
    dot.attr("edge", arrowsize="0.6")

    # Chimney
    chimney = house['chimney']
    chimney_id = f"chimney_{anchor}"
    chimney_label = f"CHIMNEY\\nE{chimney.index}: {anchor}" if chimney else f"CHIMNEY\\n(missing)"
    dot.node(chimney_id, label=chimney_label,
             shape="box", style="filled", fillcolor="#FFE4B5",
             penwidth="2.0")

    # Triplet entries
    triplet = house['triplet']
    triplet_ids = []
    for e in triplet:
        tid = f"triplet_{e.headword}_{e.index}"
        triplet_ids.append((tid, e))

        is_anchor_entry = (e.headword == anchor)
        fill = "#FFD700" if is_anchor_entry else "#87CEEB"
        dot.node(tid,
                 label=f"TRIPLET\\nE{e.index}: {e.headword}",
                 shape="box", style="filled", fillcolor=fill,
                 penwidth="2.0")

    # Walls
    for wall_key, fill in [('wall_1', '#90EE90'), ('wall_2', '#90EE90')]:
        wall = house[wall_key]
        wid = f"wall_{wall['headword']}"
        if wall['entry']:
            label = f"WALL\\nE{wall['entry'].index}: {wall['headword']}"
        else:
            label = f"WALL\\n(missing): {wall['headword']}"
        dot.node(wid, label=label,
                 shape="box", style="filled", fillcolor=fill,
                 penwidth="2.0")

    # Edges: chimney -> triplet anchor entry (same headword link)
    for tid, e in triplet_ids:
        if e.headword == anchor:
            dot.edge(chimney_id, tid, style="dashed",
                     label="redefine", fontsize="8", color="#CC6600")

    # Edges: triplet internal (mutual references)
    for tid1, e1 in triplet_ids:
        for tid2, e2 in triplet_ids:
            if tid1 != tid2 and e2.headword in e1.hw_tokens:
                dot.edge(tid1, tid2, color="#CC4444", penwidth="2.0")

    # Edges: triplet -> walls (same headword link)
    for tid, e in triplet_ids:
        for wall_key in ['wall_1', 'wall_2']:
            wall = house[wall_key]
            if e.headword == wall['headword'] and wall['entry']:
                wid = f"wall_{wall['headword']}"
                dot.edge(tid, wid, style="dashed",
                         label="ground", fontsize="8", color="#006600")

    out = dot.render(output_path, cleanup=True)
    return out


def draw_house_chain(
    vd: VDInstance,
    output_path: str = "vd_houses",
    fmt: str = "png",
) -> str:
    """
    Draw all houses showing how walls overlap into chimneys.
    """
    houses = vd.detect_houses()

    dot = graphviz.Digraph(
        name="House Chain",
        format=fmt,
        engine="dot",
    )
    dot.attr(
        rankdir="TB",
        bgcolor="white",
        fontname="Helvetica",
        label=f"House Chain: {vd.name}\\n(walls become chimneys)",
        labelloc="t",
        fontsize="16",
        nodesep="0.8",
        ranksep="1.2",
    )

    colours = ["#FFE4B5", "#B7D5E8", "#D5E8B7", "#E8B7D5", "#E8E0B7", "#D5B7E8"]

    for hi, house in enumerate(houses):
        col = colours[hi % len(colours)]
        law = house['law']
        anchor = law['anchor']
        c1, c2 = law['cyclic']

        with dot.subgraph(name=f"cluster_{hi}") as sub:
            sub.attr(
                label=f"Law {hi+1}: {anchor}",
                style="rounded,filled",
                fillcolor=col + "40",
                color=col.replace("#", "#"),
                fontsize="11",
            )

            # Add nodes for this house
            for e in house['triplet']:
                nid = f"h{hi}_t_{e.index}"
                sub.node(nid,
                         label=f"E{e.index}\\n{e.headword}",
                         shape="box", style="filled",
                         fillcolor=col, fontsize="8")

            if house['chimney']:
                nid = f"h{hi}_chim"
                sub.node(nid,
                         label=f"E{house['chimney'].index}\\n{anchor}\\n(chimney)",
                         shape="invtriangle", style="filled",
                         fillcolor="#FFD700", fontsize="8")

            for wk in ['wall_1', 'wall_2']:
                w = house[wk]
                if w['entry']:
                    nid = f"h{hi}_{wk}"
                    sub.node(nid,
                             label=f"E{w['entry'].index}\\n{w['headword']}\\n(wall)",
                             shape="rectangle", style="filled",
                             fillcolor="#90EE90", fontsize="8")

    out = dot.render(output_path, cleanup=True)
    return out
