"""Compare the two recorded Atwood traces mechanically, for answer p.

- The reconciled trace: handtrace_example_atwood.py (source ATWOOD_WORKED_TRACE_2026-11-08.md).
- The coupled-constraint trace: handtrace_example_atwood_cc.py (source
  ATWOOD_COUPLED_CONSTRAINT_WORKED_TRACE_2026-11-08.md).

Both are rebuilt and their ledgers for p are compared through the CC
encoding's NAME_MAP (each CC premise named against the reconciled one):
placement (member, pruned, out), status, and the checked verdicts. Every
countermodel of the reconciled trace whose names also exist in the CC trace
is re-run there, so a disagreement in verdict is found by the checker, not
by reading.

Run: python handtrace_example_atwood_compare.py   (prints Markdown)
"""

from __future__ import annotations

import sys

import handtrace_example_atwood as REC
import handtrace_example_atwood_cc as CC
from handtrace import Trace, TraceError, frac
from handtrace_example_atwood_statuses import P_STATUSES

LABEL = "p"


def placements(t: Trace, label: str = LABEL) -> dict[str, dict]:
    """name -> {'place', 'status', 'check', 'kind'} for every INPUT, as the ledger of label sorts it."""
    led = t.ledger(label)
    out = {}
    for place, key in (("member", "commitments"), ("pruned", "pruned"), ("out", "not_in_answer")):
        for c in led[key]:
            out[c["name"]] = {"place": place, "status": c["status"], "check": c.get("check", ""), "kind": c["kind"]}
    return out


def _names(spec: dict) -> list[str]:
    return list(spec.get("replace", {})) + list(spec.get("remove", []))


def _cc_counterparts(name: str, cc_place: dict) -> list[str]:
    """The CC premises that may carry a reconciled premise: the same name, else every NAME_MAP row naming it."""
    if name in cc_place and cc_place[name]["place"] != "out":
        return [name]
    return [cc_name for cc_name, (rec_names, _rel, _why) in CC.NAME_MAP.items()
            if rec_names and name in rec_names.split("+") and cc_place.get(cc_name, {}).get("place") not in (None, "out")]


def transfer(rec: Trace, cc: Trace, label: str = LABEL) -> list[dict]:
    """Re-run each reconciled countermodel in the CC trace, against the CC premise that carries the reconciled
    one, where every relation or value it replaces exists there. A relation it only removes and the CC lacks is
    skipped: there is nothing to remove. 'same' is None when nothing could be run."""
    rels, vals = cc._premise_system(label)
    cc_place = placements(cc, label)
    rows = []
    for name, (status, _cm, _note, check) in P_STATUSES.items():
        if "entailed_by" in check or check.get("drop_dependents"):
            continue
        row = {"premise": name, "status": status, "cc_premise": "", "same": None, "outside": [],
               "rec": rec.check_countermodel(name, answer=label, **check)["summary"]}
        have = lambda n: n in rels or n in vals  # noqa: E731
        spec = {**check, "remove": [n for n in check.get("remove", []) if have(n)]}
        changed = list(check.get("replace", {})) + spec["remove"]
        targets = _cc_counterparts(name, cc_place)
        if not targets:
            row["cc"] = "no CC premise carries it"
        elif not changed:
            row["cc"], row["cc_premise"] = "nothing to transfer (empty countermodel)", targets[0]
        elif not all(have(n) for n in changed):
            missing = [n for n in changed if not have(n)]
            row["cc"] = f"not transferable: the CC trace has no relation or value {', '.join(missing)}"
            row["cc_premise"] = targets[0]
        else:
            runs = [(tg, cc.check_countermodel(tg, answer=label, **spec)) for tg in targets]
            tg, r = min(runs, key=lambda x: len(x[1]["outside"]))  # prefer a carrier the world keeps intact
            row.update(cc_premise=tg, cc=r["summary"], same=r["summary"] == row["rec"], outside=sorted(r["outside"]),
                       tried=[t for t, _ in runs if t != tg])
        rows.append(row)
    return rows


def compare() -> dict:
    rec, cc = REC.build(), CC.build()
    ra, ca = rec._answer_targets(LABEL), cc._answer_targets(LABEL)
    rp, cp = placements(rec), placements(cc)
    mapped_rec: set[str] = set()
    rows = []
    for cc_name, (rec_names, relation, reason) in CC.NAME_MAP.items():
        targets = rec_names.split("+") if rec_names else []
        mapped_rec.update(targets)
        c = cp.get(cc_name, {"place": "absent", "status": "", "check": "", "kind": ""})
        r = [(n, rp.get(n, {"place": "not an INPUT" if n in rec.bindings else "absent", "status": "", "check": ""}))
             for n in targets]
        rows.append({"cc": cc_name, "relation": relation, "reason": reason, "cc_place": c["place"],
                     "cc_status": c["status"], "cc_check": c["check"],
                     "rec": [(n, x["place"], x["status"]) for n, x in r]})
    rec_only = sorted(n for n, x in rp.items() if x["place"] != "out" and n not in mapped_rec)
    return {
        "answers": {"reconciled": {k: frac(v) for k, v in ra.items()}, "cc": {k: frac(v) for k, v in ca.items()}},
        "same_answer": ra == ca,
        "rows": rows,
        "rec_only": [(n, rp[n]["place"], rp[n]["status"]) for n in rec_only],
        "sizes": {
            "reconciled": _sizes(rec), "cc": _sizes(cc)},
        "transfer": transfer(rec, cc),
        "warnings": {"reconciled": rec.ledger(LABEL)["warnings"], "cc": cc.ledger(LABEL)["warnings"]},
    }


def _sizes(t: Trace) -> dict:
    led = t.ledger(LABEL)
    return {"members": len(led["commitments"]), "pruned": len(led["pruned"]), "step members": len(led["step_members"]),
            "theory": len(led["theory"]), "hypothesis set": len(t.hypothesis_set(LABEL)),
            "steps in p's cone": len(t.cone(LABEL)), "steps in the whole trace": len(t.steps)}


def _md(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def to_markdown(c: dict) -> str:
    L = ["# Atwood: the two recorded traces compared, for answer p", "",
         "Generated by `handtrace_example_atwood_compare.py` from `handtrace_example_atwood.py` (the reconciled "
         "trace) and `handtrace_example_atwood_cc.py` (the coupled-constraint trace). Placement is where each "
         "ledger puts the premise for p: member (in the hypothesis set), pruned (feeds p, but ENTAILED, USES or a "
         "non-world kind) or out (does not feed p).", "",
         "## Answers", "",
         f"- Reconciled: {', '.join(f'{k} = {v}' for k, v in c['answers']['reconciled'].items())}",
         f"- Coupled-constraint: {', '.join(f'{k} = {v}' for k, v in c['answers']['cc'].items())}",
         f"- Same answer: {'yes' if c['same_answer'] else 'NO'}", "",
         "## Sizes", "", "| | Reconciled | Coupled-constraint |", "|---|---|---|"]
    for k in c["sizes"]["reconciled"]:
        L.append(f"| {k} | {c['sizes']['reconciled'][k]} | {c['sizes']['cc'][k]} |")
    L += ["", "## Premises, row by row (the CC's NAME_MAP)", "",
          "| CC premise | Relation | CC placement / status | Reconciled premise(s): placement / status | Why |",
          "|---|---|---|---|---|"]
    for r in c["rows"]:
        recs = "; ".join(f"{n}: {p}" + (f" / {s}" if s else "") for n, p, s in r["rec"]) or "—"
        cc = r["cc_place"] + (f" / {r['cc_status']}" if r["cc_status"] else "")
        L.append(f"| {r['cc']} | {r['relation']} | {cc} | {_md(recs)} | {_md(r['reason'])} |")
    L += ["", "## Reconciled premises of p with no CC counterpart", ""]
    L += [f"- {n}: {p}" + (f" / {s}" if s else "") for n, p, s in c["rec_only"]] or ["- none"]
    L += ["", "## The reconciled countermodels re-run in the CC trace", "",
          "Each countermodel is run against the CC premise that carries the reconciled one (the same name, or "
          "a NAME_MAP row naming it; among several, the one the world keeps intact). 'Same verdict' compares the "
          "numbers. 'Provenance' says whether, in the CC recording, every relation the world changes rests on "
          "that premise; where not, the CC records those relations as independent of it. — means the "
          "countermodel could not be run there.", "",
          "| Premise | Status (reconciled) | Reconciled verdict | CC premise | CC verdict | Same verdict | Provenance |",
          "|---|---|---|---|---|---|---|"]
    for r in c["transfer"]:
        same = "—" if r["same"] is None else ("yes" if r["same"] else "**no**")
        prov = "—" if r["same"] is None else ("same" if not r["outside"] else
                                              f"{', '.join(r['outside'])} do not rest on {r['cc_premise']}"
                                              + (f" (nor on {', '.join(r['tried'])})" if r.get("tried") else ""))
        L.append(f"| {r['premise']} | {r['status']} | {_md(r['rec'])} | {r['cc_premise'] or '—'} | {_md(r['cc'])} | "
                 f"{same} | {_md(prov)} |")
    L += ["", "## Ledger warnings for p", "", "**Reconciled**", ""]
    L += [f"- {_md(w)}" for w in c["warnings"]["reconciled"]] or ["- none"]
    L += ["", "**Coupled-constraint**", ""]
    L += [f"- {_md(w)}" for w in c["warnings"]["cc"]] or ["- none"]
    return "\n".join(L) + "\n"


# -- tests ----------------------------------------------------------------------------------------------------


def _need_entries():
    import pytest
    if not REC.ENTRIES.exists():
        pytest.skip(f"entries file not found: {REC.ENTRIES}")


def test_both_traces_give_the_same_answer():
    _need_entries()
    c = compare()
    assert c["same_answer"] and c["answers"]["cc"] == {"a1": "49/20", "a2": "-49/20", "T": "147/4"}


def test_value_countermodels_agree_in_both_traces():
    """Changing a supplied number is the same world in both recordings, so the verdicts must match."""
    _need_entries()
    rows = {r["premise"]: r for r in compare()["transfer"]}
    for n in ("m1", "m2", "g"):
        assert rows[n]["same"], rows[n]
    # Since the provisional decisions of 10 November the reconciled trace records relations the CC lacks (the
    # free-fall reading ff_k, and relations on E-a and E-b), so those four countermodels no longer run there.
    assert {n for n, r in rows.items() if r["same"] is not None} == {
        "m1", "m2", "rin", "admG1", "admG2", "g", "pull1", "pull2", "comp1", "comp2"}


def test_no_transferred_countermodel_disagrees_in_its_numbers():
    """Wherever a reconciled countermodel can be run in the CC trace, it gives the same verdict there. Where
    the provenance differs, the CC records the changed relations as independent of the premise: its weight
    relation and P-EQV do not rest on its membership premise mem_k (the companion's rest on admG_k), and the
    upward direction of the string member in its sums rests on §1's list of idealizations, not on C_T or on
    the vertical-segment bullet Kvde (the companion's sums rest on pull_k)."""
    _need_entries()
    rows = compare()["transfer"]
    assert [r for r in rows if r["same"] is False] == []
    assert {r["premise"]: r["outside"] for r in rows if r["outside"]} == {
        "admG1": ["peqv1", "w1"], "admG2": ["peqv2", "w2"], "pull1": ["sum1"], "pull2": ["sum2"]}
    pull = next(r for r in rows if r["premise"] == "pull1")
    assert {pull["cc_premise"], *pull["tried"]} == {"meq", "Kvde"}


def test_every_cc_input_is_mapped():
    _need_entries()
    cc = CC.build()
    inputs = {s.binds[0] for s in cc.steps if s.op == "INPUT"}
    assert inputs == set(CC.NAME_MAP)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(to_markdown(compare()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
