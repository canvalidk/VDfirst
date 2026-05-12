"""Tests for demand graph and trace state."""

import pytest

from demand import (
    Demand,
    ExpandProvenance,
    ExpandResolution,
    InjectProvenance,
    InjectResolution,
    RecallResolution,
    RootProvenance,
    Trace,
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
