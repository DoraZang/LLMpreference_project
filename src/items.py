"""
Generate the item set for the gambling game.

Item types (20 each, 60 total):
  gain  : "with probability p receive x_high, otherwise x_low", all amounts > 0
  loss  : gain items with all amounts negated
  mixed : 50/50 gamble "win G or lose L", two elicitation directions
          A: fix L, vary G across rows
          B: fix G, vary L across rows

Design decisions and their rationale are recorded in notes/lab_log.md.
Option order is NOT shuffled here; shuffling happens when prompts are built.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Design parameters (see notes/lab_log.md, 2026-10-11)
# ---------------------------------------------------------------------------

# Gain / loss items
PROBS = [0.1, 0.3, 0.5, 0.7, 0.9]   # probability of the larger-magnitude outcome
MAGNITUDES = [10, 1000]              # x_high in dollars
RATIOS_R = [0.2, 0.5]                # r = x_low / x_high
N_OPTIONS = 12                       # sure amounts per item, endpoints included

# Mixed items
N_ANCHORS = 10                       # log-spaced anchor amounts
ANCHOR_MIN, ANCHOR_MAX = 10, 1000
N_ROWS = 12                          # gain/loss ratios per item
RATIO_MIN, RATIO_MAX = 0.5, 5.0      # log-spaced

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "items" / "items.json"


def linspace(a, b, n):
    """n equally spaced values from a to b, both endpoints included."""
    step = (b - a) / (n - 1)
    return [a + i * step for i in range(n)]


def logspace(a, b, n):
    """n log-spaced values from a to b, both endpoints included."""
    factor = (b / a) ** (1 / (n - 1))
    return [a * factor**i for i in range(n)]


def make_gain_loss_items():
    items = []
    for sign, item_type in [(1, "gain"), (-1, "loss")]:
        k = 0
        for magnitude in MAGNITUDES:
            for r in RATIOS_R:
                for p in PROBS:
                    k += 1
                    x_high = sign * magnitude
                    x_low = round(sign * magnitude * r, 2)
                    ev = p * x_high + (1 - p) * x_low
                    options = [round(x, 2) for x in linspace(x_low, x_high, N_OPTIONS)]
                    items.append({
                        "item_id": f"{item_type}_{k:02d}",
                        "item_type": item_type,
                        "p_high": p,
                        "magnitude": magnitude,
                        "r": r,
                        "x_high": x_high,
                        "x_low": x_low,
                        "ev": round(ev, 4),  # for analysis only; never shown to the model
                        "options": options,
                    })
    return items


def make_mixed_items():
    anchors = [round(a) for a in logspace(ANCHOR_MIN, ANCHOR_MAX, N_ANCHORS)]
    ratios = [round(x, 4) for x in logspace(RATIO_MIN, RATIO_MAX, N_ROWS)]
    items = []
    for direction in ["A", "B"]:
        for k, anchor in enumerate(anchors, start=1):
            rows = []
            for ratio in ratios:
                if direction == "A":   # fixed loss L = anchor, gain G varies
                    gain, loss = ratio * anchor, anchor
                else:                  # fixed gain G = anchor, loss L varies
                    gain, loss = anchor, anchor / ratio
                rows.append({"ratio": ratio, "gain": round(gain, 2), "loss": round(loss, 2)})
            items.append({
                "item_id": f"mixed_{direction}_{k:02d}",
                "item_type": "mixed",
                "direction": direction,
                "p_win": 0.5,
                "anchor": anchor,
                "rows": rows,
            })
    return items


def check_items(items):
    """Sanity checks on the generated items; raises AssertionError if a design rule is violated."""
    counts = {t: sum(it["item_type"] == t for it in items) for t in ("gain", "loss", "mixed")}
    assert counts == {"gain": 20, "loss": 20, "mixed": 20}, counts
    assert len({it["item_id"] for it in items}) == len(items), "duplicate item_id"

    for it in items:
        if it["item_type"] in ("gain", "loss"):
            opts = it["options"]
            assert len(opts) == N_OPTIONS, it["item_id"]
            assert opts[0] == it["x_low"] and opts[-1] == it["x_high"], it["item_id"]
            lo, hi = sorted([it["x_low"], it["x_high"]])
            assert lo < it["ev"] < hi, it["item_id"]
            # No sure option may equal the EV (avoids indifference ties)
            assert all(abs(o - it["ev"]) > 1e-6 for o in opts), it["item_id"]
        else:
            assert len(it["rows"]) == N_ROWS, it["item_id"]
            # No row may have ratio exactly 1 (EV = 0)
            assert all(abs(row["ratio"] - 1) > 1e-6 for row in it["rows"]), it["item_id"]


def main():
    items = make_gain_loss_items() + make_mixed_items()
    check_items(items)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    print(f"Wrote {len(items)} items to {OUT_PATH}\n")

    # Print one example of each kind for a quick visual check
    for item_id in ("gain_03", "loss_03", "mixed_A_05", "mixed_B_05"):
        it = next(i for i in items if i["item_id"] == item_id)
        if it["item_type"] == "mixed":
            print(f"{item_id}: direction {it['direction']}, anchor ${it['anchor']}")
            print("   (gain, loss):", [(row["gain"], row["loss"]) for row in it["rows"]])
        else:
            print(f"{item_id}: {it['p_high']:.0%} chance of {it['x_high']}, "
                  f"otherwise {it['x_low']}; EV = {it['ev']}")
            print("   options:", it["options"])


if __name__ == "__main__":
    main()