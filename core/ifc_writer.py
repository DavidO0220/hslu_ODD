"""Writer: gültige Änderungen in eine Kopie des IFC schreiben (Phase 3)."""

import os
import tempfile

import ifcopenshell
import ifcopenshell.api.pset
import ifcopenshell.util.element as element_util
import pandas as pd

from core.ifc_reader import load_model
from core.schema import COL_GLOBAL_ID, COL_NEW, COL_PROPERTY, COL_PSET, COL_VALID
from core.validator import to_bool


def _existing_types(pset) -> dict:
    """Datentyp jedes bestehenden Properties, z. B. {'IsExternal': 'IfcBoolean'}."""
    types = {}
    for prop in pset.HasProperties or ():
        if prop.is_a("IfcPropertySingleValue") and prop.NominalValue is not None:
            types[prop.Name] = prop.NominalValue.is_a()
    return types


def _prepare(value, ifc_type):
    """Bringt den Wert in die Python-Form, die IfcOpenShell für den Typ braucht.

    Wichtig: IfcOpenShell wandelt Werte mit bool(...) um, und bool("Nein") ist
    True. Ja/Nein-Werte müssen deshalb hier schon echte bools sein.
    """
    if hasattr(value, "item") and not isinstance(value, str):
        value = value.item()
    if value is None:
        return None
    if ifc_type == "IfcBoolean":
        as_bool = to_bool(value)
        if as_bool is None:
            raise ValueError(f"'{value}' ist kein Ja/Nein-Wert")
        return as_bool
    return value


def _pset_for(model, element, pset_name):
    """Liefert das Pset des Bauteils. Fehlt es, wird es angelegt.

    Hängt das Pset an mehreren Bauteilen, wird für dieses Bauteil eine eigene
    Kopie erstellt. Sonst würde eine Änderung alle Bauteile betreffen.
    """
    psets = element_util.get_psets(element, psets_only=True, should_inherit=False)
    if pset_name not in psets:
        return ifcopenshell.api.pset.add_pset(model, product=element, name=pset_name)
    pset = model.by_id(psets[pset_name]["id"])
    if len(element_util.get_elements_by_pset(pset)) > 1:
        pset = ifcopenshell.api.pset.unshare_pset(model, products=[element], pset=pset)[0]
    return pset


def apply_changes(original_bytes: bytes, changes: pd.DataFrame) -> bytes:
    """Schreibt die gültigen Änderungen in eine NEUE Kopie und gibt sie als Bytes zurück.

    Das Modell wird frisch aus original_bytes geöffnet. Das gecachte Modell der
    Oberfläche bleibt unverändert, sonst stimmt der Vergleich alt/neu nicht mehr.
    """
    model = load_model(original_bytes)
    todo = changes[changes[COL_VALID]] if COL_VALID in changes.columns else changes

    for (guid, pset_name), group in todo.groupby([COL_GLOBAL_ID, COL_PSET], sort=False):
        element = model.by_guid(guid)
        pset = _pset_for(model, element, pset_name)
        types = _existing_types(pset)
        properties = {row[COL_PROPERTY]: _prepare(row[COL_NEW], types.get(row[COL_PROPERTY])) for _, row in group.iterrows()}
        ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=properties)

    handle, tmp_path = tempfile.mkstemp(suffix=".ifc")
    os.close(handle)
    try:
        model.write(tmp_path)
        ifcopenshell.open(tmp_path)  # Kontrolle: Datei lässt sich wieder öffnen
        with open(tmp_path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(tmp_path)
