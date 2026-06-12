"""Tests for demand graph and trace state."""

import pytest

from demand import (
    Demand,
    ExpandProvenance,
    ExpandResolution,
    InjectProvenance,
    InjectResolution,
    LiteralResolution,
    RecallResolution,
    RootProvenance,
    Trace,
    TraceEvent,
)
from definiens import Definiens
from engine import VDInstance
from residual import Residual
from simulator import Simulator


def defi(latent, headwords):
    return Definiens(Residual(latent), headwords)


def demand(latent, headwords, provenance=None):
    if provenance is None:
        provenance = RootProvenance("root")
    return Demand(defi(latent, headwords), provenance=provenance)


class TestConstruction:

    def test_order_zero_is_immediately_resolved(self):
        d = demand(["done"], [])
        assert d.open_positions == []
        assert d.is_resolved
        assert d.text() == "done"

    def test_open_positions_are_original_positions(self):
        d = demand(["", " + ", ""], ["mass", "mass"])
        assert d.open_positions == [0, 1]
        assert not d.is_resolved

    def test_headword_at_returns_parallel_headword(self):
        d = demand(["A", "B", "C"], ["x", "y"])
        assert d.headword_at(0) == "x"
        assert d.headword_at(1) == "y"

    def test_headword_at_rejects_out_of_range(self):
        d = demand(["A", "B"], ["x"])
        with pytest.raises(ValueError, match="out of range"):
            d.headword_at(2)

    def test_order_zero_rejects_position(self):
        d = demand(["done"], [])
        with pytest.raises(ValueError, match="no holes"):
            d.resolve_recall(0, "x", source_index=1)


class TestRecallResolution:

    def test_recall_closes_position_and_renders_raw_text(self):
        d = demand(["force is ", ""], ["net-force"])
        d.resolve_recall(0, "mass times acceleration", source_index=7)
        assert d.open_positions == []
        assert d.is_resolved
        assert d.text() == "force is mass times acceleration"
        assert d.resolutions[0] == RecallResolution(
            "mass times acceleration",
            7,
        )

    def test_recall_can_render_compressed_headword(self):
        d = demand(["force is ", ""], ["net-force"])
        d.resolve_recall(
            0,
            "mass times acceleration",
            source_index=7,
            compressed=True,
        )
        assert d.text() == "force is net-force"

    def test_recall_double_resolution_raises(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=2)
        with pytest.raises(ValueError, match="already resolved"):
            d.resolve_recall(0, "4 kg", source_index=3)

    def test_recall_out_of_range_raises(self):
        d = demand(["", ""], ["mass"])
        with pytest.raises(ValueError, match="out of range"):
            d.resolve_recall(1, "3 kg", source_index=2)


class TestExpandResolution:

    def test_expand_links_child_and_renders_child_text(self):
        parent = demand(["because ", ""], ["force"])
        child = demand(
            ["mass times acceleration"],
            [],
            provenance=ExpandProvenance(3),
        )
        parent.resolve_expand(0, child, source_index=3)

        assert parent.children() == {0: child}
        assert child.parent is parent
        assert parent.is_resolved
        assert parent.text() == "because mass times acceleration"
        assert isinstance(parent.resolutions[0], ExpandResolution)

    def test_expand_parent_waits_for_child_to_resolve(self):
        parent = demand(["because ", ""], ["force"])
        child = demand(["", " times ", ""], ["mass", "acceleration"])
        parent.resolve_expand(0, child, source_index=3)

        assert not parent.is_resolved
        assert parent.text() == "because {mass} times {acceleration}"

        child.resolve_recall(0, "2 kg", source_index=10)
        child.resolve_recall(1, "5 m/s^2", source_index=11)
        assert parent.is_resolved
        assert parent.text() == "because 2 kg times 5 m/s^2"

    def test_expand_can_render_compressed_headword(self):
        parent = demand(["because ", ""], ["force"])
        child = demand(["mass times acceleration"], [])
        parent.resolve_expand(
            0,
            child,
            source_index=3,
            compressed=True,
        )
        assert parent.text() == "because force"


class TestInjectResolution:

    def test_inject_links_child_and_renders_child_text(self):
        parent = demand(["given ", ""], ["mass"])
        child = demand(
            ["2.7 kg"],
            [],
            provenance=InjectProvenance("2.7 kg"),
        )
        parent.resolve_inject(0, child)

        assert parent.children() == {0: child}
        assert child.parent is parent
        assert parent.is_resolved
        assert parent.text() == "given 2.7 kg"
        assert isinstance(parent.resolutions[0], InjectResolution)

    def test_inject_can_render_abbreviation_when_compressed(self):
        parent = demand(["assume ", ""], ["string"])
        child = demand(["treated as inextensible"], [])
        parent.resolve_inject(
            0,
            child,
            compressed=True,
            abbreviation="inextensible string",
        )
        assert parent.text() == "assume inextensible string"

    def test_inject_compressed_defaults_to_original_headword(self):
        parent = demand(["assume ", ""], ["string"])
        child = demand(["treated as inextensible"], [])
        parent.resolve_inject(0, child, compressed=True)
        assert parent.text() == "assume string"


class TestLiteralResolution:

    def test_literal_resolution_closes_position_and_renders_text(self):
        d = demand(["", " times ", ""], ["mass", "acceleration"])
        d.resolve_literal(0, "mass", inert=True, source="flatten")

        assert d.open_positions == [1]
        assert d.text() == "mass times {acceleration}"
        assert d.resolutions[0] == LiteralResolution(
            text="mass",
            inert=True,
            source="flatten",
        )

    def test_inert_literal_escapes_for_reanalysis(self):
        d = demand(["", " times ", ""], ["mass", "acceleration"])
        d.resolve_literal(0, "mass", inert=True, source="flatten")
        d.resolve_literal(
            1,
            "acceleration",
            inert=True,
            source="flatten",
        )

        assert d.text() == "mass times acceleration"
        assert d.escaped_text() == "`mass` times `acceleration`"


class TestUnresolveAndCompression:

    def test_unresolve_reopens_recall_position(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=5)
        d.unresolve(0)
        assert d.open_positions == [0]
        assert d.text() == "{mass}"

    def test_unresolve_orphans_expand_child(self):
        parent = demand(["", ""], ["force"])
        child = demand(["done"], [])
        parent.resolve_expand(0, child, source_index=3)
        parent.unresolve(0)
        assert child.parent is None
        assert parent.children() == {}

    def test_unresolve_orphans_inject_child(self):
        parent = demand(["", ""], ["mass"])
        child = demand(["2 kg"], [])
        parent.resolve_inject(0, child)
        parent.unresolve(0)
        assert child.parent is None

    def test_unresolve_open_position_raises_key_error(self):
        d = demand(["", ""], ["mass"])
        with pytest.raises(KeyError):
            d.unresolve(0)

    def test_set_compression_replaces_recall_resolution(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=5)
        d.set_compression(0, True)
        assert d.text() == "mass"

    def test_set_compression_replaces_expand_resolution(self):
        parent = demand(["", ""], ["force"])
        child = demand(["mass times acceleration"], [])
        parent.resolve_expand(0, child, source_index=3)
        parent.set_compression(0, True)
        assert parent.text() == "force"

    def test_set_compression_replaces_inject_resolution(self):
        parent = demand(["", ""], ["string"])
        child = demand(["treated as inextensible"], [])
        parent.resolve_inject(0, child)
        parent.set_compression(0, True, abbreviation="inextensible string")
        assert parent.text() == "inextensible string"

    def test_set_compression_open_position_raises_key_error(self):
        d = demand(["", ""], ["mass"])
        with pytest.raises(KeyError):
            d.set_compression(0, True)


class TestMixedRendering:

    def test_mixed_resolutions_and_open_positions_render_together(self):
        d = demand(["A ", " B ", " C ", ""], ["x", "y", "z"])
        child = demand(["child"], [])
        d.resolve_recall(0, "raw-x", source_index=1)
        d.resolve_expand(2, child, source_index=3)

        assert d.open_positions == [1]
        assert not d.is_resolved
        assert d.text() == "A raw-x B {y} C child"


class TestAncestorCycle:

    def test_ancestor_cycle_none_when_unique(self):
        parent = demand(["", ""], ["force"])
        child = demand(["", ""], ["mass"])
        parent.resolve_expand(0, child, source_index=1)
        assert child.ancestor_cycle(0) is None

    def test_ancestor_cycle_finds_open_ancestor(self):
        parent = demand(["", " plus ", ""], ["force", "force"])
        child = demand(["", ""], ["force"])
        parent.resolve_expand(0, child, source_index=1)
        assert child.ancestor_cycle(0) is parent

    def test_ancestor_cycle_skips_resolved_ancestor(self):
        parent = demand(["", " then ", ""], ["force", "mass"])
        child = demand(["", ""], ["force"])
        parent.resolve_expand(0, child, source_index=1)
        assert child.ancestor_cycle(0) is None

    def test_ancestor_cycle_returns_nearest(self):
        grand = demand(["", " A ", ""], ["mass", "force"])
        mid = demand(["", " B ", ""], ["mass", "force"])
        leaf = demand(["", ""], ["force"])
        grand.resolve_expand(0, mid, source_index=1)
        mid.resolve_expand(0, leaf, source_index=2)
        assert leaf.ancestor_cycle(0) is mid

    def test_ancestor_cycle_ignores_siblings(self):
        root = demand(["", " and ", ""], ["force", "force"])
        left = demand(["", ""], ["force"])
        right = demand(["", ""], ["force"])
        root.resolve_expand(0, left, source_index=1)
        root.resolve_expand(1, right, source_index=2)
        assert right.ancestor_cycle(0) is None

    def test_ancestor_cycle_bad_position_raises(self):
        d = demand(["", ""], ["mass"])
        with pytest.raises(ValueError, match="out of range"):
            d.ancestor_cycle(1)


class TestReduction:

    def test_set_reduction_overrides_text(self):
        d = demand(["", " * ", ""], ["mass", "mass"])
        d.resolve_recall(0, "5", source_index=1)
        d.resolve_recall(1, "3", source_index=1)
        d.set_reduction("15")
        assert d.text() == "15"

    def test_set_reduction_rejects_open_hole(self):
        d = demand(["", " * ", ""], ["mass", "mass"])
        d.resolve_recall(0, "5", source_index=1)
        with pytest.raises(ValueError, match="not fully resolved"):
            d.set_reduction("15")

    def test_set_reduction_rejects_open_descendant(self):
        parent = demand(["", ""], ["force"])
        child = demand(["", ""], ["mass"])
        parent.resolve_expand(0, child, source_index=1)
        with pytest.raises(ValueError, match="not fully resolved"):
            parent.set_reduction("done")

    def test_reduced_propagates_to_parent_render(self):
        parent = demand(["F = ", ""], ["force"])
        child = demand(["5 * 3"], [])
        parent.resolve_expand(0, child, source_index=1)
        child.set_reduction("15")
        assert parent.text() == "F = 15"

    def test_compression_masks_child_reduction(self):
        parent = demand(["F = ", ""], ["force"])
        child = demand(["5 * 3"], [])
        parent.resolve_expand(0, child, source_index=1, compressed=True)
        child.set_reduction("15")
        assert parent.text() == "F = force"

    def test_clear_reduction_restores_full_render(self):
        d = demand(["", " * ", ""], ["mass", "mass"])
        d.resolve_recall(0, "5", source_index=1)
        d.resolve_recall(1, "3", source_index=1)
        d.set_reduction("15")
        d.clear_reduction()
        assert d.text() == "5 * 3"

    def test_unresolve_clears_reduction_up_chain(self):
        root = demand(["", ""], ["force"])
        mid = demand(["", ""], ["mass"])
        leaf = demand(["3 kg"], [])
        root.resolve_expand(0, mid, source_index=1)
        mid.resolve_expand(0, leaf, source_index=2)
        leaf.set_reduction("3000 g")
        mid.set_reduction("3 kg exactly")
        root.set_reduction("done")

        mid.unresolve(0)

        assert mid.reduced is None
        assert root.reduced is None
        assert leaf.reduced == "3000 g"
        assert leaf.parent is None

    def test_reduction_does_not_affect_is_resolved(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=1)
        assert d.is_resolved
        d.set_reduction("3 kg")
        assert d.is_resolved
        d.clear_reduction()
        assert d.is_resolved

    def test_reduction_does_not_affect_worklist(self):
        root = demand(["", " and ", ""], ["force", "mass"])
        child = demand(["done"], [])
        root.resolve_expand(0, child, source_index=1)
        trace = Trace(root=root, active=root)
        child.set_reduction("finished")
        assert trace.worklist == [(root, 1)]

    def test_escaped_text_honours_reduction(self):
        parent = demand(["F = ", ""], ["force"])
        child = demand(["", " * ", ""], ["mass", "mass"])
        parent.resolve_expand(0, child, source_index=1)
        child.resolve_literal(0, "5", inert=True, source="flatten")
        child.resolve_literal(1, "3", inert=True, source="flatten")
        child.set_reduction("15")

        assert parent.text() == "F = 15"
        assert parent.escaped_text() == "F = 15"
        child.clear_reduction()
        assert parent.escaped_text() == "F = `5` * `3`"


class TestCleanup:

    def test_set_latents_rewrites_render(self):
        d = demand(["", " times ", ""], ["mass", "acceleration"])
        d.set_latents(["", " multiplied by ", ""])
        assert d.text() == "{mass} multiplied by {acceleration}"

    def test_set_latents_arity_mismatch_raises(self):
        d = demand(["", " times ", ""], ["mass", "acceleration"])
        with pytest.raises(ValueError, match="expected 3 latents"):
            d.set_latents(["", ""])

    def test_set_latents_preserves_headwords_and_resolutions(self):
        d = demand(["", " times ", ""], ["mass", "acceleration"])
        d.resolve_recall(0, "2 kg", source_index=0)
        d.set_latents(["the ", " by ", " value"])
        assert d.definiens.headwords == ["mass", "acceleration"]
        assert d.open_positions == [1]
        assert d.text() == "the 2 kg by {acceleration} value"

    def test_set_latents_marks_cleaned(self):
        d = demand(["done"], [])
        assert not d.cleaned
        d.set_latents(["all done"])
        assert d.cleaned

    def test_clean_recall_text_rewrites_render(self):
        d = demand(["force is ", ""], ["net-force"])
        d.resolve_recall(0, "mass times acceleration", source_index=7)
        d.clean_recall_text(0, "the product of mass and acceleration")
        assert d.text() == (
            "force is the product of mass and acceleration"
        )
        assert d.resolutions[0].source_index == 7

    def test_clean_recall_text_marks_position_cleaned(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=2)
        d.clean_recall_text(0, "three kilograms")
        assert d.cleaned_recalls == {0}

    def test_clean_recall_text_rejects_non_recall(self):
        d = demand(["", ""], ["force"])
        child = demand(["done"], [])
        d.resolve_expand(0, child, source_index=3)
        with pytest.raises(ValueError, match="not a recall"):
            d.clean_recall_text(0, "x")

    def test_clean_recall_text_open_position_raises_key_error(self):
        d = demand(["", ""], ["mass"])
        with pytest.raises(KeyError):
            d.clean_recall_text(0, "x")


class TestDegree:

    def test_degree_counts_open_holes_in_subtree(self):
        root = demand(["", " and ", ""], ["force", "mass"])
        child = demand(["", " times ", ""], ["mass", "acceleration"])
        root.resolve_expand(0, child, source_index=1)
        assert root.degree == 3
        assert child.degree == 2

    def test_degree_zero_iff_resolved(self):
        d = demand(["", ""], ["mass"])
        assert d.degree == 1
        assert not d.is_resolved
        d.resolve_recall(0, "3 kg", source_index=1)
        assert d.degree == 0
        assert d.is_resolved

    def test_degree_ignores_reduction_overlays(self):
        d = demand(["", ""], ["mass"])
        d.resolve_recall(0, "3 kg", source_index=1)
        d.set_reduction("3 kg")
        assert d.degree == 0


class TestTrace:

    def test_start_bootstraps_root_from_simulator(self):
        v = VDInstance("small")
        v.append_many([
            ("mass", "amount of matter"),
            ("force", "mass times acceleration"),
        ])
        trace = Trace.start(Simulator(v), "find force")

        assert trace.active is trace.root
        assert trace.root.provenance == RootProvenance("find force")
        assert trace.root.definiens.headwords == ["force"]
        assert trace.worklist == [(trace.root, 0)]
        assert not trace.is_complete
        assert trace.events == [
            TraceEvent("trace", "started from 'find force'")
        ]

    def test_start_with_order_zero_text_is_complete(self):
        v = VDInstance("empty")
        trace = Trace.start(Simulator(v), "plain text")
        assert trace.is_complete
        assert trace.worklist == []

    def test_up_from_root_raises(self):
        root = demand(["", ""], ["mass"])
        trace = Trace(root=root, active=root)
        with pytest.raises(ValueError, match="already at root"):
            trace.up()

    def test_down_to_open_position_raises(self):
        root = demand(["", ""], ["mass"])
        trace = Trace(root=root, active=root)
        with pytest.raises(ValueError, match="no child"):
            trace.down(0)

    def test_down_to_recalled_position_raises(self):
        root = demand(["", ""], ["mass"])
        root.resolve_recall(0, "3 kg", source_index=4)
        trace = Trace(root=root, active=root)
        with pytest.raises(ValueError, match="no child"):
            trace.down(0)

    def test_down_and_up_move_active_focus(self):
        root = demand(["", ""], ["force"])
        child = demand(["", ""], ["mass"])
        root.resolve_expand(0, child, source_index=3)
        trace = Trace(root=root, active=root)

        trace.down(0)
        assert trace.active is child
        trace.up()
        assert trace.active is root

    def test_worklist_is_depth_first_left_to_right(self):
        root = demand(["", " and ", ""], ["force", "mass"])
        left = demand(["", " / ", ""], ["net-force", "inertial-mass"])
        right = demand(["", ""], ["kilogram"])
        root.resolve_expand(0, left, source_index=1)
        root.resolve_expand(1, right, source_index=2)
        trace = Trace(root=root, active=root)

        assert trace.worklist == [
            (left, 0),
            (left, 1),
            (right, 0),
        ]

    def test_trace_completion_tracks_root_resolution(self):
        root = demand(["", ""], ["mass"])
        trace = Trace(root=root, active=root)
        assert not trace.is_complete
        root.resolve_recall(0, "3 kg", source_index=1)
        assert trace.is_complete

    def test_flatten_active_resolves_all_open_positions(self):
        root = demand(["", " times ", ""], ["mass", "acceleration"])
        trace = Trace(root=root, active=root)

        positions = trace.flatten_active()

        assert positions == [0, 1]
        assert trace.active is root
        assert root.open_positions == []
        assert root.text() == "mass times acceleration"
        assert root.escaped_text() == "`mass` times `acceleration`"
        assert trace.is_complete
        assert trace.events == [
            TraceEvent("flatten", "active positions 0, 1")
        ]

    def test_flatten_active_position_resolves_one_position(self):
        root = demand(["", " times ", ""], ["mass", "acceleration"])
        trace = Trace(root=root, active=root)

        assert trace.flatten_active_position(1) == [1]
        assert root.open_positions == [0]
        assert root.text() == "{mass} times acceleration"
        assert trace.events == [
            TraceEvent("flatten", "active position 1")
        ]

    def test_cancel_style_unresolve_reopens_parent_and_orphans_child(self):
        root = demand(["", ""], ["force"])
        child = demand(["done"], [])
        root.resolve_expand(0, child, source_index=3)
        trace = Trace(root=root, active=child)

        trace.up()
        trace.active.unresolve(0)

        assert trace.active is root
        assert child.parent is None
        assert trace.worklist == [(root, 0)]
