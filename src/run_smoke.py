"""
Smoke test: baseline condition, every item x both versions x both reasoning modes, 1 sample each
(60 x 2 x 2 = 240 calls).

Goal: check the full pipeline on real responses and measure parse/competence rates,
reasoning-token usage, and mixed-item censoring before the pilot.

Raw records are appended to data/raw/<run>.jsonl. If the script is interrupted or
some calls fail, re-running it makes only the calls that have not yet succeeded.

Usage:
  python src/run_smoke.py                                           # shuffled rows, both modes
  python src/run_smoke.py --run smoke_sorted --modes none --no-shuffle   # sorted-order control
  python src/run_smoke.py --run smoke_fullrow --modes none --full-rows   # lottery in every row
  python src/run_smoke.py --run smoke_cot --condition cot --full-rows      # another condition
  python src/run_smoke.py --run check_oneshot_gain --condition oneshot_gain --full-rows --sample 6
                                                    # format check only: 6 random calls
  python src/run_smoke.py --run pilot --full-rows --samples 20 --items gain_03 gain_16 loss_03 loss_16 mixed_A_05 mixed_B_08
                                                    # pilot: repeated samples of selected items
"""

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm import ROOT, append_jsonl, call_model, cost_usd, get_client
from prompts import CONDITIONS, build_prompt, load_items

VERSIONS = [1, 2]
MAX_WORKERS = 8   # number of requests sent in parallel


def done_keys(out_path):
    """(item_id, version, reasoning_effort, sample) of calls that already succeeded."""
    keys = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("error") is None:
                    keys.add((r["item_id"], r["version"], r["reasoning_effort"], r.get("sample", 0)))
    return keys


def run_one(run, condition, item, version, mode, shuffle, full_rows, sample):
    # Seeded per call, so the row order is reproducible; it is also saved in the record.
    seed = f"{run}|{item['item_id']}|{version}|{mode}" + (f"|{sample}" if sample else "")
    rng = random.Random(seed)
    prompt = build_prompt(item, version, rng, condition=condition, shuffle=shuffle, full_rows=full_rows)
    base = {"run": run, "sample": sample, **prompt}
    try:
        call = call_model(prompt["system"], prompt["user"], reasoning_effort=mode,
                          long_output=prompt["long_output"])
        return {**base, **call, "error": None}
    except Exception as e:  # record the failure and keep going
        return {**base, "reasoning_effort": mode, "error": repr(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="smoke_test", help="run name; also the output file name")
    parser.add_argument("--condition", default="baseline", help="experimental condition (see prompts.CONDITIONS)")
    parser.add_argument("--modes", nargs="+", default=["none", "high"], help="reasoning efforts")
    parser.add_argument("--no-shuffle", action="store_true", help="show rows in sorted order")
    parser.add_argument("--full-rows", action="store_true", help="gain/loss: spell out the lottery in every row")
    parser.add_argument("--sample", type=int, default=None, help="run only this many randomly chosen calls")
    parser.add_argument("--samples", type=int, default=1, help="repeated calls per item x version x mode")
    parser.add_argument("--items", nargs="+", default=None, help="only these item_ids")
    args = parser.parse_args()
    if args.condition not in CONDITIONS:
        parser.error(f"unknown condition {args.condition!r}; choose from {list(CONDITIONS)}")
    out_path = ROOT / "data" / "raw" / f"{args.run}.jsonl"
    shuffle = not args.no_shuffle

    get_client()  # create the API client once before starting threads
    items = load_items()
    skip = done_keys(out_path)
    types = CONDITIONS[args.condition].get("item_types", ["gain", "loss", "mixed"])
    if args.items:
        unknown = set(args.items) - {it["item_id"] for it in items}
        if unknown:
            parser.error(f"unknown item_ids: {sorted(unknown)}")
        items = [it for it in items if it["item_id"] in args.items]
    tasks = [(args.run, args.condition, it, v, m, shuffle, args.full_rows, k)
             for m in args.modes for it in items for v in VERSIONS for k in range(args.samples)
             if it["item_type"] in types and (it["item_id"], v, m, k) not in skip]
    if args.sample is not None:
        tasks = random.Random(0).sample(tasks, min(args.sample, len(tasks)))
    print(f"{len(tasks)} calls to make ({len(skip)} already done)")

    total_cost, n_err = 0.0, 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(run_one, *t) for t in tasks]
        for i, fut in enumerate(as_completed(futures), start=1):
            rec = fut.result()
            append_jsonl(out_path, rec)  # written from the main thread only
            if rec["error"]:
                n_err += 1
            else:
                total_cost += cost_usd(rec)
            if i % 20 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} done | errors {n_err} | cost so far ~ ${total_cost:.4f}")
    print(f"Finished. Raw records: {out_path}")
    if n_err:
        print("Some calls failed; run the script again to retry them.")


if __name__ == "__main__":
    main()