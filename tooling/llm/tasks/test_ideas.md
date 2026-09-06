# Task: test_ideas

Auxiliary worker to propose test cases / edge cases. It never writes the tests
itself into the repo; it only proposes them.

## How to call

```python
from tooling.llm.router import run_llm

result = run_llm("test_ideas", TEST_IDEAS_PROMPT)
```

## Prompt template

```
You propose test cases for a fail-closed geospatial legal resolver (AlRaso).

DOMAIN UNDER TEST:
<describe the unit/feature, e.g. "coverage classification for a point that is
VERIFIED / PARTIAL / UNKNOWN", or "the resolve pipeline for a rule that is
AUTHORIZATION_REQUIRED with an unverified condition">

Propose a list of concrete test cases, each with:
- a short name
- the input (setup / fixtures)
- the expected outcome
- why it matters (the invariant it guards)

Focus on edge cases:
- empty / missing / malformed input
- boundary values (polygon edge, hole, near-zero distance)
- conflicting or overlapping scopes
- a rule with missing provenance, or a heuristic mistaken for law
- temporal boundaries (effective_from / effective_to, recorded_at)
- NaN / infinities / negative coordinates

Return a compact markdown list. Do NOT write code.
```

## Invariant

`test_ideas` output is a suggestion. Tests are only authoritative once written
in the repo, run in CI, and passing.
