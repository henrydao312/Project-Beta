# PROJECT BETA — Product Demo

**Trading signals you can actually audit**

An AI-assisted paper-trading system that filters a transparent, rule-based strategy — and gives a plain-English, checkable reason for every trade it takes or refuses.

> Henry Dao · AI Capstone (CIS 5980), Fall 2026 · Solo project
> **Paper trading only. Not investment advice. No real money at any point.**

*Companion to `PROJECT_BETA_Product_Demo.pptx` — same six beats, in speaking order. Present from either.*

---

## If you only have 60 seconds

Most "AI trading bots" let a language model pick the trades, then show you one flattering backtest. PROJECT BETA does the opposite. The strategy is a fixed rule a person can read. The AI's only job is to judge *when not to trust that rule* — and then to explain, in plain English, exactly why each trade was taken, shrunk, delayed, or refused. Every explanation is generated from a logged record, so any claim it makes can be checked against what the system actually believed at the time.

The interesting claim isn't "it beats the market." It's that you can tell precisely what it did and why — and that if the AI turns out not to help, that's a real finding, reported rather than buried.

---

## 1. Opening

**On screen:** title, tagline, one-line description.

**Say:**

> This is a trading system, but the interesting part isn't the trading. It's that every decision it makes can be audited afterwards.
>
> It runs on a paper account — real market data, real market conditions, zero financial risk. Nothing here touches real money, by design and by construction.

Set expectations early: this is a 14-week capstone, currently in week 1. What you're presenting is the design and the evidence plan, not results.

---

## 2. The problem

**On screen:** the problem statement, three pain cards, who it's for.

**Say:**

> People act on trading signals they can't fully trust. And when a trade goes wrong, there's usually no way to reconstruct why it was taken in the first place.
>
> Three specific problems. First, **noisy signals** — a rule that works on average still fires in conditions where it reliably loses money. Second, **no audit trail** — after a bad trade, nothing recorded what the system believed at the time, so you can't learn from it. Third, **black-box tools** — the products that do use AI won't tell you what drove the call.

**The one to land:** the second. This project isn't claiming the AI is smarter. It's claiming you can check what it did afterwards. That's the gap.

**Who it's for:** discretionary retail traders and junior quantitative researchers who want systematic, explainable filtering — not another black box.

---

## 3. How it works

**On screen:** five-stage pipeline. Only the middle stage is amber.

**Say:**

> Every trade passes through five stages, and only one of them is AI.
>
> **Market data** — SPY price bars, validated for gaps and bad timestamps.
> **The strategy** — a fixed, readable breakout rule. Not AI. Deliberately simple enough that you can state it in a sentence.
> **The AI filters** — this is the only AI in the trading path. Two models: one classifies what kind of market we're in — trending, falling, choppy, calm or volatile. The other scores how likely this particular signal is to work out.
> **The risk engine** — hard limits on position size and loss. No machine learning in here, ever. It can override everything upstream.
> **Paper trade** — placed on the paper account, logged, explained.

**Then the key line, slowly:**

> The AI never decides a trade. It describes the market and scores the signal. A fixed rule turns those into one of four outcomes — approve, reduce, delay, reject. And the risk engine can override all of it.

**On the explanation:** point at the example.

> "Approved — uptrend, 72%. Signal quality 0.64. No risk limits active."
>
> That sentence is generated from the stored record, and every number in it can be checked against what the system actually logged. It's not the model narrating its impressions after the fact.

---

## 4. What makes it different

**On screen:** two columns — the usual AI trading bot vs. PROJECT BETA.

| The usual AI trading bot | PROJECT BETA |
|---|---|
| A language model picks the trades | AI only filters a rule you can read |
| One flattering backtest | Each AI piece measured separately, on unseen data |
| Explanations invented after the fact | Every explanation traced to a logged record |
| Failures quietly omitted | Failure analysis is a required deliverable |

**Say:**

> The claim is not "this beats the market." It's that you can tell exactly what it did and why — and that a negative result would still be a real finding.

Saying this out loud, before anyone asks, tends to earn credibility rather than lose it. It also happens to be the honest position: the system is judged on whether the evaluation is trustworthy, not on returns.

---

## 5. How we'll know it worked

**On screen:** two metric cards on the left, the four-layer progression on the right.

**Say:**

> Measured two ways, because one isn't enough.
>
> **Does it trade better?** Risk-adjusted return and worst-case loss, compared against the identical strategy with no AI — after realistic trading costs, not in a frictionless simulation.
>
> **Can a person follow it?** Someone who has never seen the system reads the screen and correctly says why the last trade happened. Timed and scored, with three readers. That's a real measurement, not a claim about usability.

**On the bars — say this explicitly:**

> These bars aren't results. They're the experiment design. Each AI piece gets switched on one at a time — buy and hold, then the rule alone, then add the market-condition model, then add the signal-quality model — so each layer's contribution is isolated rather than assumed. And every comparison happens on time periods the models never trained on.

If someone reads the bars as performance, correct it immediately. Nothing has been measured yet.

---

## 6. Scope, risk, and where it stands

**On screen:** three columns.

**What ships for certain**

- Data pipeline and evaluation harness
- One strategy, fully tested
- Two AI filters, measured separately
- Live paper trading and a dashboard
- Explanations and failure analysis

**The one real risk**

Getting several years of fine-grained price history at usable quality. A paid fallback is already priced and approved — and if neither source works, the system moves to slower bars. The method survives either way; only the number of trades changes.

**Where it stands**

- Week 1 of 14
- Scope, evaluation plan and safety review written
- Repository and data verification in progress
- First working prototype due week 5

**Close on:**

> Paper trading only. Not investment advice. No real money is at risk at any point.

That's a design constraint, not legal boilerplate — there is no live-money code path in the system, and a test enforces it.

---

## Questions people actually ask

**"Does it make money?"**
Unknown, and that's the honest answer in week 1. The system is built so that the answer will be *credible* either way. If the AI filters don't improve on the plain rule, that gets reported with an analysis of where and why they failed — which is a legitimate result, not a failure to hide.

**"Why not just let the AI trade?"**
Three reasons. It would be impossible to audit — you couldn't reconstruct why any given trade happened. It would be difficult to evaluate honestly, because you couldn't isolate what the AI contributed. And a language model is the wrong tool for the job: the classification work here is tabular pattern-matching, where conventional machine learning is faster, cheaper and better calibrated. The AI is used only where natural language is genuinely the output.

**"Is this real money?"**
No. A paper account — real market data and real market conditions, simulated funds. Running it with real money would require a deliberate change to the code, not flipping a setting.

**"What's the AI actually doing, concretely?"**
Two small models score each candidate trade: what kind of market is this, and how likely is this particular signal to work. A third use — a language model — reads the stored decision record afterwards and writes the explanation. That last one has no access to market data or the models; it can only describe what was logged, which is what keeps the explanations honest.

**"Couldn't the explanation just make things up?"**
That's the failure mode that would make an "explainable" system worse than an opaque one, so it's tested directly. A sample of at least fifty explanations is audited, claim by claim, against the source records. Anything the model asserts that isn't in the record is treated as a release blocker.

**"What happens if you run out of time?"**
The scope is tiered, and the cuts are already decided rather than left to panic in week 10. The core — pipeline, one strategy, two AI filters, evaluation, paper trading, dashboard, explanations, failure analysis — is committed. The optional news-analysis layer has named checkpoints where it gets dropped if the core isn't on schedule.

---

## One-paragraph version, for writing

PROJECT BETA is an AI-assisted paper-trading system for a single ETF. A transparent, rule-based strategy generates candidate trades; two machine-learning models then judge the market conditions and the quality of each signal, and a deterministic risk engine enforces hard limits. Every decision — approved, reduced, delayed or rejected — is written to an append-only log, and a language model turns each logged record into a plain-English explanation that can be checked field by field against what the system actually stored. The contribution of each AI component is isolated by switching them on one at a time and comparing against the unfiltered strategy on unseen data, after realistic trading costs. The project's claim is auditability and honest evaluation rather than superior returns; a rigorously characterised negative result is an accepted outcome.
