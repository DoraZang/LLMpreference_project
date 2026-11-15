"""
Pilot report: how much do repeated answers to the same prompt vary, and how many samples
per prompt does the main experiment need? No API calls are made.

For each item x version x reasoning mode (valid responses only):
  gain/loss: range-normalized risk premium;  mixed: log of the loss-aversion ratio.
Both are measured in grid steps' terms below: one option step is 1/11 of the range
(gain/loss) and ln(10)/11 in log ratio (mixed). The smallest shift we want to detect is
HALF a step (delta).

Required samples per prompt so that the 95% CI half-width of a prompt's mean is <= delta:
  n_valid = (1.96 * SD / delta)^2, rounded up;  n_calls = n_valid / valid rate.
Also reported: the CI half-width with N = 10 samples (the original paper's Section 4 setting).

Usage: python src/pilot_report.py --run pilot
"""

import argparse
import json
import math
from collections import defaultdict
from statistics import mean, stdev

from llm import ROOT
from parse import analyze
from prompts import load_items

DELTA = {"gain": 0.5 / 11, "loss": 0.5 / 11, "mixed": 0.5 * math.log(10) / 11}


def metric(res):
    if res["item_type"] == "mixed":
        return math.log(res["la_ratio"])
    return res["risk_premium_range"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="pilot")
    raw = ROOT / "data" / "raw" / f"{parser.parse_args().run}.jsonl"
    items = {it["item_id"]: it for it in load_items()}

    groups = defaultdict(list)   # (mode, item_id, version) -> list of results
    with open(raw, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("error") is None:
                groups[(r["reasoning_effort"], r["item_id"], r["version"])].append(
                    analyze(items[r["item_id"]], r, r["output_text"]))

    for mode in ["none", "high"]:
        keys = sorted(k for k in groups if k[0] == mode)
        if not keys:
            continue
        print("=" * 78)
        print(f"Reasoning effort: {mode}")
        print("=" * 78)
        print(f"{'item':<12}{'ver':>4}{'calls':>7}{'valid':>7}{'mean':>9}{'SD':>8}{'SD/step':>9}{'censored':>10}")
        pooled = defaultdict(list)   # item_type -> (variance, n_valid)
        rates = defaultdict(list)
        for _, item_id, version in keys:
            rs = groups[(mode, item_id, version)]
            t = rs[0]["item_type"]
            valid = [x for x in rs if x["status"] == "valid"]
            vals = [metric(x) for x in valid]
            rates[t].append(len(valid) / len(rs))
            sd = stdev(vals) if len(vals) > 1 else float("nan")
            if len(vals) > 1:
                pooled[t].append((sd ** 2, len(vals)))
            cens = sum(x["censored"] is not None for x in valid)
            m = f"{mean(vals):9.3f}" if vals else f"{'-':>9}"
            print(f"{item_id:<12}{version:>4}{len(rs):>7}{len(valid):>7}{m}{sd:8.3f}"
                  f"{sd / (2 * DELTA[t]):9.2f}{cens:>10}")

        print(f"\n{'type':<7}{'pooled SD':>10}{'valid rate':>12}{'n valid':>9}{'n calls':>9}{'CI half-width, N=10':>22}")
        for t in ["gain", "loss", "mixed"]:
            if not pooled[t]:
                continue
            # pooled within-prompt variance, weighted by degrees of freedom
            var = sum(v * (n - 1) for v, n in pooled[t]) / sum(n - 1 for _, n in pooled[t])
            sd, rate = math.sqrt(var), mean(rates[t])
            n_valid = max(1, math.ceil((1.96 * sd / DELTA[t]) ** 2))
            n_calls = math.ceil(n_valid / rate) if rate > 0 else float("inf")
            half10 = 1.96 * sd / math.sqrt(max(1, 10 * rate))
            print(f"{t:<7}{sd:10.3f}{rate:12.0%}{n_valid:9d}{n_calls:9}"
                  f"{half10:12.3f} ({half10 / (2 * DELTA[t]):.2f} steps)")
        print("\n(delta = half an option step; 'SD/step' and 'steps' are in units of one option step)\n")


if __name__ == "__main__":
    main()