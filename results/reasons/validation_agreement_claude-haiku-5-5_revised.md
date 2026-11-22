# Validation agreement: hand labels vs claude-haiku-5-5

Reference file: validation_reasons_revised.xlsx (tag: revised)
Prompt hash 43055e282748; 100 reasons; 95% CIs from 2,000 bootstrap resamples of reasons.
Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),
so agreement may be inflated.

| comparison | n | percent agreement | Cohen's kappa |
|---|---|---|---|
| main label (7 labels) | 100 | 90.0% [84.0%, 96.0%] | 0.807 [0.698, 0.913] |
| main label, EV + risk averse merged into risk averse | 100 | 94.0% [89.0%, 98.0%] | 0.879 [0.781, 0.964] |
| names_preference flag | 100 | 95.0% [90.0%, 99.0%] | 0.709 [0.419, 0.912] |

## Confusion matrix (rows: hand label, columns: LLM label)

| hand \ LLM       |   EV |   EV + risk averse |   risk averse |   risk seeking |   loss averse |   vague tradeoff |
|:-----------------|-----:|-------------------:|--------------:|---------------:|--------------:|-----------------:|
| EV               |   65 |                  3 |             0 |              0 |             0 |                0 |
| EV + risk averse |    0 |                  8 |             1 |              0 |             0 |                1 |
| risk averse      |    0 |                  3 |             8 |              0 |             0 |                0 |
| risk seeking     |    1 |                  0 |             0 |              0 |             0 |                0 |
| loss averse      |    0 |                  0 |             0 |              0 |             1 |                1 |
| vague tradeoff   |    0 |                  0 |             0 |              0 |             0 |                8 |

## Per label

|                  |   n_hand |   n_llm |   agree | share_of_hand_agreed   |
|:-----------------|---------:|--------:|--------:|:-----------------------|
| EV               |       68 |      66 |      65 | 96%                    |
| EV + risk averse |       10 |      14 |       8 | 80%                    |
| risk averse      |       11 |       9 |       8 | 73%                    |
| risk seeking     |        1 |       0 |       0 | 0%                     |
| loss averse      |        2 |       1 |       1 | 50%                    |
| vague tradeoff   |        8 |      10 |       8 | 100%                   |
| other            |        0 |       0 |       0 | -                      |

## names_preference (rows: hand, columns: LLM)

| hand   |   no |   yes |
|:-------|-----:|------:|
| no     |   88 |     2 |
| yes    |    3 |     7 |
