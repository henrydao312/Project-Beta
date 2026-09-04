# PROJECT BETA — Milestone 1 Submission

**DRAFT for Henry to rewrite in his own prose.** Structure and evidence are
assembled here; per the AI-usage policy (Instruction.md §Generative AI Usage
Policy) the submitted prose is Henry's. Items needing his input are marked
`[HENRY]`. Deliverable is a single PDF.

**CIS 5980 AI Capstone · Fall 2026 · AI Engineering Track · Henry Dao and Jacky**

`[HENRY: add Jacky's surname, and confirm how faculty want a two-person M1 attributed.]`

Milestone 1 has three distinct requirement sets in the course materials. They
overlap but none subsumes the others, so all three are answered below.

---

# Part A — The eight-item deliverable spec

## A1. Track declaration

**AI Engineering Track.**

## A2. Problem, target users, value proposition

**The problem.** Retail traders and junior quantitative researchers act on
trading signals they cannot fully trust: noisy, unfiltered, and impossible to
audit after the fact when a trade goes wrong.

**Target users.** Discretionary retail traders and junior quantitative
researchers who want systematic, explainable, risk-controlled signal filtering
rather than a black box.

**The system.** A market-regime classifier and a signal-quality model gate a
transparent, rule-based momentum-breakout strategy on 5-minute SPY bars. A
deterministic risk engine enforces limits and can halt the loop. Every trade
decision receives a grounded, plain-English explanation. The same pipeline
extends to BTC/USD as a graded secondary track and to single-leg SPY options as
a validated execution layer.

**What makes it different.** Most public AI trading projects let a language
model make the trade call and show one flattering backtest. PROJECT BETA never
lets AI touch trading logic: AI only gates a strategy a reader can check, and
every explanation is grounded in a logged decision, audited at 50+ samples.
Each AI component's contribution is isolated by an ablation ladder under
walk-forward validation, and a rigorous negative result counts as a legitimate
outcome. **And each asset class makes only the claim its data can support**,
which is a discipline most student projects skip.

The differentiation is AI-engineering discipline: auditability, grounding,
honest ablation. It is not a claim to have found a better trading strategy.

## A3. Success metrics — both layers

### Offline (primary results layer)

The primary comparison is **prespecified and locked** in
`EVALUATION_PROTOCOL.md`, dated before any model was trained:

| | |
|---|---|
| Systems | M2 versus B2, equities only |
| Metric | Annualised Sharpe, net of costs |
| Estimator | 14 non-overlapping 6-month out-of-sample windows, pooled |
| Test | Paired stationary block bootstrap, 10-day blocks, 10,000 resamples, 95% interval |
| Decision rule | Interval excludes zero **and** point estimate ≥ +0.20 **and** the sign survives 2x cost stress |

The Outline originally said "Sharpe **or** maximum drawdown", which is two
chances at one claim. One metric is now chosen; maximum drawdown is reported as
secondary with an interval and no claim language.

**What the design can detect.** At 14 folds and 1,764 out-of-sample daily
observations, the minimum detectable Sharpe difference is approximately **0.34**
at a correlation of 0.90 between filtered and unfiltered returns. A true
improvement smaller than roughly 0.3 Sharpe is very unlikely to be detected.
That is a property of ten years of one instrument, and it is written down now
rather than discovered in Week 13.

### User-impact (required second layer)

| Measure | Protocol | Target |
|---|---|---|
| Decision comprehension | 3 readers unfamiliar with the project, 5 minutes with the dashboard, unaided. Each states the current regime, open positions, and why the most recent decision came out as it did | ≥ 8 of 9 correct, none failing the third |
| Time to audit a decision | Timed from clicking a decision row to naming the filter that caused the outcome | Median under 60 s |
| Explanation trust check | 10 sampled explanations; reader marks each claim traceable or not | 100% traceable; any untraceable claim is a release blocker |

**Why these and not "time saved."** Conventional user-impact metrics assume the
user was doing the task manually. The honest analogue here is auditability under
time pressure. **Limitation stated plainly: n=3 is a usability smoke test, not a
study.**

## A4. Tech stack and compute budget

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Data and broker | Alpaca Trading API, Basic (free), dual-feed |
| Data handling | pandas, pyarrow (Parquet), hashed datasets |
| Classical ML | scikit-learn, XGBoost |
| LLM | Hosted API (Claude), pinned version, explanation and failure narrative only |
| Frontend | Browser UI served locally |
| Testing / CI | pytest, GitHub Actions |
| Packaging | Docker (Week 12) |

| Cost item | Amount |
|---|---|
| Model training | CPU only, no GPU |
| Backtests | $0 by construction, cache-only |
| **Market data** | **$0, confirmed by direct measurement across all three asset classes** |
| LLM API | ~$10-30/month `[HENRY: still an estimate. State the method: measured cost per decision times expected decision count. One real measurement closes it once the explanation service exists.]` |
| CI | Free tier |

## A5. Risks and mitigations

**Named biggest risk, with a fallback**, as the course asks. It has changed
since the proposal was drafted, and the change is itself evidence:

| Risk | Status |
|---|---|
| ~~Intraday data availability and cost~~ | **CLOSED 2026-08-30.** Ten years of consolidated 5-minute history at $0 |
| ~~Real-time data may be 15-minute delayed~~ | **CLOSED 2026-09-01.** IEX measured real-time, streaming entitled |
| ~~Train/live feed mismatch~~ | **CLOSED 2026-09-02 by measurement.** See A9 |
| **Schedule: a live paper loop running unattended by Week 9** | **The leading risk now.** Named fallback checkpoints at Weeks 6, 8 and 11 decide what is cut. The guaranteed core alone is a complete capstone |
| Data leakage inflating results | Leakage checklist, walk-forward only, point-in-time instrument universe, RTH filter before features, cached AI outputs |
| Look-ahead via options contract selection | Point-in-time universe `universe_as_of(t)`; contracts chosen as of decision time, never because they are known to have traded |
| Autonomous loop cannot be stopped mid-session | Kill switch, six auto-halt triggers, deliberate restart, rollback via versioned artifacts |
| Scheduled job silently fails to run | Project moved outside macOS TCC-protected folders; scheduled jobs verified through the scheduler, never only by hand |
| Invalid credentials producing a plausible failed run | Startup authentication check that aborts on non-200. A non-empty check is not a check |
| Secondary tracks over-claimed | Tiers fixed by measured fold counts; crypto's fold count travels with every number; options makes no performance claim |
| **Team bandwidth and coordination** | Two-person group, approved 2026-09-03 with expectations unchanged by size. Onboarding costs one to two weeks and review adds latency, so **no critical-path work is assigned to the second owner**: a stall degrades scope rather than blocking the core. Interface contracts keep each stream separable; weekly journal, four logs, conditional tiers and named checkpoints as before |

Full register in `Project_Outline.md` §15.

## A6. Optional focus areas

**Evaluation & Responsible AI (primary) + Model & System (secondary).**

Data and Application & Deployment are **declined**, with reasons: the data work
is careful but is standard market-data hygiene rather than novel collection, and
the dashboard and container serve the evaluation story rather than being the
contribution. Two declared areas with explicit reasons for declining the other
two is a stronger signal than four checkboxes.

## A7. Repository

`[HENRY: repo URL. Confirm on Canvas whether the grader must be able to open it;
if so, either add course staff as collaborators or make it public, which
requires the history rewrite first.]`

Six-item checklist, all present and CI-enforced:

- `README.md` with quick start, installation, licence, **and the data-licensing
  constraint explaining why the dataset is absent**
- `LICENSE` — MIT
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- Issue labels: `bug`, `enhancement`, `documentation`, `good first issue`
- `.github/workflows/ci.yml` — green on every commit

**82 tests passing, 1 deliberate skip** (a drift canary for a service that does
not exist yet). The suite is not decorative: it asserts the disclaimer strings,
that no market data or verification report is committed, that no credential
literal is committed, that the evaluation protocol is locked, that a second data
adapter satisfies the provider interface, and that unsupported vendor
capabilities raise a typed error rather than returning an empty result.

## A8. Pitch artifact

Six-slide deck, `PROJECT_BETA_Product_Demo_Rev11.pptx`, with speaker notes, and
`Product_Demo.md` as the presenting script.

---

# Part B — The Design Checklist (five items)

| Item | Answer |
|---|---|
| Simple, defensible unique value proposition | A2 above |
| Clear primary user and problem | A2 above |
| **Role of AI in the product** | **Background automation.** The AI runs unattended inside a closed loop: it classifies the market, scores candidate trades, and afterwards writes explanations. The user watches and reviews and never converses with it to get a trade decision. Interaction style: **static dashboard**, browser, served locally |
| **High-level architecture** | Frontend: local browser dashboard. Backend: vendor-agnostic `MarketDataProvider`, data pipeline, feature engineering, Strategy Engine, Trade Decision Engine, Risk Engine with halt control, instrument selection, execution layer, decision log, evaluation harness — all deterministic. AI layer: two local classical models plus two hosted-LLM services that read the decision log only. **The boundary that matters: the AI layer never writes into the trade decision path** |
| **MVP feature set and timeline** | The guaranteed core in `Project_Outline.md` §3 is the MVP and alone is a complete capstone. Fourteen-week timeline in §12 |

**Part I — product and experience.** Answered above, plus the platform model:
self-contained, single-user, local, containerized. Serverless is rejected on
shape, since the trading loop is long-running and stateful. **Public cloud
hosting is rejected on licensing**: the data licence grants personal,
non-commercial use and the subscriber agreement bars furnishing the information
to another person, so a publicly hosted dashboard serving live market data would
breach the licence the project depends on.

**Part II — AI architecture pattern.** **Tier 1, Prompt-Centric**, for both LLM
services. Walking the decision tree as given: *could a prompt-centric solution
meet your quality and safety needs? Yes.* The tree terminates there. Confirmed
against later branches: the Explanation Service is *forbidden* from touching
anything but the decision log, which is stricter than merely not needing tools,
so not Tool-Augmented; no document corpus, so no RAG; no multi-step planning, so
nothing agentic.

**The lowest tier is also the safest here, and that is the point.** The reason
the explanation service is prompt-centric is the grounding constraint. A higher
tier would mean giving the LLM access to more than the log, which would weaken
the property the whole project rests on. Cost discipline and safety discipline
point the same way.

The regime classifier and signal-quality model are **not on this spectrum at
all**: it orders LLM application patterns, and these are conventional supervised
learning on tabular features.

**Part III — task inventory and build vs buy.**

| # | AI task | Technology | Build or buy |
|---|---|---|---|
| 1 | Classify current market conditions | Classification, tabular. Logistic regression → RF / XGBoost, local | **Build** |
| 2 | Score a candidate trade's quality | Classification, tabular. XGBoost, local | **Build** |
| 3 | Explain each trade decision | Text generation. Hosted LLM, pinned | **Buy** |
| 4 | Narrate computed failure clusters | Text generation over precomputed statistics | **Buy** |

Not used, stated deliberately: retrieval/RAG (no corpus), speech, TTS, vision,
and text classification/extraction. **Buy** the language model, because text
generation is commoditized and is not where the differentiation lives. **Build**
the classifiers, because tabular regime classification has no managed service
and their calibration and per-fold evaluation are the substance of the ablation.

---

# Part C — Responsible AI charter (four artifacts)

## C1. Licensing audit

Read against published terms. Good-faith reading, not legal advice.

| Asset | Finding | Constraint it implies |
|---|---|---|
| **Alpaca market data** | Terms and Conditions bar copying, republishing or distributing; Customer Agreement §30 independently bars reproducing, distributing or commercially exploiting market data | **The repo cannot contain the dataset.** Sample fixture + re-fetch script + `dataset_hash`, constraint stated in the README. Applies equally to equity, crypto and options bars |
| **NASDAQ OMX / NYSE Display Services** | Licensed for personal use; §12 extends "Information" to any element "used or processed in such a way that the Information can be identified, recalculated or re-engineered" | Drives the publication constraints below, **and rules out publicly hosting the dashboard.** Non-Professional status must be affirmatively qualified `[HENRY: still open, ask Alpaca support in writing]` |
| **Hosted LLM, outputs** | Consumer terms assign output rights to the user; commercial terms state Anthropic may not train on customer content | Explanations can be published. **Both agreements apply**: desktop app for development assistance, API for the in-system service. Model version pinned |
| **Hosted LLM, usage policy** | Finance is a High-Risk Use Case covering "financial decisions, including investment advice" | **Compliant by design.** The LLM never makes or influences a trade decision; it narrates a decision the deterministic engine already made. No external consumers. **The strongest point in this charter: the constraint chosen for evaluation integrity is what keeps the system outside the high-risk category** |
| scikit-learn, XGBoost, pandas, pyarrow | Permissive OSS | Resolved licences recorded in the dependency manifest |

Own-repo licence: **MIT**.

## C2. Safety plan — three harms, each with a guardrail and a test

| Harm | Guardrail | Test |
|---|---|---|
| **Financial harm through misuse.** Someone clones the repo, points it at a live account, and loses real money, or reads the dashboard as advice | No live-money code path. Paper endpoints and paper credentials only. Halt control lets an operator stop the loop. README and dashboard carry "paper trading only; not investment advice" | Unit test: the provider **rejects a non-paper trading host** at construction. CI-asserted disclaimer strings. One test per auto-halt trigger asserting no order follows |
| **Over-trust in a wrong or invented explanation** — the failure mode that makes an "explainable" system worse than an opaque one | Hard grounding rule: the prompt contains only DecisionRecord fields plus reason-code documentation. No market data, no models, no external sources. Reason codes from a fixed enum | Grounding audit on ≥50 random explanations; every factual claim must map to a field in the source record. **Any hallucinated claim is a release blocker** |
| **Misleading performance claims** through leakage, overfitting, an unstated feed limitation, or a secondary track read as if it carried the core's weight | Walk-forward only, point-in-time features and instrument universe, cached AI outputs, **a prespecified primary metric locked before any M-tier experiment**, every experiment logged, negative results framed as legitimate. Feed, asset class and fold count recorded wherever results appear | Leakage test (shift-forward invariance); backtest cache-only enforcement; 2x and 3x cost-stress runs reported alongside headline numbers; schema test asserting every results row carries `asset_class` and `n_folds`; **test asserting the evaluation protocol is locked** |

## C3. Fairness note — three steps

**Framing, stated openly.** The lecture's examples are human groups. A
single-instrument paper-trading system has no human demographic groups in its
data, and inventing one would be dishonest. The real analogue is **market
conditions**, and the adaptation is deliberate: the substance the fairness
requirement protects, *does this work for everyone it is applied to or only on
average*, maps exactly onto regimes.

**Step 1 — the groups.** Market regimes (uptrend, downtrend, choppy),
volatility states, and calendar subperiods. A filter trained mostly on trending
data can look excellent in aggregate while being actively harmful in choppy
conditions, and a user who happens to start during that regime gets the bad
version of the system.

**Step 2 — the check.** Per-regime and per-volatility-state breakdown of M2
versus B2: accept/reject rates, realised risk-adjusted performance, and
calibration. **Any regime in which the filtered system underperforms the
unfiltered baseline is reported explicitly**, not averaged away. No significance
claim is made on any slice with fewer than 60 out-of-sample trading days; those
slices report the count rather than the ratio.

**Step 3 — one concrete mitigation.** If a regime is found where the filtered
system underperforms B2, the signal-quality threshold becomes
**regime-conditional**: the model abstains rather than participates where it
demonstrably adds no value. This is a real change to the Trade Decision Engine,
already present as the `risk.regime_abstain` RunConfig parameter, not a note in
the report.

**Honest limits of that mitigation.** Abstention **reduces harm without fixing
the model**: the filter still does not work in that regime, it simply stops
being consulted there. It **costs trade count** in the abstaining regime, which
weakens the statistical power of exactly the slice already least understood, a
self-reinforcing blind spot worth naming. It **inherits the regime classifier's
own errors**. And with a single asset and finite history, some regimes will have
thin sample support, so a threshold tuned on a thin slice risks fitting noise.

## C4. Privacy plan

| Data | Why | Retention | Minimization |
|---|---|---|---|
| Alpaca API key and secret | Fetch data, place paper orders | Life of project, rotated if exposed | **Environment variables only, never committed.** `.gitignore` covers `.env`; secret scanning on; CI uses repository secrets; a CI test scans tracked files for credential-shaped literals |
| Decision log | Single source of truth for every explanation and audit | Semester + final report | Market state, model outputs, reason codes. **No personal data** |
| Cached LLM prompts and responses | Reproducibility and cost control | Semester | Assembled from DecisionRecord fields only |
| Usability-check notes | Evidence for the user-impact metric | Until the final report | Responses only, not participant identity |

**Minimization principle: the system collects nothing about anyone.**
Single-user, single-account, observational. The correct posture is never to
start collecting it.

**Data-subject rights (see, correct, delete).** Not applicable, and stated
rather than silently omitted: there are no external users and no personal data,
so there is no subject whose data could be shown, corrected or deleted. The only
personal data in scope is Henry's own credentials, which he controls directly.

**Third-party API data policies.** The LLM provider's commercial terms state
that Anthropic may not train models on customer content, and prompts carry only
market and model state. The course warns that prompts and logs may contain
personal information; here they structurally cannot, because prompts are
assembled from DecisionRecord fields which contain no personal data by schema.

**Publication constraints.** Raw bars, full multi-year decision logs and
verification reports are excluded from the public repo, because a full decision
log across years of 5-minute bars approximates a price series that "can be
identified, recalculated or re-engineered". Aggregate results tables, bounded
sample logs, model artifacts and generated explanations are publishable. The
rule of thumb: if someone could rebuild a usable price series from it, it does
not go in the repo. **Enforced by CI, not by memory.**

**Incident on record.** On 2026-09-01 two verification reports carrying
per-session volume were committed and briefly pushed to a public repository.
Contained by making the repository private within roughly 30 minutes. The files
remain in history and a rewrite is required before the repo goes public. The
guardrail gap that allowed it, a prefix-only filename match, is fixed and
tested. Recorded here rather than quietly repaired, because a publication
constraint is only credible if its failures are logged too.

---

# Appendix — what was measured in Weeks 1 and 2

Included because the course asks for controlled risk rather than absent risk,
and because two of the three risks named at proposal time are now closed by
measurement rather than argument.

**Data architecture, closed at $0.** Eight verification questions answered by
direct API probe: SIP 5-minute history from 2016-06-10 (10.2 years); IEX from
2021-06-10; SIP historical entitled but recent SIP not (403) and SIP streaming
not (409); **IEX measured genuinely real-time with an entitled websocket stream
delivering trades ~0.1 s old**; BTC/USD continuous from at least 2021-06-10;
options bars from 2024-01-18.

**Asset-class tiers, set by arithmetic rather than preference.**

| Track | History | Folds at 30/6/6 | Tier | Minimum detectable ΔSharpe |
|---|---|---|---|---|
| Equities (SPY, SIP) | 123 months | **14** | Graded core | 0.34 |
| Crypto (BTC/USD) | 63 months | **4** | Graded secondary | 0.63 |
| Options (SPY) | 31 months | **0** | Validated execution layer | no performance claim |

Options cannot be graded because one fold consumes 42 months and 31 months
cannot become 42. A shortened scheme was **explicitly considered and declined**:
27-month folds would give options exactly one fold with a minimum detectable
difference of 1.27 Sharpe, which could only ever confirm the null, while
halving the equity training window to improve its own detection threshold from
0.35 to 0.31. The trade is bad in both directions, and the arithmetic is in
`scripts/analysis/fold_power.py`.

**The tier labels are a consequence of estimator arithmetic, not a naming
convention.** A Sharpe difference is a noisy ratio of moments whose error falls
as 1/sqrt(days); a fill-feasibility rate is a proportion whose error falls as
1/sqrt(selections). The same 6-month held-out window that cannot distinguish a
real edge from noise pins a fill rate to ±3 to ±7 percentage points.

**The feed-transfer experiment, run in Week 2 rather than before Week 7.** The
graded backtest trains on SIP; the live loop reads IEX, which carries a median
3.16% of consolidated volume. The design response was that every volume-derived
feature must be scale-free. That was an assumption, so it was tested over the
full 2021-2026 overlap: 102,243 SIP RTH bars, 101,780 IEX, 101,390 aligned
observations.

| Feature | Pearson | Spearman | Worst year | KS |
|---|---|---|---|---|
| vol_tod (primary) | 0.557 | **0.572** | 0.510 | 0.069 |
| vol_ratio | 0.766 | 0.674 | 0.624 | 0.067 |
| vol_z | 0.785 | 0.664 | 0.608 | 0.016 |
| trades_ratio | 0.736 | 0.664 | 0.622 | 0.046 |

**Thresholds were fixed before the run: keep at Spearman ≥ 0.70, drop below
0.50.** No feature cleared the bar. **The pre-committed decision was honoured
and volume-derived features are dropped**, from the models and from the strategy
rules alike, since a volume threshold inside a rule carries the identical
train/live mismatch.

Three findings beyond the verdict. The KS statistics of 0.016 to 0.069 mean the
failure is **errors-in-variables, not distribution shift**: a SIP-trained model
would meet a noisy version of the same input rather than an out-of-distribution
one, with roughly 58% of the feature's variance at inference being noise.
**IEX regular-session coverage is 99.6%** of SIP bars over five years, far
better than an earlier small-sample reading suggested. And the time-of-day
baseline transferred worst of the four, because on a thin feed a single
five-minute slot gives a noisy denominator: the more data a scale-free baseline
pools, the better it transfers.

**This is the project's methodology working as designed.** The pre-commitment
was written to stop a threshold being chosen after the answer was known, and the
first time it bound, it bound against the project's own preference.
