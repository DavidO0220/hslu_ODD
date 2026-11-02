"""Offene Änderungen: eine gemeinsame Liste für Tabelle und 3D-Viewer.

Jede Änderung ist eindeutig durch (GlobalId, Pset, Property). Werte stehen in
Anzeigeform, also Ja/Nein als Text, genau wie in der Tabelle. Der Validator
bringt sie später in die Form zum Schreiben.

Die Liste ist ein normales dict. Die Oberfläche legt es in st.session_state ab,
dieses Modul kennt Streamlit nicht.

Ablauf in der Oberfläche:
- Tabelle: apply() zeigt die offenen Änderungen in der Tabelle, merge_edits()
  übernimmt neue Eingaben aus dem Tabelleneditor in die Liste.
- 3D-Viewer: put() für jede Eingabe im Pop-up.
- Prüfen und Speichern: validate_all() über alle Klassen.
"""

import pandas as pd

from core.diff import _same, find_changes, normalize
from core.schema import (CHANGE_COLUMNS, COL_CLASS, COL_GLOBAL_ID, COL_NAME, COL_NEW, COL_OLD,
                         COL_PROPERTY, COL_PSET, VALIDATED_COLUMNS)
from core.validator import validate

STORE_COLUMNS = CHANGE_COLUMNS + [COL_CLASS]


def put(store: dict, guid: str, name: str, ifc_class: str, pset: str, prop: str, old, new) -> None:
    """Änderung eintragen. Ist der neue Wert wieder der Originalwert, fällt sie weg."""
    old, new = normalize(old), normalize(new)
    key = (guid, pset, prop)
    if _same(old, new):
        store.pop(key, None)
        return
    store[key] = {COL_GLOBAL_ID: guid, COL_NAME: name, COL_PSET: pset, COL_PROPERTY: prop,
                  COL_OLD: old, COL_NEW: new, COL_CLASS: ifc_class}


def apply(table: pd.DataFrame, store: dict, pset: str) -> pd.DataFrame:
    """Kopie der Tabelle, in der die offenen Änderungen dieses Psets schon eingetragen sind."""
    out = table.copy()
    rows = {guid: idx for idx, guid in zip(out.index, out[COL_GLOBAL_ID])}
    for (guid, change_pset, prop), entry in store.items():
        if change_pset == pset and guid in rows and prop in out.columns:
            out.at[rows[guid], prop] = entry[COL_NEW]
    return out


def merge_edits(store: dict, original: pd.DataFrame, shown: pd.DataFrame, edited: pd.DataFrame,
                ifc_class: str, pset: str) -> int:
    """Neue Eingaben aus dem Tabelleneditor übernehmen.

    original: Tabelle aus dem Modell, shown: was der Editor gezeigt hat
    (original + offene Änderungen), edited: was der Editor zurückgibt.
    Rückgabe: Anzahl übernommener Zellen.
    """
    changes = find_changes(shown, edited, pset)
    if changes.empty:
        return 0
    base = original.set_index(COL_GLOBAL_ID)
    for _, c in changes.iterrows():
        put(store, c[COL_GLOBAL_ID], c[COL_NAME], ifc_class, pset, c[COL_PROPERTY],
            base.at[c[COL_GLOBAL_ID], c[COL_PROPERTY]], c[COL_NEW])
    return len(changes)


def to_frame(store: dict) -> pd.DataFrame:
    """Die Liste als Tabelle, sortiert nach Klasse, Name, Pset, Property."""
    frame = pd.DataFrame(list(store.values()), columns=STORE_COLUMNS)
    return frame.sort_values([COL_CLASS, COL_NAME, COL_PSET, COL_PROPERTY], kind="stable").reset_index(drop=True)


def validate_all(store: dict, rules: dict) -> pd.DataFrame:
    """Alle offenen Änderungen prüfen, jede mit den Regeln ihrer Klasse."""
    frame = to_frame(store)
    if frame.empty:
        return pd.DataFrame(columns=VALIDATED_COLUMNS + [COL_CLASS])
    parts = []
    for ifc_class, group in frame.groupby(COL_CLASS, sort=False):
        checked = validate(group[CHANGE_COLUMNS], ifc_class, rules)
        checked[COL_CLASS] = ifc_class
        parts.append(checked)
    return pd.concat(parts, ignore_index=True)
