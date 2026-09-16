# C2: record access

**Draft, not frozen. Revised 2026-09-15, third pass.** Henry drafted this. It
freezes only when Henry and Jacky both agree it, in writing, after the questions
in section 11 are answered. A review with no objections is not a freeze.
Changes after the freeze need a `DECISIONS.md` entry.

C2 defines how evidence is stored, named, loaded and exposed to an answering
system. C1, the case file, references evidence only through the IDs defined here.

Naming, because three things share letters. **Trading M1 and M2** are the model
rungs (regime classifier, signal-quality model). **Milestone M2** is the
September 28 deliverable. **E0 to E3, Oracle and Full** are answerers in the
evaluation harness.

---

## 1. What this contract does and does not give us

`grounding.record_numbers()` permits every number anywhere in the dict it is
given, and `record_labels()` collects controlled-vocabulary terms and uppercase
tokens from it. `check_explanation()` then checks numbers, and checks only the
**nine** terms in `CONTROLLED_VOCABULARY`. It does not check reason codes in the
text, and it does not know about thresholds or citations.

So:

- The projection in section 6 **bounds which values an answer may cite**. That is
  all it does.
- It does **not** establish that an answer is factually correct, that it cites the
  right record, or that its reasoning follows. Those need the checks in section 7,
  most of which are new code in H5 and H6.

**What this document is.** A specification of intended behaviour and the checks
that would demonstrate it. The statements about how `grounding.py` behaves today
were checked by running it; everything else here describes code that does not
exist yet. Nothing in this contract is evidence that an implementation works, and
the acceptance checks in section 10 have not been run.

## 2. Storage

```
data/fixtures/records/<corpus_id>/manifest.json
data/fixtures/records/<corpus_id>/decisions.jsonl
data/fixtures/records/<corpus_id>/traces.jsonl        (later)
data/fixtures/records/<corpus_id>/aggregates.jsonl    (later)
data/fixtures/sample_records/                          bounded, committed
```

`corpus_id` is `<config_hash_8>-<dataset_hash_8>-<export_seq>`. Config hash alone
does not identify a corpus: the same config can be exported twice, and the same
config against different bars is a different body of evidence.

**The manifest declares what exists**, which is what makes a staged delivery legal:

```json
{
  "corpus_id": "5cd99d0d-ab573530-01",
  "c2_version": "1.0",
  "config_hash": "5cd99d0d59d6ec80",
  "dataset_hash": "sha256:ab573530...",
  "exported_at": "2026-09-16T04:10:00Z",
  "exporter_version": "export_records_v1",
  "code_revision": "e3ce659",
  "cost_basis": "base",
  "replay_check": {"method": "daily_returns_vs_fold_results", "status": "not_run"},
  "systems": ["B2", "M1", "M2"],
  "folds": [0, 1, 2],
  "parts": {"decisions": true, "traces": false, "aggregates": false},
  "counts": {"decisions": 1843},
  "notes": "H1 decisions-only export"
}
```

**H1 may export decisions only.** A corpus with `traces: false` is valid and
loadable. Traces arrive with J1, aggregates with J5, each adding its file, its
count and its `parts` flag. Adding a part is a new export sequence, not an edit of
an existing corpus.

**Three failure modes, three errors, never conflated:**

| Situation | Error | What the inspector says |
|---|---|---|
| The manifest says a part is absent, and a case asks for it | `CorpusIncomplete` | "This corpus does not contain rule-state traces" |
| The part exists, the ID is not in it | `MissingEvidence` | "No trace was recorded for that bar" |
| A file or line fails to parse or fails its schema | `CorpusMalformed` | Nothing. The run aborts; this is a bug, not a refusal |

The first two produce a refusal that names what is absent. The third never
produces a refusal: a parse failure is our bug, and hiding it behind a polite
sentence is how a broken corpus passes an evaluation.

**These are behaviours, not scores.** Whether a refusal was the right answer is
decided by C1 and the harness, not here (section 7). Evidence can be unavailable
for several reasons and only one of them means something is broken:

| Why evidence is unavailable | Broken? |
|---|---|
| Withheld on purpose, as in the no-record retrieval mode | No. The refusal is the expected behaviour |
| The part was never exported, as in a decisions-only corpus | No. Legal staged delivery |
| The ID is genuinely absent, for example no trace at that bar | No. Often the true answer to the question |
| Retrieval ran and returned nothing for an answerable case | Not necessarily. Could be a retrieval failure rather than a corpus fault |
| A case C1 labels answerable names an ID the corpus should contain | Yes. Corpus or case defect, to be fixed, not scored as a refusal success |

Full corpora stay out of git (section 9).

## 3. Evidence IDs

| Form | Example |
|---|---|
| `dec:<corpus>:<system>:<trade_id>` | `dec:5cd99d0d-ab573530-01:M2:trade_00123` |
| `trace:<corpus>:<system>:<fold>:<iso8601>` | `trace:5cd99d0d-ab573530-01:B2:1:2021-03-04T10:35:00-05:00` |
| `agg:<corpus>:<script>@<script_version>:<args_hash>` | `agg:5cd99d0d-ab573530-01:most_common_rejection@v1:9f12ab` |

**Why the system is in the ID.** `systems.py` generates candidates once and runs
them through B2, M1 and M2 with the same `config.run_id`, and
`_decision_id = uuid5(run_id | trade_id)`. So the same candidate produces the
**same `decision_id` under all three systems**. The record's `decision_id` is
therefore not a unique key and must never be used as an evidence ID. Export keeps
it as a field, `source_decision_id`, for traceability back to the simulator, and
writes `evidence_id` as the key. `source_decision_id` is stored for provenance
and is **not** projected, on decisions or on traces: a value that cannot resolve a
lookup has no business in a citable answer.

**Traces carry the same ambiguity**, plus one more: the same bar is evaluated by
each system, and can be evaluated in more than one fold's windows. System and
fold index are therefore part of the trace ID.

**Aggregate identity has three inputs**, and all three belong in the ID or beside
it: the corpus the aggregate was computed from, the script and its version, and
the hash of its arguments. Same arguments over a different corpus is a different
number, and that is exactly the mistake a stale citation makes.

Rules: IDs are stable, never reused after deletion, and timestamps are full ISO
8601 in market time with offset.

## 4. Record shapes

**DecisionRecord.** As emitted by `execution/simulator.py` (`_record_for`), plus
the export additions in section 5. Approved, reduced, rejected and
no-bar-at-fill decisions are all written today, which is what gives the case set
its variety.

**Rule-state trace.** J1 owns the implementation. C2 fixes only what the loader
and the projection need:

```json
{
  "evidence_id": "trace:5cd99d0d-ab573530-01:B2:1:2021-03-04T10:35:00-05:00",
  "timestamp": "2021-03-04T10:35:00-05:00",
  "system": "B2",
  "fold": 1,
  "strategy_version": "momentum_breakout_v3",
  "conditions": [
    {"name": "dist_high_78", "required": ">= 0", "observed": -0.0031, "passed": false}
  ],
  "first_failed": "dist_high_78",
  "produced_candidate": false,
  "decision_evidence_id": null,
  "source_decision_id": null
}
```

`first_failed` is null when every condition passed.

**A trace links to its decision through `decision_evidence_id`, not through
`source_decision_id`.** The simulator's `decision_id` repeats across systems
(section 3), so it cannot resolve a decision on its own. `source_decision_id` is
kept for provenance back to the simulator and is never used for lookup. Both are
null where the bar produced no candidate, and `decision_evidence_id` is null
where a candidate was produced but no decision record was written for it in this
corpus; the two cases are distinguished by `produced_candidate`.

Where no trace exists the loader raises rather than inferring: a guessed cause
for a non-event is a fabricated claim about our own system.

**Aggregate.** Written by Jacky's scripts, never by an answering path. A single
scalar does not cover the five planned aggregates, so the contract allows three
declared value shapes:

| `value_kind` | Shape | Used by |
|---|---|---|
| `scalar` | string or number | most common rejection reason |
| `mapping` | object, string keys to numbers | approval rate by regime |
| `table` | list of row objects with declared columns | rejections per gate per quarter; trades and exposure per fold; size distribution |

```json
{
  "evidence_id": "agg:5cd99d0d-ab573530-01:rejections_by_gate@v1:9f12ab",
  "script": "scripts/aggregates/rejections_by_gate.py",
  "script_version": "v1",
  "args": {"system": "M2", "group_by": "quarter"},
  "value_kind": "table",
  "columns": ["quarter", "gate", "rejections"],
  "value": [{"quarter": "2019Q3", "gate": "regime", "rejections": 118}],
  "n": 412,
  "computed_at": "2026-09-21T18:02:11Z"
}
```

Each script declares its `value_kind` and `columns` once. The projection permits
only declared columns, with declared types. Arguments are **not** stringified:
stringifying hides numbers from the checker while the model still reads them,
which is the worst of both. Instead, argument values are restricted to the
declared enumerations and date strings in section 6.

## 5. Fields that are not emitted yet

Two gaps, both in evidence production rather than model development. Neither
requires changing trading M1 or M2.

### 5.1 `risk.position_size`

Quantity is computed by `_size()` after the gate verdict and kept on the trade
and the pending tuple, not written into the record. The contract defines it as
**the requested quantity at sizing time**, and adds filled quantity separately,
so a request that never filled cannot be read as a position.

| Path in `run_backtest` | Quantity | `risk.position_size` | `execution.filled_quantity` |
|---|---|---|---|
| Rejected at a gate, before sizing | Never computed | Absent | Absent |
| Sized to zero | 0 | `0` | Absent |
| Rejected at the fill bar: halt, daily loss, or position already open | Known | Requested | Absent |
| No fill available (`NoFill`) | Known | Requested | Absent |
| Filled | Known | Requested | Filled quantity |
| Still pending when the window ends (`NO_BAR_AT_FILL`) | Known | Requested | Absent |

In today's simulator a fill is all or nothing, so filled equals requested
wherever a fill occurred. Recording both keeps the distinction honest if partial
fills ever appear.

The change touches every site where a record is written after sizing: the
zero-quantity rejection, the three rejection paths at the fill bar, the fill
itself, and the end-of-window pending loop. Each is an assignment where
`quantity` is already in scope, with no new computation and no effect on any
number the graded run produced. The earlier "two-line change" description in this
document was wrong and is withdrawn.

### 5.2 Threshold provenance

**The threshold itself is already emitted.** `SignalQualityModel.score()` returns
`threshold` in the `signal_quality` block, so any record written through the
signal-quality gate carries it. What is missing is the provenance required by
`DECISIONS.md` #28: which fold, and which validation window, chose that value.

Fold identity lives in the runner, not the gate. The relevant objects are
`FoldArtifacts` (which holds `fold`, `regime_model`, `signal_quality` and
`threshold`), `FoldRun` (one fold at every cost level, with its artifacts) and
`WalkForward` (the runs that happened and the folds that did not). There is no
`FoldResult`; the earlier reference to one in this document was wrong.

**How H1 captures decisions.** `_test_window()` returns `FoldReturns`, which keeps
daily returns and discards `result.decisions`, so the graded run does not retain
the records at all. The export therefore re-runs the test windows rather than
reading them back:

1. Run the walk-forward as usual and keep the `WalkForward`.
2. For each `FoldRun`, rebuild the gates from its `FoldArtifacts` and replay each
   system over that fold's test window with `run_backtest`, keeping
   `result.decisions`.
3. Stamp `m2_threshold_fold` and `m2_threshold_window` from the fold.

Reusing the fitted models is necessary for an equivalent replay but not
sufficient. The replay reproduces the graded run's decisions only if all of these
match: the same bars (`dataset_hash`), the same feature frame built the same way,
the same candidate generation (same strategy and parameters), the same
`RunConfig` (`config_hash`, including the cost multiplier), the same test-window
index range, the same `starting_equity`, and the same code revision. `config_hash`
does not cover the code, so the manifest records the git revision the export ran
at, beside `exporter_version`.

**H1 exports base-cost runs only.** The 2x and 3x stressed replays are separate
series and are not exported for milestone M2.

**Replay check.** For each fold and system, compare the daily returns produced by
the export against the retained `FoldReturns` from the graded run, and record the
comparison in the manifest. Its limits, stated plainly: equal daily returns do not
prove every record is identical, since fields that do not affect returns could
still differ, and the check covers only the folds and systems the graded run
retained. **No equivalence has been tested yet.** The check is a requirement of
this contract, not a result.

The export reuses two private runner helpers, `_build_gates` and `_index_ranges`;
whether those get public names is an implementation detail for whoever writes H1,
not a contract question.

**Stamping rule.** Provenance is added **only where the record already carries
`signal_quality.threshold`**. B2 has no gate, M1 runs the regime gate alone, the
signal-quality gate returns without a `signal_quality` block when the feature row
is missing, and on folds where no signal-quality model trained, M2 runs the
regime gate. Those records have no threshold, and no threshold is invented for
them. The recorded value is preserved exactly; the export never recomputes it.

Window format: `m2_threshold_window` is `<validation_start>..<validation_end>`
from the fold, both ISO dates, half-open at the end like the fold itself.

**Ownership of both changes is open**, and is question 4 in section 11. They are
edits to evidence production, which is a different question from who develops the
trading models.

## 6. Projection: the permitted fields

`project(record, view="answerer")` returns only what is listed here, with the
listed types. Default deny: anything unlisted is dropped, including fields added
later.

**Decision records**

| Field | Type |
|---|---|
| `evidence_id`, `trade_id` | string |
| `timestamp` | ISO 8601 string |
| `system`, `symbol`, `signal_type`, `strategy_version` | string |
| `signal_strength` | number |
| `decision` | one of `approved`, `reduced`, `delayed`, `rejected` |
| `decision_reason_codes` | list of strings, each in `REASON_CODES` (14 codes) |
| `risk.sizing_rule` | string |
| `risk.risk_per_trade`, `risk.size_multiplier` | number |
| `risk.position_size` | number, requested quantity, present only where sizing happened (section 5.1) |
| `instrument.selected`, `instrument.selection_rule` | string |
| `instrument.tradeable` | boolean |
| `entry_price_ref`, `stop_price`, `target_price` | number |
| `regime.label` | one of `uptrend`, `downtrend`, `choppy` |
| `regime.probs` | object, keys restricted to those three labels, values numbers |
| `regime.model_version`, `signal_quality.model_version` | string |
| `signal_quality.p_profit`, `signal_quality.threshold` | number |
| `signal_quality.m2_threshold_fold` | integer |
| `signal_quality.m2_threshold_window` | string, `YYYY-MM-DD..YYYY-MM-DD` |
| `signal_quality.abstained` | boolean |
| `execution.fill_price`, `execution.slippage_bps`, `execution.commission` | number, present only where the decision filled |
| `execution.filled_quantity` | number, present only where the decision filled |

**Traces:** `evidence_id`, `timestamp`, `system`, `fold`, `strategy_version`,
`conditions[].name` (string), `conditions[].required` (string),
`conditions[].observed` (number), `conditions[].passed` (boolean),
`first_failed` (string or null), `produced_candidate` (boolean),
`decision_evidence_id` (string or null). `source_decision_id` is not projected,
here or on decisions (section 3).

**Aggregates:** `evidence_id`, `script`, `script_version`, `value_kind`, `n`,
`columns`, `value`, and `args` restricted to declared keys whose values are
either a declared enumeration member (`system`, `gate`, `regime`, `group_by`) or
a date or quarter string. `value` is projected against `value_kind`: scalars pass
through, mappings permit only the declared key set, tables permit only the
declared columns. Numbers inside a projected aggregate are citable, which is the
point of an aggregate.

**Excluded and not citable:** `run_id`, `mode`, `asset_class`, `feed`, `vendor`,
`config_hash`, `dataset_hash`, `execution.fill_delay_bars`, `source_decision_id`,
and every run-level configuration value. These are provenance for us rather than
facts for an answer, and each numeric one would widen what the checker permits.
`fill_delay_bars` is a configured constant repeated on every record, not a fact
about this decision.

**A threshold never travels alone.** `score()` already emits the threshold, so
the export adds the fold and window beside it. After export, a projected record
carrying `signal_quality.threshold` without both provenance fields is
`CorpusMalformed`, not a quietly weaker record. Records with no threshold at all
are ordinary and expected: B2, M1, and M2 on folds where no signal-quality model
trained.

## 7. Grounding and citations

**Both the prompt and the check use the same projected evidence.** Building the
prompt from the projection while checking against the raw record would restore
every value the projection just removed. The answering path therefore holds one
projected object per evidence ID and passes that object, not the record, to the
checker.

Order of operations on a generated answer:

1. **Parse and validate citations.** Every `evidence_id` in the text must be in
   the set supplied to this answer. An unknown or unsupplied ID fails, before
   anything else runs.
2. **Validate date-like spans, and fail unsupported ones outright.** Dates are
   strings in the evidence, and `record_numbers()` collects numbers only, so no
   date in the evidence is ever a permitted number. Meanwhile `_NUMBER` reads
   `2019-07-01` in an answer as 2019, -7 and -1. Leaving an unmatched date to the
   number check is not enough: its parts can coincide with permitted values and
   pass by accident. So every span in the answer matching one of the four formats
   this contract uses is compared against the string values of the projected
   evidence, and an unmatched span **fails immediately**, independently of
   `check_explanation`.

   The four recognised formats, and nothing else, so this stays a small matcher
   rather than a date parser: `YYYY-MM-DD`, `YYYY-MM-DD..YYYY-MM-DD`, an ISO 8601
   timestamp with offset, and `YYYYQn`. Dates written any other way are not
   recognised and are not citable; an answer needing one quotes the evidence
   string.
3. **Mask only what was validated**: citation IDs from step 1 and date spans from
   step 2. Everything else reaches the number check. Masking after validation
   means an invented ID or date cannot hide inside a masked span.
4. **`check_explanation()` on the projected evidence**, unchanged, for numbers
   and the nine controlled terms.
5. **Reason codes.** Any token matching `[A-Z][A-Z0-9_]{2,}` that is one of the 14
   `REASON_CODES` must appear in the cited evidence. Today a fabricated
   `REGIME_BLOCKS` passes against a record whose only code is
   `SQ_BELOW_THRESHOLD`; this closes that.
6. **Threshold attribution.** An answer citing a threshold value must also name
   the validation window from the same record, matched as a validated span in
   step 2. A threshold with no window, or with a window belonging to another
   fold, fails.

**What exists today:** step 4 only. **New in H5 and H6:** steps 1, 2, 3, 5 and 6,
as a thin wrapper around `enforce_grounding`. `grounding.py` itself is not
rewritten for milestone M2.

None of this shows an answer is true. It shows that every checkable claim traces
to evidence the answer was given, and that its citations resolve.

**Refusal behaviour is not a score.** This contract says what the system does
when evidence is absent: `CorpusIncomplete` and `MissingEvidence` produce a
refusal that names what is missing, and `CorpusMalformed` aborts. Whether that
refusal was the *correct* answer belongs to C1 and the harness, case by case, as
section 2 sets out:

- Evidence withheld on purpose, as in the no-record retrieval mode, is an
  evaluation condition. A refusal there is the behaviour being measured.
- Retrieval can return nothing while the corpus holds the evidence. That is a
  retrieval failure, and it is distinct from the corpus lacking anything.
- An ID a case requires, absent from the declared evaluation corpus, is a corpus
  or case defect to be fixed rather than scored.

C2's job is to keep the three situations distinguishable so the harness can score
them apart. It does not decide which one counts as success.

## 8. Loader API

`src/project_beta/inspector/records.py`, four entry points:

```python
load_corpus(path: Path) -> Corpus
Corpus.get(evidence_id: str) -> dict            # MissingEvidence / CorpusIncomplete
Corpus.evidence_for(case: dict) -> list[dict]   # resolves C1 evidence_ids, in order
project(record: dict, view: str = "answerer") -> dict
```

- Errors carry the ID that failed and, for `CorpusIncomplete`, the missing part.
- A missing record never returns an empty dict. An empty dict is how a refusal
  turns into an invented answer.
- `load_corpus` validates the manifest against the files: declared parts present,
  counts matching, IDs unique, and every **non-null** `decision_evidence_id` in a
  trace resolving to a decision in this corpus whose `system` matches the trace's
  `system`. Null links are valid and are not an error (section 4). Any failure is
  `CorpusMalformed`.
- `evidence_for` raises on the first unresolved ID rather than returning a partial
  list.
- Read-only. Nothing here writes to a corpus.
- Retrieval stays separable from generation (`DECISIONS.md` #27), so the harness
  can supply evidence directly, let the system retrieve it, or withhold it.

## 9. Git exclusions

Full corpora must be excluded **before H1 runs**, and the current `.gitignore`
covers `logs/` and `runs/` only. Nothing covers `data/fixtures/records/`.

Note the git rule that makes the obvious fix fail: a file cannot be re-included
once a parent directory is excluded, so ignoring `data/fixtures/records/` and
un-ignoring `data/fixtures/records/sample/` does not preserve the sample.

Two workable shapes, to be applied in a separate change:

- **Preferred:** ignore `data/fixtures/records/` outright and keep the committed
  sample in `data/fixtures/sample_records/`, which matches the existing
  `sample_decisions.jsonl` precedent.
- Alternative: ignore `data/fixtures/records/*/` and re-include the sample
  directory itself, which works because the negation targets a directory rather
  than a file under an excluded one.

Reason unchanged: vendor terms bar redistribution, and a multi-year decision log
approximates a price series (`DECISIONS.md` #15).

## 10. Acceptance checks

These ship with the implementation. Grouped by what they protect.

**Identity**

1. On the raw exported records, the same candidate under B2 and M2 yields
   different `evidence_id` values and identical `source_decision_id` values, so
   the collision is documented by test.
2. Trace IDs differ across systems and folds for the same bar timestamp.
3. A trace resolves its decision through `decision_evidence_id`; a trace with a
   null link and `produced_candidate: false` resolves to no decision without
   error.
4. Two aggregates with identical arguments but a different corpus or script
   version have different IDs.

**Corpus and errors**

5. A decisions-only corpus loads; asking for a trace raises `CorpusIncomplete`;
   asking for an absent decision raises `MissingEvidence`; a malformed line raises
   `CorpusMalformed`.

**Projection**

6. `project()` drops an unlisted field, asserted with a record carrying a
   deliberate extra numeric value.
7. `project()` drops an undeclared aggregate column and an undeclared
   `regime.probs` key.
8. Execution fields project from `execution.*`; `execution.fill_delay_bars` is
   dropped, and `source_decision_id` is dropped from decisions and from traces.
9. `risk.position_size` is absent for a gate rejection before sizing, zero for a
   zero-sized candidate, and the requested quantity for a filled decision, with
   `execution.filled_quantity` present only in the last case.
10. A projected record with `signal_quality.threshold` and no fold or window
    fails validation; a record with no `signal_quality` block at all passes.

**Citations, dates and codes** (with the H5 and H6 wrapper)

11. A valid citation passes; an ID not supplied to that answer fails.
12. A correct answer containing a valid citation passes the number check, proving
    masking happens after validation.
13. **Positive case:** an answer citing both the recorded threshold and its exact
    validation window passes.
14. An answer citing the threshold with no window fails.
15. An answer citing the threshold with a window from another fold fails.
16. An invented date that matches nothing in the evidence fails at step 2, even
    when its component numbers appear in the record.
17. A valid `decision_evidence_id` resolves; a link pointing at another system's
    decision fails corpus validation.
18. A replay whose daily returns differ from the retained fold results is
    reported rather than exported silently.
19. A fabricated reason code fails against a record carrying a different code.

Checks 1 to 10, 17 and 18 land with the loader and the export. Checks 11 to 16
and 19 land with the wrapper.

## 11. Open questions for Jacky

Questions 1 to 4 are what unblock a freeze, and the freeze itself is Henry and
Jacky agreeing in writing. Question 5 is optional: the current requirement stands
as written and needs no decision, so an unanswered question 5 does not hold up
anything.

1. Does the `trace:` ID form fit what J1 will emit, or do you need a bar index
   alongside the timestamp? Related: is `decision_evidence_id` the link you would
   write, given the simulator's `decision_id` repeats across systems?
2. Do the three aggregate value kinds, scalar, mapping and table, cover your five
   aggregates, and are per-script declared `columns` how you would write them?
3. Anything in section 6 that should be citable and is not, given the Tier 2
   questions you expect to write?
4. Who makes the two evidence-production changes in section 5: the
   `position_size` assignments in `run_backtest`, and the export-time fold and
   window stamping? This is about who edits evidence production. It says nothing
   about ownership of the trading models.
5. **Optional, raise it only if you want to.** Citing the validation window is
   the current requirement and stays as it is unless someone asks otherwise:
   `DECISIONS.md` #28 says a record carrying a fitted threshold carries the fold
   **and the validation window**, and its enforcement column requires a test that
   an answer citing a threshold also cites its window. Section 7 implements that,
   and no policy change is needed to keep it. If you would rather answers cited
   the fold index alone, that is a policy change: the manifest would need a fold
   table so a fold index resolves to exactly one validation window, and #28 would
   need amending, which takes both our agreement and a decision entry. Silence
   here means the window citation stands.

## 12. Relationship to C1

C1 can be drafted now. It cannot be frozen until four things line up with this
document:

- **Evidence IDs**, so `evidence_ids` entries resolve.
- **Available fields**, so no answer key names a field the corpus does not carry,
  which is what question 4 above decides for `position_size` and the window.
- **Aggregate answer shapes**, so Tier 2 keys match scalar, mapping or table
  rather than assuming a single number.
- **Missing-evidence and refusal semantics**, so C1 can score a refusal correctly
  and can tell an unanswerable case apart from a corpus gap.

Freezing C1 and C2 together, after Jacky's answers, is cheaper than freezing them
in sequence.
