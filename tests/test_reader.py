"""Tests für Phase 1. Alle müssen grün sein, dann ist Phase 1 erreicht."""

from core import ifc_reader
from core.schema import FIXED_COLUMNS


def test_classes(model):
    assert ifc_reader.list_classes(model) == ["IfcDoor", "IfcSlab", "IfcStair", "IfcWall", "IfcWindow"]


def test_psets_for_walls(model):
    assert ifc_reader.list_psets(model, "IfcWall") == ["Pset_WallCommon"]


def test_table_shape(model):
    table = ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon")
    assert len(table) == 15
    assert list(table.columns[:3]) == FIXED_COLUMNS
    assert {"FireRating", "IsExternal", "LoadBearing"} <= set(table.columns)


def test_empty_and_invalid_values(model):
    table = ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon")
    assert table["FireRating"].isna().sum() == 2
    assert (table["FireRating"] == "EI45").sum() == 1


def test_storeys(model):
    table = ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon")
    assert sorted(table["Geschoss"].unique()) == ["1. OG", "2. OG", "EG"]
    assert (table["Geschoss"] == "EG").sum() == 5


def test_booleans_are_booleans(model):
    table = ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon")
    assert set(table["IsExternal"]) == {True, False}


def test_load_from_bytes(model_path):
    loaded = ifc_reader.load_model(model_path.read_bytes())
    assert len(loaded.by_type("IfcWall")) == 15


def test_openings_are_not_listed(model):
    assert len(model.by_type("IfcOpeningElement")) > 0
    assert "IfcOpeningElement" not in ifc_reader.list_classes(model)


def test_windows_and_stair(model):
    windows = ifc_reader.to_table(model, "IfcWindow", "Pset_WindowCommon")
    assert len(windows) == 6
    assert windows["ThermalTransmittance"].isna().sum() == 1
    stair = ifc_reader.to_table(model, "IfcStair", "Pset_StairCommon")
    assert len(stair) == 1
    assert abs(stair["TreadLength"].iloc[0] - 0.27) < 1e-9
