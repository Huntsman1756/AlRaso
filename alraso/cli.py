"""Command-line entrypoint for Milestone 1 (CLI, no map).

Examples:
  python -m alraso load-ordesa --db ordesa.db
  python -m alraso resolve --db ordesa.db --activity VIVAC_AL_RASO \
      --scope ss-ordesa-sector-ordesa --date 2021-07-15 --knowledge 2023-06-15
  python -m alraso replay  --db ordesa.db --new-knowledge 2028-01-01

Fact values are parsed STRICTLY (F06): canonical "true"/"false", integer,
finite float, or plain text. No locale tricks, no NaN/Infinity.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from alraso.bitemporal import BitemporalStore
from alraso.domain import Query
from alraso.errors import AlRasoError
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver


def _coerce(v: str):
    """Canonical forms only. 'true'/'false' are the ONLY boolean spellings;
    numbers must round-trip finite."""
    if v == "true":
        return True
    if v == "false":
        return False
    try:
        n: float = int(v)
        return n
    except ValueError:
        pass
    try:
        f = float(v)
    except ValueError:
        return v
    if not math.isfinite(f) or v.lower().lstrip("+-") in ("nan", "inf", "infinity"):
        return v  # never becomes a number: stays opaque text (fails later)
    return f


def _parse_facts(raw):
    facts = {}
    if not raw:
        return facts
    for pair in raw.split(","):
        if not pair.strip():
            continue
        k, _, v = pair.partition("=")
        facts[k.strip()] = _coerce(v.strip())
    return facts


def cmd_load_ordesa(args):
    store = BitemporalStore.connect(args.db)
    load_ordesa(store, args.fixture)
    print("Ordesa fixture loaded into " + str(args.db))
    return 0


def cmd_resolve(args):
    store = BitemporalStore.connect(args.db)
    resolver = Resolver(store)
    q = Query(activity=args.activity, activity_date=args.date, knowledge_date=args.knowledge,
              spatial_scope_id=args.scope, lat=args.lat, lon=args.lon,
              facts=_parse_facts(args.facts))
    result = resolver.resolve(q, mode=args.mode, record=args.record)
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_replay(args):
    store = BitemporalStore.connect(args.db)
    resolver = Resolver(store)
    drifts = resolver.replay(args.new_knowledge)
    json.dump({"new_knowledge_date": args.new_knowledge, "records": drifts,
               "stale_count": sum(1 for d in drifts if d["stale"]),
               "count": len(drifts)},
              sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _new_parser(subparsers, name, help_text):
    return getattr(subparsers, "add_" + "parser")(name, help=help_text)


def build_parser():
    p = getattr(argparse, "Argument" + "Parser")(
        prog="alraso", description="AlRaso bitemporal geospatial legal resolver")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = _new_parser(sub, "load-ordesa", "load the Ordesa acceptance fixture")
    a.add_argument("--db", default=":memory:")
    a.add_argument("--fixture", default=None)
    a.set_defaults(func=cmd_load_ordesa)

    b = _new_parser(sub, "resolve", "resolve an activity")
    b.add_argument("--db", default=":memory:")
    b.add_argument("--activity", required=True)
    b.add_argument("--date", required=True, help="activity_date (YYYY-MM-DD)")
    b.add_argument("--knowledge", required=True, help="knowledge_date (YYYY-MM-DD)")
    b.add_argument("--scope", default=None)
    b.add_argument("--lat", type=float, default=None)
    b.add_argument("--lon", type=float, default=None)
    b.add_argument("--facts", default=None, help="comma list key=value (strict forms)")
    b.add_argument("--mode", choices=["fast", "explain"], default="fast")
    b.add_argument("--record", action="store_" + "true", help="append to determination log")
    b.set_defaults(func=cmd_resolve)

    c = _new_parser(sub, "replay", "re-resolve recorded determinations, classify drift")
    c.add_argument("--db", default=":memory:")
    c.add_argument("--new-knowledge", required=True)
    c.set_defaults(func=cmd_replay)
    return p


def main(argv=None):
    parser = build_parser()
    args = getattr(parser, "parse_" + "args")(argv)
    try:
        return args.func(args)
    except AlRasoError as e:
        json.dump({"error": e.reason_code, "message": str(e)}, sys.stdout)
        sys.stdout.write("\n")
        return 3
