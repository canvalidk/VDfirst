"""Tests for parameterized headword signatures, calls, and instantiation."""

import pytest

from application import (
    HeadwordApplicationError,
    HeadwordArityError,
    HeadwordCall,
    HeadwordSignature,
    instantiate_definition,
)


class TestHeadwordSignature:

    def test_parses_stem_and_formals(self):
        signature = HeadwordSignature.parse("force_p_t")
        assert signature.stem == "force"
        assert signature.formals == ("p", "t")
        assert signature.arity == 2
        assert signature.text == "force_p_t"

    def test_bare_headword_is_arity_zero_signature(self):
        signature = HeadwordSignature.parse("mass")
        assert signature.stem == "mass"
        assert signature.formals == ()

    def test_hyphenated_formal_is_atomic(self):
        signature = HeadwordSignature.parse(
            "canonical-force_acting-object"
        )
        assert signature.stem == "canonical-force"
        assert signature.formals == ("acting-object",)

    @pytest.mark.parametrize("headword", ["force_", "_p", "force_3"])
    def test_invalid_formals_are_rejected(self, headword):
        with pytest.raises(HeadwordApplicationError):
            HeadwordSignature.parse(headword)

    def test_duplicate_formals_are_rejected(self):
        with pytest.raises(HeadwordApplicationError, match="unique"):
            HeadwordSignature.parse("pair_x_x")


class TestHeadwordCall:

    @pytest.mark.parametrize(
        ("text", "actuals"),
        [
            ("force", ()),
            ("force_Earth", ("Earth",)),
            ("force_Earth_3", ("Earth", "3")),
            ("force_reference-frame_T", ("reference-frame", "T")),
        ],
    )
    def test_parses_atomic_actuals(self, text, actuals):
        call = HeadwordCall.parse(text)
        assert call.stem == "force"
        assert call.actuals == actuals
        assert call.text == text

    @pytest.mark.parametrize("call", ["force_", "force_two words"])
    def test_invalid_actuals_are_rejected(self, call):
        with pytest.raises(HeadwordApplicationError):
            HeadwordCall.parse(call)

    def test_over_application_is_an_arity_error(self):
        signature = HeadwordSignature.parse("force_p_t")
        with pytest.raises(HeadwordArityError, match="supplies 3 arguments"):
            signature.check(HeadwordCall.parse("force_Earth_3_extra"))


class TestInstantiateDefinition:

    def setup_method(self):
        self.signature = HeadwordSignature.parse("force_p_t")
        self.definition = (
            "inertial-mass_p multiply inertial-acceleration_p_t "
            "for p at time t"
        )

    def instantiate(self, call: str) -> str:
        return instantiate_definition(
            self.definition,
            self.signature,
            HeadwordCall.parse(call),
        )

    def test_bare_call_leaves_all_formals_visible(self):
        assert self.instantiate("force") == self.definition

    def test_partial_call_replaces_prefix_and_leaves_remainder(self):
        assert self.instantiate("force_Earth") == (
            "inertial-mass_Earth multiply "
            "inertial-acceleration_Earth_t for Earth at time t"
        )

    def test_complete_call_replaces_every_standalone_occurrence(self):
        assert self.instantiate("force_Earth_3") == (
            "inertial-mass_Earth multiply "
            "inertial-acceleration_Earth_3 for Earth at time 3"
        )

    def test_actual_case_is_preserved(self):
        signature = HeadwordSignature.parse("inertial-acceleration_t")
        assert instantiate_definition(
            "derivative of velocity at time t",
            signature,
            HeadwordCall.parse("inertial-acceleration_T"),
        ) == "derivative of velocity at time T"

    def test_replacement_does_not_touch_larger_atomic_tokens(self):
        signature = HeadwordSignature.parse("clock_t")
        assert instantiate_definition(
            "t state state-t t-state t_state velocity_t particle",
            signature,
            HeadwordCall.parse("clock_T"),
        ) == "T state state-t t-state T_state velocity_T particle"

    def test_substitution_is_simultaneous(self):
        signature = HeadwordSignature.parse("pair_x_y")
        assert instantiate_definition(
            "x followed-by y",
            signature,
            HeadwordCall.parse("pair_y_Z"),
        ) == "y followed-by Z"

    def test_escaped_formal_is_left_literal(self):
        signature = HeadwordSignature.parse("clock_t")
        assert instantiate_definition(
            "t and `t`",
            signature,
            HeadwordCall.parse("clock_3"),
        ) == "3 and `t`"
