"""
Generate the one-shot example texts in prompts/interventions/.

Each example is one demonstration item (numbers differ from every test item) with the
answers of a respondent who has the target preference. No label or explanation is given;
the Reason line is neutral. One file per example and version, because the A/B labels
must match the version of the test prompt (version 1: A = lottery; version 2: A = sure).
The example rows are shuffled once with a fixed seed, the same order in both versions.

Demonstrated preferences:
  oneshot_gain : 40% of $200, else $50 (EV $110); sure amount chosen from $90.91 upward
                 -> CE ~ $84.09, risk premium ~ 0.24
  oneshot_loss : the same lottery negated (EV -$110); sure loss chosen from -$131.82 upward
                 -> CE ~ -$138.64, risk premium ~ 0.26
  oneshot_mixed: 50/50, lose $60; gain/loss ratios 0.2, 0.4, ..., 2.4 (a different grid from the
                 test items); plays only if G >= 2 x L. Copying the switch POSITION onto the test grid
                 would give a ratio of ~2.96, adopting the PREFERENCE gives ~1.94 (baseline ~1.04).

Usage: python src/make_oneshot.py   (writes 6 files; re-run only if the examples change)
"""

import random

from items import linspace
from prompts import PROMPT_DIR, describe_lottery, format_row, money, read_template

INTRO = "Below is an example of a similar task and the answers you gave."
REASON = "I compared the two options in each row."
OUTRO = "Now answer the new task in the same format."


def gain_loss_rows(p, x_high, x_low, sure_from):
    """[(lottery_text, sure_text, takes_sure)] in sorted order."""
    lottery = describe_lottery(p, x_high, x_low)
    return lottery, [(lottery, f"{money(x)} for sure", x >= sure_from)
                     for x in [round(v, 2) for v in linspace(x_low, x_high, 12)]]


def mixed_rows(loss, ratios, play_from_ratio):
    return [(describe_lottery(0.5, round(r * loss, 2), -loss), f"{money(0)} for sure",
             not r >= play_from_ratio)   # takes_sure = does not play
            for r in ratios]


def render(rows, version, header):
    order = list(range(len(rows)))
    random.Random("oneshot_example").shuffle(order)
    task_lines, answer_lines = [], []
    for k, i in enumerate(order):
        lottery_text, sure_text, takes_sure = rows[i]
        task_lines.append(format_row(k + 1, lottery_text, sure_text, version))
        lottery_label = "A" if version == 1 else "B"
        sure_label = "B" if version == 1 else "A"
        answer_lines.append(f"Row {k + 1}: {sure_label if takes_sure else lottery_label}")
    return "\n\n".join([
        INTRO,
        "Example task:\n" + header + "\n\n" + "\n".join(task_lines),
        "Your answers:\n" + "\n".join(answer_lines) + f"\nReason: {REASON}",
        OUTRO,
    ])


def main():
    gain_lottery, gain = gain_loss_rows(0.4, 200, 50, 90.91)
    loss_lottery, loss = gain_loss_rows(0.4, -200, -50, -131.82)
    ratios = [round(0.2 * k, 2) for k in range(1, 13)]
    mixed = mixed_rows(60, ratios, 2.0)
    examples = {
        "oneshot_gain": (gain, f"The lottery is the same in every row: {gain_lottery}."),
        "oneshot_loss": (loss, f"The lottery is the same in every row: {loss_lottery}."),
        "oneshot_mixed": (mixed, read_template("user_mixed.txt").split("\n")[0]),
    }
    for name, (rows, header) in examples.items():
        for version in (1, 2):
            path = PROMPT_DIR / "interventions" / f"{name}_v{version}.txt"
            path.write_text(render(rows, version, header) + "\n", encoding="utf-8")
            print("wrote", path.relative_to(PROMPT_DIR.parent))


if __name__ == "__main__":
    main()