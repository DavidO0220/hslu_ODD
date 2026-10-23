"""Validator: Änderungen gegen die Regeln in config/rules.json prüfen (Phase 3)."""

import json
from pathlib import Path

import pandas as pd

from core.diff import normalize
from core.display import NO, YES
from core.schema import COL_MESSAGE, COL_NEW, COL_PROPERTY, COL_PSET, COL_VALID, VALIDATED_COLUMNS

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.json"

_TRUE = {"ja", "true", "wahr", "1", "yes"}
_FALSE = {"nein", "false", "falsch", "0", "no"}


def load_rules(path: Path = RULES_PATH) -> dict:
    """Liest die Regeln aus der JSON-Datei."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rules_for_class(rules: dict, ifc_class: str) -> dict:
    """Regeln einer Klasse. IFC2x3-Varianten wie IfcWallStandardCase nutzen die Regeln von IfcWall."""
    if ifc_class in rules:
        return rules[ifc_class]
    for suffix in ("StandardCase", "ElementedCase"):
        if ifc_class.endswith(suffix) and ifc_class[: -len(suffix)] in rules:
            return rules[ifc_class[: -len(suffix)]]
    return {}


def to_bool(value):
    """Ja/Nein, True/False, 1/0 usw. als Python-bool, sonst None."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return None


def check_value(value, rule: dict | None):
    """Prüft einen Wert gegen eine Regel.

    Rückgabe: (gültig, Meldung, Wert in der richtigen Form zum Schreiben)
    """
    value = normalize(value)
    if value is None:
        return True, "Wert wird entfernt", None
    if not rule:
        return True, "keine Regel hinterlegt", value

    kind = rule.get("type")
    if kind == "enum":
        allowed = rule.get("values", [])
        text = str(value).strip()
        if text in allowed:
            return True, "", text
        return False, f"nicht in der Werteliste ({', '.join(allowed)})", value
    if kind == "bool":
        as_bool = to_bool(value)
        if as_bool is None:
            return False, f"muss {YES} oder {NO} sein", value
        return True, "", as_bool
    if kind == "float":
        try:
            number = float(str(value).replace(",", "."))
        except ValueError:
            return False, "muss eine Zahl sein", value
        low, high = rule.get("min"), rule.get("max")
        if (low is not None and number < low) or (high is not None and number > high):
            return False, f"muss zwischen {low} und {high} liegen", value
        return True, "", number
    return True, f"unbekannter Regeltyp '{kind}', nicht geprüft", value


def validate(changes: pd.DataFrame, ifc_class: str, rules: dict) -> pd.DataFrame:
    """Ergänzt die Änderungsliste um 'Gueltig' und 'Meldung'.

    Die Spalte 'Neu' enthält danach den Wert in der Form, in der er ins IFC
    geschrieben wird (z. B. True statt "Ja", 0.25 statt "0,25").
    """
    class_rules = rules_for_class(rules, ifc_class)
    result = changes.copy()
    valid, messages, values = [], [], []
    for _, row in changes.iterrows():
        rule = class_rules.get(row[COL_PSET], {}).get(row[COL_PROPERTY])
        ok, message, value = check_value(row[COL_NEW], rule)
        valid.append(ok)
        messages.append(message)
        values.append(value)
    result[COL_NEW] = pd.Series(values, index=result.index, dtype=object)
    result[COL_VALID] = pd.Series(valid, index=result.index, dtype=bool)
    result[COL_MESSAGE] = pd.Series(messages, index=result.index, dtype=object)
    return result[VALIDATED_COLUMNS]
