"""
Build the prompts sent to the model.

Each prompt is built from:
  - a system message      (prompts/system_baseline.txt, preceded by an intervention from
                            prompts/interventions/ for non-baseline conditions) a system message      (prompts/system_<condition>.txt)
  - a user-message template (prompts/user_gain_loss.txt or prompts/user_mixed.txt)
  - one item              (data/items/items.json)
  - a version: version 1 puts the lottery in Option A, version 2 puts it in Option B
  - a random row order (shuffled independently on every call)

The returned record includes the displayed row order, so every response can be
mapped back to the item's rows. Design decisions: notes/lab_log.md (2026-10-25).
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts"
ITEMS_PATH = ROOT / "data" / "items" / "items.json"
# Experimental conditions. Each intervention is a text file in prompts/interventions/ that is
# placed at the start of the system message, before the baseline rules (None = baseline).
CONDITIONS = {
    "baseline": None,
    "direct_risk_tech": "direct_risk_tech.txt",
    "direct_risk_plain": "direct_risk_plain.txt",
    "direct_loss_tech": "direct_loss_tech.txt",
    "direct_loss_plain": "direct_loss_plain.txt",
}

def load_items():
    with open(ITEMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_template(name):
    return (PROMPT_DIR / name).read_text(encoding="utf-8").strip()

def build_system(condition):
    """System message for a condition: intervention text (if any) + baseline rules."""
    base = read_template("system_baseline.txt")
    name = CONDITIONS[condition]
    if name is None:
        return base
    intervention = read_template(f"interventions/{name}")
    return intervention + "\n\n" + base

def money(x):
    """Signed dollar amount with two decimals: 7.09 -> '$7.09', -77 -> '-$77.00'."""
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):.2f}"


def chance(p):
    """Probability as a whole-number percentage: 0.1 -> '10%'."""
    return f"{round(p * 100)}%"


def describe_lottery(p, x1, x2):
    """Two-outcome lottery: 'a 50% chance of $10.00 and a 50% chance of $2.00'."""
    return f"a {chance(p)} chance of {money(x1)} and a {chance(1 - p)} chance of {money(x2)}"


def format_row(row_num, lottery_text, sure_text, version):
    """One row of the choice list. Version 1: A = lottery; version 2: A = sure amount."""
    if version == 1:
        a, b = lottery_text, sure_text
    elif version == 2:
        a, b = sure_text, lottery_text
    else:
        raise ValueError(f"version must be 1 or 2, got {version}")
    return f"Row {row_num}: Option A: {a}. Option B: {b}."


def build_prompt(item, version, rng, condition="baseline", shuffle=True, full_rows=False):
    """Build one prompt for one item.

    rng is a random.Random instance used to shuffle the rows.
    If shuffle is False, rows are shown in stored order: gain/loss items from x_low to
    x_high (increasing magnitude), mixed items by increasing gain/loss ratio.
    If full_rows is True, gain/loss rows spell out the lottery in every row (as mixed items
    do) instead of "play the lottery"; uses prompts/user_gain_loss_fullrow.txt.
    Returns a dict with the system message, the user message, and row_order:
    row_order[k] is the index (into item["options"] or item["rows"]) of the row
    displayed as Row k+1.
    """
    is_gain_loss = item["item_type"] in ("gain", "loss")
    n_rows = len(item["options"]) if is_gain_loss else len(item["rows"])
    row_order = list(range(n_rows))
    if shuffle:
        rng.shuffle(row_order)

    if is_gain_loss:
        lottery = describe_lottery(item["p_high"], item["x_high"], item["x_low"])
        lottery_in_row = lottery if full_rows else "play the lottery"
        template = "user_gain_loss_fullrow.txt" if full_rows else "user_gain_loss.txt"
        lines = [
            format_row(k + 1, lottery_in_row, f"{money(item['options'][i])} for sure", version)
            for k, i in enumerate(row_order)
        ]
        user = read_template(template).format(lottery=lottery, rows="\n".join(lines))
    else:
        lines = []
        for k, i in enumerate(row_order):
            row = item["rows"][i]
            lottery = describe_lottery(item["p_win"], row["gain"], -row["loss"])
            lines.append(format_row(k + 1, lottery, f"{money(0)} for sure", version))
        user = read_template("user_mixed.txt").format(rows="\n".join(lines))

    return {
        "item_id": item["item_id"],
        "condition": condition,
        "version": version,
        "lottery_option": "A" if version == 1 else "B",
        "shuffled": shuffle,
        "full_rows": full_rows,
        "row_order": row_order,
        "system": build_system(condition),
        "user": user,
    }


if __name__ == "__main__":
    # Demo: print a few prompts for visual inspection. No API calls are made.
    items = {it["item_id"]: it for it in load_items()}
    rng = random.Random(0)  # fixed seed so the demo output is reproducible
    for item_id, version in [("gain_03", 1), ("loss_03", 2), ("mixed_A_05", 1)]:
        p = build_prompt(items[item_id], version, rng)
        print("=" * 70)
        print(f"{item_id} | version {version} | lottery is Option {p['lottery_option']}")
        print("row_order:", p["row_order"])
        print("-" * 70)
        print(p["user"])
    print("=" * 70)
    print("SYSTEM MESSAGE:\n")
    print(p["system"])