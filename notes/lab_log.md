## 2026-10-11
- set up the structue & plan for project
- Structure: with probability p receive x_high, otherwise x_low. Loss items are gain items with all amounts negated.
- Probabilities p: 10%, 30%, 50%, 70%, 90% (3 moderate + 2 extreme).
- Magnitudes x_high: $10 and $1000 (100x apart; discussed with mentor).
- Ratio r = x_low / x_high: 0.2 and 0.5. The two magnitudes differ only by a scale factor,
  so any difference between them can be attributed to stake size alone.
- Dropped items with x_low = 0 (the original paper did not use them either).
- 5 x 2 x 2 = 20 items per domain.
- Options: 12 equally spaced sure amounts including both endpoints, presented in random order.
  Expected value is not shown to the model.
  - With 12 options, no option falls exactly at 10/30/50/70/90% of the range,
    so no option ever equals the EV (avoids indifference ties for risk-neutral responses).
  - The same spacing is used for every item, so the option layout carries no information about EV.
- Analysis: the primary analysis uses all 20 items; moderate-probability (12) and
  extreme-probability (8) items are reported separately as a secondary analysis.
- Revision: initially decided to use moderate probabilities only; changed to 3 moderate + 2 extreme
  because items at 30% vs 40% are too similar and add little independent information.
- Known limitation: on extreme-probability items the EV lies close to one end of the range,
  so shifts toward that end may be censored. Interpret these items with caution.


## 2026-10-11 Item design: mixed lotteries

- Purpose: measure loss aversion (lambda proxy).
- Format: 50/50 gamble "win G or lose L"; on each row the model decides whether to play
  (declining = receiving $0). Probability fixed at 50% so that gain and loss probability
  weights are as close to equal as possible.
- Two elicitation directions:
  - Direction A: fix L, vary G across rows; metric G*/L, where G* is the smallest G accepted.
  - Direction B: fix G, vary L across rows; metric G/L*, where L* is the largest L accepted.
  If the model's loss aversion is stable, the two directions should give similar ratios.
  A systematic difference would indicate that responses depend on elicitation procedure.
- Anchor amounts: 10 log-spaced values from $10 to $1000, rounded to whole dollars
  ($10, $17, $28, $46, $77, $129, $215, $359, $599, $1000). The same values are used as L in
  Direction A and as G in Direction B, so the two directions can be paired at each amount.
- 10 amounts x 2 directions = 20 items.
- Rows: 12 gain/loss ratios, log-spaced from 0.5 to 5 (ratio_k = 0.5 * 10^(k/11), k = 0..11).
  Direction A uses G = ratio_k * L; Direction B uses L = G / ratio_k.
  - Log spacing: lambda is a ratio, so each step represents the same relative change.
  - Ratios below 1 have negative EV and should be rejected (built-in sanity check).
  - No row has ratio exactly 1 (EV = 0), avoiding indifference ties.
  - Upper bound 5 leaves room above typical human values (~2), since interventions aim to
    increase loss aversion.
- Status: provisional. Revisit after the smoke test, in particular whether baseline
  responses cluster near either end of the ratio range.
- Open for prompt design: keep the meaning of accept/reject consistent across gain, loss,
  and mixed items.


  lottery and the other is a sure amount (for mixed items, the sure amount is $0).
  Chosen over the original accept/reject wording so that all three item types share the same
  structure, parser, and competence check.
- Label counterbalancing: the two paraphrase versions swap labels
  (version 1: A = lottery, B = sure amount; version 2: A = sure amount, B = lottery).
  Averaging over versions cancels any label/position bias; comparing versions measures it.
- Message structure: rules and answer format in the system message; the item in the user message.
  Interventions will be inserted into the system message, before the rules
  (consistent with how the original paper's age prompts modify the premise).
  To check: how the chosen model handles system messages.
- Row order: shuffled independently on every call. The displayed order is saved with each raw
  response, so every response can be reconstructed. If the smoke test shows many non-monotonic
  responses due to shuffling, revert to sorted order.
- Row labels: numbered rows ("Row 1: A"), not repeated amounts. Shorter output, fewer copying
  errors; rows are mapped back to amounts using the saved order.
- Random-row rule: the instructions state that one row will be randomly selected and carried out,
  so each row is an independent choice (standard in experimental economics).
- Reason length: limited to one or two sentences, plus a max output token cap per call,
  to control output cost.
- Cost check: none of these decisions changes the number of calls; numbered rows reduce output tokens.

## 2026-10-25 Prompt design: baseline wording

- Amounts shown with signs (e.g. "-$77.00"), as in the original paper; the system message states
  that positive amounts are received and negative amounts are lost. Verbs are neutral
  ("a 50% chance of $10.00"), not "win"/"lose".
- Neutral wording: no "risk", "safe", "gamble", no expected value, no persona.
  The term "lottery" is used ("bet"/"gamble" carry risk connotations).
- Both outcome probabilities are stated explicitly; all amounts have two decimals.
- Gain/loss items: the lottery is described once at the top; each row offers "play the lottery"
  vs a sure amount. Mixed items: each row describes its own lottery vs "$0.00 for sure".
- The answer format lists all 12 rows explicitly (no "...").
- Two versions per condition differ ONLY in label assignment (A = lottery vs A = sure amount);
  wording is identical. Wording robustness is partly covered by the technical vs plain-language
  intervention conditions.
- Templates: prompts/system_baseline.txt, prompts/user_gain_loss.txt, prompts/user_mixed.txt.

## 2026-10-25 Connection test (1 call, gain_03, version 1, reasoning "none")

- Call succeeded: status "completed", 522 input / 118 output tokens, 0 reasoning tokens
  (confirms that "none" produced no reasoning on this call), cost ~$0.00011.
- The API returned only the alias "gpt-6-luna", not a dated version, so silent model updates
  cannot be detected from the response. Remaining safeguards: submit all conditions together,
  record call dates.
- Response classified non_monotonic (pattern 000000111110): consistent risk-neutral switching
  around EV = $6 on 11 rows, but the lottery was chosen over a sure $10.00 (a dominated choice).
- Observations from this single response (not conclusions):
  - Without an EV hint, the model computed the EV itself ("The lottery has an expected value of $6").
  - The stated reason refers to "exactly $6", which is not one of the options.
  - The error row (displayed as Row 7) sits inside a run of six identical answers (Rows 5-10).
    Hypothesis to check in the smoke test: errors in shuffled lists may follow neighboring answers.


## 2026-10-25 Smoke test results (baseline, 60 items x 2 versions x 2 modes, 1 sample each)

- 240/240 calls succeeded; no parse failures; no truncated responses.
- Competence (valid rate):
  - reasoning "none": gain 70.0%, loss 52.5%, mixed 95.0% (overall 72.5%) -> below the 80% criterion.
  - reasoning "high": 100% on all item types.
- Tokens/cost: "none" ~115 output tokens, 0 reasoning tokens, ~$0.00012/call;
  "high" mean 170 reasoning tokens (max 456), ~$0.0002/call -- far below the earlier estimate.
- Neighbor ("inertia") hypothesis NOT supported: in invalid responses, error rows matched the row
  above 31.9% of the time vs 62.3% for other rows.
- First look at metrics (1 sample per item; indicative only):
  - "high": risk premium median 0.000 for gains and losses -> behaves as an EV maximizer.
  - "none": gains mean -0.207 (risk-seeking), losses mean +0.417 (risk-averse) -- the reverse of the
    human reflection effect. Possible mechanism to check with the Reason field: attraction to the
    largest gain / avoidance of the largest loss in the lottery. Caveats: small n; 45% of loss
    responses excluded as invalid (possible selection bias); see risk-premium scaling note below.
  - Mixed: median loss-aversion ratio 1.04 in both modes = the interval containing 1 (EV = 0),
    i.e. consistent with switching at the sign of EV, not with loss aversion. No censoring.
- Decisions:
  - A. Run a sorted-order control (reasoning "none", 120 calls) before deciding whether to keep
    shuffled rows.
  - B. Run every main condition in both reasoning modes (not only the baseline);
    adds ~9,600 calls, ~$2-3 at measured prices.
  - C. Also compute a range-normalized risk premium, (EV - CE) / |x_high - x_low|, because the
    EV-normalized version has very different resolution across items (one option step is 26% of EV
    for "10% of $10, else $2" but 12% for "50% of $10, else $2"). The primary metric will be fixed
    in the pre-registration.

## 2026-11-08 Pending decisions confirmed; direct-instruction conditions

- Confirmed (proposed on 2026-10-25):
  - Main experiment uses shuffled rows with the full lottery in every gain/loss row.
  - No further format changes to reach the 80% valid-rate threshold; the low valid rate of the
    non-reasoning mode is reported as a finding.
  - Valid rate is an outcome measure per condition; sensitivity analysis includes invalid responses
    using the closest consistent switch point.
- Not adopted: describing the task as a "gambling game". The word carries connotations that could
  shift risk attitudes, and the baseline is fixed after the smoke tests. Possible future work:
  a framing condition testing the effect of the word "gambling".
- Direct conditions (prompts/interventions/): placed at the start of the system message, before the
  unchanged baseline rules. All begin "In this task, ...".
  - Technical versions state only the term ("risk averse", "loss averse"), with no definition,
    to test whether the model can translate the label into choices.
  - Plain-language versions describe the same preference without the term or the words
    "expected value"; the risk version uses "outcome" so it applies to both gains and losses.
  - Neither version tells the model which option to choose.
  - Known limitation: the versions are not matched in length or strength (the plain risk version
    includes the definition). Accepted and to be noted in the report.
- Code: prompts.py now builds the system message from CONDITIONS; each prompt record stores its condition.

## 2026-11-08 Zero-shot CoT condition

- Trigger phrase: "Let's think step by step." (Kojima et al.), as in the original paper's CoT condition.
- CoT changes the answer format: "Reasoning:" first, then an "Answers:" line, the 12 rows, and
  "Reason:". The Reason line is kept so that all conditions have a comparable short reason for the
  reason analysis. Unlike the direct conditions, CoT therefore differs from the baseline in more than
  one added sentence; this is inherent to the intervention.
- Template: prompts/system_cot.txt. Conditions are now defined by (base template, intervention text,
  long_output) in prompts.CONDITIONS.
- Parser: if an "Answers:" line is present, only the text after the last such line is parsed, so row
  mentions in the reasoning are ignored. Non-CoT parsing is unchanged.
- Output cap: 2000 tokens for long-output conditions in reasoning "none" (500 otherwise; 16000 with reasoning).
- CoT runs in both modes. "none" + CoT is the cell that corresponds to the original paper (GPT-4 had
  no internal reasoning) and tests whether written reasoning can substitute for internal reasoning.
  "high" + CoT (reasoning model asked to write its reasoning) is interpreted separately.
- run_smoke.py accepts --condition for small pre-tests of any condition.

## 2026-11-08 One-shot conditions

- Three conditions: oneshot_gain, oneshot_loss (original paper's approach), oneshot_mixed.
- Each example is one demonstration item whose numbers differ from every test item, followed by
  the answers of a respondent with the target preference. No label or explanation; neutral Reason
  ("I compared the two options in each row."); closing line "Now answer the new task in the same format."
  The example is presented as "the answers you gave", parallel to the "you are ..." direct conditions.
- Placement: after the rules in the system message (direct conditions go before), so the example is
  read after the task has been explained.
- Demonstrated preferences:
  - gain: 40% of $200, else $50 (EV $110); sure chosen from $90.91 -> CE ~$84.09, risk premium ~0.24.
  - loss: same lottery negated; sure loss chosen from -$131.82 -> CE ~-$138.64, risk premium ~0.26.
  - mixed: 50/50, lose $60; ratios 0.2, 0.4, ..., 2.4; plays only if G >= 2L.
- Imitation vs. preference:
  - gain/loss: adopting a preference shifts CE positions while they still track p; copying the
    switch position gives a flat CE position across p (check with position_check.py).
  - mixed: the example uses a different ratio grid from the test items, so the three outcomes differ:
    unaffected ~1.04, preference adopted ~1.94, switch position copied ~2.96.
    (An earlier draft grid of 0.4-4.8 was rejected: copying its position would give ~1.04,
    indistinguishable from no effect.)
- Labels follow the test prompt's version; example rows shuffled once with a fixed seed (same order
  in both versions). Texts generated by src/make_oneshot.py into prompts/interventions/oneshot_*_v{1,2}.txt.
- Pre-test limited to a format check (6 calls per condition); effects not inspected before pre-registration.


## 2026-11-08 EV-hint condition (supplementary, reduced scope)

- Purpose: test whether the non-reasoning mode's biases come from not computing the EV.
  If stating the EV removes the biases, the problem is computational (and CoT may work by making the
  model compute the EV); if biases remain, the model's choice rule itself is not EV-based.
  Also links our results to the original paper, whose prompts stated the EV.
- Scope: reasoning "none" only, gain/loss items only (1,200 calls, ~$0.2).
  - Reasoning "high" is already an EV maximizer, so the hint is not expected to change it.
  - Mixed items would need an EV on every row, changing the row format; omitted.
- Wording follows the original: "The expected value of the lottery is $X." Placed in the user message,
  after the lottery description, because the EV differs by item.
- Code: CONDITIONS entries can now restrict item types ("item_types") and request the EV line ("ev_hint").

## 2026-11-09 Pilot (baseline, full-row shuffled format; 6 items x 2 versions x 2 modes x 20 samples = 480 calls)

- Items: gain_03, gain_16, loss_03, loss_16, mixed_A_05, mixed_B_08 (both magnitudes, both r,
  moderate and extreme p, both mixed directions).
- Reasoning "high": essentially deterministic. Within-prompt SD = 0 for gain/loss items (identical
  answers in 20 samples despite reshuffled rows); mixed SD 0 except one censored response.
  Valid rate ~99-100%.
- Reasoning "none": large within-prompt variation. SD in option steps: gain ~2-3, loss ~3,
  mixed ~0.4-1.9. Valid rates: gain 74%, loss 51%, mixed 92%.
- Label bias in "none": in gain and loss items, version 1 (A = lottery) chose the lottery more often
  than version 2 (e.g. gain_16 risk premium -0.49 vs -0.12) -> the model favors option A regardless of
  content. Confirms the need for counterbalancing; "high" shows no label effect.
- Sample size: the per-prompt criterion in pilot_report.py (CI half-width of one prompt's mean
  <= half a step) is stricter than needed (129-297 calls per prompt in "none"). The research question
  concerns condition effects aggregated over 40 prompts per item type, paired with baseline. With n
  samples per prompt, the approximate CI half-width of a condition-minus-baseline difference
  (sampling noise only) is, for "none": gain 0.33 / 0.29 steps, loss 0.50 / 0.43 steps at n = 15 / 20.
- Decision (proposed): n = 20 per prompt in "none", n = 5 in "high"; EV hint n = 20.
  Total ~28,600 calls, ~$5 standard (~$2.5 with Batch API).
- Original paper's N = 10 per setting: in "none", the per-setting 95% CI half-width at N = 10 would be
  ~1.8 (gain), ~2.7 (loss), ~0.8 (mixed) option steps -- far larger than the effects of interest.
  The original pooled 56 settings in a curve fit, so this does not show its conclusions are wrong,
  but it shows why uncertainty must be reported.

## 2026-11-15 Pre-registration committed

- docs/preregistration.md committed and pushed before any main-experiment data were collected.
- Commit: <hash and time from git log>
- 12 confirmatory contrasts (P1-P10 reasoning "none", P11-P12 reasoning "high"), Bonferroni-adjusted CIs.

## 2026-11-15 Analysis code and recovery test (before main data)

- src/analyze_main.py implements the pre-registered analysis (per-prompt means over valid responses,
  version-averaged item values, min 3 valid per version, paired item-level contrasts, 10,000-resample
  item bootstrap, 95% CIs, Bonferroni-adjusted CIs for the 12 primary contrasts, half-step decision rule).
- src/simulate_recovery.py simulates the full pre-registered design (28,600 responses) with known effects,
  noise, 30% random answers and a version-1 label bias in reasoning "none".
- Result: all 12 primary conclusions recovered correctly, including an effect set below half a step
  (not called an effect) and a true null (P8: "no meaningful effect").
- Finding: in reasoning "none", gain/loss effects are attenuated to ~60-70% of their true size
  (e.g. +1.10 steps measured as +0.66). Cause: with noisy responses, switch points pushed beyond the option
  range become dominance violations and are excluded, so the remaining valid responses are pulled toward the
  middle of the range. Mixed items and reasoning "high" are not affected.
  Implication for interpretation: a null or inconclusive gain/loss result in reasoning "none" may partly
  reflect this attenuation; sensitivity analysis S1 (including invalid responses) addresses it in part.
- A first version of the simulation had the loss-domain direction reversed (a bug in the simulation, not the
  analysis), detected because P7/P10 came out with the opposite sign.