"""Load the Ordesa acceptance fixture into a bitemporal store.

The fixture ships INSIDE the package (alraso/resources/fixture_ordesa.json)
and is read via importlib.resources, so installed wheels work without a
checkout (M1 remediation F09). The discovery copy remains untouched as
historical evidence but is no longer a runtime dependency.

It is an acceptance fixture, not product data: it encodes only regimes
already verified in the discovery (RD 409/1995 permit -> D 16/2022
prohibition effective 2022-02-09) and carries no new legal conclusion.

Loading runs inside ONE store transaction (F07): a failure anywhere rolls
back the entire batch; a duplicate load fails atomically with IntegrityError
and no partial state.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from alraso.bitemporal import BitemporalStore


def load_fixture_json(path: str | Path | None = None) -> dict[str, Any]:
    """Fixture payload from an explicit path or from package resources."""
    if path is not None:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    ref = resources.files("alraso.resources").joinpath("fixture_ordesa.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def ingest_corpus(store: BitemporalStore, fx: dict[str, Any]) -> None:
    """One atomic use-case: documents, fragments, scopes, rules, relations."""
    with store.transaction():
        for d in fx.get("source_documents", []):
            store.add_source_document(d)
        for f in fx.get("legal_fragments", []):
            store.add_legal_fragment(f)
        for s in fx.get("spatial_scopes", []):
            store.add_spatial_scope(s)
        for v in fx.get("legal_rule_versions", []):
            store.add_rule_version(v)
        for r in fx.get("rule_relations", []):
            store.add_relation(r)


def load_ordesa(store: BitemporalStore, path: str | Path | None = None) -> dict[str, Any]:
    fx = load_fixture_json(path)
    ingest_corpus(store, fx)
    return fx
