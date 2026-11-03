"""Tests für den IDS-Import, die neuen Regeltypen und die Modellprüfung."""

from pathlib import Path

import pytest

from core import ids_import, ifc_reader, model_check, pending
from core.validator import check_value, load_rules, merge_rules, rules_for_class

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "beispiel_anforderungen.ids"
OFFICIAL_EXAMPLES = Path(__file__).resolve().parent / "ids_beispiele"


@pytest.fixture(scope="module")
def example():
    return ids_import.parse_ids(EXAMPLE.read_bytes())


def test_example_rules(example):
    rules, notes, info = example
    assert info["specifications"] == 5 and info["ifc_versions"] == ["IFC2X3", "IFC4"]
    wall = rules_for_class(rules, "IfcWall")
    assert wall["Pset_WallCommon"]["FireRating"] == {
        "type": "enum", "values": ["EI30", "EI60", "EI90"], "required": True, "dataType": "IFCLABEL",
        "instructions": "Feuerwiderstand nach VKF, z. B. EI60", "source": "Wände: Brandschutz und Tragwerk"}
    assert wall["CH_Brandschutz"]["Nachweis"]["type"] == "pattern"
    assert rules_for_class(rules, "IfcWallStandardCase")["Pset_WallCommon"]["LoadBearing"]["type"] == "bool"
    u = rules_for_class(rules, "IfcWindow")["Pset_WindowCommon"]["ThermalTransmittance"]
    assert (u["type"], u["min"], u["max"]) == ("float", 0.3, 1.3)
    assert any("attribute" in n for n in notes)            # Attribut-Anforderung nicht übernommen


def test_not_an_ids():
    with pytest.raises(ids_import.IdsError):
        ids_import.parse_ids(b"<root/>")
    with pytest.raises(ids_import.IdsError):
        ids_import.parse_ids(b"kein xml")


def test_rule_types():
    assert check_value(None, {"type": "enum", "values": ["A"], "required": True})[0] is False
    assert check_value(None, {"type": "enum", "values": ["A"]})[0] is True
    assert check_value("VKF 2015", {"type": "pattern", "pattern": "VKF.*"})[0] is True
    assert check_value("SIA", {"type": "pattern", "pattern": "VKF.*"})[0] is False
    assert check_value("x", {"type": "prohibited"})[0] is False
    assert check_value("Nein", {"type": "bool", "value": True})[0] is False
    assert check_value("30", {"type": "enum", "values": ["30.0"]})[0] is True
    ok, message, _ = check_value("EI45", {"type": "enum", "values": ["EI30"], "source": "Wände"})
    assert not ok and "(Regel: Wände)" in message


def test_merge_keeps_rules_json_and_ids_wins(example):
    merged = merge_rules(load_rules(), example[0])
    wall = rules_for_class(merged, "IfcWall")["Pset_WallCommon"]
    assert wall["FireRating"]["required"] is True                    # aus der IDS
    assert rules_for_class(merged, "IfcSlab")["Pset_SlabCommon"]     # aus rules.json, nicht in der IDS


def test_model_check_with_example(model, example):
    props = ifc_reader.element_properties(model)
    issues = model_check.check_model(props, example[0])
    count = lambda cls, prop: int(((issues["Klasse"] == cls) & (issues["Property"] == prop)).sum())  # noqa: E731
    assert count("IfcWall", "FireRating") == 3          # 2 fehlen, 1 mit EI45
    assert count("IfcDoor", "FireRating") == 1
    assert count("IfcWindow", "ThermalTransmittance") == 1
    assert count("IfcStair", "RiserHeight") == 0        # 0.1765 liegt im Bereich


def test_model_check_counts_pending_fix(model, example):
    props = ifc_reader.element_properties(model)
    door = next(g for g, p in props.items() if p["cls"] == "IfcDoor" and p["psets"]["Pset_DoorCommon"].get("FireRating") is None)
    store = {}
    pending.put(store, door, "Tür", "IfcDoor", "Pset_DoorCommon", "FireRating", None, "EI30")
    issues = model_check.check_model(props, example[0], store)
    assert not ((issues["Klasse"] == "IfcDoor") & (issues["Property"] == "FireRating")).any()


@pytest.mark.parametrize("path", sorted(OFFICIAL_EXAMPLES.glob("*.ids")), ids=lambda p: p.name)
def test_official_examples_parse(path):
    """Beispiele aus dem IDS-Repository von buildingSMART lassen sich lesen, ohne Absturz."""
    rules, notes, info = ids_import.parse_ids(path.read_bytes())
    assert info["specifications"] > 0
