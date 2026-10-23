import pandas as pd

from core.schema import CHANGE_COLUMNS
from core.validator import check_value, load_rules, rules_for_class, validate

RULES = load_rules()


def _changes(*rows):
    return pd.DataFrame([["g", "Wand", "Pset_WallCommon", p, None, v] for p, v in rows], columns=CHANGE_COLUMNS)


def test_enum():
    result = validate(_changes(("FireRating", "EI60"), ("FireRating", "EI45")), "IfcWall", RULES)
    assert list(result["Gueltig"]) == [True, False]
    assert "Werteliste" in result.iloc[1]["Meldung"]


def test_bool_converted():
    result = validate(_changes(("IsExternal", "Ja"), ("LoadBearing", "Nein"), ("IsExternal", "vielleicht")), "IfcWall", RULES)
    assert list(result["Gueltig"]) == [True, True, False]
    assert result.iloc[0]["Neu"] is True
    assert result.iloc[1]["Neu"] is False


def test_float_with_comma_and_range():
    rule = {"type": "float", "min": 0.05, "max": 3.0}
    assert check_value("0,25", rule) == (True, "", 0.25)
    assert check_value("5", rule)[0] is False
    assert check_value("abc", rule)[0] is False


def test_removal_and_no_rule():
    assert check_value(None, {"type": "enum", "values": ["A"]})[0] is True
    assert check_value("frei", None) == (True, "keine Regel hinterlegt", "frei")


def test_ifc2x3_class_falls_back():
    assert rules_for_class(RULES, "IfcWallStandardCase") == RULES["IfcWall"]


def test_empty_changes():
    result = validate(_changes(), "IfcWall", RULES)
    assert len(result) == 0 and "Gueltig" in result.columns
