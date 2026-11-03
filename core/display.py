"""Anzeige: Tabelle für die Oberfläche aufbereiten.

Ja/Nein-Properties (IfcBoolean) werden als Text "Ja"/"Nein" angezeigt. So kann
die Oberfläche sie als Auswahlfeld darstellen, und leere Werte bleiben leer.
Original- und bearbeitete Tabelle werden beide in dieser Form verglichen.
"""

import pandas as pd

from core.schema import LOCKED_COLUMNS

YES, NO = "Ja", "Nein"


def bool_columns(table: pd.DataFrame) -> list[str]:
    """Spalten, deren nicht-leere Werte alle True/False sind."""
    result = []
    for col in table.columns:
        if col in LOCKED_COLUMNS:
            continue
        values = [v for v in table[col] if v is not None and not pd.isna(v)]
        if values and all(isinstance(v, bool) for v in values):
            result.append(col)
    return result


def to_display(table: pd.DataFrame) -> pd.DataFrame:
    """Kopie der Tabelle, in der True/False durch Ja/Nein ersetzt ist."""
    shown = table.copy()
    for col in bool_columns(table):
        shown[col] = [None if v is None or pd.isna(v) else (YES if v else NO) for v in table[col]]
    return shown


def add_columns(table: pd.DataFrame, names) -> pd.DataFrame:
    """Leere Spalten für Properties ergänzen, die laut Regeln fehlen (zum Nachtragen)."""
    out = table.copy()
    for name in names:
        if name not in out.columns:
            out[name] = pd.Series([None] * len(out), index=out.index, dtype=object)
    return out
