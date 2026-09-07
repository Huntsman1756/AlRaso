"""DEM fail-closed: if the DEM stack is not configured/available, no cota_m is
injected and the resolver stays UNDETERMINED (never a guess, never a fallback).
Runs in the stdlib-only CI (no rasterio needed)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import dem as dem_mod  # noqa: E402
import server  # noqa: E402

TODAY = "2026-09-06"


@pytest.fixture(scope="module")
def svc() -> server.Service:
    return server.Service()


def _unconfigured(monkeypatch):
    monkeypatch.setattr(dem_mod, "DEM_META", str(Path("nonexistent/picos_mdt.meta.json")))
    monkeypatch.setattr(dem_mod, "DEM_TILE", str(Path("nonexistent/picos_mdt.tif")))


def test_dem_unconfigured_never_injects_cota(svc, monkeypatch):
    _unconfigured(monkeypatch)
    out = server.resolve_point(svc, lat=43.2662, lon=-4.8686, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"actividad_montana_o_escalada": True, "nights": 2})
    assert out["cotaFactSource"] == "NONE"
    assert out["dem"] is None
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["determination"]["reasonCodes"]


def test_dem_unavailable_user_cota_still_used(svc, monkeypatch):
    _unconfigured(monkeypatch)
    out = server.resolve_point(svc, lat=43.2662, lon=-4.8686, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"actividad_montana_o_escalada": True,
                                      "nights": 2, "cota_m": 2000})
    assert out["cotaFactSource"] == "USER"
    assert out["dem"] is None
    assert out["determination"]["legalStatus"] == "PERMITTED"  # user cota 2000 > 1800


def test_dem_sample_raises_incomplete_when_unconfigured(monkeypatch):
    _unconfigured(monkeypatch)
    with pytest.raises(dem_mod.DemEvidenceIncomplete):
        dem_mod.sample_elevation(43.2662, -4.8686)
