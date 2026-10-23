"""Reader: IFC-Modell laden und als Tabelle bereitstellen (Phase 1)."""

import os
import tempfile

import ifcopenshell
import ifcopenshell.util.element as element_util
import pandas as pd

from core.schema import COL_GLOBAL_ID, COL_NAME, COL_STOREY, FIXED_COLUMNS


def load_model_from_path(path: str) -> ifcopenshell.file:
    """Öffnet eine IFC-Datei von der Festplatte."""
    return ifcopenshell.open(str(path))


def load_model(file_bytes: bytes) -> ifcopenshell.file:
    """Öffnet eine IFC-Datei aus dem Upload der Oberfläche.

    IfcOpenShell braucht einen Dateipfad, deshalb wird der Upload kurz in eine
    temporäre Datei geschrieben. Auf Windows muss die Datei geschlossen sein,
    bevor sie geöffnet werden kann, daher mkstemp statt NamedTemporaryFile.
    """
    handle, tmp_path = tempfile.mkstemp(suffix=".ifc")
    try:
        with os.fdopen(handle, "wb") as tmp:
            tmp.write(file_bytes)
        return ifcopenshell.open(tmp_path)
    finally:
        os.remove(tmp_path)


def list_classes(model: ifcopenshell.file) -> list[str]:
    """Alle Bauteilklassen im Modell, z. B. ['IfcDoor', 'IfcSlab', 'IfcWall']."""
    return sorted({element.is_a() for element in model.by_type("IfcElement")})


def _psets_of(element) -> dict:
    """Property-Sets direkt am Bauteil, ohne Mengen und ohne Werte vom Typ.

    should_inherit=False: Werte, die nur am Bauteiltyp hängen, werden nicht
    angezeigt, weil der Writer später nur am Bauteil selbst schreibt.
    """
    return element_util.get_psets(element, psets_only=True, should_inherit=False)


def list_psets(model: ifcopenshell.file, ifc_class: str) -> list[str]:
    """Alle Property-Set-Namen, die an Bauteilen dieser Klasse vorkommen."""
    names = set()
    for element in model.by_type(ifc_class):
        names.update(_psets_of(element).keys())
    return sorted(names)


def _storey_name(element) -> str:
    """Name des Geschosses, in dem das Bauteil liegt, sonst leer."""
    container = element_util.get_container(element)
    return container.Name if container is not None and container.Name else ""


def to_table(model: ifcopenshell.file, ifc_class: str, pset_name: str) -> pd.DataFrame:
    """Baut die Tabelle für die Oberfläche: eine Zeile pro Bauteil.

    Spalten: GlobalId, Name, Geschoss und danach eine Spalte pro Property des
    gewählten Psets. Fehlt ein Property an einem Bauteil, ist die Zelle leer
    (None). Die Spalte 'id', die IfcOpenShell intern mitliefert, wird entfernt.
    """
    rows = []
    property_names = set()
    for element in model.by_type(ifc_class):
        values = dict(_psets_of(element).get(pset_name, {}))
        values.pop("id", None)
        property_names.update(values.keys())
        rows.append({
            COL_GLOBAL_ID: element.GlobalId,
            COL_NAME: element.Name or "",
            COL_STOREY: _storey_name(element),
            **values,
        })

    columns = FIXED_COLUMNS + sorted(property_names)
    table = pd.DataFrame(rows, columns=columns)
    table = table.astype(object).where(table.notna(), None)
    return table.sort_values([COL_STOREY, COL_NAME], kind="stable").reset_index(drop=True)
