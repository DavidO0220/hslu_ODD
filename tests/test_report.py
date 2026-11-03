"""Tests für die Bauteilliste (Excel-Arbeitsmappe nach dem Speichern)."""

import io
from datetime import datetime

import pytest
from openpyxl import load_workbook

from core import ifc_reader, ifc_writer, model_check, pending, report
from core.validator import load_rules, STANDARD_RULES_PATH

NOW = datetime(2026, 11, 3, 11, 20)


@pytest.fixture(scope="module")
def result(model_path):
    """Drei Eingaben: eine gültige Wand, eine abgelehnte Wand, ein neues Pset an allen Türen."""
    rules = load_rules(STANDARD_RULES_PATH)
    rules["IfcWall"]["Pset_WallCommon"]["FireRating"]["required"] = True   # damit leere Wände offen sind
    original = model_path.read_bytes()
    model = ifc_reader.load_model(original)
    before = ifc_reader.element_properties(model)
    walls = [(g, p) for g, p in before.items() if p["cls"] == "IfcWall"]
    empty = [(g, p) for g, p in walls if p["psets"].get("Pset_WallCommon", {}).get("FireRating") is None]
    store = {}
    g1, p1 = empty[0]
    g2, p2 = empty[1]
    pending.put(store, g1, p1["name"], "IfcWall", "Pset_WallCommon", "FireRating", None, "EI60",
                pending.SOURCE_TABLE, now=NOW)
    pending.put(store, g2, p2["name"], "IfcWall", "Pset_WallCommon", "FireRating", None, "EI45",
                pending.SOURCE_3D, now=NOW)
    doors = [(g, p["name"], "IfcDoor") for g, p in before.items() if p["cls"] == "IfcDoor"]
    pending.create_pset(store, doors, "CH_Brandschutz", [("Nachweis", "Text", "VKF 2015")], {})
    validated = pending.validate_all(store, rules)
    copy = ifc_writer.apply_changes(original, validated)
    after = ifc_reader.element_properties(ifc_reader.load_model(copy))
    data = report.build_workbook(
        file_name="testmodell.ifc", copy_name="testmodell_bearbeitet.ifc", original_bytes=original,
        copy_bytes=copy, props_before=before, props_after=after, validated=validated, rules=rules,
        rules_label="config/rules.json (14 Regeln)", user="Brandschutzplanung", now=NOW,
        storeys=ifc_reader.storey_order(model), schema=model.schema)
    wb = load_workbook(io.BytesIO(data))
    return {"wb": wb, "before": before, "after": after, "rules": rules, "g1": g1, "g2": g2,
            "validated": validated, "original": original, "copy": copy}


def _cells(ws):
    return [[c.value for c in row] for row in ws.iter_rows()]


def _find(ws, text):
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == text:
                return cell
    raise AssertionError(f"«{text}» nicht gefunden")


def test_sheet_order(result):
    names = result["wb"].sheetnames
    assert names[0] == "Übersicht"
    assert names[-2:] == ["Legende", "Änderungen"]
    assert names[1:-2] == ["Wände", "Decken", "Türen", "Fenster", "Treppen"]


def test_overview_counts(result):
    ws = result["wb"]["Übersicht"]
    issues_before = model_check.check_model(result["before"], result["rules"])
    issues_after = model_check.check_model(result["after"], result["rules"])
    label = _find(ws, "Offene Werte")
    assert ws.cell(label.row, 2).value == str(len(issues_before))
    assert ws.cell(label.row, 3).value == str(len(issues_after))
    assert len(issues_after) == len(issues_before) - 1          # eine Lücke geschlossen
    changed = _find(ws, "Geänderte Werte · Bauteile")
    assert ws.cell(changed.row, 3).value == "4 Werte · 4 Bauteile"   # 1 Wand + 3 Türen
    new = _find(ws, "Neue Property-Sets")
    assert ws.cell(new.row, 3).value == "CH_Brandschutz an 3 Bauteilen"
    assert _find(ws, report.sha256(result["copy"])).value != report.sha256(result["original"])


def test_overview_links_to_class_sheets(result):
    ws = result["wb"]["Übersicht"]
    link = _find(ws, "Wände →")
    assert link.hyperlink.location == "'Wände'!A1" or link.hyperlink.target == "#'Wände'!A1"
    total = _find(ws, "Total")
    assert ws.cell(total.row, 3).value == len(result["after"])


def test_rejected_listed_on_overview(result):
    ws = result["wb"]["Übersicht"]
    flat = [v for row in _cells(ws) for v in row]
    assert "EI45" in flat
    assert any(isinstance(v, str) and "nicht in der Werteliste" in v for v in flat)


def test_class_sheet_marks_changes_and_gaps(result):
    ws = result["wb"]["Wände"]
    assert [c.value for c in ws[2]][:4] == ["Geschoss", "Bauteil", "GlobalId", "FireRating"]
    assert ws["D1"].value == "Pset_WallCommon"
    row_of = {ws.cell(r, 3).value: r for r in range(3, ws.max_row + 1)}
    r1, r2 = row_of[result["g1"]], row_of[result["g2"]]
    assert ws.cell(r1, 4).value == "leer → EI60"
    assert ws.cell(r1, 4).fill.start_color.rgb.endswith(report.GREEN)
    assert ws.cell(r2, 4).value == "leer"                       # abgelehnt, im Modell weiter leer
    assert ws.cell(r2, 4).fill.start_color.rgb.endswith(report.RED)
    assert ws.cell(r2, 4).comment is not None
    stand = ws.cell(r2, ws.max_column).value
    assert stand.startswith("✗ offen") and ws.cell(r1, ws.max_column).value == "✓ erfüllt"
    assert ws.freeze_panes == "D3"


def test_new_pset_column_on_door_sheet(result):
    ws = result["wb"]["Türen"]
    headers = [c.value for c in ws[2]]
    assert "Nachweis" in headers
    col = headers.index("Nachweis") + 1
    assert {ws.cell(r, col).value for r in range(3, ws.max_row + 1)} == {"leer → VKF 2015"}


def test_storeys_sorted_bottom_up(result):
    ws = result["wb"]["Wände"]
    storeys = [ws.cell(r, 1).value for r in range(3, ws.max_row + 1)]
    order = list(dict.fromkeys(storeys))
    assert order == [s for s in ifc_reader.storey_order(ifc_reader.load_model(result["original"])) if s in order]


def test_changes_sheet_has_all_inputs(result):
    ws = result["wb"]["Änderungen"]
    rows = _cells(ws)
    assert rows[0] == report.CHANGE_HEADERS
    body = rows[1:]
    assert len(body) == len(result["validated"]) == 5
    status = report.CHANGE_HEADERS.index("Status")
    source = report.CHANGE_HEADERS.index("Eingabe über")
    assert sorted(r[status] for r in body) == ["abgelehnt"] + ["gespeichert"] * 4
    assert {r[source] for r in body} == {"Tabelle", "3D-Modell", "Neues Pset"}
    entered = report.CHANGE_HEADERS.index("Erfasst")
    assert "2026-11-03 11:20" in {r[entered] for r in body}


def test_legend_lists_rules(result):
    ws = result["wb"]["Legende"]
    flat = [v for row in _cells(ws) for v in row]
    assert "Werteliste: EI30, EI60, EI90" in flat
    assert "Zahl zwischen 0.3 und 3" in flat


def test_sheet_names_unique_and_valid():
    names = report.sheet_names(["IfcWall", "IfcWallStandardCase", "IfcFlowTerminal", "IfcA/B"])
    assert len(set(names.values())) == 4
    assert all(len(n) <= 31 and not set(n) & set("[]:*?/\\") for n in names.values())


def test_put_keeps_first_entry_time():
    store = {}
    pending.put(store, "g", "W", "IfcWall", "P", "X", None, "A", "Tabelle", now=datetime(2026, 1, 1, 8, 0))
    pending.put(store, "g", "W", "IfcWall", "P", "X", None, "A", "Tabelle", now=datetime(2026, 1, 1, 9, 0))
    assert store[("g", "P", "X")]["Erfasst"] == "2026-01-01 08:00"
    pending.put(store, "g", "W", "IfcWall", "P", "X", None, "B", "3D-Modell", now=datetime(2026, 1, 1, 9, 0))
    assert store[("g", "P", "X")]["Erfasst"] == "2026-01-01 09:00"
    assert pending.remove(store, [("g", "P", "X")]) == 1 and store == {}
