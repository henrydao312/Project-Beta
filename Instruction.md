# AI Capstone (CIS 5980, Fall 2026) — Project Instructions & Requirements

## Purpose
This file distills the **official Fall 2026 syllabus** (Dr. Chris Callison-Burch, Penn Engineering Online MSE-AI) plus this project's own plan. All project work in this workspace should align with these requirements. This is a **solo** capstone — a team-up with a classmate was briefly under discussion (2026-08-26) but the teammate backed out (2026-08-28); see `Decision_Tracker.md` for the closed fork and its findings.

**Track:** AI Engineering Track (not Research Track).
**Course dates:** Monday 8/24/2026 – Sunday 12/6/2026 (14 weeks). No classes 9/7 (Labor Day) or 11/23–11/29 (Thanksgiving).

**Updated 2026-08-30** against the Phase 1 lecture deck (`CIS5980_Phase1.pdf`, 85 slides) and the Canvas page *Course Flow and Project Overview*. Those materials made the Milestone 1 deliverable spec explicit for the first time — see the two new sections below ("Milestone 1 — Official Deliverable Spec" and "Optional Focus Areas") — and named artifacts at M3/M4 that the original plan did not produce. All resulting changes are reflected in `Project_Outline.md` (Revision 8) and `PROJECT_BETA_PRD_v1.1.md` (v1.6).

---

## Generative AI Usage Policy — CONFIRMED (two independent sources)

Henry emailed Dr. Callison-Burch about the apparent conflict between the syllabus's "unacceptable uses" language ("avoid using AI for generating code ... for assignments") and a course that mandates a paid AI subscription and centers on building an AI-integrated application.

**Source 1 — Professor's email reply (2026-08-24):** that line is a mistake in the syllabus; coding agents are explicitly allowed in this course, and he will correct the syllabus text.

**Source 2 — the course's own Introduction Video, slide "Working with AI Tools" (independently confirms the same thing, so this isn't just one offhand reply):**
> **Encouraged.** Use Claude Code, Cursor, Copilot, ChatGPT — whatever helps.
> **Document what you do.** AI-assisted code in your repo is fine; just be clear about provenance.
> **You are responsible** for what you ship — its correctness, its safety, its claims.
> The capstone is a chance to learn *how to work with AI tools well*, not to avoid them.

**Source 3 — Phase 1 lecture, "Software Engineering in the Era of AI: Repo Hygiene & CI" (2026-08-30 review):** reinforces the same position and adds the standard the work is held to — *"use them like an engineer, not like a tourist"*; **vibecoding** (prompt, accept, ship without reading or testing) is called out as the failure mode; the durable skills named are **specification, verification, reading code you did not write, and judgment**. The lecture's practical stress test is worth adopting directly: **"can you regenerate the project from your spec and tests?"** — if not, the behavior lives only in code that was never pinned down. For PROJECT BETA that is an argument for keeping `PROJECT_BETA_PRD_v1.1.md` (module contracts, data schemas, acceptance criteria) genuinely current, since it *is* that spec.

**Confirmed policy for this project:**
- **Coding agents (Claude, Claude Code, Copilot, etc.) are allowed and actively encouraged for all system code** — the trading bot's pipeline, models, risk engine, dashboard, tests, and everything else that makes up the deliverable itself. No restriction here.
- **Document provenance, not just "usage."** It's not enough to log that AI was used somewhere — the repo/AI-usage log should make clear *which parts* were AI-assisted (commit messages, comments, or a provenance note per major component), per the video's explicit instruction.
- **Henry owns what ships, regardless of who/what wrote it.** Correctness (does it work, is it tested), safety (no reckless risk-engine bypasses, no leakage), and claims (results tables, explanations, the final report) all need to hold up to Henry's own scrutiny before they're submitted — AI assistance doesn't transfer that responsibility.
- **Written graded deliverables** (milestone proposal text, weekly journals, decision/experiment logs, final technical report prose, reflections): neither source above specifically addressed AI-drafted *prose* (both were framed around code), so the previous conservative default still applies here — Claude helps with thinking, structuring, research, and critique, Henry writes the submitted prose, and any AI-drafted text he does keep gets cited per the syllabus's academic-integrity clause. Worth a quick follow-up question if this project starts leaning on AI-drafted prose for the report or journals.
- **No AI use** on anything resembling a quiz/exam (the syllabus lists none for this course, so likely moot).
- All AI usage — in-system (explanation agent, failure-analysis assistant) and copilot-style (development assistance) — continues to be recorded in the AI usage log per Outline §16, with provenance detail per the point above.

---

## Fall 2026 Schedule, Deliverables, and Due Weeks

| Week (dates) | Phase | Topics | Deliverable(s) due |
|---|---|---|---|
| 1 (8/24–8/30) | Phase 1 | Course overview; what makes a strong capstone; scoping for impact | Weekly Journal |
| 2 (8/31–9/6) | Phase 1 | Responsible AI (licensing/safety/privacy); AI app patterns (prompting, RAG, tools/agents); repo hygiene + lightweight CI | **Milestone 1: Project Proposal and Scope** · optional reflection · **mandatory 1:1 with Faculty** |
| — (9/7) | — | No class (Labor Day) | — |
| 3 (9/8–9/13) | Phase 2 | Designing evaluation (automatic metrics vs. task-specific rubrics) | Weekly Journal |
| 4 (9/14–9/20) | Phase 2 | Building evaluation harnesses; dataset hygiene and data cards | Weekly Journal |
| 5 (9/21–9/27) | Phase 2 | Baselines: heuristics and off-the-shelf OSS models; introductory error analysis | **Milestone 2: Prototype and Initial Model Integration** · optional reflection · **mandatory 1:1 with TA** |
| 6 (9/28–10/4) | Phase 3 | Prompt engineering strategies; retrieval design and indexing | Weekly Journal |
| 7 (10/5–10/11) | Phase 3 | Structured outputs; tool use/orchestration | Weekly Journal |
| 8 (10/12–10/18) | Phase 3 | Agent frameworks, harnesses, workflow runtimes; automated PR reviewers demo | Weekly Journal |
| 9 (10/19–10/25) | Phase 3 | Latency/cost/caching; model & system cards; UX for AI (guardrails, failure modes) | **Milestone 3: Model or System Development and Alpha Application** · optional reflection |
| 10 (10/26–11/1) | Phase 4 | Packaging and containerization; red-teaming and safety checks | Weekly Journal |
| 11 (11/2–11/8) | Phase 4 | Communicating results; demo storytelling | Weekly Journal |
| 12 (11/9–11/15) | Phase 4 | Local deployment acceptable, with a public demo video | **Milestone 4: Pre-Final Version and Documentation Draft** · optional reflection · **mandatory 1:1 with TA** |
| 13 (11/16–11/22) | Phase 5 | Packaging your work for employers | Weekly Journal |
| — (11/23–11/29) | — | No classes (Thanksgiving) | — |
| 14 (11/30–12/6) | Phase 5 | Course closure and next steps | **Final Capstone Presentation and Showcase** · optional reflection |

**Note 1 — Final Technical Report due date:** the syllabus's grading table lists a **Final Technical Report (20%)** as a separate assessment component, but the schedule table above (pulled from the syllabus's own week-by-week grid) does not list an explicit weekly due date for it. Confirm the exact report due date on Canvas/Ed Discussion — most likely it lands alongside the Final Presentation in Week 14, but don't assume.

**Note 2 — M1 week discrepancy (raised 2026-08-30):** the Phase 1 deck's "Milestones at a Glance" slide dates **M1 as "week ~3"**, while the syllabus's own week-by-week grid (above) puts Milestone 1 at **end of Week 2**, alongside the mandatory Faculty 1:1 that same week. M2 (~5), M3 (~9), and M4 (~12) match between the two sources; only M1 differs. **Plan to Week 2** — being early costs nothing and the Faculty 1:1 is anchored there — but confirm on Canvas. Tracked in `Decision_Tracker.md`.

Mandatory appointments total 3: 1 with Faculty (Phase 1 / Week 2) + 2 with TAs (end of Phase 2 / Week 5, and end of Phase 4 / Week 12) — sign up via WaitWhile.

---

## Grading Breakdown

| Component | Weight | Notes |
|---|---|---|
| Milestones 1–4 | 40% (10% each) | See schedule above for content and due weeks |
| Final Technical Report | 20% | System architecture, methodology, training/fine-tuning process, evaluation, results, future work |
| Final Presentation and Showcase | 25% | Live demo + explanation to peers/faculty/guests — clarity, technical depth, professional polish |
| Weekly Journals | 5% | 9 total, complete/incomplete basis; the Phase 1 deck calls this the **weekly self-evaluation journal**. Document decision points; serves as Milestone reference material |
| Public Repository & Documentation | 5% | Clean, well-documented repo showing dev process, code quality, reproducibility |
| Mandatory Appointments | 5% | 1 Faculty + 2 TA check-ins |

Confirmed unchanged against the Phase 1 deck's "Assessment Breakdown" slide (2026-08-30) — all six components and weights match.

Not curved. Letter grade bands: A+ ≥98, A 93–98, A- 90–93, B+ 87–90, B 83–87, B- 80–83, C+ 75–80, C 70–75, C- 65–70, D 50–65, F <50. No extra credit in this course.

**Late policy:** 10% penalty per late day. 5 free late days for the semester (any reason, self-reported, verified by staff), extension request form required beyond that. No late submissions accepted for the Final Presentation/Showcase.

---

## Milestone 1 — Official Deliverable Spec (from the Phase 1 deck, added 2026-08-30)

The Phase 1 lecture states the M1 submission is **a single PDF** containing exactly eight items. This is the authoritative content list — everything below must appear in the submitted document. The "charter" wording used elsewhere in the deck refers to this same document.

| # | Required item | Where PROJECT BETA's material lives | Status |
|---|---|---|---|
| 1 | **Track declaration** (AI Engineering or Research-Driven) | State explicitly in the proposal header: **AI Engineering Track** | Ready — must be an explicit line, not implied |
| 2 | **Problem statement, target users / readers, value proposition** | `Project_Outline.md` §1A (Product One-Pager) | Ready |
| 3 | **Success metrics — both layers (offline + user-impact)** | Outline §10, restructured into two explicit layers | Ready as of Outline Rev 8 |
| 4 | **Tech stack and compute budget** | Outline §9A (new) | Ready — figures are Week 1 estimates, confirm before submission |
| 5 | **Risks + mitigations** | Outline §15 (Risk Register) | Ready — strongest existing section |
| 6 | **Optional Focus Areas selected** (AI Engineering track only) | Outline §21 (new); declaration summarized below | Ready as of Outline Rev 8 |
| 7 | **Repo URL** with README, LICENSE, CONTRIBUTING, basic CI smoke test | Repo checklist below; Outline §12 Weeks 1–2 | To build — Week 1/2 task |
| 8 | **Pitch artifact — 6-slide deck OR 3–5 min concept video** | Not previously planned; now a Week 2 deliverable in Outline §12 | To build — format decision tracked |

**Plus the Responsible AI material.** The Responsible AI lecture closes with an exercise titled *"Responsible AI for Your Milestone 1"* and states plainly: *"Together these are the ethics-and-safety material in your M1 charter; the staff read them to give feedback."* Four artifacts:

1. **Licensing audit** — pick 2 datasets and 2 models you might use; list each license and the constraint it implies.
2. **Safety plan** — top 3 harms for your system, each with a guardrail and a test.
3. **Fairness note** — name the groups at risk and the one fairness check you'll run.
4. **Privacy plan** — what user data you store, why, retention limits, and your minimization steps.

All four are drafted in **`Project_Outline.md` §20**. Note that these are *distinct from* the Risk Register (§15): §15 is project-execution risk (will the project finish, will the data exist), §20 is system-behavior risk (what could this thing do to someone in the world). Both are required; neither substitutes for the other.

### Milestone 1 Repo Checklist (from the "Repo Hygiene & CI" lecture — six items, not four)

By the end of Phase 1 the repo needs all six. The deck estimates the whole checklist at **about 30 minutes** using GitHub's own templates, and notes the reference document on Canvas has the templates and links.

- [ ] `README.md` — title + one-sentence description, quick start (running in five minutes), installation and usage with a basic example, license. Written for someone who knows nothing about the project; keep it scannable.
- [ ] `LICENSE` — MIT or Apache 2.0. Deck's guidance: *"when in doubt, use MIT"*; Apache 2.0 if explicit patent protection matters. **PROJECT BETA: MIT** (see Outline §20.1).
- [ ] `CONTRIBUTING.md` — setup instructions, how to run tests, PR process.
- [ ] `CODE_OF_CONDUCT.md` — Contributor Covenant via GitHub's one-click template.
- [ ] **Issue labels configured** — start with `bug`, `enhancement`, `documentation`, `good first issue`. The deck notes labeled issues are also how discrete tasks get handed to collaborators *and agents*, which is directly useful for a solo AI-assisted build.
- [ ] `.github/workflows/ci.yml` — a passing CI smoke test, green check on every commit.

**CI guidance from the deck, worth following literally:** `on: [push, pull_request]`, `runs-on: ubuntu-latest`, `uses: actions/checkout@v4`, `run: python -m pytest`. Keep it simple, fix failing tests immediately, **do not run hour-long training or huge datasets in CI**, and never disable a test just to force the check green. For an AI project the smoke test asks the cheapest possible question — does the pipeline load, does inference run on a sample input — e.g. `assert model is not None and model.predict(sample) is not None`.

**Pitfalls the deck calls out by name** (all of which apply to a solo build under time pressure): *"I'll add docs later"* → a stub README now beats a perfect one never; *"my code is too simple to test"* → even `assert model is not None` is real smoke testing; *"I don't need a license for a school project"* → the repo is public and employers will look; *"the AI wrote it, so it must be fine"* → that is vibecoding, verify before you trust; *"CI is too complicated"* → it is fifteen lines of YAML.

### Optional Focus Areas — declared

AI Engineering students pick a focus area (or several) at Milestone 1. The four on offer:

- **Data** — careful data work, novel collection, hard cleaning, novel splitting
- **Model & System** — prompting, RAG, agents, fine-tuning, novel architectures
- **Application & Deployment** — CLI, lightweight UI, containerized, public demo
- **Evaluation & Responsible AI** — custom suite, robustness, bias, safety, latency/cost profiling

**PROJECT BETA declares: Evaluation & Responsible AI (primary) + Model & System (secondary).** Rationale and the full argument are in `Project_Outline.md` §21. In short: the ablation ladder, walk-forward robustness suite, cost-stress testing, grounding audit, and failure-mode analysis are where this project's actual differentiation lives, and the deck's own "Strong vs Weak Projects" rubric rewards exactly that ("custom evaluation tied to the use case", "honest limitations section"). Claiming all four would read as unfocused; claiming *Data* or *Application & Deployment* as primary would misrepresent where the effort goes.

---

## What Each Milestone Needs to Contain (AI Engineering Track)

These content expectations (from the pre-registration capstone guidance, updated 2026-08-30 with the artifacts the Phase 1 deck names) still apply — map them onto the due weeks above:

1. **Milestone 1 (Wk 2) — Project Proposal and Scope:** see the eight-item spec above. The pre-registration framing (one-sentence project statement, initial inputs, simple + off-the-shelf baseline, evaluation metrics and qualitative rubric) is compatible with it — the eight-item list is just more specific. *`Project_Outline.md` §1/§1A serves as the core of this artifact; §9A, §20, and §21 fill the newly-specified gaps.*
2. **Milestone 2 (Wk 5) — Prototype and Initial Model Integration:** a working prototype with at least one model integrated end-to-end (not full calibration yet) — for PROJECT BETA, this means baselines (B1/B2) running plus a first-cut regime classifier wired into the pipeline, not necessarily the completed M1 ablation. The deck's phase summary adds **"Dataset, evaluation harness and rubric, baseline results"** as the Phase 2 output, which matches. A **Data Card** is named at M2 in the deck's milestone slide — Week 4's topic is "dataset hygiene and data cards" — so budget for one.
3. **Milestone 3 (Wk 9) — Model or System Development and Alpha Application:** end-to-end workflow backed by a live inference service ("alpha application"). For PROJECT BETA this is the full paper-trading loop (data → regime → signal-quality → risk → Alpaca paper trade → basic dashboard) — no news component required at this stage. **New from the deck: M3 is "runnable end-to-end with Model & System Cards."** Week 9's topics are latency/cost/caching, model & system cards, and UX for AI. Model and system cards were not in the original plan; they are now Week 9 deliverables in Outline §12 and PRD §7.
4. **Milestone 4 (Wk 12) — Pre-Final Version and Documentation Draft:** near-complete release candidate with reproducible run instructions, documentation, and a demo video draft. **New from the deck: M4 is a "containerized release candidate, demo video, latency & cost report, full eval pass."** Containerization and a latency/cost report were not in the original plan — Week 10's topic is packaging and containerization, Week 9's is latency/cost/caching. Both are now on the timeline. Week 10 also covers **red-teaming and safety checks**; PROJECT BETA's natural red-team target is prompt injection reaching the extraction service through news headlines (if Plan A proceeds) — see Outline §20.2.
5. **Final (Wk 14) — Presentation and Showcase:** polished demo, live presentation to peers/faculty/guests, portfolio-ready framing (Week 13's "packaging your work for employers" is explicitly for this polish pass). The deck confirms the AI Engineering track expects a **live demo at the showcase**, and that deployment may be local or public **provided there is a demo video**.

---

## Milestone 1 Proposal — Reviewer Checklist (from the Intro Video, slide "Three Things Reviewers Look For")

The course materials say reviewers score the proposal against exactly three things. Self-check against PROJECT BETA below — use this framing explicitly when drafting the Milestone 1 write-up, since it's clearly the rubric the reviewer (Faculty, per the Week 2 1:1) will actually apply. The Product One-Pager in `Project_Outline.md` §1A is written specifically to lead with this framing.

1. **A clear problem worth solving — not "build a thing with an LLM."** PROJECT BETA passes: the problem is a named user (discretionary retail trader / junior quant researcher) who wants systematic, interpretable, risk-controlled filtering of trading signals — not "add AI to trading" for its own sake. Lead the proposal with the project statement in Outline §1/§1A, not with the tech stack.
2. **Demonstrable value — something a real user or reader would care about.** PROJECT BETA passes: success is defined as a measurable, prespecified risk-adjusted improvement (Sharpe/max drawdown) over an identical unfiltered baseline, net of costs — or a rigorously characterized negative result — plus an auditable explanation for every trade decision. Both are concrete and falsifiable, which is what "demonstrable" means here; a reviewer can check them. **Added 2026-08-30:** the deck requires a *user-impact* metric alongside the offline ones (see below), and this row is where it earns its keep — "what changes for the user" is the demonstrable-value question restated as a measurement.
3. **Achievable scope — finishable in 14 weeks at a quality you're proud of.** This is the one genuine risk in the current plan and should be addressed head-on in the proposal, not left implicit:
   - The **full** system (data pipeline, features, regime classifier, signal-quality model, risk engine, execution simulator, Alpaca paper trading, evaluation harness, explanation agent, failure-analysis assistant, dashboard, plus a conditional news gate) is a lot for one person in 14 weeks, especially with a working Alpaca paper-trading loop due by **Week 9** (Milestone 3) — nearly two-thirds through the semester's build time, not the full 14 weeks.
   - The existing **Scope Tiers table (Outline §3)** already does the right thing here — it explicitly marks the news components (M3/M4) and the secondary-strategy toggle as conditional/optional/lightweight and states "guaranteed core alone is a complete capstone." **Make this the centerpiece of how the proposal answers the scope question**, not a footnote: reviewers want to see that you already know where you'd cut if behind schedule, and PROJECT BETA already has that answer.
   - Consider naming explicit fallback checkpoints in the proposal itself (e.g., "if the regime classifier isn't calibrated by Week 6, the news gate is dropped regardless of the Week 2 feasibility verdict") so "achievable scope" reads as a decision already made, not an aspiration.
   - The deck's **Time Budget** slide is a useful sanity check to quote against: Weeks 1–2 scope + repo + groundwork (*"don't start the build yet"*), Weeks 3–5 data + eval + baselines (*"the hardest part for most students"*), Weeks 6–9 the main build (*"4 weeks goes fast"*), Weeks 10–12 polish and ship (*"resist the urge to add features"*), Weeks 13–14 write, record, present (*"reserve real time for this"*). PROJECT BETA's Outline §12 already matches this shape.

### Two kinds of success metrics — both required (added 2026-08-30)

The deck devotes a slide to this and marks **both** rows "Necessary":

| Offline metric | User-impact metric |
|---|---|
| What you measure on a test set | What changes for the user |
| Accuracy, F1, BLEU, NDCG | Task completion rate, time saved, perceived quality |
| Easy to compute, hard to interpret | Hard to compute, easy to interpret |
| **Necessary** | **Necessary** |

PROJECT BETA's metrics were all offline (Sharpe, drawdown, Calmar, precision/recall, calibration, Brier). The user-impact layer now lives in `Project_Outline.md` §10 as a measured protocol rather than an unquantified rubric — the existing "a new user can identify the current regime, open positions, and last decision rationale without guidance" statement was the right idea, it just needed a number, a procedure, and a target. **Report both layers in the proposal and in every milestone write-up.**

### The Interview Test (worth re-reading at every milestone)

The deck calls this *"the single most useful question to ask yourself at every milestone"*: **"In a job interview six months from now, will I want to talk about this project?"** If yes, keep going. If no, change scope until the answer becomes yes.

### Risk vs Ambition

The deck's 2×2 recommends **high ambition, controlled risk**, and asks specifically that you **identify your one biggest risk in M1 and propose a fallback**. PROJECT BETA's single biggest risk is the Week 1 data-source question — multi-year 5–10 min SPY history at usable quality — and it already has a pre-approved fallback (Massive/Polygon Developer tier). Name that pair explicitly in the M1 write-up rather than burying it in the Risk Register; it is a direct answer to a question the reviewer was told to ask.

---

## Strong vs. Weak Projects — Self-Check (from the Intro Video, slide "Strong vs Weak Projects")

Another rubric from the same course materials, phrased as a five-row comparison. PROJECT BETA checks out well against all five — worth knowing which rows are genuine strengths to protect (don't let them erode as the semester gets busy) versus rows that are only strong *if the plan is actually executed as documented*:

| Row | Stronger (what PROJECT BETA should be) | Weaker (the trap to avoid) | Where PROJECT BETA stands |
|---|---|---|---|
| 1 | One concrete deliverable, defended end-to-end | A grab-bag of AI experiments | **Strong, protect it.** Five AI components (regime classifier, signal-quality model, explanation agent, failure-analysis assistant, optional news gate) plus a secondary-strategy toggle sound like a grab-bag on paper, but they're all wired into *one* pipeline behind *one* primary deliverable (Outline §4), with the secondary strategies explicitly walled off from the graded evaluation (PRD §5.14) so they can't dilute it into a grab-bag. Keep it that way. |
| 2 | Clear user / reader / use case | "Something with an LLM" | **Strong** — same basis as the Milestone 1 checklist above (named user, named workflow). |
| 3 | Custom evaluation tied to the use case | Generic accuracy metrics | **Strong, and a real differentiator.** The trading metrics (Sharpe, Sortino, drawdown, Calmar, profit factor — Outline §10) are specific to the use case, not generic ML accuracy; ML metrics (precision/recall/calibration) are explicitly secondary support for the trading claim, not the headline result. Keep the trading metrics as the lead result in every milestone write-up and the final report — don't let ML metrics crowd them out just because they're easier to compute early. |
| 4 | Honest limitations section | Glossy demo with no failure modes | **Already a required deliverable, not an afterthought** — the Failure-Analysis Assistant (Outline §5.5) and the explicit framing in §18 ("a rigorous negative result is an acceptable and defensible outcome") mean limitations are structurally built into the success criteria, not something bolted on for the final report. This is arguably the project's strongest row on this rubric — make sure the final report and demo actually show the failure-mode analysis prominently, not just mention that it exists. |
| 5 | Demo *and* a real eval result | Demo only | **Strong by design** — Milestone 3 (Wk 9) requires the live Alpaca paper-trading demo, and the evaluation harness (B1→M2 ablation, walk-forward, robustness suite) produces the eval-result side independently of the demo. The risk is sequencing: if time gets tight, make sure the eval harness doesn't get sacrificed to polish the demo — the rubric explicitly penalizes demo-only, and the eval results are actually the guaranteed-core section's real evidence for the primary research question (Outline §2). |

**Common failure modes the deck names** (worth checking against at each milestone): scope creep (*"started with two features, ended with twelve, finished with one, badly"*); **no eval until M3** (*"building blind for nine weeks, then panicking"*) — PROJECT BETA is structurally protected here, since the eval harness is a Weeks 3–4 deliverable, well before the build; all build, no docs; all docs, no system; and picking a problem you don't actually care about (*"burns out by week 8"*).

**Bottom line:** PROJECT BETA's design already satisfies both rubrics well on paper. The main execution risk isn't scope-cutting away from these strengths — it's letting time pressure quietly narrow the "guaranteed core" work down to demo polish (Row 5's weak side) or a thin limitations mention (Row 4's weak side) later in the semester. Re-check this table at each milestone, not just at proposal time.

---

## Positioning Note — "Is there enough AI in this?" (added 2026-08-30)

The Phase 1 deck's AI-application-patterns material puts capstone-appropriate work at the lower tiers of the cost/complexity spectrum (prompting, structured outputs, light tool use) and lands on the takeaway that **the unique value lives in the pipeline, not in any single model**. That is a useful shield for PROJECT BETA, because a fast reader could look at it and see classical ML (XGBoost regime and signal-quality models) doing the analytical work with the LLM confined to explanation and failure analysis, and wonder whether it clears the bar.

Preempt it in the proposal rather than waiting to be asked. The honest framing: PROJECT BETA deliberately selects the **lowest pattern tier that meets the requirement** for each job — deterministic math where determinism matters (risk engine, cost model), gradient-boosted trees where the task is tabular classification on price features, and an LLM only where natural language is genuinely the output (grounded explanations, failure-mode narrative). Using an LLM for regime classification would be more expensive, slower, less calibratable, and worse — and choosing not to is an engineering judgment worth stating out loud. The value claim is the composed, audited pipeline, which is exactly what the course says it should be.

---

## Timeline Alignment Check — PROJECT BETA vs. Official Schedule

Comparing `Project_Outline.md` §12 / `PROJECT_BETA_PRD_v1.1.md` §7 against the table above surfaced two real misalignments, corrected in both docs:

1. **"Alpha" was pinned to Week 7 in the original plan; the actual Milestone 3 (Alpha Application) is due end of Week 9.** Week 7's actual syllabus topic (structured outputs / tool orchestration) has no deliverable attached. The plan's Weeks 7–9 now target getting the full paper-trading loop live on Alpaca by Week 9, not Week 7.
2. **Documentation/demo-video work was originally scheduled for Week 13 ("release candidate"), but Milestone 4 (Pre-Final Version + Documentation Draft, including a public demo video) is due end of Week 12.** The plan's Week 11–12 block now targets a substantially complete release candidate — docs, architecture diagram, demo video draft — by Week 12, leaving Week 13 for the "package for employers" polish pass the syllabus schedules that week, and Week 14 for final presentation delivery.

**Third alignment pass (2026-08-30), from the Phase 1 deck:** three artifacts the plan did not previously produce are now on the timeline — a **pitch artifact** (6-slide deck or 3–5 min concept video) at Week 2, **Model & System Cards** at Week 9, and a **containerized release candidate plus a latency & cost report** at Week 12. See Outline §12 and PRD §7.

Milestone 1 (Wk 2) and Milestone 2 (Wk 5) remain on track as originally scoped. This also matches the simplified 5-phase summary from the course's own materials (Phase 1 Wks 1–2 → M1; Phase 2 Wks 3–5 → M2 + TA check-in; Phase 3 Wks 6–9 → M3; Phase 4 Wks 10–12 → M4 + TA check-in; Phase 5 Wks 13–14 → Final Deliverable), confirming the corrected mapping is right.

---

## Multi-Strategy Architecture — RESOLVED (2026-08-26)

Was previously an open design question alongside the interactive query layer. Now confirmed: **one primary strategy (momentum breakout) ships with full evaluation rigor; MA trend and mean reversion are exposed through the same Strategy Engine interface as a lightweight, backtest-only exploratory toggle**, explicitly so the architecture stays extensible for continued development after the course ends. See `Project_Outline.md` §3/§5.3/§7 and `PROJECT_BETA_PRD_v1.1.md` §2/§5.3/§5.14 for the full design and the evaluation-rigor safeguard (secondary strategies are structurally blocked from entering the graded ablation harness, not just documented as off-limits).

**Still open:** the interactive query layer (ask the explanation agent about a trade on demand) remains an optional, Week-10-gated decision — see `Decision_Tracker.md`.

---

## Product One-Pager & Demo Walkthrough — added 2026-08-26

`Project_Outline.md` §1A now has a tight, proposal-ready statement of the problem, audience, proposed idea, differentiator, and success criteria — use it as the lead framing for the Milestone 1 write-up rather than re-deriving it. `Project_Outline.md` §19 has a full plain-language pipeline walkthrough, a screen-by-screen description of the dashboard UI (including the new strategy-toggle panel), and a sample demo script — useful for the proposal's "what does the end user see" question, the Milestone 3 Alpha demo, and the Milestone 4/Final Presentation demo video. §19 is also the source material for the Week 2 pitch artifact.

---

## Professor Policy Confirmations — added 2026-08-28

Three additional policy questions were emailed to Dr. Callison-Burch and confirmed by his reply (2026-08-28): VPN use has no restriction; real-money trading is allowed though he recommends sticking with simulated funds; implementation language is open (not restricted to Python/C++). None of these change PROJECT BETA's current plan — they're logged as available fallback levers in `Decision_Tracker.md` in case execution issues require a pivot later in the semester. He also asked that future policy/logistics questions go through Canvas rather than email, since TAs can help there and his email response time varies.

---

## Success Criteria (unchanged)
The final deliverable should be **coherent, reviewable, and defensible** — with clear evidence of what it does well and where it still falls short. Perfection is not the goal.