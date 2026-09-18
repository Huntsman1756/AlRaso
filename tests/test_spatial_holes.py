"""P0 spatial correctness: interior rings (holes), multipolygon parts and the
preregistered boundary policy (docs/validation/m8/M8-PREREG.md).

Semantics under test:

  * a scope is a set of parts ``[exterior, *holes]``;
  * inside exterior AND inside no hole -> inside;
  * strictly inside a hole -> outside;
  * within _EDGE_EPS of ANY edge (exterior or hole) -> boundary flag,
    never silently in or out;
  * boundary-flagged hits are returned but marked so consumers can
    fail closed;
  * no holes are ever approximated or filled.
"""

from __future__ import annotations

import pytest

from alraso.spatial import (InMemorySpatialProvider, ScopeHit,
                            SpatialFactsError, parts_from_geojson,
                            parts_from_parts_latlon,
                            parts_from_rings_latlon, _EDGE_EPS)

# Square exterior 0..10 in both axes, square hole 4..6.
EXT = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
HOLE = [(4.0, 4.0), (4.0, 6.0), (6.0, 6.0), (6.0, 4.0)]
EXT2 = [(20.0, 20.0), (20.0, 30.0), (30.0, 30.0), (30.0, 20.0)]


def _provider(**kw) -> InMemorySpatialProvider:
    p = InMemorySpatialProvider()
    p.add_scope("s", "s", "OTHER", **kw)
    return p


def _hit(p: InMemorySpatialProvider, lat: float, lon: float) -> ScopeHit | None:
    hits = p.resolve(lat, lon)
    assert len(hits) <= 1
    return hits[0] if hits else None


def test_hole_point_is_outside():
    p = _provider(parts=[[EXT, HOLE]])
    assert _hit(p, 5.0, 5.0) is None          # centre of the hole
    assert _hit(p, 4.5, 5.5) is None          # still inside hole


def test_exterior_around_hole_is_inside():
    p = _provider(parts=[[EXT, HOLE]])
    h = _hit(p, 1.0, 1.0)
    assert h is not None and h.on_boundary is False
    h = _hit(p, 8.0, 8.0)
    assert h is not None and h.on_boundary is False


def test_outside_everything():
    p = _provider(parts=[[EXT, HOLE]])
    assert _hit(p, 15.0, 15.0) is None
    assert _hit(p, -1.0, 5.0) is None


def test_multipart_with_holes():
    p = _provider(parts=[[EXT, HOLE], [EXT2]])
    assert _hit(p, 5.0, 5.0) is None          # hole in part 1
    assert _hit(p, 25.0, 25.0) is not None    # inside part 2
    assert _hit(p, 15.0, 15.0) is None        # gap between parts


def test_boundary_exterior_flagged_not_in_or_out():
    p = _provider(parts=[[EXT, HOLE]])
    h = _hit(p, 0.0, 5.0)                     # exactly on west edge
    assert h is not None and h.on_boundary is True
    h = _hit(p, 5.0, 10.0)                    # on north edge
    assert h is not None and h.on_boundary is True


def test_boundary_hole_edge_flagged():
    p = _provider(parts=[[EXT, HOLE]])
    h = _hit(p, 4.0, 5.0)                     # on the hole's west edge
    assert h is not None and h.on_boundary is True
    h = _hit(p, 5.0, 6.0)                     # on the hole's north edge
    assert h is not None and h.on_boundary is True


def test_within_eps_counts_as_boundary():
    p = _provider(parts=[[EXT, HOLE]])
    h = _hit(p, _EDGE_EPS / 2, 5.0)           # just inside eps of west edge
    assert h is not None and h.on_boundary is True


def test_vertex_is_boundary():
    p = _provider(parts=[[EXT, HOLE]])
    h = _hit(p, 0.0, 0.0)                     # exterior corner
    assert h is not None and h.on_boundary is True


def test_boundary_never_silently_in_or_out():
    """A boundary point must not produce a definitive non-flagged hit —
    that is the whole point of the preregistered policy."""
    p = _provider(parts=[[EXT, HOLE]])
    for lat, lon in ((0.0, 5.0), (10.0, 5.0), (5.0, 0.0), (5.0, 10.0),
                     (4.0, 5.0), (6.0, 5.0), (5.0, 4.0), (5.0, 6.0)):
        h = _hit(p, lat, lon)
        assert h is not None and h.on_boundary is True, (lat, lon)


def test_inside_one_part_boundary_of_another_is_inside():
    """A point definitively inside part 2 is inside even if it is also on
    part 1's edge — the inside is not ambiguous."""
    # part2 overlaps part1 (lat 8..20): (10,5) sits on part1's lat=10 edge
    # but is strictly interior to part2 -> definitive inside.
    p = _provider(parts=[[EXT, HOLE],
                         [[(8.0, 0.0), (8.0, 10.0), (20.0, 10.0), (20.0, 0.0)]]])
    h = _hit(p, 10.0, 5.0)
    assert h is not None and h.on_boundary is False


def test_legacy_rings_still_work():
    p = _provider(rings=[EXT])
    assert _hit(p, 5.0, 5.0) is not None
    assert _hit(p, 15.0, 5.0) is None
    # legacy rings = independent parts, never holes
    p = _provider(rings=[EXT, HOLE])
    assert _hit(p, 5.0, 5.0) is not None  # inside the "hole" ring = separate part


def test_add_scope_requires_one_form():
    p = InMemorySpatialProvider()
    with pytest.raises(SpatialFactsError):
        p.add_scope("s", "s", "OTHER")
    with pytest.raises(SpatialFactsError):
        p.add_scope("s", "s", "OTHER", rings=[EXT], parts=[[EXT]])


def test_parts_from_geojson_polygon_and_multipolygon():
    poly = {"type": "Polygon",
            "coordinates": [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
                            [[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0]]]}
    parts = parts_from_geojson(poly)
    assert len(parts) == 1 and len(parts[0]) == 2   # ext + 1 hole
    # GeoJSON is (lon, lat); parts are (lat, lon)
    assert parts[0][0][1] == (0.0, 10.0)
    multi = {"type": "MultiPolygon",
             "coordinates": [poly["coordinates"],
                             [[[20.0, 20.0], [30.0, 20.0], [30.0, 30.0]]]]}
    parts = parts_from_geojson(multi)
    assert len(parts) == 2
    p = InMemorySpatialProvider()
    p.add_scope("s", "s", "OTHER", parts=parts)
    assert _hit(p, 5.0, 5.0) is None           # inside hole (GeoJSON hole)
    assert _hit(p, 1.0, 1.0) is not None
    assert _hit(p, 21.0, 25.0) is not None   # inside triangular part 2


def test_parts_from_geojson_rejects_other_types():
    for bad in ({"type": "Point", "coordinates": [0, 0]},
                {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                {"type": "Polygon", "coordinates": []},
                {"type": "Polygon", "coordinates": [[(0, 0), (1, 1)]]}):
        with pytest.raises(SpatialFactsError):
            parts_from_geojson(bad)


def test_fixture_serialisation_forms():
    """Both fixture forms round-trip: rings_latlon (legacy) and
    parts_latlon (holes-capable)."""
    rings = parts_from_rings_latlon(
        [[[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0]]])
    assert rings == [[EXT]]
    parts = parts_from_parts_latlon(
        [[[[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0]],
          [[4.0, 4.0], [4.0, 6.0], [6.0, 6.0], [6.0, 4.0]]]])
    assert parts == [[EXT, HOLE]]
    with pytest.raises(SpatialFactsError):
        parts_from_parts_latlon([])
    with pytest.raises(SpatialFactsError):
        parts_from_parts_latlon([[]])
