"""
Label every Reason line of a run with Claude through the Message Batches API (50% price, results within
24 hours). Reason analysis step 3b; the labeler and its setup are validated in label_reasons.py.

Workflow (one labeling run = one folder data/labels/batch/<run>_<model>/):
  1. plan     extract the reasons (same code as reason_sample.py), drop parse_fail responses,
              keep each distinct reason text once, split into parts      -> texts.jsonl, responses.jsonl,
                                                                            settings.json, batches.json
  2. submit   create the batches (re-run to submit further parts)
  3. status   progress of each batch
  4. collect  download finished batches                                  -> data/labels/<run>_<model>.jsonl
  5. retry    put every text without a successful label into a new part, then submit again
  6. merge    one row per response with its label                        -> results/reasons/reason_labels_<run>_<model>.csv
              and a re-labeling check against the validation run (same reasons, separate calls)

Design notes:
  - Requests are built with label_reasons.request_params, so they are identical to the validated setup.
    The prompt hash is stored in settings.json and in every label record; merge refuses to mix hashes.
  - Identical reason texts are labeled once (custom_id = hash of the text) and the label is copied to
    every response with that text. This saves calls and gives identical texts identical labels.
  - Request bodies are not written to disk (each repeats the ~6 KB codebook); they are rebuilt from
    texts.jsonl at submit time.
  - Batch results can be downloaded for 29 days after a batch is created; run collect soon.

Usage:
  python src/label_batch.py plan --run main --name labeltest --model claude-haiku-5-5 --thinking disabled --test 20
  (then the same commands with --name labeltest; for the full run leave out --name and --test)
  python src/label_batch.py plan --run main --model claude-haiku-5-5 --thinking disabled
  python src/label_batch.py submit --run main --model claude-haiku-5-5
  python src/label_batch.py status --run main --model claude-haiku-5-5
  python src/label_batch.py collect --run main --model claude-haiku-5-5
  python src/label_batch.py retry --run main --model claude-haiku-5-5
  python src/label_batch.py merge --run main --model claude-haiku-5-5
"""

import argparse
import csv
import hashlib
import json
import os
import random
from collections import Counter
from datetime import datetime, timezone

import anthropic

import label_reasons as L
from llm import ROOT, append_jsonl
from reason_sample import load_with_reasons

META_FIELDS = ["custom_id", "condition", "mode", "item_id", "item_type", "version", "status",
               "risk_premium_range", "la_ratio"]


def run_dir(args):
    return ROOT / "data" / "labels" / "batch" / f"{args.name or args.run}_{args.model}"


def text_id(reason):
    return "t" + hashlib.sha256(reason.encode("utf-8")).hexdigest()[:24]


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def use_settings(args):
    """Load settings.json and set the labeler to exactly the planned setup."""
    s = load_json(run_dir(args) / "settings.json", None)
    if s is None:
        raise SystemExit("no plan for this run and model; run 'plan' first")
    L.THINKING = s["thinking"]
    if L.prompt_hash() != s["prompt_sha256"]:
        raise SystemExit("the codebook or labeler settings changed since 'plan'; prompts no longer match")
    return s


def get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def done_ids(args, prompt_sha256):
    path = L.labels_path(args.name or args.run, args.model)
    ids = set()
    if path.exists():
        for r in read_jsonl(path):
            if r["error"] is None and r["prompt_sha256"] == prompt_sha256:
                ids.add(r["text_id"])
    return ids


def add_parts(batches, ids, part_size):
    start = len(batches)
    for i in range(0, len(ids), part_size):
        batches[f"part{start + i // part_size:02d}"] = {"text_ids": ids[i:i + part_size], "batch_id": None}
    return [f"part{start + i // part_size:02d}" for i in range(0, len(ids), part_size)]


def cmd_plan(args):
    if args.model not in L.PRICE_PER_M:
        raise SystemExit(f"unknown model {args.model}; add its prices to label_reasons.PRICE_PER_M first")
    d = run_dir(args)
    if (d / "settings.json").exists():
        raise SystemExit(f"{d} already has a plan; use another --run name or delete the folder first")
    L.THINKING = args.thinking
    recs = load_with_reasons(args.run)
    statuses = Counter(r["status"] for r in recs)
    recs = [r for r in recs if r["status"] != "parse_fail"]
    for r in recs:
        r["text_id"] = text_id(r["reason"])
    texts = {}
    for r in recs:
        texts.setdefault(r["text_id"], r["reason"])
    ids = sorted(texts)
    random.Random(f"{args.run}|label-order").shuffle(ids)   # every part mixes all conditions
    if args.test:
        ids = ids[:args.test]
        recs = [r for r in recs if r["text_id"] in set(ids)]

    d.mkdir(parents=True, exist_ok=True)
    with open(d / "texts.jsonl", "w", encoding="utf-8") as f:
        for t in ids:
            f.write(json.dumps({"text_id": t, "reason": texts[t]}) + "\n")
    with open(d / "responses.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps({**{k: r[k] for k in META_FIELDS}, "text_id": r["text_id"]}) + "\n")
    settings = {"run": args.run, "model": args.model, **L.settings(), "prompt_sha256": L.prompt_hash(),
                "planned_at": datetime.now(timezone.utc).isoformat(), "test": args.test}
    save_json(d / "settings.json", settings)
    batches = {}
    names = add_parts(batches, ids, args.part_size)
    save_json(d / "batches.json", batches)

    p_in = L.PRICE_PER_M[args.model][0]
    est = len(ids) * 2500 * p_in / 2 / 1e6        # upper bound: ~2,500 input tokens, no cache hits, batch price
    print(f"responses with a reason: {sum(statuses.values())} {dict(statuses)}")
    print(f"labeled (parse_fail dropped): {len(recs)} responses, {len(ids)} distinct reason texts")
    print(f"prompt {settings['prompt_sha256'][:12]} | thinking {settings['thinking']} | parts {names}")
    print(f"cost upper bound without cache hits: ~${est:.2f}")


def cmd_submit(args):
    d = run_dir(args)
    s = use_settings(args)
    batches = load_json(d / "batches.json", {})
    texts = {r["text_id"]: r["reason"] for r in read_jsonl(d / "texts.jsonl")}
    client = get_client()
    active = sum(1 for info in batches.values() if info["batch_id"]
                 and client.messages.batches.retrieve(info["batch_id"]).processing_status != "ended")
    for name, info in batches.items():
        if info["batch_id"]:
            continue
        if active >= args.max_active:
            print(f"{active} batch(es) still running; run submit again after they end.")
            break
        requests = [{"custom_id": t, "params": L.request_params(s["model"], texts[t])} for t in info["text_ids"]]
        batch = client.messages.batches.create(requests=requests)
        info.update(batch_id=batch.id, submitted_at=datetime.now(timezone.utc).isoformat())
        save_json(d / "batches.json", batches)
        active += 1
        print(f"submitted {name}: {batch.id} ({len(requests)} requests)")
    pending = [n for n, info in batches.items() if not info["batch_id"]]
    print(f"parts not yet submitted: {pending or 'none'}")


def cmd_status(args):
    batches = load_json(run_dir(args) / "batches.json", {})
    client = get_client()
    for name, info in batches.items():
        if not info["batch_id"]:
            print(f"{name}: not submitted")
            continue
        b = client.messages.batches.retrieve(info["batch_id"])
        c = b.request_counts
        print(f"{name}: {b.processing_status:<11} succeeded {c.succeeded}, errored {c.errored}, "
              f"processing {c.processing}, expired {c.expired}, canceled {c.canceled}")


def cmd_collect(args):
    d = run_dir(args)
    s = use_settings(args)
    batches = load_json(d / "batches.json", {})
    have = done_ids(args, s["prompt_sha256"])
    client = get_client()
    added = errors = 0
    cost = 0.0
    for name, info in batches.items():
        if not info["batch_id"]:
            continue
        b = client.messages.batches.retrieve(info["batch_id"])
        if b.processing_status != "ended":
            print(f"{name}: {b.processing_status}, not ready")
            continue
        for entry in client.messages.batches.results(info["batch_id"]):
            if entry.custom_id in have:
                continue
            base = {"run": args.name or args.run, "text_id": entry.custom_id, "batch_id": info["batch_id"],
                    "model_requested": s["model"], "prompt_sha256": s["prompt_sha256"], **L.settings()}
            if entry.result.type == "succeeded":
                rec = {**base, **L.summarize_message(entry.result.message)}
            else:
                err = getattr(entry.result, "error", None)
                rec = {**base, "error": f"{entry.result.type}: {err}"}
            append_jsonl(L.labels_path(args.name or args.run, args.model), rec)
            if rec["error"] is None:
                have.add(entry.custom_id)
                added += 1
                cost += L.cost_usd(rec, s["model"]) / 2
            else:
                errors += 1
        print(f"{name}: ended")
    total = len(read_jsonl(d / "texts.jsonl"))
    print(f"added {added} labels (~${cost:.4f} at batch price), {errors} errors")
    print(f"labeled so far: {len(have)}/{total}; without a label: {total - len(have)}")
    if total - len(have):
        print("When all batches have ended, run 'retry' and then 'submit' for the missing texts.")


def cmd_retry(args):
    d = run_dir(args)
    s = use_settings(args)
    batches = load_json(d / "batches.json", {})
    client = get_client()
    for name, info in batches.items():
        if not info["batch_id"]:
            raise SystemExit(f"{name} is not submitted yet; submit every part before retrying")
        if client.messages.batches.retrieve(info["batch_id"]).processing_status != "ended":
            raise SystemExit(f"{name} has not ended yet; wait, run collect, then retry")
    have = done_ids(args, s["prompt_sha256"])
    missing = [r["text_id"] for r in read_jsonl(d / "texts.jsonl") if r["text_id"] not in have]
    if not missing:
        print("nothing to retry")
        return
    names = add_parts(batches, missing, args.part_size)
    save_json(d / "batches.json", batches)
    print(f"{len(missing)} texts put into new part(s) {names}; now run submit.")


def cmd_merge(args):
    d = run_dir(args)
    s = use_settings(args)
    labels = {}
    for r in read_jsonl(L.labels_path(args.name or args.run, args.model)):
        if r["error"] is None and r["prompt_sha256"] == s["prompt_sha256"]:
            labels[r["text_id"]] = r
    responses = read_jsonl(d / "responses.jsonl")
    out = ROOT / "results" / "reasons" / f"reason_labels_{args.name or args.run}_{args.model}.csv"
    texts = {r["text_id"]: r["reason"] for r in read_jsonl(d / "texts.jsonl")}
    fields = META_FIELDS + ["text_id", "label", "names_preference", "reason"]
    missing = 0
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in responses:
            lab = labels.get(r["text_id"])
            missing += lab is None
            w.writerow({**r, "reason": texts[r["text_id"]],
                        "label": lab["label"] if lab else "",
                        "names_preference": ("yes" if lab["names_preference"] else "no") if lab else ""})
    print(f"wrote {out.relative_to(ROOT)}: {len(responses)} responses, {missing} without a label")
    counts = Counter(labels[r["text_id"]]["label"] for r in responses if r["text_id"] in labels)
    print("labels over responses:", dict(counts.most_common()))

    # Re-labeling check: the validation reasons were labeled before in separate calls with the same setup
    val = L.load_labels("validation", args.model)
    if val:
        df = L.load_validation(L.VALIDATION_XLSX)
        pairs = [(val[sid]["label"], labels[text_id(reason)]["label"])
                 for sid, reason in zip(df["sample_id"], df["reason"])
                 if sid in val and text_id(reason) in labels]
        if pairs:
            a, b = zip(*pairs)
            print(f"re-labeling check on {len(pairs)} validation reasons: same label {L.pct(a, b):.1%}, "
                  f"kappa {L.kappa(a, b):.3f}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "submit", "status", "collect", "retry", "merge"):
        p = sub.add_parser(name)
        p.add_argument("--run", default="main")
        p.add_argument("--model", default="claude-haiku-5-5")
        p.add_argument("--name", default=None, help="name of the labeling run (default: --run), e.g. labeltest")
        if name == "plan":
            p.add_argument("--thinking", choices=["between_tools", "disabled", "adaptive"], required=True)
            p.add_argument("--test", type=int, default=None, help="plan only this many (random) reason texts")
        if name in ("plan", "retry"):
            p.add_argument("--part-size", type=int, default=5000, help="requests per batch (size limit 256 MB)")
        if name == "submit":
            p.add_argument("--max-active", type=int, default=2, help="batches allowed to run at the same time")
    args = parser.parse_args()
    {"plan": cmd_plan, "submit": cmd_submit, "status": cmd_status, "collect": cmd_collect,
     "retry": cmd_retry, "merge": cmd_merge}[args.command](args)


if __name__ == "__main__":
    main()