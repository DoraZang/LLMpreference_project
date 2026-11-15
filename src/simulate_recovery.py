"""
Recovery test for the analysis: simulate a full main run with KNOWN effects and check that
analyze_main.py finds them. No API calls are made.

The simulated respondent switches at a certainty equivalent (gain/loss items) or a loss-aversion
ratio (mixed items) set by the TRUE values below, plus noise in reasoning "none", plus
30% random (invalid) answers in reasoning "none", plus a label bias in version 1.
It uses the real prompts and row orders of the pre-registered design (batch.main_tasks).

Usage:
  python src/simulate_recovery.py          # writes data/raw/simrecovery.jsonl
  python src/analyze_main.py --run simrecovery
Expected: every effect of at least half a step is detected in the predicted direction;
direct_risk_plain (set to 1/3 of a step) is not called an effect; oneshot_loss leaves the mixed ratio unchanged.
"""

import json
import math
import random

from batch import build_request, main_tasks
from llm import ROOT
from prompts import load_items

RUN = "simrecovery"
STEP = 1 / 11   # one option step in range-normalized risk premium

# True levels: risk premium in range units (positive = risk-averse) and log loss-aversion ratio
BASE = {"none": {"gain": -0.15, "loss": 0.20, "mixed": math.log(1.04)},
        "high": {"gain": 0.0, "loss": 0.0, "mixed": math.log(1.04)}}
# True effects relative to baseline
EFFECT = {
    ("none", "direct_risk_tech"): {"gain": 0.10, "loss": 0.10},
    ("none", "direct_risk_plain"): {"gain": 0.03, "loss": 0.03},          # below half a step on purpose
    ("none", "oneshot_gain"): {"gain": 0.10},
    ("none", "oneshot_loss"): {"loss": 0.10},                             # no effect on mixed items
    ("none", "direct_loss_tech"): {"mixed": 0.40},
    ("none", "direct_loss_plain"): {"mixed": 0.40},
    ("none", "oneshot_mixed"): {"mixed": math.log(2) - math.log(1.04)},  # loss-aversion ratio 2
    ("none", "cot"): {"gain": 0.15, "loss": -0.20},                       # both back to EV
    ("high", "direct_risk_tech"): {"gain": 0.10},
    ("high", "direct_loss_tech"): {"mixed": 0.40},
}
NOISE_SD = {"none": 0.2, "high": 0.0}
P_RANDOM = {"none": 0.3, "high": 0.0}
LABEL_BIAS = 0.05   # version 1 (A = lottery) in "none": more lottery choices


def simulated_answer(meta, item, rng):
    mode, t = meta["reasoning_effort"], item["item_type"]
    level = BASE[mode][t] + EFFECT.get((mode, meta["condition"]), {}).get(t, 0)
    if mode == "none" and t != "mixed" and meta["version"] == 1:
        level -= LABEL_BIAS
    level += rng.gauss(0, NOISE_SD[mode])
    random_answers = rng.random() < P_RANDOM[mode]
    lines = []
    for k, idx in enumerate(meta["row_order"]):
        if random_answers:
            lottery = rng.random() < 0.5
        elif t == "mixed":
            lottery = math.log(item["rows"][idx]["ratio"]) >= level
        else:
            ce = item["ev"] - level * abs(item["x_high"] - item["x_low"])   # risk-averse: CE below EV
            lottery = item["options"][idx] < ce
        other = "B" if meta["lottery_option"] == "A" else "A"
        lines.append(f"Row {k + 1}: {meta['lottery_option'] if lottery else other}")
    return "\n".join(lines) + "\nReason: simulated."


def main():
    items = {it["item_id"]: it for it in load_items()}
    rng = random.Random(1)
    path = ROOT / "data" / "raw" / f"{RUN}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for task in main_tasks():
            _, meta = build_request(RUN, task, items)
            rec = {**meta, "output_text": simulated_answer(meta, items[meta["item_id"]], rng), "error": None}
            f.write(json.dumps(rec) + "\n")
    print(f"wrote simulated responses to {path}")
    print("True effects (option steps):")
    for (mode, cond), eff in EFFECT.items():
        parts = [f"{t} {v / (STEP if t != 'mixed' else math.log(10) / 11):+.2f}" for t, v in eff.items()]
        print(f"  {mode:<5}{cond:<19}" + ", ".join(parts))


if __name__ == "__main__":
    main()