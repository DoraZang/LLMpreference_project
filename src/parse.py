"""
Parse model responses, run the competence check, and compute metrics.

For each response:
  1. Parse: read the A/B choice for each of the 12 rows and the Reason.
     Lenient on form (case, markdown bold, "Option A"), strict on content
     (every row exactly once, answer exactly A or B).
     If the response contains an "Answers:" line (CoT format), only the text after the last
     such line is parsed, so row mentions inside the written reasoning are ignored.
  2. Restore order: use row_order (saved when the prompt was built) to sort the
     choices by sure amount (gain/loss items) or by gain/loss ratio (mixed items).
  3. Competence check, in this order:
       parse_fail          - could not read all 12 rows
       non_monotonic       - more than one switch, or a switch in the wrong direction
       dominance_violation - gain/loss only: wrong choice at an endpoint
       valid
  4. Metrics (valid responses only):
       gain/loss: certainty equivalent CE = arithmetic midpoint of the switch interval;
                  risk premium = (EV - CE) / |EV|
                  range-normalized risk premium = (EV - CE) / |x_high - x_low|
       mixed:     loss-aversion ratio = geometric midpoint of the switch interval
                  (ratios are log-spaced); no switch -> censored at the range boundary

Design decisions: notes/lab_log.md (2026-10-25).
"""

import math
import re

N_ROWS = 12

ROW_RE = re.compile(r"^row\s*(\d+)\s*[:\-]\s*(?:option\s*)?([ab])\s*\.?$", re.IGNORECASE)
REASON_RE = re.compile(r"^reason\s*:\s*(.*)$", re.IGNORECASE | re.DOTALL)
ANSWERS_RE = re.compile(r"^answers\s*:?\s*$", re.IGNORECASE)

def parse_response(text):
    """Return (choices, reason). choices maps displayed row number -> 'A'/'B', or is None on failure."""
    choices, reason = {}, None
    lines = [line.replace("*", "").replace("_", "").strip() for line in text.strip().splitlines()]
    markers = [i for i, line in enumerate(lines) if ANSWERS_RE.match(line)]
    if markers:                            # CoT format: skip the written reasoning
        lines = lines[markers[-1] + 1:]
    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if m:
            row_num, answer = int(m.group(1)), m.group(2).upper()
            if row_num in choices or not 1 <= row_num <= N_ROWS:
                return None, None          # duplicate or out-of-range row
            choices[row_num] = answer
            continue
        m = REASON_RE.match(line)
        if m:
            reason = " ".join([m.group(1)] + lines[i + 1:]).strip()
            break
    if len(choices) != N_ROWS:
        return None, reason                # missing rows
    return choices, reason


def sorted_states(item, prompt, choices):
    """Return (keys, states) sorted by key ascending.

    gain/loss: key = sure amount; state = True if the sure amount was chosen.
    mixed:     key = gain/loss ratio; state = True if the lottery was chosen.
    In both cases a consistent respondent goes from False to True exactly once.
    """
    pairs = []
    for k, idx in enumerate(prompt["row_order"]):
        took_lottery = choices[k + 1] == prompt["lottery_option"]
        if item["item_type"] in ("gain", "loss"):
            pairs.append((item["options"][idx], not took_lottery))
        else:
            pairs.append((item["rows"][idx]["ratio"], took_lottery))
    pairs.sort()
    return [p[0] for p in pairs], [p[1] for p in pairs]


def analyze(item, prompt, response_text):
    """Parse one response and return a result record."""
    result = {
        "item_id": item["item_id"], "item_type": item["item_type"],
        "version": prompt["version"], "status": None, "pattern": None,
        "n_switches": None, "ce": None, "risk_premium": None, "risk_premium_range": None,
        "la_ratio": None, "censored": None, "reason": None,
    }
    choices, reason = parse_response(response_text)
    result["reason"] = reason
    if choices is None:
        result["status"] = "parse_fail"
        return result

    keys, states = sorted_states(item, prompt, choices)
    result["pattern"] = "".join("1" if s else "0" for s in states)
    switches = [i for i in range(1, N_ROWS) if states[i] != states[i - 1]]
    result["n_switches"] = len(switches)

    # Consistent pattern: 0...0 1...1 (at most one switch, from 0 to 1)
    if len(switches) > 1 or (len(switches) == 1 and states[0]):
        result["status"] = "non_monotonic"
        return result

    if item["item_type"] in ("gain", "loss"):
        # Lowest sure amount: the lottery dominates; highest sure amount: the sure option dominates
        if states[0] or not states[-1]:
            result["status"] = "dominance_violation"
            return result
        i = switches[0]
        ce = (keys[i - 1] + keys[i]) / 2
        result["ce"] = round(ce, 4)
        result["risk_premium"] = round((item["ev"] - ce) / abs(item["ev"]), 4)
        result["risk_premium_range"] = round((item["ev"] - ce) / abs(item["x_high"] - item["x_low"]), 4)
    else:
        if not switches:   # never switched: outside the measured range
            result["censored"] = "high" if not states[0] else "low"
            result["la_ratio"] = keys[-1] if not states[0] else keys[0]
        else:
            i = switches[0]
            result["censored"] = None
            result["la_ratio"] = round(math.sqrt(keys[i - 1] * keys[i]), 4)

    result["status"] = "valid"
    return result


if __name__ == "__main__":
    # Demo with hand-made responses. No API calls are made.
    import random
    from prompts import build_prompt, load_items

    items = {it["item_id"]: it for it in load_items()}
    rng = random.Random(0)

    def fake_response(item, prompt, rule, style="plain"):
        """Answer every displayed row with rule(key) -> True/False (True = state 1)."""
        lines = []
        for k, idx in enumerate(prompt["row_order"]):
            if item["item_type"] in ("gain", "loss"):
                take_sure = rule(item["options"][idx])
                lottery = not take_sure
            else:
                lottery = rule(item["rows"][idx]["ratio"])
            letter = prompt["lottery_option"] if lottery else ("B" if prompt["lottery_option"] == "A" else "A")
            if style == "plain":
                lines.append(f"Row {k + 1}: {letter}")
            else:  # formatting variants a lenient parser should accept
                lines.append(f"**row {k + 1}:** Option {letter.lower()}.")
        lines.append("Reason: I compared each sure amount with the lottery.")
        return "\n".join(lines)

    cases = [
        ("gain_03", 1, lambda x: x >= 5.3, "plain", "takes sure amounts >= $5.30"),
        ("gain_03", 2, lambda x: x >= 5.3, "fancy", "same rule, version 2, messy formatting"),
        ("loss_03", 1, lambda x: x >= -6.5, "plain", "accepts sure losses no worse than -$6.50"),
        ("gain_03", 1, lambda x: random.random() < 0.5, "plain", "random answers"),
        ("gain_03", 1, lambda x: True, "plain", "always takes the sure amount"),
        ("mixed_A_05", 1, lambda r: r >= 2.0, "plain", "plays if G/L >= 2"),
        ("mixed_B_05", 2, lambda r: r >= 2.0, "plain", "same rule, direction B, version 2"),
        ("mixed_A_05", 1, lambda r: False, "plain", "never plays"),
    ]
    for item_id, version, rule, style, label in cases:
        item = items[item_id]
        prompt = build_prompt(item, version, rng)
        res = analyze(item, prompt, fake_response(item, prompt, rule, style))
        print(f"{item_id} v{version} | {label}")
        print(f"   status={res['status']}  pattern={res['pattern']}  ce={res['ce']}  "
              f"risk_premium={res['risk_premium']}  la_ratio={res['la_ratio']}  censored={res['censored']}")

    # A response with a missing row
    item = items["gain_03"]
    prompt = build_prompt(item, 1, rng)
    broken = "\n".join(fake_response(item, prompt, lambda x: x >= 5.3).splitlines()[1:])
    print("gain_03 v1 | Row 1 missing")
    print("   status =", analyze(item, prompt, broken)["status"])