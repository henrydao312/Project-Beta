# PROJECT BETA — Decision Tracker

Live tracking doc for every open/undecided item across `Project_Outline.md`, `PROJECT_BETA_PRD.md`, and `Instruction.md`.

**Status legend:** 🔴 Blocking · 🟡 Needed soon · 🟢 Deferred by design · ✅ Resolved

**Last major update: 2026-09-01 (evening)** — **Week 1 data verification COMPLETE, and all asset-class roles decided.** Q2/Q2b closed: the IEX free tier is genuinely real-time and IEX streaming is entitled, so no paid data tier is required for Milestone 3. Asset-class tiers set (**Shape A**), with the architecture built so the options-forward upgrade is a bounded post-course job. **Nothing on the data or design side now blocks building.**

> **Companion document: `Upgrade_Path.md`** — the six architecture seams, what options delivers this semester, the post-course roadmap, the vendor comparison, and the Week 6 gate. Read it before writing the data layer.

**Previous: 2026-08-31** — News gate dropped in favour of options. M1 repo built, committed, pushed private. Crypto verified.

**Previous: 2026-08-30** — Week 1 data verification begun; full 85-page Phase 1 deck read. Docs at Outline Rev 10, PRD v2.0.

> **Provenance note.** The first deck review covered 45 of 85 pages while describing itself as complete. Anything dated before 2026-08-30 referencing "the deck" was working from a partial read.

---

## ✅ Asset-class tiers — DECIDED 2026-09-01

**Shape A for the course. Shape B (options-forward) is the post-course upgrade, with the seams built now.**

| Track | Data | Tier | What it claims |
|---|---|---|---|
| **Equities (SPY, SIP)** | 122 months, ~14 folds | **Graded core** | Full walk-forward, full ablation B1→B2→M1→M2. The primary claim rests here |
| **Crypto (BTC/USD)** | ~63 months, ~4 folds | **Graded secondary** | A real validated result, explicitly underpowered. **The fold count travels with every reported number.** Tests generalisation; never supports a claim alone |
| **Options (SPY)** | 31 months, 0 folds | **Validated execution layer** | Quantitative, with a genuine train/test split, making **no strategy-performance claim** |

**Definitions, so the labels are not decorative.** A *graded* tier makes a **performance** claim backed by walk-forward validation. A *validated execution layer* makes a **capability and feasibility** claim, quantitatively and out-of-sample, about whether the system's decisions could actually be executed. The dividing line is the kind of claim, not the quality of the work.

**The ablation ladder is equities-only.** One table, four rungs, fourteen folds. Crypto and options appear in a separate cross-asset generalisation section where the limits of each are stated plainly.

**Why "validated execution layer" and not "demonstration".** Options can support a real statistical result today: fill-feasibility rates with confidence intervals, and a held-out test of the contract-selection rule (fit on ~25 months, test on ~6). That is out-of-sample validation of the selection rule — it simply is not a walk-forward performance claim.

**Rejected: swapping options to graded secondary and crypto to demonstration.** Not a judgment call — arithmetic. A graded tier requires walk-forward folds; options has zero at 30/6/6, and 31 months cannot become 42. Crypto's 4 folds are free evidence that demoting would discard. *Prominence* is a separate axis from grading tier and remains available: options can take most of the engineering and headline the Week 12 demo without a tier change.

## 🔴 Open and blocking

| Item | Status | Notes |
|---|---|---|
| **Walk-forward fold arithmetic: is there a validation window?** | 🔴 **Decide before the harness (Wk 3)** | The docs say "36/6/6" and "one fold requires 48 months", which implies train/validation/test. `WalkForwardConfig` had `train/test/step` and no validation window, so one fold cost 42 months. The two readings give different fold counts: **48-month folds → 13 equity / 3 crypto; 42-month folds → 14 equity / 4 crypto.** Options is 0 either way, so the tier structure is unaffected. `config.py` now implements the 48-month reading, because the signal-quality acceptance threshold has to be chosen somewhere and choosing it on the test window is leakage. **Three options:** (a) keep 48, update "~14"/"~4" to 13/3 everywhere; (b) drop the validation window and document how thresholds avoid test contamination; (c) carve the validation window out of the 36 (30 train / 6 val / 6 test), keeping 14 folds *and* a clean threshold split. **(c) is the answer, and it is now measured, not argued.** `scripts/analysis/fold_power.py` computes the power of each scheme: total out-of-sample coverage is capped by total history, not by fold length, so shortening the fold from 48 to 27 months moves the minimum detectable Sharpe difference only from 0.35 to 0.31 while halving the training window and its regime variety. **27 months buys options exactly 1 fold**, with a minimum detectable difference of **1.27 Sharpe** over a 6-month test window inside a single regime: a label upgrade with no evidence behind it. 30/6/6 step 6 gives 14 equity folds, 4 crypto, 0 options, keeps every published figure intact and adds the validation window at no cost. |
| **Feed-transfer validation experiment** | ✅ **RUN 2026-09-02. Verdict: PARTIAL, and the pre-committed rule resolves PARTIAL-with-an-empty-keep-list to DROP. Awaiting Henry's decision to honour it.** | Backtests train on SIP volume; live runs on IEX at ~3% of the magnitude. Scale-free features *should* transfer — that's an assumption, so test it: compute the volume features from both feeds over the overlapping 2021–2026 period, correlate bar-by-bar. **Pre-committed:** strong agreement → keep and publish the correlation; weak → **drop volume features entirely** and record that IEX proved unrepresentative. Must conclude before Week 7 |
| **History rewrite before the repo goes public** | 🔴 **Before Week 12** | See the M1 table |
| **Documentation pass** | ✅ **DONE 2026-09-01** | Outline Rev 11, PRD v3.0 |
| ~~Crypto track role~~ | ✅ **CLOSED 2026-09-01** | Graded secondary |
| ~~Options track shape~~ | ✅ **CLOSED 2026-09-01** | Validated execution layer |
| ~~IEX real-time latency (Q2/Q2b)~~ | ✅ **CLOSED 2026-09-01** | Real-time; streaming entitled |
| ~~Week 10 red-team target~~ | ✅ **Never actually open** | `Instruction.md` already specifies "prompt injection via news headlines **or the explanation service if Plan A is NO-GO**". News is NO-GO → **the explanation service** |

## ✅ Feed-transfer experiment — RESULT (2026-09-02)

Run over the full 2021-06-10 to 2026-08-30 overlap: 102,243 SIP RTH bars,
101,780 IEX RTH bars, 101,390 aligned observations on the primary feature.
Artifact: `artifacts/transfer_check_d8d4297b.json`.

| Feature | Pearson | Spearman | Worst year | KS |
|---|---|---|---|---|
| **vol_tod** (primary) | 0.557 | **0.572** | 0.510 | 0.069 |
| vol_ratio | 0.766 | 0.674 | 0.624 | 0.067 |
| vol_z | 0.785 | 0.664 | 0.608 | **0.016** |
| trades_ratio | 0.736 | 0.664 | 0.622 | 0.046 |

**Pre-committed thresholds (fixed 2026-09-02, before the run): keep at
Spearman ≥ 0.70 overall and ≥ 0.60 every year; drop below 0.50.**
No feature clears 0.70. The primary sits at 0.572, above the drop floor but
below the keep bar, and the keep list is empty — which the rule as written
resolves to **DROP**.

**What the numbers say, beyond the verdict.**

1. **Distributions transfer; individual bars do not.** KS statistics of
   0.016–0.069 mean a model trained on SIP would not meet out-of-distribution
   inputs on IEX. It would meet a **noisy** version of the same input. That is
   errors-in-variables, not distribution shift. At ρ ≈ 0.65 the reliability
   ratio is ρ² ≈ 0.42, so roughly 58% of the feature's variance at inference
   is noise, and whatever edge it carries is attenuated toward zero.
2. **The time-of-day baseline was the wrong choice and the data says so.**
   `vol_tod` was made primary on the reasoning that intraday volume is
   U-shaped. It is the *worst* transferring feature. Its baseline is a
   per-slot median over 20 sessions, and on a feed carrying ~3% of volume a
   single 5-minute slot is thin, so the baseline itself is noisy. The
   session-wide rolling median pools 78 bars and transfers better. **General
   lesson: the more data a scale-free baseline pools, the better it transfers.**
3. **IEX RTH coverage is far better than assumed.** 99.6% of SIP RTH bars have
   an IEX counterpart across five years, against an earlier reading of 74–87
   bars/day that suggested frequent no-trade intervals. The no-forward-fill
   rule stays (it is still correct for options), but the Data Card should
   record 99.6% rather than implying a gappy feed.
4. **Stable across years.** Worst-year Spearman of 0.51–0.62 with no collapse,
   so this is a structural property of the feeds and not a regime artifact.
5. **The 2-month sanity run agreed** (vol_tod 0.523), so the full-run figure is
   not a fluke of one window.

**Consequence beyond M1/M2, which needs a decision.** If volume features are
dropped, the same logic applies to any **volume-dependent rule inside B2**. A
rule such as "volume above 1.5x the trailing median" has the identical
train/live mismatch. Either volume leaves the strategy rules too, or the
strategy's live behaviour differs in construction from its backtest.

**Three responses, only two of which are available.**

- **(A) Honour the pre-commitment.** Drop volume-derived features from the
  models and the strategy rules. Record the correlation table in the Data Card
  and every Model Card. The risk-register entry closes by removal, and §18's
  negative-result framing covers it. Clean, defensible, and cheap.
- **(B) Pre-specify a *new* experiment** and report both results. Two candidate
  questions, each needing its own threshold fixed before it is run:
  conditional agreement in the top decile of volume, where a breakout filter
  actually fires; and a longer time-of-day lookback (60 sessions rather than
  20) to see whether a better-estimated baseline transfers. Legitimate only if
  the DROP verdict above is reported with equal prominence whatever B finds.
- **(C) Move the threshold.** **Not available.** It is the thing the
  pre-commitment exists to forbid, and doing it once would devalue every other
  pre-commitment in the project.

## ▶️ Where the build starts

**Repo state as of 2026-09-01:** `src/project_beta/config.py`, `src/project_beta/grounding.py`, three test files, one example RunConfig. Scaffold plus the grounding checker. Everything else in the Outline §4 pipeline is unwritten.

**First task: the vendor-agnostic data provider (`Upgrade_Path.md` §2.1), and the SIP/IEX transfer experiment on top of it.** It is on the critical path, is a Week 1–2 deliverable, forces the provider seam into existence when it is cheapest, and produces the project's strongest interview artifact. Nothing should come before it.

## ✅ Data verification — ALL QUESTIONS CLOSED (2026-09-01)

| # | Question | Answer | Closed |
|---|---|---|---|
| Q1 | Equities history depth | SIP 2016-06-10 (10.2y) · IEX 2021-06-10 (5.2y) | 08-30 |
| Q2 | Does the 15-minute delay restriction bite? | **NO — real-time** | **09-01** |
| Q2b | Is IEX streaming entitled and live? | **YES — sub-second** | **09-01** |
| Q3 | IEX share of consolidated volume | 3.16% median (2.79–3.78%) | 08-30 |
| Q4 | Session coverage / gap profile | Good; profile corrected 09-01 | 09-01 |
| Q5 | Crypto continuity | BTC/USD continuous from ≥2021-06-10 | 08-31 |
| Q6 | Options data exists? | Yes, from 2024-06-21 expiries onward | 09-01 |
| Q6b | Options history start | 2024-01-18 (~31 months, 0 folds) | 09-01 |

**Semester data cost: $0. No upgrade required.**

### Q2 / Q2b — the decisive latency result (2026-09-01, 19:24 UTC, market open)

| Endpoint | Lag | Reading |
|---|---|---|
| `latest_trade` | **0.1 min** | Real-time |
| `latest_quote` | **-0.0 min** | Real-time (negative = clock skew) |
| REST `/stocks/bars` | 1.5 and 4.1 min on two runs 3 min apart | **Not a feed delay** — see below |
| **Websocket stream** | **authenticated · subscribed · 5 live trades · last 0.1 s old** | **Definitive** |

**The 15-minute restriction does not apply on IEX. The Milestone 3 live loop works on the free tier.**

**Do not confuse the two readings.** The REST *bars* lag moved 1.5 → 4.1 minutes across three minutes. That is the age of the last *completed* 5-minute bar, cycling between ~0 and ~5 minutes depending on when you ask — not feed jitter. Trade, quote and stream are sub-second. **Design consequence: a bar-driven loop is one bar-interval behind by construction, not because of the data tier.**

**IEX streaming entitlement is now proven**, which it never was. The 08-30 run established that **SIP** streaming returns `409 insufficient subscription`; the M3 live loop runs on the IEX websocket, and it authenticates and delivers.

### Q4 — coverage profile, corrected (2026-09-01)

42 trading days sampled (2026-07-02 → 2026-08-31): 42 days with bars · **40 with ≥78 bars** · 1 below 90% · **0 duplicates** · bars/day min 9, median 82, max 87.

**Correction to the 08-30 record ("41/41 full sessions, zero gaps").** The two non-full days:

- **2026-07-02, 9 bars** — the **first date in the sample window**, with every other day at 74–87. A real outage appears mid-window, not exactly at the edge. **Window-boundary artifact, not a feed gap.**
- **2026-08-31, 74 bars** — mid-window, 94.9% of the RTH maximum. Consistent with a feed carrying ~3% of consolidated volume: some 5-minute intervals contain no IEX trades, so no bar is emitted.

**"Zero gaps" was a property of that window, not of the feed.** The honest statement: no duplicates ever observed; near-complete coverage; occasional no-trade intervals on a thin feed.

**Consequences for §5.1 validation and the Week 4 Data Card:** do not assert exactly 78 bars/day on IEX; flag days below ~90% for review rather than auto-rejecting; **exclude the first and last day of any fetch window from coverage statistics**; a missing bar is a **no-trade interval, not missing data**.

## 📌 Options note — fully answered 2026-09-01

**Q6 — the data exists.** Bars at every monthly expiry from 2024-06-21 forward (611–1,458 bars per contract); 0 bars at the 2023 expiries with no entitlement error. Options is **not** paper-forward-only.

**Q6b — but there are only 31 months of it.** `probe_options_start.py` enumerated real contracts via `status=inactive` across the six 2024 monthlies with an unbounded lookback. **All eighteen contracts across six different expiries clipped their first bar into 2024-01-18/19** — including a June expiry trading for months by January. The evidence is the *shape*, not the minimum: eighteen contracts cannot coincidentally begin trading in the same two days. **`data.start` for options = 2024-01-18**, a hard data floor of the same class as the 2016-06-10 SIP floor.

| Asset class | History | Folds at 30/6/6 |
|---|---|---|
| Equities | 122 months | ~14 |
| Crypto | ~63 months | ~4 |
| **Options** | **31 months** | **0 — not one complete fold** |

**Why this does not remove options from scope.** The signal-quality model scores the *underlying*; contract selection is deterministic and downstream, so options adds no model. Nothing in the ablation is trained on options bars. Options never needed 42 months to train anything — it needs history to validate a deterministic execution mapping, and 31 months of 5-minute bars is ample.

**Supporting argument against a shortened scheme:** the 31 months run 2024-01 → 2026-09, close to a single market regime. A regime classifier trained or tested only there would have almost no regime variety, defeating the purpose of M1. Short history is not just fewer folds; it is fewer *regimes*.

### Corrections these runs forced

1. **"Hand-built OCC symbology required" is retired.** Expired-contract discovery works with `status=inactive` (`HTTP 200`). The original zeros came from omitting that parameter.
2. **"Earliest bar 2024-05-28" was an artifact** of `probe_options_depth.py`'s 25-day query windows.
3. **Extended-hours bars appear in options too** — 1,458 bars against a ~1,377 RTH maximum. The RTH filter is load-bearing there as well.

### Hazards for the design

- **Sparsity is strike-dependent**: 5 to 1,458 bars per contract lifetime. Absent bars are no-trade intervals, never forward-filled.
- **The probes sampled mid-range strikes, not near-the-money** — in January 2024 that meant deep-ITM calls with SPY near 476. Those counts understate ATM liquidity and must not be read as a liquidity measurement. The start-date finding is unaffected.
- **Point-in-time universe correctness** — selecting contracts that turn out to have bars is look-ahead bias. See `Upgrade_Path.md` §2.4.

## 📌 The market-open launchd job — retired (2026-09-01)

`com.projectbeta.marketopen` existed to answer Q2/Q2b and the options questions. All are closed, so the job was booted out and its LaunchAgents plist removed. The plist is kept in-repo as a record only; nothing is bootstrapped.

### The TCC finding is durable and belongs in the M3 architecture

The 06:30 run on 2026-09-01 failed before executing a line:

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: /Users/god/Desktop/Project-Beta/run_market_open.sh: Operation not permitted
```

**`~/Desktop` is a macOS TCC privacy-protected location. A launchd agent has no access and cannot even exec a script that lives there.** Terminal *does* have that access — which is why every manual run worked and the scheduled one did not. **Testing by hand does not test the scheduled path.**

**Resolved 2026-09-01:** the project was moved to `~/dev/Project-Beta`. Not `~/projects/Project-Beta` — macOS filesystems are case-insensitive by default, so that would have collided with the existing `~/projects/project-beta`.

- Granting Full Disk Access to `/bin/bash` is the wrong fix: it hands every script the shell runs unrestricted access to the user's files, to work around a folder choice.
- Any scheduled job must be verified **through launchd** (`launchctl kickstart`), never only by hand.

## 🔑 Credential rotation — 2026-09-01

The Alpaca key pair was **regenerated** (the original secret was unrecoverable — Alpaca displays it once and does not retain it). The new pair is verified working: `HTTP 200` on market data, websocket authenticates.

- `run_market_open.sh` only checked that the variables were *non-empty*, never that they were valid. **A credential check that cannot fail is not a check** — the M3 loop must make one authenticated call and abort on non-200.
- Store the secret in a password manager. There is no second chance to read it.

## ✅ Data architecture — resolved 2026-08-30, extended 2026-08-31 and 2026-09-01

**Alpaca Basic (free) tier, dual-feed. Semester data cost: $0.**

| Measured | Result |
|---|---|
| SIP historical depth, 5-min | **2016-06-10 → now = 10.2 years** |
| IEX historical depth | 2021-06-10 → now = 5.2 years |
| SIP historical entitlement | ✅ Entitled |
| SIP recent data | ❌ **Not entitled** — `403` |
| SIP streaming | ❌ **Not entitled** — `409` |
| **IEX recency** | **Real-time. Trade lag 0.1 min, quote lag ~0** |
| **IEX streaming** | **✅ Entitled — trades ~0.1 s old** |
| IEX share of consolidated volume | **3.16% median** (2.79–3.78%) |
| **Coverage, 42 sessions** | **40/42 full RTH · 0 duplicates · 74–87 bars/day** |
| SIP bars/day | 192 = 04:00–20:00 ET |
| **IEX bars/day** | **74–87, straddling the 78-bar RTH maximum.** Above = extended-hours bars; below = no-trade intervals |
| BTC/USD 5-min depth | 2021-06-10 or earlier → now |
| BTC/USD coverage | 865 bars per 3-day window vs 864 expected for genuine 24/7 |
| **Options 5-min bars — start** | **2024-01-18 = 31 months** |
| Options contract discovery | Works for expired contracts with `status=inactive` — `HTTP 200` |
| Options bar density | 5 to 1,458 bars per contract lifetime, strongly strike-dependent |

| Decision | Resolution |
|---|---|
| Data source and tier | ✅ Alpaca Basic free, dual-feed. **No paid subscription — confirmed by measurement** |
| `data.start` | ✅ **2016-06-10** (equities) · **2024-01-18** (options). Asset-class-specific |
| Walk-forward folds | ✅ **30/6/6 step 6 (42 months/fold), decided 2026-09-02** → **14 folds** equities · 4 crypto · 0 options |
| **M3 live-loop data tier** | ✅ **Free tier suffices** |
| Volume features | ✅ Scale-free only, subject to the transfer experiment |
| Regular vs extended hours | ✅ Regular hours only, filtered at ingestion — necessary on IEX **and** options |

*Corrections logged: (1) "SIP is entitled" from a historical-date query was too broad. (2) The `--assets` probe queried crypto and options under `/v2`; Alpaca versions data APIs per asset class. (3) Options zeros then misread as a discovery limitation. (4) "Earliest bar 2024-05-28" was a query-window artifact. (5) "41/41 sessions, zero gaps" was a property of one window. (6) A 9-bar session initially read as a feed gap is a window-boundary artifact.*

## Upgrade paths — recorded, NOT needed

| Option | Price | Verdict |
|---|---|---|
| **Alpaca Algo Trader Plus** | $99/mo | ❌ **Trigger did not fire.** Its case was collapsing the dual feed if IEX proved delayed. IEX is real-time with an entitled stream |
| **Massive (Polygon) Options Advanced** | $199/mo | ❌ 5+ years → **~3 folds**; crypto already gives 4, free. Data vendor, not a broker — execution stays on Alpaca, adding a second feed mismatch |
| Massive Options Developer / Starter / Basic | $79 / $29 / $0 | ❌ 4 / 2 / 2 years. The lower tiers offer **less** than Alpaca's 31 months |
| Databento | Quote-based | Depth unconfirmed; $125 free credits |

**Trigger for spending:** only if the transfer experiment fails *and* losing volume features materially degrades the SQ model.

## Open — Milestone 1 window (due end of Week 2)

| Item | Status | Notes |
|---|---|---|
| **Repo — six-item checklist** | ✅ Built and committed | 39 tests passing, 1 deliberate skip |
| **Push to GitHub** | ✅ **Fully pushed** | `git@github.com:henrydao312/Project-Beta.git`, **private** |
| **Move off TCC-protected folder** | ✅ **DONE 2026-09-01** | Now at `~/dev/Project-Beta` |
| **History rewrite before the repo goes public** | 🔴 **Before Week 12** | `alpaca_verification_report.json` and `report_offhours.json` are in **two pushed commits**: added at `17b0ca3`, removed at `3215dc9`. Removal does not erase them. Verify after: `git log --all --name-only \| grep -i report` must return nothing |
| **Book the mandatory Faculty 1:1** | 🟡 This week | 5% of the grade; the reviewer who applies the proposal rubric |
| **Confirm M1 due week** | 🟡 | Grid says Week 2; the deck says "week ~3". Confirm on Canvas |
| **Compute-budget LLM figure** | 🟡 | Needs one real cost-per-decision measurement. The data line is confirmed $0 |
| **3 readers for the Week 12 user-impact protocol** | 🟡 Before Wk 12 | Must be unfamiliar with the project |

## Fallback checkpoints

- **Week 6** — if the equity core is running end-to-end (B1→B2→M1→M2, 14 folds, risk engine, execution simulator), graded options may be revisited. If not, options stays a validated execution layer and moves to Phase 2. *(`Upgrade_Path.md` §6)*
- **Week 8** — paper loop not running end-to-end → the secondary-strategy toggle is dropped; Week 8 goes to the alpha.
- **Week 11** — release candidate not containerized and reproducible → the query layer is off the table.

## Later

| Decision | Status | Notes |
|---|---|---|
| Dashboard stack (Streamlit vs. custom) | 🟢 Wk 3 | Must host the halt control, the replay/live indicator, feed provenance, the cross-asset tier labels |
| Signal-quality acceptance threshold | 🟢 After first M2 calibration | |
| Plan B / HMM comparison | 🟢 Wk 10 gate | |
| Query layer go/no-go | 🟢 Wk 10 gate | If built: a second injection surface |
| Final Technical Report due date | 🟡 Confirm on Canvas | |

---

## Resolved

| Decision | Resolved | Notes |
|---|---|---|
| Coding-agent use on system code | ✅ 2026-08-24 | Three consistent sources |
| Milestone timeline alignment | ✅ 2026-08-25 | Alpha = Wk 9; docs/video = Wk 12 |
| Solo vs. group | ✅ 2026-08-28 | Solo |
| Primary strategy | ✅ 2026-08-26 | Momentum breakout |
| Multi-strategy architecture | ✅ 2026-08-26 | One primary with full rigor; secondaries backtest-only |
| Optional Focus Area declaration | ✅ 2026-08-30 | Evaluation & Responsible AI (primary) + Model & System (secondary) |
| Repo license | ✅ 2026-08-30 | MIT |
| User-impact metric protocol | ✅ 2026-08-30 | Outline §10.2 |
| Trading API vs Broker API | ✅ 2026-08-30 | Trading API |
| Decision-log publication constraint | ✅ 2026-08-30 | Bounded sample logs, CI-enforced |
| **Data architecture** | ✅ **2026-08-30** | The project's largest risk, closed at $0 |
| **AI role, interaction style, platform, pattern tier, task inventory** | ✅ **2026-08-30** | Outline §22 |
| **What-if scenarios** | ✅ **2026-08-30 — excluded** | Attacks the grounding claim, not merely scope |
| **Fairness mitigation (step 3)** | ✅ 2026-08-30 | Regime-conditional abstention |
| **News / sentiment gate** | ✅ **2026-08-31 — dropped** | Options replaces it; closes the FinBERT licensing problem by removal |
| **Ablation ladder** | ✅ **2026-08-31** | B1 → B2 → M1 → M2, equities only |
| **M1 repo scaffold** | ✅ **2026-08-31** | Pushed private |
| **Crypto feasibility** | ✅ **2026-08-31** | Continuous from ≥2021-06-10 |
| **Options data existence (Q6)** | ✅ **2026-09-01** | Bars at every expiry from 2024-06-21 on |
| **Options contract discovery** | ✅ **2026-09-01** | `status=inactive` enumerates expired contracts |
| **Options history start (Q6b)** | ✅ **2026-09-01** | 2024-01-18, ~31 months, 0 folds |
| **IEX real-time latency (Q2)** | ✅ **2026-09-01** | Real-time. Trade lag 0.1 min |
| **IEX streaming entitlement (Q2b)** | ✅ **2026-09-01** | Entitled and live — trades ~0.1 s old |
| **M3 data-tier decision** | ✅ **2026-09-01** | Free tier suffices |
| **Session coverage profile (Q4)** | ✅ **2026-09-01** | 40/42 full RTH, 0 duplicates; "zero gaps" corrected |
| **Asset-class tiers** | ✅ **2026-09-01** | **Shape A**: equities graded core · crypto graded secondary (4 folds) · options validated execution layer |
| **Vendor switch for options** | ✅ **2026-09-01 — rejected** | $199/mo buys ~3 folds; crypto gives 4 free |
| **Week 10 red-team target** | ✅ **2026-09-01** | The explanation service |
| **TCC / scheduled-execution constraint** | ✅ **2026-09-01** | Project moved to `~/dev/Project-Beta` |
