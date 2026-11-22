# Validation agreement: hand labels vs claude-sonnet-5-5

Reference file: validation_reasons_revised.xlsx (tag: revised)
Prompt hash 425f6ec9fefc; 100 reasons; 95% CIs from 2,000 bootstrap resamples of reasons.
Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),
so agreement may be inflated.

| comparison | n | percent agreement | Cohen's kappa |
|---|---|---|---|
| main label (7 labels) | 100 | 88.0% [81.0%, 94.0%] | 0.772 [0.656, 0.881] |
| main label, EV + risk averse merged into risk averse | 100 | 92.0% [86.0%, 97.0%] | 0.841 [0.728, 0.939] |
| names_preference flag | 100 | 97.0% [93.0%, 100.0%] | 0.826 [0.589, 1.000] |

## Confusion matrix (rows: hand label, columns: LLM label)

| hand \ LLM       |   EV |   EV + risk averse |   risk averse |   risk seeking |   loss averse |   vague tradeoff |
|:-----------------|-----:|-------------------:|--------------:|---------------:|--------------:|-----------------:|
| EV               |   64 |                  1 |             1 |              2 |             0 |                0 |
| EV + risk averse |    0 |                  7 |             1 |              0 |             1 |                1 |
| risk averse      |    0 |                  3 |             8 |              0 |             0 |                0 |
| risk seeking     |    1 |                  0 |             0 |              0 |             0 |                0 |
| loss averse      |    0 |                  1 |             0 |              0 |             1 |                0 |
| vague tradeoff   |    0 |                  0 |             0 |              0 |             0 |                8 |

## Per label

|                  |   n_hand |   n_llm |   agree | share_of_hand_agreed   |
|:-----------------|---------:|--------:|--------:|:-----------------------|
| EV               |       68 |      65 |      64 | 94%                    |
| EV + risk averse |       10 |      12 |       7 | 70%                    |
| risk averse      |       11 |      10 |       8 | 73%                    |
| risk seeking     |        1 |       2 |       0 | 0%                     |
| loss averse      |        2 |       2 |       1 | 50%                    |
| vague tradeoff   |        8 |       9 |       8 | 100%                   |
| other            |        0 |       0 |       0 | -                      |

## names_preference (rows: hand, columns: LLM)

| hand   |   no |   yes |
|:-------|-----:|------:|
| no     |   89 |     1 |
| yes    |    2 |     8 |
