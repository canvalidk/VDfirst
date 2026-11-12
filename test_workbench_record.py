"""Portable workbench records preserve replayable decisions and claim evidence.

These use the public record API rather than restoring Demand internals.  A
successful validation establishes replay consistency, not correct arithmetic.
"""

import copy
import hashlib
import json
import re

import pytest

from workbench import apply_command, start_record, validate_record


DICTIONARY = {
    "name": "Correction choices — exact supplied dictionary",
    "entries": [
        ["force_p_t", "mass_p times acceleration_p_t"],
        ["mass_p", "supplied mass of p"],
        ["acceleration_p_t", "supplied acceleration of p at t"],
        ["force_p_t", "acceleration_p_t times mass_p"],
    ],
}


def latest(record):
    return record["snapshots"][-1]


def frame(record, identity="F"):
    return next(item for item in latest(record)["frames"] if item["id"] == identity)


def command(record, operation, frame_id="F", **fields):
    return apply_command(record, {"operation": operation, "frame_id": frame_id, **fields})


def rehash(record):
    """An editable consistency checksum must not replace engine replay checks."""
    payload = {key: value for key, value in record.items() if key != "sha256"}
    record["sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def supplied_calculation():
    record = start_record(DICTIONARY, "force_cart_0", "Cart experiment, t = 0")
    record = command(record, "expand", position=0, entry_index=0)
    record = command(record, "inject", "F/0", position=0, response="2 kg")
    return command(record, "inject", "F/0", position=1, response="5 m/s^2")


def correction_record():
    record = supplied_calculation()
    record = command(record, "reduce", "F/0", response="12 N", note="mistaken response")
    record = command(record, "reduce", response="Prediction: 12 N", note="report")
    record = command(record, "reopen", "F/0", note="revisit the product")
    record = command(record, "reduce", "F/0", response="10 N", note="new response")
    return command(record, "reduce", response="Prediction: 10 N", note="revised report")


def test_start_records_exact_dictionary_question_and_initial_snapshot():
    supplied = copy.deepcopy(DICTIONARY)
    context = "  Measured cart\nUncertainty not yet assessed: ±0.1 kg.  "
    record = start_record(supplied, "force_cart_0", context)
    assert record["format"] == "vd-trace-record"
    assert record["version"] == 1
    assert record["record_id"]
    assert re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
    assert record["producer"]["name"] == "VDfirst"
    assert record["producer"]["protocol_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", record["producer"]["engine_sha256"])
    assert record["dictionary"]["name"] == supplied["name"]
    assert record["dictionary"]["entries"] == [
        {"index": index, "headword": headword, "definition": definition}
        for index, (headword, definition) in enumerate(supplied["entries"])
    ]
    assert re.fullmatch(r"[0-9a-f]{64}", record["dictionary"]["sha256"])
    assert record["question"] == {"demand": "force_cart_0", "context": context}
    assert record["commands"] == []
    assert len(record["snapshots"]) == 1
    assert latest(record)["id"] == "S0"
    assert latest(record)["command_index"] == -1
    assert latest(record)["root_frame_id"] == "F"
    assert frame(record)["address"] == []
    assert frame(record)["parent_id"] is None
    assert frame(record)["render"] == "{force_cart_0}"
    assert not frame(record)["resolved"]
    assert latest(record)["prediction_set"]["predictions"] == []
    supplied["entries"][0][1] = "altered outside the record"
    assert record["dictionary"]["entries"][0]["definition"] == DICTIONARY["entries"][0][1]


def test_engine_candidates_preserve_duplicate_choices_and_instantiate_parameters():
    record = start_record(DICTIONARY, "force_cart_0")
    hole = frame(record)["holes"][0]
    assert hole["headword"] == "force_cart_0"
    assert hole["resolution"] is None
    assert hole["child_frame_id"] is None
    assert [(item["entry_index"], item["instantiated_definition"]) for item in hole["candidates"]] == [
        (0, "mass_cart times acceleration_cart_0"),
        (3, "acceleration_cart_0 times mass_cart"),
    ]
    assert hole["candidates"][0]["definition"] == "mass_p times acceleration_p_t"
    alternative = command(record, "expand", position=0, entry_index=3)
    assert frame(alternative, "F/0")["render"] == "{acceleration_cart_0} times {mass_cart}"
    assert frame(alternative, "F/0")["source_index"] == 3
    assert frame(alternative)["holes"][0]["source_index"] == 3
    assert frame(record)["holes"][0]["resolution"] is None


def test_recall_is_literal_while_expand_analyses_the_instantiated_definition():
    record = start_record(DICTIONARY, "force_cart_0")
    recalled = command(record, "recall", position=0, entry_index=0)
    assert frame(recalled)["render"] == "mass_cart times acceleration_cart_0"
    assert frame(recalled)["resolved"]
    assert frame(recalled)["holes"][0]["resolution"] == "recall"
    assert frame(recalled)["holes"][0]["child_frame_id"] is None
    assert len(latest(recalled)["frames"]) == 1
    assert latest(recalled)["prediction_set"]["trace_complete"]
    assert latest(recalled)["prediction_set"]["predictions"] == []
    expanded = command(record, "expand", position=0, entry_index=0)
    child = frame(expanded, "F/0")
    assert child["headwords"] == ["mass_cart", "acceleration_cart_0"]
    assert not child["resolved"]
    assert child["address"] == [0]
    assert child["parent_id"] == "F"
    assert child["via_position"] == 0
    assert not latest(expanded)["prediction_set"]["trace_complete"]


def test_supplied_input_is_analysed_and_keeps_its_exact_claim_evidence():
    record = start_record(DICTIONARY, "mass_cart")
    supplied = command(record, "inject", position=0, response="acceleration_cart_0", note="reader input")
    assert frame(supplied)["holes"][0]["resolution"] == "inject"
    assert frame(supplied, "F/0")["source_index"] is None
    assert frame(supplied, "F/0")["headwords"] == ["acceleration_cart_0"]
    assert not latest(supplied)["prediction_set"]["trace_complete"]
    claim = latest(supplied)["prediction_set"]["predictions"][0]
    assert claim["kind"] == "supplied_input"
    assert claim["evidence"]["stimulus"] == "mass_cart"
    assert claim["evidence"]["response"] == "acceleration_cart_0"
    assert claim["evidence"]["position"] == 0
    assert claim["verification"] == "unchecked"


def test_correction_preserves_mistake_but_replaces_its_current_support():
    record = correction_record()
    snapshots = record["snapshots"]
    mistaken = snapshots[5]["prediction_set"]
    reopened = snapshots[6]["prediction_set"]
    corrected = latest(record)["prediction_set"]
    assert mistaken["result"] == "Prediction: 12 N"
    assert reopened["result"] == "2 kg times 5 m/s^2"
    assert corrected["result"] == "Prediction: 10 N"
    old_claims = [item for item in corrected["predictions"] if item["evidence"]["response"] in ("12 N", "Prediction: 12 N")]
    assert len(old_claims) == 2
    assert {item["id"] for item in old_claims} <= set(corrected["historical_prediction_ids"])
    assert not ({item["id"] for item in old_claims} & set(corrected["current_prediction_ids"]))
    correction = next(item for item in corrected["predictions"] if item["evidence"]["response"] == "10 N")
    assert correction["evidence"]["stimulus"] == "2 kg times 5 m/s^2"
    assert correction["evidence"]["before"]["address"] == [0]
    assert correction["evidence"]["before"]["source_index"] == 0
    assert correction["evidence"]["before"]["headwords"] == ["mass_cart", "acceleration_cart_0"]
    assert [item["text"] for item in correction["evidence"]["before"]["arguments"]] == ["2 kg", "5 m/s^2"]
    assert correction["id"] in corrected["current_prediction_ids"]
    report = corrected["predictions"][-1]
    assert correction["event_index"] in report["evidence"]["dependencies"]
    assert frame({"snapshots": [snapshots[6]]})["reduced"] is None
    assert frame({"snapshots": [snapshots[6]]}, "F/0")["reduced"] is None
    assert corrected["dependency_selection_complete"]
    assert not corrected["coverage_complete"]
    assert all(item["verification"] == "unchecked" for item in corrected["predictions"])


def test_reducing_an_existing_overlay_retains_the_consumed_claim():
    record = start_record(DICTIONARY, "5+6")
    record = command(record, "reduce", response="11")
    record = command(record, "reduce", response="eleven")
    predictions = latest(record)["prediction_set"]
    assert predictions["predictions"][-1]["evidence"]["stimulus"] == "11"
    assert predictions["current_prediction_ids"] == [item["id"] for item in predictions["predictions"]]
    assert predictions["historical_prediction_ids"] == []


def test_clean_records_prose_change_without_replacing_holes_or_children():
    record = supplied_calculation()
    before = frame(record, "F/0")
    record = command(record, "clean", "F/0", latents=["", " multiplied by ", ""], note="wording")
    after = frame(record, "F/0")
    assert after["headwords"] == before["headwords"]
    assert after["holes"] == before["holes"]
    assert after["render"] == "2 kg multiplied by 5 m/s^2"
    change = latest(record)["prediction_set"]["predictions"][-1]
    assert change["operation"] == "clean"
    assert change["verification"] == "unchecked"


def test_json_roundtrip_validates_and_can_continue_without_changing_saved_history():
    source = supplied_calculation()
    saved = json.loads(json.dumps(source, ensure_ascii=False))
    original = copy.deepcopy(saved)
    checked = validate_record(saved)
    assert checked == source
    assert checked is not saved
    continued = command(checked, "reduce", "F/0", response="10 N")
    assert saved == original
    assert continued["record_id"] == saved["record_id"]
    assert continued["dictionary"] == saved["dictionary"]
    assert continued["producer"] == saved["producer"]
    assert continued["question"] == saved["question"]
    assert continued["commands"][:-1] == saved["commands"]
    assert continued["snapshots"][:-1] == saved["snapshots"]
    assert continued["events"][:len(saved["events"])] == saved["events"]
    assert latest(continued)["prediction_set"]["result"] == "10 N"
    assert validate_record(json.loads(json.dumps(continued))) == continued


def test_event_frame_and_snapshot_ids_are_stable_across_reopening_and_replay():
    record = correction_record()
    assert [item["id"] for item in record["events"]] == [f"event-{index}" for index in range(len(record["events"]))]
    assert [item["index"] for item in record["events"]] == list(range(len(record["events"])))
    assert [item["id"] for item in record["snapshots"]] == [f"S{index}" for index in range(len(record["snapshots"]))]
    for index, snapshot in enumerate(record["snapshots"]):
        assert snapshot["command_index"] == index - 1
        assert snapshot["event_count"] <= len(record["events"])
        for item in snapshot["frames"]:
            assert item["id"] == "F" + "".join(f"/{position}" for position in item["address"])
        for claim in snapshot["prediction_set"]["predictions"]:
            assert claim["id"] == f"P{claim['event_index']}"
            assert record["events"][claim["event_index"]]["change"] == claim["evidence"]
    ids_before = {item["id"] for item in record["snapshots"][5]["frames"]}
    assert ids_before == {item["id"] for item in latest(record)["frames"]}
    assert validate_record(record) == record


def test_validation_returns_detached_data_and_checksum_covers_question_metadata():
    source = supplied_calculation()
    returned = validate_record(source)
    returned["snapshots"][-1]["frames"][0]["render"] = "caller edit"
    assert frame(source)["render"] == "2 kg times 5 m/s^2"
    altered = copy.deepcopy(source)
    altered["question"]["context"] = "different experimental account"
    with pytest.raises(ValueError):
        validate_record(altered)


@pytest.mark.parametrize("bad_command", [
    {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": 1},
    {"operation": "expand", "frame_id": "F", "position": -1, "entry_index": 0},
    {"operation": "expand", "frame_id": "F", "position": 99, "entry_index": 0},
    {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": -1},
    {"operation": "reduce", "frame_id": "F/99", "response": "10 N"},
    {"operation": "reopen", "frame_id": "F"},
    {"operation": "reduce", "frame_id": "F", "response": ""},
    {"operation": "inject", "frame_id": "F", "position": 0, "response": "   "},
    {"operation": "reduce", "frame_id": "F", "response": "10 N", "entry_index": 0},
    {"operation": "clean", "frame_id": "F", "latents": ["wrong count"]},
    {"operation": "expand", "frame_id": "F", "position": True, "entry_index": 0},
    {"operation": "expand", "frame_id": "F", "position": 0, "entry_index": False},
    {"operation": "evaluate", "frame_id": "F", "response": "10 N"},
    {"operation": "reduce", "frame_id": "F", "response": 10},
    {"operation": "reduce", "frame_id": "F", "response": "10 N", "note": []},
    {}, None, [],
])
def test_failed_commands_leave_the_callers_record_unchanged(bad_command):
    record = start_record(DICTIONARY, "force_cart_0")
    before = copy.deepcopy(record)
    with pytest.raises(ValueError):
        apply_command(record, bad_command)
    assert record == before


def test_committed_resolution_cannot_be_overwritten():
    record = supplied_calculation()
    before = copy.deepcopy(record)
    with pytest.raises(ValueError):
        command(record, "inject", "F/0", position=0, response="3 kg")
    assert record == before


@pytest.mark.parametrize("repair_checksum", [False, True])
@pytest.mark.parametrize("target", [
    "snapshot render", "snapshot predictions", "snapshot source", "snapshot candidate",
    "event detail", "event evidence", "event id", "dictionary text", "dictionary digest",
    "command", "engine fingerprint", "missing event", "extra snapshot",
])
def test_validation_rejects_tampered_recorded_material(target, repair_checksum):
    original = correction_record()
    altered = copy.deepcopy(original)
    if target == "snapshot render":
        altered["snapshots"][-1]["frames"][0]["render"] = "forged result"
    elif target == "snapshot predictions":
        altered["snapshots"][-1]["prediction_set"]["predictions"][0]["verification"] = "verified"
    elif target == "snapshot source":
        altered["snapshots"][1]["frames"][1]["source_index"] = 3
    elif target == "snapshot candidate":
        altered["snapshots"][0]["frames"][0]["holes"][0]["candidates"][0]["instantiated_definition"] = "forged definition"
    elif target == "event detail":
        altered["events"][-1]["detail"] = "forged note"
    elif target == "event evidence":
        changed = next(item for item in altered["events"] if item["change"] is not None)
        changed["change"]["response"] = "forged response"
    elif target == "event id":
        altered["events"][-1]["id"] = "event-999"
    elif target == "dictionary text":
        altered["dictionary"]["entries"][0]["definition"] = "something else"
    elif target == "dictionary digest":
        altered["dictionary"]["sha256"] = "0" * 64
    elif target == "command":
        altered["commands"][-1]["response"] = "Prediction: 99 N"
    elif target == "engine fingerprint":
        altered["producer"]["engine_sha256"] = "0" * 64
    elif target == "missing event":
        altered["events"].pop()
    else:
        altered["snapshots"].append(copy.deepcopy(altered["snapshots"][-1]))
    if repair_checksum:
        rehash(altered)
    before = copy.deepcopy(altered)
    with pytest.raises(ValueError):
        validate_record(altered)
    assert altered == before
    assert validate_record(original) == original
    with pytest.raises(ValueError):
        command(altered, "reduce", response="another response")


@pytest.mark.parametrize("field,value", [
    ("format", "unrelated-format"), ("version", 2), ("version", True),
    ("commands", None), ("events", {}), ("snapshots", []),
    ("dictionary", []), ("question", "force_cart_0"), ("producer", None),
])
def test_validation_rejects_unsupported_versions_and_malformed_record_shape(field, value):
    record = start_record(DICTIONARY, "force_cart_0")
    record[field] = value
    rehash(record)
    with pytest.raises(ValueError):
        validate_record(record)


@pytest.mark.parametrize("dictionary,demand,context", [
    (None, "force_cart_0", ""),
    ({"name": "bad", "entries": "force := product"}, "force", ""),
    ({"name": "bad", "entries": [["force"]]}, "force", ""),
    ({"name": "bad", "entries": [["force", 10]]}, "force", ""),
    (DICTIONARY, "", ""), (DICTIONARY, "   ", ""),
    (DICTIONARY, 10, ""), (DICTIONARY, "force_cart_0", []),
])
def test_start_rejects_malformed_input(dictionary, demand, context):
    with pytest.raises(ValueError):
        start_record(dictionary, demand, context)


def test_unreasonably_large_input_is_rejected_before_it_becomes_a_record():
    with pytest.raises(ValueError):
        start_record(DICTIONARY, "force_cart_0", "x" * 10_000_000)
    record = start_record(DICTIONARY, "force_cart_0")
    before = copy.deepcopy(record)
    with pytest.raises(ValueError):
        command(record, "reduce", response="x" * 10_000_000)
    assert record == before


def test_empty_dictionary_can_record_literal_results_and_correction():
    record = start_record({"name": "Literal-only work", "entries": []}, "5+6")
    assert frame(record)["holes"] == []
    assert frame(record)["resolved"]
    assert latest(record)["prediction_set"]["trace_complete"]
    record = command(record, "reduce", response="12")
    record = command(record, "reopen")
    record = command(record, "reduce", response="11")
    predictions = latest(record)["prediction_set"]
    assert predictions["result"] == "11"
    assert len(predictions["current_prediction_ids"]) == 1
    assert len(predictions["historical_prediction_ids"]) == 1
    assert validate_record(record) == record


@pytest.mark.parametrize("location", ["entry index", "protocol version", "snapshot command index"])
def test_boolean_values_do_not_impersonate_integer_record_fields(location):
    record = start_record(DICTIONARY, "force_cart_0")
    if location == "entry index":
        record["dictionary"]["entries"][0]["index"] = False
    elif location == "protocol version":
        record["producer"]["protocol_version"] = True
    else:
        record = command(record, "expand", position=0, entry_index=0)
        record["snapshots"][1]["command_index"] = False
    rehash(record)
    with pytest.raises(ValueError):
        validate_record(record)


def test_nonfinite_and_non_json_values_are_rejected_as_record_errors():
    record = start_record(DICTIONARY, "force_cart_0")
    for invalid in [float("nan"), float("inf"), {"not", "JSON"}]:
        altered = copy.deepcopy(record)
        altered["unexpected"] = invalid
        with pytest.raises(ValueError):
            validate_record(altered)


def test_composed_render_is_bounded_even_when_each_literal_is_permitted():
    dictionary = {"name": "Long recalled fragments", "entries": [["fragment", "x" * 4000]]}
    record = start_record(dictionary, " + ".join(["fragment"] * 16))
    successful_recalls = 0
    for position in range(16):
        before = copy.deepcopy(record)
        try:
            continued = command(record, "recall", position=position, entry_index=0)
        except ValueError:
            assert successful_recalls > 0
            assert record == before
            assert validate_record(record) == record
            break
        record = continued
        successful_recalls += 1
    else:
        pytest.fail("a large composite render escaped the workbench resource bound")
