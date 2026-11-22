"""
Reason analysis step 4 (exploratory, pre-registration Section 9). No API calls.

Input: the full labeling output, one row per response (results/reasons/reason_labels_<name>.csv).

Label groups used for interpretation (raw labels are always reported too):
  EV              EV
  risk averse     EV + risk averse, risk averse, and loss averse on gain / loss items
                  (on items without a gain-loss trade-off "loss averse" can only mean avoiding losses or
                  uncertainty; see notes/lab_log.md 2026-11-22)
  loss averse     loss averse on mixed items
  risk seeking, vague tradeoff
  other           shown, not interpreted (the spot check found this label unreliable; < 0.2% of responses)

Behavior that is consistent with an EV rule: the switch interval contains the expected value, i.e.
|range-normalized risk premium| <= half an option step (gain / loss) or |log ratio| <= half a ratio step
(mixed). Same half steps as the main analysis.

Outputs (results/reasons/step4/):
  t1_labels_by_cell.csv        raw label shares per mode x condition x item type
  t2_groups_vs_baseline.csv    group shares per item, condition minus baseline (same mode), item bootstrap CI
  t3_names_preference.csv      flag share; among flagged reasons, which rule is stated
  t4_behavior_by_label.csv     valid responses: mean outcome and share EV-consistent, per label
  t5_status_by_label.csv       valid / non_monotonic / dominance_violation per label
  t6_dominance_violations.csv  which rule the always-sure responses state, per cell
Exploratory: 95% CIs without multiplicity adjustment; read them as descriptive.

Usage:
  python src/reason_analysis.py
"""

import argparse
import math
import random

import pandas as pd

from analyze_main import HALF_STEP
from llm import ROOT

GROUPS = ["EV", "risk averse", "loss averse", "risk seeking", "vague tradeoff", "other"]
LABELS = ["EV", "EV + risk averse", "risk averse", "loss averse", "risk seeking", "vague tradeoff", "other"]
N_BOOT = 2000
SEED = 20261122


def group_of(label, item_type):
    if label in ("EV + risk averse", "risk averse"):
        return "risk averse"
    if label == "loss averse":
        return "loss averse" if item_type == "mixed" else "risk averse"
    return label


def outcome(row):
    """Primary behavioral outcome of a valid response (range RP or log loss-aversion ratio)."""
    if row["item_type"] == "mixed":
        return math.log(row["la_ratio"]) if row["la_ratio"] > 0 else float("nan")
    return row["risk_premium_range"]


def half_step(item_type):
    return HALF_STEP["log_ratio"] if item_type == "mixed" else HALF_STEP["rp_range"]


def shares(df, by, col, cats):
    """Row shares of the categories of col within each group of by, plus n."""
    t = pd.crosstab([df[c] for c in by], df[col]).reindex(columns=cats, fill_value=0)
    n = t.sum(axis=1)
    out = t.div(n, axis=0).round(4)
    out.insert(0, "n", n)
    return out.reset_index()


def boot_ci(diffs, rng):
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(N_BOOT))
    return means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT) - 1]


def groups_vs_baseline(df):
    """Per item: share of each group (both versions pooled); contrast = mean over items of condition minus
    baseline in the same mode; items are the resampling unit, as in the main analysis."""
    per_item = (pd.crosstab([df["mode"], df["condition"], df["item_type"], df["item_id"]], df["group"],
                            normalize="index").reindex(columns=GROUPS, fill_value=0))
    rng = random.Random(SEED)
    rows = []
    for (mode, cond, itype), sub in per_item.groupby(level=[0, 1, 2]):
        if cond == "baseline" or (mode, "baseline", itype) not in per_item.index.droplevel(3):
            continue
        base = per_item.loc[(mode, "baseline", itype)]
        this = sub.droplevel([0, 1, 2])
        common = this.index.intersection(base.index)
        for g in GROUPS:
            diffs = (this.loc[common, g] - base.loc[common, g]).tolist()
            lo, hi = boot_ci(diffs, rng)
            rows.append({"mode": mode, "condition": cond, "item_type": itype, "group": g, "n_items": len(common),
                         "share_condition": round(this.loc[common, g].mean(), 4),
                         "share_baseline": round(base.loc[common, g].mean(), 4),
                         "difference": round(sum(diffs) / len(diffs), 4),
                         "ci95_low": round(lo, 4), "ci95_high": round(hi, 4)})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default="reason_labels_main_v2_claude-haiku-5-5.csv")
    args = parser.parse_args()
    df = pd.read_csv(ROOT / "results" / "reasons" / args.labels, encoding="utf-8-sig")
    unknown = set(df["label"]) - set(LABELS)
    if unknown or df["label"].isna().any():
        raise SystemExit(f"unexpected or missing labels: {unknown}")
    df["group"] = [group_of(l, t) for l, t in zip(df["label"], df["item_type"])]
    df["flag"] = df["names_preference"].eq("yes")
    cell = ["mode", "condition", "item_type"]
    out_dir = ROOT / "results" / "reasons" / "step4"
    out_dir.mkdir(parents=True, exist_ok=True)

    t1 = shares(df, cell, "label", LABELS)
    t2 = groups_vs_baseline(df)

    flagged = df[df["flag"]]
    t3 = shares(flagged, cell, "group", GROUPS).rename(columns={"n": "n_flagged"})
    t3.insert(3, "share_flagged", (t3["n_flagged"] / t3.merge(t1, on=cell)["n"]).round(4).values)

    valid = df[df["status"] == "valid"].copy()
    valid["y"] = valid.apply(outcome, axis=1)
    valid["ev_consistent"] = [abs(y) <= half_step(t) + 1e-9 for y, t in zip(valid["y"], valid["item_type"])]
    t4 = (valid.groupby(["mode", "item_type", "label"])
          .agg(n=("y", "size"), mean_outcome=("y", "mean"), share_ev_consistent=("ev_consistent", "mean"))
          .round(4).reset_index())

    t5 = shares(df, ["item_type", "label"], "status", ["valid", "non_monotonic", "dominance_violation"])
    t6 = shares(df[df["status"] == "dominance_violation"], cell, "group", GROUPS)

    for name, t in [("t1_labels_by_cell", t1), ("t2_groups_vs_baseline", t2), ("t3_names_preference", t3),
                    ("t4_behavior_by_label", t4), ("t5_status_by_label", t5), ("t6_dominance_violations", t6)]:
        t.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)
    print(f"{len(df)} responses; tables written to {out_dir.relative_to(ROOT)}\n")
    print("Group shares, condition minus baseline (percentage points), mode none:")
    view = t2[(t2["mode"] == "none") & t2["group"].isin(["EV", "risk averse", "loss averse"])].copy()
    view["diff_pp"] = (100 * view["difference"]).round(1).astype(str) + " [" + \
        (100 * view["ci95_low"]).round(1).astype(str) + ", " + (100 * view["ci95_high"]).round(1).astype(str) + "]"
    print(view.pivot_table(index=["condition", "item_type"], columns="group", values="diff_pp",
                           aggfunc="first").to_string())
    print("\nBehavior of valid responses by stated rule (mode none):")
    print(t4[t4["mode"] == "none"].to_string(index=False))


if __name__ == "__main__":
    main()