"""
Draw the samples of Reason lines for the reason analysis (pre-registration, Section 9). No API calls.

Two non-overlapping stratified samples, one stratum per condition x reasoning mode x item type:
  discovery  : PER_CELL_DISCOVERY reasons per stratum, read to build the category scheme
  validation : VALIDATION_N reasons (1-2 per stratum), hand-labeled to check the LLM labels

The labeling files show ONLY the reason text, in random order, so labels are not influenced by
knowing the condition. A separate key file links each sample_id to its condition, mode, item and
measured behavior; open the key only after labeling.

For CoT responses the Reason line (after the answers) is used, not the written reasoning, so that
all conditions are compared on the same kind of text.

Usage:
  python src/reason_sample.py --run main
Outputs (results/reasons/):
  discovery_reasons.csv, validation_reasons.csv   to read / label (UTF-8, opens in Excel)
  discovery_key.csv, validation_key.csv           hidden information for each sample_id
"""

import argparse
import csv
import json
import random
from collections import defaultdict

from llm import ROOT
from parse import analyze
from prompts import load_items

PER_CELL_DISCOVERY = 2
VALIDATION_N = 100
SEED = 911


def load_with_reasons(run):
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
        if res["reason"]:
            out.append({"custom_id": r["custom_id"], "condition": r["condition"], "mode": r["reasoning_effort"],
                        "item_id": r["item_id"], "item_type": res["item_type"], "version": r["version"],
                        "status": res["status"], "risk_premium_range": res["risk_premium_range"],
                        "la_ratio": res["la_ratio"], "reason": res["reason"]})
    return out


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel reads it correctly
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_sample(name, sample, rng, out_dir, label_columns):
    rng.shuffle(sample)
    for i, rec in enumerate(sample, start=1):
        rec["sample_id"] = f"{name[0].upper()}{i:03d}"
    write_csv(out_dir / f"{name}_reasons.csv",
              [{"sample_id": r["sample_id"], "reason": r["reason"], **{c: "" for c in label_columns}} for r in sample],
              ["sample_id", "reason"] + label_columns)
    key_fields = ["sample_id", "custom_id", "condition", "mode", "item_id", "item_type", "version", "status",
                  "risk_premium_range", "la_ratio"]
    write_csv(out_dir / f"{name}_key.csv", [{k: r[k] for k in key_fields} for r in sample], key_fields)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="main")
    args = parser.parse_args()
    rng = random.Random(SEED)

    strata = defaultdict(list)
    for rec in load_with_reasons(args.run):
        strata[(rec["condition"], rec["mode"], rec["item_type"])].append(rec)
    keys = sorted(strata)
    for k in keys:
        rng.shuffle(strata[k])

    discovery = [rec for k in keys for rec in strata[k][:PER_CELL_DISCOVERY]]

    # Validation: one per stratum first, then a second one from randomly chosen strata, up to VALIDATION_N
    remaining = {k: strata[k][PER_CELL_DISCOVERY:] for k in keys}
    validation = [remaining[k].pop(0) for k in keys if remaining[k]]
    extra = [k for k in keys if remaining[k]]
    rng.shuffle(extra)
    for k in extra[:max(0, VALIDATION_N - len(validation))]:
        validation.append(remaining[k].pop(0))

    out_dir = ROOT / "results" / "reasons"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_sample("discovery", discovery, rng, out_dir, ["notes"])
    save_sample("validation", validation, rng, out_dir, ["label", "notes"])
    print(f"{len(strata)} strata; discovery sample {len(discovery)}, validation sample {len(validation)}")
    print(f"written to {out_dir}")


if __name__ == "__main__":
    main()