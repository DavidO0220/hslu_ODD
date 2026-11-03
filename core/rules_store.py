"""Regeln als Tabelle: anzeigen, von Hand bearbeiten, speichern, zurücksetzen.

config/rules_standard.json ist die Standardvorlage und wird nie verändert.
config/rules.json enthält die aktiven Regeln. Der Reiter «Regeln» der
Oberfläche zeigt sie als Tabelle mit einer Zeile pro Property.
"""

import json
import re
import shutil
from pathlib import Path

import pandas as pd

from core.validator import RULES_PATH, STANDARD_RULES_PATH

# Spalten der Regel-Tabelle
COL_CLASS, COL_PSET, COL_PROP = "Klasse", "Pset", "Property"
COL_TYPE, COL_VALUES, COL_MIN, COL_MAX = "Typ", "Werteliste", "Min", "Max"
COL_PATTERN, COL_REQUIRED, COL_NOTE = "Muster", "Pflicht", "Hinweis"
TABLE_COLUMNS = [COL_CLASS, COL_PSET, COL_PROP, COL_TYPE, COL_VALUES, COL_MIN, COL_MAX,
                 COL_PATTERN, COL_REQUIRED, COL_NOTE]

# Regeltyp in der Datei <-> Bezeichnung in der Tabelle
TYPE_LABELS = {"enum": "Werteliste", "bool": "Ja/Nein", "float": "Zahl", "pattern": "Muster",
               "text": "Text", "prohibited": "verboten"}
LABEL_TYPES = {v: k for k, v in TYPE_LABELS.items()}


def _blank(value) -> bool:
    return value is None or (isinstance(value, float) and value != value) or str(value).strip() == ""


def rules_to_table(rules: dict) -> pd.DataFrame:
    """Eine Zeile pro Klasse, Pset und Property."""
    rows = []
    for cls, psets in rules.items():
        for pset, props in psets.items():
            for prop, rule in props.items():
                kind = rule.get("type")
                values = ""
                if kind == "enum":
                    values = ", ".join(str(v) for v in rule.get("values", []))
                elif kind == "bool" and "value" in rule:
                    values = "Ja" if rule["value"] else "Nein"
                rows.append({
                    COL_CLASS: cls, COL_PSET: pset, COL_PROP: prop,
                    COL_TYPE: TYPE_LABELS.get(kind, kind),
                    COL_VALUES: values,
                    COL_MIN: rule.get("min"), COL_MAX: rule.get("max"),
                    COL_PATTERN: rule.get("pattern", ""),
                    COL_REQUIRED: bool(rule.get("required", False)),
                    COL_NOTE: rule.get("instructions", ""),
                })
    frame = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    frame[COL_MIN] = pd.to_numeric(frame[COL_MIN], errors="coerce")
    frame[COL_MAX] = pd.to_numeric(frame[COL_MAX], errors="coerce")
    return frame.sort_values([COL_CLASS, COL_PSET, COL_PROP], kind="stable").reset_index(drop=True)


def table_to_rules(table: pd.DataFrame) -> tuple[dict, list[str]]:
    """Tabelle zurück in Regeln. Leere Zeilen werden übersprungen.

    Rückgabe: (Regeln, Fehlermeldungen). Bei Fehlern sind die Regeln nicht verwendbar.
    """
    rules: dict = {}
    errors: list[str] = []
    for n, row in enumerate(table.to_dict("records"), start=1):
        cls, pset, prop = (str(row.get(c) or "").strip() for c in (COL_CLASS, COL_PSET, COL_PROP))
        if not cls and not pset and not prop:
            continue
        where = f"Zeile {n} ({cls or '?'} · {pset or '?'} · {prop or '?'})"
        if not cls or not pset or not prop:
            errors.append(f"{where}: Klasse, Pset und Property müssen ausgefüllt sein.")
            continue
        kind = LABEL_TYPES.get(str(row.get(COL_TYPE) or "").strip())
        if kind is None:
            errors.append(f"{where}: Typ fehlt oder ist unbekannt ({', '.join(LABEL_TYPES)}).")
            continue
        rule: dict = {"type": kind}
        values = "" if _blank(row.get(COL_VALUES)) else str(row.get(COL_VALUES))
        if kind == "enum":
            items = [v.strip() for v in values.split(",") if v.strip()]
            if not items:
                errors.append(f"{where}: Werteliste ist leer, Werte mit Komma trennen.")
                continue
            rule["values"] = items
        elif kind == "bool" and values.strip():
            if values.strip() not in ("Ja", "Nein"):
                errors.append(f"{where}: Bei Ja/Nein ist in «Werteliste» nur «Ja» oder «Nein» als fester Wert erlaubt.")
                continue
            rule["value"] = values.strip() == "Ja"
        elif kind == "float":
            for col, key in ((COL_MIN, "min"), (COL_MAX, "max")):
                if not _blank(row.get(col)):
                    try:
                        rule[key] = float(str(row.get(col)).replace(",", "."))
                    except ValueError:
                        errors.append(f"{where}: {col} ist keine Zahl.")
            if "min" in rule and "max" in rule and rule["min"] > rule["max"]:
                errors.append(f"{where}: Min ist grösser als Max.")
        elif kind == "pattern":
            pattern = "" if _blank(row.get(COL_PATTERN)) else str(row.get(COL_PATTERN)).strip()
            if not pattern:
                errors.append(f"{where}: Muster fehlt.")
                continue
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{where}: Muster ist ungültig ({exc}).")
                continue
            rule["pattern"] = pattern
        if bool(row.get(COL_REQUIRED)) and kind != "prohibited":
            rule["required"] = True
        if not _blank(row.get(COL_NOTE)):
            rule["instructions"] = str(row.get(COL_NOTE)).strip()
        target = rules.setdefault(cls, {}).setdefault(pset, {})
        if prop in target:
            errors.append(f"{where}: kommt doppelt vor.")
            continue
        target[prop] = rule
    return rules, errors


def save_rules(rules: dict, path: Path = RULES_PATH) -> None:
    """Regeln lesbar als JSON speichern."""
    Path(path).write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reset_rules(path: Path = RULES_PATH, standard: Path = STANDARD_RULES_PATH) -> None:
    """Aktive Regeln mit der Standardvorlage überschreiben."""
    shutil.copyfile(standard, path)


def differences(rules: dict, standard: dict) -> list[str]:
    """Kurze Liste, worin die aktiven Regeln von der Vorlage abweichen."""
    def flat(r):
        return {(c.upper(), p, q): v for c, ps in r.items() for p, qs in ps.items() for q, v in qs.items()}
    a, b = flat(rules), flat(standard)
    out = [f"neu: {k[0]} · {k[1]} · {k[2]}" for k in a.keys() - b.keys()]
    out += [f"entfernt: {k[0]} · {k[1]} · {k[2]}" for k in b.keys() - a.keys()]
    out += [f"geändert: {k[0]} · {k[1]} · {k[2]}" for k in a.keys() & b.keys() if a[k] != b[k]]
    return sorted(out)
