"""Engine integration tests for parameterized headwords."""

import pytest

from application import HeadwordArityError, HeadwordSignatureConflictError
from engine import Tokeniser, VDInstance
from newton import build_newton_instance


@pytest.fixture
def parameterized_vd() -> VDInstance:
    vd = VDInstance("parameterized")
    vd.append_many([
        ("velocity_t", "velocity at time t"),
        (
            "inertial-acceleration_t",
            "derivative of velocity_t at time t",
        ),
        ("inertial-mass_p", "mass of p"),
        ("two-place-acceleration_p_t", "acceleration of p at t"),
        (
            "force_p_t",
            "inertial-mass_p multiply two-place-acceleration_p_t",
        ),
    ])
    return vd


class TestParameterizedAnalyse:

    @pytest.mark.parametrize(
        "call",
        [
            "inertial-acceleration",
            "inertial-acceleration_t",
            "inertial-acceleration_3",
            "inertial-acceleration_T",
        ],
    )
    def test_bare_partial_and_complete_calls_are_demands(
        self,
        parameterized_vd,
        call,
    ):
        definiens = parameterized_vd.analyse(f"measure {call} now")
        assert definiens.headwords == [call]
        assert definiens.residual.latent == ["measure ", " now"]

    def test_multiple_actuals_form_one_outer_demand(self, parameterized_vd):
        definiens = parameterized_vd.analyse("force_Earth_3")
        assert definiens.headwords == ["force_Earth_3"]
        assert definiens.order == 1

    def test_argument_is_not_also_matched_as_a_nested_headword(self):
        vd = VDInstance("outer-call")
        vd.append_many([
            ("acting-object", "object"),
            ("canonical-force_acting-object", "force"),
        ])
        definiens = vd.analyse("canonical-force_acting-object")
        assert definiens.headwords == ["canonical-force_acting-object"]

    def test_unknown_stem_remains_inert(self, parameterized_vd):
        definiens = parameterized_vd.analyse("unknown_Earth_3")
        assert definiens.order == 0
        assert definiens.text == "unknown_Earth_3"

    def test_over_application_raises(self, parameterized_vd):
        with pytest.raises(HeadwordArityError, match="accepts 2"):
            parameterized_vd.analyse("force_Earth_3_extra")

    def test_escaped_call_remains_literal(self, parameterized_vd):
        definiens = parameterized_vd.analyse("`force_Earth_3`")
        assert definiens.order == 0
        assert definiens.text == "force_Earth_3"

    def test_definition_tokenisation_records_signature_identity(
        self,
        parameterized_vd,
    ):
        _, headwords, _ = parameterized_vd.tokeniser.tokenise_definition(
            "force_Earth_3 and inertial-acceleration_T",
            parameterized_vd.headword_set,
        )
        assert headwords == {"force_p_t", "inertial-acceleration_t"}


class TestSignatureConsistency:

    def test_redefinition_with_same_signature_is_allowed(self):
        vd = VDInstance("same-signature")
        vd.append("force_p_t", "first")
        vd.append("force_p_t", "second")
        assert [entry.index for entry in vd.entry_by_headword("force_p_t")] == [
            0,
            1,
        ]

    def test_conflicting_formals_for_one_stem_are_rejected_atomically(self):
        vd = VDInstance("conflict")
        vd.append("force_p_t", "first")
        with pytest.raises(HeadwordSignatureConflictError):
            vd.append("force_object_time", "second")
        assert len(vd.entries) == 1

    def test_conflicting_arity_for_one_stem_is_rejected_atomically(self):
        vd = VDInstance("conflict")
        vd.append("force_p_t", "first")
        with pytest.raises(HeadwordSignatureConflictError):
            vd.append("force_p", "second")
        assert len(vd.entries) == 1

    def test_bare_and_parameterized_definitions_conflict(self):
        vd = VDInstance("conflict")
        vd.append("force", "first")
        with pytest.raises(HeadwordSignatureConflictError):
            vd.append("force_p", "second")

    def test_conflicting_batch_does_not_append_any_entries(self):
        vd = VDInstance("batch-conflict")
        with pytest.raises(HeadwordSignatureConflictError):
            vd.append_many([
                ("force_p_t", "first"),
                ("force_p", "second"),
            ])
        assert vd.entries == []

    def test_over_applied_definition_does_not_append(self):
        vd = VDInstance("bad-definition")
        vd.append("force_p_t", "first")
        with pytest.raises(HeadwordArityError):
            vd.append("bad", "force_Earth_3_extra")
        assert [entry.headword for entry in vd.entries] == ["force_p_t"]


class TestExistingDictionaryCompatibility:

    def test_newton_underscore_headwords_form_valid_signatures(self):
        vd = build_newton_instance()
        assert vd.entry_by_headword("canonical-force_acting-object")
        assert vd.resolve_call("canonical-force_Earth") is not None


class TestPureTokeniserSignatureValidation:

    def test_conflicting_signature_set_is_rejected(self):
        tokeniser = Tokeniser()
        with pytest.raises(HeadwordSignatureConflictError):
            tokeniser.analyse("force", {"force_p", "force_p_t"})
