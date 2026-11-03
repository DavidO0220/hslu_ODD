"""Tests für die gemeinsame Änderungsliste von Tabelle und 3D-Viewer."""

from core import ifc_reader, ifc_writer, pending
from core.display import to_display
from core.validator import load_rules, STANDARD_RULES_PATH


def _walls(model):
    return to_display(ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon"))


def _empty_wall(table):
    return table.loc[table["FireRating"].isna()].iloc[0]


def test_put_and_revert():
    store = {}
    pending.put(store, "g1", "Wand", "IfcWall", "Pset_WallCommon", "FireRating", None, "EI60")
    assert len(store) == 1
    pending.put(store, "g1", "Wand", "IfcWall", "Pset_WallCommon", "FireRating", None, "")   # zurück auf leer
    assert store == {}


def test_table_edit_lands_in_store(model):
    original = _walls(model)
    store = {}
    shown = pending.apply(original, store, "Pset_WallCommon")
    edited = shown.copy()
    row = _empty_wall(original)
    edited.loc[edited["GlobalId"] == row["GlobalId"], "FireRating"] = "EI60"
    assert pending.merge_edits(store, original, shown, edited, "IfcWall", "Pset_WallCommon") == 1
    entry = store[(row["GlobalId"], "Pset_WallCommon", "FireRating")]
    assert entry["Alt"] is None and entry["Neu"] == "EI60" and entry["Klasse"] == "IfcWall"


def test_viewer_change_shows_in_table(model):
    original = _walls(model)
    row = _empty_wall(original)
    store = {}
    pending.put(store, row["GlobalId"], row["Name"], "IfcWall", "Pset_WallCommon", "FireRating", None, "EI90")
    shown = pending.apply(original, store, "Pset_WallCommon")
    assert shown.loc[shown["GlobalId"] == row["GlobalId"], "FireRating"].iloc[0] == "EI90"
    # Unverändert zurückgegeben: keine neue Änderung, die alte bleibt
    assert pending.merge_edits(store, original, shown, shown.copy(), "IfcWall", "Pset_WallCommon") == 0
    assert len(store) == 1


def test_validate_all_and_write_across_classes(model_path):
    data = model_path.read_bytes()
    model = ifc_reader.load_model(data)
    props = ifc_reader.element_properties(model)
    wall = next(g for g, p in props.items() if p["cls"] == "IfcWall" and p["psets"]["Pset_WallCommon"].get("FireRating") is None)
    window = next(g for g, p in props.items() if p["cls"] == "IfcWindow")
    store = {}
    pending.put(store, wall, "Wand", "IfcWall", "Pset_WallCommon", "FireRating", None, "EI60")
    pending.put(store, window, "Fenster", "IfcWindow", "Pset_WindowCommon", "ThermalTransmittance", 0.9, "7")  # zu hoch
    pending.put(store, window, "Fenster", "IfcWindow", "Pset_WindowCommon", "IsExternal", "Ja", "Nein")
    checked = pending.validate_all(store, load_rules(STANDARD_RULES_PATH))
    assert sorted(checked["Gueltig"]) == [False, True, True]
    after = ifc_reader.element_properties(ifc_reader.load_model(ifc_writer.apply_changes(data, checked)))
    assert after[wall]["psets"]["Pset_WallCommon"]["FireRating"] == "EI60"
    assert after[window]["psets"]["Pset_WindowCommon"]["IsExternal"] == "Nein"
    assert abs(after[window]["psets"]["Pset_WindowCommon"]["ThermalTransmittance"] - 0.9) < 1e-9


def test_element_properties(model):
    props = ifc_reader.element_properties(model)
    assert len(props) == 28                         # ohne Öffnungen
    stair = next(p for p in props.values() if p["cls"] == "IfcStair")
    assert stair["psets"]["Pset_StairCommon"]["FireRating"] == "R30"
    assert stair["psets"]["Pset_StairCommon"]["IsExternal"] == "Nein"
    assert stair["storey"] == "EG" and stair["qtos"] == {}


def test_typed_values():
    assert pending.typed("0,25", "Zahl") == 0.25
    assert pending.typed("Nein", "Ja/Nein") is False
    assert pending.typed(" EI30 ", "Text") == "EI30"
    for bad, kind in (("abc", "Zahl"), ("vielleicht", "Ja/Nein")):
        try:
            pending.typed(bad, kind)
            raise AssertionError(f"{bad} hätte abgelehnt werden müssen")
        except ValueError:
            pass


def test_create_pset_checks_input():
    store = {}
    n, errors = pending.create_pset(store, [("g1", "W", "IfcWall")], "", [("A", "Zahl", "x"), ("A", "Text", "1")], {})
    assert n == 0 and store == {} and len(errors) == 3   # Name fehlt, Zahl falsch, doppelt


def test_new_pset_written_with_types(model_path):
    """Neues Pset mit Text, Zahl und Ja/Nein an zwei Wänden: Typen stimmen in der IFC-Kopie."""
    data = model_path.read_bytes()
    model = ifc_reader.load_model(data)
    walls = [(w.GlobalId, w.Name, "IfcWall") for w in model.by_type("IfcWall")[:2]]
    store = {}
    n, errors = pending.create_pset(store, walls, "CH_Brandschutz",
                                    [("Nachweis", "Text", "VKF 2015"), ("Dicke", "Zahl", "0,3"), ("Geprueft", "Ja/Nein", "Ja")], {})
    assert errors == [] and n == 6
    checked = pending.validate_all(store, load_rules(STANDARD_RULES_PATH))
    assert checked["Gueltig"].all()
    after = ifc_reader.load_model(ifc_writer.apply_changes(data, checked))
    import ifcopenshell.util.element as eu
    for guid, _, _ in walls:
        props = {p.Name: p for rel in after.by_guid(guid).IsDefinedBy
                 if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.Name == "CH_Brandschutz"
                 for p in rel.RelatingPropertyDefinition.HasProperties}
        assert props["Nachweis"].NominalValue.is_a() == "IfcLabel"
        assert props["Dicke"].NominalValue.is_a() == "IfcReal" and abs(props["Dicke"].NominalValue.wrappedValue - 0.3) < 1e-9
        assert props["Geprueft"].NominalValue.is_a() == "IfcBoolean" and props["Geprueft"].NominalValue.wrappedValue is True
        assert eu.get_psets(after.by_guid(guid))["Pset_WallCommon"]   # bestehendes Pset unverändert da
