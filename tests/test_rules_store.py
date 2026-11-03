"""Tests für den Regel-Editor: Tabelle hin und zurück, Prüfung der Eingaben, Speichern, Zurücksetzen."""

import json

from core import rules_store
from core.validator import STANDARD_RULES_PATH, load_rules


def test_roundtrip_standard():
    standard = load_rules(STANDARD_RULES_PATH)
    rules, errors = rules_store.table_to_rules(rules_store.rules_to_table(standard))
    assert errors == [] and rules == standard


def test_roundtrip_all_types():
    rules = {"IfcWall": {"P": {
        "a": {"type": "enum", "values": ["EI30", "EI60"], "required": True},
        "b": {"type": "bool", "value": True},
        "c": {"type": "float", "min": 0.3, "max": 3.0, "instructions": "U-Wert"},
        "d": {"type": "pattern", "pattern": "VKF.*"},
        "e": {"type": "text"},
        "f": {"type": "prohibited"},
    }}}
    back, errors = rules_store.table_to_rules(rules_store.rules_to_table(rules))
    assert errors == [] and back == rules


def test_input_errors():
    table = rules_store.rules_to_table({"IfcWall": {"P": {"a": {"type": "enum", "values": ["X"]}}}})
    table.loc[1] = {"Klasse": "IfcWall", "Pset": "P", "Property": "b", "Typ": "Muster", "Muster": "([",
                    "Werteliste": "", "Min": None, "Max": None, "Pflicht": False, "Hinweis": ""}
    table.loc[2] = {"Klasse": "IfcWall", "Pset": "", "Property": "c", "Typ": "Zahl", "Muster": "",
                    "Werteliste": "", "Min": 5, "Max": 1, "Pflicht": False, "Hinweis": ""}
    table.loc[3] = {"Klasse": "IfcWall", "Pset": "P", "Property": "a", "Typ": "Werteliste", "Muster": "",
                    "Werteliste": "", "Min": None, "Max": None, "Pflicht": False, "Hinweis": ""}
    _, errors = rules_store.table_to_rules(table)
    assert len(errors) == 3 and any("ungültig" in e for e in errors) and any("Pset" in e for e in errors)


def test_save_and_reset(tmp_path):
    active, standard = tmp_path / "rules.json", tmp_path / "rules_standard.json"
    standard.write_text(STANDARD_RULES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    rules = load_rules(standard)
    rules["IfcWall"]["Pset_WallCommon"]["FireRating"]["values"].append("EI120")
    rules_store.save_rules(rules, active)
    assert "EI120" in json.loads(active.read_text(encoding="utf-8"))["IfcWall"]["Pset_WallCommon"]["FireRating"]["values"]
    assert rules_store.differences(load_rules(active), load_rules(standard)) == ["geändert: IFCWALL · Pset_WallCommon · FireRating"]
    rules_store.reset_rules(active, standard)
    assert rules_store.differences(load_rules(active), load_rules(standard)) == []
