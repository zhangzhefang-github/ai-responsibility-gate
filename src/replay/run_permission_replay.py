"""
Permission Real Case Replay.

Reads cases from cases/permission_real/*.json, maps scope_request via adapter,
calls core_decide per round, and outputs results.
"""
import asyncio
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from ..core.gate import decide as core_decide
from .permission_adapter import (
    scope_request_to_signal,
    permission_signals_to_project_signals,
    permission_round_to_decision_request,
)

CASES_DIR = Path("cases") / "permission_real"
DEFAULT_MATRIX = "matrices/permission_demo.yaml"


async def replay_permission_case(case: dict, verbose: bool = False) -> dict:
    """
    Replay a permission case round by round.

    Returns:
        {
            "case_id": str,
            "rounds": [
                {
                    "round_index": int,
                    "scope_request": str,
                    "project_signals": list,
                    "decision": str,
                    "matrix_version": str,
                    "expected_decision": str | None,
                    "match": bool | None,
                    "trace": str | None,
                },
                ...
            ],
        }
    """
    case_id = case.get("case_id", "unknown")
    matrix_path = case.get("matrix_path") or DEFAULT_MATRIX
    rounds_data = case.get("rounds", [])

    result = {
        "case_id": case_id,
        "rounds": [],
    }

    for i, round_data in enumerate(rounds_data):
        scope_request = round_data.get("scope_request", "")
        signal = scope_request_to_signal(scope_request)
        project_signals = permission_signals_to_project_signals([signal])

        req = permission_round_to_decision_request(
            round_data,
            case_id=case_id,
            round_index=i,
            project_signals=project_signals,
            verbose=verbose,
        )

        trace_capture = io.StringIO()
        with redirect_stdout(trace_capture):
            resp = await core_decide(req, matrix_path=matrix_path)

        trace_output = trace_capture.getvalue() if verbose else None

        expected = round_data.get("expected_decision")
        predicted = resp.decision.value
        match = predicted == expected if expected is not None else None

        result["rounds"].append({
            "round_index": i,
            "scope_request": scope_request,
            "project_signals": project_signals,
            "decision": predicted,
            "matrix_version": resp.policy.matrix_version,
            "expected_decision": expected,
            "match": match,
            "trace": trace_output,
        })

    return result


def _print_round(round_result: dict, verbose: bool) -> None:
    r = round_result
    print(f"  Round {r['round_index']}:")
    print(f"    scope_request:     {r['scope_request']}")
    print(f"    project_signals:   {r['project_signals']}")
    print(f"    decision:          {r['decision']}")
    print(f"    matrix_version:    {r['matrix_version']}")
    if r["expected_decision"] is not None:
        status = "✓" if r["match"] else "✗"
        print(f"    expected_decision: {r['expected_decision']} {status}")
    if verbose and r.get("trace"):
        print(f"    trace:")
        for line in r["trace"].strip().split("\n"):
            print(f"      {line}")
    print()


async def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []

    if not case_files:
        print(f"No cases found in {CASES_DIR}")
        return

    all_results = []
    for cf in case_files:
        with open(cf, encoding="utf-8") as f:
            case = json.load(f)
        result = await replay_permission_case(case, verbose=verbose)
        all_results.append(result)

    for res in all_results:
        print(f"\n{'='*60}")
        print(f"Case: {res['case_id']}")
        print("=" * 60)
        for r in res["rounds"]:
            _print_round(r, verbose)

    total = sum(len(r["rounds"]) for r in all_results)
    with_expected = [
        (r, i)
        for r in all_results
        for i, rd in enumerate(r["rounds"])
        if rd.get("expected_decision") is not None
    ]
    correct = sum(1 for r, i in with_expected if r["rounds"][i]["match"])
    n_expected = len(with_expected)

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Total rounds: {total}")
    print(f"  With expected_decision: {n_expected}")
    print(f"  Correct: {correct}")
    if n_expected > 0:
        print(f"  Accuracy: {correct / n_expected:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
