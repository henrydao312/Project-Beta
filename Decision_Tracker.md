# PROJECT BETA — Decision Tracker

Live tracking doc for every open/undecided item across `Project_Outline.md`, `PROJECT_BETA_PRD_v1.1.md`, and `Instruction.md`. Update this doc (status + date) whenever a decision lands.

**Status legend:** 🔴 Blocking · 🟡 Needed soon · 🟢 Deferred by design · ✅ Resolved

**Last major update: 2026-08-30** — Week 1 data verification complete. **The project's largest risk is closed** and the data architecture is settled (Outline Rev 9, PRD v1.9). Six decisions resolved; two new items opened.

---

## ✅ Data architecture — RESOLVED 2026-08-30 by direct API verification

**Alpaca Basic (free) tier, dual-feed. Total semester data cost: $0.**

| Measured | Result |
|---|---|
| SIP historical depth, 5-min | **2016-06-10 → now = 10.2 years.** 2015 empty on both feeds, so 2016 is the true floor |
| IEX historical depth | 2021-06-10 → now = 5.2 years |
| SIP recent data | **Not entitled** — `403: subscription does not permit querying recent SIP data` |
| SIP streaming | **Not entitled** — `409 insufficient subscription` |
| IEX share of consolidated volume | **3.16% median** (2.79–3.36% over six sessions) |
| Coverage, 42 sessions | 42/42 full regular sessions, zero gaps, zero duplicate timestamps |
| SIP bars/day | 192 = 04:00–20:00 ET |

**Architecture:** SIP for backtest / walk-forward / the whole graded ablation; IEX for the live paper loop. Every RunConfig, DecisionRecord and results table records which.

**Decisions that fell out of it, all now recorded:**

| Decision | Resolution |
|---|---|
| Data source and tier | ✅ Alpaca Basic free, dual-feed. No paid subscription needed for the graded project |
| `data.start` | ✅ **2016-06-10** |
| Walk-forward folds | ✅ 36-month train / 6 test / 6 step → **~14 folds**. The original ten-year design survives intact |
| Volume features | ✅ **Retained, but scale-free only** — ratios or z-scores against a trailing window, never absolute. Subject to the transfer experiment below |
| Regular vs extended hours | ✅ **Regular hours only**, filtered at the data-pipeline stage so nothing downstream can forget |
| Bar timeframe | ✅ 5-minute confirmed viable (was provisional) |

**A correction logged at the same time:** an earlier bonus probe reported "SIP is entitled" from a query against a historical date. That was too broad — historical and recent SIP are entitled separately. The script has been patched to test both and report them apart.

---

## 🔴 New: the train/live feed mismatch

Now the leading technical risk, created by the architecture above.

| Item | Status | Notes |
|---|---|---|
| **Feed-transfer validation experiment** | 🔴 **Blocking §5.5 — do in Week 1–2** | Backtests train on SIP volume; live runs on IEX volume at ~3% of the magnitude. Scale-free features should transfer, but that is an assumption. **Test:** compute the volume features from both feeds over the overlapping 2021–2026 period, correlate bar-by-bar, compare distributions. **Pre-committed decision:** strong agreement → keep volume features and publish the correlation; weak agreement → **drop volume-derived features entirely** and record that IEX proved unrepresentative. Must conclude before Week 7 signal-quality work begins. Outline §5.2, PRD §5.2 |
| **IEX real-time streaming latency** | 🟡 Monday, market hours | The one outstanding verification. Determines whether the Milestone 3 live loop works as designed. `python verify_alpaca_data.py --feed iex --stream` between 06:30 and 13:00 PT. Mitigations if it fails: lengthen the live bar interval, or upgrade (see below) |

---

## Upgrade paths — recorded, not needed (Outline §9B)

Verified pricing, 2026-08-30. **Nothing here is required for the graded project.**

| Option | Price | Verdict |
|---|---|---|
| **Alpaca Algo Trader Plus** | $99/mo | **The only upgrade worth considering.** Real-time SIP across all US exchanges collapses the dual-feed architecture to one feed, removing the mismatch problem class entirely. Same vendor, same keys, same code path |
| Polygon / Massive Advanced | $199/mo | Real-time consolidated + 20 years. Twice the price, second vendor, stricter licensing (§5(d), single-end-user, delete-on-termination) |
| Polygon / Massive Developer | $79/mo | **Correction to earlier docs: this tier is 15-minute DELAYED, not real-time.** Buys nothing the free Alpaca tier doesn't already give this project. Not recommended |
| Databento | Usage-based | Institutional-grade, metered rather than subscription. Suits bounded research bursts; confirm current rates directly |

**Trigger for spending anything:** only if the transfer experiment fails *and* losing volume features materially degrades the signal-quality model. Then $99/mo buys back a real capability. Otherwise the money is better not spent.

**Going live** (permanently out of scope, §3) would additionally require: real-time data as a hard prerequisite; re-examining Professional vs Non-Professional subscriber status; deliberately removing the paper-only guardrail that a test currently enforces; and an actual track record — walk-forward results are evidence about a hypothesis, not a track record. Outline §9B.

---

## Licensing — verified 2026-08-30 (Outline §20.1)

| Item | Status | Finding |
|---|---|---|
| Alpaca data redistribution | ✅ **Prohibited** | Terms & Conditions *and* Customer Agreement §30, independently. Sample-fixture + re-fetch-script + hash design is required |
| Agreement beyond the public T&C | ✅ **Yes — the Customer Agreement**, read and audited. It incorporates the NASDAQ/NYSE subscriber agreements by reference *"if provided access to such data"* |
| Publishing decision logs | ✅ Resolved into design | NASDAQ §12 reaches data from which the original *"can be identified, recalculated or re-engineered."* DecisionRecords carry prices → **committed sample logs bounded to a few trading days, CI-enforced** |
| Professional vs Non-Professional status | 🟡 Confirm in-account | Default is Professional unless actively qualified. Check Account → Documents. Matters again in any live scenario |
| LLM output rights | ✅ Resolved | Outputs assigned to the user under both consumer and commercial terms; commercial adds *"Anthropic may not train models on Customer Content"* |
| Which Anthropic terms apply | ✅ Resolved — **both** | Desktop app (consumer) covers development assistance; the API (commercial) covers the explanation service. Two agreements, two uses, both favourable |
| LLM usage policy — finance | ✅ Resolved, **favourable** | Finance is a High-Risk Use Case, but the project is compliant by design: the LLM narrates decisions the deterministic engine already made, no external consumers, disclaimer present. **Use this in the M1 charter** |
| FinBERT license | 🔴 Week 2 gate | **No license declared on the HF model card.** Upstream repo is Apache-2.0 but covers code, not weights. Recommend switching to an explicitly-licensed model given the repo is a public portfolio piece |
| Polygon §5(d) | 🟢 Moot | Not subscribed, and §9 resolved without it |

---

## Open — Milestone 1 window (due end of Week 2)

| Item | Status | Notes |
|---|---|---|
| **Confirm M1 due week — Week 2 or Week 3** | 🟡 | Syllabus grid says end of Week 2 with the Faculty 1:1; the Phase 1 deck says "week ~3." Plan to Week 2, confirm on Canvas |
| **Book the mandatory Faculty 1:1** | 🟡 This week | Part of the 5% appointments grade; this is the reviewer who applies the proposal rubric |
| **News feasibility gate verdict** | 🟡 | GO / CONDITIONAL / NO-GO. Also carries the sentiment-model licensing call, and sets the Week 10 red-team target |
| **Compute-budget LLM figure** | 🟡 Before M1 | Needs one real cost-per-decision measurement. The data line is now confirmed $0 |
| **Pitch artifact** | ✅ Built 2026-08-30 | `PROJECT_BETA_Product_Demo.pptx` (6 slides, speaker notes) + `Product_Demo.md` (presenting script). Format decision: deck, per Outline §19.4 |
| **Line up 3 readers for the Week 12 user-impact protocol** | 🟡 Before Wk 12 | Must be unfamiliar with the project |

### Artifacts on the timeline

| Artifact | Due | Specified in |
|---|---|---|
| Six-item repo checklist | Wk 1–2 | `Instruction.md` |
| **Feed-transfer validation experiment** | Wk 1–2 | Outline §5.2, PRD §5.2 |
| Responsible AI charter | Wk 2 | Outline §20 |
| Publication-constraint CI check on log size | Wk 1–2 | Outline §20.5, PRD §5.10 |
| Data Card (both feeds, the 3.16% finding) | Wk 4 | PRD §5.1 |
| Model Cards + System Card | Wk 9 | PRD §5.15 |
| Red-team pass | Wk 10 | Outline §20.2 |
| Container + latency & cost report | Wk 12 | PRD §5.15 |

---

## ✅ Professor-approved fallback levers (2026-08-28)

| Lever | Status | Notes |
|---|---|---|
| VPN use | ✅ Approved | Includes commercial VPNs |
| Real-money trading | ✅ Approved, with caveat | "I recommend simulated funds... not opposed as long as you recognize the risks." **Not a plan change** — paper-only is enforced in code and tested, so this would need a deliberate design change plus its own risk entry. See Outline §9B for what going live would actually require |
| Implementation language | ✅ Approved | Build assumes Python |

## Team-up / Polymarket fork — CLOSED (2026-08-28)

Teammate backed out; solo confirmed. Findings preserved: Polymarket has no paper-trading mode and no historical backtesting API — the walk-forward/ablation methodology doesn't map onto that data shape; the original venue is geoblocked for US IPs; the only legal US venue requires KYC and real funding. Sources: [Is Polymarket Legal in the USA?](https://tech-insider.org/prediction-markets/is-polymarket-legal-in-the-usa/), [Polymarket API Developer Guide — Rekko](https://rekko.ai/docs/guides/polymarket-api-guide)

## Later

| Decision | Status | Notes |
|---|---|---|
| Dashboard stack (Streamlit vs. custom) | 🟢 Wk 3 | Must host a persistent disclaimer, display feed provenance, and support the §10.2 protocol |
| Signal-quality acceptance threshold | 🟢 After first M2 calibration | |
| Plan B / HMM comparison | 🟢 Wk 10 gate | Also gated by the Week 11 fallback checkpoint |
| Interactive query layer | 🟢 Wk 10 gate | If built, introduces the first new data class (user queries) — Outline §20.4 needs a retention line first |
| Final Technical Report due date | 🟡 Confirm on Canvas | Not in the syllabus's weekly grid |
| Written-deliverable AI policy | 🟢 Deferred | Only if the project leans on AI-drafted prose |

---

## Resolved

| Decision | Resolved | Notes |
|---|---|---|
| Coding-agent use on system code | ✅ 2026-08-24 | Three consistent sources |
| Milestone timeline alignment | ✅ 2026-08-25 | Alpha = Wk 9; docs/video = Wk 12 |
| Solo vs. group | ✅ 2026-08-28 | Solo |
| Primary strategy | ✅ 2026-08-26 | Momentum breakout |
| Multi-strategy architecture | ✅ 2026-08-26 | One primary with full rigor; secondaries backtest-only |
| Product One-Pager & Demo Walkthrough | ✅ 2026-08-26 | Outline §1A, §19 |
| VPN / real-money / language levers | ✅ 2026-08-28 | |
| Optional Focus Area declaration | ✅ 2026-08-30 | Evaluation & Responsible AI (primary) + Model & System (secondary) |
| Repo license | ✅ 2026-08-30 | MIT |
| User-impact metric protocol | ✅ 2026-08-30 | Outline §10.2 |
| Named fallback checkpoints | ✅ 2026-08-30 | Wks 6, 8, 11 |
| Trading API vs Broker API | ✅ 2026-08-30 | Trading API |
| Decision-log publication constraint | ✅ 2026-08-30 | Bounded sample logs, CI-enforced |
| **Data architecture (source, tier, feeds, start date, folds, session, volume features)** | ✅ **2026-08-30** | See the top section. The project's largest risk, closed at $0 |
| Pitch artifact | ✅ 2026-08-30 | Deck + presenting script built |