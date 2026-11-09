"""
Where in the list does the model switch? Compares smoke-test runs (e.g. shuffled vs sorted rows).
No API calls are made.

For valid responses:
  - switch position = number of 0s before the switch in the restored (sorted) pattern
    (1-11 for a switch inside the list; 0 or 12 = no switch, mixed items only)
  - gain/loss items: relative CE position = (CE - x_low) / (x_high - x_low), in [0, 1].
    The EV sits at relative position p, so a model that compares the lottery with each sure
    amount should track p; a model that switches in the middle of the list stays near 0.5.

Usage:
  python src/position_check.py --runs smoke_test smoke_sorted --mode none
"""

import argparse
from collections import Counter
from statistics import mean

from llm import ROOT
from parse import analyze
from prompts import load_items
from smoke_report import load_records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", default=["smoke_test", "smoke_sorted"])
    parser.add_argument("--mode", default="none")
    args = parser.parse_args()
    items = {it["item_id"]: it for it in load_items()}

    for run in args.runs:
        records = [r for r in load_records(ROOT / "data" / "raw" / f"{run}.jsonl")
                   if r["reasoning_effort"] == args.mode]
        valid = []
        for r in records:
            res = analyze(items[r["item_id"]], r, r["output_text"])
            if res["status"] == "valid":
                valid.append((items[r["item_id"]], res))

        print("=" * 72)
        print(f"Run: {run} | reasoning: {args.mode} | valid responses: {len(valid)}")
        print("=" * 72)

        # Relative CE position vs p (gain/loss)
        print("Relative CE position (EV is at p):")
        print(f"{'p':>6}{'gain':>10}{'loss':>10}")
        for p in sorted({it["p_high"] for it, _ in valid if it["item_type"] != "mixed"}):
            row = f"{p:>6.1f}"
            for t in ["gain", "loss"]:
                pos = [(res["ce"] - it["x_low"]) / (it["x_high"] - it["x_low"])
                       for it, res in valid if it["item_type"] == t and it["p_high"] == p]
                row += f"{mean(pos):>10.2f}" if pos else f"{'-':>10}"
            print(row)

        # Switch position histogram
        print("\nSwitch position (number of 0s before the switch):")
        print(f"{'type':<7}" + "".join(f"{k:>4}" for k in range(13)))
        for t in ["gain", "loss", "mixed"]:
            c = Counter(res["pattern"].count("0") for it, res in valid if it["item_type"] == t)
            print(f"{t:<7}" + "".join(f"{c[k]:>4}" for k in range(13)))
        print()


if __name__ == "__main__":
    main()