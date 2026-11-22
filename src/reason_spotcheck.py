"""
Spot check of the labels that the validation sample barely contained (reason analysis, step 3c).

Draws N distinct reason texts per label (default: other, risk seeking, loss averse) from the full
labeling output and writes them to one file for a quick human check: for each row, does the LLM label
follow the codebook? Condition and mode are left out so they do not influence the check; item type is
shown because the codebook treats pure-loss items differently for loss aversion.

Usage:
  python src/reason_spotcheck.py
Output:
  results/reasons/spotcheck_rare_labels.csv   fill in "agree" (yes/no) and, if no, "correct_label"
"""

import argparse

import pandas as pd

from llm import ROOT

SEED = 2026


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default="reason_labels_main_claude-haiku-5-5.csv")
    parser.add_argument("--check", nargs="+", default=["other", "risk seeking", "loss averse"])
    parser.add_argument("--n", type=int, default=20, help="distinct reason texts per label")
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="earlier spot-check files whose reason texts must not be drawn again")
    parser.add_argument("--out", default="spotcheck_rare_labels.csv")
    args = parser.parse_args()

    df = pd.read_csv(ROOT / "results" / "reasons" / args.labels, encoding="utf-8-sig")
    seen = set()
    for name in args.exclude:
        seen |= set(pd.read_csv(ROOT / "results" / "reasons" / name, encoding="utf-8-sig")["reason"])
    rows = []
    for label in args.check:
        sub = df[(df["label"] == label) & ~df["reason"].isin(seen)]
        texts = sub.drop_duplicates("text_id")
        pick = texts.sample(n=min(args.n, len(texts)), random_state=SEED)
        print(f"{label}: {len(sub)} responses, {len(texts)} distinct texts, "
              f"{sub['item_type'].value_counts().to_dict()} -> {len(pick)} drawn")
        rows.append(pick)
    out = pd.concat(rows).sample(frac=1, random_state=SEED)   # mix the labels
    out.insert(0, "check_id", [f"S{i:03d}" for i in range(1, len(out) + 1)])
    out = out[["check_id", "item_type", "label", "names_preference", "reason", "text_id"]]
    out = out.rename(columns={"label": "llm_label", "names_preference": "llm_flag"})
    out["agree"] = ""
    out["correct_label"] = ""
    out["note"] = ""
    path = ROOT / "results" / "reasons" / args.out
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"wrote {path.relative_to(ROOT)} ({len(out)} rows)")


if __name__ == "__main__":
    main()