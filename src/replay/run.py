import json
import asyncio
from pathlib import Path
from typing import Any
from ..core.models import DecisionRequest, Decision
from ..core.gate import decide, STRICT_ORDER

CASES_DIR = Path("cases")
REPORT_PATH = Path("replay_report.md")

async def replay_one(case: dict, matrix_path: str = "matrices/v0.1.yaml") -> dict:
    case_id = case["case_id"]
    results = {"case_id": case_id, "turns": []}

    turns = case.get("turns", [])
    if not turns:
        input_data = case["input"]
        expected = case["expected"]["decision"]
        turns = [{"input": input_data, "expected_decision": expected}]

    for turn in turns:
        input_data = turn["input"]
        expected = turn.get("expected_decision") or turn.get("expected", {}).get("decision")

        req = DecisionRequest(
            session_id=input_data.get("session_id"),
            user_id=input_data.get("user_id"),
            text=input_data["text"],
            debug=input_data.get("debug", False),
            context=input_data.get("context")
        )

        resp = await decide(req, matrix_path)
        predicted = resp.decision.value

        results["turns"].append({
            "input": input_data["text"],
            "expected": expected,
            "predicted": predicted,
            "match": predicted == expected
        })

    return results

def calculate_metrics(all_results: list) -> dict:
    total = 0
    correct = 0
    false_accept = 0
    false_reject = 0

    for r in all_results:
        for turn in r["turns"]:
            total += 1
            if turn["match"]:
                correct += 1
            else:
                exp_idx = STRICT_ORDER.index(turn["expected"])
                pred_idx = STRICT_ORDER.index(turn["predicted"])

                if pred_idx < exp_idx:
                    false_accept += 1
                else:
                    false_reject += 1

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0,
        "false_accept": false_accept,
        "false_reject": false_reject
    }

async def main():
    case_files = list(CASES_DIR.glob("*.json"))
    all_results = []

    for cf in case_files:
        with open(cf, encoding="utf-8") as f:
            case = json.load(f)
        result = await replay_one(case)
        all_results.append(result)

    metrics = calculate_metrics(all_results)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Replay Report\n\n")
        f.write(f"**Matrix:** matrices/v0.1.yaml\n\n")
        f.write("## Metrics\n\n")
        f.write(f"- Total: {metrics['total']}\n")
        f.write(f"- Correct: {metrics['correct']}\n")
        f.write(f"- Accuracy: {metrics['accuracy']:.2%}\n")
        f.write(f"- False Accept: {metrics['false_accept']}\n")
        f.write(f"- False Reject: {metrics['false_reject']}\n\n")

        f.write("## Case Results\n\n")
        for r in all_results:
            f.write(f"### {r['case_id']}\n\n")
            for t in r["turns"]:
                status = "✓" if t["match"] else "✗"
                f.write(f"- {status} Input: \"{t['input']}\"\n")
                f.write(f"  - Expected: {t['expected']}, Got: {t['predicted']}\n")
            f.write("\n")

    print(f"Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
