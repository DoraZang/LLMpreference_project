# Validation agreement: hand labels vs claude-sonnet-5-5

Prompt hash 425f6ec9fefc; 100 reasons; 95% CIs from 2,000 bootstrap resamples of reasons.
Hand labels: blind first pass, then partly revised after LLM suggestions (original labels not kept),
so agreement may be inflated.

| comparison | n | percent agreement | Cohen's kappa |
|---|---|---|---|
| main label (7 labels) | 100 | 83.0% [75.0%, 90.0%] | 0.674 [0.535, 0.802] |
| main label, EV + risk averse merged into risk averse | 100 | 87.0% [80.0%, 93.0%] | 0.739 [0.608, 0.860] |
| names_preference flag | 100 | 97.0% [93.0%, 100.0%] | 0.826 [0.589, 1.000] |

## Confusion matrix (rows: hand label, columns: LLM label)

| hand \ LLM       |   EV |   EV + risk averse |   risk averse |   risk seeking |   loss averse |   vague tradeoff |
|:-----------------|-----:|-------------------:|--------------:|---------------:|--------------:|-----------------:|
| EV               |   63 |                  3 |             1 |              2 |             0 |                0 |
| EV + risk averse |    0 |                  5 |             1 |              0 |             1 |                1 |
| risk averse      |    0 |                  3 |             8 |              0 |             0 |                1 |
| risk seeking     |    0 |                  0 |             0 |              0 |             0 |                1 |
| loss averse      |    0 |                  0 |             0 |              0 |             1 |                0 |
| vague tradeoff   |    2 |                  1 |             0 |              0 |             0 |                6 |

## Per label

|                  |   n_hand |   n_llm |   agree | share_of_hand_agreed   |
|:-----------------|---------:|--------:|--------:|:-----------------------|
| EV               |       69 |      65 |      63 | 91%                    |
| EV + risk averse |        8 |      12 |       5 | 62%                    |
| risk averse      |       12 |      10 |       8 | 67%                    |
| risk seeking     |        1 |       2 |       0 | 0%                     |
| loss averse      |        1 |       2 |       1 | 100%                   |
| vague tradeoff   |        9 |       9 |       6 | 67%                    |
| other            |        0 |       0 |       0 | -                      |

## names_preference (rows: hand, columns: LLM)

| hand   |   no |   yes |
|:-------|-----:|------:|
| no     |   89 |     1 |
| yes    |    2 |     8 |
