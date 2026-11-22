# Reason codebook

Codebook for the exploratory reason analysis (pre-registration, Section 9). Each response ends with a
one- or two-sentence "Reason:" line. For CoT responses, only this final Reason line is coded, not the
written reasoning. The codebook was built from a stratified discovery sample of 112 reasons
(results/reasons/discovery_reasons.csv), read blind to condition.

Each reason gets one main label and one yes/no flag. The label describes the decision rule the
reason states, not which condition it came from and not what the model actually chose. Item type
(gain / loss / mixed) is not part of the label; it is taken from the data when analyzing.

## Main label: decision procedure

Answer the questions in order and stop at the first label that applies.

1. Does the reason give no usable rule (empty, generic, or only restates the task)?
   -> `other`
   A rule that chooses the same kind of option in every row (always the sure option, or always the
   lottery), with or without an exception for rows where one option dominates, is a usable rule and
   is never `other`.
2. If the stated rule were followed exactly, would the choices maximize expected value
   (choose whichever option has the higher expected value / smaller expected loss)?
   -> `EV`
3. Does the rule favor the lottery even when the sure option is somewhat better than the
   lottery's expected value? Choosing the lottery only in rows where it is at least as good as the
   sure option in every outcome does not count.
   -> `risk seeking`
4. Does the rule favor the sure option (or avoid the gamble), and is this justified by losses
   counting more than gains of the same size?
   -> `loss averse`
5. Does the rule favor the sure option (or avoid the gamble) even when this gives up some expected
   value, or to avoid uncertainty or the chance of a loss?
   -> `EV + risk averse` if the reason refers to the expected value or average outcome,
   -> `risk averse` otherwise
6. Does the reason weigh the upside against the risk or the possible loss, without referring to
   expected value and without saying where the threshold is?
   -> `vague tradeoff`

## Labels

| Label | Definition | Example |
|---|---|---|
| `EV` | The rule is an expected-value comparison; following it is risk-neutral. Includes "positive expected value" rules for mixed items. | "The lottery has an expected value of $6, so I chose the sure amount when it was at least $6 and the lottery when it was below $6." |
| `EV + risk averse` | Refers to the expected value or average, but accepts a sure option that is somewhat worse, or rejects gambles with positive expected value. Cue words: close to, not too much worse, somewhat lower, even when. | "I chose the guaranteed option when its loss was close to the lottery's average loss, to avoid uncertainty." |
| `risk averse` | Prefers the sure option to avoid uncertainty or the possibility of a loss, without referring to expected value. Includes rules that choose the sure option in every row except rows where the lottery dominates. | "I prefer the guaranteed $0 to risking a loss of $28." / "I prefer the guaranteed outcome over a lottery. In Row 12, the lottery is better because it never gives a worse outcome than the sure loss." |
| `risk seeking` | Favors the lottery even when the sure option is somewhat better, e.g. for the chance of a larger payout. Includes rules that choose the lottery in every row. | "I prefer the lottery to each sure amount, including $10, because it offers a chance at the larger payout." |
| `loss averse` | Favors the sure option because losses count more than equal gains. | "I weigh the possibility of a loss more heavily than an equally sized gain, so I choose the sure $0 when the downside is substantial." |
| `vague tradeoff` | Weighs the upside against the risk or loss, but gives no expected value and no clear threshold. | "I chose the lotteries with larger potential gains to compensate for the $17 possible loss, and took the sure $0 when the gain seemed too small." |
| `other` | No usable rule. A rule that always chooses the same kind of option is a usable rule, not `other`. | "I compared the two options in each row." |

## Flag: `names_preference` (yes / no)

"yes" only if the reason uses one of these expressions (or a close variant), whether or not the rule
reflects it: risk aversion / risk averse, loss aversion / loss averse, losses loom larger / feel
worse / weigh more than gains, dislike uncertainty / dislike risk. Other wording such as "I prefer
certainty" or "to avoid uncertainty" is "no".

The flag together with the main label separates a stated preference that shapes the rule
(e.g. `EV + risk averse`, yes) from a preference that is only claimed (`EV`, yes).

## Boundary cases

- Ties: statements about what the model would choose if both options had equal expected value are
  ignored. The items contain no such rows.
- Dominated rows: remarks such as "at $10 the sure amount is at least as good as the lottery in
  every outcome" do not change the label; they are consistent with every label. Label the rule
  stated for the other rows. "I prefer the guaranteed amount in each row, except where the lottery
  is at least as good in every outcome" -> `risk averse`, not `risk seeking` and not `other`.
- Always the same option: "I prefer the guaranteed outcome over a lottery" (in every row) ->
  `risk averse`; "I prefer the lottery to each sure amount" -> `risk seeking`, unless the reason
  says every sure amount is below the lottery's expected value (then `EV`).
- "Positive expected value ... when the possible loss is less than $46" is `EV`: the threshold is
  exactly where expected value is zero.
- "Gain large enough to justify the risk" without expected value is `vague tradeoff`;
  "even when their expected values were positive" makes it `EV + risk averse`.
- Losses in pure-loss items: preferring a sure loss is risk aversion, not loss aversion, unless
  the reason says losses count more than gains.
- Label what the reason states, not what can be inferred about the item or the condition.
- A reference to expected value or average inside an "even when ..." clause counts as referring to
  expected value ("even when it is lower than the lottery's average" -> `EV + risk averse`).