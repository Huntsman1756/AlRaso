"""Spatial facts: lat/lon -> ALL applicable scopes (discovery §F, Spike B).

SpatialProvider CONTRACT (what every implementation must guarantee):

  * resolve(lat, lon) returns EVERY scope whose area contains the point
    (multi-scope hits are the norm: park + sector + …);
  * the resolver MUST NOT depend on the returned order (it canonicalises);
  * implementations must define boundary/hole/multipolygon semantics.

Two implementations with DIFFERENT guarantees:

  * InMemorySpatialProvider — pure-Python even-odd ray casting, zero deps.
    SCOPE: fixtures, tests and CLI demo ONLY. Semantics:
      - each supplied ring is an independent polygon part (multipolygon as a
        union of parts; nested-ring holes are NOT supported);
      - boundary points: even-odd ray-cast result is undefined-typical of the
        raster-free approximation — DO NOT rely on edges;
      - parent_scope is informational (stored separately): containment of a
        parent in a child is NOT computed here.
    It is engineering scaffolding, NOT a legally-reviewed GIS, and no parity
    with PostGIS is claimed.

  * PostGISSpatialProvider — production TARGET. PostGIS = spatial authority
    (ST_Intersects, SRID 4258, valid polygons, holes, geodesic-safe edges).
    No functional test exists yet (needs a live DB), so PostGIS remains the
    documented spatial target, not a validated implementation.

Shapely is deliberately NOT added: no local test has demonstrated a need
PostGIS does not cover, and M1 is explicitly no-map.

Legality never resolves here: ALL hits flow into the resolver, which
COMPOSES them (M1 remediation F03 — the old _pick_scope semantics is gone).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SpatialFactsError(Exception):
    """Provider failure; the resolver maps it to UNDETERMINED (fail-closed)."""


@dataclass
class ScopeHit:
    scope_id: str
    official_name: str
    scope_type: str

    def as_dict(self) -> dict[str, str]:
        return {"scope_id": self.scope_id, "official_name": self.official_name,
                "scope_type": self.scope_type}


class SpatialFactsProvider(Protocol):
    def resolve(self, lat: float, lon: float) -> list[ScopeHit]:
        ...


def _point_in_ring(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class InMemorySpatialProvider:
    """Fixtures-only provider; see module docstring for exact semantics."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict] = {}

    def add_scope(self, scope_id: str, official_name: str, scope_type: str,
                  rings: list[list[tuple[float, float]]], parent: str | None = None) -> None:
        for ring in rings:
            if len(ring) < 3:
                raise SpatialFactsError(f"{scope_id}: ring needs >=3 points")
        self._scopes[scope_id] = {
            "official_name": official_name, "scope_type": scope_type,
            "rings": rings, "parent": parent,
        }

    def resolve(self, lat: float, lon: float) -> list[ScopeHit]:
        hits = [ScopeHit(sid, meta["official_name"], meta["scope_type"])
                for sid, meta in self._scopes.items()
                if any(_point_in_ring(lat, lon, ring) for ring in meta["rings"])]
        return sorted(hits, key=lambda h: h.scope_id)


def _pg_sql() -> str:
    # Kept as a template; %s params are bound by psycopg, never interpolated.
    return (
        "SELECT id, official_name, scope_type FROM spatial_scope "
        "WHERE geom IS " + ("NOT " + "NULL") + " "
        "AND ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4258))"
    )


class PostGISSpatialProvider:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._sql = _pg_sql()

    def resolve(self, lat: float, lon: float) -> list[ScopeHit]:  # pragma: no cover - needs PostGIS
        import psycopg  # type: ignore

        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(self._sql, (lon, lat)).fetchall()
        return [ScopeHit(r[0], r[1], r[2]) for r in rows]
