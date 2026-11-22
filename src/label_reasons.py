"""
Label the one-line "Reason:" of each response with Claude, using docs/reason_codebook.md as the prompt
(exploratory reason analysis, pre-registration Section 9, step 3).

Step 3a: label the 100 validation reasons and compare with the hand labels.
  python src/label_reasons.py label --model claude-haiku-5-5
  python src/label_reasons.py agreement --model claude-haiku-5-5

Design notes:
  - The labeler sees only the reason text, like the hand labeling (blind to condition, mode, item and
    behavior).
  - The answer is forced through a tool call whose input schema allows only the codebook labels, so every
    successful answer is a valid label (no free-text parsing).
  - temperature 0, no extended thinking, no rationale field.
  - The full prompt (system text + tool schema) is identified by a SHA-256 hash stored with every record.
    If the codebook file changes, the hash changes and earlier labels are not mixed with new ones.
  - Records are append-only (data/labels/<run>_<model>.jsonl); re-running skips reasons already labeled
    with the same model and prompt hash.
  - The system prompt is marked for prompt caching, which makes the long codebook cheap after the first call.
"""

import argparse
import hashlib
import json
import os
import random

import anthropic
import pandas as pd

from llm import ROOT, append_jsonl   # llm.py also loads .env

LABELS = ["EV", "EV + risk averse", "risk averse", "risk seeking", "loss averse", "vague tradeoff", "other"]
MERGE = {"EV + risk averse": "risk averse"}   # secondary agreement with the two risk-averse labels merged

# USD per 1M tokens, standard rate: input, output, 5-minute cache write, cache read
PRICE_PER_M = {
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
}

CODEBOOK = ROOT / "docs" / "reason_codebook.md"
VALIDATION_XLSX = ROOT / "results" / "reasons" / "validation_reasons.xlsx"

SYSTEM_TEMPLATE = """You label short explanations ("reasons") written by a language model after a choice task.
In the task the model compared, row by row, a lottery with a sure amount (gain or loss items), or a 50/50
gamble (win a gain or lose a loss) with a sure $0 (mixed items). It then wrote a one- or two-sentence reason.

Apply the codebook below exactly. Answer the questions of the decision procedure in order and stop at the
first label that applies. Label only what the reason states; do not guess the item, the instructions the
model was given, or what it actually chose. Then set the names_preference flag as the codebook defines it.
Record your answer with the record_label tool.

<codebook>
{codebook}
</codebook>"""

TOOL = {
    "name": "record_label",
    "description": "Record the codebook label and the names_preference flag for one reason.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": LABELS,
                      "description": "Main label from the decision procedure (first label that applies)."},
            "names_preference": {"type": "boolean",
                                 "description": "True only if the reason uses one of the expressions listed "
                                                "for the names_preference flag (or a close variant)."},
        },
        "required": ["label", "names_preference"],
        "additionalProperties": False,
    },
}


def system_text():
    return SYSTEM_TEMPLATE.format(codebook=CODEBOOK.read_text(encoding="utf-8").strip())


def prompt_hash():
    return hashlib.sha256((system_text() + json.dumps(TOOL, sort_keys=True)).encode()).hexdigest()


def request_params(model, reason):
    """Request body for one reason. Shared by direct calls and (later) the Batch API."""
    return {
        "model": model,
        "max_tokens": 200,
        "temperature": 0,
        "system": [{"type": "text", "text": system_text(), "cache_control": {"type": "ephemeral"}}],
        "tools": [TOOL],
        "tool_choice": {"type": "tool", "name": "record_label"},
        "messages": [{"role": "user", "content": f"<reason>\n{reason}\n</reason>"}],
    }


def summarize_message(msg):
    """Label, flag and call metadata from a Message object."""
    tool_input = next((b.input for b in msg.content if b.type == "tool_use"), None)
    u = msg.usage
    rec = {
        "model_returned": msg.model,
        "message_id": msg.id,
        "stop_reason": msg.stop_reason,
        "tool_input": tool_input,
        "label": None, "names_preference": None,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": u.cache_read_input_tokens or 0,
        "error": None,
    }
    if tool_input and tool_input.get("label") in LABELS and isinstance(tool_input.get("names_preference"), bool):
        rec["label"] = tool_input["label"]
        rec["names_preference"] = tool_input["names_preference"]
    else:
        rec["error"] = "invalid or missing tool input"
    return rec


def cost_usd(rec, model):
    p_in, p_out, p_write, p_read = PRICE_PER_M[model]
    return (rec["input_tokens"] * p_in + rec["output_tokens"] * p_out
            + rec["cache_creation_input_tokens"] * p_write + rec["cache_read_input_tokens"] * p_read) / 1e6


def labels_path(run, model):
    return ROOT / "data" / "labels" / f"{run}_{model}.jsonl"


def load_labels(run, model):
    """Latest successful label per sample_id for this model and the current prompt."""
    path, h, out = labels_path(run, model), prompt_hash(), {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["prompt_sha256"] == h and r["error"] is None:
                    out[r["sample_id"]] = r
    return out


def load_validation(path):
    df = pd.read_excel(path, sheet_name=0)
    df["names_preference"] = df["names_preference"].astype(str).str.strip().str.lower().eq("yes")
    unknown = set(df["label"]) - set(LABELS)
    if unknown:
        raise SystemExit(f"hand labels not in the codebook: {unknown}")
    return df


def cmd_label(args):
    if args.model not in PRICE_PER_M:
        raise SystemExit(f"unknown model {args.model}; add its prices to PRICE_PER_M first")
    df = load_validation(args.xlsx)
    done = load_labels("validation", args.model)
    todo = df[~df["sample_id"].isin(done)]
    print(f"prompt {prompt_hash()[:12]} | {len(done)} already labeled, {len(todo)} to label")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    total = 0.0
    for i, row in enumerate(todo.itertuples(), 1):
        base = {"run": "validation", "sample_id": row.sample_id, "model_requested": args.model,
                "prompt_sha256": prompt_hash()}
        try:
            msg = client.messages.create(**request_params(args.model, row.reason))
            rec = {**base, **summarize_message(msg)}
            total += cost_usd(rec, args.model)
        except anthropic.APIError as e:
            rec = {**base, "error": f"{type(e).__name__}: {e}"}
        append_jsonl(labels_path("validation", args.model), rec)
        if rec["error"]:
            print(f"  {row.sample_id}: ERROR {rec['error'][:200]}")
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} done, ~${total:.4f} so far")
    if len(todo):
        last = rec
        print(f"last call: cache write {last.get('cache_creation_input_tokens')}, "
              f"cache read {last.get('cache_read_input_tokens')}, input {last.get('input_tokens')} tokens")


# ---------- agreement ----------

def kappa(a, b):
    """Unweighted Cohen's kappa for two equal-length label lists."""
    a, b = pd.Series(list(a)), pd.Series(list(b))
    po = (a.values == b.values).mean()
    pa, pb = a.value_counts(normalize=True), b.value_counts(normalize=True)
    pe = sum(pa.get(c, 0) * pb.get(c, 0) for c in set(a) | set(b))
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def boot_ci(a, b, stat, n_boot=2000, seed=0):
    """Percentile 95% CI, resampling reasons (rows) with replacement."""
    rng = random.Random(seed)
    a, b, n = list(a), list(b), len(a)
    vals = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        v = stat([a[i] for i in idx], [b[i] for i in idx])
        if v == v:   # drop nan (all resampled labels identical)
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def pct(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def agreement_block(name, ref, llm):
    k = kappa(ref, llm)
    lo, hi = boot_ci(ref, llm, kappa)
    plo, phi = boot_ci(ref, llm, pct)
    return (f"| {name} | {len(ref)} | {pct(ref, llm):.1%} [{plo:.1%}, {phi:.1%}] "
            f"| {k:.3f} [{lo:.3f}, {hi:.3f}] |")


def cmd_agreement(args):
    df = load_validation(args.xlsx)
    got = load_labels("validation", args.model)
    df = df[df["sample_id"].isin(got)].copy()
    if df.empty:
        raise SystemExit("no labels for this model and prompt yet; run 'label' first")
    df["llm_label"] = df["sample_id"].map(lambda s: got[s]["label"])
    df["llm_flag"] = df["sample_id"].map(lambda s: got[s]["names_preference"])
    ref, llm = df["label"].tolist(), df["llm_label"].tolist()
    ref_m, llm_m = [MERGE.get(x, x) for x in ref], [MERGE.get(x, x) for x in llm]
    flag_ref = ["yes" if x else "no" for x in df["names_preference"]]
    flag_llm = ["yes" if x else "no" for x in df["llm_flag"]]

    cm = pd.crosstab(df["label"], df["llm_label"]).reindex(index=LABELS, columns=LABELS, fill_value=0)
    used = [c for c in LABELS if cm.loc[c].sum() > 0 or cm[c].sum() > 0]
    cm = cm.loc[used, used]
    cm.index.name, cm.columns.name = "hand \\ LLM", None
    per = pd.DataFrame({
        "n_hand": df["label"].value_counts(),
        "n_llm": df["llm_label"].value_counts(),
        "agree": df.loc[df["label"] == df["llm_label"], "label"].value_counts(),
    }).reindex(LABELS).fillna(0).astype(int)
    per["share_of_hand_agreed"] = (per["agree"] / per["n_hand"]).map(lambda x: f"{x:.0%}" if x == x else "-")

    lines = [
        f"# Validation agreement: hand labels vs {args.model}",
        "",
        f"Prompt hash {prompt_hash()[:12]}; {len(df)} reasons; 95% CIs from 2,000 bootstrap resamples of reasons.",
        "Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),",
        "so agreement may be inflated.",
        "",
        "| comparison | n | percent agreement | Cohen's kappa |",
        "|---|---|---|---|",
        agreement_block("main label (7 labels)", ref, llm),
        agreement_block("main label, EV + risk averse merged into risk averse", ref_m, llm_m),
        agreement_block("names_preference flag", flag_ref, flag_llm),
        "",
        "## Confusion matrix (rows: hand label, columns: LLM label)",
        "",
        cm.to_markdown(),
        "",
        "## Per label",
        "",
        per.to_markdown(),
        "",
        "## names_preference (rows: hand, columns: LLM)",
        "",
        pd.crosstab(pd.Series(flag_ref, name="hand"), pd.Series(flag_llm, name="LLM")).to_markdown(),
    ]
    out_dir = ROOT / "results" / "reasons"
    report = out_dir / f"validation_agreement_{args.model}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dis = df[(df["label"] != df["llm_label"]) | (df["names_preference"] != df["llm_flag"])]
    dis_path = out_dir / f"validation_disagreements_{args.model}.csv"
    dis[["sample_id", "reason", "label", "llm_label", "names_preference", "llm_flag", "notes"]].to_csv(
        dis_path, index=False, encoding="utf-8-sig")
    print("\n".join(lines))
    print(f"\nwrote {report.relative_to(ROOT)} and {dis_path.relative_to(ROOT)} ({len(dis)} disagreements)")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("label", "agreement"):
        p = sub.add_parser(name)
        p.add_argument("--model", default="claude-haiku-5-5")
        p.add_argument("--xlsx", default=str(VALIDATION_XLSX), help="hand-labeled validation file")
    args = parser.parse_args()
    {"label": cmd_label, "agreement": cmd_agreement}[args.command](args)


if __name__ == "__main__":
    main()