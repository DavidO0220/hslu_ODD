from core import ifc_reader
from core.display import bool_columns, to_display


def test_bool_columns(model):
    table = ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon")
    assert bool_columns(table) == ["IsExternal", "LoadBearing"]


def test_bool_shown_as_ja_nein(model):
    shown = to_display(ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon"))
    assert set(shown["IsExternal"]) == {"Ja", "Nein"}
    assert shown["FireRating"].isna().sum() == 2
