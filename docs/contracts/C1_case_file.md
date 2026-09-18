# C1: the case file

**Draft, not frozen. Revised 2026-09-16, fourth pass.** Henry drafted this. It
freezes together with C2, when Henry and Jacky both agree both documents in
writing. Assumptions that depend on open questions are marked **[pending]** and
collected in section 12. Changes after the freeze need a `DECISIONS.md` entry.

C1 defines the evaluation cases: what the answerer is given, what the evaluator
holds, what counts as a correct answer, and how a case set is validated. It
references evidence only through the IDs defined in `C2_record_access.md`.

Naming: **trading M1 and M2** are the model rungs, **milestone M2** is the
September 28 deliverable, **E0 to E3, Oracle and Full** are answerers.

---

## 1. What C1 does and does not do

C1 says what each case asks, which evidence a correct answer rests on, and what
that answer contains. It does **not** define metrics, scoring formulas, prompts
or retrieval behaviour; the harness owns those, and C2 owns evidence access. It
does define the comparison rules a key value is checked with (section 7), because
a key that cannot be compared is not a key.

## 2. Files, and who sees what

```
data/eval/cases/<set_id>/cases.jsonl        answerer inputs
data/eval/cases/<set_id>/keys.jsonl         evaluator only, never sent
data/eval/cases/<set_id>/manifest.json      counts, splits, corpus binding
```

**`cases.jsonl` carries only what a real user would have**: the question, and any
evidence reference the user explicitly has in view.

**`keys.jsonl` is evaluator-held**: tier, required evidence, answer key, split and
generator record. The answering path never loads it. The required evidence IDs
are here rather than in the public file because they are exactly what default
retrieval is supposed to find. Publishing them would turn the retrieval
measurement into a lookup, and publishing the tier would hand over the answer to
every Tier 3 case.

### 2.1 What each retrieval mode receives

| Mode (`DECISIONS.md` #27) | Answerer receives | How |
|---|---|---|
| Oracle-record | `question`, `context.evidence_ids`, and the projected records for `required_evidence_ids`, in key order | The harness calls C2 `Corpus.evidence_for(key)` |
| Default | `question`, `context.evidence_ids` | The system under test retrieves through C2's read path |
| No-record | `question`, `context.evidence_ids` | Nothing is supplied and retrieval is disabled |

A context ID is a reference string. Its record content arrives only through
oracle supply or retrieval. Evidence a refusal declares absent (section 6) is
never supplied, because it does not exist. Tier, answer key and generator record
are never supplied in any mode.

**Context is not a hint channel.** A context ID is legitimate only where the user
would really hold that reference: a record selected in the interface, or an ID
quoted in the question. Each generator template declares whether it supplies
context. Because context and required evidence can legitimately overlap, the
manifest reports, per tier, the share of cases whose required evidence is
contained in their context, so default-mode results are read with that overlap
in view.

## 3. Case fields

**Answerer inputs, `cases.jsonl`.** No other field is permitted.

| Field | Meaning |
|---|---|
| `case_id` | Stable identifier, unique in the set, never reused after deletion |
| `question` | The question as a user would ask it, one sentence |
| `context` | Optional. `{"evidence_ids": [...]}`: references the user explicitly holds. Omitted when there are none |

**Evaluator only, `keys.jsonl`**

| Field | Meaning |
|---|---|
| `case_id` | Join key |
| `tier` | 1, 2 or 3, per section 4 |
| `required_evidence_ids` | Evidence that must resolve in the declared corpus and that the answer or the refusal framing rests on, in order. May be empty only for a refusal |
| `answer_key` | Section 5 or section 6. Exactly one per case |
| `split` | `dev` or `holdout`, assigned at freeze |
| `generator` | `{"template", "template_version", "params"}`, or `{"template": "hand_authored", "note"}` |
| `difficulty` | `{"records", "hops"}`, a description rather than a claim about hardness |
| `author`, `created` | Who wrote it and when |

**`manifest.json`** records `set_id`, `c1_version`, the `corpus_id` it was
validated against, counts by tier and split, the number of hand-authored cases,
and the context overlap share by tier. At freeze it also records the sha256 of
both case files (section 9).

Absent evidence never appears in `context` or `required_evidence_ids`. It is
declared inside a refusal boundary, where the validator confirms it is absent.

## 4. Tiers

| Tier | Definition | Count |
|---|---|---|
| 1 | Answerable from one record | 30 |
| 2 | Answerable, needs several records or one aggregate | 15 |
| 3 | Not answerable from the declared corpus, or not permitted by policy. Correct behaviour is refusal | 15 |

Tier is a property of the case against the **declared evaluation corpus**, fixed
at freeze. It does not change per run.

## 5. Answer keys for answerable cases

```json
{"kind": "answer",
 "derivation": {"op": "<operation>", "...": "parameters"},
 "answer_type": "number | string | boolean | null | set | mapping | table",
 "value": "<expected answer>",
 "compare": {}}
```

Template showing shape only; section 11 has complete keys. `derivation` states how the expected answer follows from the required evidence,
using exactly one operation from the closed list below. It is data read by the
validator, not code: there is no expression language, no chaining, and no way for
a case to run a script. A question needing more than one operation needs a new
aggregate script under C2, reviewed like any other evidence producer.

**Evidence shape and answer shape are separate.** An aggregate's `value_kind`
(C2 §4) describes the evidence. `answer_type` describes the answer, and is the
type of `value`. A table can answer with a string.

**A present null is an answer; a missing field is not.** A field that C2 allows
to be null and that is present with `null` gives `answer_type: "null"` and
`value: null`. A field absent from a record cannot be read by an answer key: the
case is invalid, unless it is written as a refusal over a legitimately absent
field (section 6.1).

### 5.1 Operations

| Op | Tier | Parameters | Result `answer_type` |
|---|---|---|---|
| `field` | 1 | `evidence_id`, `path` | The field's value type: `number`, `string`, `boolean` or `null`; `set` for a list of strings |
| `fields` | 1 | `evidence_id`, `paths` | `mapping` from path to value |
| `collect` | 2 | `evidence_ids` (two or more), `path` | `mapping` from evidence ID to value |
| `agg_value` | 2 | `evidence_id` | `number` or `string` for a scalar; `mapping` or `table` otherwise |
| `mapping_get` | 2 | `evidence_id`, `key` | `number` |
| `table_select` | 2 | `evidence_id`, `where`, `return_column` | The cell's type |
| `table_argmax`, `table_argmin` | 2 | `evidence_id`, `where`, `value_column`, `return_column` | The cell's type |

**Operations select; they never compute.** Every value a key holds is a value
already present in the projected required evidence. `table_argmax` and
`table_argmin` compare numbers but return an existing cell. There is no sum,
count, mean or difference operation, because C2's number check permits only
numbers present in the evidence (C2 §7): a correct answer of 29 computed from
rows of 12 and 17 would fail grounding. A question whose answer is a computed
number needs an aggregate that carries that number as a declared scalar, mapping
value or column, produced and reproduced under C2 (C2 acceptance check 23).

**Cardinality**

| Op | Must match | Case invalid when |
|---|---|---|
| `field`, `fields`, `collect` | Every record read carries every path | A path is absent from a record read. A present null is not absent |
| `agg_value` | The whole value | Never on cardinality. An empty table answers as an empty `table` |
| `mapping_get` | Exactly one key | The key is absent |
| `table_select` | Exactly one row | Zero rows, or more than one |
| `table_argmax`, `table_argmin` | One or more rows | Zero rows; a tie for the extreme value; a null or non-numeric `value_column` cell in a matched row |

- `field`, `fields` and `collect` read decision or trace records. The `agg_`,
  `mapping_` and `table_` operations read one aggregate of the matching
  `value_kind`.
- `path` is a dotted field name that C2 projects for that record type, such as
  `regime.vol_flag`. It must name a scalar or a list of strings; list-of-object
  fields such as a trace's `conditions` are not readable by a key.
- `where` is equality on declared columns only, as `{"column": scalar}`. `{}`
  selects every row.
- The evidence IDs a derivation reads must equal `required_evidence_ids` as a
  set: none missing, none extra.

### 5.2 Answers resting on several records

A Tier 2 answer that needs several records uses `collect`, and the key holds
every record's value keyed by evidence ID. A question about a count, a rate, a
total or a ranking across many records is answered from an aggregate instead, so
the arithmetic is done once, by a reproducible script, and never by a case.

## 6. Refusal keys

One representation. The boundary and its review live inside `answer_key`; there
is no separate top-level boundary field.

```json
{"kind": "refusal",
 "boundary": {"kind": "missing_evidence | out_of_policy", "...": "per kind",
              "review": {"...": "section 6.3"}},
 "must_not_assert": ["claims that make an answer wrong even if it refuses"]}
```

Partial templates in this section show shape only. Section 11 has complete keys.

### 6.1 `missing_evidence`

`absent` is non-empty. Each entry takes exactly one of three forms:

| Absence | Entry | Verified by |
|---|---|---|
| A part the manifest declares not exported | `{"evidence_id", "part", "expected_error": "CorpusIncomplete"}` | `Corpus.get` raises `CorpusIncomplete` |
| A record not in an exported part | `{"evidence_id", "expected_error": "MissingEvidence"}` | `Corpus.get` raises `MissingEvidence` |
| A field legitimately absent from a record that exists | `{"evidence_id", "path", "absence": "conditional_field"}` | `Corpus.get` succeeds; `path` is conditional in C2 §6; its presence condition does not hold **for this record**; and `path` is absent from `project()` |

- Part and record entries name IDs that appear in neither `context` nor
  `required_evidence_ids`. A conditional-field entry names a record that exists,
  so its ID also appears in `required_evidence_ids`.
- Naming an absent ID or path is safe here because the key declares it absent and
  the validator confirms that absence. An intended absence cannot be confused with
  a broken reference.
- **A required field missing from a record is not a boundary**, whether it is
  unconditionally required or required because its condition holds on that
  record. C2's loader raises `CorpusMalformed` for it (C2 §6), and **`CorpusMalformed` is never a
  boundary**: it invalidates the case set (C2 §2).
- **A present null is not an absence.** A field present with `null` is answerable
  with a null answer (section 5).

### 6.2 `out_of_policy`

```json
{"kind": "out_of_policy", "policy_category": "counterfactual",
 "rule": "no outcomes under settings the system did not run",
 "review": {"...": "section 6.3"}}
```

- `policy_category` is one of `advice`, `recommendation`, `strategy_ranking`,
  `counterfactual`. `rule` states the boundary in one sentence.
  **[pending: stable rule references from the written policy document, which
  does not exist yet.]**
- There is no `absent` field. The evidence may exist in full; the boundary is
  policy, not a gap.

### 6.3 Boundary review

**Absence is verified mechanically. Unanswerability is a reviewed judgment.**
Corpus checks prove that each `absent` entry is absent. They cannot prove that no
other evidence answers the question: the same candidate has records under other
systems, an aggregate may carry the fact, and a permitted read may reach it. Every
refusal key therefore carries a review:

```json
{"reviewer": "name", "reviewed_on": "YYYY-MM-DD",
 "corpus_id": "00000000-00000000-01", "read_surface": "c2_read_v1",
 "finding": "why no other permitted evidence settles the question"}
```

- For `missing_evidence`, the reviewer confirms against the declared corpus and
  the permitted read surface that no other record, trace, aggregate or read
  settles the question.
- For `out_of_policy`, the reviewer confirms the question falls in the declared
  category.
- `read_surface` names the permitted reads. For milestone M2 that is C2's loader
  and projection (C2 §8); `c2_read_v1` is a placeholder name.
  **[pending: the MCP tool surface, once it exists, is a new `read_surface`
  value and needs new reviews.]**
- The review binds to one `corpus_id`. A new corpus needs a new review and a new
  set (section 9).
- Who may review, and whether the reviewer must differ from the author, is open
  (section 12).

For both kinds, `must_not_assert` is non-empty, and `required_evidence_ids` lists
evidence that exists and frames the case, such as the record a user selected. It
may be empty.

## 7. Comparison rules

These rules compare a key's `value` with the value the validator derives, and are
the rules the harness's mechanical checks apply to extracted answers.

| Type | Rule | Required in `compare` |
|---|---|---|
| number | Absolute difference at most `tolerance`. NaN and infinity are not permitted in keys | `tolerance`, including 0. Counts use 0 |
| string | Exact and case-sensitive, no trimming or normalisation. Dates and timestamps are compared as the evidence string (C2 §7) | Nothing |
| boolean | Exact | Nothing |
| null | Matches only null. A number, string or boolean never matches null, and null never matches an absent value | Nothing |
| set | Elements are strings. Duplicates in a key are invalid; order is ignored. Sets must be equal: a missing member or any extra member fails | `match: "exact"` |
| mapping | Keys are strings, and key sets must be identical. Values compared by their own type; a list-of-strings value compares as a set | `match: "exact"`, plus `tolerance` if any value is a number |
| table | Only `columns` are compared. Rows are matched by `key_columns`, which must be unique on both sides. Row counts must match. Row order is ignored unless `ordered` is `true`. Cells compared by their own type | `columns`, `key_columns`, and a `tolerance` object with an entry for each numeric column |

**Only exact matching is defined for milestone M2.** `match` must be `"exact"`;
any other value is invalid. The former `contains` rule is removed: a subset rule
accepts unsupported extra members, so it does not implement "give one valid
reason". A question with several recorded reasons asks for all of them.

`compare` is `{}` where no parameter applies. Keys record what a correct answer
contains, not the wording it uses.

## 8. Answerable is not the same as available

| Situation | Case status | What it means |
|---|---|---|
| Evidence withheld, as in no-record mode | Unchanged | An evaluation condition. A refusal is the behaviour measured |
| Retrieval returns nothing although the corpus holds the evidence | Unchanged | A retrieval failure, attributed to the system under test |
| A context or required ID does not resolve | Case invalid | A corpus or case defect, fixed rather than scored |
| An answer key reads a path absent from a record | Case invalid | Fixed, or rewritten as a conditional-field refusal if the absence is legitimate for that record and the review supports it |
| The corpus lacks a part, record or legitimately absent field, the key declares that absence, and the review finds nothing else settles the question | Tier 3 | The refusal is correct |
| The corpus raises `CorpusMalformed`, including a missing required field | Case set invalid | A bug, never scored |

C1 fixes the tier. C2 keeps the failure situations distinguishable. The harness
decides what each one scores.

## 9. Counts and splits

Sixty cases for milestone M2: 30 at Tier 1, 15 at Tier 2, 15 at Tier 3.

| Split | Tier 1 | Tier 2 | Tier 3 | Total |
|---|---:|---:|---:|---:|
| Development | 20 | 10 | 10 | 40 |
| Held out | 10 | 5 | 5 | 20 |

Splits are assigned at freeze and recorded in `keys.jsonl` and the manifest.
Held-out cases are not opened during prompt or retrieval iteration, and results
are reported for the two splits separately. The capstone target of 200 cases is
out of scope for milestone M2.

**Set identity.** A frozen set's files are never edited. At freeze the manifest
records the sha256 of `cases.jsonl` and `keys.jsonl`. Any later change produces a
new `set_id`, **even when every expected value stays equal**, including a change
to:

- the corpus binding (`corpus_id`),
- the manifest,
- any case line or key,
- any evidence reference: `context`, `required_evidence_ids`, `absent`, or a
  review's `corpus_id`.

The new set re-runs every check in section 10 against its declared corpus,
including new boundary reviews. The original set, its manifest and any results
reported against it are preserved unchanged.

## 10. Validation

**Per object**, from one line or file alone:

1. A `cases.jsonl` line has `case_id`, `question` and optionally `context`, and
   nothing else.
2. A `keys.jsonl` line has every required field, and `tier` is 1, 2 or 3.
3. Key kind matches tier: Tier 1 uses `answer` with `field` or `fields`; Tier 2
   uses `answer` with any other operation in section 5.1; Tier 3 uses `refusal`.
4. An `answer` key names an operation in section 5.1 with all its parameters.
   `answer_type` is a listed type, matches the type of `value`, and is a result
   type the operation can produce. `compare` carries every parameter section 7
   requires, and any `match` is `"exact"`.
5. A derivation's evidence IDs equal `required_evidence_ids` as a set.
6. A `refusal` key has exactly one boundary kind, a non-empty `must_not_assert`,
   and a complete `review` with a non-empty `finding`. For `missing_evidence`: a
   non-empty `absent` whose entries each take exactly one form from section 6.1.
   For `out_of_policy`: a listed `policy_category` and a `rule`.
7. Every evidence ID is well formed against C2 §3. Part and record absence IDs
   appear in neither `context` nor `required_evidence_ids`; conditional-field
   absence IDs appear in `required_evidence_ids`.
8. The manifest is schema valid.

**Whole case set**:

9. `case_id` is unique in each file. Every case has exactly one key and every key
   has exactly one case: no duplicates and no orphans.
10. Counts match section 9, the split is stratified by tier, and the manifest
    counts match the files.
11. No public field contains key content, a tier, or an evidence ID other than
    that case's own context IDs.
12. No two cases share the same question and context.
13. The manifest's context overlap shares match the files.
14. For a frozen set, the files' sha256 values equal those in its manifest. A
    mismatch under the same `set_id` invalidates the set (section 9).

**Against the declared corpus**:

15. The manifest's `corpus_id`, and every review's `corpus_id`, match the loaded
    corpus.
16. Every `context` and `required_evidence_ids` entry resolves without error.
17. Every part or record absence raises exactly its declared error. Every
    conditional-field absence resolves its record without error, names a
    conditional path in C2 §6, evaluates that path's presence condition on this
    record and finds it does not hold, and finds the path absent from the
    projected record. A path merely listed as conditional is not enough. Any
    `CorpusMalformed` invalidates the whole case set.
18. Every `path` a derivation reads is projected by C2 and present on each record
    read. A present null counts as present.
19. **Values are independently derived.** The validator applies the derivation
    to the projected evidence with its own operation interpreter, applying the
    cardinality rules in section 5.1, and the result must match the key's `value`
    under section 7. Valid field names and shapes are not enough. The validator
    does not call the answering path or reuse generator code to derive values.
20. **Keys select; they do not compute.** Every number in a key's `value` is
    permitted by C2 §7 step 4 against the projected required evidence. A key
    holding a number the evidence does not carry is invalid (C2 acceptance
    check 23).
21. Every aggregate a key reads passes C2 acceptance check 22: its script, at its
    version and arguments, reproduces its value over the corpus.
22. **Generator replay is reproducible derivation.** Running a template at its
    version with its parameters regenerates the same case line and key. A
    read-only derivation does not make a false assertion true, since the fact was
    already recorded, so there is no requirement that assertions fail before the
    solution runs. Hand-authored cases are exempt from replay and counted in the
    manifest. **[pending: PRD §9 still describes that pre-solution check.]**
23. A refusal about a non-event at a timestamp is checked against the corpus: no
    decision record exists for that system and timestamp.

**What the checks do not establish.** Checks 17 and 23 verify declared absences.
They do not show that a question is unanswerable. That judgment is the boundary
review in section 6.3, which is recorded and bound to the corpus but is not a
mechanical check.

A case set that fails any whole-set or corpus check, or lacks a review on any
refusal key, is not usable for a reported result.

## 11. Examples

Each case is one JSON line in its file; lines are wrapped here. The IDs use a
syntactically valid placeholder corpus `00000000-00000000-01` and placeholder
trade IDs, and resolve to nothing. Real `trade_id` values are UUIDs. Reviewer
names are placeholders. Every example describes a situation the registered
strategies and simulator produce today, and reads only fields that C2 §6
projects; none reads `risk.position_size`, the threshold window
or a computed number. Section 12 lists which examples depend on simulator
corrections.

**Tier 1, one field, context held by the user**

```json
{"case_id": "t1-0007", "question": "Why was this entry rejected?",
 "context": {"evidence_ids": ["dec:00000000-00000000-01:M2:trade_00123"]}}
```

```json
{"case_id": "t1-0007", "tier": 1,
 "required_evidence_ids": ["dec:00000000-00000000-01:M2:trade_00123"],
 "answer_key": {"kind": "answer",
   "derivation": {"op": "field",
     "evidence_id": "dec:00000000-00000000-01:M2:trade_00123",
     "path": "decision_reason_codes"},
   "answer_type": "set", "value": ["REGIME_PERMITS", "SQ_BELOW_THRESHOLD"],
   "compare": {"match": "exact"}},
 "split": "dev",
 "generator": {"template": "rejection_reason", "template_version": "v1",
   "params": {"system": "M2", "gate": "signal_quality"}},
 "difficulty": {"records": 1, "hops": 1},
 "author": "example", "created": "2026-09-16"}
```

**Tier 1, several fields of one record: why size was halved**

```json
{"case_id": "t1-0011", "question": "Why was the size of this trade halved?",
 "context": {"evidence_ids": ["dec:00000000-00000000-01:M1:trade_00456"]}}
```

```json
{"case_id": "t1-0011", "tier": 1,
 "required_evidence_ids": ["dec:00000000-00000000-01:M1:trade_00456"],
 "answer_key": {"kind": "answer",
   "derivation": {"op": "fields",
     "evidence_id": "dec:00000000-00000000-01:M1:trade_00456",
     "paths": ["decision", "risk.size_multiplier", "regime.vol_flag"]},
   "answer_type": "mapping",
   "value": {"decision": "reduced", "risk.size_multiplier": 0.5,
             "regime.vol_flag": "high"},
   "compare": {"match": "exact", "tolerance": 0}},
 "split": "dev",
 "generator": {"template": "regime_size_reduction", "template_version": "v1",
   "params": {"system": "M1"}},
 "difficulty": {"records": 1, "hops": 1},
 "author": "example", "created": "2026-09-16"}
```

**Tier 2, table evidence with a string answer**

```json
{"case_id": "t2-0003",
 "question": "Which gate rejected the most M2 candidates in 2019Q3?"}
```

```json
{"case_id": "t2-0003", "tier": 2,
 "required_evidence_ids": ["agg:00000000-00000000-01:rejections_by_gate@v1:9f12ab"],
 "answer_key": {"kind": "answer",
   "derivation": {"op": "table_argmax",
     "evidence_id": "agg:00000000-00000000-01:rejections_by_gate@v1:9f12ab",
     "where": {"quarter": "2019Q3"}, "value_column": "rejections",
     "return_column": "gate"},
   "answer_type": "string", "value": "regime", "compare": {}},
 "split": "holdout",
 "generator": {"template": "top_rejecting_gate", "template_version": "v1",
   "params": {"system": "M2", "quarter": "2019Q3"}},
 "difficulty": {"records": 1, "hops": 2},
 "author": "example", "created": "2026-09-16"}
```

**Tier 2, several records**

```json
{"case_id": "t2-0005",
 "question": "What regime did the model assign to each of these two trades?",
 "context": {"evidence_ids": ["dec:00000000-00000000-01:M1:trade_00456",
                              "dec:00000000-00000000-01:M1:trade_00789"]}}
```

```json
{"case_id": "t2-0005", "tier": 2,
 "required_evidence_ids": ["dec:00000000-00000000-01:M1:trade_00456",
                           "dec:00000000-00000000-01:M1:trade_00789"],
 "answer_key": {"kind": "answer",
   "derivation": {"op": "collect",
     "evidence_ids": ["dec:00000000-00000000-01:M1:trade_00456",
                      "dec:00000000-00000000-01:M1:trade_00789"],
     "path": "regime.label"},
   "answer_type": "mapping",
   "value": {"dec:00000000-00000000-01:M1:trade_00456": "uptrend",
             "dec:00000000-00000000-01:M1:trade_00789": "choppy"},
   "compare": {"match": "exact"}},
 "split": "dev",
 "generator": {"template": "regime_labels_for_selection", "template_version": "v1",
   "params": {"system": "M1", "n": 2}},
 "difficulty": {"records": 2, "hops": 1},
 "author": "example", "created": "2026-09-16"}
```

**Tier 3, missing evidence in a decisions-only corpus**

```json
{"case_id": "t3-0004",
 "question": "Why did B2 not propose a trade at 10:35 on 2021-03-04?"}
```

```json
{"case_id": "t3-0004", "tier": 3,
 "required_evidence_ids": [],
 "answer_key": {"kind": "refusal",
   "boundary": {"kind": "missing_evidence",
     "absent": [{"evidence_id": "trace:00000000-00000000-01:B2:3:2021-03-04T10:35:00-05:00",
                 "part": "traces", "expected_error": "CorpusIncomplete"}],
     "review": {"reviewer": "example", "reviewed_on": "2026-09-16",
       "corpus_id": "00000000-00000000-01", "read_surface": "c2_read_v1",
       "finding": "No decision record exists for B2 at that timestamp, the corpus exports no traces, and no aggregate reports rule conditions per bar"}},
   "must_not_assert": ["a rule condition that failed at that bar"]},
 "split": "dev",
 "generator": {"template": "non_event_without_traces", "template_version": "v1",
   "params": {"system": "B2"}},
 "difficulty": {"records": 0, "hops": 0},
 "author": "example", "created": "2026-09-16"}
```

**Tier 3, field legitimately absent from an existing record**

M1 permits few candidates, so M2 records rejected by the regime gate are common
in a historical export. The regime gate runs first in `CompositeGate`, so on
those records the signal-quality model never scores the candidate and C2 §6
requires the `signal_quality` fields to be absent.

```json
{"case_id": "t3-0007",
 "question": "What signal-quality score did M2 give this candidate?",
 "context": {"evidence_ids": ["dec:00000000-00000000-01:M2:trade_00321"]}}
```

```json
{"case_id": "t3-0007", "tier": 3,
 "required_evidence_ids": ["dec:00000000-00000000-01:M2:trade_00321"],
 "answer_key": {"kind": "refusal",
   "boundary": {"kind": "missing_evidence",
     "absent": [{"evidence_id": "dec:00000000-00000000-01:M2:trade_00321",
                 "path": "signal_quality.p_profit", "absence": "conditional_field"}],
     "review": {"reviewer": "example", "reviewed_on": "2026-09-16",
       "corpus_id": "00000000-00000000-01", "read_surface": "c2_read_v1",
       "finding": "The M2 record carries REGIME_BLOCKS and no SQ_ code, so no score was computed; the B2 and M1 records for this candidate never carry signal_quality fields, and no aggregate reports per-candidate scores"}},
   "must_not_assert": ["a signal-quality score for this candidate",
                       "that the candidate scored below the threshold"]},
 "split": "dev",
 "generator": {"template": "sq_score_after_regime_block", "template_version": "v1",
   "params": {"system": "M2"}},
 "difficulty": {"records": 1, "hops": 1},
 "author": "example", "created": "2026-09-16"}
```

A missing-field refusal built on `regime.label: null` is not a historical case:
the registered strategies never propose a candidate at a bar without a feature
row (C2 §6, reachability note). Such a record exists only as a constructed loader
fixture (C2 acceptance check 25) and does not belong in an evaluation case set.

**Tier 3, out of policy**

```json
{"case_id": "t3-0012",
 "question": "Would this trade have worked with a tighter stop?",
 "context": {"evidence_ids": ["dec:00000000-00000000-01:M2:trade_00123"]}}
```

```json
{"case_id": "t3-0012", "tier": 3,
 "required_evidence_ids": ["dec:00000000-00000000-01:M2:trade_00123"],
 "answer_key": {"kind": "refusal",
   "boundary": {"kind": "out_of_policy", "policy_category": "counterfactual",
     "rule": "no outcomes under settings the system did not run",
     "review": {"reviewer": "example", "reviewed_on": "2026-09-16",
       "corpus_id": "00000000-00000000-01", "read_surface": "c2_read_v1",
       "finding": "The question asks for the outcome under a stop the system did not use"}},
   "must_not_assert": ["an outcome under a different stop"]},
 "split": "dev",
 "generator": {"template": "counterfactual_stop", "template_version": "v1",
   "params": {"system": "M2"}},
 "difficulty": {"records": 1, "hops": 0},
 "author": "example", "created": "2026-09-16"}
```

## 12. Pending assumptions and dependencies

| # | Assumption | Depends on |
|---|---|---|
| A1 | Trace IDs take C2's form, so `absent` entries and trace derivations can name a bar | C2 Q1 |
| A2 | Scalar, mapping and table cover every aggregate, section 5.1's selection-only operations cover every planned Tier 2 answer, and every total or rate a case needs is a declared aggregate value | C2 Q2 |
| A3 | Every path a key reads is projected with the presence rule in C2 §6, including `regime.vol_flag` | C2 Q3 |
| A4 | `risk.position_size` and the threshold window exist before any key reads them | C2 Q4 |
| A5 | `out_of_policy` rules gain stable references | The written policy document |
| A6 | PRD §9's description of case verification matches section 10 check 22 | A PRD revision |
| A7 | Who may perform boundary reviews, and whether the reviewer must differ from the author | Henry and Jacky |
| A8 | The permitted read surface for reviews stays C2's loader and projection until the MCP tools exist | The tool surface |

**Simulator correction dependency.** The trading simulator correction plan is a
draft proposal, not approved or implemented (C2 §5.3). Keys and reviews are valid
only against the corpus they were validated on, and the manifest binds that
`corpus_id`. If corrections are approved, implemented and records re-exported,
the result is a new corpus. Binding a case set to it produces a new `set_id` even
if every expected value is unchanged (section 9); every check and review re-runs,
and the original set is preserved.

- **t1-0007, t1-0011, t2-0003.** The fact types exist today, but whether a given
  candidate is rejected or reduced, and how many rejections a gate has per
  quarter, can change: corrected fills and exits change later position
  conflicts, sizing, halts and M2's fitted thresholds.
- **t2-0005.** Regime labels come from price-derived features and a model fitted
  on price-derived labels, which execution does not touch, so they are expected
  to be stable. The case is still re-validated.
- **t3-0007.** Whether a given M2 record is a regime rejection depends only on
  the regime model, but which records exist and M2's trained folds can change
  with corrections. The absence and its review are re-checked.
- **t3-0004, t3-0012.** No dependency on execution behaviour.
- **No key may read the `outcome` block or any reason code missing from the
  corpus manifest's `reason_codes`.**

None of these assumptions is settled here, and none assigns work to anyone.

## 13. Freezing

C1 and C2 freeze together, by explicit agreement between Henry and Jacky, after
the C2 questions are answered. Reviewing without objection is not a freeze. A
frozen case set changes only by becoming a new set (section 9).
