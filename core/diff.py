"""Diff: Änderungen zwischen Original- und bearbeiteter Tabelle finden (Phase 2)."""

import math

import pandas as pd

from core.schema import (CHANGE_COLUMNS, COL_GLOBAL_ID, COL_NAME, COL_NEW, COL_OLD,
                         COL_PROPERTY, COL_PSET, LOCKED_COLUMNS)


def normalize(value):
    """Einheitliche Form für Vergleiche: leer wird None, Text ohne Leerzeichen am Rand.

    Aus der Oberfläche kommen leere Zellen als None, NaN oder '' an, und Zahlen
    teilweise als numpy-Typen. Alles wird hier auf normale Python-Werte gebracht.
    """
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()  # numpy -> Python
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        # Streamlit wandelt Spalten mit gemischten Typen in Text um. Leere Zellen
        # kommen dann als "None", "nan" oder "<NA>" an.
        return None if value in ("", "None", "nan", "NaN", "<NA>") else value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _as_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _same(a, b) -> bool:
    """Gleichheit mit Toleranz: 0.25 und "0.25" gelten als gleich."""
    if a is None or b is None:
        return a is None and b is None
    if type(a) is type(b):
        if isinstance(a, float):
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        return a == b
    x, y = _as_number(a), _as_number(b)
    if x is not None and y is not None:
        return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)
    return str(a) == str(b)


def find_changes(original: pd.DataFrame, edited: pd.DataFrame, pset_name: str) -> pd.DataFrame:
    """Vergleicht zwei Tabellen und liefert nur die geänderten Zellen.

    Zeilen werden über die GlobalId zugeordnet, nicht über die Position.
    Gesperrte Spalten (GlobalId, Name, Geschoss) werden nicht verglichen.
    Rückgabe: Spalten CHANGE_COLUMNS, eine Zeile pro geänderter Zelle.
    """
    properties = [c for c in original.columns if c not in LOCKED_COLUMNS and c in edited.columns]
    old_rows = original.set_index(COL_GLOBAL_ID)
    new_rows = edited.set_index(COL_GLOBAL_ID)

    changes = []
    for guid in old_rows.index:
        if guid not in new_rows.index:
            continue
        for prop in properties:
            old = normalize(old_rows.at[guid, prop])
            new = normalize(new_rows.at[guid, prop])
            if not _same(old, new):
                changes.append({
                    COL_GLOBAL_ID: guid,
                    COL_NAME: old_rows.at[guid, COL_NAME],
                    COL_PSET: pset_name,
                    COL_PROPERTY: prop,
                    COL_OLD: old,
                    COL_NEW: new,
                })
    return pd.DataFrame(changes, columns=CHANGE_COLUMNS)
