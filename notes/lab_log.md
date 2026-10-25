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