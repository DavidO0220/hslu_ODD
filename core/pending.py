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
- Neues Property-Set: create_pset() merkt dasselbe Pset für mehrere Bauteile vor.
- Prüfen und Speichern: validate_all() über alle Klassen.
"""

import pandas as pd

from core.diff import _same, find_changes, normalize
from core.schema import (CHANGE_COLUMNS, COL_CLASS, COL_GLOBAL_ID, COL_NAME, COL_NEW, COL_OLD,
                         COL_PROPERTY, COL_PSET, VALIDATED_COLUMNS)
from core.validator import to_bool, validate

STORE_COLUMNS = CHANGE_COLUMNS + [COL_CLASS]

# Typen für Properties eines neuen Psets. Der Python-Typ bestimmt beim Schreiben
# den IFC-Typ: Text -> IfcLabel, Zahl -> IfcReal, Ja/Nein -> IfcBoolean.
KIND_TEXT, KIND_NUMBER, KIND_BOOL = "Text", "Zahl", "Ja/Nein"
KINDS = [KIND_TEXT, KIND_NUMBER, KIND_BOOL]
RULE_KIND = {"enum": KIND_TEXT, "float": KIND_NUMBER, "bool": KIND_BOOL}


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


def typed(value, kind: str):
    """Eingabe aus dem Formular in den Python-Typ bringen, der den IFC-Typ bestimmt.

    Wirft ValueError, wenn der Wert nicht zum Typ passt.
    """
    value = normalize(value)
    if value is None:
        return None
    if kind == KIND_NUMBER:
        if isinstance(value, bool):
            raise ValueError(value)
        return float(str(value).replace(",", "."))
    if kind == KIND_BOOL:
        as_bool = to_bool(value)
        if as_bool is None:
            raise ValueError(value)
        return as_bool
    return str(value)


def create_pset(store: dict, elements: list[tuple[str, str, str]], pset_name: str,
                rows: list[tuple], pset_rules: dict) -> tuple[int, list[str]]:
    """Ein neues Property-Set für mehrere Bauteile vormerken.

    elements:   [(GlobalId, Name, Klasse)] der Bauteile, die das Pset bekommen
    rows:       [(Property, Typ, Wert)] mit Typ aus KINDS, gleicher Wert für alle Bauteile
    pset_rules: Regeln für dieses Pset ({Property: Regel}), sonst {}

    Properties mit Regel bleiben Text, der Validator prüft und wandelt sie
    später. Alle anderen werden hier in ihren Typ umgewandelt.
    Rückgabe: (Anzahl vorgemerkter Werte, Fehlermeldungen). Bei Fehlern wird nichts eingetragen.
    """
    errors, cleaned, seen = [], [], set()
    name = normalize(pset_name)
    if not name:
        errors.append("Der Name des Property-Sets fehlt.")
    for prop, kind, value in rows:
        prop, value = normalize(prop), normalize(value)
        if prop is None:
            if value is not None:
                errors.append("Eine Zeile hat einen Wert, aber keinen Property-Namen.")
            continue
        if prop in seen:
            errors.append(f"«{prop}» kommt doppelt vor.")
            continue
        seen.add(prop)
        if value is None:
            errors.append(f"«{prop}» hat keinen Wert.")
            continue
        if prop in pset_rules:
            cleaned.append((prop, str(value)))
            continue
        try:
            cleaned.append((prop, typed(value, kind or KIND_TEXT)))
        except ValueError:
            errors.append(f"«{prop}»: «{value}» passt nicht zum Typ {kind}.")
    if not cleaned and not errors:
        errors.append("Mindestens ein Property mit Wert eintragen.")
    if not elements:
        errors.append("Es ist kein Bauteil ausgewählt.")
    if errors:
        return 0, errors
    for guid, element_name, ifc_class in elements:
        for prop, value in cleaned:
            put(store, guid, element_name, ifc_class, name, prop, None, value)
    return len(elements) * len(cleaned), []
