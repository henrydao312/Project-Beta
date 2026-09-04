# AI Models in PROJECT BETA

What each model is, whether it is built or bought, what it may and may not do,
and the constraints that apply to it. Referenced by Outline §5, §22.6 and
§20.1, and by the Model Cards due in Week 9.

---

## 1. Three distinct roles for AI

Confusing these is the most common misreading of the project.

| Role | What it is | Build or buy | Ships in the system |
|---|---|---|---|
| **Development assistance** | Coding agents and chat assistants used while writing the code | Neither | No |
| **M1 and M2** | Market-regime classifier and signal-quality model | **Build** | Yes |
| **Explanation services** | Hosted LLM writing trade rationales and failure narratives | **Buy** | Yes, as an API call |

Development assistance is a tool, not a deliverable. It is permitted course-wide
and its use is recorded with per-component provenance in the AI usage log, per
Outline §16. It is not part of the shipped system and is not evaluated.

No model in this project is pretrained or fine-tuned. Outline §22.5 walks the
course's architecture decision tree and terminates at Tier 1, Prompt-Centric,
for both LLM services. The two classical models are not on that spectrum, which
orders LLM application patterns.

---

## 2. Models the project builds

### 2.1 M1 - Market-regime classifier

| Field | Value |
|---|---|
| Task | Multiclass classification on tabular features |
| Algorithms | Logistic regression (baseline), random forest, XGBoost. Optional HMM comparison |
| Input | Per-bar features from SPY 5-minute RTH bars |
| Output | Probabilities over three trend states (uptrend, downtrend, choppy) plus a separate binary volatility flag |
| Use | Permits, restricts or sizes participation. Never proposes a trade |
| Library | scikit-learn, XGBoost |

**Labelling scheme.** Three trend states plus a binary volatility flag, derived
from transparent rules on moving-average slope and realised-return thresholds.
Crossed classes on short-bar history produce thin, noisy labels; 3+1 keeps
classes populated and interpretable.

**Constraint: there is no ground truth for a market regime.** The labels are a
construction of this project, so M1 cannot be validated against an external
reference. Its real test is downstream: does gating B2 on it improve the
ablation.

### 2.2 M2 - Signal-quality model

| Field | Value |
|---|---|
| Task | Binary classification on tabular features |
| Algorithm | XGBoost |
| Input | Regime probabilities, signal strength, realised volatility, trend strength |
| Output | Probability of a profitable outcome, probability target is hit before stop, confidence |
| Training data | Candidate-trade outcomes from the SIP backtest |
| Library | scikit-learn, XGBoost |

**Scope note.** M2 scores the underlying. Contract selection for the options
layer is deterministic and downstream, so the options track adds no model.

**Constraint: M2's sample size is trade count, not bar count.** The dataset has
one row per candidate trade, not per bar. If B2 generates 500 candidates over
ten years, M2 trains on roughly 250 rows per fold. Candidate count must be
measured the first time B2 runs (Week 4) and treated as a gate: if it is too
low, strategy parameters are widened before M2 is built.

### 2.3 Compute and cost

| Item | Value |
|---|---|
| Dataset | 200,460 RTH bars, 2016-06-10 onward |
| Feature matrix | Approximately 24 MB |
| Training rows per fold | 49,140 (30-month train window) |
| Measured fit time | 0.96 s for XGBoost, 49,140 rows, 15 features, 300 trees |
| Full sweep estimate | 14 folds x 2 models x ~20 configurations, 5 to 30 minutes |
| Hardware | CPU only. No GPU |
| Cost | $0 |

Compute is not a constraint on this project.

### 2.4 Constraints that apply to both built models

1. **Calibration is required, not optional.** The trade gate uses probability
   thresholds. Raw gradient-boosted probabilities are not calibrated, so Platt
   or isotonic calibration is applied and Brier score is reported.
2. **All fitting happens inside the fold.** Scalers, calibrators and threshold
   selection use training and validation data only. Thresholds are chosen on the
   validation window, never the test window.
3. **No forward-looking labels.** A regime label computed from a window that
   extends past the bar it labels is leakage.
4. **No volume-derived features.** The feed-transfer experiment (2026-09-02)
   failed its pre-committed threshold, so volume-derived features are dropped
   from both models and from B2's strategy rules.
5. **Point-in-time features only**, per Outline §11.
6. **Artifacts are versioned and hashed**, so rolling back to a known-good model
   version is a configuration change rather than a rebuild.
7. **AI never enters the trade decision path.** M1 and M2 produce inputs to a
   deterministic Trade Decision Engine, which combines them by documented logic.
   The risk engine can override the result.

---

## 3. Model the project buys

### 3.1 Explanation service and failure narrative

| Field | Value |
|---|---|
| Task | Text generation |
| Technology | Hosted LLM API (Anthropic), model version pinned in RunConfig |
| Input | DecisionRecord fields plus reason-code documentation. Nothing else |
| Output | Plain-English rationale for a logged decision; narrative over precomputed failure-cluster statistics |
| Cost | Estimated $10 to $30 per month, billed separately from any consumer subscription |

**Constraints.**

1. **Hard grounding rule.** The prompt contains only fields present in the
   decision record, plus reason-code documentation. No market data, no model
   internals, no external sources. Reason codes come from a fixed enum.
2. **It never makes or influences a trade decision.** It narrates a decision the
   deterministic engine has already made. This is what keeps the system outside
   the LLM provider's high-risk "financial decisions" category.
3. **Statistics first, narrative second** for failure analysis. The LLM may not
   reference a cluster that was not computed.
4. **Outputs are cached** for reproducibility and cost control. Backtests never
   call live APIs.
5. **Model version is pinned** and recorded with every result.
6. **Audited at 50 or more samples.** Every factual claim must map to a field in
   the source record. Any untraceable claim is a release blocker.

**Excluded by design.** Generative what-if scenarios are permanently out of
scope. A counterfactual has no logged referent, so the model would have to
speculate or the grounding rule would have to be weakened.

### 3.2 Build versus buy rationale

Buy the language model: text generation is mature and commoditised, and it is
not where this project's contribution lies.

Build the classifiers: tabular market-regime classification has no managed
service, and their calibration and per-fold evaluation are the substance of the
graded ablation.

---

## 4. AI tasks not used, stated deliberately

Information retrieval and RAG (no document corpus), speech recognition,
text-to-speech, vision and OCR, and text classification or structured
extraction. The last of these was removed with the news gate on 2026-08-31.

---

## 5. How the built models are measured

Two layers. Only one decides.

**ML metrics, supporting.** Per-class precision, recall and F1; ROC-AUC; PR
curves; per-regime confusion matrices; calibration curves; Brier score.

**Trading metrics, primary.** The ablation ladder B1 to B2 to M1 to M2 under
walk-forward validation, with ΔSharpe evaluated per `EVALUATION_PROTOCOL.md`.

A model with strong ML metrics that does not improve the ablation is a failed
component. ML metrics diagnose; the ablation decides.

---

## 6. Required documentation

**Model Cards** (Week 9), one per built model: feed provenance, asset class,
fold count, the feed-transfer result, feature list, walk-forward results,
calibration, and limitations.

**System Card** (Week 9): the composed pipeline, where AI sits and where it
deliberately does not, the §20.2 guardrails, the asset-class tier structure,
known failure modes, and the paper-trading statement.
