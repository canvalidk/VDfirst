"""
vd/engine.py — The Valid Dictionary Engine

Core data structures and computations for a VD instance.
Implements the append-only entry log, headword-aware tokeniser,
per-entry six-component decomposition, dependency graph,
law/triplet detection, six-entry house detection, and structural audits.

Design note: everything downstream of (headword, definition_string)
is a pure function of the log state. Human judgment lives only in
authoring entries and in the residual/poetic layer.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from itertools import combinations
import networkx as nx

from application import (
    ARGUMENT_ATOM_PATTERN,
    HeadwordApplicationError,
    HeadwordArityError,
    HeadwordCall,
    HeadwordSignature,
    HeadwordSignatureConflictError,
    instantiate_definition,
)
from residual import Residual
from definiens import Definiens


# ── Colour helpers (ANSI) ───────────────────────────────────────────

class C:
    """Tiny ANSI colour namespace."""
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"

    @staticmethod
    def styled(text, *codes):
        return "".join(codes) + str(text) + C.RESET


# ── Entry ───────────────────────────────────────────────────────────

@dataclass
class Entry:
    """
    A single VD entry: (headword, definition_string).

    After insertion into a VDInstance, the computed fields are populated:
    index, tokens, hw_tokens, residue_tokens, forward_refs, is_supported,
    is_meaningfully_defined.
    """
    headword: str
    definition: str
    signature: HeadwordSignature = field(init=False)

    # Computed at insertion time (stage-aware)
    index: Optional[int] = None
    tokens: set[str] = field(default_factory=set)
    hw_tokens: set[str] = field(default_factory=set)       # H_i = τ(D_i) ∩ HD
    residue_tokens: set[str] = field(default_factory=set)   # R_i = τ(D_i) \ HD
    forward_refs: set[str] = field(default_factory=set)     # F_i = H_i \ PD_i
    is_supported: bool = False                               # F_i = ∅
    is_meaningfully_defined: bool = False                    # H_i = ∅

    def __post_init__(self) -> None:
        self.signature = HeadwordSignature.parse(self.headword)

    def short(self) -> str:
        return f"E{self.index}"

    def __repr__(self):
        tag = "✓" if self.is_supported else "⚠"
        return f"E{self.index} [{tag}] {self.headword}"


# ── Tokeniser ───────────────────────────────────────────────────────

class Tokeniser:
    """
    Headword-aware tokeniser implementing R-TOK-00.

    Core guarantees:
      1. No substring matching — headwords only match at delimiter boundaries
      2. Delimiter discipline — explicit set of boundary characters
      3. Backtick spans are escaped literal text
      4. Underscores introduce positional headword arguments

    Strategy:
      - Normalise both headwords and definitions to a canonical form
      - Parse authored headwords as signatures (for example ``force_p_t``)
      - Match their stems longest-first at valid delimiter boundaries
      - Consume zero through signature-arity underscore arguments
      - Blank matched regions to prevent double-counting
      - Extract residue word-tokens from whatever remains

    Normalisation rules:
      - Collapse whitespace to single space
      - Normalise parenthetical arguments: strip internal padding around ( , )
        so "net force(p, t)" and "net force(p,t)" are equivalent
      - Matching is case-insensitive (configurable)
    """

    # Characters that constitute a valid boundary (delimiter)
    # A headword match is valid iff it starts at position 0 or is preceded
    # by a delimiter, AND ends at len(text) or is followed by a delimiter.
    DELIMITERS = set(' \t\n.,;:!?/=+*<>[]{}()|"\'–—−#@&^~')

    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive
        self._log: list[dict] = []  # audit log for debugging

    @staticmethod
    def normalise(text: str) -> str:
        """
        Canonical normalisation applied to both headwords and definitions.

        1. Strip outer whitespace and quotes
        2. Collapse internal whitespace to single space
        3. Normalise headword-style parenthetical arguments:
           Only collapses space before '(' when preceded by a word char
           (catches "f (x)" → "f(x)" but not "particle (in a frame)")
           Normalises comma-space inside parens: "(p, t)" → "(p,t)"
        """
        text = text.strip().strip('"').strip()
        text = re.sub(r'\s+', ' ', text)

        # Normalise headword-style argument parens:
        # "word (" → "word(" but only when ( follows a word-character
        text = re.sub(r'(\w)\s+\(', r'\1(', text)

        # Normalise space before closing paren when inside short argument:
        # Greedy match for short paren groups that look like arguments
        text = re.sub(r'\(\s+', '(', text)

        # Normalise comma-space inside parenthetical arguments
        # "(p, t)" → "(p,t)"  but be conservative: only inside parens
        def _norm_paren_content(m):
            inner = m.group(1)
            inner = re.sub(r',\s+', ',', inner)
            inner = inner.rstrip()
            return f'({inner})'

        text = re.sub(r'\(([^)]{1,40})\)', _norm_paren_content, text)

        return text

    @staticmethod
    def _unescape_with_mask(text: str) -> tuple[str, list[bool]]:
        """Remove backtick escape markers and mark escaped characters.

        Escaped spans are literal text: they survive in the returned string
        but are hidden from headword matching. A dangling opening backtick
        escapes through end-of-string; this keeps the rule simple for the
        simulator.
        """

        plain: list[str] = []
        mask: list[bool] = []
        in_escape = False
        for ch in text:
            if ch == "`":
                in_escape = not in_escape
                continue
            plain.append(ch)
            mask.append(in_escape)
        return "".join(plain), mask

    @staticmethod
    def _mask_escaped(text: str, mask: list[bool]) -> str:
        """Blank escaped characters while preserving string positions."""

        return "".join(
            "\x00" if escaped else ch
            for ch, escaped in zip(text, mask)
        )

    def _is_boundary(self, text: str, pos: int) -> bool:
        """Check if position is a valid boundary (start/end of text or delimiter)."""
        if pos < 0 or pos >= len(text):
            return True
        return text[pos] in self.DELIMITERS

    def _find_headword_at_boundary(
        self, hw_norm: str, text: str
    ) -> list[tuple[int, int]]:
        """
        Find all occurrences of hw_norm in text that respect delimiter boundaries.
        Returns list of (start, end) positions.
        """
        matches = []
        search_text = text if self.case_sensitive else text.lower()
        search_hw = hw_norm if self.case_sensitive else hw_norm.lower()

        start = 0
        while start <= len(search_text) - len(search_hw):
            pos = search_text.find(search_hw, start)
            if pos == -1:
                break

            end_pos = pos + len(search_hw)

            # Boundary check: character before the match
            left_ok = self._is_boundary(text, pos - 1)

            # Boundary check: character after the match
            right_ok = self._is_boundary(text, end_pos)

            if left_ok and right_ok:
                matches.append((pos, end_pos))

            start = pos + 1

        return matches

    def _signatures(
        self,
        headword_set: set[str],
    ) -> list[HeadwordSignature]:
        """Parse and validate the temporary one-signature-per-stem rule."""

        by_stem: dict[str, HeadwordSignature] = {}
        for headword in sorted(headword_set):
            signature = HeadwordSignature.parse(headword)
            normalised = self.normalise(signature.stem)
            key = normalised if self.case_sensitive else normalised.lower()
            existing = by_stem.get(key)
            if existing is not None and existing.formals != signature.formals:
                raise HeadwordSignatureConflictError(
                    existing.stem,
                    existing.formals,
                    signature.formals,
                )
            if existing is None:
                by_stem[key] = signature

        return sorted(
            by_stem.values(),
            key=lambda signature: len(self.normalise(signature.stem)),
            reverse=True,
        )

    def _find_signature_calls(
        self,
        signature: HeadwordSignature,
        text: str,
    ) -> list[tuple[int, int, HeadwordCall]]:
        """Find bare/partial/full calls of one signature in ``text``."""

        base = self.normalise(signature.stem)
        search_text = text if self.case_sensitive else text.lower()
        search_base = base if self.case_sensitive else base.lower()
        argument_re = re.compile(ARGUMENT_ATOM_PATTERN)
        matches: list[tuple[int, int, HeadwordCall]] = []

        cursor = 0
        while cursor <= len(search_text) - len(search_base):
            start = search_text.find(search_base, cursor)
            if start == -1:
                break
            cursor = start + 1

            if not self._is_boundary(text, start - 1):
                continue

            end = start + len(search_base)
            actuals: list[str] = []
            malformed = False
            while end < len(text) and text[end] == "_":
                match = argument_re.match(text, end + 1)
                if match is None:
                    malformed = True
                    break
                actuals.append(match.group(0))
                end = match.end()

            if malformed or not self._is_boundary(text, end):
                continue

            call = HeadwordCall(signature.stem, tuple(actuals))
            if call.arity > signature.arity:
                surface = text[start:end]
                raise HeadwordArityError(
                    surface,
                    signature.stem,
                    signature.arity,
                    call.arity,
                )
            matches.append((start, end, call))

        return matches

    def _collect_headword_matches(
        self,
        text: str,
        escaped_mask: list[bool],
        headword_set: set[str],
    ) -> tuple[list[tuple[int, int, str, str]], str]:
        """Return positional (signature, call) matches and blanked text."""

        working = self._mask_escaped(text, escaped_mask)
        matches: list[tuple[int, int, str, str]] = []
        for signature in self._signatures(headword_set):
            for start, end, call in self._find_signature_calls(
                signature,
                working,
            ):
                matches.append((start, end, signature.text, call.text))
                working = (
                    working[:start]
                    + "\x00" * (end - start)
                    + working[end:]
                )
        return matches, working

    def tokenise_definition(
        self, definition: str, headword_set: set[str]
    ) -> tuple[set[str], set[str], set[str]]:
        """
        Tokenise a definition string against a headword set.

        Algorithm:
          1. Normalise the definition
          2. Normalise all headwords
          3. Sort headwords longest-first (greedy match)
          4. For each headword, find boundary-respecting matches
          5. Blank matched regions with placeholder chars
          6. Extract residue word-tokens from what remains

        Returns (all_tokens, hw_tokens, residue_tokens).
        """
        text, escaped_mask = self._unescape_with_mask(
            self.normalise(definition)
        )
        matches, working = self._collect_headword_matches(
            text,
            escaped_mask,
            headword_set,
        )
        hw_found: set[str] = set()
        match_log: list[dict] = []
        for start, end, signature, call in matches:
            hw_found.add(signature)
            match_log.append({
                'headword': signature,
                'call': call,
                'normalised': self.normalise(signature),
                'positions': [(start, end)],
            })

        # Extract residue: word-tokens from non-blanked regions
        # Replace blanked chars with spaces, then tokenise
        residue_text = working.replace('\x00', ' ')
        residue: set[str] = set()
        for word in re.findall(r'[a-zA-Z_]\w*', residue_text):
            if len(word) > 1 or word in ('a', 'A'):
                residue.add(word)

        all_tokens = hw_found | residue

        # Store log for debugging
        self._log.append({
            'definition': definition,
            'normalised': text,
            'hw_found': hw_found.copy(),
            'residue': residue.copy(),
            'match_log': match_log,
        })

        return all_tokens, hw_found, residue

    def analyse(
        self, definition: str, headword_set: set[str]
    ) -> Definiens:
        """
        Ordered tokenisation: produce a Definiens from a definition string.

        Mirrors `tokenise_definition`'s matching algorithm — same
        normalisation, same longest-first boundary-respecting search, same
        blanking — but preserves match positions and slices the (normalised)
        text accordingly. The result is a Definiens whose:

          - residual.latent are the literal chunks of the normalised text
            between headword matches, in order
          - headwords list holds each canonical call spelling (authored stem,
            supplied actuals preserved) at its hole position

        Self-references are NOT discarded here. That is a higher-layer
        semantic decision; `_tokenise_entry` handles it for stored entries.
        For arbitrary text the caller decides.

        Does not write to `_log`. The simulator's audit needs differ from
        the existing log shape; if needed, log there separately.
        """
        text, escaped_mask = self._unescape_with_mask(
            self.normalise(definition)
        )

        matches, _ = self._collect_headword_matches(
            text,
            escaped_mask,
            headword_set,
        )

        # Sort by position. Overlap should not occur given longest-first +
        # blanking, but assert defensively — silent overlap would corrupt
        # slicing.
        matches.sort(key=lambda m: m[0])
        for i in range(len(matches) - 1):
            if matches[i][1] > matches[i + 1][0]:
                raise RuntimeError(
                    f"overlapping matches in analyse(): "
                    f"{matches[i]!r} vs {matches[i + 1]!r}"
                )

        # Slice text at match boundaries to build (latents, headwords).
        latents: list[str] = []
        headwords: list[str] = []
        cursor = 0
        for start, end, _, call in matches:
            latents.append(text[cursor:start])
            headwords.append(call)
            cursor = end
        latents.append(text[cursor:])

        return Definiens(Residual(latents), headwords)

    @property
    def last_log(self) -> dict:
        """Return the tokenisation log for the most recent call."""
        return self._log[-1] if self._log else {}

    def explain(self, definition: str, headword_set: set[str]) -> str:
        """
        Tokenise and return a human-readable explanation of what happened.
        Useful for debugging tokeniser decisions.
        """
        all_tok, hw_tok, res_tok = self.tokenise_definition(definition, headword_set)
        log = self.last_log

        lines = [
            f"Input:      {definition[:100]}",
            f"Normalised: {log['normalised'][:100]}",
            f"",
            f"Headword matches ({len(hw_tok)}):",
        ]
        for m in log['match_log']:
            positions = ', '.join(f"[{s}:{e}]" for s, e in m['positions'])
            lines.append(f"  ✓ '{m['headword']}' at {positions}")

        lines.append(f"")
        lines.append(f"Residue tokens ({len(res_tok)}): {sorted(res_tok)}")

        # Show rejected matches (headwords NOT found)
        norms = {self.normalise(hw) for hw in headword_set}
        found_norms = {self.normalise(hw) for hw in hw_tok}
        missed = norms - found_norms
        if missed:
            lines.append(f"")
            lines.append(f"Headwords not matched ({len(missed)}):")
            for m in sorted(missed)[:10]:
                lines.append(f"  ✗ '{m}'")

        return '\n'.join(lines)


# ── VD Instance ─────────────────────────────────────────────────────

class VDInstance:
    """
    A Valid Dictionary instance: an append-only log of entries
    with computed structural overlays.
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name
        self.entries: list[Entry] = []
        self.tokeniser = Tokeniser()
        self._graph: Optional[nx.DiGraph] = None
        self._graph_dirty = True

    # ── Entry management ──

    @property
    def headword_set(self) -> set[str]:
        return {e.headword for e in self.entries}

    @property
    def headword_list(self) -> list[str]:
        return [e.headword for e in self.entries]

    @property
    def signatures_by_stem(self) -> dict[str, HeadwordSignature]:
        """The temporary one-signature-per-exact-stem registry."""

        signatures: dict[str, HeadwordSignature] = {}
        for entry in self.entries:
            signatures.setdefault(entry.signature.stem, entry.signature)
        return signatures

    def previously_defined(self, stage: int) -> set[str]:
        """PD_n: headwords from entries before stage n."""
        return {e.headword for e in self.entries[:stage]}

    def _validate_signatures(self, new_entries: list[Entry]) -> None:
        signatures = self.signatures_by_stem
        for entry in new_entries:
            existing = signatures.get(entry.signature.stem)
            if (
                existing is not None
                and existing.formals != entry.signature.formals
            ):
                raise HeadwordSignatureConflictError(
                    entry.signature.stem,
                    existing.formals,
                    entry.signature.formals,
                )
            signatures.setdefault(entry.signature.stem, entry.signature)

    def append(self, headword: str, definition: str) -> Entry:
        """
        Append an entry to the log.

        NOTE: if you are loading a batch, prefer append_many() which does
        two-pass tokenisation against the FULL headword set (per R-SUP-01).
        Single appends tokenise against the headword set known so far,
        which may miss forward-reference edges.  Call retokenise() after
        the log is complete to fix this.
        """
        entry = Entry(headword=headword, definition=definition)
        self._validate_signatures([entry])
        entry.index = len(self.entries)

        # Tokenise before committing so an invalid over-applied reference
        # cannot leave a half-appended entry in the log.
        prospective_headwords = self.headword_set | {entry.headword}
        self._tokenise_entry(entry, prospective_headwords)
        self.entries.append(entry)
        self._graph_dirty = True
        return entry

    def append_many(self, entries: list[tuple[str, str]]) -> list[Entry]:
        """
        Append multiple (headword, definition) pairs with two-pass tokenisation.

        Pass 1: collect all headwords (existing + new).
        Pass 2: tokenise every definition against the FULL headword set.

        This is the correct method per R-SUP-01: HD = {h_1,...,h_N} is the
        complete headword set, not the partial set at each stage.
        """
        # Pass 1: create entries and validate signatures without mutation.
        new_entries: list[Entry] = []
        for hw, defn in entries:
            entry = Entry(headword=hw, definition=defn)
            entry.index = len(self.entries) + len(new_entries)
            new_entries.append(entry)
        self._validate_signatures(new_entries)

        # Preflight every definition before committing the batch.  This
        # catches over-application while preserving append-only atomicity.
        full_hw = self.headword_set | {e.headword for e in new_entries}
        for entry in [*self.entries, *new_entries]:
            self.tokeniser.tokenise_definition(entry.definition, full_hw)

        # Pass 2: commit, then tokenise ALL entries against the complete set.
        self.entries.extend(new_entries)
        for e in self.entries:
            self._tokenise_entry(e, full_hw)

        self._graph_dirty = True
        return new_entries

    def _tokenise_entry(self, entry: Entry, headword_set: set[str]):
        """Compute the 6-component decomposition of an entry."""
        tokens, hw_tokens, residue = self.tokeniser.tokenise_definition(
            entry.definition, headword_set
        )

        # Remove self-reference from hw_tokens
        hw_tokens.discard(entry.headword)

        pd = self.previously_defined(entry.index)

        entry.tokens = tokens
        entry.hw_tokens = hw_tokens
        entry.residue_tokens = residue
        entry.forward_refs = hw_tokens - pd
        entry.is_supported = len(entry.forward_refs) == 0
        entry.is_meaningfully_defined = len(hw_tokens) == 0

    def retokenise(self):
        """
        Re-run tokenisation for ALL entries against the complete headword set.
        Call this after a sequence of single append() calls to ensure
        forward-reference edges are correctly detected.
        """
        full_hw = self.headword_set
        for e in self.entries:
            self._tokenise_entry(e, full_hw)
        self._graph_dirty = True

    def analyse(self, text: str) -> Definiens:
        """
        Ordered tokenisation of arbitrary text against this instance's
        current headword set. Returns a Definiens whose holes correspond
        to headword references in position order.

        This is a thin convenience over `Tokeniser.analyse`; it does not
        mutate dictionary state. Intended consumer: the simulator, which
        feeds the result into a demand-graph node.
        """
        return self.tokeniser.analyse(text, self.headword_set)

    def entry_by_headword(self, hw: str) -> list[Entry]:
        """All entries with a given headword (may be >1 for redefines)."""
        return [e for e in self.entries if e.headword == hw]

    def resolve_call(
        self,
        text: str,
    ) -> tuple[HeadwordSignature, HeadwordCall] | None:
        """Resolve an exact-case call to its dictionary signature."""

        call = HeadwordCall.parse(text)
        signature = self.signatures_by_stem.get(call.stem)
        if signature is None:
            return None
        signature.check(call)
        return signature, call

    def entry_by_call(self, text: str) -> list[Entry]:
        """All entries applicable to a bare, partial, or complete call."""

        resolved = self.resolve_call(text)
        if resolved is None:
            return []
        signature, _ = resolved
        return [
            entry for entry in self.entries
            if entry.signature == signature
        ]

    def instantiate_entry(self, index: int, call_text: str) -> str:
        """Instantiate one selected entry for ``call_text``."""

        entry = self.entry_by_index(index)
        resolved = self.resolve_call(call_text)
        if resolved is None:
            raise HeadwordApplicationError(
                f"no headword signature for {call_text!r}"
            )
        signature, call = resolved
        if entry.signature != signature:
            raise HeadwordApplicationError(
                f"E{index} defines {entry.headword!r}, not {call_text!r}"
            )
        return instantiate_definition(entry.definition, signature, call)

    def entry_by_index(self, i: int) -> Entry:
        return self.entries[i]

    # ── Dependency graph ──

    @property
    def graph(self) -> nx.DiGraph:
        """
        Dependency graph G = (HD, →).
        Edge w → u means: some entry with headword w references u in its definition.
        """
        if self._graph_dirty or self._graph is None:
            self._rebuild_graph()
        return self._graph

    def _rebuild_graph(self):
        G = nx.DiGraph()
        # Add all unique headwords as nodes
        for e in self.entries:
            G.add_node(e.headword)

        # Add edges: h_i → each headword in H_i
        for e in self.entries:
            for ref in e.hw_tokens:
                if ref != e.headword:
                    G.add_edge(e.headword, ref)

        self._graph = G
        self._graph_dirty = False

    # ── Law / triplet detection ──

    def find_3_cycles(self) -> list[tuple[str, str, str]]:
        """
        Find all minimal 3-cycles in the dependency graph.
        A 3-cycle is three nodes (A, B, C) with a directed cycle
        A→B→C→A (in some permutation).
        """
        G = self.graph
        cycles = []

        for trio in combinations(G.nodes(), 3):
            a, b, c = trio
            # Check the two possible rotational orderings
            has_3_cycle = (
                (G.has_edge(a, b) and G.has_edge(b, c) and G.has_edge(c, a)) or
                (G.has_edge(a, c) and G.has_edge(c, b) and G.has_edge(b, a))
            )
            if has_3_cycle:
                cycles.append(tuple(sorted(trio)))

        return list(set(cycles))

    def detect_laws(self) -> list[dict]:
        """
        Detect laws: minimal 3-cycles satisfying the temporal constraint.
        Exactly one headword must be previously-defined (the Anchor/November)
        at the stage the cycle closes; the other two must be new (Winter).

        For each 3-cycle, we find the "triplet entries": the specific entries
        where each headword is defined in terms of the other two.
        """
        cycles = self.find_3_cycles()
        laws = []

        for trio in cycles:
            trio_set = set(trio)

            # For each headword in the trio, find entries that reference
            # at least one other trio member (candidate triplet entries)
            hw_candidates = {}
            for hw in trio:
                candidates = []
                for e in self.entry_by_headword(hw):
                    refs_to_trio = e.hw_tokens & (trio_set - {hw})
                    if refs_to_trio:
                        candidates.append(e)
                hw_candidates[hw] = candidates

            # Each headword must have at least one candidate
            if not all(hw_candidates[hw] for hw in trio):
                continue

            # Pick the best candidate per headword: REQUIRE entries that
            # reference BOTH other trio members (R-LAW-03 3-cycle schema).
            # Each triplet entry must be f(other1, other2).
            triplet_entries = []
            valid_trio = True
            for hw in trio:
                others = trio_set - {hw}
                # Filter to candidates referencing BOTH other members
                full_ref_cands = [
                    e for e in hw_candidates[hw]
                    if others.issubset(e.hw_tokens)
                ]
                if not full_ref_cands:
                    valid_trio = False
                    break
                # Break ties: prefer later index (triplet redefine)
                full_ref_cands.sort(key=lambda e: e.index)
                triplet_entries.append(full_ref_cands[-1])

            if not valid_trio:
                continue

            # Temporal constraint: at the stage the first triplet entry
            # is laid down, exactly one of the three headwords must be PD
            first_triplet_idx = min(e.index for e in triplet_entries)
            pd_at_start = self.previously_defined(first_triplet_idx)

            november_candidates = [hw for hw in trio if hw in pd_at_start]
            winter_candidates = [hw for hw in trio if hw not in pd_at_start]

            if len(november_candidates) == 1 and len(winter_candidates) == 2:
                laws.append({
                    'trio': trio,
                    'anchor': november_candidates[0],
                    'cyclic': tuple(winter_candidates),
                    'entries': triplet_entries,
                    'closing_stage': max(e.index for e in triplet_entries),
                })

        return laws

    # ── Six-entry house detection ──

    def detect_houses(self) -> list[dict]:
        """
        Detect six-entry functional units (houses).

        A house consists of:
          - Chimney (1): peripheral definition of the Anchor, before the triplet
          - Triplet (3): the law entries
          - Walls (2): peripheral definitions of the Winter words, after the triplet
        """
        laws = self.detect_laws()
        houses = []

        for law in laws:
            anchor = law['anchor']
            c1, c2 = law['cyclic']
            triplet_indices = {e.index for e in law['entries']}

            # Chimney: an entry defining the anchor that is NOT part of the triplet
            # and appears BEFORE the triplet
            min_triplet = min(triplet_indices)
            chimney_candidates = [
                e for e in self.entry_by_headword(anchor)
                if e.index < min_triplet and e.index not in triplet_indices
            ]

            # Walls: entries defining each winter word that are NOT part of the triplet
            # and appear AFTER the triplet
            max_triplet = max(triplet_indices)
            wall1_candidates = [
                e for e in self.entry_by_headword(c1)
                if e.index not in triplet_indices
            ]
            wall2_candidates = [
                e for e in self.entry_by_headword(c2)
                if e.index not in triplet_indices
            ]

            house = {
                'law': law,
                'chimney': chimney_candidates[-1] if chimney_candidates else None,
                'triplet': sorted(law['entries'], key=lambda e: e.index),
                'wall_1': {'headword': c1, 'entry': wall1_candidates[0] if wall1_candidates else None},
                'wall_2': {'headword': c2, 'entry': wall2_candidates[0] if wall2_candidates else None},
            }
            houses.append(house)

        return houses

    # ── Structural audits ──

    def audit_supported(self) -> list[Entry]:
        """Return entries that are NOT supported (have forward references)."""
        return [e for e in self.entries if not e.is_supported]

    def audit_grounded(self) -> list[str]:
        """
        Check grounding: every headword reachable from law anchors
        must trace back to at least one meaningfully-defined entry.
        Returns ungrounded headwords.
        """
        G = self.graph
        laws = self.detect_laws()
        grounded = {e.headword for e in self.entries if e.is_meaningfully_defined}

        # Walk backward from each grounded node
        grounded_closure = set(grounded)
        changed = True
        while changed:
            changed = False
            for e in self.entries:
                if e.headword not in grounded_closure:
                    if e.hw_tokens and e.hw_tokens.issubset(grounded_closure):
                        grounded_closure.add(e.headword)
                        changed = True

        # Check law anchors
        ungrounded = []
        for law in laws:
            if law['anchor'] not in grounded_closure:
                ungrounded.append(law['anchor'])

        return ungrounded

    def audit_productivity(self, roots: Optional[set[str]] = None) -> list[str]:
        """
        Check productivity: no dead reachable words.
        A headword is 'dead' if it is reachable from roots but never
        used in any later definition.

        Returns unproductive (dead) headwords.
        """
        G = self.graph
        if roots is None:
            # Default roots: law triplet headwords
            laws = self.detect_laws()
            roots = set()
            for law in laws:
                roots.update(law['trio'])

        reachable = set()
        for r in roots:
            if r in G:
                reachable.update(nx.descendants(G, r))
        reachable.update(roots & set(G.nodes()))

        # For each reachable headword, check if it's used after its first definition
        dead = []
        for hw in reachable:
            first_def = None
            for e in self.entries:
                if e.headword == hw:
                    first_def = e.index
                    break

            if first_def is None:
                continue

            used_after = False
            for e in self.entries:
                if e.index > first_def and hw in e.hw_tokens:
                    used_after = True
                    break

            if not used_after and hw not in roots:
                dead.append(hw)

        return dead

    def degree_of_law(self, law: dict, _visited: Optional[set] = None) -> int:
        """
        Compute degree of a recognised law (R-LAW-07).

        Walk from the anchor through the dependency graph to find which
        prior laws this law depends on.  Two kinds of node are excluded
        from the walk:

          1. The law's OWN cyclic terms — removed from the graph entirely,
             so the walk cannot loop through the law's own triplet edges.

          2. Other laws' cyclic terms — these are nodes whose entry-level
             degree is already determined by law membership, not by the
             content of their definitions.  There is nothing to discover
             by walking through them, so the walk records them and stops.

        The degree is then:
          1                                       if no other law's cyclic
                                                  terms were reached
          1 + max{deg(L') : L'.cyclic hit}        otherwise
        """
        if _visited is None:
            _visited = set()

        trio_key = law['trio']
        if trio_key in _visited:
            import warnings
            warnings.warn(
                f"Circular law dependency detected: degree computation "
                f"for law with anchor '{law['anchor']}' (trio={trio_key}) "
                f"re-entered itself. Visited chain: {_visited}. "
                f"Returning degree 1 as fallback.",
                stacklevel=2,
            )
            return 1
        _visited.add(trio_key)

        all_laws = self.detect_laws()

        # Collect cyclic terms of OTHER laws — these are entries whose
        # degree is settled by law membership, not by graph traversal.
        other_law_cyclic = set()
        for l in all_laws:
            if l['trio'] != law['trio']:
                other_law_cyclic.update(l['cyclic'])

        G = self.graph
        anchor = law['anchor']
        own_cyclic = set(law['cyclic'])

        # Remove own cyclic nodes entirely (prevents self-loop through triplet)
        G_pruned = G.copy()
        G_pruned.remove_nodes_from(own_cyclic)

        # BFS from anchor.  When we reach a node whose degree is already
        # determined by another law (a cyclic term), we record it but do
        # not expand through it — its degree comes from its law, not from
        # what its definition references.
        visited_nodes = set()
        frontier = [anchor]
        hit_law_cyclic = set()

        while frontier:
            node = frontier.pop(0)
            if node in visited_nodes:
                continue
            visited_nodes.add(node)

            # If this node's degree is law-determined (cyclic term of
            # another law), record it and stop — nothing further to
            # discover by walking through its definition.
            if node in other_law_cyclic and node != anchor:
                hit_law_cyclic.add(node)
                continue

            if node in G_pruned:
                for succ in G_pruned.successors(node):
                    if succ not in visited_nodes:
                        frontier.append(succ)

        if not hit_law_cyclic:
            return 1

        max_sub_degree = 0
        for l in all_laws:
            if l['trio'] != law['trio']:
                if set(l['cyclic']) & hit_law_cyclic:
                    d = self.degree_of_law(l, _visited.copy())
                    max_sub_degree = max(max_sub_degree, d)

        return 1 + max_sub_degree

    # ── Summary ──

    def summary(self) -> str:
        """One-line summary of the instance."""
        n = len(self.entries)
        hw = len(self.headword_set)
        laws = len(self.detect_laws())
        unsupported = len(self.audit_supported())
        return (
            f"VD '{self.name}': {n} entries, {hw} unique headwords, "
            f"{laws} laws detected, {unsupported} unsupported entries"
        )
