"""Tests für Phase 2: Änderungen erkennen."""

import pandas as pd

from core import diff, ifc_reader
from core.display import to_display
from core.schema import CHANGE_COLUMNS


def _walls(model):
    return to_display(ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon"))


def test_no_change(model):
    table = _walls(model)
    assert len(diff.find_changes(table, table.copy(), "Pset_WallCommon")) == 0


def test_one_change(model):
    table = _walls(model)
    edited = table.copy()
    row = edited.index[edited["FireRating"].isna()][0]
    edited.loc[row, "FireRating"] = "EI60"
    changes = diff.find_changes(table, edited, "Pset_WallCommon")
    assert list(changes.columns) == CHANGE_COLUMNS
    assert len(changes) == 1
    assert changes.iloc[0]["Property"] == "FireRating"
    assert changes.iloc[0]["Alt"] is None
    assert changes.iloc[0]["Neu"] == "EI60"


def test_empty_variants_are_no_change(model):
    table = _walls(model)
    edited = table.copy()
    edited["FireRating"] = edited["FireRating"].astype(object).where(edited["FireRating"].notna(), "")
    assert len(diff.find_changes(table, edited, "Pset_WallCommon")) == 0
    edited["FireRating"] = edited["FireRating"].replace("", float("nan"))
    assert len(diff.find_changes(table, edited, "Pset_WallCommon")) == 0


def test_rows_matched_by_guid_not_position(model):
    table = _walls(model)
    shuffled = table.iloc[::-1].reset_index(drop=True)
    assert len(diff.find_changes(table, shuffled, "Pset_WallCommon")) == 0


def test_locked_columns_ignored(model):
    table = _walls(model)
    edited = table.copy()
    edited.loc[0, "Name"] = "umbenannt"
    assert len(diff.find_changes(table, edited, "Pset_WallCommon")) == 0


def test_whitespace_only_is_no_change():
    a = pd.DataFrame({"GlobalId": ["x"], "Name": ["W"], "Geschoss": ["EG"], "FireRating": ["EI60"]})
    b = a.copy(); b.loc[0, "FireRating"] = " EI60 "
    assert len(diff.find_changes(a, b, "P")) == 0


def test_streamlit_text_conversion_is_no_change():
    """Streamlit kann Spalten mit gemischten Typen in Text umwandeln."""
    a = pd.DataFrame({"GlobalId": ["x", "y"], "Name": ["A", "B"], "Geschoss": ["EG", "EG"], "U": [0.25, None]})
    b = a.copy(); b["U"] = ["0.25", "None"]
    assert len(diff.find_changes(a, b, "P")) == 0
    b.loc[0, "U"] = "0.3"
    assert len(diff.find_changes(a, b, "P")) == 1
