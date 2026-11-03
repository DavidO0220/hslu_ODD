"""Modellprüfung: alle Bauteile gegen die Regeln prüfen, nicht nur die Änderungen.

Der Validator prüft Eingaben. Diese Prüfung zeigt dazu, wo das Modell die
Regeln noch nicht erfüllt: fehlende Pflichtwerte und ungültige Werte. Offene
Änderungen werden berücksichtigt, eine korrigierte Eingabe verschwindet also
aus der Liste, sobald sie gültig ist.
"""

import pandas as pd

from core.schema import COL_CLASS, COL_GLOBAL_ID, COL_NAME, COL_NEW, COL_PROPERTY, COL_PSET, COL_STOREY
from core.validator import check_value, rules_for_class

COL_VALUE = "Wert"
COL_PROBLEM = "Problem"
COL_STATE = "Stand"
CHECK_COLUMNS = [COL_CLASS, COL_NAME, COL_STOREY, COL_PSET, COL_PROPERTY, COL_VALUE, COL_PROBLEM, COL_STATE, COL_GLOBAL_ID]


def check_model(properties: dict, rules: dict, store: dict | None = None) -> pd.DataFrame:
    """Alle Regelverstösse im aktuellen Stand (Modell plus offene Änderungen).

    properties: Ergebnis von ifc_reader.element_properties
    store:      gemeinsame Änderungsliste (core.pending), optional
    """
    store = store or {}
    rows = []
    for guid, info in properties.items():
        for pset, props in rules_for_class(rules, info["cls"]).items():
            for prop, rule in props.items():
                key = (guid, pset, prop)
                if key in store:
                    value, state = store[key][COL_NEW], "offene Änderung"
                else:
                    value, state = info["psets"].get(pset, {}).get(prop), "Modell"
                ok, message, _ = check_value(value, rule)
                if ok:
                    continue
                rows.append({COL_CLASS: info["cls"], COL_NAME: info["name"], COL_STOREY: info["storey"],
                             COL_PSET: pset, COL_PROPERTY: prop, COL_VALUE: value,
                             COL_PROBLEM: message, COL_STATE: state, COL_GLOBAL_ID: guid})
    frame = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    return frame.sort_values([COL_CLASS, COL_PSET, COL_PROPERTY, COL_STOREY, COL_NAME], kind="stable").reset_index(drop=True)
