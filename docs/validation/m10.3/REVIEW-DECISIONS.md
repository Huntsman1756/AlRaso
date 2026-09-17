# M10.3 — ReviewDecision pipeline (human adjudication → publication)

The three M10.3 candidates (`discovery/evidence/m10.3-*/`) are
`REVIEW_REQUIRED` and non-publishable. The **only** legitimate route to
publication is an explicit human `ReviewDecision` artifact — a JSON file
that binds cryptographically to the exact case, the exact candidate fixture
and the exact evidence the reviewer claims to have reviewed.

## Artifact

Schema: `alraso/review-decision@1` (`schemas/alraso-review-decision-v1.schema.json`).
Required fields:

| Field | Meaning |
|---|---|
| `review_case_id` | must equal the case's `review_case_id` |
| `case_sha256` | sha256 of the canonical review_case.json — binds the decision to the exact case content |
| `candidate_fixture_sha256` | sha256 of the canonical candidate_fixture.json — required for `APPROVE`, binds approval to exact rule content |
| `decision` | `APPROVE` \| `REJECT` \| `EXTERNAL_REVIEW` |
| `reviewer.name` / `reviewer.reference` | real human identity + verifiable reference |
| `decided_at` | ISO-8601 timestamp |
| `reviewed_evidence` | map `key → sha256` covering the extract file (recomputed), the source artifact hash (`source:akn_sha256`/`source:pdf_sha256`, attestation binding for non-redistributed official bytes) and the geometry reference (recomputed) |
| `spatial_disposition` | `REVIEWED` \| `NOT_APPLICABLE` \| `INCOMPLETE` — `APPROVE` requires `REVIEWED` or `NOT_APPLICABLE` |
| `annotation` | reviewer's written basis for the decision |

## Owner workflow (per park)

```bash
# 1. Generate the skeleton (hashes pre-computed; human fields blank —
#    the skeleton is INVALID until a human fills them)
python tooling/review_decision_prepare.py \
    --case discovery/evidence/m10.3-aiguestortes/review_case.json \
    --candidate discovery/evidence/m10.3-aiguestortes/candidate_fixture.json \
    --repo-root . --out decision-aiguestortes.json

# 2. Human edits decision/reviewer/decided_at/spatial_disposition/annotation.

# 3. Validate (exit 0 = valid; reasons printed otherwise)
python -m alraso validate-decision \
    --decision decision-aiguestortes.json \
    --case discovery/evidence/m10.3-aiguestortes/review_case.json \
    --candidate discovery/evidence/m10.3-aiguestortes/candidate_fixture.json \
    --repo-root .

# 4. Publish (only ever succeeds on a valid APPROVE)
python -m alraso publish-reviewed \
    --decision decision-aiguestortes.json \
    --case discovery/evidence/m10.3-aiguestortes/review_case.json \
    --candidate discovery/evidence/m10.3-aiguestortes/candidate_fixture.json \
    --out alraso/resources/fixture_aiguestortes.json \
    --repo-root .
```

`REJECT` and `EXTERNAL_REVIEW` are valid terminal decisions that produce
**no** fixture. A tampered case, fixture or evidence file invalidates the
decision (`CASE_SHA256_MISMATCH`, `FIXTURE_SHA256_MISMATCH`,
`EVIDENCE_HASH_MISMATCH`). Deciding a case whose `reviewer_decision` is no
longer `PENDING` fails closed (`CASE_NOT_PENDING`).

## What this does NOT do

- It cannot create a valid `APPROVE` by itself — the human fields are the
  gate, and the artifact is only as trustworthy as the human who signs it.
- It does not modify the review case: after adjudication the human also
  records the outcome in `review_case.json:reviewer_decision` and
  `docs/validation/m10.3/M10.3-HUMAN-REVIEW.md`.
- `VERIFIED` here means "human-reviewed per this artifact"; `PUBLISHED`
  remains a release-time state.

Coverage/limitation unchanged: published rules only cover what the human
explicitly approved — absence of coverage is never permission.
