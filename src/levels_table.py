"""
Print the mean level of each outcome per condition and reasoning mode, from
results/tables/<run>_levels.csv (written by analyze_main.py). No API calls.

Columns per mode:
  gain RP, loss RP : range-normalized risk premium (positive = risk-averse)
  mixed ratio      : geometric mean loss-aversion ratio
  valid g/l/m      : share of valid responses for gain / loss / mixed items

Usage: python src/levels_table.py --run main
"""

import argparse
import csv

from llm import ROOT

CONDITION_ORDER = ["baseline", "direct_risk_tech", "direct_risk_plain", "oneshot_gain",
                   "direct_loss_tech", "direct_loss_plain", "oneshot_loss", "oneshot_mixed", "cot", "ev_hint"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="main")
    parser.add_argument("--s1", action="store_true", help="read the S1 sensitivity analysis levels")
    args = parser.parse_args()
    path = ROOT / "results" / "tables" / f"{args.run}_levels{'_S1' if args.s1 else ''}.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    level = {(r["mode"], r["condition"], r["item_type"], r["outcome"]): r for r in rows}

    def cell(mode, cond, item_type, outcome):
        r = level.get((mode, cond, item_type, outcome))
        if r is None:
            return "-"
        if outcome == "log_ratio":
            return r["ratio_geometric_mean"]
        if outcome == "valid":
            return f"{float(r['mean']):.0%}"
        return f"{float(r['mean']):+.3f}"

    for mode in ["none", "high"]:
        print(f"\nReasoning effort: {mode}")
        print(f"{'condition':<19}{'gain RP':>9}{'loss RP':>9}{'mixed ratio':>13}{'valid g/l/m':>18}")
        for cond in CONDITION_ORDER:
            if not any(k[0] == mode and k[1] == cond for k in level):
                continue
            valid = "/".join(cell(mode, cond, t, "valid") for t in ["gain", "loss", "mixed"])
            print(f"{cond:<19}{cell(mode, cond, 'gain', 'rp_range'):>9}{cell(mode, cond, 'loss', 'rp_range'):>9}"
                  f"{cell(mode, cond, 'mixed', 'log_ratio'):>13}{valid:>18}")


if __name__ == "__main__":
    main()