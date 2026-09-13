"""AlRaso M10.1 pilot evidence pipeline.

Evidence-only: prepares reproducible ReviewPackets from official sources.
Never publishes rules, never infers PERMITTED from missing coverage.
Jurisdiction-agnostic: no ``if jurisdiction`` branching is allowed here —
source peculiarities live in ``pipeline/sources/*.profile.json``.
"""
