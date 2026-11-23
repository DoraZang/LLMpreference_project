"""
One table for the appendix: the 12 primary contrasts under the primary analysis and every sensitivity
analysis (S1, S3-S6), so a changed conclusion is easy to spot. No API calls; reads the contrast tables
written by analyze_main.py. S2 (EV-normalized risk premium) is a different outcome and is listed
separately for the gain/loss primary contrasts.

Usage:
  python src/sensitivity_summary.py --run main
Output:
  results/tables/<run>_sensitivity_summary.csv
"""

import argparse
import csv

from llm import ROOT

ANALYSES = [("primary", ""), ("S1 invalid included", "_S1"), ("S3 moderate p", "_moderate_p"),
            ("S3 extreme p", "_extreme_p"), ("S4 version 1", "_version1"), ("S4 version 2", "_version2"),
            ("S5 direction A", "_mixed_A"), ("S5 direction B", "_mixed_B"), ("S6 uncensored", "_uncensored")]
SHORT = {"effect as predicted": "pred", "effect opposite to prediction": "OPPOSITE",
         "no meaningful effect": "null", "inconclusive": "inconcl.", "effect (increase)": "up",
         "effect (decrease)": "down"}


def read(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="main")
    args = parser.parse_args()
    tables = ROOT / "results" / "tables"
    primary = {r["primary"]: r for r in read(tables / f"{args.run}_contrasts.csv") if r["primary"]}
    ids = sorted(primary, key=lambda x: int(x[1:]))
    rows = []
    for pid in ids:
        p = primary[pid]
        row = {"id": pid, "mode": p["mode"], "condition": p["condition"], "item_type": p["item_type"],
               "prediction": p["prediction"]}
        for name, suffix in ANALYSES:
            t = read(tables / f"{args.run}_contrasts{suffix}.csv")
            r = next((x for x in t or [] if x["primary"] == pid), None)
            row[name] = (f"{float(r['estimate_steps']):+.2f} ({SHORT.get(r['conclusion'], r['conclusion'])}, "
                         f"{r['n_items']} items)") if r else ("not run" if t is None else "-")
        if p["outcome"] == "rp_range":   # S2: same contrast with the EV-normalized risk premium (95% CI)
            t = read(tables / f"{args.run}_contrasts.csv")
            r = next((x for x in t if x["mode"] == p["mode"] and x["condition"] == p["condition"]
                      and x["item_type"] == p["item_type"] and x["outcome"] == "rp_ev"), None)
            row["S2 EV-normalized RP (95% CI)"] = (f"{float(r['estimate']):+.3f} [{float(r['ci95_low']):+.3f}, "
                                                    f"{float(r['ci95_high']):+.3f}]") if r else "-"
        else:
            row["S2 EV-normalized RP (95% CI)"] = "-"
        rows.append(row)

    out = tables / f"{args.run}_sensitivity_summary.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out.relative_to(ROOT)}")
    print("Estimate in option steps (conclusion, items); '-' = contrast not in that subset\n")
    for row in rows:
        changed = [name for name, _ in ANALYSES[1:]
                   if row[name] not in ("-", "not run") and row[name].split("(")[1].split(",")[0]
                   != row["primary"].split("(")[1].split(",")[0]]
        print(f"{row['id']:<4} {row['condition']:<18} {row['item_type']:<6} primary {row['primary']:<28} "
              f"changed in: {', '.join(changed) or 'none'}")


if __name__ == "__main__":
    main()