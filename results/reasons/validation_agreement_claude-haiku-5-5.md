# Validation agreement: hand labels vs claude-haiku-5-5

Reference file: validation_reasons.xlsx
Prompt hash 43055e282748; 100 reasons; 95% CIs from 2,000 bootstrap resamples of reasons.
Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),
so agreement may be inflated.

| comparison | n | percent agreement | Cohen's kappa |
|---|---|---|---|
| main label (7 labels) | 100 | 84.0% [76.0%, 91.0%] | 0.688 [0.553, 0.810] |
| main label, EV + risk averse merged into risk averse | 100 | 88.0% [81.0%, 94.0%] | 0.755 [0.628, 0.875] |
| names_preference flag | 100 | 95.0% [90.0%, 99.0%] | 0.709 [0.419, 0.912] |

## Confusion matrix (rows: hand label, columns: LLM label)

| hand \ LLM       |   EV |   EV + risk averse |   risk averse |   risk seeking |   loss averse |   vague tradeoff |
|:-----------------|-----:|-------------------:|--------------:|---------------:|--------------:|-----------------:|
| EV               |   64 |                  4 |             0 |              0 |             1 |                0 |
| EV + risk averse |    0 |                  6 |             1 |              0 |             0 |                1 |
| risk averse      |    0 |                  3 |             8 |              0 |             0 |                1 |
| risk seeking     |    0 |                  0 |             0 |              0 |             0 |                1 |
| loss averse      |    0 |                  0 |             0 |              0 |             0 |                1 |
| vague tradeoff   |    2 |                  1 |             0 |              0 |             0 |                6 |

## Per label

|                  |   n_hand |   n_llm |   agree | share_of_hand_agreed   |
|:-----------------|---------:|--------:|--------:|:-----------------------|
| EV               |       69 |      66 |      64 | 93%                    |
| EV + risk averse |        8 |      14 |       6 | 75%                    |
| risk averse      |       12 |       9 |       8 | 67%                    |
| risk seeking     |        1 |       0 |       0 | 0%                     |
| loss averse      |        1 |       1 |       0 | 0%                     |
| vague tradeoff   |        9 |      10 |       6 | 67%                    |
| other            |        0 |       0 |       0 | -                      |

## names_preference (rows: hand, columns: LLM)

| hand   |   no |   yes |
|:-------|-----:|------:|
| no     |   88 |     2 |
| yes    |    3 |     7 |
