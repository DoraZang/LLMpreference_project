"""
Break down response status by reasoning mode, condition and item type, to see WHY responses are
invalid. For dominance violations of gain/loss items, distinguishes:
  always_sure    - the sure amount was chosen in every row (pattern 111111111111)
  always_lottery - the lottery was chosen in every row (pattern 000000000000)
  other          - a single switch but a wrong endpoint
No API calls are made.

Usage: python src/status_table.py --run main
"""

import argparse
from collections import Counter, defaultdict

from analyze_main import load_results

CONDITION_ORDER = ["baseline", "direct_risk_tech", "direct_risk_plain", "oneshot_gain",
                   "direct_loss_tech", "direct_loss_plain", "oneshot_loss", "oneshot_mixed", "cot", "ev_hint"]
COLUMNS = ["valid", "non_monotonic", "always_sure", "always_lottery", "dom_other", "parse_fail"]


def category(res):
    if res["status"] != "dominance_violation":
        return res["status"]
    if res["pattern"] == "1" * 12:
        return "always_sure"
    if res["pattern"] == "0" * 12:
        return "always_lottery"
    return "dom_other"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="main")
    args = parser.parse_args()
    counts = defaultdict(Counter)
    for res in load_results(args.run):
        counts[(res["mode"], res["condition"], res["item_type"])][category(res)] += 1

    for mode in ["none", "high"]:
        for item_type in ["gain", "loss"]:
            print(f"\nReasoning effort: {mode} | {item_type} items (share of responses)")
            print(f"{'condition':<19}" + "".join(f"{c:>15}" for c in COLUMNS))
            for cond in CONDITION_ORDER:
                c = counts.get((mode, cond, item_type))
                if not c:
                    continue
                total = sum(c.values())
                print(f"{cond:<19}" + "".join(f"{c[col] / total:>15.0%}" for col in COLUMNS))


if __name__ == "__main__":
    main()