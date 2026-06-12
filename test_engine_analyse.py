"""Tests for engine.analyse — the ordered-tokenisation Definiens producer.

Covers Tokeniser.analyse (pure, takes headword_set explicitly) and
VDInstance.analyse (convenience over the instance's headword set).

Run: python -m pytest test_engine_analyse.py -v
"""

import pytest

from engine import VDInstance, Tokeniser
from definiens import Definiens
from residual import Residual


# ── Tokeniser.analyse: pure positional tokenisation ────────────────

class TestTokeniserAnalyseBasic:

    def setup_method(self):
        self.tok = Tokeniser()
        self.hw = {"mass", "particle", "force"}

    def test_returns_definiens(self):
        d = self.tok.analyse("force on a particle", self.hw)
        assert isinstance(d, Definiens)

    def test_no_matches_gives_order_zero(self):
        d = self.tok.analyse("none of these words match", self.hw)
        assert d.order == 0
        assert d.headwords == []
        assert d.text == "none of these words match"

    def test_empty_input_gives_order_zero(self):
        d = self.tok.analyse("", self.hw)
        assert d.order == 0
        assert d.text == ""
        assert d.headwords == []

    def test_single_match(self):
        d = self.tok.analyse("the mass of it", self.hw)
        assert d.order == 1
        assert d.headwords == ["mass"]
        assert d.residual.latent == ["the ", " of it"]

    def test_multiple_distinct_headwords(self):
        d = self.tok.analyse("force on a particle", self.hw)
        assert d.order == 2
        assert d.headwords == ["force", "particle"]
        assert d.render() == "{force} on a {particle}"

    def test_repeated_same_headword(self):
        d = self.tok.analyse("mass times mass", self.hw)
        assert d.order == 2
        assert d.headwords == ["mass", "mass"]
        assert d.render() == "{mass} times {mass}"


# ── Tokeniser.analyse: longest-first / overlap handling ────────────

class TestTokeniserAnalyseOverlap:

    def setup_method(self):
        self.tok = Tokeniser()
        self.hw = {"force", "net force", "particle"}

    def test_longer_headword_wins(self):
        # "net force" must match as a unit, not as "force".
        d = self.tok.analyse("the net force on a particle", self.hw)
        assert d.headwords == ["net force", "particle"]
        assert d.order == 2

    def test_short_headword_still_matches_when_alone(self):
        d = self.tok.analyse("the force on a particle", self.hw)
        assert d.headwords == ["force", "particle"]

    def test_both_match_when_both_present(self):
        d = self.tok.analyse(
            "the net force exceeds the force",
            self.hw,
        )
        assert d.headwords == ["net force", "force"]
        assert d.order == 2


# ── Tokeniser.analyse: boundary discipline ─────────────────────────

class TestTokeniserAnalyseBoundary:

    def test_substring_does_not_match(self):
        # "mass" should not match inside "amassing".
        tok = Tokeniser()
        d = tok.analyse("amassing the troops", {"mass"})
        assert d.order == 0
        assert d.headwords == []

    def test_match_at_string_start(self):
        tok = Tokeniser()
        d = tok.analyse("force is real", {"force"})
        assert d.order == 1
        assert d.residual.latent == ["", " is real"]

    def test_match_at_string_end(self):
        tok = Tokeniser()
        d = tok.analyse("apply a force", {"force"})
        assert d.order == 1
        assert d.residual.latent == ["apply a ", ""]

    def test_punctuation_boundary(self):
        tok = Tokeniser()
        d = tok.analyse("force, then mass.", {"force", "mass"})
        assert d.headwords == ["force", "mass"]


# ── Tokeniser.analyse: self-reference NOT discarded ────────────────

class TestTokeniserAnalyseSelfReference:
    """Pure tokenisation. Self-reference policy is a higher-layer concern;
    `analyse` reports every match, including ones where headword == entry."""

    def test_self_reference_appears_as_hole(self):
        tok = Tokeniser()
        d = tok.analyse("a particle is a particle", {"particle"})
        assert d.order == 2
        assert d.headwords == ["particle", "particle"]


# ── Tokeniser.analyse: original headword names preserved ───────────

class TestTokeniserAnalyseEscapes:
    """Backticks mark literal text that should not become headword holes."""

    def test_escaped_headword_is_literal_latent_text(self):
        tok = Tokeniser()
        d = tok.analyse("`mass` times force", {"mass", "force"})
        assert d.order == 1
        assert d.headwords == ["force"]
        assert d.render() == "mass times {force}"

    def test_fully_escaped_headword_gives_order_zero(self):
        tok = Tokeniser()
        d = tok.analyse("`mass`", {"mass"})
        assert d.order == 0
        assert d.text == "mass"

    def test_tokenise_definition_ignores_escaped_headword(self):
        tok = Tokeniser()
        _, hw_tokens, residue = tok.tokenise_definition(
            "`mass` and force",
            {"mass", "force"},
        )
        assert hw_tokens == {"force"}
        assert "mass" not in residue


class TestTokeniserAnalyseHeadwordNames:
    """The headwords list holds the un-normalised dictionary headword name,
    not the normalised matching form."""

    def test_case_difference_normalised_but_name_preserved(self):
        # Default tokeniser is case-insensitive; the headword in the set
        # is "Force" but the text says "force". The match succeeds, and
        # the recorded headword is the original "Force" from the set.
        tok = Tokeniser()
        d = tok.analyse("a force is felt", {"Force"})
        assert d.headwords == ["Force"]


# ── VDInstance.analyse: convenience integration ────────────────────

class TestVDInstanceAnalyse:

    def setup_method(self):
        self.v = VDInstance("test")
        self.v.append_many([
            ("mass", "numerical property of a particle"),
            ("particle", "thing that has mass"),
            ("force", "cause of acceleration of a particle"),
        ])

    def test_uses_instance_headword_set(self):
        d = self.v.analyse("the force on a particle equals mass")
        assert d.order == 3
        assert d.headwords == ["force", "particle", "mass"]

    def test_unknown_terms_pass_through_as_text(self):
        d = self.v.analyse("acceleration is unrelated to anything indexed")
        # "acceleration" is not a headword; should not match.
        assert d.order == 0
        assert "acceleration" in d.text

    def test_does_not_mutate_instance(self):
        before_n = len(self.v.entries)
        before_hw = self.v.headword_set
        _ = self.v.analyse("force and mass and particle")
        assert len(self.v.entries) == before_n
        assert self.v.headword_set == before_hw

    def test_result_is_fillable(self):
        # Confirm the produced Definiens behaves correctly under fill —
        # i.e. it really is a usable Definiens, not just a struct.
        d = self.v.analyse("force on a particle")
        assert d.order == 2
        filled = d.fill_list(["F", "p"])
        assert filled.text == "F on a p"


# ── Round-trip property ─────────────────────────────────────────────

class TestRoundTrip:
    """For any text T, analyse(T).render(hole=hw) reconstructs the
    normalised T exactly. This is the structural guarantee we want."""

    def setup_method(self):
        self.v = VDInstance("test")
        self.v.append_many([
            ("mass", "x"),
            ("particle", "x"),
            ("force", "x"),
            ("net force", "x"),
        ])

    @pytest.mark.parametrize("text", [
        "",
        "no matches at all",
        "the force on a particle",
        "the net force on a particle equals mass times acceleration",
        "force force force",
        "mass + mass + mass",
    ])
    def test_render_reconstructs_normalised_text(self, text):
        d = self.v.analyse(text)
        # Render with each hole as the headword's literal name (no braces)
        rendered = d.render(lambda i, h: h)
        normalised = self.v.tokeniser.normalise(text)
        assert rendered == normalised


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
