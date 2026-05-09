"""Tests for vd/simulator.py — inspection primitives.

Run: python -m pytest test_simulator.py -v
"""

import pytest

from engine import VDInstance
from simulator import Simulator


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def empty_sim() -> Simulator:
    return Simulator(VDInstance("empty"))


@pytest.fixture
def small_sim() -> Simulator:
    v = VDInstance("small")
    v.append_many([
        ("mass", "numerical property of a particle"),
        ("particle", "thing that has mass"),
        ("force", "cause of acceleration"),
    ])
    return Simulator(v)


@pytest.fixture
def sim_with_redefines() -> Simulator:
    v = VDInstance("redef")
    v.append_many([
        ("mass", "first definition"),         # E0
        ("particle", "thing"),                # E1
        ("mass", "second definition"),        # E2 (redefine)
        ("force", "cause of acceleration"),   # E3
        ("particle", "redefined thing"),      # E4 (redefine)
    ])
    return Simulator(v)


# ── Construction ────────────────────────────────────────────────────

class TestConstruction:

    def test_holds_instance(self, small_sim):
        assert isinstance(small_sim.instance, VDInstance)

    def test_empty_instance(self, empty_sim):
        assert empty_sim.entry_count() == 0
        assert empty_sim.headword_count() == 0
        assert empty_sim.all_headwords() == []


# ── all_headwords ───────────────────────────────────────────────────

class TestAllHeadwords:

    def test_sorted(self, small_sim):
        assert small_sim.all_headwords() == ["force", "mass", "particle"]

    def test_deduplicated_with_redefines(self, sim_with_redefines):
        assert sim_with_redefines.all_headwords() == [
            "force", "mass", "particle"
        ]

    def test_empty_dictionary(self, empty_sim):
        assert empty_sim.all_headwords() == []

    def test_returns_list_not_set(self, small_sim):
        # Sortedness is a contract; type matters for downstream code.
        assert isinstance(small_sim.all_headwords(), list)


# ── headword_count ──────────────────────────────────────────────────

class TestHeadwordCount:

    def test_distinct_count(self, small_sim):
        assert small_sim.headword_count() == 3

    def test_redefines_dont_inflate(self, sim_with_redefines):
        # 5 entries, but only 3 distinct headwords
        assert sim_with_redefines.headword_count() == 3

    def test_empty(self, empty_sim):
        assert empty_sim.headword_count() == 0

    def test_matches_all_headwords_length(self, sim_with_redefines):
        sim = sim_with_redefines
        assert sim.headword_count() == len(sim.all_headwords())


# ── entry_count ─────────────────────────────────────────────────────

class TestEntryCount:

    def test_log_length(self, small_sim):
        assert small_sim.entry_count() == 3

    def test_redefines_count_separately(self, sim_with_redefines):
        assert sim_with_redefines.entry_count() == 5

    def test_empty(self, empty_sim):
        assert empty_sim.entry_count() == 0

    def test_count_exceeds_headword_count_with_redefines(
        self, sim_with_redefines
    ):
        sim = sim_with_redefines
        assert sim.entry_count() > sim.headword_count()


# ── entry_indexes ───────────────────────────────────────────────────

class TestEntryIndexes:

    def test_single_entry_for_headword(self, small_sim):
        # build order: mass=0, particle=1, force=2
        assert small_sim.entry_indexes("mass") == [0]
        assert small_sim.entry_indexes("particle") == [1]
        assert small_sim.entry_indexes("force") == [2]

    def test_multiple_entries_for_redefined_headword(
        self, sim_with_redefines
    ):
        # mass first at 0, redefined at 2
        assert sim_with_redefines.entry_indexes("mass") == [0, 2]
        # particle first at 1, redefined at 4
        assert sim_with_redefines.entry_indexes("particle") == [1, 4]
        # force just at 3
        assert sim_with_redefines.entry_indexes("force") == [3]

    def test_unknown_headword_returns_empty(self, small_sim):
        assert small_sim.entry_indexes("not-a-headword") == []

    def test_empty_string_returns_empty(self, small_sim):
        assert small_sim.entry_indexes("") == []

    def test_indexes_in_dictionary_order(self, sim_with_redefines):
        idxs = sim_with_redefines.entry_indexes("mass")
        assert idxs == sorted(idxs)

    def test_empty_dictionary(self, empty_sim):
        assert empty_sim.entry_indexes("anything") == []


# ── entry_text ──────────────────────────────────────────────────────

class TestEntryText:

    def test_returns_definition(self, small_sim):
        assert small_sim.entry_text(0) == "numerical property of a particle"
        assert small_sim.entry_text(1) == "thing that has mass"
        assert small_sim.entry_text(2) == "cause of acceleration"

    def test_redefined_entries_distinct(self, sim_with_redefines):
        assert sim_with_redefines.entry_text(0) == "first definition"
        assert sim_with_redefines.entry_text(2) == "second definition"

    def test_out_of_range_raises(self, small_sim):
        with pytest.raises(IndexError):
            small_sim.entry_text(99)

    def test_negative_raises(self, small_sim):
        # Python lists allow negative indexing; we explicitly don't —
        # E-numbers are non-negative by convention.
        with pytest.raises(IndexError, match="non-negative"):
            small_sim.entry_text(-1)

    def test_empty_dictionary_raises(self, empty_sim):
        with pytest.raises(IndexError):
            empty_sim.entry_text(0)


# ── entry_headword ──────────────────────────────────────────────────

class TestEntryHeadword:

    def test_returns_headword(self, small_sim):
        assert small_sim.entry_headword(0) == "mass"
        assert small_sim.entry_headword(1) == "particle"
        assert small_sim.entry_headword(2) == "force"

    def test_redefined_entries_have_same_headword(
        self, sim_with_redefines
    ):
        assert sim_with_redefines.entry_headword(0) == "mass"
        assert sim_with_redefines.entry_headword(2) == "mass"

    def test_out_of_range_raises(self, small_sim):
        with pytest.raises(IndexError):
            small_sim.entry_headword(99)

    def test_negative_raises(self, small_sim):
        with pytest.raises(IndexError, match="non-negative"):
            small_sim.entry_headword(-1)


# ── Non-mutation ────────────────────────────────────────────────────

class TestNonMutation:
    """Inspection primitives must not mutate the underlying instance."""

    def test_all_headwords_does_not_mutate(self, small_sim):
        before = small_sim.entry_count()
        before_set = set(small_sim.instance.headword_set)
        _ = small_sim.all_headwords()
        assert small_sim.entry_count() == before
        assert set(small_sim.instance.headword_set) == before_set

    def test_entry_indexes_does_not_mutate(self, small_sim):
        before = small_sim.entry_count()
        _ = small_sim.entry_indexes("mass")
        _ = small_sim.entry_indexes("not-a-headword")
        assert small_sim.entry_count() == before

    def test_entry_text_does_not_mutate(self, small_sim):
        before = small_sim.entry_count()
        _ = small_sim.entry_text(0)
        assert small_sim.entry_count() == before


# ── Round-trip property ─────────────────────────────────────────────

class TestRoundTrip:
    """For any valid index i: i ∈ entry_indexes(entry_headword(i))."""

    def test_index_round_trip_small(self, small_sim):
        for i in range(small_sim.entry_count()):
            hw = small_sim.entry_headword(i)
            assert i in small_sim.entry_indexes(hw)

    def test_index_round_trip_with_redefines(self, sim_with_redefines):
        for i in range(sim_with_redefines.entry_count()):
            hw = sim_with_redefines.entry_headword(i)
            assert i in sim_with_redefines.entry_indexes(hw)

    def test_indexes_round_trip(self, sim_with_redefines):
        # For every headword: every index returned by entry_indexes
        # round-trips via entry_headword.
        sim = sim_with_redefines
        for hw in sim.all_headwords():
            for i in sim.entry_indexes(hw):
                assert sim.entry_headword(i) == hw


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
