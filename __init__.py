"""
vd - The Valid Dictionary Engine.

This file is used in two layouts:

- package layout: parent directory contains ``vd/``
- flat layout: tests are run directly from this directory

Keep import failure non-fatal for the flat layout, where pytest imports
``__init__.py`` during collection even though tests import sibling modules
directly.
"""

try:
    from vd.engine import VDInstance, Entry, Tokeniser, C
    from vd.newton import build_newton_instance, NEWTON_ENTRIES, SECTIONS
    from vd.display import (
        show_entry, show_entry_table, show_decomposition,
        show_laws, show_houses, show_audit, show_headword,
        show_graph_stats, full_report, banner,
    )
    from vd.viz import draw_dependency_graph, draw_house, draw_house_chain

    __all__ = [
        'VDInstance', 'Entry', 'Tokeniser',
        'build_newton_instance', 'NEWTON_ENTRIES', 'SECTIONS',
        'show_entry', 'show_entry_table', 'show_decomposition',
        'show_laws', 'show_houses', 'show_audit', 'show_headword',
        'show_graph_stats', 'full_report',
        'draw_dependency_graph', 'draw_house', 'draw_house_chain',
    ]
except ModuleNotFoundError:
    from engine import VDInstance, Entry, Tokeniser, C

    __all__ = ['VDInstance', 'Entry', 'Tokeniser', 'C']
