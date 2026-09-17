"""M10.2-B refresh core — snapshot store, canonicalizers, classifier.

Boundary: this package detects source/evidence change and emits review
artifacts. It never parses instruments into rules, never writes
``legal_rule_version``, never publishes, and never deletes evidence.
All classification is deterministic; live access lives only in
``tooling/m102_refresh_run.py`` (``--live``), never in tests.
"""
