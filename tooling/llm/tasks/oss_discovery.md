# Task: oss_discovery

Auxiliary worker for **finding open-source candidates**. Output is a *hint*, never evidence.

## How to call

```python
from tooling.llm.router import run_llm

result = run_llm("oss_discovery", OSS_DISCOVERY_PROMPT)
# result["response"] -> markdown or structured text
```

## Prompt template

```
You are a research assistant for an open-source reuse pass (OSS_REUSE_GATE).

Find real, existing open-source repositories that solve AT LEAST PART of the
following capability, for a Spain/EU outdoor + legal-compliance product
(bivouac/camping legality maps, MapLibre, PMTiles, offline).

CAPABILITY: <describe the capability, e.g. "offline MapLibre + PMTiles map
with protected-areas overlay and refuges/water POIs">

Requirements:
- Real repos that exist today (do not invent names or URLs).
- Prefer: recent code, permissive license (MIT/Apache/BSD), real production,
  CI, tests, data/provenance, automatic updates, Spain/EU relevance.
- For EACH candidate report:
  1. owner/repo
  2. license (from the repo's LICENSE/COPYING/SPDX)
  3. last commit activity (rough)
  4. what concrete part is reusable (name files/dirs)
  5. reuse class: ADOPT / ADAPT / COPY_PATTERN / REFERENCE_ONLY / REJECT
  6. one-line reason
- If you are unsure of a license, say LICENSE_UNKNOWN and mark REFERENCE_ONLY.

Return a compact markdown table. Do NOT write code. Do NOT claim any repo is
verified or evidence for legal purposes.
```

## Invariant

`OSS_DISCOVERY_OUTPUT != LEGAL_EVIDENCE`. A repo suggestion is a lead. Before any
adoption, the repo, its license, and its provenance must be verified against the
primary source (the repo itself), and any legal content must go through the
existing review pipeline.
