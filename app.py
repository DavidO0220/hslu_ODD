"""IFC-Property-Editor: Weboberfläche.

Start:  streamlit run app.py

Die Oberfläche enthält keine IFC-Logik. Sie ruft nur Funktionen aus core/ auf.

Aufbau «Eine Arbeitsfläche», vier Bereiche ohne Seitenleiste:
1 Laden               Datei und Prüfregeln, Übersicht über das Modell
2 Arbeitsfläche       links Filter (Klasse, Pset, Geschoss, nur Lücken), Mitte
                      Tabelle, rechts 3D und Eigenschaften des gewählten Bauteils.
                      Umschaltbar: «Neues Pset anlegen» und «3D gross».
3 Prüfen & Speichern  Änderungsliste mit Entfernen, Modell gegen Regeln, Speichern
⚙ Regeln              Prüfregeln von Hand bearbeiten

Zwei Eigenheiten von Streamlit bestimmen den Aufbau:
- Bei jedem Klick läuft dieses Skript von oben neu durch. Modell, Geometrie und
  Eigenschaften werden deshalb mit st.cache_resource nur einmal gelesen.
- Die Bereiche sind Reiter (st.tabs) mit Schlüssel «area». So kann ein Knopf
  in einen anderen Bereich wechseln. Alle Reiter laufen bei jedem Durchlauf,
  damit Eingaben erhalten bleiben. Nur die 3D-Ansichten werden im
  verborgenen Reiter übersprungen, weil sie viele Daten an den Browser senden.

Alle offenen Änderungen liegen in einer gemeinsamen Liste (core/pending.py,
in st.session_state["pending"]). Tabelle, Eigenschaften-Formular, 3D-Pop-up und
«Neues Pset» schreiben hinein, «Prüfen & Speichern» liest daraus.

Gewählte Klasse, Pset und Geschoss liegen in eigenen Schlüsseln (ifc_class,
pset, storey). Die Auswahlfelder übernehmen sie nur (siehe pick). Ein Klick im
3D oder «zum Bauteil» kann sie deshalb von aussen setzen.
"""

import json
import zlib
from pathlib import Path

import pandas as pd
import streamlit as st

import viewer
from core import (changelog, geometry, ids_import, ifc_reader, ifc_writer, model_check, pending, report,
                  rules_store)
from core.display import NO, YES, add_columns, bool_columns, to_display
from core.schema import (COL_CLASS, COL_GLOBAL_ID, COL_MESSAGE, COL_NAME, COL_NEW, COL_OLD, COL_PROPERTY,
                         COL_PSET, COL_SOURCE, COL_STOREY, COL_VALID, LOCKED_COLUMNS)
from core.validator import STANDARD_RULES_PATH, load_rules, merge_rules, rules_for_class

TEST_MODEL = Path(__file__).resolve().parent / "data" / "testmodell.ifc"
EXAMPLE_IDS = Path(__file__).resolve().parent / "config" / "beispiel_anforderungen.ids"
AREAS = ["1  Laden", "2  Arbeitsfläche", "3  Prüfen & Speichern", "⚙  Regeln"]
AREA_LOAD, AREA_WORK, AREA_CHECK, AREA_RULES = AREAS
MODE_EDIT, MODE_NEW = "Werte bearbeiten", "Neues Pset anlegen"
VIEW_SPLIT, VIEW_3D = "Tabelle + 3D", "3D gross"
COL_SHOW = "3D"          # Häkchen-Spalte: Bauteil im Viewer zeigen. Nur Oberfläche, wird nie geschrieben.
COL_REMOVE = "Entfernen"  # Häkchen-Spalte in der Änderungsliste
STATUS_ALL, STATUS_OK, STATUS_BAD = "alle", "gültig", "Fehler"
ALL_CLASSES = "alle Klassen"

st.set_page_config(page_title="IFC-Property-Editor", layout="wide")


# =============================== Daten (zwischengespeichert) ==================
@st.cache_resource(show_spinner="IFC-Modell wird geladen …")
def get_model(file_bytes: bytes):
    """Lädt das Modell nur einmal pro Datei, nicht bei jedem Klick."""
    return ifc_reader.load_model(file_bytes)


@st.cache_data(show_spinner="Tabelle wird aufgebaut …")
def get_table(file_bytes: bytes, ifc_class: str, pset: str):
    """Tabelle zwischenspeichern: bei grossen Modellen dauert das Auslesen spürbar."""
    return ifc_reader.to_table(get_model(file_bytes), ifc_class, pset)


@st.cache_data
def get_storeys(file_bytes: bytes) -> list[str]:
    """Geschosse von unten nach oben."""
    return ifc_reader.storey_order(get_model(file_bytes))


@st.cache_data
def base_rules() -> dict:
    """Regeln aus config/rules.json."""
    return load_rules()


@st.cache_data
def read_ids(data: bytes):
    """IDS-Datei lesen: (Regeln, Hinweise, Info). Wirft IdsError bei ungültiger Datei."""
    return ids_import.parse_ids(data)


@st.cache_resource(show_spinner="3D-Geometrie wird berechnet …")
def get_meshes(file_bytes: bytes) -> list[dict]:
    """Geometrie nur einmal pro Datei berechnen, das dauert bei grossen Modellen."""
    return geometry.load_meshes(get_model(file_bytes))


@st.cache_resource(show_spinner="Eigenschaften werden gelesen …")
def get_properties(file_bytes: bytes) -> dict:
    """Alle Eigenschaften aller Bauteile (Pop-up, Formular, Prüfung, Bauteilliste)."""
    return ifc_reader.element_properties(get_model(file_bytes))


def get_rules() -> dict:
    """Aktive Regeln: rules.json, ergänzt oder ersetzt durch eine IDS (Bereich «Laden»)."""
    return RULES


def n_rules(rules: dict) -> int:
    return sum(len(props) for psets in rules.values() for props in psets.values())


# =============================== Zustand ======================================
def change_store(file_key) -> dict:
    """Die gemeinsame Änderungsliste. Eine neue Datei beginnt mit einer leeren Liste."""
    if "pending" not in st.session_state or st.session_state.get("store_file") != file_key:
        st.session_state["store_file"] = file_key
        st.session_state["pending"] = {}
        st.session_state["editor_rev"] = 0
        st.session_state["sel3d"] = []      # Auswahl in Tabelle und Viewer
        for key in ("result_ifc", "result_log", "result_xlsx", "result_after"):
            st.session_state.pop(key, None)
    return st.session_state["pending"]


def restart_editor() -> None:
    """Tabellen und Formular neu aufsetzen, damit sie Änderungen von aussen zeigen."""
    st.session_state["editor_rev"] = st.session_state.get("editor_rev", 0) + 1


def reset_downstream() -> None:
    """Änderungen haben sich geändert: die alte IFC-Kopie und Bauteilliste passen nicht mehr."""
    for key in ("result_ifc", "result_log", "result_xlsx", "result_after"):
        st.session_state.pop(key, None)


def go(area: str) -> None:
    """Knopf-Callback: in einen anderen Bereich wechseln."""
    st.session_state["area"] = area


def open_element(guid: str, ifc_class: str, pset: str) -> None:
    """Knopf-Callback «zum Bauteil»: Bauteil in der Arbeitsfläche anwählen."""
    st.session_state.update(ifc_class=ifc_class, pset=pset, storey=None, sel3d=[guid], only_gaps=False,
                            work_mode=MODE_EDIT, work_view=VIEW_SPLIT, area=AREA_WORK)
    restart_editor()


def _sync(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = st.session_state[widget_key]


def choose(state_key: str, options: list, allow_none: bool = False):
    """Gültigen Wert für state_key bestimmen, bevor das Auswahlfeld gezeichnet wird."""
    value = st.session_state.get(state_key)
    if value not in options and not (allow_none and value is None):
        value = None if allow_none or not options else options[0]
        st.session_state[state_key] = value
    return value


def pick(widget, label: str, options: list, state_key: str, widget_key: str, **kwargs):
    """Auswahlfeld, das seinen Wert in st.session_state[state_key] ablegt.

    Vor dem Zeichnen bekommt das Feld den gemeinsamen Wert, bei einer Änderung
    schreibt es ihn zurück. So kann ein Klick im 3D oder «zum Bauteil» die
    Auswahl von aussen setzen.
    """
    st.session_state[widget_key] = st.session_state.get(state_key)
    return widget(label, options, key=widget_key, on_change=_sync, args=(widget_key, state_key), **kwargs)


def pending_for_viewer(store: dict, checked: pd.DataFrame) -> list[dict]:
    """Offene Änderungen mit Prüfergebnis in der Form für das Pop-up (Werte in Anzeigeform)."""
    result = {(r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY]): (bool(r[COL_VALID]), r[COL_MESSAGE] or "")
              for _, r in checked.iterrows()}
    return [{"guid": g, "pset": ps, "prop": pr, "old": e[COL_OLD], "new": e[COL_NEW],
             "valid": result.get((g, ps, pr), (True, ""))[0], "msg": result.get((g, ps, pr), (True, ""))[1]}
            for (g, ps, pr), e in store.items()]


def keep_type(store: dict, key: tuple, original, value):
    """Wert eines neu angelegten Psets: Typ (Zahl, Ja/Nein) der Vormerkung beibehalten."""
    before = store.get(key)
    if before is not None and original is None and not isinstance(before[COL_NEW], str):
        kind = pending.KIND_BOOL if isinstance(before[COL_NEW], bool) else pending.KIND_NUMBER
        try:
            return pending.typed(value, kind)
        except ValueError:
            return value
    return value


def class_label(ifc_class: str) -> str:
    return report.PLURAL.get(ifc_class, ifc_class)


def _text(value) -> str:
    return report.readable(value)


# =============================== Bausteine Arbeitsfläche ======================
def column_config_for(table: pd.DataFrame, raw: pd.DataFrame, pset_rules: dict) -> dict:
    """Auswahlfelder in der Tabelle: Ja/Nein und Wertelisten aus den Regeln, sonst freier Text.

    Pflicht-Properties bekommen ein «*» im Spaltenkopf.
    """
    config = {}
    bools = set(bool_columns(raw)) | {p for p, r in pset_rules.items() if r.get("type") == "bool"}
    for col in table.columns:
        if col in LOCKED_COLUMNS or col == COL_SHOW:
            continue
        rule = pset_rules.get(col, {})
        label = f"{col} *" if rule.get("required") else col
        if col in bools:
            config[col] = st.column_config.SelectboxColumn(label, options=[YES, NO])
        elif rule.get("type") == "enum":
            allowed = list(rule.get("values", []))
            # Werte aus dem Modell, die nicht in der Liste stehen (z. B. EI45), bleiben sichtbar
            extra = sorted({str(v) for v in table[col] if v is not None and not pd.isna(v)} - set(allowed))
            config[col] = st.column_config.SelectboxColumn(
                label, options=allowed + extra, help=f"Werteliste: {', '.join(allowed)}")
        elif rule.get("type") == "float":
            low, high = rule.get("min"), rule.get("max")
            config[col] = st.column_config.TextColumn(label, help=f"Zahl zwischen {low} und {high}")
        elif rule.get("type") == "pattern":
            config[col] = st.column_config.TextColumn(label, help=f"Text nach Muster {rule.get('pattern')}")
        elif rule.get("required"):
            config[col] = st.column_config.TextColumn(label)
    return config


def follow_click(clicked: str | None, in_table: set, file_bytes: bytes) -> None:
    """Angeklicktes Bauteil steht nicht in der Tabelle: auf seine Klasse, sein Pset und alle Geschosse wechseln."""
    if not clicked or clicked in in_table:
        return
    info = get_properties(file_bytes).get(clicked)
    if info is None:
        return
    st.session_state["ifc_class"] = info["cls"]
    if st.session_state.get("pset") not in info["psets"] and info["psets"]:
        st.session_state["pset"] = sorted(info["psets"])[0]
    st.session_state["storey"] = None
    st.session_state["only_gaps"] = False


def viewer_select(file_bytes: bytes, in_table: set, height: int = 460) -> None:
    """Viewer neben der Tabelle. Klick im 3D wählt aus, wie ein Häkchen in der Spalte «3D»."""
    try:
        meshes = get_meshes(file_bytes)
    except Exception as exc:
        st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
        return
    if not meshes:
        st.info("Das Modell enthält keine darstellbare Geometrie.")
        return
    value = viewer.select3d(meshes, st.session_state.get("sel3d", []), model_id=f"{file_name}:{len(file_bytes)}",
                            focus=focus_on_select, transparency=transparency / 100, height=height)
    if value and value.get("nonce") != st.session_state.get("select_nonce"):
        st.session_state["select_nonce"] = value.get("nonce")
        st.session_state["sel3d"] = list(value.get("ids", []))
        follow_click(value.get("clicked"), in_table, file_bytes)
        restart_editor()            # Häkchen in der Tabelle neu setzen
        st.rerun()


def properties_form(guid: str, pset: str, columns: list[str], store: dict, checked: pd.DataFrame) -> None:
    """Eigenschaften des gewählten Bauteils im aktuellen Pset, als Formular mit «Übernehmen»."""
    info = get_properties(ifc_bytes)[guid]
    pset_rules = rules_for_class(get_rules(), info["cls"]).get(pset, {})
    original = info["psets"].get(pset, {})
    status = {(r[COL_PROPERTY]): (bool(r[COL_VALID]), r[COL_MESSAGE] or "")
              for _, r in checked.iterrows() if r[COL_GLOBAL_ID] == guid and r[COL_PSET] == pset}
    rev = st.session_state.get("editor_rev", 0)
    values = {}
    with st.form(f"props::{guid}::{pset}::{rev}", border=True):
        st.caption(f"EIGENSCHAFTEN · {info['name'] or 'ohne Name'} · {info['storey'] or 'ohne Geschoss'} · {pset}")
        for prop in columns:
            entry = store.get((guid, pset, prop))
            current = entry[COL_NEW] if entry else original.get(prop)
            shown = "" if current is None else _text(current)
            rule = pset_rules.get(prop, {})
            label = f"{prop} *" if rule.get("required") else prop
            key = f"form::{guid}::{pset}::{prop}::{rev}"
            is_bool = rule.get("type") == "bool" or isinstance(current, bool) or shown in (YES, NO) and not rule
            if rule.get("type") == "enum" or is_bool:
                options = ["", YES, NO] if is_bool else ["", *[str(v) for v in rule.get("values", [])]]
                if shown not in options:
                    options.append(shown)
                values[prop] = st.selectbox(label, options, index=options.index(shown), key=key,
                                            help=rule.get("instructions"))
            else:
                hint = {"float": f"Zahl {rule.get('min', '')} … {rule.get('max', '')}",
                        "pattern": f"Muster {rule.get('pattern', '')}"}.get(rule.get("type"), "")
                values[prop] = st.text_input(label, value=shown, key=key, placeholder=hint,
                                             help=rule.get("instructions"))
            if prop in status:
                ok, message = status[prop]
                old = _text(entry[COL_OLD]) if entry else "leer"
                text = f"{old} → {_text(entry[COL_NEW])}" if entry else ""
                st.caption(f":green[✓ {text}, gültig]" if ok else f":red[✗ {text}: {message}]")
        submitted = st.form_submit_button("Übernehmen", type="primary")
    if submitted:
        for prop, value in values.items():
            key = (guid, pset, prop)
            value = keep_type(store, key, original.get(prop), value)
            pending.put(store, guid, info["name"], info["cls"], pset, prop, original.get(prop), value,
                        pending.SOURCE_FORM)
        restart_editor()
        st.rerun()
    others = {p: v for p, v in info["psets"].items() if p != pset}
    if others:
        with st.expander(f"Weitere Property-Sets dieses Bauteils ({len(others)})"):
            for name, props in others.items():
                st.markdown(f"**{name}**  \n" + " · ".join(f"{k}: {_text(v)}" for k, v in props.items()))


def new_pset_form(file_bytes: bytes, ifc_class: str, storey: str | None, store: dict) -> list[str]:
    """Formular: ein neues Property-Set für mehrere Bauteile einer Klasse vormerken.

    Rückgabe: GlobalIds der gewählten Bauteile, für die Vorschau im 3D.
    """
    props = get_properties(file_bytes)
    class_rules = rules_for_class(get_rules(), ifc_class)
    elements = {g: p for g, p in props.items() if p["cls"] == ifc_class}
    if not elements:
        st.info(f"Im Modell gibt es keine Bauteile der Klasse {ifc_class}.")
        return []

    c1, c2 = st.columns([1.2, 1])
    template = c2.selectbox("Vorlage", ["— ohne Vorlage —", *class_rules], key=f"new_tpl::{ifc_class}",
                            help="Property-Sets, für die Regeln hinterlegt sind")
    from_rules = template in class_rules
    name = c1.text_input("Name des neuen Property-Sets", value=template if from_rules else "",
                         key=f"new_name::{ifc_class}::{template}", placeholder="z. B. CH_Brandschutz")
    name = name.strip()
    if name.startswith(("Pset_", "Qto_")) and name not in class_rules:
        st.warning("Die Präfixe «Pset_» und «Qto_» sind für die Standard-Sets von buildingSMART reserviert. "
                   "Für eigene Sets ein eigenes Präfix verwenden, zum Beispiel «CH_» oder ein Firmenkürzel.")

    pset_rules = class_rules.get(name, {})
    if from_rules:
        start = pd.DataFrame([{"Property": p, "Typ": pending.RULE_KIND.get(r.get("type"), pending.KIND_TEXT), "Wert": None}
                              for p, r in class_rules[template].items()])
    else:
        start = pd.DataFrame({"Property": [None] * 3, "Typ": [pending.KIND_TEXT] * 3, "Wert": [None] * 3})
    st.write("**Properties** — eine Zeile pro Property. Der Wert gilt für alle gewählten Bauteile.")
    rows = st.data_editor(
        start, num_rows="dynamic", hide_index=True, key=f"new_rows::{ifc_class}::{template}",
        column_config={
            "Property": st.column_config.TextColumn("Property"),
            "Typ": st.column_config.SelectboxColumn("Typ", options=pending.KINDS, required=True,
                                                    help="Bestimmt den IFC-Typ: Text, Zahl (IfcReal), Ja/Nein (IfcBoolean)"),
            "Wert": st.column_config.TextColumn("Wert"),
        },
    )
    hints = [f"{p}: {', '.join(r['values'])}" for p, r in pset_rules.items() if r.get("type") == "enum"]
    if hints:
        st.caption("Wertelisten laut Regeln · " + " · ".join(hints))

    without = [g for g, p in elements.items() if not name or name not in p["psets"]]
    candidates = [g for g in without if storey is None or elements[g]["storey"] == storey]
    label = lambda g: f"{elements[g]['name'] or 'ohne Name'} · {elements[g]['storey'] or 'ohne Geschoss'}"  # noqa: E731
    targets = st.multiselect("Bauteile, die das neue Property-Set bekommen", candidates, default=candidates,
                             format_func=label, key=f"new_targets::{ifc_class}::{name}::{storey}",
                             help="Geschoss links in der Filterspalte wählen")
    already = len(elements) - len(without)
    if name and already:
        st.caption(f"{already} Bauteil(e) haben «{name}» schon und fehlen in der Liste. "
                   f"Ihre Werte änderst du im Modus «{MODE_EDIT}».")

    if st.button(f"Property-Set bei {len(targets)} Bauteil(en) vormerken", type="primary",
                 disabled=not name or not targets):
        n, errors = pending.create_pset(
            store, [(g, elements[g]["name"], ifc_class) for g in targets], name,
            [(r["Property"], r["Typ"], r["Wert"]) for _, r in rows.iterrows()], pset_rules)
        for message in errors:
            st.error(message)
        if not errors:
            restart_editor()
            st.success(f"{n} Werte vorgemerkt. Geprüft und gespeichert wird in «Prüfen & Speichern».")
    return targets


def is_open(tab) -> bool:
    """Ist der Reiter gerade sichtbar? Ohne Angabe gilt er als sichtbar."""
    return getattr(tab, "open", None) is not False


# =============================== Kopfzeile ====================================
head_title, head_status, head_view = st.columns([2.2, 3, 0.8], vertical_alignment="center")
head_title.markdown("#### IFC-Property-Editor")
status_box = head_status.empty()      # wird am Ende gefüllt, wenn alle Eingaben dieses Durchlaufs drin sind
with head_view.popover("⚙ Ansicht", help="Einstellungen für die 3D-Ansichten"):
    focus_on_select = st.toggle(
        "Beim Anwählen hinzoomen", value=True, key="focus_on_select",
        help="Die Kamera fährt zur Auswahl, der Rest des Modells wird transparent. "
             "Ausgeschaltet bleibt die Auswahl orange markiert, die Kamera bleibt stehen.",
    )
    transparency = st.slider("Transparenz übriges Modell (%)", 0, 95, 85, step=5, key="transparency",
                             disabled=not focus_on_select)

tab_load, tab_work, tab_check, tab_rules = st.tabs(AREAS, key="area", on_change="rerun")

# =============================== 1 Laden =====================================
with tab_load:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        with st.container(border=True):
            st.caption("IFC-DATEI")
            uploaded = st.file_uploader("IFC-Datei hochladen", type=["ifc"],
                                        help="IFC4 oder IFC2x3. Das Original wird nie verändert.")
            use_test = TEST_MODEL.exists() and st.checkbox("Testmodell aus data/ verwenden")

        # Prüfregeln: rules.json, optional mit IDS-Datei (buildingSMART)
        with st.container(border=True):
            st.caption("PRÜFREGELN")
            ids_upload = st.file_uploader("IDS-Datei (optional)", type=["ids", "xml"],
                                          help="Anforderungen nach dem Standard IDS von buildingSMART")
            use_example_ids = EXAMPLE_IDS.exists() and st.checkbox("Beispiel-IDS aus config/ verwenden")
            ids_bytes = ids_upload.getvalue() if ids_upload is not None else (EXAMPLE_IDS.read_bytes() if use_example_ids else None)
            RULES, ids_info = base_rules(), None
            rules_label = f"config/rules.json ({n_rules(RULES)} Regeln)"
            if ids_bytes is not None:
                try:
                    ids_rules, ids_notes, ids_info = read_ids(ids_bytes)
                except ids_import.IdsError as exc:
                    st.error(str(exc))
                else:
                    only_ids = st.checkbox("Nur Regeln aus der IDS", help="Sonst ergänzt die IDS config/rules.json und hat Vorrang.")
                    RULES = ids_rules if only_ids else merge_rules(base_rules(), ids_rules)
                    ids_text = f"IDS «{ids_info['title'] or 'ohne Titel'}» ({ids_info['rules']} Regeln)"
                    rules_label = ids_text if only_ids else f"{rules_label} + {ids_text}"
                    st.caption(f"IDS «{ids_info['title'] or 'ohne Titel'}»: {ids_info['rules']} Regeln aus "
                               f"{ids_info['specifications']} Spezifikationen"
                               + (f", für {' '.join(ids_info['ifc_versions'])}" if ids_info["ifc_versions"] else ""))
                    if ids_notes:
                        with st.expander(f"Nicht übernommen ({len(ids_notes)})"):
                            for note in ids_notes:
                                st.write("· " + note)
            st.caption(f"Grundregeln: config/rules.json mit {n_rules(base_rules())} Regeln, bearbeiten im Bereich «⚙ Regeln».")

    ifc_bytes, file_name = None, None
    if uploaded is not None:
        ifc_bytes, file_name = uploaded.getvalue(), uploaded.name
    elif use_test:
        ifc_bytes, file_name = TEST_MODEL.read_bytes(), TEST_MODEL.name

    model = None
    store = change_store((file_name, len(ifc_bytes)) if ifc_bytes is not None else None)
    with right:
        if ifc_bytes is None:
            st.info("Noch keine Datei geladen. Links eine IFC-Datei hochladen oder das Testmodell verwenden.")
        else:
            try:
                model = get_model(ifc_bytes)
            except Exception as exc:  # beschädigte oder ungültige Datei
                st.error(f"Die Datei konnte nicht gelesen werden: {exc}")

    classes = report.class_order(ifc_reader.list_classes(model)) if model is not None else []
    if model is not None:
        with right:
            if not classes:
                st.warning("Im Modell wurden keine Bauteile gefunden.")
            else:
                with st.container(border=True):
                    st.caption(f"IM MODELL · {file_name} · {model.schema}")
                    props_loaded = get_properties(ifc_bytes)
                    issues_loaded = model_check.check_model(props_loaded, get_rules())
                    stats = report.class_summary(props_loaded, issues_loaded)
                    ok_total = sum(s["ok"] for s in stats.values())
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Bauteile", len(props_loaded))
                    m2.metric("Geschosse", len(get_storeys(ifc_bytes)))
                    m3.metric("erfüllen alle Regeln", f"{round(100 * ok_total / max(1, len(props_loaded)))} %")
                    overview = pd.DataFrame([{
                        "Klasse": f"{class_label(c)} · {c}" if c in report.PLURAL else c,
                        "Bauteile": stats[c]["n"],
                        "Property-Sets": ", ".join(ifc_reader.list_psets(model, c)) or "—",
                        "offene Werte": stats[c]["open"],
                        "Stand": stats[c]["ok"] / stats[c]["n"] if stats[c]["n"] else 1.0,
                    } for c in classes])
                    st.dataframe(overview, hide_index=True, column_config={
                        "Stand": st.column_config.ProgressColumn(
                            "erfüllt", min_value=0.0, max_value=1.0, format="percent",
                            help="Anteil der Bauteile, die alle Regeln ihrer Klasse erfüllen"),
                    })
                    st.button("Zur Arbeitsfläche →", type="primary", on_click=go, args=(AREA_WORK,), width="stretch")

# =============================== 2 Arbeitsfläche =============================
with tab_work:
    if not classes:
        st.info("Zuerst im Bereich «Laden» ein Modell laden.")
    else:
        props_all = get_properties(ifc_bytes)
        storeys_all = get_storeys(ifc_bytes)
        # Auswahl aus dem Zustand lesen. Die Felder dazu stehen in der Filterspalte,
        # die erst nach der Tabelle gezeichnet wird (damit ihre Zähler aktuell sind).
        ifc_class = choose("ifc_class", classes)
        psets = ifc_reader.list_psets(model, ifc_class)
        pset = choose("pset", psets) if psets else None
        class_storeys = [s for s in storeys_all if any(p["cls"] == ifc_class and p["storey"] == s for p in props_all.values())]
        storey = choose("storey", class_storeys, allow_none=True)
        only_gaps = bool(st.session_state.get("only_gaps", False))
        issues_before_edit = model_check.check_model(props_all, get_rules(), store)

        rail, main = st.columns([1, 4.4], gap="medium")
        with main:
            top_mode, top_view = st.columns([1, 1])
            # Startwert über den Zustand statt default=, weil «zum Bauteil» den Modus von aussen setzt
            st.session_state.setdefault("work_mode", MODE_EDIT)
            st.session_state.setdefault("work_view", VIEW_SPLIT)
            mode = top_mode.segmented_control("Modus", [MODE_EDIT, MODE_NEW], required=True,
                                              key="work_mode", label_visibility="collapsed") or MODE_EDIT
            view = top_view.segmented_control("Ansicht", [VIEW_SPLIT, VIEW_3D], required=True,
                                              key="work_view", label_visibility="collapsed",
                                              disabled=mode == MODE_NEW) or VIEW_SPLIT

            if mode == MODE_NEW:
                st.markdown(f"**{class_label(ifc_class)} · neues Property-Set** — für Bauteile, die es noch nicht haben"
                            + (f", Geschoss {storey}" if storey else ""))
                form_col, preview_col = st.columns([1.3, 1], gap="medium")
                with form_col:
                    targets = new_pset_form(ifc_bytes, ifc_class, storey, store)
                with preview_col:
                    if is_open(tab_work):
                        try:
                            meshes = get_meshes(ifc_bytes)
                        except Exception as exc:
                            meshes = []
                            st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
                        if meshes:
                            viewer.select3d(meshes, targets, model_id=f"{file_name}:{len(ifc_bytes)}",
                                            focus=focus_on_select, transparency=transparency / 100, height=460,
                                            key="viewer_targets")
                            st.caption(f"Vorschau: {len(targets)} Bauteil(e) bekommen das neue Property-Set (orange).")

            elif view == VIEW_3D:
                if is_open(tab_work):
                    try:
                        meshes = get_meshes(ifc_bytes)
                    except Exception as exc:
                        meshes = []
                        st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
                    if meshes:
                        checked_now = pending.validate_all(store, get_rules())
                        value = viewer.model3d(meshes, props_all, get_rules(), pending_for_viewer(store, checked_now),
                                               model_id=f"{file_name}:{len(ifc_bytes)}", height=720)
                        # Neue Eingabe aus dem Pop-up in die gemeinsame Liste übernehmen
                        if value and value.get("nonce") != st.session_state.get("model3d_nonce"):
                            st.session_state["model3d_nonce"] = value.get("nonce")
                            info = props_all.get(value.get("guid"))
                            if info is not None:
                                for c in value.get("changes", []):
                                    original = info["psets"].get(c["pset"], {}).get(c["prop"])
                                    new_value = keep_type(store, (value["guid"], c["pset"], c["prop"]), original, c.get("value"))
                                    pending.put(store, value["guid"], info["name"], info["cls"], c["pset"], c["prop"],
                                                original, new_value, pending.SOURCE_3D)
                                restart_editor()
                                st.rerun()
                        st.caption("Bauteil anklicken, Werte im Fenster ändern, «Übernehmen». Schnitt und Ansichten oben "
                                   "in der Leiste. Die Filter links gelten hier nicht.")

            elif pset is None:
                st.info(f"Die Klasse {ifc_class} hat noch kein Property-Set. Eines im Modus «{MODE_NEW}» anlegen.")

            else:
                raw_table = get_table(ifc_bytes, ifc_class, pset)
                table = to_display(raw_table)
                with_pset = {g for g, p in props_all.items() if pset in p["psets"]}
                pset_rules = rules_for_class(get_rules(), ifc_class).get(pset, {})
                added = [p for p in pset_rules if p not in table.columns and pset_rules[p].get("type") != "prohibited"]
                rows = add_columns(table[table[COL_GLOBAL_ID].isin(with_pset)], added)
                view_rows = rows if storey is None else rows[rows[COL_STOREY] == storey]
                if only_gaps:
                    flagged = set(issues_before_edit.loc[issues_before_edit[COL_PSET] == pset, COL_GLOBAL_ID])
                    flagged |= {g for (g, ps, _) in store if ps == pset}
                    view_rows = view_rows[view_rows[COL_GLOBAL_ID].isin(flagged)]
                ordered = {s: i for i, s in enumerate(storeys_all)}
                view_rows = view_rows.sort_values(COL_STOREY, key=lambda s: s.map(lambda x: ordered.get(x, len(ordered))),
                                                  kind="stable")

                total = len(rows)
                detail = " mit Lücken oder Fehlern" if only_gaps else ""
                st.markdown(f"**{class_label(ifc_class)} · {pset}** — {len(view_rows)} von {total} Bauteilen{detail}"
                            + (f" · {storey}" if storey else ""))
                notes = []
                if len(rows) < len(table):
                    notes.append(f"{len(table) - len(rows)} Bauteil(e) ohne dieses Property-Set, anlegen im Modus «{MODE_NEW}»")
                if added:
                    notes.append(f"Spalten aus den Regeln, die im Modell noch fehlen: {', '.join(added)}")

                left, right = st.columns([1.25, 1], gap="medium")
                with left:
                    shown = pending.apply(view_rows, store, pset)      # Tabelle mit den offenen Änderungen
                    config = column_config_for(shown, raw_table, pset_rules)
                    config[COL_SHOW] = st.column_config.CheckboxColumn(COL_SHOW, help="Bauteil anwählen: 3D und Eigenschaften",
                                                                       width="small")
                    selection = st.session_state.setdefault("sel3d", [])
                    with_show = shown.copy()
                    with_show.insert(0, COL_SHOW, with_show[COL_GLOBAL_ID].isin(selection).astype(bool))
                    fingerprint = zlib.crc32("|".join(with_show[COL_GLOBAL_ID]).encode())
                    context = f"{file_name}::{len(ifc_bytes)}::{ifc_class}::{pset}"
                    edited_full = st.data_editor(
                        with_show,
                        disabled=LOCKED_COLUMNS,
                        hide_index=True,
                        column_config=config,
                        num_rows="fixed",
                        key=f"editor::{context}::{storey}::{fingerprint}::{st.session_state['editor_rev']}",
                    )
                    checked_rows = list(edited_full.loc[edited_full[COL_SHOW] == True, COL_GLOBAL_ID])  # noqa: E712
                    visible = set(edited_full[COL_GLOBAL_ID])
                    # Auswahl aus der Tabelle übernehmen, Auswahl ausserhalb der Tabelle bleibt
                    new_selection = [g for g in selection if g not in visible or g in checked_rows]
                    new_selection += [g for g in checked_rows if g not in new_selection]
                    st.session_state["sel3d"] = new_selection
                    edited = edited_full.drop(columns=[COL_SHOW])   # die Häkchen sind keine Änderung am Modell
                    pending.merge_edits(store, view_rows, shown, edited, ifc_class, pset, pending.SOURCE_TABLE)
                    st.caption("Zelle anklicken zum Ändern, Zelle leeren entfernt den Wert. Häkchen «3D» oder Klick im "
                               "Modell wählt das Bauteil an (Ctrl+Klick für mehrere). * Pflicht laut Regeln.")
                    others = sum(1 for (_, ps, _), e in store.items() if e[COL_CLASS] != ifc_class or ps != pset)
                    if others:
                        notes.append(f"dazu {others} offene Änderung(en) in anderen Klassen oder Property-Sets")
                    if notes:
                        st.caption(" · ".join(notes))
                with right:
                    if is_open(tab_work):
                        viewer_select(ifc_bytes, set(edited[COL_GLOBAL_ID]))
                    chosen = st.session_state.get("sel3d", [])
                    in_pset = [g for g in chosen if g in props_all and pset in props_all[g]["psets"]
                               and props_all[g]["cls"] == ifc_class]
                    if len(chosen) == 1 and in_pset:
                        properties_form(in_pset[0], pset, [c for c in edited.columns if c not in LOCKED_COLUMNS],
                                        store, pending.validate_all(store, get_rules()))
                    elif len(chosen) == 1:
                        info = props_all.get(chosen[0], {})
                        st.caption(f"«{info.get('name') or 'Bauteil'}» hat kein {pset}. "
                                   "Links eine andere Klasse oder ein anderes Property-Set wählen.")
                    elif chosen:
                        names = [props_all[g]["name"] or "ohne Name" for g in chosen if g in props_all]
                        st.caption(f"{len(chosen)} Bauteile angewählt: {', '.join(names[:5])}"
                                   + (" …" if len(names) > 5 else "") + ". Eigenschaften erscheinen, wenn genau eines angewählt ist.")
                    else:
                        st.caption("Bauteil in der Tabelle anhaken oder im Modell anklicken, dann erscheinen hier seine Eigenschaften.")

        # Filterspalte, nach der Tabelle gezeichnet: Zähler enthalten die Eingaben dieses Durchlaufs
        with rail:
            issues_now = model_check.check_model(props_all, get_rules(), store)
            open_by_class = issues_now[COL_CLASS].value_counts().to_dict() if len(issues_now) else {}
            count = {c: sum(1 for p in props_all.values() if p["cls"] == c) for c in classes}

            def rail_label(c):
                bad = open_by_class.get(c, 0)
                return f"{class_label(c)} · {count[c]}" + (f"  :red[● {bad}]" if bad else "")

            pick(st.radio, "Bauteilklasse", classes, "ifc_class", "work_class", format_func=rail_label,
                 help="● Anzahl offener Werte (Pflichtwert fehlt oder Wert ungültig)")
            if psets:
                pick(st.selectbox, "Property-Set", psets, "pset", "work_pset")
            if class_storeys:
                pick(st.pills, "Geschoss", class_storeys, "storey", "work_storey", selection_mode="single",
                     help="Nichts gewählt: alle Geschosse")
            st.toggle("nur Lücken und Fehler", key="only_gaps", disabled=mode == MODE_NEW or view == VIEW_3D,
                      help="Nur Bauteile mit fehlendem Pflichtwert, ungültigem Wert oder offener Änderung in diesem Pset")

# =============================== 3 Prüfen & Speichern ========================
validated = pending.validate_all(store, get_rules())
signature = validated.to_csv(index=False)
if st.session_state.get("validated_signature") != signature:   # Kopie aus einem älteren Stand verwerfen
    st.session_state["validated_signature"] = signature
    reset_downstream()
n_ok = int(validated[COL_VALID].sum()) if len(validated) else 0
n_bad = len(validated) - n_ok

with tab_check:
    if model is None:
        st.info("Zuerst im Bereich «Laden» ein Modell laden.")
    else:
        props_all = get_properties(ifc_bytes)
        rail, main, side = st.columns([1, 3.4, 1.5], gap="medium")
        with rail:
            status_counts = {STATUS_ALL: len(validated), STATUS_OK: n_ok, STATUS_BAD: n_bad}
            status_filter = st.radio("Status", list(status_counts), key="check_status",
                                     format_func=lambda s: f"{'Alle Änderungen' if s == STATUS_ALL else s} · {status_counts[s]}")
            store_classes = sorted(set(validated[COL_CLASS])) if len(validated) else []
            class_filter = st.radio("Nach Klasse", [ALL_CLASSES, *store_classes], key="check_class",
                                    format_func=lambda c: c if c == ALL_CLASSES else
                                    f"{class_label(c)} · {int((validated[COL_CLASS] == c).sum())}")
            st.caption(f"Regeln: {rules_label}")

        with main:
            st.markdown(f"##### Änderungen · {len(validated)} offen")
            if validated.empty:
                st.info("Noch keine Änderungen. Werte in der «Arbeitsfläche» ändern.")
            else:
                shown_changes = validated
                if status_filter == STATUS_OK:
                    shown_changes = shown_changes[shown_changes[COL_VALID]]
                elif status_filter == STATUS_BAD:
                    shown_changes = shown_changes[~shown_changes[COL_VALID]]
                if class_filter != ALL_CLASSES:
                    shown_changes = shown_changes[shown_changes[COL_CLASS] == class_filter]
                keys = [(r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY]) for _, r in shown_changes.iterrows()]
                frame = pd.DataFrame({
                    COL_REMOVE: [False] * len(shown_changes),
                    "Status": ["✓" if v else "✗" for v in shown_changes[COL_VALID]],
                    "Bauteil": [f"{r[COL_NAME] or 'ohne Name'} · {props_all.get(r[COL_GLOBAL_ID], {}).get('storey') or '–'}"
                                for _, r in shown_changes.iterrows()],
                    "Klasse · Pset": [f"{class_label(r[COL_CLASS])} · {r[COL_PSET]}" for _, r in shown_changes.iterrows()],
                    "Property": list(shown_changes[COL_PROPERTY]),
                    "Alt": [_text(v) for v in shown_changes[COL_OLD]],
                    "Neu": [_text(v) for v in shown_changes[COL_NEW]],
                    "Meldung": [m or "" for m in shown_changes[COL_MESSAGE]],
                    "Eingabe über": list(shown_changes[COL_SOURCE]),
                })
                marked = st.data_editor(
                    frame, hide_index=True, num_rows="fixed", disabled=[c for c in frame.columns if c != COL_REMOVE],
                    key=f"changes::{zlib.crc32(signature.encode())}::{status_filter}::{class_filter}",
                    column_config={COL_REMOVE: st.column_config.CheckboxColumn(
                        COL_REMOVE, help="Änderung aus der Liste nehmen, der Wert im Modell bleibt wie er war", width="small")},
                )
                ticked = [keys[i] for i, v in enumerate(marked[COL_REMOVE]) if v]
                c1, c2, c3 = st.columns([1.2, 1, 1.2])
                if c1.button(f"{len(ticked)} markierte entfernen", disabled=not ticked):
                    pending.remove(store, ticked)
                    restart_editor()
                    st.rerun()
                with c3.popover("Alle verwerfen …"):
                    st.write(f"Alle {len(validated)} offenen Änderungen verwerfen? Das lässt sich nicht rückgängig machen.")
                    if st.button("Ja, alle verwerfen", type="primary"):
                        store.clear()
                        restart_editor()
                        st.rerun()
                if n_bad:
                    st.caption("Änderungen mit ✗ werden nicht gespeichert. In der «Arbeitsfläche» korrigieren oder hier entfernen.")

            st.markdown("##### Modell gegen Regeln")
            st.caption(f"Alle Bauteile mit dem aktuellen Stand (Modell plus offene Änderungen), Regeln: {rules_label}.")
            issues = model_check.check_model(props_all, get_rules(), store)
            if issues.empty:
                st.success("Alle Bauteile erfüllen die Regeln.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Regelverstösse", len(issues))
                m2.metric("betroffene Bauteile", issues[COL_GLOBAL_ID].nunique())
                m3.metric("davon Pflichtwert fehlt", int(issues[model_check.COL_PROBLEM].str.startswith("Pflichtwert").sum()))
                st.dataframe(issues.drop(columns=[COL_GLOBAL_ID]), hide_index=True)
                choices = list(dict.fromkeys(zip(issues[COL_GLOBAL_ID], issues[COL_CLASS], issues[COL_PSET])))
                o1, o2 = st.columns([2.2, 1], vertical_alignment="bottom")
                target = o1.selectbox(
                    "Bauteil öffnen", choices, key="open_target",
                    format_func=lambda t: f"{props_all[t[0]]['name'] or 'ohne Name'} · {props_all[t[0]]['storey'] or '–'} "
                                          f"· {class_label(t[1])} · {t[2]}")
                o2.button("zum Bauteil →", on_click=open_element, args=target, width="stretch")

        with side:
            with st.container(border=True):
                st.caption("SPEICHERN")
                st.markdown(f"### {n_ok} gültige Änderung{'en' if n_ok != 1 else ''}")
                st.write("werden in eine **Kopie** geschrieben. Das Original bleibt unverändert."
                         + (f" {n_bad} Fehler werden nicht gespeichert." if n_bad else ""))
                user = st.text_input("Name für das Protokoll", placeholder="z. B. Brandschutzplanung", key="user")
                if st.button("IFC-Kopie erstellen", type="primary", disabled=n_ok == 0, width="stretch"):
                    try:
                        with st.spinner("Schreibe IFC-Kopie und Bauteilliste …"):
                            stem = Path(file_name).stem
                            copy_bytes = ifc_writer.apply_changes(ifc_bytes, validated)
                            props_after = ifc_reader.element_properties(ifc_reader.load_model(copy_bytes))
                            xlsx = report.build_workbook(
                                file_name=file_name, copy_name=f"{stem}_bearbeitet.ifc", original_bytes=ifc_bytes,
                                copy_bytes=copy_bytes, props_before=props_all, props_after=props_after,
                                validated=validated, rules=get_rules(), rules_label=rules_label, user=user,
                                storeys=get_storeys(ifc_bytes), schema=model.schema)
                            after_issues = model_check.check_model(props_after, get_rules())
                            st.session_state.update(
                                result_ifc=copy_bytes, result_xlsx=xlsx,
                                result_log=changelog.to_csv_bytes(changelog.build_log(validated, user)),
                                result_after=(len(props_after) - after_issues[COL_GLOBAL_ID].nunique(), len(props_after)))
                    except Exception as exc:
                        st.error(f"Beim Schreiben ist ein Fehler aufgetreten: {exc}")
                if "result_ifc" in st.session_state:
                    stem = Path(file_name).stem
                    st.success("IFC-Kopie und Bauteilliste sind bereit.")
                    st.download_button("IFC-Kopie herunterladen", st.session_state["result_ifc"],
                                       file_name=f"{stem}_bearbeitet.ifc", mime="application/octet-stream",
                                       type="primary", width="stretch")
                    st.download_button("Bauteilliste (Excel)", st.session_state["result_xlsx"],
                                       file_name=f"{stem}_bauteilliste.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       width="stretch")
                    st.download_button("Protokoll (CSV)", st.session_state["result_log"],
                                       file_name=f"{stem}_protokoll.csv", mime="text/csv", width="stretch")
            if "result_after" in st.session_state:
                ok, total = st.session_state["result_after"]
                with st.container(border=True):
                    st.caption("NACH DEM SPEICHERN")
                    st.write(f"Erfüllt danach: {ok} von {total} Bauteilen ({round(100 * ok / max(1, total))} %). "
                             "Die Kopie lässt sich später im Bereich «Laden» wieder hochladen, um weiterzuarbeiten.")

# =============================== Regeln ======================================
with tab_rules:
    rules_rev = st.session_state.setdefault("rules_rev", 0)
    current_rules = base_rules()
    standard_rules = load_rules(STANDARD_RULES_PATH)
    diffs = rules_store.differences(current_rules, standard_rules)
    left, right = st.columns([3.2, 1.1], gap="medium")
    with left:
        st.write("**Prüfregeln** aus `config/rules.json`, eine Zeile pro Property. Werte direkt in der Tabelle ändern, "
                 "unten eine Zeile hinzufügen, Zeilen links markieren und mit dem Papierkorb löschen. Erst «Regeln speichern» übernimmt.")
        if message := st.session_state.pop("rules_message", None):
            st.success(message)
        if ids_info:
            st.info("Eine IDS-Datei ist aktiv. Ihre Regeln haben bei gleicher Property Vorrang und erscheinen hier nicht.")
        labels = list(rules_store.TYPE_LABELS.values())
        edited_rules = st.data_editor(
            rules_store.rules_to_table(current_rules), num_rows="dynamic", hide_index=True, key=f"rules_editor::{rules_rev}",
            column_config={
                rules_store.COL_CLASS: st.column_config.TextColumn("Klasse", help="IFC-Klasse, z. B. IfcWall"),
                rules_store.COL_PSET: st.column_config.TextColumn("Pset", help="Property-Set, z. B. Pset_WallCommon"),
                rules_store.COL_PROP: st.column_config.TextColumn("Property", help="Name der Property, z. B. FireRating"),
                rules_store.COL_TYPE: st.column_config.SelectboxColumn("Typ", options=labels, required=True),
                rules_store.COL_VALUES: st.column_config.TextColumn(
                    "Werteliste", help="Bei Werteliste: erlaubte Werte mit Komma trennen. Bei Ja/Nein optional ein fester Wert."),
                rules_store.COL_MIN: st.column_config.NumberColumn("Min", help="Bei Zahl: kleinster erlaubter Wert"),
                rules_store.COL_MAX: st.column_config.NumberColumn("Max", help="Bei Zahl: grösster erlaubter Wert"),
                rules_store.COL_PATTERN: st.column_config.TextColumn("Muster", help="Bei Muster: regulärer Ausdruck, z. B. VKF.*"),
                rules_store.COL_REQUIRED: st.column_config.CheckboxColumn("Pflicht", help="Leer ist ein Fehler"),
                rules_store.COL_NOTE: st.column_config.TextColumn("Hinweis", help="Erscheint als Hilfe im Pop-up und im Formular"),
            },
        )
        new_rules, rule_errors = rules_store.table_to_rules(edited_rules)
        unsaved = not rule_errors and new_rules != current_rules
        if unsaved:
            st.caption("Es gibt ungespeicherte Änderungen.")

    with right:
        with st.container(border=True):
            st.caption("REGELN")
            st.write(f"{n_rules(current_rules)} Regeln in {len(current_rules)} Klassen")
            if diffs:
                with st.expander(f"{len(diffs)} Abweichung(en) von der Standardvorlage"):
                    for d in diffs:
                        st.write("· " + d)
            else:
                st.caption("Entspricht der Standardvorlage `config/rules_standard.json`.")
            if st.button("Regeln speichern", type="primary", disabled=not unsaved and not rule_errors, width="stretch"):
                if rule_errors:
                    for message in rule_errors:
                        st.error(message)
                else:
                    rules_store.save_rules(new_rules)
                    base_rules.clear()
                    st.session_state["rules_rev"] = rules_rev + 1
                    st.session_state["rules_message"] = "Regeln gespeichert. Sie gelten ab sofort für Arbeitsfläche, Prüfen und 3D."
                    st.rerun()
            st.download_button("rules.json herunterladen",
                               (json.dumps(current_rules, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                               file_name="rules.json", mime="application/json", width="stretch")
        with st.container(border=True):
            st.caption("STANDARDVORLAGE")
            confirm = st.checkbox("Eigene Regeln verwerfen", disabled=not diffs and not unsaved,
                                  help="Sicherung gegen versehentliches Zurücksetzen")
            if st.button("Auf Standard zurücksetzen", disabled=not confirm, width="stretch"):
                rules_store.reset_rules()
                base_rules.clear()
                st.session_state["rules_rev"] = rules_rev + 1
                st.session_state["rules_message"] = "Regeln auf die Standardvorlage zurückgesetzt."
                st.rerun()
            with st.expander("Vorlage ansehen"):
                st.dataframe(rules_store.rules_to_table(standard_rules), hide_index=True)

# =============================== Kopfzeile füllen ============================
chips = []
if file_name:
    chips.append(f":gray-badge[{file_name}{' · ' + model.schema if model is not None else ''}]")
if len(validated):
    chips.append(f":green-badge[✓ {n_ok} gültig]")
    if n_bad:
        chips.append(f":red-badge[✗ {n_bad} Fehler]")
else:
    chips.append(":gray-badge[keine Änderungen]")
if st.session_state.get("sel3d"):
    chips.append(f":orange-badge[{len(st.session_state['sel3d'])} angewählt]")
status_box.markdown("  ".join(chips))
