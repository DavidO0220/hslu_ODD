"""Validator: Änderungen gegen die Regeln prüfen (Phase 3).

Regeln kommen aus config/rules.json und optional aus einer IDS-Datei
(core/ids_import.py). Regeltypen:

    enum        Wert aus einer Liste             {"type": "enum", "values": ["EI30", "EI60"]}
    bool        Ja/Nein, optional fester Wert    {"type": "bool", "value": true}
    float       Zahl, optional mit Grenzen       {"type": "float", "min": 0.3, "max": 3.0}
    pattern     Text nach Muster (Regex)         {"type": "pattern", "pattern": "VKF.*"}
    text        beliebiger Text                  {"type": "text"}
    prohibited  Property darf nicht vorkommen    {"type": "prohibited"}

Zusätzlich bei jeder Regel: "required": true heisst Pflichtwert, leer ist ein
Fehler. "source" nennt die Herkunft (z. B. Name der IDS-Spezifikation).
"""

import copy
import json
import re
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
    """Regeln einer Klasse, ohne Gross-/Kleinschreibung (IDS schreibt IFCWALL).

    IFC2x3-Varianten wie IfcWallStandardCase nutzen die Regeln von IfcWall,
    falls es für die Variante selbst keine gibt.
    """
    by_upper = {k.upper(): v for k, v in rules.items()}
    name = ifc_class.upper()
    if name in by_upper:
        return by_upper[name]
    for suffix in ("STANDARDCASE", "ELEMENTEDCASE"):
        if name.endswith(suffix) and name[: -len(suffix)] in by_upper:
            return by_upper[name[: -len(suffix)]]
    return {}


def merge_rules(base: dict, extra: dict) -> dict:
    """Regeln zusammenführen. Bei gleicher Klasse, gleichem Pset und gleicher Property gilt extra."""
    result = copy.deepcopy(base)
    keys = {k.upper(): k for k in result}
    for cls, psets in extra.items():
        target = result.setdefault(keys.get(cls.upper(), cls), {})
        for pset, props in psets.items():
            target.setdefault(pset, {}).update(copy.deepcopy(props))
    return result


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
    ok, message, out = _check(value, rule)
    if not ok and rule and rule.get("source"):
        message = f"{message} (Regel: {rule['source']})"
    return ok, message, out


def _number(value):
    if isinstance(value, bool):
        raise ValueError(value)
    return float(str(value).replace(",", "."))


def _check(value, rule: dict | None):
    if not rule:
        return True, ("Wert wird entfernt" if value is None else "keine Regel hinterlegt"), value
    kind = rule.get("type")
    if kind == "prohibited":
        return (True, "Wert wird entfernt", None) if value is None else (False, "darf laut Regel nicht vorkommen", value)
    if value is None:
        if rule.get("required"):
            return False, "Pflichtwert, darf nicht leer sein", None
        return True, "Wert wird entfernt", None

    if kind == "enum":
        allowed = [str(v) for v in rule.get("values", [])]
        text = str(value).strip()
        if text in allowed:
            return True, "", text
        try:   # Zahlen in einer Werteliste: 30 und 30.0 gelten als gleich
            number = _number(text)
            match = next((a for a in allowed if _number(a) == number), None)
            if match is not None:
                return True, "", match
        except ValueError:
            pass
        return False, f"nicht in der Werteliste ({', '.join(allowed)})", value
    if kind == "bool":
        as_bool = to_bool(value)
        if as_bool is None:
            return False, f"muss {YES} oder {NO} sein", value
        if "value" in rule and as_bool != bool(rule["value"]):
            return False, f"muss {YES if rule['value'] else NO} sein", value
        return True, "", as_bool
    if kind == "float":
        try:
            number = _number(value)
        except ValueError:
            return False, "muss eine Zahl sein", value
        low, high = rule.get("min"), rule.get("max")
        low_x, high_x = rule.get("min_exclusive"), rule.get("max_exclusive")
        if (low is not None and number < low) or (high is not None and number > high):
            if low == high:
                return False, f"muss {low} sein", value
            return False, f"muss zwischen {low} und {high} liegen", value
        if (low_x is not None and number <= low_x) or (high_x is not None and number >= high_x):
            return False, f"muss grösser als {low_x} und kleiner als {high_x} sein", value
        return True, "", number
    if kind == "pattern":
        text = str(value).strip()
        if re.fullmatch(rule.get("pattern", ".*"), text):
            return True, "", text
        return False, f"entspricht nicht dem Muster «{rule.get('pattern')}»", value
    if kind == "text":
        return True, "", str(value).strip()
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
