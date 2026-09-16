# C1: the case file

**Draft, not frozen. Written 2026-09-15.** Henry drafted this. It freezes
together with C2, when Henry and Jacky both agree both documents in writing.
Four assumptions in this draft depend on the C2 questions and are marked
**[pending C2 Qn]**. Changes after the freeze need a `DECISIONS.md` entry.

C1 defines the evaluation cases: what a case contains, what counts as a correct
answer, and how a case set is validated. It references evidence only through the
IDs defined in `C2_record_access.md`.

Naming: **trading M1 and M2** are the model rungs, **milestone M2** is the
September 28 deliverable, **E0 to E3, Oracle and Full** are answerers.

---

## 1. What C1 does and does not do

C1 says what each case asks, which evidence exists for it, and what a correct
answer contains. It does **not** define metrics, scoring formulas, prompts or
retrieval behaviour. The harness owns those, and C2 owns evidence access.

## 2. Files, and what the answerer may see

A case set is a directory with two files plus a manifest:

```
data/eval/cases/<set_id>/cases.jsonl         given to the answerer
data/eval/cases/<set_id>/keys.jsonl          evaluator only, never sent
data/eval/cases/<set_id>/manifest.json       counts, splits, corpus binding
```

`cases.jsonl` carries only what a user would have: `case_id`, `question`, and
`evidence_ids`. `keys.jsonl` carries the answer key, the tier, the split, the
refusal boundary and the generator record, joined by `case_id`.

**The tier lives in the keys file.** Telling the answerer a case is Tier 3 hands
it the answer, since the correct behaviour for Tier 3 is refusal. For the same
reason `keys.jsonl` is never loaded by the answering path, and the harness passes
only the public fields into a prompt.

## 3. Case fields

**Public, in `cases.jsonl`**

| Field | Meaning |
|---|---|
| `case_id` | Stable identifier, unique in the set, never reused after deletion |
| `question` | The question as a user would ask it, one sentence |
| `evidence_ids` | Evidence that **exists in the declared corpus and must resolve**, in the order the case intends |

**Evaluator only, in `keys.jsonl`**

| Field | Meaning |
|---|---|
| `case_id` | Join key |
| `tier` | 1, 2 or 3, per section 4 |
| `answer_key` | What a correct answer contains, per section 5 |
| `boundary` | Tier 3 only, per section 6 |
| `split` | `dev` or `holdout`, assigned at freeze |
| `generator` | How the case was produced: template name, solution steps, assertion steps |
| `difficulty` | `{records, hops}`, a description rather than a claim about hardness |
| `author`, `created` | Who wrote it and when |

**`evidence_ids` is not a list of what is missing.** It lists evidence that is
present. A Tier 3 case describes absent evidence in prose in `boundary`, never as
an ID, because an ID that does not resolve is indistinguishable from a broken
case.

## 4. Tiers

| Tier | Definition | Count |
|---|---|---|
| 1 | Answerable from one piece of evidence | 30 |
| 2 | Answerable, needs several records or a precomputed aggregate | 15 |
| 3 | Not answerable from the declared corpus, or not permitted by policy. Correct behaviour is refusal | 15 |

Tier is a property of the case against the **declared evaluation corpus**, fixed
at freeze. It does not change per run.

## 5. Answer keys

Four kinds. Exactly one per case, and the kind is fixed by tier.

**`lookup`**, Tier 1. One field of one record.

```json
{"kind": "lookup", "evidence_id": "dec:...", "field": "risk.size_multiplier",
 "value": 0.5, "tolerance": 0}
```

`tolerance` is mandatory and explicit, including zero. The field must be one C2
projects, so an answer can cite it.

**`set`**, Tier 1 or 2. An unordered set of labels or reason codes.

```json
{"kind": "set", "evidence_id": "dec:...", "field": "decision_reason_codes",
 "values": ["SQ_BELOW_THRESHOLD"], "match": "exact"}
```

`match` is `exact` or `contains`. Use `contains` only where the question asks for
one reason among several.

**`aggregate`**, Tier 2. The value comes from Jacky's aggregate script, cited
through its `agg:` evidence ID, and its shape follows C2's three value kinds.
**[pending C2 Q2: scalar, mapping and table are assumed to cover the five
aggregates.]**

```json
{"kind": "aggregate", "evidence_id": "agg:...", "value_kind": "mapping",
 "value": {"uptrend": 0.41, "choppy": 0.12}, "tolerance": 0.005}
```

For `table`, the key names the columns compared and permits row order to differ.
A Tier 2 key is never read off an answer: it is whatever the aggregate script
computed, which is why Jacky owns those scripts and the keys together.

**`refusal`**, Tier 3. See section 6.

Keys record what a correct answer must contain, not the wording it must use. How
a rubric grades the surrounding prose is the harness's business.

## 6. Refusal cases

```json
{"kind": "refusal", "boundary_kind": "missing_evidence",
 "missing": "no rule-state trace is recorded for that timestamp",
 "must_not_assert": ["a reason the bar produced no candidate"]}
```

Two boundary kinds, and a case declares exactly one:

- **`missing_evidence`.** The corpus cannot settle the question. The prose in
  `missing` names the evidence kind or field that is absent. Never an ID.
- **`out_of_policy`.** The corpus could settle it, or the question is not the kind
  we answer at all: investment advice, a recommendation, ranking one strategy
  against another, or speculation about what would have happened under different
  settings. The refusal is a policy decision, not an evidence gap.

A refusal case may still carry `evidence_ids`. "Why did nothing fire at 10:35"
can cite the trace that exists while the boundary is that no reason was recorded;
"should I lower the threshold" cites the record the user is looking at while the
boundary is policy.

`must_not_assert` lists claims that make an answer wrong even if it refuses in
form, which is how a hedged answer that still names a cause gets caught.

**An empty generator solution is not proof of unanswerability.** Every Tier 3
case states its boundary in words, and the reviewer checks that boundary against
the declared corpus and the policy document.

## 7. Answerable is not the same as available

Tier says whether the **declared corpus** can settle the question. What reaches
the answerer during one run is a separate matter, and the two must not be
conflated:

| Situation | Case tier | What it means |
|---|---|---|
| Evidence withheld deliberately, as in C2's no-record retrieval mode | Unchanged | An evaluation condition. A refusal is the behaviour being measured |
| Retrieval returns nothing although the corpus holds the evidence | Unchanged | A retrieval failure, attributed to the system under test |
| The corpus never contained an ID the case requires | Case is invalid | A corpus or case defect, fixed rather than scored |
| The corpus genuinely has no such evidence, and the case says so | 3 | The refusal is correct |

C1 fixes the tier. C2 keeps the three failure situations distinguishable. The
harness decides what each one scores.

## 8. Counts and splits

Sixty cases for milestone M2, 30 at Tier 1, 15 at Tier 2, 15 at Tier 3.

| Split | Tier 1 | Tier 2 | Tier 3 | Total |
|---|---:|---:|---:|---:|
| Development | 20 | 10 | 10 | 40 |
| Held out | 10 | 5 | 5 | 20 |

Splits are assigned at freeze and recorded in `keys.jsonl` and the manifest. Held-
out cases are not opened during prompt or retrieval iteration, and results are
reported for the two splits separately. Any later change to a case set is a new
`set_id`, not an edit, so a reported number always names the set it came from.

The capstone target of 200 cases is out of scope for milestone M2, and the counts
above are what the work plan funds.

## 9. Validation

**Per case**, mechanical, from the file alone:

1. Schema valid, required fields present, `case_id` unique in the set.
2. Key kind matches tier: Tier 1 uses `lookup` or `set`, Tier 2 uses `set` or
   `aggregate`, Tier 3 uses `refusal`.
3. `lookup` and `aggregate` carry an explicit `tolerance`.
4. `refusal` carries exactly one `boundary_kind` and non-empty `missing` or
   policy text.
5. `evidence_ids` is well formed against C2's ID grammar.
6. No answer key content appears in `cases.jsonl`.

**Per corpus**, requiring the declared evidence corpus:

7. Every `evidence_ids` entry resolves in that corpus, and the corpus's
   `corpus_id` is recorded in the case-set manifest.
8. Every field named by a `lookup` key exists on the cited record and is
   projected by C2.
9. Every `aggregate` key's cited `agg:` evidence exists and its `value_kind`
   matches.
10. Split counts match section 8, and the split is stratified by tier.
11. Generator solutions replay: applying the solution satisfies the assertions,
    and the assertions do **not** already hold before it, which is what stops a
    degenerate case.
12. No two cases share a question string over the same evidence.

A case set that fails any corpus check is not usable for a reported result.

## 10. Examples

Illustrative only. **The IDs below are made up and resolve to nothing**, and two
fields they use, `risk.position_size` and the threshold window, are not emitted
yet **[pending C2 Q4]**.

**Tier 1**

```json
{"case_id": "t1-0007",
 "question": "Why was the 2021-03-04 10:35 entry rejected?",
 "evidence_ids": ["dec:EXAMPLE:M2:trade_00123"]}
```

```json
{"case_id": "t1-0007", "tier": 1,
 "answer_key": {"kind": "set", "evidence_id": "dec:EXAMPLE:M2:trade_00123",
                "field": "decision_reason_codes",
                "values": ["SQ_BELOW_THRESHOLD"], "match": "exact"},
 "split": "dev"}
```

**Tier 2**

```json
{"case_id": "t2-0003",
 "question": "Which gate rejected the most candidates in the third quarter of 2019?",
 "evidence_ids": ["agg:EXAMPLE:rejections_by_gate@v1:EXAMPLE"]}
```

```json
{"case_id": "t2-0003", "tier": 2,
 "answer_key": {"kind": "aggregate", "evidence_id": "agg:EXAMPLE:rejections_by_gate@v1:EXAMPLE",
                "value_kind": "scalar", "value": "regime", "tolerance": 0},
 "split": "holdout"}
```

**Tier 3**

```json
{"case_id": "t3-0011",
 "question": "Would this trade have worked with a tighter stop?",
 "evidence_ids": ["dec:EXAMPLE:M2:trade_00123"]}
```

```json
{"case_id": "t3-0011", "tier": 3,
 "answer_key": {"kind": "refusal", "boundary_kind": "out_of_policy",
                "missing": "speculation about settings the system did not run",
                "must_not_assert": ["an outcome under a different stop"]},
 "split": "dev"}
```

## 11. Assumptions pending Jacky's C2 answers

| # | Assumption here | C2 question |
|---|---|---|
| A1 | Trace evidence IDs take C2's form, so a case can cite a bar where nothing happened | Q1 |
| A2 | Scalar, mapping and table cover every Tier 2 aggregate, so `aggregate` keys need no fourth shape | Q2 |
| A3 | Every field a `lookup` key can name is in C2's projected list | Q3 |
| A4 | `risk.position_size` and the threshold window exist by the time cases are written, or no case names them | Q4 |

None of these is settled here, and none of them assigns work to anyone.

## 12. Freezing

C1 and C2 freeze together, by explicit agreement between Henry and Jacky, after
the four C2 questions are answered. Reviewing without objection is not a freeze.
