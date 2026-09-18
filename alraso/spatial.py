"""Spatial facts: lat/lon -> ALL applicable scopes (discovery §F, Spike B).

SpatialProvider CONTRACT (what every implementation must guarantee):

  * resolve(lat, lon) returns EVERY scope whose area contains the point
    (multi-scope hits are the norm: park + sector + …);
  * the resolver MUST NOT depend on the returned order (it canonicalises);
  * implementations must define boundary/hole/multipolygon semantics.

Two implementations with DIFFERENT guarantees:

  * InMemorySpatialProvider — pure-Python even-odd ray casting, zero deps.
    SCOPE: fixtures, tests and CLI demo ONLY. Semantics:
      - geometry is a set of PARTS; each part is ``[exterior, *holes]``
        (GeoJSON Polygon semantics). A point is inside a scope iff it is
        inside at least one part's exterior and inside NONE of that part's
        holes. Interior rings (holes) are fully supported — never
        approximated or filled;
      - legacy ``rings=`` callers keep working: each ring becomes an
        independent exterior-only part (multipolygon as a union of parts);
      - BOUNDARY POLICY (preregistered in docs/validation/m8/M8-PREREG.md):
        a point lying within _EDGE_EPS degrees of any ring edge is
        AMBIGUOUS. The scope is still returned but flagged
        ``ScopeHit.on_boundary=True``. Consumers MUST NOT let a
        boundary-flagged hit alone support a favourable or unfavourable
        legal determination — it must degrade to UNDETERMINED (fail-closed).
        Non-flagged hits are definitive in/out;
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
from typing import Any, Protocol

# Boundary tolerance in degrees (~0.1 mm): only exact-edge coincidences and
# floating-point noise land inside it.  Larger buffers belong to dedicated
# uncertainty zones (e.g. Picos boundary_uncertainty rings), not to this eps.
_EDGE_EPS = 1e-9


class SpatialFactsError(Exception):
    """Provider failure; the resolver maps it to UNDETERMINED (fail-closed)."""


@dataclass
class ScopeHit:
    scope_id: str
    official_name: str
    scope_type: str
    on_boundary: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"scope_id": self.scope_id, "official_name": self.official_name,
                "scope_type": self.scope_type, "on_boundary": self.on_boundary}


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


def _on_edge(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    """True iff the point lies within _EDGE_EPS of any ring segment."""
    n = len(ring)
    for i in range(n):
        y1, x1 = ring[i]
        y2, x2 = ring[(i + 1) % n]
        # Degenerate segment: distance to the vertex.
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 == 0.0:
            d2 = (lon - x1) ** 2 + (lat - y1) ** 2
        else:
            t = ((lon - x1) * dx + (lat - y1) * dy) / seg2
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            px, py = x1 + t * dx, y1 + t * dy
            d2 = (lon - px) ** 2 + (lat - py) ** 2
        if d2 <= _EDGE_EPS * _EDGE_EPS:
            return True
    return False


def _ring_locate(lat: float, lon: float, ring: list[tuple[float, float]]) -> str:
    """Tri-state point/ring test: 'inside' | 'outside' | 'boundary'."""
    if _on_edge(lat, lon, ring):
        return "boundary"
    return "inside" if _point_in_ring(lat, lon, ring) else "outside"


def _part_locate(lat: float, lon: float, part: list[list[tuple[float, float]]]) -> str:
    """Tri-state point/part test for ``[exterior, *holes]``.

    inside  = inside exterior and inside no hole;
    outside = outside exterior, or strictly inside a hole;
    boundary= on the exterior edge or on any hole edge (ambiguous).
    """
    ext = _ring_locate(lat, lon, part[0])
    if ext != "inside":
        return ext
    for hole in part[1:]:
        loc = _ring_locate(lat, lon, hole)
        if loc == "inside":
            return "outside"
        if loc == "boundary":
            return "boundary"
    return "inside"


def parts_from_geojson(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    """GeoJSON Polygon/MultiPolygon -> parts in (lat, lon) tuples.

    Polygon coordinates ``[ext, h1, ...]`` -> ``[[ext, h1, ...]]``;
    MultiPolygon ``[[ext, h1, ...], [ext2, ...]]`` -> same structure.
    Raises SpatialFactsError on anything else — never approximates.
    """
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        raw_parts = [coords]
    elif gtype == "MultiPolygon":
        raw_parts = coords
    else:
        raise SpatialFactsError(f"unsupported geometry type {gtype!r}")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise SpatialFactsError("geometry has no parts")
    parts = []
    for part in raw_parts:
        if not isinstance(part, list) or not part or len(part[0]) < 3:
            raise SpatialFactsError("part needs an exterior ring with >=3 points")
        parts.append([[(float(lat), float(lon)) for lon, lat in ring]
                      for ring in part])
    return parts


def parts_from_rings_latlon(
        rings: list[list[list[float]]]) -> list[list[list[tuple[float, float]]]]:
    """Legacy ``rings_latlon`` fixture form -> parts (each ring = own part)."""
    return [[[(float(lat), float(lon)) for lat, lon in ring]] for ring in rings]


def parts_from_parts_latlon(
        parts: list[list[list[list[float]]]]
) -> list[list[list[tuple[float, float]]]]:
    """``parts_latlon`` fixture form -> parts.  Structure mirrors GeoJSON
    Polygon/MultiPolygon but with (lat, lon) pairs: ``[[ext, h1, ...], ...]``."""
    if not isinstance(parts, list) or not parts:
        raise SpatialFactsError("parts_latlon must be a non-empty list")
    out = []
    for part in parts:
        if not isinstance(part, list) or not part or len(part[0]) < 3:
            raise SpatialFactsError("part needs an exterior ring with >=3 points")
        out.append([[(float(lat), float(lon)) for lat, lon in ring]
                    for ring in part])
    return out


class InMemorySpatialProvider:
    """Fixtures-only provider; see module docstring for exact semantics."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict] = {}

    def add_scope(self, scope_id: str, official_name: str, scope_type: str,
                  rings: list[list[tuple[float, float]]] | None = None,
                  parts: list[list[list[tuple[float, float]]]] | None = None,
                  parent: str | None = None) -> None:
        if rings is None and parts is None:
            raise SpatialFactsError(f"{scope_id}: rings or parts required")
        if rings is not None and parts is not None:
            raise SpatialFactsError(f"{scope_id}: pass rings OR parts, not both")
        if parts is None:
            parts = [[r] for r in (rings or [])]
        for part in parts:
            for ring in part:
                if len(ring) < 3:
                    raise SpatialFactsError(f"{scope_id}: ring needs >=3 points")
        self._scopes[scope_id] = {
            "official_name": official_name, "scope_type": scope_type,
            "parts": parts, "parent": parent,
        }

    def scope_ids(self) -> list[str]:
        """The complete catalog of scopes this provider can determine
        membership for. The resolver uses it to expose derived
        ``scope:<id>`` facts (True for hits, False for catalog misses);
        scopes outside the catalog stay unknown, never assumed absent."""
        return sorted(self._scopes)

    def resolve(self, lat: float, lon: float) -> list[ScopeHit]:
        hits = []
        for sid, meta in self._scopes.items():
            locs = [_part_locate(lat, lon, part) for part in meta["parts"]]
            if "inside" in locs:
                hits.append(ScopeHit(sid, meta["official_name"],
                                     meta["scope_type"], on_boundary=False))
            elif "boundary" in locs:
                hits.append(ScopeHit(sid, meta["official_name"],
                                     meta["scope_type"], on_boundary=True))
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
