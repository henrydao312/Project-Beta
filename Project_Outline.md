# PROJECT BETA — Project Outline (Revision 9)

**AI Capstone (CIS 5980) — AI Engineering Track — Solo Project**

Revisions 2–7 established scope, timeline, the multi-strategy architecture, the Product One-Pager (§1A) and the Demo Walkthrough (§19). **Revision 8** aligned the plan to the Phase 1 lecture deck (§9A, two-layer metrics in §10, the Responsible AI charter in §20, focus areas in §21). **Revision 8.1** verified the licensing audit against published terms. **Revision 8.2** added the Alpaca account agreements and the publication constraints (§20.5).

**Revision 9 (2026-08-30) — the Week 1 data verification is done, and it settles the project's biggest open risk.** Findings and consequences:

1. **§9 is resolved: a dual-feed architecture on Alpaca's free tier, $0.** Historical SIP (full consolidated tape) reaches back to **2016-06-10 — 10.2 years**, so the original ten-year walk-forward design survives intact. Recent SIP and SIP streaming are *not* entitled, so the live paper loop runs on IEX. Backtest and live therefore use **different feeds**, deliberately and documented.
2. **A new first-class risk: train/live feed mismatch (§5.2, §15).** IEX carries a measured **3.16%** of consolidated volume. Volume-derived features trained on SIP would see values ~30× larger than they meet live on IEX. Resolved by design — volume features are **scale-free** — with a validation experiment scheduled in Week 1–2 to prove the features actually transfer.
3. **Regular-hours filtering is now mandatory (§5.1).** SIP returns 192 bars/day (04:00–20:00 ET); ~60% are extended-hours.
4. **New §9B — upgrade paths**, for better data and for any move toward live trading, with verified current pricing.

*Correction carried into §9B: Rev 8.2's tier table implied Polygon's $79 Developer tier offered real-time data. It does not — Developer is 15-minute delayed; real-time is the $199 Advanced tier. The earlier comparison understated the cost of that route by more than half.*

*Nothing in §20.1 is legal advice; it is a good-faith reading of published terms, cited so a reader can check it.*

---

## 1. Project Statement (Course Step 1)

> **PROJECT BETA is an AI-assisted paper-trading system for a single liquid ETF (SPY) that uses a market-regime classifier and a signal-quality filter to gate a transparent rule-based strategy, enforces deterministic risk controls, and produces grounded LLM explanations for every trade decision — with an optional, feasibility-gated news-risk filter.**

- **Track declaration:** **AI Engineering Track.**
- **User / stakeholder:** A discretionary retail trader or junior quantitative researcher who wants systematic, interpretable, risk-controlled filtering of trading signals.
- **Main workflow:** Market data → validation → features → rule-based signal → regime classification → signal-quality scoring → (conditional) news gate → risk engine → simulated/paper execution → decision log → explanation → dashboard.
- **Expected value:** Improved risk-adjusted performance and reduced drawdown versus the identical unfiltered strategy, with a transparent, auditable rationale for every decision.
- **User-relevant success criteria:**
  1. The AI-filtered strategy improves at least one prespecified risk-adjusted metric (Sharpe ratio or maximum drawdown) versus the identical rule-based strategy in walk-forward testing, net of transaction costs — **or** produces a rigorously supported negative result.
  2. Every accepted, reduced, delayed, or rejected trade has a structured explanation that accurately reflects the true model and risk state.
  3. A reader of the dashboard can correctly state why the system took (or refused) a given trade, unaided — measured, not asserted; see §10.2.

## 1A. Product One-Pager

**The issue.** Retail traders and junior quant researchers routinely act on trading signals they can't fully trust — noisy, unfiltered, and impossible to audit after the fact when a trade goes wrong.

**The audience.** Discretionary retail traders and junior quantitative researchers who want systematic, explainable, risk-controlled signal filtering — not a black box.

**The proposed idea.** An AI-assisted paper-trading system: a market-regime classifier and signal-quality model filter a transparent, rule-based momentum-breakout strategy on 5-minute SPY bars, a deterministic risk engine enforces limits, and every trade decision gets a grounded, plain-English explanation.

**What makes it stand out.** Most public "AI trading bots" let an LLM make the trade call directly and show one cherry-picked backtest. PROJECT BETA never lets AI touch trading logic — it only gates a transparent rule-based strategy — and every explanation is grounded in a logged decision (audited: ≥50-sample grounding check). Success is measured with an ablation ladder (B1→M2, §7) that isolates exactly what each AI component adds, under walk-forward validation, and a rigorous negative result counts as a legitimate outcome rather than a failure to hide (§18). The differentiation is AI-engineering discipline — auditability, grounding, honest ablation — not a claim to have found a better trading strategy.

**Success criteria.**
- *Primary (offline):* the regime + signal-quality filters improve Sharpe ratio or maximum drawdown over an identical unfiltered baseline (B2), net of transaction costs, in walk-forward testing — or the negative result is rigorously characterized.
- *Primary (user-impact):* an unaided reader of the decision feed can correctly identify the current regime, the open positions, and the reason for the most recent decision (§10.2).
- *Secondary:* 100% of a random sample of trade explanations audit as grounded in the decision log; the system runs live, unattended, on an Alpaca paper account.

**Biggest single risk + fallback — UPDATED Rev 9.** The data-availability risk that headed this list is **closed**: ten years of consolidated 5-minute history is confirmed available at zero cost (§9). The largest remaining technical risk is the **train/live feed mismatch** it created (§5.2), which has a designed mitigation and a scheduled validation experiment. The largest *schedule* risk is unchanged: a working Alpaca paper loop is due at Week 9, two-thirds through the build time.

## 2. Research Questions

**Primary:** Can an ML-based market-regime classifier and signal-quality model improve the risk-adjusted performance or reduce the drawdown of a transparent rule-based trading strategy on out-of-sample data, net of transaction costs?

**Secondary (conditional on news feasibility):** Does structured news understanding provide incremental value beyond technical and regime information?

## 3. Scope Tiers

| Tier | Components | Status |
|---|---|---|
| **Guaranteed core** | Data pipeline, feature engineering, rule-based strategy (momentum breakout, primary), regime classifier (M1), signal-quality model (M2), risk engine, execution simulator, paper trading, evaluation harness, explanation agent, failure-analysis assistant, dashboard | Committed — this alone is a complete capstone |
| **Conditional** | Plan A news gate (M3) | Week 2 feasibility gate |
| **Confirmed design, lightweight scope** | Multi-strategy toggle — MA trend and mean reversion behind the same Strategy Engine interface (§5.3) as a **backtest-only exploratory toggle** | **Confirmed 2026-08-26** |
| **Optional** | Plan B news features (M4), HMM regime comparison, daily AI trading summary, interactive query layer | Week 10 decision |
| **Excluded** | Live-money trading, reinforcement learning, autonomous LLM trading, multiple assets, tick-level data, full SEC-filing RAG, AI-controlled risk rules | Out of scope permanently |

**Named fallback checkpoints:**

- If the regime classifier is not calibrated and ablated against B2 by **end of Week 6**, Plan A is dropped regardless of the Week 2 feasibility verdict.
- If the Alpaca paper loop is not running end-to-end by **end of Week 8**, the secondary-strategy toggle is dropped and Week 8 goes to the alpha.
- If the release candidate is not containerized and reproducible by **end of Week 11**, Plan B and the interactive query layer are off the table.

## 4. Core Pipeline

```text
SPY market data  — SIP consolidated (backtest) | IEX (live paper), §9
→ data validation (gaps, duplicates, outliers, timestamps, RTH filter)
→ feature engineering (returns, realized vol, MA slopes, ADX, scale-free volume, VWAP distance, range expansion)
→ transparent rule-based signal
→ market-regime classifier
→ signal-quality model
→ (conditional) news gate — Plan A
→ combined trade gate
→ deterministic risk engine
→ execution simulator / Alpaca paper broker
→ structured decision log
→ LLM trade explanation (grounded in logged state only)
→ dashboard
→ failure-analysis assistant
```

## 5. AI Components

### 5.1 Market-Regime Classifier (required — M1)

**Labeling scheme:** 3 trend states — *uptrend / downtrend / choppy* — from transparent rules on MA slope and realized-return thresholds, with a separate binary **high/low volatility flag**. Rationale: 6+ crossed classes on a short-bar history produces thin, noisy labels; 3+1 keeps classes populated and interpretable.

**Models:** logistic regression (baseline), random forest, XGBoost; optional HMM comparison.
**Outputs:** regime probabilities per bar, used to permit, restrict, or size strategy participation.
**Documentation deliverable (Wk 9):** a **Model Card**, recording feed provenance per §9.

### 5.2 Signal-Quality Model (required — M2)

Scores each candidate trade from the rule-based strategy.

**Features:** regime probabilities, signal strength, realized volatility, volume confirmation, trend strength; news features only under Plan B.
**Outputs:** probability of profitable outcome (primary), probability target is hit before stop, confidence score.
**Training data:** candidate-trade outcomes from the backtest on SIP history.

#### The train/live feed mismatch, and how it is handled (Rev 9 — read before building any feature)

Verified 2026-08-30: **IEX carries a median 3.16% of consolidated volume** (measured over six sessions; range 2.79–3.36%, so this is structural, not noise). Because backtests run on SIP and live paper trading runs on IEX (§9), any feature defined on *absolute* volume would be trained on values roughly thirty times larger than it encounters at inference. Such a model would not degrade gracefully — it would produce nonsense the moment it went live, and the failure would be silent.

**Design decision: all volume-derived features are scale-free.** Volume enters the feature set only as a ratio or standardized score against its own trailing window *on the same feed* — "volume is 2.3× its recent normal" — never as a raw count or a raw delta. A relative measure carries the same meaning whether computed on 3% of the tape or 100% of it, provided IEX is a representative sample of consolidated activity.

**That proviso is an assumption, so it gets tested, not assumed.** The two feeds overlap historically from 2021, which makes the check cheap and direct:

> **Feed-transfer validation experiment (Week 1–2).** Compute the scale-free volume features from IEX and from SIP over the same 2021–2026 period. Correlate them bar-by-bar and compare their distributions. Report the correlation in the Data Card and the Model Card.
> - **Strong agreement** → volume features are kept, and the transfer evidence is cited wherever they appear.
> - **Weak agreement** → volume-derived features are **dropped entirely**, and the Model Card states that IEX proved unrepresentative. This is a perfectly defensible outcome and a better one than shipping a feature that silently breaks at deployment.

Either way the result is recorded before the signal-quality model is built, so the decision rests on evidence rather than convenience. **Deadline: this must conclude before Week 7's signal-quality work begins.**

**Documentation deliverable (Wk 9):** its own **Model Card**, including the transfer-validation result.

### 5.3 Strategy Engine (multi-strategy design)

**Responsibility:** `generate_candidates(features, bars) -> list[CandidateTrade]` from a transparent rule set.
**Primary — momentum breakout:** the only strategy with full evaluation rigor this semester.
**Secondary — MA trend, mean reversion:** same interface, backtest-only, labeled exploratory/not graded.
**Requirements:** parameters in RunConfig, not code; primary rules documented in plain language.
**AC:** same data + config ⇒ byte-identical candidate list; the primary/secondary distinction enforced in the harness (PRD §5.14).

### 5.4 LLM Trade-Explanation Agent (required)

Converts the decision log into readable rationales. **Grounding rule:** only fields present in the decision log; never alters trading logic, never makes buy/sell decisions. *This constraint is also what keeps the project outside the LLM provider's high-risk "financial decisions" category — §20.1.*

*Optional extension (Week 10 gate):* interactive query mode, same grounding constraint.

### 5.5 Failure-Analysis Assistant (required)

Statistical clustering of losing trades first, followed by LLM-generated interpretation and targeted-test suggestions.

### 5.6 Plan A — News-Risk Gate (conditional — M3)

An independent eligibility gate; never generates directional trades.

- **Extraction:** structured fields per headline — event type, sentiment, materiality, relevance to SPY, uncertainty, freshness.
- **Hybrid architecture:** a small local sentiment model scores bulk *historical* headlines; the LLM handles *live* extraction. All outputs cached — backtests never re-query an API.
- **Model choice caveat:** FinBERT's published weights carry **no declared license** (§20.1). Either accept the documented handling, or pick an explicitly-licensed model. Decide at the Week 2 gate.
- **Deterministic policy:** transparent thresholds map extracted fields to Approve / Reduce / Delay / Reject.
- **Security note:** headlines are untrusted third-party text entering an LLM prompt — the project's one genuine prompt-injection surface, and the Week 10 red-team target (§20.2).

### 5.7 Plan B — News Features in the Quality Model (optional — M4)

Cached Plan A outputs become features in the signal-quality model. Week 10 decision.

## 6. Week 2 News Feasibility Gate

Validate by end of Week 2: historical news depth and coverage; timestamp reliability; duplicate/stale handling; licensing and redistribution terms (§20.1); rate limits; scoring cost; reproducibility of cached outputs; **and the sentiment-model licensing question (§5.6).**

| Outcome | Consequence |
|---|---|
| **GO** | Implement Plan A historically; M3 enters the ablation |
| **CONDITIONAL** | Plan A runs in live paper trading only; no M3 backtest claims |
| **NO-GO** | Drop Plan A; project proceeds through M2 with full ablation intact |

## 7. Baseline & Ablation Ladder

| # | System | Regime AI | Signal AI | News AI | Status |
|---|---|---:|---:|---:|---|
| B1 | Buy & hold | – | – | – | Guaranteed |
| B2 | Momentum-breakout strategy + risk layer | – | – | – | Guaranteed |
| M1 | B2 + regime classifier | ✓ | – | – | Guaranteed |
| M2 | M1 + signal-quality model | ✓ | ✓ | – | Guaranteed |
| M3 | M2 + Plan A news gate | ✓ | ✓ | ✓ | Conditional |
| M4 | M3 + Plan B news features | ✓ | ✓ | ✓ | Optional |

**Only B1–M2 are guaranteed, and only for the primary strategy.** All ladder runs use the SIP backtest feed (§9); secondary strategies appear only as informal backtest comparisons.

## 8. Risk & Execution Layer (deterministic, auditable)

**Risk controls:** maximum position size, volatility-adjusted sizing, stop-loss rules, maximum drawdown limit, daily loss limit, post-event cooldown, maximum exposure, defined no-trade periods.

**Execution simulator / paper broker:** commissions, spread, slippage, delayed fills, market-hour constraints. Live demo path runs on an Alpaca paper account, primary strategy only.

**Paper-only enforcement:** the execution layer accepts only paper endpoints and paper credentials; there is no live-money code path, and a unit test asserts a non-paper endpoint is rejected. Harm 1's guardrail in §20.2.

## 9. Data Architecture — RESOLVED 2026-08-30 by direct API verification

**Decision: Alpaca free (Basic) tier, dual-feed. Total data cost for the semester: $0.**

### What was measured

| Probe | Result |
|---|---|
| SIP historical depth, 5-min bars | **2016-06-10 onward — 10.2 years.** 2015 returned nothing on both feeds, so 2016 is the true floor |
| IEX historical depth, 5-min bars | 2021-06-10 onward — 5.2 years |
| SIP recent data | **Not entitled** — `403: subscription does not permit querying recent SIP data` |
| SIP streaming | **Not entitled** — `409 insufficient subscription` |
| IEX volume vs. consolidated | **3.16% median** (range 2.79–3.36% over six sessions) |
| Coverage, 42 sessions | 42/42 full regular sessions, **zero gaps, zero duplicate timestamps** |
| Bars per day, SIP | 192 = 04:00–20:00 ET full extended session |

### The resulting architecture

| | Feed | Why |
|---|---|---|
| **Backtest / walk-forward / ablation ladder** | **SIP consolidated** | Ten years of history and true market volume. The entire graded evaluation runs here |
| **Live paper trading (Milestone 3)** | **IEX** | The only real-time feed entitled on this tier. *Pending final confirmation of IEX streaming latency during market hours* |

**Every RunConfig, results table and Model Card records which feed produced it** (PRD §4.3, §5.14). SIP-derived and IEX-derived results are never compared as though equivalent.

### Consequences that flow from this

1. **`data.start: 2016-06-10`.** The original ten-year walk-forward design is intact — 36-month train / 6-month test / 6-month step yields roughly 14 folds.
2. **The feed mismatch is a first-class design constraint**, not a footnote — see §5.2 for the scale-free volume design and its validation experiment.
3. **Regular-hours filtering is mandatory.** 192 bars/day means ~60% of SIP bars fall outside 09:30–16:00 ET. Overnight and pre-market liquidity and spreads behave nothing like the regular session. **The strategy trades regular hours only, and the filter is applied at the data-pipeline stage** so no downstream component can forget it.
4. **One apparent anomaly is an artifact, not a defect.** The single thin day (2026-06-30, 13 bars) sits exactly at the 60-day query boundary — a partial first day. Validation rules must distinguish "partial day at a query edge" from a genuine gap, or this ghost gets chased again.
5. **No paid data subscription is needed for the graded project.** §9B covers what would change that.

## 9A. Tech Stack and Compute Budget (required Milestone 1 item)

| Layer | Choice | Note |
|---|---|---|
| Language | Python 3.11+ | Unconstrained by the course |
| Data / broker | **Alpaca Trading API, Basic (free) tier — dual-feed per §9** | $0 |
| Data handling | pandas, pyarrow (Parquet bar store), hashed datasets | `dataset_hash` per PRD §5.1 |
| Classical ML | scikit-learn, XGBoost | Regime and signal-quality models |
| NLP (conditional) | Small local sentiment model | Plan A only; licensing caveat §5.6 |
| LLM | Hosted API (Claude), pinned model version | Explanation + failure-analysis narrative only |
| Dashboard | Streamlit vs. lightweight web app — Week 3 decision | Choose the cheaper one |
| Testing / CI | pytest, GitHub Actions | Smoke test from Week 1 |
| Packaging | Docker (release candidate, Wk 12) | §12 |

| Cost item | Amount | Basis |
|---|---|---|
| Model training | **CPU only, no GPU** | Tabular features; walk-forward folds run in minutes |
| Backtests | **$0 by construction** | All AI outputs cached; backtest mode is cache-only |
| **Market data** | **$0 — confirmed 2026-08-30** | Free tier covers both the ten-year backtest history and the live paper feed (§9) |
| LLM API | Order of **~$10–30/month** | One bounded prompt per decision record; cached. Refine after the first live week. **Billed separately from the Claude subscription** — the explanation service calls the API, which is a Console account under commercial terms |
| CI | GitHub Actions free tier | Smoke tests only |

**Total expected semester spend: the LLM API line only.** The data risk that dominated the original budget is closed.

## 9B. Upgrade Paths — better data, and what going live would require (new, Rev 9)

Not needed for the graded project. Recorded because the Strategy Engine exists to keep growing after the course (§2), and because "what would it take to run this for real" is a question the showcase audience will ask.

### If better data is needed

| Option | Price | What it adds | Honest assessment |
|---|---|---|---|
| **Alpaca Algo Trader Plus** | **$99/mo** | Real-time SIP across all US exchanges, unlimited API calls, unlimited websocket symbols, real-time OPRA options | **The obvious upgrade if the mismatch matters.** It collapses the dual-feed architecture to one feed — same data in training and live — which removes §5.2's entire problem class. Same vendor, same keys, same code path |
| **Polygon / Massive Advanced** | **$199/mo** | Real-time consolidated, 20+ years history | Deeper history than Alpaca's ~10 years. Twice the price, a second vendor to integrate, and the stricter licensing posture in §20.1 (single-end-user limit, §5(d) derivative-works clause, delete-on-termination) |
| **Polygon / Massive Developer** | **$79/mo** | 10 years history, **15-minute delayed** | **Correction to Rev 8.2:** this tier is *not* real-time. It buys nothing Alpaca's free tier doesn't already provide for this project. Not recommended |
| **Databento** | Usage-based | Institutional-grade US equities, pay-as-you-go rather than subscription | Worth pricing if a specific dataset is needed for a bounded period; the usage model suits research bursts better than a monthly seat. Confirm current rates directly — pricing is metered, not a flat tier |

**Recommendation if an upgrade is ever needed: Alpaca Algo Trader Plus.** Not because it is cheapest — Polygon Developer is — but because it is the only option that removes an actual methodological problem rather than adding history the project doesn't need. Buy it to eliminate the feed mismatch, not to buy years.

**Trigger condition:** if the §5.2 transfer experiment shows IEX volume features do *not* transfer, and losing volume features materially degrades the signal-quality model, then $99/mo buys back a real capability. Otherwise the free tier is sufficient and the money is better not spent.

### If the project were ever taken live

Out of scope for the course (§3, permanently excluded) and not planned. Recorded so the answer is honest rather than improvised:

1. **Real-time data becomes mandatory** — a 15-minute-delayed feed cannot support a 5-minute-bar strategy. That is the $99/mo line above, at minimum.
2. **Subscriber status is re-examined.** Exchange agreements (§20.1 row 2) classify all subscribers as Professional unless they qualify as Non-Professional. Trading personal funds generally keeps non-professional status; trading anyone else's money, or trading in a business capacity, does not — and professional exchange fees are materially higher.
3. **The paper-only guardrail would have to be deliberately removed.** There is no live-money code path and a test enforces its absence (§8, §20.2 Harm 1). That is intentional friction, and any real-money move would need its own risk assessment before the guardrail came out — not a config flag.
4. **The professor has confirmed real-money trading is permitted but recommends against it** (`Decision_Tracker.md`). It remains outside this project's scope.
5. **Track record first.** Nothing in this project's evaluation design licenses a claim that the system is profitable. Walk-forward results are evidence about a hypothesis, not a track record; extended paper trading would come first.

## 10. Evaluation Framework (Course Step 2)

Two layers of success metric, both necessary.

### 10.1 Offline metrics (primary results layer)

**Trading metrics — the headline result.** Total and annualized return, Sharpe, Sortino, maximum drawdown, Calmar, profit factor, win rate, average win/loss, turnover, exposure, trade count, transaction-cost sensitivity. Prespecified primary comparison: **M-tier vs. B2 on Sharpe or maximum drawdown, net of costs, under walk-forward validation.**

**ML metrics — supporting, not headline.** Precision, recall, F1, ROC-AUC, PR curves, confusion matrices per regime, calibration, Brier score.

**News-filter metrics (if Plan A proceeds).** Trades suppressed/reduced/delayed; false suppression rate; missed winners vs. avoided losers; post-event performance; M4 vs. M3 increment; threshold sensitivity.

### 10.2 User-impact metrics (required second layer)

| Measure | Protocol | Target |
|---|---|---|
| **Decision comprehension** | 3 readers unfamiliar with the project, 5 minutes with the live dashboard, unaided. Each states (a) current regime, (b) open positions, (c) why the most recent decision came out as it did. Scored against the decision log | **≥ 8 of 9 correct**, no reader failing (c) |
| **Time to audit a decision** | Timed: from clicking a decision row to correctly naming the filter that caused the outcome | **Median under 60 seconds** |
| **Explanation trust check** | For 10 sampled explanations, the reader marks each claim "I can see where this came from" or "I can't" | **100% traceable**; any untraceable claim is a grounding failure and a release blocker |

**Why these and not "time saved."** Conventional user-impact metrics assume the user was doing the task manually. The honest analogue here is *auditability under time pressure*.

**Limitation to state honestly:** n=3 is a usability smoke test, not a study.

### 10.3 Robustness tests

Walk-forward only; bull/bear/sideways subperiods; 2–3× transaction-cost stress; delayed execution; missing-data handling; duplicate/stale news handling; out-of-distribution volatility; confidence threshold sweeps. **Plus the §5.2 feed-transfer check, reported alongside.**

### 10.4 Reproducibility rubric

Results regenerate from a clean clone using documented config and the documented data-acquisition step (§17.7).

## 11. Leakage Prevention (Week 1 artifact, ongoing)

- Walk-forward evaluation only; no future information at any pipeline stage.
- Event-time joins for all news–price alignment.
- News timestamp verification (freshness from first-publication time).
- Duplicate and stale headline removal before scoring.
- All AI/LLM outputs cached; backtests never call live APIs.
- Feature code self-reviewed specifically for lookahead bias before merge.
- **RTH filtering applied before any feature computation** (§9), so extended-hours bars cannot leak into features for a regular-session strategy.

## 12. Timeline (14 weeks)

| Weeks | Milestone (internal) | Deliverables | Official due date |
|---|---|---|---|
| 1–2 | Foundations | **Repo checklist — all six items**; data pipeline + validation (**§9 architecture, RTH filter, dataset hashing**); feature pipeline; **§5.2 feed-transfer validation experiment**; leakage checklist; all four logs; **news feasibility verdict**; **§20 Responsible AI charter**; **§21 focus-area declaration**; **pitch artifact (§19.4)** | **Milestone 1 — end of Wk 2** |
| 3–4 | Baselines + harness | B1/B2 running, walk-forward framework (14 folds), cost model, full metrics suite, B1/B2 results, **Data Card** | — |
| 5 | Regime prototype | Regime classifier (M1) first-cut wired end-to-end | **Milestone 2 — end of Wk 5** |
| 6 | Regime intelligence | Labeling finalized, models calibrated, M1 vs. B2 ablation. **Fallback checkpoint** | — |
| 7–8 | Signal-quality intelligence | Candidate-trade dataset, quality model (volume features per the §5.2 verdict), calibration, threshold tests, M2 ablation. **Fallback checkpoint at end of Wk 8** | — |
| 9 | **ALPHA — Milestone 3** | End-to-end flow on the Alpaca paper account, **IEX live feed**. **No news components required.** **Plus Model Cards + System Card** | **Milestone 3 — end of Wk 9** |
| 9–10 | Plan A (if GO) | News gate on cached historical scores; M3 ablation | — |
| 10 | Plan B gate · safety checks | Go/no-go on M4 and the query layer. **Red-team pass** (§20.2) | — |
| 11–12 | Interpretability + robustness + release candidate | Explanation agent, failure clustering, targeted tests, robustness suite, final results, architecture diagram, quick-start docs, fresh-clone test, demo script, **demo video draft**, **container**, **latency & cost report**, **user-impact run**. **Fallback checkpoint at end of Wk 11** | **Milestone 4 — end of Wk 12** |
| 13 | Polish for portfolio | Package repo/demo/report for employers; no new features | — |
| 14 | Ship | Final demo video, final report, live presentation. **Second user-impact run** | **Final Presentation — end of Wk 14** |

## 13. Work Breakdown (Solo Project)

1. **Data & pipeline** — ingestion, validation, RTH filtering, features, leakage prevention, news feasibility
2. **ML** — regime + signal-quality models, calibration, ablations, feed-transfer validation
3. **Systems** — risk engine, execution simulator, Alpaca integration, dashboard, containerization
4. **Evaluation & research** — harness, robustness tests, failure analysis, experiment log, latency/cost profiling
5. **Docs & demo** — documentation, model/system cards, architecture diagram, demo video, report

## 14. Logs (all started Week 1)

- **Decision log** — major system decisions with rationale
- **Experiment log** — changes tested, what improved, what didn't, what's fragile
- **AI usage log** — where generative AI was used, with provenance detail (§16)
- **Risk register** — live version of §15

## 15. Risk Register

*Project-execution risk. For system-behavior risk see §20.*

| Risk | Mitigation |
|---|---|
| Data leakage inflating results | Week 1 leakage checklist; walk-forward only; self-review of all feature code; cached AI outputs; RTH filter applied pre-feature |
| ~~Intraday data availability/cost~~ | **CLOSED 2026-08-30** — ten years of consolidated 5-minute history verified available at $0 (§9). This was the project's largest risk; it is now a solved problem |
| **Train/live feed mismatch** | **New and now the leading technical risk (§5.2).** Backtest runs on SIP, live on IEX, and IEX carries 3.16% of consolidated volume. Mitigated by scale-free volume features, and *validated* by the Week 1–2 transfer experiment — with a pre-committed decision to drop volume features entirely if they don't transfer |
| **Extended-hours bars contaminating features** | **New (§9).** 60% of SIP bars are outside regular hours. RTH filtering at the pipeline stage, enforced in code, not left to each consumer |
| Historical news unavailable or unreliable | Week 2 feasibility gate with three-way outcome; core project (B1–M2) is news-independent |
| Regime labels ambiguous | 3+1 scheme (§5.1); documented as a design decision; revised only with logged evidence |
| Signal-quality model overfits (few trades) | Ten years of 5-minute bars maximizes trade count; regularization; calibration + Brier score reported |
| Market-data licensing blocks repo reproducibility | **Confirmed** — Alpaca's T&C *and* Customer Agreement §30 prohibit redistribution. Mitigation: sample fixture + documented re-fetch script + `dataset_hash` (§17.7) |
| Published decision logs may constitute redistributable data | NASDAQ's "Information" definition reaches reconstructable data (§20.1 row 2). Mitigation: §20.5 — sample logs bounded to a short window, CI-enforced |
| Pretrained sentiment model has no declared license | §20.1 — don't vendor weights, or switch to an explicitly-licensed model at the Week 2 gate |
| Transaction-cost sensitivity at 5-minute bars | Cost-stress tests (§10.3) matter more here; report cost sensitivity prominently |
| Multi-strategy toggle dilutes evaluation rigor | Secondary strategies never enter the graded ablation ladder; the harness enforces it |
| LLM cost / API changes | Local model for bulk scoring; outputs cached; pinned model versions; budget in §9A |
| Solo bandwidth | Weekly journal; four logs; work-breakdown checklist; conditional tiers absorb slippage; named fallback checkpoints (§3) |
| Overfitting via repeated backtest iteration | Prespecify the primary metric and hypothesis before M1 experiments; log every experiment |
| Milestone timing mismatch | Corrected in Revisions 4 and 8; re-verify against Canvas each phase |

## 16. Generative AI Usage Policy — CONFIRMED by Professor (2026-08-24)

Coding agents are explicitly allowed course-wide (professor's email, the Intro Video, and the Phase 1 repo-hygiene lecture all agree).

- **Coding agents (system code):** allowed without restriction.
- **In-system use:** explanation agent and failure-analysis assistant only. LLMs never generate or modify trading logic and never make buy/sell decisions.
- **Written graded deliverables:** conservative default — AI assists thinking/structure/research; Henry writes the submitted prose; any kept AI-drafted text is cited.
- **Two different agreements apply** (§20.1): the desktop Claude app for development assistance is under consumer terms; the explanation service calls the API under commercial terms, which additionally provide that customer content is not trained on.
- All usage recorded in the AI usage log with provenance detail.
- **Anti-vibecoding practice:** the PRD is the spec and stays current; nothing merges without a test that would fail if the behavior were wrong; CI stays green and no test is disabled to make it so.

## 17. Success Criteria

1. The system runs end to end from ingestion through paper-trade decision, logging, and monitoring.
2. Each AI component is evaluated independently with the metrics in §10.
3. The full ablation through M2 is complete for the primary strategy; M3/M4 reported if gated in.
4. The AI-enhanced strategy improves at least one **prespecified** risk-adjusted metric versus B2 after costs — or the negative result is rigorously characterized.
5. Every trade decision has a grounded explanation that audits correctly against the decision log.
6. The top failure modes are identified, tested, and documented.
7. **A fresh clone reproduces headline results from documented instructions.** *(Licensing prohibits redistributing raw bars, so the repo ships a sample fixture, a re-fetch script, and the `dataset_hash`; the criterion is met when a fresh clone plus a legitimately-obtained dataset matching that hash reproduces the tables.)*
8. The release candidate builds and runs from the container image, and the latency & cost report is published with the results.
9. The user-impact protocol in §10.2 is run and reported, whatever the outcome.
10. Nothing in the public repo violates §20.5's publication constraints.
11. **Every reported result records the feed that produced it, and the §5.2 transfer-validation result is published with the Model Cards.**

## 18. Framing the Outcome

The prespecified hypothesis is that regime and quality filtering improve risk-adjusted performance. **A rigorous negative result is an acceptable and defensible outcome** — the deliverable is judged on coherence, evaluation quality, and honest failure analysis, not on beating the market.

## 19. Demo Walkthrough & Sample UI

### 19.1 How the trading works — plain-language pipeline walkthrough

The system is **not** an interactive advisor — it's a closed-loop paper-trading system a user watches, then reviews.

1. **Data pipeline** pulls SPY 5-minute bars and validates them, filtering to regular trading hours. No AI.
2. **Feature engineering** computes indicators. No AI — deterministic math.
3. **Strategy Engine** checks fixed rules; if triggered, proposes a candidate trade. No AI.
4. **Regime classifier (AI)** outputs trend probabilities and a volatility flag — describes the environment, doesn't propose trades.
5. **Signal-quality model (AI)** scores the candidate trade.
6. **News gate (AI, conditional)** — if built, checks whether headlines should delay or block the trade.
7. **Trade Decision Engine** combines these into one of four fixed outcomes via documented logic, not an LLM's judgment.
8. **Risk Engine** (no AI, ever) enforces sizing, stops, drawdown limits — a hard backstop.
9. **Execution** — if approved, placed on the Alpaca paper account.
10. **Decision log** records every input, output, and reason code.
11. **Explanation agent (AI)** reads that log and writes a rationale limited to what's in it.
12. **Dashboard** — what the user looks at (§19.2).
13. **Failure-analysis assistant (AI)** clusters losing trades statistically, then narrates the clusters.

*Steps 7 and 8 are load-bearing for §20.1: the trade decision is deterministic, and no AI output reaches it as an instruction.*

### 19.2 What the end user sees — sample UI

**Main dashboard:** header strip (regime label + probability, volatility flag, equity, today's P&L); equity curve vs. buy-and-hold (B1); open positions with active risk constraints; **decision feed** — most-recent-first rows with timestamp, decision badge, signal-quality score, and a one-line grounded explanation, expanding to the full DecisionRecord. *This screen is what §10.2 measures.* Persistent disclaimer: paper trading only; not investment advice.

**Strategy toggle panel** (backtest-only): momentum breakout (primary, live), MA trend, or mean reversion, with equity curve and basic metrics. Labeled "exploratory backtest — not part of the graded evaluation."

**Failure analysis view:** clustered failure modes with the LLM's interpretation and a link to each targeted test.

### 19.3 Sample demo script (Milestone 4 video, refined for Wk 14)

1. Open on the dashboard mid-session — current regime and equity curve vs. baseline.
2. Click into 2-3 real decisions — read the grounded explanation, show it matches the DecisionRecord fields exactly.
3. Show the results table: Sharpe/drawdown for B1→M2, the primary comparison vs. baseline.
4. Open the strategy toggle briefly — note these are exploratory by design.
5. Open the failure-analysis view — one real failure cluster and its targeted test.

### 19.4 Pitch artifact — 6-slide structure (Week 2 deliverable)

1. **The problem** — §1A issue + audience.
2. **The system in one diagram** — §4, annotated to show where AI is and deliberately is not.
3. **What makes it different** — §1A differentiator.
4. **How success is measured** — §10.1 + §10.2, and the §7 ablation ladder.
5. **Scope and risk** — §3 tiers with named fallback checkpoints; biggest risk and fallback.
6. **Where it stands** — repo link with green CI check, Week 1–2 progress, news feasibility verdict.

*Built: `PROJECT_BETA_Product_Demo.pptx` with speaker notes, and `Product_Demo.md` as the presenting script.*

## 20. Responsible AI Charter (required Milestone 1 material)

Covers **system-behavior risk** — what this thing could do to someone in the world — as distinct from §15's project-execution risk.

### 20.1 Licensing audit — VERIFIED 2026-08-30

Read against the published terms. **Good-faith reading, not legal advice.**

| # | Asset | Verified finding | Constraint it implies |
|---|---|---|---|
| **1** | **Alpaca market data** — dataset. *Two governing documents, both read* | **Confirmed prohibited, twice over.** Terms & Conditions: *"No part of the Service or Content may be copied, reproduced, republished, uploaded, posted, publicly displayed, encoded, translated, transmitted or distributed in any way (including 'mirroring')... without Alpaca's express prior written consent"*; Content is *"provided exclusively for personal and noncommercial access and use."* **Customer Agreement §30**: *"I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent,"* and it incorporates the NASDAQ OMX and Display Services agreements by reference *"if I am provided access to such data"* | **The public repo cannot contain the dataset.** Ship a sample fixture + re-fetch script + `dataset_hash`; state the constraint in the README. Personal, non-commercial academic use is exactly what this project is — only redistribution is blocked |
| **2** | **NASDAQ OMX / NYSE Display Services** — dataset, *conditional* | Non-professional subscribers: *"the Information is licensed only for personal use."* §1: *"Subscriber may not sell, lease, furnish or otherwise permit or provide access to the Information to any other Person."* **§12** defines "Information" to include *"any element of Information as used or processed in such a way that the Information can be identified, recalculated or re-engineered from the processed Information."* §12: *"All subscribers are deemed Professional or Business unless they are qualified as Non-Professional"* | (a) Personal-use posture, consistent with the plan. (b) **§12's derived-data reach** drives the publication constraint in §20.5. (c) **Non-Professional status must be affirmatively qualified** — the default is Professional. Relevant again in any live-trading scenario (§9B) |
| **3** | **Polygon / Massive (not subscribed)** — dataset | §1: *"personal, non-business, and non-commercial purposes."* §2: *"you may not use the Market Data to build an application intended for use by end users other than you."* **§5(d)** bars derivative works *"including... any investment strategy."* §8 requires deleting all Market Data on termination | Not currently relevant — no subscription, and §9 resolved without one. If ever revisited, §5(d)'s application to an academic backtest is ambiguous and needs Henry's own read |
| **4** | **FinBERT (Plan A only)** — model | **No license declared on the Hugging Face model card** — verified against the model's API metadata. Upstream repo (`ProsusAI/finBERT`) is Apache-2.0, but that covers the **code**, not the weights | Undeclared weights default to all-rights-reserved. **Do not vendor them.** Either load by pinned revision with the ambiguity disclosed, or choose an explicitly-licensed model at the Week 2 gate — probably worth the swap for a public portfolio repo |
| **5** | **Hosted LLM — outputs** | Consumer terms: *"we assign to you all of our right, title, and interest—if any—in Outputs."* Commercial terms §B: *"Customer... owns its Outputs,"* and *"Anthropic may not train models on Customer Content from Services"* | Explanations can be published. **Both agreements apply, to different uses:** the desktop app for development assistance (consumer), the API for the explanation service (commercial). Pin the model version in RunConfig |
| **6** | **Hosted LLM — usage policy** | Finance is a High-Risk Use Case: *"financial decisions, including investment advice..."* Conditions: qualified human review of advice *"directly affecting individuals or consumers"*, and AI-use disclosure where outputs reach consumers | **Compliant by design, and the proposal should say so.** The LLM never makes or influences a trade decision (§19.1 steps 7–8); it narrates a decision already logged. No external consumers. The dashboard disclaimer already meets the disclosure standard. **The strongest single point in the charter:** the constraint chosen for evaluation integrity is exactly what keeps the system outside the high-risk category |
| *(7)* | scikit-learn, XGBoost, pandas, pyarrow | Standard permissive OSS (BSD-3 / Apache-2.0 family) | Record resolved licenses in the dependency manifest |

**Own-repo license: MIT.**

**Still open:** confirmation, from Account → Documents, of how the Professional / Non-Professional classification was recorded.

**Sources:** [Alpaca Terms and Conditions](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf) · [Alpaca Customer Agreement](https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf) · [NASDAQ OMX Global Subscriber Agreement](https://files.alpaca.markets/disclosures/library/NASDAQ+OMX+Global+Subscriber+Agreement.pdf) · [NYSE Market Data Display Services](https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf) · [Alpaca market data plans](https://alpaca.markets/data) · [Massive/Polygon Market Data ToS](https://massive.com/legal/market-data-terms-of-service) · [Massive/Polygon pricing](https://massive.com/pricing) · [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) · [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) · [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) · [Anthropic Usage Policy](https://www.anthropic.com/legal/aup)

### 20.2 Safety plan — top 3 harms, each with a guardrail and a test

| # | Harm | Guardrail | Test |
|---|---|---|---|
| **1** | **Financial harm through misuse.** Someone clones the repo, points it at a live account, and loses real money — or reads the dashboard as investment advice | No live-money code path exists; the execution layer accepts only paper endpoints and credentials (§8). README and dashboard carry "paper trading only; not investment advice" — which also satisfies the provider's AI-use disclosure standard (§20.1 row 6). No performance claim without its cost model and walk-forward caveat | Unit test: the execution layer **rejects** a non-paper endpoint or live credential set. Documentation test: disclaimers present, CI-asserted as a string check |
| **2** | **Over-trust in a wrong or invented explanation** — the failure mode that makes an "explainable" system worse than an opaque one | Hard grounding rule: prompt contains only DecisionRecord fields plus reason-code documentation; no market data, no model access, no external source. Reason codes from a fixed enum. Same rule for the failure-analysis narrative | Grounding audit on ≥50 random explanations: every factual claim maps to a field in the source record. Target 100%; **any hallucinated claim is a release blocker.** Plus the §10.2 trust check |
| **3** | **Misleading performance claims.** Leakage, overfitting, an under-modelled cost assumption, **an unstated feed limitation, or extended-hours contamination** produces a result that looks good and isn't | Walk-forward only, point-in-time features, cached AI outputs, prespecified primary metric fixed before M1 experiments, every experiment logged, negative results framed as legitimate (§18). **Feed provenance and the RTH filter stated wherever results are reported** | Leakage test (shifting inputs forward one bar changes no historical feature value); backtest cache-only enforcement; 2–3× cost-stress runs reported *alongside* headline numbers; **feed recorded in every results table** |

**Fourth harm, tracked (Plan A only): prompt injection via news headlines.** Guardrail: extraction returns a constrained schema; the deterministic policy layer consumes only those fields; no free headline text reaches the trading path or the explanation prompt. Test: the **Week 10 red-team pass** with adversarial instruction-shaped headlines. If Plan A is NO-GO, the pass targets the explanation service instead.

### 20.3 Fairness note

A single-instrument paper-trading system has no human demographic groups in its data, and forcing a demographic frame onto it would be dishonest. The real analogue is **market conditions**:

- **Groups at risk:** market regimes (uptrend / downtrend / choppy), volatility states, and calendar subperiods. A filter trained mostly on trending data can look excellent in aggregate while being harmful in choppy conditions — and a user who starts during that regime gets the bad version of the system.
- **The one fairness check to run:** a **per-regime and per-volatility-state performance breakdown** for the M-tier system versus B2 — accept/reject rates, realized performance, and calibration, sliced by regime. **Any regime in which the filtered system underperforms the unfiltered baseline is reported explicitly**, not averaged away.
- **Honest limitation:** some regimes will have thin sample support. Where a slice is too thin to support a claim, report the count rather than the ratio.

### 20.4 Privacy plan

| Data | Why | Retention | Minimization |
|---|---|---|---|
| Alpaca API key / secret, paper account ID | Fetch data and place paper orders | Life of the project; rotated if exposed | **Environment variables only — never committed.** `.gitignore` covers `.env`; secret scanning enabled; CI uses repository secrets |
| Decision log (DecisionRecords) | Single source of truth; basis of every explanation and audit | Semester + final report | Market state, model outputs, reason codes only. **No personal data.** *Contains market prices — see §20.5* |
| Cached LLM prompts/responses | Reproducibility and cost control | Semester | Assembled from DecisionRecord fields only. Plan A caches store headline hashes and structured fields, not full text |
| Usability-check notes (§10.2) | Evidence for the user-impact metric | Until the final report | Responses only, not participant identity |

**Minimization principle:** the system collects nothing about anyone. Single-user, single-account, observational — the correct posture is **"never start collecting it."** If the interactive query layer is ever built, user-typed queries become the first new data class and need a retention line here first.

### 20.5 Publication constraints — what may and may not go in the public repo

| Artifact | Publishable? | Reasoning |
|---|---|---|
| Raw OHLCV bars | **No** | Alpaca T&C and Customer Agreement §30 both prohibit it |
| Small sample fixture (bounded window) | **Yes, minimally** | Enough to run tests; not a usable dataset |
| Re-fetch script + `dataset_hash` | **Yes** | Code and a hash — makes reproduction verifiable without redistribution |
| **Full multi-year decision logs** | **No** | DecisionRecords carry entry/stop/target/fill prices; across years of 5-minute bars this approximates a price series that *"can be identified, recalculated or re-engineered"* (§20.1 row 2) |
| **Sample decision logs — bounded window** | **Yes** | A few trading days, enough to show schema, grounding and dashboard. CI-enforced (PRD §5.10) |
| Aggregate results tables, equity curves, metrics | **Yes** | Statistics over the data, not reconstructable to bars |
| Trained model artifacts | **Yes** | Parameters learned from the data, not the data. Hash them |
| Pretrained third-party weights | **No** | Not ours to redistribute; FinBERT's position is undeclared |
| Full news headline text | **No** | Provider terms; the cache stores hashes + structured fields by design |
| Generated explanations | **Yes** | Outputs are assigned to the user (§20.1 row 5) |

**Rule of thumb:** if someone could rebuild a usable price series from it, it doesn't go in the repo. State the constraint in the README so a reader understands *why* the dataset is absent — that transparency is part of the reproducibility story, not an apology for a gap.

## 21. Optional Focus Areas — Declared

**Evaluation & Responsible AI (primary) + Model & System (secondary).**

| Area | Declared | Why |
|---|---|---|
| **Evaluation & Responsible AI** | ✅ **Primary** | The ablation ladder (§7), walk-forward-only validation, cost-stress and subperiod robustness (§10.3), per-regime fairness disaggregation (§20.3), **the feed-transfer validation experiment (§5.2)**, latency/cost profiling, the ≥50-sample grounding audit, and failure analysis with targeted tests. A custom evaluation suite tied to the use case |
| **Model & System** | ✅ Secondary | Two trained classical models with calibration; a composed multi-stage gating pipeline; grounded LLM services under a hard structural constraint; conditional structured extraction under Plan A |
| Data | ❌ Not declared | Careful work but standard market-data hygiene, not novel collection or splitting |
| Application & Deployment | ❌ Not declared | Dashboard and container ship, but they serve the evaluation story rather than being the contribution |

**Why not claim all four.** A proposal claiming everything reads as unfocused and invites the "grab-bag" criticism the rubric warns against. Two declared areas, with explicit reasons for declining the other two, is a stronger signal.