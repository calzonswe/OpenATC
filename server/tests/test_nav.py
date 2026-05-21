import pytest
from src.services.nav import NavDatabase


# Use the actual downloaded data
nav = NavDatabase(data_dir="data")


def test_get_airport_found():
    apt = nav.get_airport("EDDM")
    assert apt is not None
    assert apt.icao == "EDDM"
    assert apt.country_code == "DE"
    assert apt.type == "large_airport"


def test_get_airport_not_found():
    apt = nav.get_airport("XXXX")
    assert apt is None


def test_get_runways():
    runways = nav.get_runways("EDDM")
    assert len(runways) > 0
    runway_idents = [r.ident for r in runways]
    assert "26R" in runway_idents or "08L" in runway_idents


def test_get_runway():
    rw = nav.get_runway("EDDM", "26R")
    if rw:
        assert rw.airport_icao == "EDDM"
        assert rw.ident == "26R"
        if rw.heading_deg:
            assert 250 <= rw.heading_deg <= 270  # Approx


def test_get_frequency():
    # EDDM tower frequency
    freq = nav.get_frequency("EDDM", "TOWER")
    if freq:
        assert 118.0 <= freq <= 137.0


def test_get_country_code():
    assert nav.get_country_code("EDDM") == "DE"
    assert nav.get_country_code("EGLL") == "GB"
    assert nav.get_country_code("LFPG") == "FR"


def test_nearest_airport_munich():
    # Position near EDDM (Munich Airport) — EDDM is at ~48.3538, 11.7861
    apt = nav.nearest_airport(48.35, 11.78, radius_nm=5)
    assert apt is not None
    assert apt.icao == "EDDM"
    assert apt.country_code == "DE"


def test_nearest_airport_london():
    apt = nav.nearest_airport(51.47, -0.46, radius_nm=10)
    assert apt is not None
    assert apt.country_code == "GB"


def test_nearest_airports_multiple():
    results = nav.nearest_airports(48.35, 11.78, radius_nm=30, limit=3)
    assert len(results) >= 1
    assert results[0][0].icao == "EDDM"


def test_nearest_navaid():
    nav_id = nav.nearest_navaid(48.14, 11.56, radius_nm=50)
    if nav_id:
        assert len(nav_id.ident) > 0


def test_country_from_position():
    country = nav.country_from_position(48.14, 11.56)
    assert country == "DE"

    country = nav.country_from_position(51.47, -0.46)
    assert country == "GB"
