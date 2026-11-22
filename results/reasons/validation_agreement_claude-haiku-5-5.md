# Validation agreement: hand labels vs claude-haiku-5-5

Prompt hash fe25ff54a191; 100 reasons; 95% CIs from 2,000 bootstrap resamples of reasons.
Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),
so agreement may be inflated.

| comparison | n | percent agreement | Cohen's kappa |
|---|---|---|---|
| main label (7 labels) | 100 | 85.0% [77.0%, 92.0%] | 0.704 [0.573, 0.824] |
| main label, EV + risk averse merged into risk averse | 100 | 89.0% [82.0%, 95.0%] | 0.773 [0.644, 0.889] |
| names_preference flag | 100 | 96.0% [92.0%, 99.0%] | 0.778 [0.514, 0.951] |

## Confusion matrix (rows: hand label, columns: LLM label)

| hand \ LLM       |   EV |   EV + risk averse |   risk averse |   risk seeking |   loss averse |   vague tradeoff |
|:-----------------|-----:|-------------------:|--------------:|---------------:|--------------:|-----------------:|
| EV               |   65 |                  3 |             0 |              0 |             1 |                0 |
| EV + risk averse |    0 |                  6 |             1 |              0 |             0 |                1 |
| risk averse      |    0 |                  3 |             8 |              0 |             0 |                1 |
| risk seeking     |    0 |                  0 |             0 |              0 |             0 |                1 |
| loss averse      |    0 |                  0 |             0 |              0 |             0 |                1 |
| vague tradeoff   |    2 |                  1 |             0 |              0 |             0 |                6 |

## Per label

|                  |   n_hand |   n_llm |   agree | share_of_hand_agreed   |
|:-----------------|---------:|--------:|--------:|:-----------------------|
| EV               |       69 |      67 |      65 | 94%                    |
| EV + risk averse |        8 |      13 |       6 | 75%                    |
| risk averse      |       12 |       9 |       8 | 67%                    |
| risk seeking     |        1 |       0 |       0 | 0%                     |
| loss averse      |        1 |       1 |       0 | 0%                     |
| vague tradeoff   |        9 |      10 |       6 | 67%                    |
| other            |        0 |       0 |       0 | -                      |

## names_preference (rows: hand, columns: LLM)

| hand   |   no |   yes |
|:-------|-----:|------:|
| no     |   88 |     2 |
| yes    |    2 |     8 |
