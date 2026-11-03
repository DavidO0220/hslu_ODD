"""Tests für Phase 3: Rückschreiben. Der wichtigste Test ist der Rundlauf."""

from core import diff, ifc_reader, ifc_writer
from core.display import to_display
from core.validator import load_rules, validate, STANDARD_RULES_PATH


def _roundtrip(model_path, edit):
    original_bytes = model_path.read_bytes()
    model = ifc_reader.load_model(original_bytes)
    table = to_display(ifc_reader.to_table(model, "IfcWall", "Pset_WallCommon"))
    edited = table.copy()
    edit(edited)
    changes = validate(diff.find_changes(table, edited, "Pset_WallCommon"), "IfcWall", load_rules(STANDARD_RULES_PATH))
    new_bytes = ifc_writer.apply_changes(original_bytes, changes)
    new_model = ifc_reader.load_model(new_bytes)
    return changes, ifc_reader.to_table(new_model, "IfcWall", "Pset_WallCommon"), original_bytes


def test_valid_value_written_invalid_skipped(model_path):
    def edit(t):
        empty = t.index[t["FireRating"].isna()]
        t.loc[empty[0], "FireRating"] = "EI60"   # gültig
        t.loc[empty[1], "FireRating"] = "EI45"   # ungültig, darf nicht geschrieben werden
    changes, after, _ = _roundtrip(model_path, edit)
    assert sorted(changes["Gueltig"]) == [False, True]
    assert after["FireRating"].isna().sum() == 1          # vorher 2 leer, 1 befüllt
    assert (after["FireRating"] == "EI60").sum() == 2     # EG-Innenwand hatte schon EI60
    assert (after["FireRating"] == "EI45").sum() == 1     # nur der Wert aus dem Modell


def test_bool_stays_bool(model_path):
    def edit(t):
        t.loc[t["IsExternal"] == "Ja", "IsExternal"] = "Nein"
    _, after, _ = _roundtrip(model_path, edit)
    assert set(after["IsExternal"]) == {False}
    assert all(isinstance(v, bool) for v in after["IsExternal"])


def test_original_bytes_unchanged(model_path):
    before = model_path.read_bytes()
    _roundtrip(model_path, lambda t: t.__setitem__("FireRating", "EI30"))
    assert model_path.read_bytes() == before


def test_delete_value(model_path):
    def edit(t):
        t.loc[t["FireRating"] == "EI45", "FireRating"] = None
    _, after, _ = _roundtrip(model_path, edit)
    assert (after["FireRating"] == "EI45").sum() == 0


def _model_with_shared_pset(model_path, tmp_path):
    """Testmodell plus ein Pset 'Pset_Projekt', das an zwei Wänden gemeinsam hängt."""
    import ifcopenshell
    import ifcopenshell.guid
    model = ifcopenshell.open(str(model_path))
    walls = model.by_type("IfcWall")[:2]
    prop = model.create_entity("IfcPropertySingleValue", Name="Code", NominalValue=model.create_entity("IfcLabel", "A"))
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_Projekt", HasProperties=[prop])
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=walls, RelatingPropertyDefinition=pset)
    path = tmp_path / "geteilt.ifc"
    model.write(str(path))
    return path.read_bytes(), [w.GlobalId for w in walls]


def test_shared_pset_is_unshared(model_path, tmp_path):
    data, (g1, g2) = _model_with_shared_pset(model_path, tmp_path)
    table = to_display(ifc_reader.to_table(ifc_reader.load_model(data), "IfcWall", "Pset_Projekt"))
    edited = table.copy()
    edited.loc[edited["GlobalId"] == g1, "Code"] = "B"
    changes = validate(diff.find_changes(table, edited, "Pset_Projekt"), "IfcWall", load_rules(STANDARD_RULES_PATH))
    after = ifc_reader.to_table(ifc_reader.load_model(ifc_writer.apply_changes(data, changes)), "IfcWall", "Pset_Projekt")
    code = dict(zip(after["GlobalId"], after["Code"]))
    assert code[g1] == "B"
    assert code[g2] == "A"   # die andere Wand ist nicht mitgeändert


def test_missing_pset_is_created(model_path, tmp_path):
    data, (g1, g2) = _model_with_shared_pset(model_path, tmp_path)
    table = to_display(ifc_reader.to_table(ifc_reader.load_model(data), "IfcWall", "Pset_Projekt"))
    other = table.loc[~table["GlobalId"].isin([g1, g2]), "GlobalId"].iloc[0]
    edited = table.copy()
    edited.loc[edited["GlobalId"] == other, "Code"] = "C"
    changes = validate(diff.find_changes(table, edited, "Pset_Projekt"), "IfcWall", load_rules(STANDARD_RULES_PATH))
    after = ifc_reader.to_table(ifc_reader.load_model(ifc_writer.apply_changes(data, changes)), "IfcWall", "Pset_Projekt")
    assert dict(zip(after["GlobalId"], after["Code"]))[other] == "C"


def test_window_u_value_float(model_path):
    """Zahl-Regel: fehlender U-Wert wird als Zahl geschrieben, ein Wert ausserhalb der Grenzen nicht."""
    original_bytes = model_path.read_bytes()
    table = to_display(ifc_reader.to_table(ifc_reader.load_model(original_bytes), "IfcWindow", "Pset_WindowCommon"))
    edited = table.copy()
    empty = edited.index[edited["ThermalTransmittance"].isna()][0]
    other = edited.index[edited["ThermalTransmittance"].notna()][0]
    edited.loc[empty, "ThermalTransmittance"] = "1,1"     # Komma wie in der Schweiz üblich
    edited.loc[other, "ThermalTransmittance"] = "5"       # über dem Maximum 3.0
    changes = validate(diff.find_changes(table, edited, "Pset_WindowCommon"), "IfcWindow", load_rules(STANDARD_RULES_PATH))
    assert sorted(changes["Gueltig"]) == [False, True]
    after = ifc_reader.to_table(ifc_reader.load_model(ifc_writer.apply_changes(original_bytes, changes)), "IfcWindow", "Pset_WindowCommon")
    u = dict(zip(after["GlobalId"], after["ThermalTransmittance"]))
    assert abs(u[table.loc[empty, "GlobalId"]] - 1.1) < 1e-9
    assert abs(u[table.loc[other, "GlobalId"]] - 0.9) < 1e-9
