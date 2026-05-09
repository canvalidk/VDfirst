"""
vd/display.py — Query Interface & Pretty Display

Provides functions to inspect and interrogate a VD instance,
producing formatted terminal output.
"""

from __future__ import annotations
from textwrap import wrap, indent
import networkx as nx
from vd.engine import VDInstance, Entry, C


WIDTH = 88
SEP = "─" * WIDTH
DSEP = "═" * WIDTH


def _box(title: str, body: str, colour: str = C.CYAN) -> str:
    """Wrap text in a titled box."""
    top = f"┌{'─' * (WIDTH - 2)}┐"
    bot = f"└{'─' * (WIDTH - 2)}┘"
    title_line = f"│ {colour}{C.BOLD}{title}{C.RESET}{' ' * (WIDTH - 4 - len(title))}│"
    body_lines = []
    for line in body.split('\n'):
        # Truncate/pad
        visible = line[:WIDTH - 4]
        # Can't easily pad ANSI strings, just use raw
        body_lines.append(f"│ {visible}")
    return '\n'.join([top, title_line, f"│{'─' * (WIDTH - 2)}│"] + body_lines + [bot])


def banner(text: str) -> str:
    return f"\n{C.BOLD}{C.CYAN}{DSEP}\n  {text}\n{DSEP}{C.RESET}\n"


# ── Entry display ───────────────────────────────────────────────────

def show_entry(e: Entry, verbose: bool = False) -> str:
    """Format a single entry for display."""
    sup = C.styled("SUPPORTED", C.GREEN) if e.is_supported else C.styled("UNSUPPORTED", C.RED)
    md = C.styled(" [meaningfully defined]", C.BLUE) if e.is_meaningfully_defined else ""

    lines = [
        f"{C.BOLD}E{e.index}{C.RESET}  {C.YELLOW}{e.headword}{C.RESET}  {sup}{md}",
        f"  {C.DIM}:= \"{e.definition[:120]}{'...' if len(e.definition) > 120 else ''}\"{C.RESET}",
    ]

    if verbose:
        lines.append(f"  hw_tokens:      {sorted(e.hw_tokens) if e.hw_tokens else '∅'}")
        lines.append(f"  residue_tokens: {sorted(e.residue_tokens)[:8]}{'...' if len(e.residue_tokens) > 8 else ''}")
        if e.forward_refs:
            lines.append(f"  forward_refs:   {C.RED}{sorted(e.forward_refs)}{C.RESET}")

    return '\n'.join(lines)


def show_entry_table(vd: VDInstance) -> str:
    """Compact table of all entries."""
    lines = [banner(f"Entry Log: {vd.name}")]
    lines.append(f"{'Idx':<5} {'Headword':<40} {'Sup':>5} {'MD':>4} {'|H|':>4} {'|R|':>4} {'|F|':>4}")
    lines.append(SEP)

    for e in vd.entries:
        sup = C.styled("✓", C.GREEN) if e.is_supported else C.styled("✗", C.RED)
        md = C.styled("●", C.BLUE) if e.is_meaningfully_defined else " "
        lines.append(
            f"E{e.index:<4} {e.headword:<40} {sup:>14} {md:>13} {len(e.hw_tokens):>4} "
            f"{len(e.residue_tokens):>4} {len(e.forward_refs):>4}"
        )

    return '\n'.join(lines)


# ── Decomposition display ──────────────────────────────────────────

def show_decomposition(vd: VDInstance, entry_index: int) -> str:
    """Show the full 6-component decomposition of an entry."""
    e = vd.entry_by_index(entry_index)
    lines = [banner(f"Decomposition: E{e.index}")]

    components = [
        ("1. h_i  (headword)",          e.headword),
        ("2. D_i  (definition)",        e.definition),
        ("3. τ(D_i) (all tokens)",      sorted(e.tokens)[:15]),
        ("4. H_i  (headword tokens)",   sorted(e.hw_tokens) if e.hw_tokens else "∅"),
        ("5. R_i  (residue tokens)",    sorted(e.residue_tokens)[:15]),
        ("6. F_i  (forward refs)",      sorted(e.forward_refs) if e.forward_refs else "∅"),
    ]

    for label, val in components:
        lines.append(f"  {C.BOLD}{label}{C.RESET}")
        if isinstance(val, list):
            lines.append(f"    {val}")
        else:
            wrapped = wrap(str(val), width=WIDTH - 6)
            for w in wrapped:
                lines.append(f"    {w}")
        lines.append("")

    # Predicates
    lines.append(f"  {C.BOLD}Predicates:{C.RESET}")
    lines.append(f"    Supported(E{e.index})           = {e.is_supported}")
    lines.append(f"    MeaningfullyDefined(E{e.index}) = {e.is_meaningfully_defined}")

    return '\n'.join(lines)


# ── Law display ─────────────────────────────────────────────────────

def show_laws(vd: VDInstance) -> str:
    """Display all detected laws with their structure."""
    laws = vd.detect_laws()
    lines = [banner(f"Laws Detected: {len(laws)}")]

    for i, law in enumerate(laws):
        degree = vd.degree_of_law(law)
        lines.append(f"{C.BOLD}{C.YELLOW}Law {i+1}{C.RESET}  "
                      f"degree={degree}")
        lines.append(f"  Anchor (November): {C.CYAN}{law['anchor']}{C.RESET}")
        lines.append(f"  Cyclic (Winter):   {C.MAGENTA}{law['cyclic'][0]}{C.RESET}")
        lines.append(f"                     {C.MAGENTA}{law['cyclic'][1]}{C.RESET}")

        lines.append(f"  Entries:")
        for e in sorted(law['entries'], key=lambda x: x.index):
            role = "anchor" if e.headword == law['anchor'] else "cyclic"
            lines.append(f"    E{e.index}: {e.headword} ({role})")

        lines.append(SEP)

    return '\n'.join(lines)


# ── House display ───────────────────────────────────────────────────

def show_houses(vd: VDInstance) -> str:
    """Display all six-entry houses."""
    houses = vd.detect_houses()
    lines = [banner(f"Six-Entry Houses: {len(houses)}")]

    for i, house in enumerate(houses):
        law = house['law']
        anchor = law['anchor']

        lines.append(f"{C.BOLD}{C.YELLOW}House {i+1}: {anchor}{C.RESET}")
        lines.append("")

        # Chimney
        ch = house['chimney']
        if ch:
            lines.append(f"  {C.styled('▲ CHIMNEY', C.YELLOW, C.BOLD)}  E{ch.index}: {ch.headword}")
            lines.append(f"    := \"{ch.definition[:80]}...\"")
        else:
            lines.append(f"  {C.styled('▲ CHIMNEY', C.RED, C.BOLD)}  (missing)")
        lines.append("")

        # Triplet
        lines.append(f"  {C.styled('◆ TRIPLET', C.CYAN, C.BOLD)}")
        for e in house['triplet']:
            role = "Nov" if e.headword == anchor else "Win"
            lines.append(f"    [{role}] E{e.index}: {e.headword}")
            lines.append(f"          refs → {sorted(e.hw_tokens & set(law['trio']))}")
        lines.append("")

        # Walls
        for wk in ['wall_1', 'wall_2']:
            w = house[wk]
            if w['entry']:
                lines.append(f"  {C.styled('■ WALL', C.GREEN, C.BOLD)}     E{w['entry'].index}: {w['headword']}")
                lines.append(f"    := \"{w['entry'].definition[:80]}...\"")
            else:
                lines.append(f"  {C.styled('■ WALL', C.RED, C.BOLD)}     (missing): {w['headword']}")
        lines.append("")
        lines.append(DSEP)

    return '\n'.join(lines)


# ── Audit display ───────────────────────────────────────────────────

def show_audit(vd: VDInstance) -> str:
    """Run all structural audits and display results."""
    lines = [banner("Structural Audit")]

    # Summary
    lines.append(f"  {vd.summary()}")
    lines.append("")

    # Supported check
    unsupported = vd.audit_supported()
    if unsupported:
        lines.append(f"  {C.styled('UNSUPPORTED ENTRIES:', C.RED, C.BOLD)} {len(unsupported)}")
        for e in unsupported:
            lines.append(f"    E{e.index} ({e.headword}): forward refs = {sorted(e.forward_refs)}")
    else:
        lines.append(f"  {C.styled('✓ All entries supported', C.GREEN)}")
    lines.append("")

    # Grounding check
    ungrounded = vd.audit_grounded()
    if ungrounded:
        lines.append(f"  {C.styled('UNGROUNDED ANCHORS:', C.RED, C.BOLD)} {ungrounded}")
    else:
        lines.append(f"  {C.styled('✓ All law anchors grounded', C.GREEN)}")
    lines.append("")

    # Productivity check
    dead = vd.audit_productivity()
    if dead:
        lines.append(f"  {C.styled('UNPRODUCTIVE HEADWORDS:', C.YELLOW, C.BOLD)} {dead}")
    else:
        lines.append(f"  {C.styled('✓ All reachable headwords productive', C.GREEN)}")
    lines.append("")

    # Meaningfully defined entries
    md_entries = [e for e in vd.entries if e.is_meaningfully_defined]
    lines.append(f"  {C.BOLD}Meaningfully defined (ground) entries:{C.RESET} {len(md_entries)}")
    for e in md_entries:
        lines.append(f"    E{e.index}: {e.headword}")
    lines.append("")

    # Law summary
    laws = vd.detect_laws()
    lines.append(f"  {C.BOLD}Laws:{C.RESET} {len(laws)}")
    for i, law in enumerate(laws):
        d = vd.degree_of_law(law)
        lines.append(f"    Law {i+1} (degree {d}): "
                      f"Nov={law['anchor']}, Win={law['cyclic']}")

    return '\n'.join(lines)


# ── Headword inspector ──────────────────────────────────────────────

def show_headword(vd: VDInstance, hw: str) -> str:
    """Everything the system knows about a headword."""
    entries = vd.entry_by_headword(hw)
    if not entries:
        return f"{C.RED}No entries found for headword: {hw}{C.RESET}"

    lines = [banner(f"Headword: {hw}")]
    lines.append(f"  Entries: {len(entries)}")
    lines.append("")

    for e in entries:
        lines.append(show_entry(e, verbose=True))
        lines.append("")

    # Graph context
    G = vd.graph
    if hw in G:
        deps = list(G.successors(hw))
        used_by = list(G.predecessors(hw))
        lines.append(f"  {C.BOLD}Depends on:{C.RESET} {deps}")
        lines.append(f"  {C.BOLD}Used by:{C.RESET}    {used_by}")

    # Law membership
    laws = vd.detect_laws()
    for i, law in enumerate(laws):
        if hw in law['trio']:
            role = "Anchor (November)" if hw == law['anchor'] else "Cyclic (Winter)"
            lines.append(f"  {C.BOLD}Law {i+1}:{C.RESET} {role}")
            lines.append(f"    trio: {law['trio']}")

    return '\n'.join(lines)


# ── Graph stats ─────────────────────────────────────────────────────

def show_graph_stats(vd: VDInstance) -> str:
    """Display dependency graph statistics."""
    G = vd.graph
    lines = [banner("Dependency Graph Statistics")]

    lines.append(f"  Nodes (unique headwords): {G.number_of_nodes()}")
    lines.append(f"  Edges (definition refs):  {G.number_of_edges()}")
    lines.append("")

    # Degree distribution
    in_degs = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)
    lines.append(f"  {C.BOLD}Top referenced headwords (in-degree):{C.RESET}")
    for hw, d in in_degs[:10]:
        bar = "█" * d
        lines.append(f"    {hw:<40} {d:>3} {C.CYAN}{bar}{C.RESET}")
    lines.append("")

    out_degs = sorted(G.out_degree(), key=lambda x: x[1], reverse=True)
    lines.append(f"  {C.BOLD}Most dependent headwords (out-degree):{C.RESET}")
    for hw, d in out_degs[:10]:
        bar = "█" * d
        lines.append(f"    {hw:<40} {d:>3} {C.MAGENTA}{bar}{C.RESET}")

    # Connected components (undirected)
    UG = G.to_undirected()
    components = list(nx.connected_components(UG))
    lines.append(f"\n  {C.BOLD}Connected components:{C.RESET} {len(components)}")
    for i, comp in enumerate(sorted(components, key=len, reverse=True)):
        lines.append(f"    Component {i+1}: {len(comp)} nodes")
        if len(comp) <= 8:
            lines.append(f"      {sorted(comp)}")

    return '\n'.join(lines)


# ── Full report ─────────────────────────────────────────────────────

def full_report(vd: VDInstance) -> str:
    """Generate a complete structural report."""
    sections = [
        show_entry_table(vd),
        show_audit(vd),
        show_laws(vd),
        show_houses(vd),
        show_graph_stats(vd),
    ]
    return '\n\n'.join(sections)
