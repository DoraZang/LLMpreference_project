"""
Summarize a smoke-test run from data/raw/<run>.jsonl. No API calls are made.

Usage:
  python src/smoke_report.py                     # default run: smoke_test
  python src/smoke_report.py --run smoke_sorted

Sections:
  1. Competence status by reasoning mode and item type
  2. Token usage and cost by reasoning mode
  3. Mixed items: censoring
  4. First look at the metrics (1 sample per item: indicative only)
  5. Neighbor check: in invalid responses, do error rows copy the answer of the row above?
"""

import argparse
import json
from collections import Counter
from statistics import mean, median

from llm import ROOT, cost_usd
from parse import analyze, parse_response
from prompts import load_items

STATUSES = ["valid", "parse_fail", "non_monotonic", "dominance_violation"]
TYPES = ["gain", "loss", "mixed"]


def load_records(raw):
    """Latest successful record for each (item, version, mode)."""
    latest = {}
    with open(raw, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("error") is None:
                latest[(r["item_id"], r["version"], r["reasoning_effort"])] = r
    return list(latest.values())


def error_rows(states):
    """Sorted positions that disagree with the closest consistent 0...01...1 pattern."""
    n = len(states)
    best = None
    for zeros in range(n + 1):
        target = [False] * zeros + [True] * (n - zeros)
        mismatches = [i for i in range(n) if states[i] != target[i]]
        if best is None or len(mismatches) < len(best):
            best = mismatches
    return best


def neighbor_stats(item, rec):
    """For one parsed response: (#error rows, #error rows equal to the row above,
    #other rows, #other rows equal to the row above). Rows are in displayed order."""
    choices, _ = parse_response(rec["output_text"])
    if choices is None:
        return None
    rows = []  # (key, displayed_row_number, letter, state)
    for k, idx in enumerate(rec["row_order"]):
        letter = choices[k + 1]
        took_lottery = letter == rec["lottery_option"]
        if item["item_type"] in ("gain", "loss"):
            rows.append((item["options"][idx], k + 1, letter, not took_lottery))
        else:
            rows.append((item["rows"][idx]["ratio"], k + 1, letter, took_lottery))
    rows.sort()
    errors = {rows[i][1] for i in error_rows([r[3] for r in rows])}
    e = e_same = o = o_same = 0
    for k in range(2, len(rows) + 1):  # displayed rows 2..12 have a row above
        same = choices[k] == choices[k - 1]
        if k in errors:
            e, e_same = e + 1, e_same + same
        else:
            o, o_same = o + 1, o_same + same
    return e, e_same, o, o_same


def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "   n/a"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="smoke_test")
    raw = ROOT / "data" / "raw" / f"{parser.parse_args().run}.jsonl"

    items = {it["item_id"]: it for it in load_items()}
    records = load_records(raw)
    results = [(r, analyze(items[r["item_id"]], r, r["output_text"])) for r in records]
    print(f"{len(records)} successful calls in {raw.name}\n")

    for mode in ["none", "high"]:
        sub = [(r, res) for r, res in results if r["reasoning_effort"] == mode]
        if not sub:
            continue
        print("=" * 72)
        print(f"Reasoning effort: {mode}   ({len(sub)} calls)")
        print("=" * 72)

        # 1. Competence status
        print(f"{'type':<7}" + "".join(f"{s:>22}" for s in STATUSES))
        for t in TYPES:
            rs = [res for _, res in sub if res["item_type"] == t]
            c = Counter(res["status"] for res in rs)
            print(f"{t:<7}" + "".join(f"{c[s]:>13} ({pct(c[s], len(rs))})" for s in STATUSES))

        # 2. Tokens and cost
        rt = [r["reasoning_tokens"] or 0 for r, _ in sub]
        ot = [r["output_tokens"] for r, _ in sub]
        it = [r["input_tokens"] for r, _ in sub]
        incomplete = sum(r["status"] != "completed" for r, _ in sub)
        print(f"\nInput tokens  mean {mean(it):.0f} | Output tokens mean {mean(ot):.0f}, max {max(ot)}")
        print(f"Reasoning tokens mean {mean(rt):.0f}, median {median(rt):.0f}, max {max(rt)} | "
              f"incomplete responses: {incomplete}")
        print(f"Cost: total ${sum(cost_usd(r) for r, _ in sub):.4f}, per call ${mean(cost_usd(r) for r, _ in sub):.6f}")

        # 3. Censoring
        mixed_valid = [res for _, res in sub if res["item_type"] == "mixed" and res["status"] == "valid"]
        cens = Counter(res["censored"] for res in mixed_valid)
        print(f"\nMixed (valid {len(mixed_valid)}): censored high {cens['high']}, low {cens['low']}, "
              f"not censored {cens[None]}")

        # 4. First look at metrics
        for t in ["gain", "loss"]:
            valid = [res for _, res in sub if res["item_type"] == t and res["status"] == "valid"]
            for key, label in [("risk_premium", "risk premium (/|EV|)  "),
                               ("risk_premium_range", "risk premium (/range)")]:
                vals = [res[key] for res in valid]
                if vals:
                    print(f"{t} {label}: mean {mean(vals):+.3f}, median {median(vals):+.3f} (n={len(vals)})")
        la = [res["la_ratio"] for res in mixed_valid]
        if la:
            print(f"mixed loss-aversion ratio: median {median(la):.2f} (n={len(la)})")

        # 5. Neighbor check on invalid responses
        e = e_same = o = o_same = 0
        for r, res in sub:
            if res["status"] in ("non_monotonic", "dominance_violation"):
                s = neighbor_stats(items[r["item_id"]], r)
                e, e_same, o, o_same = e + s[0], e_same + s[1], o + s[2], o_same + s[3]
        print(f"\nNeighbor check (invalid responses): error rows equal to the row above "
              f"{e_same}/{e} ({pct(e_same, e).strip()}); other rows {o_same}/{o} ({pct(o_same, o).strip()})\n")


if __name__ == "__main__":
    main()