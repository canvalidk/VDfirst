"""Tests for vd/definiens.py.

Run: python -m pytest test_definiens.py -v
"""

import pytest
from residual import Residual
from definiens import Definiens


# ── Construction ────────────────────────────────────────────────────

class TestConstruction:

    def test_order_0_no_headwords(self):
        d = Definiens(Residual(["3 kg"]), [])
        assert d.order == 0
        assert d.is_done
        assert d.text == "3 kg"

    def test_order_1(self):
        d = Definiens(Residual(["mass of ", ""]), ["particle"])
        assert d.order == 1
        assert d.headwords == ["particle"]

    def test_order_2_with_duplicate_headwords(self):
        # the "two masses" case
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        assert d.order == 2
        assert d.headwords == ["mass", "mass"]

    def test_headword_count_mismatch_rejected(self):
        with pytest.raises(ValueError, match="requires 2 headwords"):
            Definiens(Residual(["", " + ", ""]), ["only_one"])

    def test_extra_headwords_rejected(self):
        with pytest.raises(ValueError, match="requires 0 headwords"):
            Definiens(Residual(["done"]), ["extra"])


# ── text ─────────────────────────────────────────────────────────────

class TestText:

    def test_text_on_done(self):
        assert Definiens(Residual(["hello"]), []).text == "hello"

    def test_text_on_open_raises(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        with pytest.raises(ValueError, match="order 0"):
            _ = d.text


# ── fill ─────────────────────────────────────────────────────────────

class TestFill:

    def test_full_fill_with_strings(self):
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        out = d.fill({0: "3 kg", 1: "5 kg"})
        assert out.is_done
        assert out.text == "3 kg + 5 kg"
        assert out.headwords == []

    def test_partial_fill_consumes_headword(self):
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        out = d.fill({0: "3 kg"})
        assert out.order == 1
        assert out.headwords == ["mass"]  # only the second remains
        assert out.residual.latent == ["3 kg + ", ""]

    def test_skip_first_fill_second(self):
        d = Definiens(Residual(["", " + ", ""]), ["a", "b"])
        out = d.fill({1: "Y"})
        assert out.order == 1
        assert out.headwords == ["a"]

    def test_no_args_is_identity(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        out = d.fill()
        assert out.order == 1
        assert out.headwords == ["x"]

    def test_fill_with_definiens(self):
        host = Definiens(Residual(["force on ", ""]), ["particle"])
        sub = Definiens(Residual(["the ", " mass"]), ["particle"])
        out = host.fill({0: sub})
        # order 1, with sub's headword promoted to remaining slot
        assert out.order == 1
        assert out.headwords == ["particle"]
        # text of the residual side
        final = out.fill({0: "p"})
        assert final.text == "force on the p mass"

    def test_fill_with_higher_order_definiens(self):
        # host: order 2; fill pos 0 with order-2 sub; result order 3
        host = Definiens(Residual(["A", "B", "C"]), ["x", "y"])
        sub = Definiens(Residual(["[", ",", "]"]), ["s", "t"])
        out = host.fill({0: sub})
        assert out.order == 3
        # headwords: sub's "s","t" replace host's "x", then host's "y" follows
        assert out.headwords == ["s", "t", "y"]

    def test_bare_residual_rejected(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        with pytest.raises(TypeError, match="bare Residual not accepted"):
            d.fill({0: Residual(["3"])})

    def test_unknown_position_raises(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        with pytest.raises(ValueError, match="unknown position"):
            d.fill({5: "3"})

    def test_fill_on_order_0_raises(self):
        d = Definiens(Residual(["done"]), [])
        with pytest.raises(ValueError, match="no holes"):
            d.fill({0: "x"})


# ── fill_list ────────────────────────────────────────────────────────

class TestFillList:

    def test_full_fill(self):
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        out = d.fill_list(["3 kg", "5 kg"])
        assert out.text == "3 kg + 5 kg"

    def test_short_list_fills_prefix(self):
        d = Definiens(Residual(["A", "B", "C", "D"]), ["x", "y", "z"])
        out = d.fill_list(["a", "b"])
        assert out.order == 1
        assert out.headwords == ["z"]

    def test_none_skips(self):
        d = Definiens(Residual(["A", "B", "C", "D"]), ["x", "y", "z"])
        out = d.fill_list(["a", None, "c"])
        assert out.order == 1
        assert out.headwords == ["y"]

    def test_empty_list_is_identity(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        out = d.fill_list([])
        assert out.order == 1

    def test_long_list_raises(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        with pytest.raises(ValueError, match="got 3 values"):
            d.fill_list(["a", "b", "c"])

    def test_fill_list_with_definiens(self):
        d = Definiens(Residual(["", " then ", ""]), ["a", "b"])
        sub = Definiens(Residual(["X"]), [])
        out = d.fill_list([sub, "y"])
        assert out.text == "X then y"


# ── render ───────────────────────────────────────────────────────────

class TestRender:

    def test_render_default_shows_headwords(self):
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        assert d.render() == "{mass} + {mass}"

    def test_render_with_callback_can_distinguish(self):
        d = Definiens(Residual(["", " + ", ""]), ["mass", "mass"])
        out = d.render(lambda i, h: f"<{i}:{h}>")
        assert out == "<0:mass> + <1:mass>"

    def test_render_order_0(self):
        assert Definiens(Residual(["done"]), []).render() == "done"


# ── repr ─────────────────────────────────────────────────────────────

class TestRepr:

    def test_repr_done(self):
        assert "text='hi'" in repr(Definiens(Residual(["hi"]), []))

    def test_repr_open(self):
        d = Definiens(Residual(["f(", ")"]), ["x"])
        s = repr(d)
        assert "order=1" in s
        assert "f({x})" in s


# ── manual run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
