# Jacky — Contribution Plan

**2026-09-03.** Written to be handed to Jacky, so most of it is addressed to
them directly. One gate remains, in §0.

---

## 0. Status of the gates

**1. Faculty approval — CLEARED 2026-09-03.** A two-person group is approved,
and **expectations do not scale with team size.** That second clause is the
important one: Jacky is genuine slack rather than a raised bar. The slack is
spent on depth and on the workstreams that previously had no owner, **not on new
scope.** The Scope Tiers table and the named fallback checkpoints are unchanged.
All documents have been updated from solo.

**2. History rewrite — STILL OPEN. Do this before granting repo access.**
`alpaca_verification_report.json` and `report_offhours.json` are still reachable
at commits `17b0ca3` and `3215dc9`. Adding a collaborator before the rewrite
hands them licensed vendor data that the project has already had one incident
over. Verify with `git log --all --name-only | grep -i report` returning
nothing.

---

## 1. The project in five minutes (read this before anything else)

PROJECT BETA is an AI-assisted **paper-trading** system for SPY. A transparent,
readable rule proposes trades. Two machine-learning models decide whether to
trust the rule right now. A deterministic risk engine can veto or halt
everything. Every decision is logged, and a language model writes a plain-English
explanation **grounded only in that log**.

Four things define how the project works, and they are not negotiable:

1. **AI gates, it never decides.** No model output reaches the trade decision as
   an instruction. The trade decision and the instrument choice are both
   deterministic.
2. **Every claim is sized to its data.** Equities is the graded core with 14
   walk-forward folds. Crypto is a graded secondary with 4, and that number is
   printed beside every crypto figure. Options makes no performance claim at
   all, because 31 months of history yields zero folds.
3. **A negative result is a legitimate outcome.** The project is judged on
   evaluation quality and honest failure analysis, not on returns.
4. **Pre-commitments are honoured.** Thresholds are fixed before experiments run.
   This already bound once, against the project's own preference: the feed
   transfer test failed and an entire feature class was dropped.

**Read in this order, and stop there:** `README.md`, then `Project_Outline.md`
§1 to §10, then `EVALUATION_PROTOCOL.md`. Skip the rest until you need it. The
Decision Tracker is a reference, not a reading assignment.

---

## 2. Four candidate workstreams

Pick one after the conversation in §6. Each is designed to be **separable**: a
fixed interface, its own tests, and no merge contention with the critical path.

### A. Dashboard and replay mode — recommended default

**What.** The browser UI a user watches and audits: current regime, open
positions, equity curve against baseline, a decision feed with grounded
explanations, halt status and the kill switch, the cross-asset panel, and a
deterministic replay mode.

**Why it matters more than it looks.** The Final Presentation is **25% of the
grade** and is a live demo. On 5-minute bars a demo slot can contain zero
trades, which is why replay exists. The §10.2 user-impact metric is measured
entirely on this screen: three readers unfamiliar with the project must state
the current regime, the open positions, and why the last decision came out as it
did, unaided, in five minutes. **This workstream currently has no owner and
appears nowhere in the §12 timeline.**

**Interface contract.** Reads a `DecisionRecord` JSONL log and a results table.
Nothing else. It must never import from `project_beta.models`,
`project_beta.strategy` or the harness.

**Henry supplies:** the DecisionRecord schema and a sample fixture log, by end of
Week 4.

**Weeks 5 to 12.** Build against the fixture from Week 5, before any live data
exists.

**Done when:** replaying a run twice produces byte-identical displayed sequences;
live and replay are unmistakably labelled and CI-asserted; the disclaimer string
is CI-asserted; each cross-asset panel states its tier; three unfamiliar readers
hit 8 of 9 on the comprehension protocol.

**Fits:** frontend, UX, data visualisation, anyone who cares whether a stranger
can understand a screen.

### B. Crypto secondary track

**What.** Run the whole pipeline on BTC/USD: 5-minute bars, continuous session,
about 63 months of history, 4 walk-forward folds.

**Why.** It is a graded deliverable that tests whether the approach generalises
beyond one equity instrument, it currently has no owner, and it lands in Weeks
9-10, which is already the most overloaded stretch in the plan.

**Interface contract.** Configs plus a crypto-specific validation module. **Do
not modify the harness.** If the harness cannot express something crypto needs,
that is a conversation, not a patch.

**Henry supplies:** the harness and its results schema by end of Week 5, plus
`configs/example_crypto.yaml`, which already validates.

**Weeks 6 to 10.**

**Done when:** the same ablation runs on crypto; every reported figure carries
`asset_class` and `n_folds`; the 4-fold limitation is stated in the results
rather than in prose around them.

**Fits:** data or ML background, comfortable with pandas and scikit-learn.

### C. Red team and grounding audit

**What.** Attack the explanation service. Try to make it assert something that is
not in the decision record it was given. Then run the formal audit: 50 or more
random explanations, every factual claim traced to a field in its source record.

**Why an outsider is better at this.** The author is structurally the worst
auditor of their own system, and a single hallucinated claim is a **release
blocker**. The rules are already written in Outline §20.2, so the handover cost
is nearly zero.

**Interface contract.** You may add tests anywhere. **You may not change
non-test code.** Findings become issues with a failing test attached.

**Weeks 10 to 11.**

**Done when:** 100% of the audited sample traces to a source field, or the
failures are documented and fixed; the adversarial cases are merged as
regression tests.

**Fits:** a careful skeptic. Less code than the others, more judgement.

### D. Options execution layer

**What.** Given an approved trade on SPY, deterministically pick a single-leg
contract and report whether it was actually tradeable. Contract discovery,
selection rule, liquidity screen with a genuine fit/validate/test split, and a
fill-feasibility study with confidence intervals.

**Why.** Without an owner this is the first thing cut at the Week 6 gate.

**The two traps, stated up front.** Selecting a contract *because it turns out to
have bars* is look-ahead bias, and it is the most likely correctness bug in this
project. A missing options bar is an interval in which the contract did not
trade, never a forward-filled price. Both are already guarded in code
(`universe_as_of(t)`, `fill_model: sparse_bar`). Do not route around them.

**Interface contract.** Build against the existing `MarketDataProvider`. Do not
touch the equity path.

**Weeks 7 to 10.** Detail in `Options_Plan.md` Part II.

**Done when:** fill feasibility is reported with intervals by moneyness and
regime; the selection rule is deterministic and tested; **no options result row
carries a Sharpe or drawdown field.**

**Fits:** someone strong who wants the hardest piece, and who will take the two
traps seriously.

---

## 3. What Jacky should not take

The walk-forward harness, the regime classifier, and the signal-quality model.
These are the critical path in Weeks 3 to 8, they require the whole mental model,
and merge contention there costs more than the help returns.

---

## 4. Week one

| Day | Task |
|---|---|
| 1 | Read §1's three documents. Nothing else |
| 2 | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`, then `python -m pytest -q`. Expect 82 passing, 1 skipped |
| 3 | Run `python -m project_beta.config configs/example_backtest.yaml`, then the crypto and options configs. Read `src/project_beta/config.py` and work out why the options config is rejected when a `walk_forward` block is added |
| 4-5 | First pull request. Something small and real in the chosen workstream. The goal is to exercise the review loop, not to ship value |

If anything in the docs contradicts the code, **the code is right and the doc is
a bug**. Report it.

---

## 5. Working agreements

- **Branch and pull request. Never commit to `main`.**
- **Henry reviews everything and owns what ships**, its correctness, its safety
  and its claims. That is the course's standard and it does not change because
  someone else wrote the code.
- **Nothing merges without a test that would fail if the behaviour were wrong.**
  A test that passes against a broken implementation is not a test.
- **Never disable a test to make CI green.** Fix what it caught.
- **Log AI usage with provenance.** Which parts were AI-assisted, per component.
  Coding agents are explicitly allowed; undocumented use is not.
- **Decisions go in `Decision_Tracker.md`**, not in chat. A decision nobody can
  find later was not made.
- **Publication constraints apply to everyone.** No market data, no verification
  reports, no full decision logs in the repo. If someone could rebuild a usable
  price series from it, it does not go in. CI enforces this and will fail your PR.
- **Credentials live in `.env`, never in git.** Alpaca shows the API secret once
  and does not retain it.

---

## 6. First conversation with Jacky

Five questions, in this order. The answer to the first two picks the workstream:

1. What do you actually enjoy building? Interfaces, models, breaking things, or
   infrastructure?
2. Realistically, how many hours a week, and for how many weeks?
3. How comfortable are you with Python, pandas, git branches and pull requests?
4. What do you want out of this? A portfolio piece, a grade, or learning quant
   finance? The three point at different slices.
5. Are you fine with the pre-commitment discipline, meaning thresholds fixed
   before results are seen and honoured afterwards even when inconvenient?

Question 5 matters more than it sounds. It is the project's central habit, and
someone who finds it precious rather than necessary will be unhappy here.

---

## 7. What changes the day Jacky joins

Documents were updated from solo on 2026-09-03: Outline (§13 now carries an
ownership table), Instruction, README, PRD, Product_Demo, Decision Tracker, the
M1 draft, and the pitch deck.

- **Jacky cannot be one of the three §10.2 readers.** They must be unfamiliar
  with the project. Recruit a fourth person.
- **A real review gate has to exist.** `CONTRIBUTING.md` is written but unused;
  from now it is the process.
- **Budget one to two weeks of onboarding** before Jacky is productive. At Week 2
  that is affordable. It would not be at Week 8.
