"""
Main analysis, implementing docs/preregistration.md (Sections 3-6). No API calls are made.

Steps:
  1. Parse every successful response of the run (parse.analyze).
  2. Per-prompt value: mean outcome over valid responses for each item x version x condition x mode.
  3. Per-item value: mean of the two versions; an item is used in a contrast only if both versions have
     at least MIN_VALID valid responses in both conditions compared.
  4. Contrast: per-item difference (condition - baseline) in the same mode, averaged over items.
  5. Item-level bootstrap (N_BOOT resamples): 95% CI for every contrast, plus a Bonferroni-adjusted CI
     (1 - 0.05/12) for the 12 pre-registered primary contrasts.
  6. Decision rule with the smallest effect of interest (half an option step).

Outcomes:
  gain/loss: range-normalized risk premium (primary) and EV-normalized risk premium (secondary)
  mixed:     log loss-aversion ratio (reported back as a ratio)
  valid:     share of valid responses (per item: mean over both versions)

Outputs:
  results/tables/<run>_contrasts.csv   every contrast with CIs and conclusion
  results/tables/<run>_levels.csv      mean level of every outcome per condition and mode
  The primary contrasts are also printed.

Sensitivity analysis S1 (--include-invalid): non-monotonic and dominance-violating responses are
not excluded; each gets the switch point of the closest consistent pattern (fewest changed rows; if
several are equally close, their values are averaged). Parse failures stay excluded. Outputs are
written with the suffix _S1, so the pre-registered primary results are not overwritten.

Usage:
  python src/analyze_main.py --run main
  python src/analyze_main.py --run main --include-invalid      # sensitivity analysis S1
"""

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from statistics import mean

from llm import ROOT
from parse import analyze
from prompts import load_items

MIN_VALID = 3                 # valid responses needed per version (pre-registration, Section 4)
N_BOOT = 10_000
SEED = 20261115
STEP = {"rp_range": 1 / 11, "rp_ev": None, "log_ratio": math.log(10) / 11, "valid": None}
HALF_STEP = {k: (v / 2 if v else None) for k, v in STEP.items()}
OUTCOMES = {"gain": ["rp_range", "rp_ev", "valid"], "loss": ["rp_range", "rp_ev", "valid"],
            "mixed": ["log_ratio", "valid"]}

# Primary contrasts (pre-registration, Section 6): (id, mode, condition, item type, outcome, prediction)
PRIMARY = [
    ("P1", "none", "direct_risk_tech", "gain", "rp_range", "up"),
    ("P2", "none", "direct_risk_plain", "gain", "rp_range", "up"),
    ("P3", "none", "oneshot_gain", "gain", "rp_range", "up"),
    ("P4", "none", "direct_loss_tech", "mixed", "log_ratio", "up"),
    ("P5", "none", "direct_loss_plain", "mixed", "log_ratio", "up"),
    ("P6", "none", "oneshot_mixed", "mixed", "log_ratio", "up"),
    ("P7", "none", "oneshot_loss", "loss", "rp_range", "up"),
    ("P8", "none", "oneshot_loss", "mixed", "log_ratio", "0"),
    ("P9", "none", "cot", "gain", "rp_range", "up"),
    ("P10", "none", "cot", "loss", "rp_range", "down"),
    ("P11", "high", "direct_risk_tech", "gain", "rp_range", "up"),
    ("P12", "high", "direct_loss_tech", "mixed", "log_ratio", "up"),
]
ADJ_LEVEL = 1 - 0.05 / len(PRIMARY)

# All predictions for the primary outcomes (pre-registration, Section 5); missing = "?" (no prediction)
PREDICTIONS = {
    ("none", "direct_risk_tech"): {"gain": "up", "loss": "up"},
    ("none", "direct_risk_plain"): {"gain": "up", "loss": "up"},
    ("none", "oneshot_gain"): {"gain": "up"},
    ("none", "direct_loss_tech"): {"gain": "0", "mixed": "up"},
    ("none", "direct_loss_plain"): {"gain": "0", "mixed": "up"},
    ("none", "oneshot_loss"): {"loss": "up", "mixed": "0"},
    ("none", "oneshot_mixed"): {"mixed": "up"},
    ("none", "cot"): {"gain": "up", "loss": "down", "mixed": "0"},
    ("high", "direct_risk_tech"): {"gain": "up"},
    ("high", "direct_loss_tech"): {"mixed": "up"},
    ("high", "cot"): {"gain": "0", "loss": "0", "mixed": "0"},
}


def recover(res, item):
    """S1: give a non-monotonic or dominance-violating response the metrics of the closest consistent
    pattern. Gain/loss: patterns 0^k 1^(12-k) with 1 <= k <= 11 (a switch inside the list, both endpoints
    correct). Mixed: 0 <= k <= 12 (no switch = censored, as in the primary analysis)."""
    states = [c == "1" for c in res["pattern"]]
    n = len(states)
    gain_loss = item["item_type"] in ("gain", "loss")
    ks = range(1, n) if gain_loss else range(0, n + 1)
    dist = {k: sum(states[i] != (i >= k) for i in range(n)) for k in ks}
    best = min(dist.values())
    tied = [k for k in ks if dist[k] == best]
    if gain_loss:
        keys = sorted(item["options"])
        ces = [(keys[k - 1] + keys[k]) / 2 for k in tied]
        ce = mean(ces)
        res["ce"] = ce
        res["risk_premium"] = (item["ev"] - ce) / abs(item["ev"])
        res["risk_premium_range"] = (item["ev"] - ce) / abs(item["x_high"] - item["x_low"])
    else:
        keys = sorted(r["ratio"] for r in item["rows"])
        def la(k):
            if k == 0:
                return keys[0]
            if k == n:
                return keys[-1]
            return math.sqrt(keys[k - 1] * keys[k])
        res["la_ratio"] = math.exp(mean(math.log(la(k)) for k in tied))
    res["status"] = "valid"
    res["recovered"] = True
    return res


def load_results(run, include_invalid=False):
    """Parsed result of the latest successful record for each custom_id.
    include_invalid: apply recover() to non-monotonic and dominance-violating responses (S1)."""
    items = {it["item_id"]: it for it in load_items()}
    latest = {}
    with open(ROOT / "data" / "raw" / f"{run}.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("error") is None:
                latest[r["custom_id"]] = r
    out = []
    for r in latest.values():
        res = analyze(items[r["item_id"]], r, r["output_text"])
        res.update(condition=r["condition"], mode=r["reasoning_effort"])
        if include_invalid and res["status"] in ("non_monotonic", "dominance_violation"):
            res = recover(res, items[r["item_id"]])
        out.append(res)
    return out


def outcome_value(res, outcome):
    if outcome == "rp_range":
        return res["risk_premium_range"]
    if outcome == "rp_ev":
        return res["risk_premium"]
    if outcome == "log_ratio":
        return math.log(res["la_ratio"])
    raise ValueError(outcome)


def item_values(results):
    """{(mode, condition, item_type, outcome): {item_id: value}} following steps 2-3."""
    groups = defaultdict(list)    # (mode, condition, item_id, version) -> results
    types = {}
    for res in results:
        groups[(res["mode"], res["condition"], res["item_id"], res["version"])].append(res)
        types[res["item_id"]] = res["item_type"]
    per_prompt = {}               # (mode, condition, item_id, version) -> (n_valid, {outcome: value})
    for key, rs in groups.items():
        valid = [x for x in rs if x["status"] == "valid"]
        vals = {"valid": len(valid) / len(rs)}
        for outcome in OUTCOMES[types[key[2]]]:
            if outcome != "valid" and valid:
                vals[outcome] = mean(outcome_value(x, outcome) for x in valid)
        per_prompt[key] = (len(valid), vals)

    values = defaultdict(dict)
    for (mode, condition, item_id, version) in per_prompt:
        if version != 1:
            continue
        v1 = per_prompt.get((mode, condition, item_id, 1))
        v2 = per_prompt.get((mode, condition, item_id, 2))
        if v1 is None or v2 is None:
            continue
        item_type = types[item_id]
        for outcome in OUTCOMES[item_type]:
            if outcome == "valid":
                values[(mode, condition, item_type, outcome)][item_id] = (v1[1]["valid"] + v2[1]["valid"]) / 2
            elif v1[0] >= MIN_VALID and v2[0] >= MIN_VALID:
                values[(mode, condition, item_type, outcome)][item_id] = (v1[1][outcome] + v2[1][outcome]) / 2
    return values


def quantile(sorted_vals, q):
    """Linear-interpolation quantile of an already sorted list."""
    pos = q * (len(sorted_vals) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_ci(diffs, levels, rng):
    """Percentile CIs of the mean of diffs, resampling items with replacement."""
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(N_BOOT))
    return {lvl: (quantile(means, (1 - lvl) / 2), quantile(means, 1 - (1 - lvl) / 2)) for lvl in levels}


def conclude(est, ci, half_step, prediction):
    """Decision rule (pre-registration, Section 4)."""
    lo, hi = ci
    if half_step is None:                                  # no smallest effect of interest defined
        if lo > 0 or hi < 0:
            return "increase" if est > 0 else "decrease"
        return "CI includes 0"
    if -half_step < lo and hi < half_step:
        return "no meaningful effect"
    if (lo > 0 or hi < 0) and abs(est) >= half_step:
        direction = "up" if est > 0 else "down"
        if prediction in ("up", "down"):
            return "effect as predicted" if direction == prediction else "effect opposite to prediction"
        return f"effect ({'increase' if direction == 'up' else 'decrease'})"
    return "inconclusive"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="main")
    parser.add_argument("--include-invalid", action="store_true", help="sensitivity analysis S1")
    args = parser.parse_args()
    results = load_results(args.run, include_invalid=args.include_invalid)
    suffix = "_S1" if args.include_invalid else ""
    values = item_values(results)
    rng = random.Random(SEED)
    primary_keys = {(m, c, t, o): pid for pid, m, c, t, o, _ in PRIMARY}

    rows = []
    for (mode, condition, item_type, outcome), cond_vals in sorted(values.items()):
        if condition == "baseline":
            continue
        base_vals = values.get((mode, "baseline", item_type, outcome), {})
        common = sorted(set(cond_vals) & set(base_vals))
        if len(common) < 2:
            continue
        diffs = [cond_vals[i] - base_vals[i] for i in common]
        est = mean(diffs)
        pid = primary_keys.get((mode, condition, item_type, outcome))
        levels = [0.95] + ([ADJ_LEVEL] if pid else [])
        cis = bootstrap_ci(diffs, levels, rng)
        pred = "?"
        if outcome in ("rp_range", "log_ratio"):
            pred = PREDICTIONS.get((mode, condition), {}).get(item_type, "?")
        decision_ci = cis[ADJ_LEVEL] if pid else cis[0.95]
        rows.append({
            "primary": pid or "", "mode": mode, "condition": condition, "item_type": item_type,
            "outcome": outcome, "prediction": pred, "n_items": len(common),
            "n_excluded": 20 - len(common),
            "estimate": round(est, 4),
            "estimate_steps": round(est / STEP[outcome], 2) if STEP[outcome] else "",
            "ci95_low": round(cis[0.95][0], 4), "ci95_high": round(cis[0.95][1], 4),
            "ci_adj_low": round(cis[ADJ_LEVEL][0], 4) if pid else "",
            "ci_adj_high": round(cis[ADJ_LEVEL][1], 4) if pid else "",
            "conclusion": conclude(est, decision_ci, HALF_STEP[outcome], pred),
        })

    out_dir = ROOT / "results" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{args.run}_contrasts{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    levels = []
    for (mode, condition, item_type, outcome), vals in sorted(values.items()):
        m = mean(vals.values())
        levels.append({"mode": mode, "condition": condition, "item_type": item_type, "outcome": outcome,
                       "n_items": len(vals), "mean": round(m, 4),
                       "ratio_geometric_mean": round(math.exp(m), 3) if outcome == "log_ratio" else ""})
    with open(out_dir / f"{args.run}_levels{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(levels[0]))
        writer.writeheader()
        writer.writerows(levels)

    print(f"{len(results)} responses analyzed; {len(rows)} contrasts written to {out_dir}\n")
    label = "S1 sensitivity analysis (invalid responses included)" if args.include_invalid else "Primary contrasts"
    print(f"{label} (decision on Bonferroni-adjusted {ADJ_LEVEL:.2%} CI):")
    print(f"{'ID':<5}{'mode':<6}{'condition':<19}{'type':<7}{'pred':<6}{'items':>6}{'est (steps)':>12}"
          f"{'adjusted CI':>22}   conclusion")
    by_id = {r["primary"]: r for r in rows if r["primary"]}
    for pid, *_ in PRIMARY:
        r = by_id.get(pid)
        if r is None:
            print(f"{pid:<5}(no data)")
            continue
        ci = f"[{r['ci_adj_low']:+.3f}, {r['ci_adj_high']:+.3f}]"
        print(f"{pid:<5}{r['mode']:<6}{r['condition']:<19}{r['item_type']:<7}{r['prediction']:<6}"
              f"{r['n_items']:>6}{r['estimate_steps']:>12}{ci:>22}   {r['conclusion']}")


if __name__ == "__main__":
    main()