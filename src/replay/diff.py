import json
import asyncio
import argparse
from pathlib import Path
from typing import Any
from .run import replay_one, calculate_metrics

CASES_DIR = Path("cases")
REPORT_PATH = Path("replay_diff_report.md")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--cand", required=True)
    parser.add_argument("--cases", required=True)
    args = parser.parse_args()

    case_files = list(Path(args.cases).glob("*.json"))
    base_results = []
    cand_results = []
    per_case_changes = []

    for cf in case_files:
        with open(cf, encoding="utf-8") as f:
            case = json.load(f)

        base_r = await replay_one(case, args.base)
        cand_r = await replay_one(case, args.cand)

        base_results.append(base_r)
        cand_results.append(cand_r)

        changes = []
        for i, (bt, ct) in enumerate(zip(base_r["turns"], cand_r["turns"])):
            if bt["predicted"] != ct["predicted"]:
                changes.append({
                    "turn_idx": i,
                    "input": bt["input"],
                    "old_decision": bt["predicted"],
                    "new_decision": ct["predicted"]
                })

        if changes:
            per_case_changes.append({
                "case_id": base_r["case_id"],
                "changes": changes
            })

    base_metrics = calculate_metrics(base_results)
    cand_metrics = calculate_metrics(cand_results)

    decision_change_count = sum(len(c["changes"]) for c in per_case_changes)
    decision_change_rate = decision_change_count / base_metrics["total"] if base_metrics["total"] > 0 else 0

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Replay Diff Report\n\n")
        f.write(f"**Base:** {args.base}\n")
        f.write(f"**Candidate:** {args.cand}\n\n")

        f.write("## Overall Metrics\n\n")
        f.write(f"| Metric | Base | Candidate | Delta |\n")
        f.write(f"|--------|------|-----------|-------|\n")
        f.write(f"| Accuracy | {base_metrics['accuracy']:.2%} | {cand_metrics['accuracy']:.2%} | {cand_metrics['accuracy'] - base_metrics['accuracy']:+.2%} |\n")
        f.write(f"| False Accept | {base_metrics['false_accept']} | {cand_metrics['false_accept']} | {cand_metrics['false_accept'] - base_metrics['false_accept']:+d} |\n")
        f.write(f"| False Reject | {base_metrics['false_reject']} | {cand_metrics['false_reject']} | {cand_metrics['false_reject'] - base_metrics['false_reject']:+d} |\n")
        f.write(f"\n**decision_change_rate:** {decision_change_rate:.2%}\n\n")

        f.write("## Per-Case Changes\n\n")
        for cc in per_case_changes:
            f.write(f"### {cc['case_id']}\n\n")
            for ch in cc["changes"]:
                f.write(f"- Turn {ch['turn_idx']}: {ch['old_decision']} → {ch['new_decision']}\n")
                f.write(f"  - Input: \"{ch['input']}\"\n")
            f.write("\n")

        if not per_case_changes:
            f.write("No decision changes detected.\n")

    print(f"Diff report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
