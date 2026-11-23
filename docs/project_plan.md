> **Superseded.** This was the initial plan. The final design is in [preregistration.md](preregistration.md), results in [report.md](report.md).
# Can Prompting Shift an LLM's Risk and Loss Preferences? A Revisit of "LLM Economicus?" Section 4

**Author:** Dora
**Status:** Draft plan for feedback
**Planned duration:** 4–5 weeks
**Estimated budget:** ~$25 (OpenAI Batch API)

---

## 1. Background

Ross, Kim & Lo (2024), *"LLM economicus? Mapping the Behavioral Biases of LLMs via Utility Theory"* (arXiv:2408.02784), use classic behavioral-economics games to fit utility functions to LLM behavior. Section 4 asks whether prompting can shift GPT-4's risk and loss aversion in a gambling game. They test direct prompting, zero-shot chain-of-thought (CoT), one-/two-shot examples, and age-based role-play/advice prompts. Their main finding is that only one-shot prompting reliably changes behavior.

### Limitations of the original Section 4

1. **Small sample, no uncertainty reported.** One model (GPT-4), 56 game settings, N = 10 samples per setting. Results are shown only as fitted value-function curves, with no parameter values, variances, or confidence intervals. It is therefore unclear whether "no effect" means no effect or insufficient power.
2. **Older models only.** Newer models, including reasoning models, are not tested.
3. **Most prompts are not published.** Only the age-based prompts (Appendix E) are given. The direct, CoT, and one-/two-shot prompts and examples are not.
4. **A measurement issue for loss aversion.** The paper infers loss aversion from loss lotteries and teaches it with a pure-loss example. In prospect theory, however, the loss-aversion coefficient λ cancels out in pure-loss lotteries (both sides of the indifference condition are multiplied by −λ), so pure-loss choices identify only the loss-domain curvature β. λ can only be identified from **mixed** lotteries, where gains and losses appear in the same gamble.
5. **No analysis of why interventions work or fail.** The answer format already asks the model for a `Reason:` field, but these reasons are never analyzed.

## 2. Research Questions

- **RQ1.** Can prompting reliably shift an LLM's risk aversion and loss aversion?
- **RQ2.** When a prompt does shift behavior, *which* preference does it shift? Does it move the targeted measure without moving the others?
- **RQ3.** What are the likely reasons an intervention succeeds or fails, judging from both the model's choices and its stated reasons?
- **RQ4.** Does reasoning (prompted CoT vs. the model's built-in reasoning mode) change baseline preferences?

## 3. Experimental Design

### 3.1 Model

- One recent small GPT-5.x model (e.g., `gpt-5.4-mini`; exact model to be confirmed against current OpenAI docs, including support for `reasoning_effort = none`).
- **Non-reasoning mode** (`reasoning_effort = none`): all conditions.
- **Reasoning mode** (e.g., `reasoning_effort = high`): baseline only, to keep cost low while still allowing a clean comparison within the same model.
- Temperature = 1 throughout (matches the original paper; reasoning modes only support 1 anyway).
- Exact model version string, date, and parameters are logged for every call.

### 3.2 Task: gambling game

The format follows the original paper (Table 4): each item presents one prospect and 7 options; the model answers accept/reject for each option, then gives a `Reason:`. The switching point gives the certainty equivalent.

**Change from the original:** the prompt does **not** state the prospect's expected value. The original prompt includes it (e.g., "The expected value of the prospect is −95.00 dollars"), which may anchor the model toward expected-value maximization. We treat the no-EV version as the main setting (closer to real decisions) and test the EV hint as a separate condition.

### 3.3 Item set (60 items, generated programmatically)

| Item type | # | Variation | Metric | Target parameter |
|---|---|---|---|---|
| Gain lotteries | 20 | probability × magnitude | Risk premium | α (gain-domain curvature) |
| Loss lotteries | 20 | probability × magnitude | Risk premium | β (loss-domain curvature) |
| Mixed lotteries | 20 | 50% win G / 50% lose L, varying L; the 7 rows are 7 values of G | G* / L | λ (loss aversion) |

- **Risk premium** = (EV − CE) / |EV|. Positive means risk-averse and negative means risk-seeking, in both domains. Prospect theory predicts positive values for gains and negative values for losses in humans.
- **G\*** = the smallest G the model accepts. G*/L is a direct, model-free proxy for λ. It equals λ exactly only when α = β and gain/loss probability weights at 50% are equal, so it is reported as an approximation.
- Risk premium is a proxy for α/β; it also absorbs probability weighting. Fitting the full prospect-theory model (α, β, λ, φ⁺, φ⁻) is an optional extension.

### 3.4 Conditions

**Main experiment (9 conditions, non-reasoning mode, all tested on all 60 items):**

| # | Condition | Target | Pre-registered expectation |
|---|---|---|---|
| 1 | Baseline | — | Reference |
| 2 | Direct, technical ("be risk averse") | Risk | Risk premium ↑ (gains and losses) |
| 3 | Direct, plain language (same preference described in everyday words) | Risk | Same as #2 |
| 4 | One-shot, gain example | Risk | Gain risk premium ↑ |
| 5 | Direct, technical ("be loss averse") | Loss | G*/L ↑ |
| 6 | Direct, plain language | Loss | G*/L ↑ |
| 7 | One-shot, loss example (original paper's approach) | Loss | In theory only the loss-domain risk premium (β) changes; G*/L unchanged |
| 8 | One-shot, mixed example | Loss | G*/L ↑ |
| 9 | Zero-shot CoT | — | Behavior moves toward expected-value maximization |

Plus **Reasoning-mode baseline**, which together with #1 and #9 gives a three-way comparison: no reasoning / prompted reasoning / built-in reasoning.

**Design rules:**
- Only the "more averse" direction is tested (the original also tested "not averse" / "seeking"), to control cost.
- All one-shot examples use amounts and probabilities that differ from every test item, so the model cannot simply copy a switching position. (The original only shuffled option order.)
- Because every condition is tested on all three item types, each condition yields both **target** and **off-target** effects. For example, if teaching with a pure-loss example also moves G*/L, the model has generalized the concept beyond the example.
- Note: the mixed-example one-shot (#8) is not the same as the original two-shot. The two-shot used one pure-gain and one pure-loss example, neither of which contains information about λ.

**Supplementary conditions (if time permits, non-reasoning mode):**
- Baseline + EV hint (1 condition; cheap, run together with the main experiment).
- Role-play vs. Advice × {no age, young, old} (5 new conditions; role-play/no-age = baseline). This tests the original's counterintuitive finding that GPT-4 advises older people to be *less* loss-averse, and separates framing effects from age effects.

### 3.5 Prompt variation and sampling

- 2 paraphrased versions per condition; option order randomized.
- Non-reasoning mode: 15 samples per prompt. Reasoning mode: 10 samples per prompt. Final numbers are set from the pilot using n ≈ (2·SD/δ)², where SD is the within-prompt standard deviation of the switching point and δ is the smallest shift of interest (e.g., half an option step).

## 4. Analysis

### 4.1 Competence test

- A response is valid only if it parses and is monotonic (a single switching point).
- Parse failures and non-monotonic responses are recorded separately.
- A condition passes if more than 80% of responses are valid (same threshold as the original).
- Results are reported both with and without excluding invalid responses, since an intervention could change validity rates.

### 4.2 Statistics

- **Unit of analysis = item.** Repeated samples of the same prompt are not independent evidence. Responses are first averaged within each item, then aggregated across items.
- Means, variances, and 95% bootstrap CIs (resampling items).
- Each intervention is compared with baseline by **paired** differences per item.
- **Directionality:** does the target metric move while off-target metrics stay put?
- **Robustness:** agreement between the two paraphrased versions.
- **Sample-size check:** using pilot data, report how wide the CIs would be with N = 10, i.e., whether the original sample size was sufficient.

### 4.3 Explaining the results (behavior + stated reasons)

Reasons are elicited **after** the choices, as in the original format, so that eliciting them does not act as CoT and change the choices.

1. Read a few dozen reasons and derive a small coding scheme (4–6 categories, e.g., "computes expected value", "explicitly avoids risk", "refers to the example", "restates the instruction but does not follow it").
2. Hand-label 30–50 reasons; label all reasons with a small LLM; report agreement with the hand labels.
3. Compare category frequencies across conditions and reasoning modes.
4. **Reason–behavior consistency:** how often does the stated reason match the actual choice (e.g., "I am loss averse" but the switching point equals baseline)? Since stated reasons may be post-hoc rationalizations, this is measured rather than assumed.
5. For the most plausible explanation that emerges, run one small targeted control to test it.

## 5. Reproducibility

- Every call's input, output, model version string, date, and parameters are saved as JSONL.
- All prompt templates and item-generation code are in the repository.
- A one-page table of expected directions for each condition is committed **before** the main experiment runs (light pre-registration).

## 6. Timeline (5 weeks; week 5 is a buffer)

| Week | Tasks | Done when |
|---|---|---|
| 1 | Generate 60 items in code; write all prompt templates and paraphrases; build the pipeline (API + Batch calls, parsing, competence check, metric computation) | Any condition × item automatically yields parsed choices, switching point, metric, and competence status |
| 2 | Pilot (3–4 items, 20 samples, both modes): measure cost, reasoning-token usage, and variance; fix sample sizes; check N = 10 CI width. Commit the expected-direction table. Run baseline in both modes. Write bootstrap/paired-comparison code | Final sample sizes set; baseline metrics with 95% CIs and competence rates for both modes |
| 3 | Submit all 8 interventions + EV-hint condition via Batch API; build the analysis notebook while waiting | Main results table: change vs. baseline in each of the three metrics, with CIs, marking which match the predicted direction |
| 4 | Reason analysis: coding scheme, hand labels, LLM labeling, consistency rate; one targeted control | A short, evidence-backed answer to which interventions work, which don't, and why |
| 5 | (Optional) age experiment; clean up repository; write short report | Repository organized; report draft complete |

If only 4 weeks are available, the age experiment is dropped and listed as future work.

## 7. Budget

Estimated with GPT-5.4 mini pricing and the Batch API (50% discount). Assumptions: ~400 input tokens per call, ~120 output tokens in non-reasoning mode, ~2,000 reasoning tokens in reasoning mode (to be measured in the pilot).

| Component | Calls | Est. cost |
|---|---|---|
| Main experiment (9 conditions, non-reasoning) | 16,200 | ~$8 |
| Reasoning-mode baseline | 1,200 | ~$6 |
| Supplementary conditions | 10,800 | ~$5 |
| Reason labeling + pilot | — | ~$5 |
| **Total** | | **~$25** |

The main uncertainty is reasoning-token usage; even at double the estimate, it adds only a few dollars because reasoning mode is limited to the baseline.

## 8. Deliverables

- GitHub repository: code, prompt templates, raw data, analysis notebooks, pre-registration file.
- Short report: methods, main results with CIs, explanation analysis, limitations.

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Non-reasoning mode fails the competence test | Revise answer-format instructions; if it still fails, report it as a finding |
| Reasoning tokens far exceed estimate | Lower reasoning effort or reduce samples for reasoning mode |
| Wide CIs due to large between-item variance | Add items rather than samples per prompt |
| Unreliable reason labeling | Rely on hand labels; reduce the number of categories |
| Stated reasons are post-hoc rationalizations | Treat reasons as evidence to be checked against behavior, not as ground truth |

## 10. Questions for Feedback

1. Is 60 items (20 per type) enough, or should the budget go toward more items rather than paraphrases?
2. Is G*/L an acceptable proxy for λ for this scope, or is fitting the full prospect-theory model worth the extra time?
3. Is testing only the "more averse" direction a reasonable simplification?
4. Is limiting the reasoning mode to the baseline condition a sound trade-off?
5. Is the reason-analysis method (coding scheme + LLM labeling validated on hand labels + reason–behavior consistency) rigorous enough to support claims about *why* interventions work or fail?
