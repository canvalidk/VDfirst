"""
vd/simulator.py — Simulator over a VDInstance.

The inspection layer used by the REPL: pure, read-only queries over the
dictionary plus an `analyse` pass-through that produces a Definiens. No
I/O, no trace state, no mutation of the underlying VDInstance.

The REPL does dispatch, prompts, and trace state. This file is the data
layer it queries.

Conventions:
  - 'index' is an E-number (0-based, matching VDInstance.entries).
  - E-numbers are non-negative; we explicitly reject negative indices
    rather than allow Python's silent wrap-around.
  - 'headword' is the original (un-normalised) form as authored.
  - All methods are pure: no mutation of the VDInstance.
"""

from __future__ import annotations

from engine import VDInstance
from definiens import Definiens


class Simulator:
    """Read-only oracle over a VDInstance.

    Inspection and trace commands query this. Construction takes a
    VDInstance and holds it on `.instance`; the simulator never mutates
    it.
    """

    def __init__(self, instance: VDInstance):
        self.instance = instance

    # ── Internal helpers ────────────────────────────────────────────

    def _check_index(self, index: int) -> None:
        if index < 0:
            raise IndexError(
                f"entry index {index}: E-numbers are non-negative"
            )
        n = len(self.instance.entries)
        if index >= n:
            if n == 0:
                raise IndexError(
                    f"entry index {index} out of range; "
                    f"dictionary is empty"
                )
            raise IndexError(
                f"entry index {index} out of range; valid: 0..{n - 1}"
            )

    # ── Counts ──────────────────────────────────────────────────────

    def entry_count(self) -> int:
        """Total number of entries (counts redefinitions separately)."""
        return len(self.instance.entries)

    def headword_count(self) -> int:
        """Number of distinct headwords."""
        return len(self.instance.headword_set)

    # ── Headword listing ────────────────────────────────────────────

    def all_headwords(self) -> list[str]:
        """All distinct headwords, sorted alphabetically.

        Sortedness is a contract: callers that want dictionary order
        of first appearance can derive it via entry_headword over
        range(entry_count()) and dedup themselves.
        """
        return sorted(self.instance.headword_set)

    # ── Entry access by index ───────────────────────────────────────

    def entry_text(self, index: int) -> str:
        """Raw definition text at the given E-number.

        Raises IndexError on out-of-range or negative indices.
        """
        self._check_index(index)
        return self.instance.entries[index].definition

    def entry_headword(self, index: int) -> str:
        """Headword at the given E-number.

        Raises IndexError on out-of-range or negative indices.
        """
        self._check_index(index)
        return self.instance.entries[index].headword

    # ── Lookup by headword ──────────────────────────────────────────

    def entry_indexes(self, headword: str) -> list[int]:
        """E-numbers applicable to a headword or headword call.

        Exact authored-headword lookup remains the fast path.  Otherwise,
        a bare, partial, or complete call resolves through the signature's
        stem.  Returns [] if no signature exists.  Results remain in
        dictionary order.
        """
        if not headword:
            return []

        exact = [
            e.index for e in self.instance.entries
            if e.headword == headword
        ]
        if exact:
            return exact
        return [e.index for e in self.instance.entry_by_call(headword)]

    def instantiated_entry_text(self, index: int, call: str) -> str:
        """Selected entry text after flat instantiation for ``call``."""

        self._check_index(index)
        return self.instance.instantiate_entry(index, call)

    # ── Tokenisation pass-through ───────────────────────────────────

    def analyse(self, text: str) -> Definiens:
        """Ordered tokenisation of arbitrary text against the
        dictionary's current headword set.

        Pass-through to VDInstance.analyse; no extra logic here.
        """
        return self.instance.analyse(text)
