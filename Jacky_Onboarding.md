# Onboarding and Contribution Areas - Jacky

Written for Jacky. Covers what the project is, which areas need work, and how we
work together.

---

## 1. The project in five minutes

PROJECT BETA is an AI-assisted paper-trading system for SPY. A transparent,
readable rule proposes trades. Two machine-learning models decide whether to
trust that rule under current conditions. A deterministic risk engine can veto
or halt everything. Every decision is logged, and a language model writes a
plain-English explanation grounded only in that log.

Four properties define how it works:

1. **AI gates, it never decides.** No model output reaches the trade decision as
   an instruction. The trade decision and the instrument choice are both
   deterministic.
2. **Every claim is sized to its data.** Equities is the graded core with 14
   walk-forward folds. Crypto is a graded secondary with 4, and that count is
   printed beside every crypto figure. Options makes no performance claim,
   because 31 months of history yields zero folds.
3. **A negative result is a legitimate outcome.** The project is judged on
   evaluation quality and honest failure analysis, not on returns.
4. **Thresholds are fixed before experiments run and honoured afterwards.** This
   has already bound once: the feed-transfer test failed on 2026-09-02 and
   volume-derived features were dropped as a result.

**Read in this order and stop there:** `README.md`, then `Project_Outline.md`
§1 to §10, then `DECISIONS.md`, then `EVALUATION_PROTOCOL.md`. The Decision Tracker is a reference,
not a reading assignment. `AI_Models.md` covers what is built versus bought.

---

## 2. Four areas that need work

Each is designed to be separable: a fixed interface, its own tests, and no
overlap with the critical path in Weeks 3 to 8.

### A. Dashboard and replay mode

**What.** The browser interface: current regime, open positions, equity curve
against baseline, a decision feed with explanations, halt status and kill
switch, the cross-asset panel, and a deterministic replay mode.

**Why it matters.** The Final Presentation is 25% of the grade and is a live
demo. On 5-minute bars a demo slot can contain zero trades, which is why replay
exists. The user-impact metric in Outline §10.2 is measured entirely on this
screen: three readers unfamiliar with the project must state the current regime,
the open positions, and the reason for the most recent decision, unaided, in
five minutes. This area currently has no owner and does not appear in the §12
timeline.

**Interface.** Reads a DecisionRecord JSONL log and a results table. It must not
import from `project_beta.models`, `project_beta.strategy`, or the harness.

**Supplied:** DecisionRecord schema and a sample fixture log, end of Week 4.

**Weeks 5 to 12.** Work can start against the fixture before live data exists.

**Done when:** replaying a run twice produces byte-identical displayed
sequences; live and replay are unmistakably labelled and CI-asserted; the
disclaimer string is CI-asserted; each cross-asset panel states its tier; three
unfamiliar readers score 8 of 9 on the comprehension protocol.

**Suits:** frontend, UX, data visualisation.

### B. Crypto secondary track

**What.** Run the pipeline on BTC/USD: 5-minute bars, continuous session,
approximately 63 months of history, 4 walk-forward folds.

**Why.** It tests whether the approach generalises beyond one equity instrument.
It has no owner and currently lands in Weeks 9 to 10, which is the most loaded
part of the schedule.

**Interface.** Configs plus a crypto-specific validation module. Do not modify
the harness. If the harness cannot express something crypto needs, raise it
rather than patching around it.

**Supplied:** harness and results schema by end of Week 5.
`configs/example_crypto.yaml` already validates.

**Weeks 6 to 10.**

**Done when:** the same ablation runs on crypto; every reported figure carries
`asset_class` and `n_folds`; the 4-fold limitation appears in the results data
rather than only in surrounding text.

**Suits:** data or ML background, pandas and scikit-learn.

### C. Red team and grounding audit

**What.** Attempt to make the explanation service assert something not present
in the decision record it was given. Then run the formal audit: 50 or more
random explanations, every factual claim traced to a field in its source record.

**Why an outsider is better at it.** The author of a system is a poor auditor of
it, and a single hallucinated claim is a release blocker. The rules are already
written in Outline §20.2.

**Interface.** Tests may be added anywhere. Non-test code is not modified.
Findings become issues with a failing test attached.

**Weeks 10 to 11.**

**Done when:** 100% of the audited sample traces to a source field, or failures
are documented and fixed; adversarial cases are merged as regression tests.

**Suits:** careful, adversarial reading. Less code than the others.

### D. Options execution layer

**What.** Given an approved trade on SPY, deterministically select a single-leg
contract and report whether it was tradeable. Contract discovery, selection
rule, liquidity screen with a fit/validate/test split, and a fill-feasibility
study with confidence intervals.

**Why.** Without an owner this is first to be cut at the Week 6 gate.

**Two traps.** Selecting a contract because it turns out to have bars is
look-ahead bias, and it is the most likely correctness bug in this project. A
missing options bar is an interval in which the contract did not trade, never a
forward-filled price. Both are guarded in code (`universe_as_of(t)`,
`fill_model: sparse_bar`). Do not route around them.

**Interface.** Build against the existing `MarketDataProvider`. Do not modify
the equity path.

**Weeks 7 to 10.** The full contract-selection specification and liquidity-screen
design are provided when this area is assigned.

**Done when:** fill feasibility is reported with intervals by moneyness and
regime; the selection rule is deterministic and tested; no options result row
carries a Sharpe or drawdown field.

**Suits:** someone who wants the hardest piece and will respect the two traps.

---

## 3. Areas that stay with Henry

The walk-forward harness, the regime classifier, and the signal-quality model.
These are the critical path in Weeks 3 to 8 and require full context, so
splitting them would cost more than it returns.

---

## 4. Week one

| Day | Task |
|---|---|
| 1 | Read the three documents in §1 |
| 2 | `python3 -m venv .venv`, `source .venv/bin/activate`, `pip install -e ".[dev]"`, then `git config core.hooksPath .githooks` and `python -m pytest -q`. Expect 136 passing, 1 skipped. The hook blocks direct pushes to `main` and runs the suite before every push |
| 3 | Run `python -m project_beta.config` against each file in `configs/`. Read `src/project_beta/config.py` and work out why an options config is rejected when a `walk_forward` block is added |
| 4-5 | First pull request, something small and real in the chosen area. The goal is to exercise the review loop |

If a document contradicts the code, the code is correct and the document is a
bug. Report it.

---

## 5. Working agreements

- Branch and pull request. No direct commits to `main`.
- Henry reviews all changes and is accountable for what ships, its correctness,
  its safety and its claims. This is the course standard and does not change
  based on who wrote the code.
- Nothing merges without a test that would fail if the behaviour were wrong.
- Never disable a test to make CI pass. Fix what it caught.
- Record AI usage with provenance: which components were AI-assisted. Coding
  agents are permitted course-wide; undocumented use is not.
- **Read `DECISIONS.md` before writing code.** It lists the rules already settled
  and why. Most are enforced by a test or a config check. If one looks wrong,
  raise it; do not work around it.
- New decisions are recorded, not left in chat. Anything that changes behaviour
  goes in the pull-request description and, where it affects others, a GitHub
  issue. Henry maintains the full decision log.
- Publication constraints apply to everyone. No market data, no verification
  reports, no full decision logs in the repository. If a usable price series
  could be rebuilt from it, it does not go in. CI enforces this.
- Credentials live in `.env` and are never committed. Alpaca displays the API
  secret once and does not retain it.

---

## 6. Two practical notes

The three readers for the §10.2 comprehension protocol must be unfamiliar with
the project, so Jacky is not eligible. A separate group of three is needed
before Week 8.

Faculty confirmed on 2026-09-03 that scope expectations do not scale with team
size. The second contributor is capacity for depth and for areas that had no
owner, not a reason to add scope. The Scope Tiers table in Outline §3 and the
fallback checkpoints at Weeks 6, 8 and 11 are unchanged.
