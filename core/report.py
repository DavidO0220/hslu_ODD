"""Bauteilliste als Excel-Arbeitsmappe (Ergebnis von «Speichern»).

Aufbau der Mappe:
1. Übersicht   Datei, Prüfsummen, Regeln, Ergebnis vorher/nachher, eine Zeile
               pro Bauteilklasse mit Link auf ihr Blatt, abgelehnte Eingaben, Visum
2. … ein Blatt pro Bauteilklasse: eine Zeile pro Bauteil, die geprüften und
               geänderten Properties nebeneinander, gruppiert nach Property-Set.
               Geändert grün mit «alt → neu», Regel nicht erfüllt rot.
3. Legende     Farben und die verwendeten Regeln
4. Änderungen  jede Eingabe, gespeichert oder abgelehnt, mit Herkunft und Zeit

Der Stand «nachher» wird aus der geschriebenen IFC-Kopie gelesen, nicht aus der
Änderungsliste. Die Mappe zeigt also, was wirklich in der Datei steht.
Dieses Modul kennt Streamlit nicht.
"""

import hashlib
import io
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core import model_check
from core.display import NO, YES
from core.schema import (COL_CLASS, COL_ENTERED, COL_GLOBAL_ID, COL_MESSAGE, COL_NAME, COL_NEW, COL_OLD,
                         COL_PROPERTY, COL_PSET, COL_SOURCE, COL_VALID)
from core.validator import rules_for_class

# Blattnamen für die häufigen Klassen, sonst der IFC-Name ohne «Ifc»
PLURAL = {
    "IfcWall": "Wände", "IfcWallStandardCase": "Wände", "IfcSlab": "Decken", "IfcDoor": "Türen",
    "IfcWindow": "Fenster", "IfcStair": "Treppen", "IfcStairFlight": "Treppenläufe", "IfcColumn": "Stützen",
    "IfcBeam": "Träger", "IfcRoof": "Dächer", "IfcRailing": "Geländer", "IfcCovering": "Bekleidungen",
    "IfcCurtainWall": "Vorhangfassaden", "IfcPlate": "Platten", "IfcMember": "Profile", "IfcRamp": "Rampen",
    "IfcFooting": "Fundamente", "IfcPile": "Pfähle", "IfcBuildingElementProxy": "Proxy-Bauteile",
    "IfcFurnishingElement": "Mobiliar", "IfcFurniture": "Mobiliar", "IfcSpace": "Räume",
}

# Farben (dieselben wie in der App: grün geändert, rot offen)
GREEN, GREEN_TEXT = "DFF3E8", "0F6E56"
RED, RED_TEXT = "FBE3E1", "B3261E"
HEAD, HEAD_TEXT = "1F3A4D", "FFFFFF"
GROUP = "DCE6EE"
MUTED = "6B7780"
BAR = "0F6E56"

_FILL = lambda color: PatternFill("solid", start_color=color, end_color=color)  # noqa: E731
_THIN = Side(style="thin", color="C9D1D8")
_BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_ARROW = " → "

SHEET_OVERVIEW, SHEET_LEGEND, SHEET_CHANGES = "Übersicht", "Legende", "Änderungen"
CHANGE_HEADERS = ["Nr", "Erfasst", "Bearbeitet von", "Geschoss", "Klasse", "Bauteil", "GlobalId",
                  "Property-Set", "Property", "Alt", "Neu", "Status", "Eingabe über", "Meldung"]
STATUS_SAVED, STATUS_REJECTED = "gespeichert", "abgelehnt"


# --------------------------------------------------------------------------- Hilfen
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def readable(value) -> str:
    """Wert für die Liste: Ja/Nein statt True/False, «leer» statt None."""
    if value is None or (isinstance(value, float) and value != value):
        return "leer"
    if isinstance(value, bool):
        return YES if value else NO
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def class_order(classes) -> list[str]:
    """Bekannte Klassen in fester Reihenfolge (Wände, Decken, Türen …), danach die übrigen alphabetisch."""
    known = list(PLURAL)
    return sorted(set(classes), key=lambda c: (c not in PLURAL, known.index(c) if c in PLURAL else 0, c))


def sheet_names(classes: list[str]) -> dict[str, str]:
    """Eindeutige, gültige Blattnamen (max. 31 Zeichen, ohne []:*?/\\)."""
    used = {SHEET_OVERVIEW, SHEET_LEGEND, SHEET_CHANGES}
    result = {}
    for cls in classes:
        name = PLURAL.get(cls, cls[3:] if cls.startswith("Ifc") else cls)
        name = "".join(ch for ch in name if ch not in "[]:*?/\\")[:31] or "Klasse"
        if name in used:
            name = f"{name} {cls}"[:31]
        n = 2
        base = name
        while name in used:
            name = f"{base[:28]} {n}"
            n += 1
        used.add(name)
        result[cls] = name
    return result


def rule_summary(rule: dict) -> str:
    """Regel in einem Satz, für die Legende."""
    kind = rule.get("type")
    if kind == "enum":
        text = "Werteliste: " + ", ".join(str(v) for v in rule.get("values", []))
    elif kind == "bool":
        text = f"Ja/Nein, muss {YES if rule['value'] else NO} sein" if "value" in rule else "Ja/Nein"
    elif kind == "float":
        low, high = rule.get("min"), rule.get("max")
        if low is not None and high is not None:
            text = f"Zahl zwischen {readable(low)} und {readable(high)}"
        elif low is not None:
            text = f"Zahl ab {readable(low)}"
        elif high is not None:
            text = f"Zahl bis {readable(high)}"
        else:
            text = "Zahl"
    elif kind == "pattern":
        text = f"Text nach Muster «{rule.get('pattern')}»"
    elif kind == "prohibited":
        text = "darf nicht vorkommen"
    else:
        text = "Text"
    return text


def _issue_index(issues: pd.DataFrame) -> dict:
    return {(r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY]): r[model_check.COL_PROBLEM] for _, r in issues.iterrows()}


def class_summary(properties: dict, issues: pd.DataFrame) -> dict[str, dict]:
    """Pro Klasse: Anzahl Bauteile, davon erfüllt, offene Werte."""
    out: dict[str, dict] = {}
    bad = set(issues[COL_GLOBAL_ID]) if len(issues) else set()
    for guid, info in properties.items():
        entry = out.setdefault(info["cls"], {"n": 0, "ok": 0, "open": 0})
        entry["n"] += 1
        entry["ok"] += guid not in bad
    for cls, count in (issues[COL_CLASS].value_counts().items() if len(issues) else []):
        out.setdefault(cls, {"n": 0, "ok": 0, "open": 0})["open"] = int(count)
    return out


def new_psets(before: dict, after: dict) -> dict[str, int]:
    """Property-Sets, die ein Bauteil vorher nicht hatte: {Pset: Anzahl Bauteile}."""
    out: dict[str, int] = {}
    for guid, info in after.items():
        had = before.get(guid, {}).get("psets", {})
        for pset in info["psets"]:
            if pset not in had:
                out[pset] = out.get(pset, 0) + 1
    return dict(sorted(out.items()))


def _columns_for(cls: str, rules: dict, saved: pd.DataFrame, after: dict) -> list[tuple[str, str]]:
    """Spalten eines Klassenblatts: (Pset, Property) aus den Regeln, dann die geänderten.

    Verbotene Properties erscheinen nur, wenn ein Bauteil sie tatsächlich hat.
    """
    cols: list[tuple[str, str]] = []
    present = {(ps, p) for info in after.values() if info["cls"] == cls for ps, props in info["psets"].items() for p in props}
    for pset, props in rules_for_class(rules, cls).items():
        for prop, rule in props.items():
            if rule.get("type") == "prohibited" and (pset, prop) not in present:
                continue
            cols.append((pset, prop))
    for _, row in saved[saved[COL_CLASS] == cls].iterrows():
        key = (row[COL_PSET], row[COL_PROPERTY])
        if key not in cols:
            cols.append(key)
    # nach Pset gruppieren, Reihenfolge innerhalb des Psets beibehalten
    order = list(dict.fromkeys(ps for ps, _ in cols))
    return sorted(cols, key=lambda c: order.index(c[0]))


# --------------------------------------------------------------------------- Zellen
def _put(ws, row, col, value, *, bold=False, color=None, fill=None, box=False, size=None, wrap=False,
         italic=False, align=None):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(bold=bold, color=color, size=size, italic=italic)
    if fill:
        cell.fill = _FILL(fill)
    if box:
        cell.border = _BOX
    cell.alignment = Alignment(vertical="top", wrap_text=wrap, horizontal=align)
    return cell


def _head(ws, row, headers, start=1):
    for i, text in enumerate(headers):
        _put(ws, row, start + i, text, bold=True, color=HEAD_TEXT, fill=HEAD, box=True)


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _print_setup(ws, title_rows: str | None = None):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    if title_rows:
        ws.print_title_rows = title_rows


# --------------------------------------------------------------------------- Blätter
def _overview(ws, *, file_name, copy_name, schema, n_storeys, original_bytes, copy_bytes, user, now,
              rules_label, before, after, issues_before, issues_after, saved, rejected, names, created):
    _widths(ws, [38, 22, 22, 12, 12, 12, 26])
    ws.sheet_view.showGridLines = False
    _put(ws, 1, 1, "Bauteilliste IFC-Property-Editor", bold=True, size=16)
    _put(ws, 2, 1, "Übersicht der bearbeiteten IFC-Kopie, ein Blatt pro Bauteilklasse", color=MUTED)

    n_elements = len(after)
    model_text = " · ".join(t for t in (file_name, schema, f"{n_elements} Bauteile", f"{n_storeys} Geschosse") if t)
    info = [
        ("Modell", model_text),
        ("Kopie", copy_name),
        ("SHA-256 Original", sha256(original_bytes)),
        ("SHA-256 Kopie", sha256(copy_bytes)),
        ("Erstellt am · von", f"{now.strftime('%d.%m.%Y %H:%M')} · {user}"),
        ("Prüfregeln", rules_label),
    ]
    row = 4
    for label, value in info:
        _put(ws, row, 1, label, bold=True)
        _put(ws, row, 2, value, color=MUTED if label.startswith("SHA") else None)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=7)
        row += 1

    # Ergebnis vorher / nachher
    row += 1
    _head(ws, row, ["Ergebnis", "vorher", "nachher"])
    row += 1

    def share(issues, props):
        bad = issues[COL_GLOBAL_ID].nunique() if len(issues) else 0
        ok = len(props) - bad
        pct = round(100 * ok / len(props)) if props else 100
        return ok, f"{ok} von {len(props)} ({pct} %)"

    ok_before, text_before = share(issues_before, before)
    ok_after, text_after = share(issues_after, after)
    changed_elements = saved[COL_GLOBAL_ID].nunique() if len(saved) else 0
    added = new_psets(before, after)
    lines = [
        ("Bauteile, die alle Regeln erfüllen", text_before, text_after,
         GREEN_TEXT if ok_after > ok_before else None),
        ("Offene Werte", str(len(issues_before)), str(len(issues_after)),
         GREEN_TEXT if len(issues_after) < len(issues_before) else (RED_TEXT if len(issues_after) else None)),
        ("Geänderte Werte · Bauteile", "",
         f"{len(saved)} Wert{'e' if len(saved) != 1 else ''} · {changed_elements} Bauteil{'e' if changed_elements != 1 else ''}", None),
        ("Neue Property-Sets", "",
         " · ".join(f"{p} an {n} Bauteil{'en' if n != 1 else ''}" for p, n in added.items()) or "keine", None),
        ("Abgelehnte Eingaben (nicht gespeichert)", "",
         f"{len(rejected)}, siehe unten" if len(rejected) else "keine", RED_TEXT if len(rejected) else None),
    ]
    for label, a, b, color in lines:
        _put(ws, row, 1, label, box=True)
        _put(ws, row, 2, a, box=True)
        _put(ws, row, 3, b, box=True, bold=color is not None, color=color)
        row += 1

    # eine Zeile pro Klasse
    row += 1
    _head(ws, row, ["Klasse", "Blatt", "Bauteile", "geändert", "erfüllt", "offen", "Erfüllungsgrad"])
    row += 1
    first = row
    stats = class_summary(after, issues_after)
    changed_by_class = saved.groupby(COL_CLASS)[COL_GLOBAL_ID].nunique().to_dict() if len(saved) else {}
    total = {"n": 0, "ch": 0, "ok": 0, "open": 0}
    for cls in [c for c in names if c in stats]:
        s = stats[cls]
        ch = int(changed_by_class.get(cls, 0))
        label = f"{PLURAL.get(cls, cls)} · {cls}" if cls in PLURAL else cls
        _put(ws, row, 1, label, bold=True, box=True)
        sheet = names.get(cls)
        if sheet and sheet in created:
            link = _put(ws, row, 2, f"{sheet} →", color="1A5FB4", box=True)
            link.hyperlink = f"#'{sheet}'!A1"
            link.font = Font(color="1A5FB4", underline="single")
        else:
            _put(ws, row, 2, "kein Blatt (keine Regeln)", color=MUTED, box=True, italic=True)
        _put(ws, row, 3, s["n"], box=True)
        _put(ws, row, 4, ch, box=True, color=GREEN_TEXT if ch else MUTED)
        _put(ws, row, 5, s["ok"], box=True)
        _put(ws, row, 6, s["open"], box=True, color=RED_TEXT if s["open"] else MUTED, bold=bool(s["open"]))
        pct = _put(ws, row, 7, s["ok"] / s["n"] if s["n"] else 1.0, box=True)
        pct.number_format = "0 %"
        for k, v in (("n", s["n"]), ("ch", ch), ("ok", s["ok"]), ("open", s["open"])):
            total[k] += v
        row += 1
    last = row - 1
    _put(ws, row, 1, "Total", bold=True, box=True)
    _put(ws, row, 2, "", box=True)
    for col, k in ((3, "n"), (4, "ch"), (5, "ok"), (6, "open")):
        _put(ws, row, col, total[k], bold=True, box=True)
    pct = _put(ws, row, 7, total["ok"] / total["n"] if total["n"] else 1.0, bold=True, box=True)
    pct.number_format = "0 %"
    if last >= first:
        ws.conditional_formatting.add(
            f"G{first}:G{row}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color=BAR))
    row += 2

    # abgelehnte Eingaben
    _put(ws, row, 1, "Abgelehnte Eingaben", bold=True, size=12)
    row += 1
    if len(rejected):
        _head(ws, row, ["Klasse · Geschoss", "Bauteil", "Property", "Eingabe", "Grund"])
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
        row += 1
        for _, r in rejected.iterrows():
            storey = before.get(r[COL_GLOBAL_ID], {}).get("storey") or "ohne Geschoss"
            _put(ws, row, 1, f"{r[COL_CLASS]} · {storey}", box=True)
            _put(ws, row, 2, r[COL_NAME] or "ohne Name", bold=True, box=True)
            _put(ws, row, 3, f"{r[COL_PSET]} · {r[COL_PROPERTY]}", box=True, wrap=True)
            _put(ws, row, 4, readable(r[COL_NEW]), color=RED_TEXT, box=True)
            _put(ws, row, 5, r[COL_MESSAGE], color=RED_TEXT, box=True, wrap=True)
            ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)
            row += 1
    else:
        _put(ws, row, 1, "keine, alle Eingaben wurden gespeichert", color=MUTED)
        row += 1

    # Visum
    row += 1
    _head(ws, row, ["Visum", "Name", "", "Datum", "", "Unterschrift", ""])
    for a, b in ((2, 3), (4, 5), (6, 7)):
        ws.merge_cells(start_row=row, start_column=a, end_row=row, end_column=b)
    row += 1
    for label in ("Geprüft", "Freigegeben"):
        _put(ws, row, 1, label, bold=True, box=True)
        for col in range(2, 8):
            _put(ws, row, col, None, box=True)
        for a, b in ((2, 3), (4, 5), (6, 7)):
            ws.merge_cells(start_row=row, start_column=a, end_row=row, end_column=b)
        ws.row_dimensions[row].height = 30
        row += 1
    _print_setup(ws)
    ws.page_setup.fitToHeight = 1          # Übersicht immer auf einer Seite


def _class_sheet(ws, cls, *, before, after, rules, saved, problems, storeys):
    columns = _columns_for(cls, rules, saved, after)
    elements = [(g, info) for g, info in after.items() if info["cls"] == cls]
    rank = {s: i for i, s in enumerate(storeys)}
    elements.sort(key=lambda e: (rank.get(e[1]["storey"], len(rank)), e[1]["storey"], e[1]["name"]))
    changed = {(r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY]) for _, r in saved.iterrows()}

    fixed = ["Geschoss", "Bauteil", "GlobalId"]
    ws.sheet_view.showGridLines = False
    # Zeile 1: Pset-Gruppen, Zeile 2: Spaltenköpfe
    for i in range(len(fixed)):
        _put(ws, 1, i + 1, None, fill=GROUP)
    col = len(fixed) + 1
    for pset in dict.fromkeys(ps for ps, _ in columns):
        span = sum(1 for ps, _ in columns if ps == pset)
        _put(ws, 1, col, pset, bold=True, fill=GROUP, box=True, align="center")
        if span > 1:
            ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + span - 1)
        col += span
    _put(ws, 1, col, None, fill=GROUP)
    _head(ws, 2, fixed + [p for _, p in columns] + ["Stand"])

    for n, (guid, info) in enumerate(elements, start=3):
        _put(ws, n, 1, info["storey"] or "ohne Geschoss", box=True)
        _put(ws, n, 2, info["name"] or "ohne Name", bold=True, box=True)
        _put(ws, n, 3, guid, color=MUTED, box=True)
        open_here = 0
        for i, (pset, prop) in enumerate(columns, start=len(fixed) + 1):
            new = info["psets"].get(pset, {}).get(prop)
            key = (guid, pset, prop)
            problem = problems.get(key)
            if key in changed:
                old = before.get(guid, {}).get("psets", {}).get(pset, {}).get(prop)
                cell = _put(ws, n, i, f"{readable(old)}{_ARROW}{readable(new)}", box=True,
                            fill=RED if problem else GREEN, color=RED_TEXT if problem else GREEN_TEXT)
            elif problem:
                cell = _put(ws, n, i, readable(new), box=True, fill=RED, color=RED_TEXT)
            else:
                cell = _put(ws, n, i, None if new is None else readable(new), box=True)
            if problem:
                open_here += 1
                cell.comment = Comment(problem, "IFC-Property-Editor", width=260, height=70)
        stand = f"✗ offen ({open_here})" if open_here else "✓ erfüllt"
        _put(ws, n, len(fixed) + len(columns) + 1, stand, box=True, bold=True,
             color=RED_TEXT if open_here else GREEN_TEXT, fill=RED if open_here else GREEN)

    last_col = len(fixed) + len(columns) + 1
    span = {ps: sum(1 for q, _ in columns if q == ps) for ps, _ in columns}
    widths = [max(14, min(30, len(p) + 4), len(ps) + 3 if span[ps] == 1 else 0) for ps, p in columns]
    _widths(ws, [14, 28, 26] + widths + [13])
    ws.freeze_panes = "D3"
    ws.auto_filter.ref = f"A2:{get_column_letter(last_col)}{max(2, len(elements) + 2)}"
    _print_setup(ws, "1:2")


def _legend(ws, rules, rules_label):
    ws.sheet_view.showGridLines = False
    _widths(ws, [22, 26, 26, 46, 9, 34])
    _put(ws, 1, 1, "Legende", bold=True, size=14)
    row = 3
    for text, fill, color, meaning in [
        ("alt → neu", GREEN, GREEN_TEXT, "Wert wurde geändert und erfüllt die Regel"),
        ("alt → neu", RED, RED_TEXT, "Wert wurde geändert, erfüllt die Regel aber noch nicht"),
        ("leer / Wert", RED, RED_TEXT, "Regel nicht erfüllt (Pflichtwert fehlt oder Wert ungültig), Grund als Kommentar in der Zelle"),
        ("Wert", None, None, "unverändert und in Ordnung"),
        ("✓ erfüllt", GREEN, GREEN_TEXT, "Bauteil erfüllt alle Regeln seiner Klasse"),
        ("✗ offen (n)", RED, RED_TEXT, "Bauteil hat n offene Werte"),
    ]:
        _put(ws, row, 1, text, fill=fill, color=color, box=True, bold=fill is not None)
        _put(ws, row, 2, meaning)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
        row += 1
    row += 1
    _put(ws, row, 1, "Verwendete Regeln", bold=True, size=12)
    _put(ws, row, 2, rules_label, color=MUTED)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
    row += 1
    _head(ws, row, ["Klasse", "Property-Set", "Property", "Regel", "Pflicht", "Quelle"])
    head_row = row
    row += 1
    for cls in sorted(rules):
        for pset, props in rules[cls].items():
            for prop, rule in props.items():
                values = [cls, pset, prop, rule_summary(rule), "ja" if rule.get("required") else "",
                          rule.get("source") or "config/rules.json"]
                for i, v in enumerate(values, start=1):
                    _put(ws, row, i, v, box=True, wrap=i == 4)
                row += 1
    ws.auto_filter.ref = f"A{head_row}:F{max(head_row, row - 1)}"
    _print_setup(ws)


def _changes(ws, validated: pd.DataFrame, before: dict, user: str, now: datetime):
    ws.sheet_view.showGridLines = False
    _head(ws, 1, CHANGE_HEADERS)
    for n, (_, r) in enumerate(validated.iterrows(), start=1):
        ok = bool(r[COL_VALID])
        entered = r.get(COL_ENTERED) if COL_ENTERED in validated.columns else None
        source = r.get(COL_SOURCE) if COL_SOURCE in validated.columns else None
        values = [n, entered or now.strftime("%Y-%m-%d %H:%M"), user,
                  before.get(r[COL_GLOBAL_ID], {}).get("storey") or "", r[COL_CLASS], r[COL_NAME] or "ohne Name",
                  r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY], readable(r[COL_OLD]), readable(r[COL_NEW]),
                  STATUS_SAVED if ok else STATUS_REJECTED, source or "", r[COL_MESSAGE] or ""]
        for i, v in enumerate(values, start=1):
            status = i == 12
            _put(ws, n + 1, i, v, box=True, wrap=i == 14,
                 color=(GREEN_TEXT if ok else RED_TEXT) if status or (i == 14 and not ok) else (MUTED if i == 7 else None),
                 fill=(GREEN if ok else RED) if status else None, bold=status)
    _widths(ws, [5, 17, 20, 12, 13, 26, 25, 22, 22, 12, 12, 13, 14, 48])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(CHANGE_HEADERS))}{max(1, len(validated) + 1)}"
    _print_setup(ws, "1:1")


# --------------------------------------------------------------------------- Mappe
def build_workbook(*, file_name: str, copy_name: str, original_bytes: bytes, copy_bytes: bytes,
                   props_before: dict, props_after: dict, validated: pd.DataFrame, rules: dict,
                   rules_label: str, user: str = "", now: datetime | None = None,
                   storeys: list[str] | None = None, schema: str = "") -> bytes:
    """Arbeitsmappe als Bytes, bereit zum Herunterladen.

    props_before / props_after: ifc_reader.element_properties von Original und Kopie
    validated: pending.validate_all, gültige Zeilen wurden gespeichert, die anderen abgelehnt
    storeys:   Geschossnamen von unten nach oben (ifc_reader.storey_order)
    """
    now = now or datetime.now()
    user = (user or "").strip() or "unbekannt"
    storeys = storeys or sorted({i["storey"] for i in props_after.values() if i["storey"]})
    valid_mask = validated[COL_VALID].astype(bool) if len(validated) else pd.Series([], dtype=bool)
    saved = validated[valid_mask] if len(validated) else validated
    rejected = validated[~valid_mask] if len(validated) else validated

    issues_before = model_check.check_model(props_before, rules)
    issues_after = model_check.check_model(props_after, rules)
    problems = _issue_index(issues_after)

    classes = class_order(i["cls"] for i in props_after.values())
    names = sheet_names(classes)

    wb = Workbook()
    ws_overview = wb.active
    ws_overview.title = SHEET_OVERVIEW
    created = []
    for cls in classes:
        if not _columns_for(cls, rules, saved, props_after):
            continue          # keine Regeln und keine Änderungen: kein eigenes Blatt
        ws = wb.create_sheet(names[cls])
        _class_sheet(ws, cls, before=props_before, after=props_after, rules=rules, saved=saved,
                     problems=problems, storeys=storeys)
        created.append(names[cls])
    _legend(wb.create_sheet(SHEET_LEGEND), rules, rules_label)
    _changes(wb.create_sheet(SHEET_CHANGES), validated, props_before, user, now)
    _overview(ws_overview, file_name=file_name, copy_name=copy_name, schema=schema, n_storeys=len(storeys),
              original_bytes=original_bytes, copy_bytes=copy_bytes, user=user, now=now, rules_label=rules_label,
              before=props_before, after=props_after, issues_before=issues_before, issues_after=issues_after,
              saved=saved, rejected=rejected, names=names, created=created)

    wb.properties.title = f"Bauteilliste {file_name}"
    wb.properties.creator = "IFC-Property-Editor"
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
