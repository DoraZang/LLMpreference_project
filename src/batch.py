"""
Run an experiment through the OpenAI Batch API (50% price, results within 24 hours).

Workflow (one run = one folder data/batch/<run>/):
  1. plan     build every request and split them into parts      -> requests_partNN.jsonl, meta.jsonl
  2. submit   upload parts and create batches                    -> batches.json
  3. status   show the progress of each batch
  4. collect  download finished batches, convert them to raw records
              in the same format as run_smoke.py                  -> data/raw/<run>.jsonl
  5. retry    put every request without a successful result into a new part, then submit again

Design notes:
  - Requests are built with the same code as direct calls (prompts.build_prompt, llm.request_params).
  - Rows are shuffled independently on every call (pre-registration, Section 2.3); the seed includes the
    run, condition, item, version, mode and sample, so every prompt can be rebuilt exactly.
  - Raw records do not store the full prompt text (it would make the data file too large for GitHub);
    they store everything needed to rebuild it plus a SHA-256 hash of the exact system and user text.
  - All requests of a run are shuffled before being split into parts, so every part mixes all
    conditions; a model change during the run would then affect all conditions alike.

Usage:
  python src/batch.py plan --run batchtest --test 20          # small end-to-end test
  python src/batch.py plan --run main --part-size 3000         # the pre-registered main experiment
  python src/batch.py submit --run main --max-active 1         # submit pending parts (re-run to submit more)
  python src/batch.py status --run main
  python src/batch.py collect --run main
  python src/batch.py retry --run main
"""

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone

from openai.types.responses import Response

from llm import ROOT, append_jsonl, cost_usd, get_client, request_params, summarize_response
from prompts import CONDITIONS, build_prompt, load_items

# Pre-registered design (docs/preregistration.md, Section 2.5)
MAIN_CONDITIONS = ["baseline", "direct_risk_tech", "direct_risk_plain", "oneshot_gain",
                   "direct_loss_tech", "direct_loss_plain", "oneshot_loss", "oneshot_mixed", "cot"]
SAMPLES = {"none": 20, "high": 5}
EV_HINT_SAMPLES = 20          # ev_hint: reasoning "none" only, gain/loss items only
VERSIONS = [1, 2]


def run_dir(run):
    return ROOT / "data" / "batch" / run


def custom_id(task):
    return f"{task['condition']}|{task['item_id']}|{task['version']}|{task['mode']}|{task['sample']}"


def main_tasks():
    """Every call of the pre-registered main experiment."""
    tasks = []
    for item in load_items():
        for version in VERSIONS:
            for mode, n in SAMPLES.items():
                for condition in MAIN_CONDITIONS:
                    for sample in range(n):
                        tasks.append(dict(condition=condition, item_id=item["item_id"], version=version,
                                          mode=mode, sample=sample))
            if item["item_type"] in CONDITIONS["ev_hint"]["item_types"]:
                for sample in range(EV_HINT_SAMPLES):
                    tasks.append(dict(condition="ev_hint", item_id=item["item_id"], version=version,
                                      mode="none", sample=sample))
    return tasks


def build_request(run, task, items):
    """(request line, metadata record) for one task."""
    seed = f"{run}|{task['condition']}|{task['item_id']}|{task['version']}|{task['mode']}|{task['sample']}"
    prompt = build_prompt(items[task["item_id"]], task["version"], random.Random(seed),
                          condition=task["condition"], shuffle=True, full_rows=True)
    params = request_params(prompt["system"], prompt["user"], reasoning_effort=task["mode"],
                            long_output=prompt["long_output"])
    cid = custom_id(task)
    request = {"custom_id": cid, "method": "POST", "url": "/v1/responses", "body": params}
    meta = {k: v for k, v in prompt.items() if k not in ("system", "user")}
    meta.update(run=run, custom_id=cid, sample=task["sample"], reasoning_effort=task["mode"],
                prompt_sha256=hashlib.sha256((prompt["system"] + "\n\n" + prompt["user"]).encode()).hexdigest())
    return request, meta


def write_parts(run, requests, part_size, start_index):
    """Write requests into part files numbered from start_index; return the new part names."""
    names = []
    for i in range(0, len(requests), part_size):
        name = f"part{start_index + i // part_size:02d}"
        path = run_dir(run) / f"requests_{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in requests[i:i + part_size]:
                f.write(json.dumps(r) + "\n")
        est_tokens = sum(len(r["body"]["instructions"]) + len(r["body"]["input"])
                         for r in requests[i:i + part_size]) // 4
        print(f"  {path.name}: {len(requests[i:i + part_size])} requests, ~{est_tokens / 1e6:.1f}M input tokens")
        names.append(name)
    return names


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cmd_plan(args):
    d = run_dir(args.run)
    if (d / "meta.jsonl").exists():
        raise SystemExit(f"{d} already has a plan; use a new run name or delete the folder first.")
    d.mkdir(parents=True, exist_ok=True)
    items = {it["item_id"]: it for it in load_items()}
    tasks = main_tasks()
    rng = random.Random(f"{args.run}|order")
    rng.shuffle(tasks)
    if args.test:
        tasks = tasks[:args.test]
    requests, metas = [], []
    for t in tasks:
        req, meta = build_request(args.run, t, items)
        requests.append(req)
        metas.append(meta)
    with open(d / "meta.jsonl", "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m) + "\n")
    print(f"{len(requests)} requests planned for run '{args.run}'")
    names = write_parts(args.run, requests, args.part_size, 0)
    save_json(d / "batches.json", {name: None for name in names})


def cmd_submit(args):
    d = run_dir(args.run)
    batches = load_json(d / "batches.json", {})
    client = get_client()
    active = 0
    for name, info in batches.items():
        if info and client.batches.retrieve(info["batch_id"]).status in ("validating", "in_progress", "finalizing"):
            active += 1
    for name, info in batches.items():
        if info is not None:
            continue
        if active >= args.max_active:
            print(f"{active} batch(es) still running; run submit again after they finish.")
            break
        with open(d / f"requests_{name}.jsonl", "rb") as f:
            file = client.files.create(file=f, purpose="batch")
        batch = client.batches.create(input_file_id=file.id, endpoint="/v1/responses",
                                      completion_window="24h", metadata={"run": args.run, "part": name})
        batches[name] = {"batch_id": batch.id, "input_file_id": file.id,
                         "submitted_at": datetime.now(timezone.utc).isoformat()}
        save_json(d / "batches.json", batches)
        active += 1
        print(f"submitted {name}: {batch.id}")
    pending = [n for n, info in batches.items() if info is None]
    print(f"parts not yet submitted: {pending or 'none'}")


def cmd_status(args):
    batches = load_json(run_dir(args.run) / "batches.json", {})
    client = get_client()
    for name, info in batches.items():
        if info is None:
            print(f"{name}: not submitted")
            continue
        b = client.batches.retrieve(info["batch_id"])
        c = b.request_counts
        print(f"{name}: {b.status:<11} completed {c.completed}/{c.total}, failed {c.failed}")
        if b.errors and b.errors.data:
            for e in b.errors.data[:3]:
                print(f"    error: {e.code} {e.message}")


def done_ids(raw_path):
    ids = set()
    if raw_path.exists():
        with open(raw_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("error") is None:
                    ids.add(r["custom_id"])
    return ids


def convert_line(line, metas, batch_id):
    """One Batch API output (or error) line -> raw record in the run_smoke.py format."""
    meta = metas[line["custom_id"]]
    base = {**meta, "batch_id": batch_id}
    resp = line.get("response") or {}
    if line.get("error") or resp.get("status_code") != 200:
        return {**base, "error": json.dumps(line.get("error") or resp.get("body"))}
    response = Response.model_validate(resp["body"])
    params = {"model": response.model, "reasoning": {"effort": meta["reasoning_effort"]},
              "temperature": 1 if meta["reasoning_effort"] == "none" else None,
              "max_output_tokens": response.max_output_tokens}
    call = summarize_response(response, params)
    call["model_requested"] = resp["body"].get("model")
    return {**base, **call, "error": None}


def cmd_collect(args):
    d = run_dir(args.run)
    raw_path = ROOT / "data" / "raw" / f"{args.run}.jsonl"
    metas = {}
    with open(d / "meta.jsonl", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            metas[m["custom_id"]] = m
    batches = load_json(d / "batches.json", {})
    client = get_client()
    have = done_ids(raw_path)
    added = cost = 0
    for name, info in batches.items():
        if info is None:
            continue
        b = client.batches.retrieve(info["batch_id"])
        if b.status not in ("completed", "expired", "cancelled", "failed"):
            print(f"{name}: {b.status}, not ready")
            continue
        for kind, file_id in (("output", b.output_file_id), ("errors", b.error_file_id)):
            if not file_id:
                continue
            local = d / f"{kind}_{name}.jsonl"
            if not local.exists():
                local.write_bytes(client.files.content(file_id).read())
            with open(local, encoding="utf-8") as f:
                for text in f:
                    line = json.loads(text)
                    if line["custom_id"] in have:
                        continue
                    rec = convert_line(line, metas, info["batch_id"])
                    append_jsonl(raw_path, rec)
                    if rec["error"] is None:
                        have.add(line["custom_id"])
                        added += 1
                        cost += cost_usd(rec)
        print(f"{name}: {b.status}")
    missing = len(set(metas) - have)
    print(f"added {added} successful records to {raw_path.name} (~${cost / 2:.4f} at batch price)")
    print(f"successful so far: {len(have)}/{len(metas)}; without a successful result: {missing}")
    if missing:
        print("When all batches have finished, run 'retry' to resubmit the missing requests.")


def cmd_retry(args):
    d = run_dir(args.run)
    raw_path = ROOT / "data" / "raw" / f"{args.run}.jsonl"
    have = done_ids(raw_path)
    items = {it["item_id"]: it for it in load_items()}
    requests = []
    with open(d / "meta.jsonl", encoding="utf-8") as f:
        for text in f:
            m = json.loads(text)
            if m["custom_id"] in have:
                continue
            task = dict(condition=m["condition"], item_id=m["item_id"], version=m["version"],
                        mode=m["reasoning_effort"], sample=m["sample"])
            req, meta = build_request(args.run, task, items)
            if meta["prompt_sha256"] != m["prompt_sha256"]:
                raise SystemExit(f"prompt for {m['custom_id']} no longer matches the plan; prompts were changed.")
            requests.append(req)
    if not requests:
        print("nothing to retry")
        return
    batches = load_json(d / "batches.json", {})
    names = write_parts(args.run, requests, args.part_size, len(batches))
    batches.update({name: None for name in names})
    save_json(d / "batches.json", batches)
    print(f"{len(requests)} requests put into new part(s) {names}; now run submit.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "submit", "status", "collect", "retry"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        if name in ("plan", "retry"):
            p.add_argument("--part-size", type=int, default=3000, help="requests per batch file")
        if name == "plan":
            p.add_argument("--test", type=int, default=None, help="plan only this many (random) requests")
        if name == "submit":
            p.add_argument("--max-active", type=int, default=1, help="batches allowed to run at the same time")
    args = parser.parse_args()
    {"plan": cmd_plan, "submit": cmd_submit, "status": cmd_status,
     "collect": cmd_collect, "retry": cmd_retry}[args.command](args)


if __name__ == "__main__":
    main()