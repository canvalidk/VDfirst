"""Tests for vd/residual.py (positional, label-free).

Run: python -m pytest test_residual.py -v
"""

import pytest
from residual import Residual


# ── Construction ────────────────────────────────────────────────────

class TestConstruction:

    def test_order_0(self):
        r = Residual(["hello"])
        assert r.order == 0
        assert r.is_done
        assert r.text == "hello"

    def test_order_1(self):
        r = Residual(["f(", ")"])
        assert r.order == 1
        assert not r.is_done

    def test_order_2(self):
        r = Residual(["", " + ", ""])
        assert r.order == 2

    def test_empty_latent_rejected(self):
        with pytest.raises(ValueError, match="at least one latent"):
            Residual([])


# ── text property ────────────────────────────────────────────────────

class TestText:

    def test_text_on_order_0(self):
        assert Residual(["done"]).text == "done"

    def test_text_on_higher_order_raises(self):
        r = Residual(["f(", ")"])
        with pytest.raises(ValueError, match="order 0"):
            _ = r.text


# ── fill: basic ──────────────────────────────────────────────────────

class TestFillBasic:

    def test_full_fill_with_strings(self):
        r = Residual(["", " + ", ""])
        out = r.fill({0: "3", 1: "4"})
        assert out.is_done
        assert out.text == "3 + 4"

    def test_empty_string_fill(self):
        r = Residual(["[", "]"])
        out = r.fill({0: ""})
        assert out.text == "[]"

    def test_no_args_is_identity(self):
        r = Residual(["f(", ")"])
        out = r.fill()
        assert out.order == 1
        assert out.latent == ["f(", ")"]

    def test_empty_dict_is_identity(self):
        r = Residual(["f(", ")"])
        out = r.fill({})
        assert out.order == 1

    def test_partial_fill_lowers_order(self):
        r = Residual(["", " + ", ""])
        out = r.fill({0: "3"})
        assert out.order == 1
        assert out.latent == ["3 + ", ""]

    def test_skip_first_fill_second(self):
        r = Residual(["", " + ", ""])
        out = r.fill({1: "4"})
        assert out.order == 1
        assert out.latent == ["", " + 4"]

    def test_two_holes_filled_independently(self):
        # the "two masses" case — no labels needed.
        r = Residual(["", " + ", ""])
        out = r.fill({0: "3 kg", 1: "5 kg"})
        assert out.text == "3 kg + 5 kg"


# ── fill_list ────────────────────────────────────────────────────────

class TestFillList:

    def test_full_fill(self):
        r = Residual(["", " + ", ""])
        out = r.fill_list(["3", "4"])
        assert out.text == "3 + 4"

    def test_short_list_fills_prefix(self):
        r = Residual(["A", "B", "C", "D"])  # order 3
        out = r.fill_list(["x", "y"])
        assert out.order == 1
        assert out.latent == ["AxByC", "D"]

    def test_none_skips_position(self):
        r = Residual(["A", "B", "C", "D"])  # order 3
        out = r.fill_list(["x", None, "z"])
        assert out.order == 1
        assert out.latent == ["AxB", "CzD"]

    def test_empty_list_is_identity(self):
        r = Residual(["f(", ")"])
        out = r.fill_list([])
        assert out.order == 1
        assert out.latent == ["f(", ")"]

    def test_long_list_raises(self):
        r = Residual(["f(", ")"])  # order 1
        with pytest.raises(ValueError, match="got 3 values"):
            r.fill_list(["a", "b", "c"])

    def test_with_sub_residuals(self):
        host = Residual(["", " + ", ""])
        sub = Residual(["g(", ")"])
        out = host.fill_list([sub, "x"])
        assert out.order == 1
        # final fill of the sub's hole
        final = out.fill_list(["y"])
        assert final.text == "g(y) + x"

    def test_empty_string_in_list_fills(self):
        # empty string is a real fill value, distinct from None (skip)
        r = Residual(["[", "][", "]"])  # order 2
        out = r.fill_list(["", "x"])
        assert out.text == "[][x]"


# ── fill: errors ─────────────────────────────────────────────────────

class TestFillErrors:

    def test_unknown_position_raises(self):
        r = Residual(["f(", ")"])
        with pytest.raises(ValueError, match="unknown position"):
            r.fill({5: "3"})

    def test_negative_position_raises(self):
        r = Residual(["f(", ")"])
        with pytest.raises(ValueError, match="unknown position"):
            r.fill({-1: "3"})

    def test_fill_on_order_0_with_position_raises(self):
        r = Residual(["done"])
        with pytest.raises(ValueError, match="no holes"):
            r.fill({0: "x"})


# ── fill: recursive ─────────────────────────────────────────────────

class TestFillRecursive:

    def test_fill_with_order_0_residual(self):
        r = Residual(["f(", ")"])
        out = r.fill({0: Residual(["3"])})
        assert out.text == "f(3)"

    def test_fill_with_higher_order_residual(self):
        host = Residual(["f(", ")"])
        sub = Residual(["g(", ")"])
        out = host.fill({0: sub})
        assert out.order == 1
        final = out.fill({0: "3"})
        assert final.text == "f(g(3))"

    def test_order_arithmetic(self):
        # host order 3, fill 2 holes (orders 0 and 2), result: 3-2+0+2=3
        host = Residual(["A", "B", "C", "D"])
        sub = Residual(["[", ",", "]"])
        out = host.fill({0: "x", 1: sub})
        assert out.order == 3

    def test_position_renumbering_after_fill(self):
        # host: A_B_C  (positions 0, 1)
        # fill position 0 with sub of order 2 ([_,_])
        # result: A[_,_]B_C  (positions 0, 1, 2)
        # fill the new positions to verify
        host = Residual(["A", "B", "C"])
        sub = Residual(["[", ",", "]"])
        out = host.fill({0: sub})
        assert out.order == 3
        final = out.fill({0: "x", 1: "y", 2: "z"})
        assert final.text == "A[x,y]Bz C"[:8] + "C"  # checking format below
        # exact: "A[x,y]BzC"
        assert final.text == "A[x,y]BzC"


# ── render ───────────────────────────────────────────────────────────

class TestRender:

    def test_render_default_shows_positions(self):
        r = Residual(["", " + ", ""])
        assert r.render() == "{0} + {1}"

    def test_render_with_callback(self):
        r = Residual(["", " + ", ""])
        names = ["mass(p)", "mass(q)"]
        assert r.render(lambda i: names[i]) == "mass(p) + mass(q)"

    def test_render_callback_can_distinguish_same_label(self):
        r = Residual(["", " + ", ""])
        # caller supplies whatever discrimination it wants
        out = r.render(lambda i: f"<hole {i}: mass>")
        assert out == "<hole 0: mass> + <hole 1: mass>"

    def test_render_order_0(self):
        # callback irrelevant for order 0
        assert Residual(["done"]).render() == "done"
        assert Residual(["done"]).render(lambda i: "X") == "done"


# ── repr ─────────────────────────────────────────────────────────────

class TestRepr:

    def test_repr_order_0(self):
        assert "text='hi'" in repr(Residual(["hi"]))

    def test_repr_higher_order(self):
        r = Residual(["f(", ")"])
        s = repr(r)
        assert "order=1" in s
        assert "f({0})" in s


# ── manual run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
