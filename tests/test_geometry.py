"""Tests für die 3D-Geometrie. Prüft die Netze gegen die bekannten Masse des Testmodells."""

import pytest

from core import geometry


@pytest.fixture(scope="module")
def meshes(model):
    return geometry.load_meshes(model)


def _find(meshes, name, storey):
    return next(m for m in meshes if m["name"] == name and m["storey"] == storey)


def _close(a, b, tol=1e-3):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def test_every_component_has_a_mesh(meshes):
    counts = {}
    for m in meshes:
        counts[m["cls"]] = counts.get(m["cls"], 0) + 1
    assert counts == {"IfcWall": 15, "IfcSlab": 3, "IfcDoor": 3, "IfcWindow": 6, "IfcStair": 1}


def test_meshes_are_consistent(meshes):
    for m in meshes:
        assert len(m["v"]) % 3 == 0 and len(m["f"]) % 3 == 0
        assert max(m["f"]) < len(m["v"]) // 3
        assert len(m["id"]) == 22   # GlobalId verbindet Netz und Tabellenzeile


def test_inner_wall_position(meshes):
    low, high = geometry.bounds(_find(meshes, "Innenwand 120", "EG"))
    assert _close(low, [4.94, 0.0, 0.25]) and _close(high, [5.06, 8.0, 3.0])


def test_upper_storey_and_rotation(meshes):
    # Ostwand im 2. OG: um 90° gedreht und 6 m höher
    low, high = geometry.bounds(_find(meshes, "Aussenwand Ost 300", "2. OG"))
    assert _close(low, [9.85, 0.0, 6.25]) and _close(high, [10.15, 8.0, 9.0])


def test_window_position(meshes):
    low, high = geometry.bounds(_find(meshes, "Fenster Süd 1", "EG"))
    assert _close(low, [2.0, -0.04, 1.15]) and _close(high, [3.2, 0.04, 2.55])


def test_stair_reaches_upper_floor(meshes):
    low, high = geometry.bounds(_find(meshes, "Treppe EG bis 1. OG", "EG"))
    assert _close(low, [0.5, 1.5, 0.25]) and high[2] < 3.25 and high[2] > 3.0
