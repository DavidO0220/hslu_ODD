"""IFC-Property-Editor: Weboberfläche.

Start:  streamlit run app.py

Die Oberfläche enthält keine IFC-Logik. Sie ruft nur Funktionen aus core/ auf.

Zwei Eigenheiten von Streamlit bestimmen den Aufbau:
- Bei jedem Klick läuft dieses Skript von oben neu durch. Das Modell wird
  deshalb mit st.cache_resource nur einmal geladen.
- Die Schritte sind Reiter (st.tabs). Streamlit führt alle Reiter bei
  jedem Durchlauf aus, so bleiben Eingaben erhalten, wenn man zwischen den
  Schritten wechselt.

Alle offenen Änderungen liegen in einer gemeinsamen Liste (core/pending.py,
in st.session_state["pending"]). Die Tabelle in «Bearbeiten» und das Pop-up
im Reiter «3D-Modell» schreiben beide hinein, «Prüfen» und «Speichern» lesen
daraus. Ein Wechsel der Klasse verwirft deshalb keine Eingaben.

Im Schritt «Bearbeiten» steht neben der Tabelle der kleine 3D-Viewer (viewer/).
Die bearbeitbare Tabelle meldet keine angeklickte Zeile zurück. Bauteile
werden deshalb über die Häkchen-Spalte «3D» in der Tabelle angewählt.

Bauteilklasse und Property-Set lassen sich in «Laden» und «Bearbeiten»
wählen. Beide Auswahlfelder sind gekoppelt (siehe pick).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

import viewer
from core import changelog, geometry, ifc_reader, ifc_writer, pending
from core.display import NO, YES, add_columns, bool_columns, to_display
from core.schema import (COL_CLASS, COL_GLOBAL_ID, COL_MESSAGE, COL_NAME, COL_NEW, COL_OLD, COL_PROPERTY,
                         COL_PSET, COL_STOREY, COL_VALID, LOCKED_COLUMNS)
from core.validator import load_rules, rules_for_class

TEST_MODEL = Path(__file__).resolve().parent / "data" / "testmodell.ifc"
COL_SHOW = "3D"   # Häkchen-Spalte: Bauteil im Viewer zeigen. Nur Oberfläche, wird nie geschrieben.
MAX_CARDS = 5     # so viele angewählte Bauteile werden unter dem Viewer mit Werten gezeigt
ALL_STOREYS = "alle Geschosse"
MODE_EDIT, MODE_NEW = "Bestehendes Pset bearbeiten", "Neues Pset anlegen"

st.set_page_config(page_title="IFC-Property-Editor", layout="wide")


@st.cache_resource(show_spinner="IFC-Modell wird geladen …")
def get_model(file_bytes: bytes):
    """Lädt das Modell nur einmal pro Datei, nicht bei jedem Klick."""
    return ifc_reader.load_model(file_bytes)


@st.cache_data(show_spinner="Tabelle wird aufgebaut …")
def get_table(file_bytes: bytes, ifc_class: str, pset: str):
    """Tabelle zwischenspeichern: bei grossen Modellen dauert das Auslesen spürbar."""
    return ifc_reader.to_table(get_model(file_bytes), ifc_class, pset)


@st.cache_data
def get_rules() -> dict:
    return load_rules()


@st.cache_resource(show_spinner="3D-Geometrie wird berechnet …")
def get_meshes(file_bytes: bytes) -> list[dict]:
    """Geometrie nur einmal pro Datei berechnen, das dauert bei grossen Modellen."""
    return geometry.load_meshes(get_model(file_bytes))


@st.cache_resource(show_spinner="Eigenschaften werden gelesen …")
def get_properties(file_bytes: bytes) -> dict:
    """Alle Eigenschaften aller Bauteile, für das Pop-up im Reiter «3D-Modell»."""
    return ifc_reader.element_properties(get_model(file_bytes))


def change_store(file_key) -> dict:
    """Die gemeinsame Änderungsliste. Eine neue Datei beginnt mit einer leeren Liste."""
    if "pending" not in st.session_state or st.session_state.get("store_file") != file_key:
        st.session_state["store_file"] = file_key
        st.session_state["pending"] = {}
        st.session_state["editor_rev"] = 0
        st.session_state["sel3d"] = []      # Auswahl im kleinen Viewer
    return st.session_state["pending"]


def restart_editor() -> None:
    """Tabelleneditor neu aufsetzen, damit er Änderungen von aussen (3D, Verwerfen) zeigt."""
    st.session_state["editor_rev"] = st.session_state.get("editor_rev", 0) + 1


def pending_for_viewer(store: dict, checked: pd.DataFrame) -> list[dict]:
    """Offene Änderungen mit Prüfergebnis in der Form für das Pop-up (Werte in Anzeigeform)."""
    result = {(r[COL_GLOBAL_ID], r[COL_PSET], r[COL_PROPERTY]): (bool(r[COL_VALID]), r[COL_MESSAGE] or "")
              for _, r in checked.iterrows()}
    return [{"guid": g, "pset": ps, "prop": pr, "old": e[COL_OLD], "new": e[COL_NEW],
             "valid": result.get((g, ps, pr), (True, ""))[0], "msg": result.get((g, ps, pr), (True, ""))[1]}
            for (g, ps, pr), e in store.items()]


def _text(value) -> str:
    return "leer" if value is None or (isinstance(value, float) and value != value) else str(value)


def show_3d_panel(file_bytes: bytes, current: pd.DataFrame, ifc_class: str) -> None:
    """Kleiner Viewer neben der Tabelle. Klick im 3D wählt aus, wie ein Häkchen in der Spalte «3D»."""
    try:
        meshes = get_meshes(file_bytes)
    except Exception as exc:
        st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
        return
    if not meshes:
        st.info("Das Modell enthält keine darstellbare Geometrie.")
        return

    selected = st.session_state.get("sel3d", [])
    value = viewer.select3d(meshes, selected, model_id=f"{file_name}:{len(file_bytes)}",
                            focus=focus_on_select, transparency=transparency / 100)
    if value and value.get("nonce") != st.session_state.get("select_nonce"):
        st.session_state["select_nonce"] = value.get("nonce")
        st.session_state["sel3d"] = list(value.get("ids", []))
        follow_click(value.get("clicked"), set(current[COL_GLOBAL_ID]), file_bytes)
        restart_editor()            # Häkchen in der Tabelle neu setzen
        st.rerun()

    if not selected:
        st.caption(f"Bauteil im 3D anklicken (Ctrl+Klick für mehrere) oder Häkchen in der Spalte «{COL_SHOW}» setzen.")
        return
    props = [c for c in current.columns if c not in LOCKED_COLUMNS]
    rows = current[current[COL_GLOBAL_ID].isin(selected)]
    for _, row in rows.head(MAX_CARDS).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row[COL_NAME] or 'ohne Name'}** · {row[COL_STOREY] or 'ohne Geschoss'} · {ifc_class}  \n"
                        + " · ".join(f"{p}: **{_text(row[p])}**" for p in props))
    if len(rows) > MAX_CARDS:
        st.caption(f"… und {len(rows) - MAX_CARDS} weitere ausgewählte Bauteile.")
    if len(selected) > len(rows):
        st.caption(f"{len(selected) - len(rows)} ausgewählte(s) Bauteil(e) aus anderen Klassen, Psets oder Geschossen.")


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
    st.session_state["reset::edit_storey"] = True   # Geschossfilter erst beim nächsten Durchlauf zurücksetzen


def _sync(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = st.session_state[widget_key]


def pick(label: str, options: list[str], state_key: str, widget_key: str, where=st):
    """Auswahlfeld, das mit dem gleichen Feld im anderen Reiter gekoppelt ist.

    Der gemeinsame Wert liegt in st.session_state[state_key]. Vor dem Zeichnen
    bekommt das Feld diesen Wert, bei einer Änderung schreibt es ihn zurück.
    So zeigen «Laden» und «Bearbeiten» immer dieselbe Klasse und dasselbe Pset.
    """
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = options[0]
    st.session_state[widget_key] = st.session_state[state_key]
    return where.selectbox(label, options, key=widget_key, on_change=_sync, args=(widget_key, state_key))


def pick_class_and_pset(prefix: str):
    """Die beiden gekoppelten Auswahlfelder. Gibt (Klasse, Pset oder None) zurück."""
    col1, col2 = st.columns(2)
    ifc_class = pick("Bauteilklasse", classes, "ifc_class", f"{prefix}_class", col1)
    psets = ifc_reader.list_psets(model, ifc_class)
    if not psets:
        st.warning(f"Die Bauteile der Klasse {ifc_class} haben keine Property-Sets.")
        return ifc_class, None
    return ifc_class, pick("Property-Set", psets, "pset", f"{prefix}_pset", col2)


def column_config_for(table: pd.DataFrame, raw: pd.DataFrame, pset_rules: dict) -> dict:
    """Auswahlfelder in der Tabelle: Ja/Nein und Wertelisten aus den Regeln, sonst freier Text."""
    config = {}
    bools = set(bool_columns(raw)) | {p for p, r in pset_rules.items() if r.get("type") == "bool"}
    for col in table.columns:
        rule = pset_rules.get(col, {})
        if col in bools:
            config[col] = st.column_config.SelectboxColumn(col, options=[YES, NO])
        elif rule.get("type") == "enum":
            allowed = list(rule.get("values", []))
            # Werte aus dem Modell, die nicht in der Liste stehen (z. B. EI45), bleiben sichtbar
            extra = sorted({str(v) for v in table[col] if v is not None and not pd.isna(v)} - set(allowed))
            config[col] = st.column_config.SelectboxColumn(
                col, options=allowed + extra, help=f"Werteliste: {', '.join(allowed)}")
        elif rule.get("type") == "float":
            low, high = rule.get("min"), rule.get("max")
            config[col] = st.column_config.TextColumn(col, help=f"Zahl zwischen {low} und {high}")
    return config


def pick_storey(storeys: list[str], key: str, where=st) -> str:
    """Geschossfilter. Gibt ALL_STOREYS oder ein Geschoss zurück."""
    options = [ALL_STOREYS, *storeys]
    if st.session_state.pop(f"reset::{key}", False) or st.session_state.get(key) not in options:
        st.session_state[key] = ALL_STOREYS
    return where.selectbox("Geschoss", options, key=key)


def new_pset_form(file_bytes: bytes, ifc_class: str, store: dict) -> None:
    """Formular: ein neues Property-Set für mehrere Bauteile einer Klasse vormerken."""
    props = get_properties(file_bytes)
    class_rules = rules_for_class(get_rules(), ifc_class)
    elements = {g: p for g, p in props.items() if p["cls"] == ifc_class}
    if not elements:
        st.info(f"Im Modell gibt es keine Bauteile der Klasse {ifc_class}.")
        return

    c1, c2, c3 = st.columns([1.2, 1, 1])
    template = c2.selectbox("Vorlage", ["— ohne Vorlage —", *class_rules], key=f"new_tpl::{ifc_class}",
                            help="Property-Sets, für die in config/rules.json Regeln stehen")
    from_rules = template in class_rules
    name = c1.text_input("Name des neuen Property-Sets", value=template if from_rules else "",
                         key=f"new_name::{ifc_class}::{template}", placeholder="z. B. CH_Brandschutz")
    name = name.strip()
    if name.startswith("Pset_") and name not in class_rules:
        st.warning("Das Präfix «Pset_» ist für die Standard-Sets von buildingSMART reserviert. "
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
    storey = pick_storey(sorted({elements[g]["storey"] for g in without}), f"new_storey::{ifc_class}", c3)
    candidates = [g for g in without if storey == ALL_STOREYS or elements[g]["storey"] == storey]
    label = lambda g: f"{elements[g]['name'] or 'ohne Name'} · {elements[g]['storey'] or 'ohne Geschoss'}"  # noqa: E731
    targets = st.multiselect("Bauteile, die das neue Property-Set bekommen", candidates, default=candidates,
                             format_func=label, key=f"new_targets::{ifc_class}::{name}::{storey}")
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
            st.success(f"{n} Werte vorgemerkt. Geprüft und gespeichert wird in «Prüfen» und «Speichern».")


def reset_downstream() -> None:
    """Datei, Klasse oder Pset gewechselt: alte Bearbeitungen und Ergebnisse verwerfen."""
    for key in ("result_ifc", "result_log"):
        st.session_state.pop(key, None)


# Einstellungen für den 3D-Viewer, gelten für die ganze Sitzung
with st.sidebar:
    st.subheader("3D-Ansicht")
    show_3d = st.toggle("3D-Ansicht anzeigen", value=True)
    focus_on_select = st.toggle(
        "Beim Anwählen hinzoomen", value=True, disabled=not show_3d,
        help="Die Kamera fährt zur Auswahl, der Rest des Modells wird transparent. "
             "Ausgeschaltet bleibt die Auswahl orange markiert, die Kamera bleibt stehen.",
    )
    transparency = st.slider("Transparenz übriges Modell (%)", 0, 95, 85, step=5,
                             disabled=not (show_3d and focus_on_select))
    st.divider()

st.title("IFC-Property-Editor")
st.caption("Properties von IFC-Modellen im Browser ergänzen, prüfen und zurückschreiben")
tab_load, tab_edit, tab_3d, tab_check, tab_save = st.tabs(
    ["1  Laden", "2  Bearbeiten", "3  3D-Modell", "4  Prüfen", "5  Speichern"])

# =============================== 1 Laden =====================================
with tab_load:
    uploaded = st.file_uploader("IFC-Datei hochladen", type=["ifc"])
    use_test = TEST_MODEL.exists() and st.checkbox("Testmodell aus data/ verwenden")

    ifc_bytes, file_name = None, None
    if uploaded is not None:
        ifc_bytes, file_name = uploaded.getvalue(), uploaded.name
    elif use_test:
        ifc_bytes, file_name = TEST_MODEL.read_bytes(), TEST_MODEL.name

    model = table = None
    store = change_store((file_name, len(ifc_bytes)) if ifc_bytes is not None else None)
    if ifc_bytes is None:
        st.info("Noch keine Datei geladen.")
    else:
        try:
            model = get_model(ifc_bytes)
        except Exception as exc:  # beschädigte oder ungültige Datei
            st.error(f"Die Datei konnte nicht gelesen werden: {exc}")

    classes = ifc_reader.list_classes(model) if model is not None else []
    if model is not None:
        if not classes:
            st.warning("Im Modell wurden keine Bauteile gefunden.")
        else:
            ifc_class, pset = pick_class_and_pset("load")
            if pset is not None:
                context = (file_name, len(ifc_bytes), ifc_class, pset)
                if st.session_state.get("context") != context:
                    st.session_state["context"] = context
                    reset_downstream()

                raw_table = get_table(ifc_bytes, ifc_class, pset)
                table = to_display(raw_table)
                empty = int(table.drop(columns=LOCKED_COLUMNS).isna().sum().sum())
                m1, m2, m3 = st.columns(3)
                m1.metric("Bauteile", len(table))
                m2.metric("Properties", len(table.columns) - len(LOCKED_COLUMNS))
                m3.metric("Leere Werte", empty)
                st.dataframe(table, hide_index=True)

# =============================== 2 Bearbeiten ================================
edited = None
selected_ids: list[str] = []
with tab_edit:
    if not classes:
        st.info("Zuerst im Schritt «Laden» eine Datei laden.")
    else:
        mode = st.radio("Modus", [MODE_EDIT, MODE_NEW], horizontal=True, key="edit_mode", label_visibility="collapsed")

    if classes and mode == MODE_NEW:
        st.caption("Ein Property-Set anlegen, das die gewählten Bauteile noch nicht haben.")
        new_class = pick("Bauteilklasse", classes, "ifc_class", "new_class", st.columns(3)[0])
        new_pset_form(ifc_bytes, new_class, store)

    elif classes:
        st.caption("Werte in einem Property-Set ändern, das die Bauteile schon haben.")
        pick_class_and_pset("edit")   # dieselbe Auswahl wie in «Laden»
        if table is None:
            st.info(f"Die Klasse hat noch kein Property-Set. Eines im Modus «{MODE_NEW}» anlegen.")
        else:
            props_all = get_properties(ifc_bytes)
            with_pset = {g for g, p in props_all.items() if pset in p["psets"]}
            rows = table[table[COL_GLOBAL_ID].isin(with_pset)]
            pset_rules = rules_for_class(get_rules(), ifc_class).get(pset, {})
            added = [p for p in pset_rules if p not in rows.columns]
            rows = add_columns(rows, added)          # Properties laut Regeln, die im Modell noch fehlen
            storey = pick_storey(sorted({s for s in rows[COL_STOREY] if s}), "edit_storey", st.columns(3)[0])
            view = rows if storey == ALL_STOREYS else rows[rows[COL_STOREY] == storey]

            st.write(f"**{ifc_class} · {pset}** — {len(view)} Bauteil(e). Werte direkt in der Tabelle ändern. "
                     "GlobalId, Name und Geschoss sind gesperrt. Zelle leeren entfernt den Wert.")
            notes = []
            if len(rows) < len(table):
                notes.append(f"{len(table) - len(rows)} Bauteil(e) der Klasse haben dieses Property-Set nicht, "
                             f"anlegen im Modus «{MODE_NEW}»")
            if added:
                notes.append(f"Spalten aus den Regeln, die im Modell noch fehlen: {', '.join(added)}")
            if notes:
                st.caption(" · ".join(notes))

            left, right = st.columns([1.15, 1], gap="medium") if show_3d else (st.container(), None)
            with left:
                shown = pending.apply(view, store, pset)      # Tabelle mit den offenen Änderungen
                config = column_config_for(shown, raw_table, pset_rules)
                config[COL_SHOW] = st.column_config.CheckboxColumn(COL_SHOW, help="Bauteil im 3D-Viewer zeigen", width="small")
                selection = st.session_state.setdefault("sel3d", [])
                with_show = shown.copy()
                with_show.insert(0, COL_SHOW, with_show[COL_GLOBAL_ID].isin(selection).astype(bool))
                edited_full = st.data_editor(
                    with_show,
                    disabled=LOCKED_COLUMNS,
                    hide_index=True,
                    column_config=config,
                    num_rows="fixed",
                    key=f"editor::{'::'.join(map(str, st.session_state['context']))}::{storey}::{st.session_state['editor_rev']}",
                )
                checked = list(edited_full.loc[edited_full[COL_SHOW] == True, COL_GLOBAL_ID])  # noqa: E712
                visible = set(edited_full[COL_GLOBAL_ID])
                # Auswahl aus der Tabelle übernehmen, Auswahl ausserhalb der Tabelle bleibt
                new_selection = [g for g in selection if g not in visible or g in checked]
                new_selection += [g for g in checked if g not in new_selection]
                st.session_state["sel3d"] = new_selection
                selected_ids = new_selection
                edited = edited_full.drop(columns=[COL_SHOW])   # die Häkchen sind keine Änderung am Modell
                pending.merge_edits(store, view, shown, edited, ifc_class, pset)
                others = sum(1 for (_, ps, _), e in store.items() if e[COL_CLASS] != ifc_class or ps != pset)
                if others:
                    st.caption(f"Dazu {others} offene Änderung(en) in anderen Klassen oder Property-Sets, siehe «Prüfen».")
            if right is not None:
                with right:
                    show_3d_panel(ifc_bytes, edited, ifc_class)

# =============================== 3 3D-Modell =================================
with tab_3d:
    if model is None:
        st.info("Zuerst im Schritt «Laden» eine Datei laden.")
    else:
        try:
            meshes = get_meshes(ifc_bytes)
        except Exception as exc:
            meshes = []
            st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
        if meshes:
            props = get_properties(ifc_bytes)
            checked_now = pending.validate_all(store, get_rules())
            value = viewer.model3d(meshes, props, get_rules(), pending_for_viewer(store, checked_now),
                                   model_id=f"{file_name}:{len(ifc_bytes)}", height=720)
            # Neue Eingabe aus dem Pop-up in die gemeinsame Liste übernehmen
            if value and value.get("nonce") != st.session_state.get("model3d_nonce"):
                st.session_state["model3d_nonce"] = value.get("nonce")
                info = props.get(value.get("guid"))
                if info is not None:
                    for c in value.get("changes", []):
                        original = info["psets"].get(c["pset"], {}).get(c["prop"])
                        new_value = c.get("value")
                        # Wert eines neu angelegten Psets: Typ (Zahl, Ja/Nein) der Vormerkung beibehalten
                        before = store.get((value["guid"], c["pset"], c["prop"]))
                        if before is not None and original is None and not isinstance(before[COL_NEW], str):
                            kind = pending.KIND_BOOL if isinstance(before[COL_NEW], bool) else pending.KIND_NUMBER
                            try:
                                new_value = pending.typed(new_value, kind)
                            except ValueError:
                                pass
                        pending.put(store, value["guid"], info["name"], info["cls"], c["pset"], c["prop"],
                                    original, new_value)
                    restart_editor()
                    st.rerun()
            n_bad = int((~checked_now[COL_VALID].astype(bool)).sum()) if len(checked_now) else 0
            c1, c2 = st.columns([3, 1])
            c1.caption(f"Offene Änderungen: {len(store)}, davon {n_bad} mit Fehler. "
                       "Bauteil anklicken, Werte im Fenster ändern, «Übernehmen». Geprüft und gespeichert wird in «Prüfen» und «Speichern».")
            if store and c2.button("Alle offenen Änderungen verwerfen"):
                store.clear()
                restart_editor()
                st.rerun()

# =============================== 4 Prüfen ====================================
validated = None
with tab_check:
    if not store:
        st.info("Noch keine Änderungen. Werte im Schritt «Bearbeiten» oder im «3D-Modell» ändern.")
    else:
        validated = pending.validate_all(store, get_rules())
        # Ergebnis aus Schritt 5 verwerfen, sobald sich die Änderungen ändern
        signature = validated.to_csv(index=False)
        if st.session_state.get("validated_signature") != signature:
            st.session_state["validated_signature"] = signature
            reset_downstream()
        n_ok = int(validated[COL_VALID].sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Änderungen", len(validated))
        m2.metric("gültig", n_ok)
        m3.metric("Fehler", len(validated) - n_ok)
        for _, row in validated.iterrows():
            old = "leer" if row[COL_OLD] is None else row[COL_OLD]
            new = row[COL_NEW]
            new = "leer" if new is None else (YES if new is True else NO if new is False else new)
            text = f"**{row[COL_NAME]}** · {row[COL_PROPERTY]}: {old} → {new}"
            where = f"  ·  {row[COL_CLASS]} · {row[COL_PSET]}"
            if row[COL_VALID]:
                st.success(text + (f"  ·  {row[COL_MESSAGE]}" if row[COL_MESSAGE] else "") + where)
            else:
                st.error(f"{text}  ·  {row[COL_MESSAGE]}{where}")
        if n_ok < len(validated):
            st.caption("Fehlerhafte Änderungen werden nicht gespeichert. In «Bearbeiten» oder im «3D-Modell» korrigieren.")

# =============================== 5 Speichern =================================
with tab_save:
    if validated is None or not validated[COL_VALID].any():
        st.info("Es gibt noch keine gültigen Änderungen zum Speichern.")
    else:
        n_ok = int(validated[COL_VALID].sum())
        st.write(f"{n_ok} gültige Änderung(en) werden in eine **Kopie** der Datei geschrieben. Das Original bleibt unverändert.")
        user = st.text_input("Name für das Protokoll", placeholder="z. B. Brandschutzplanung")
        if st.button("IFC-Kopie erstellen", type="primary"):
            try:
                with st.spinner("Schreibe IFC-Kopie …"):
                    st.session_state["result_ifc"] = ifc_writer.apply_changes(ifc_bytes, validated)
                    st.session_state["result_log"] = changelog.to_csv_bytes(changelog.build_log(validated, user))
            except Exception as exc:
                st.error(f"Beim Schreiben ist ein Fehler aufgetreten: {exc}")

        if "result_ifc" in st.session_state:
            stem = Path(file_name).stem
            st.success("Die IFC-Kopie ist bereit.")
            c1, c2 = st.columns(2)
            c1.download_button("IFC-Kopie herunterladen", st.session_state["result_ifc"],
                               file_name=f"{stem}_bearbeitet.ifc", mime="application/octet-stream", type="primary")
            c2.download_button("Protokoll (CSV)", st.session_state["result_log"],
                               file_name=f"{stem}_protokoll.csv", mime="text/csv")

# =============================== Seitenleiste ================================
with st.sidebar:
    st.subheader("Status")
    st.write(f"Datei: {file_name or '—'}")
    if table is not None:
        st.write(f"Klasse: {ifc_class}  \nPset: {pset}")
    if selected_ids:
        st.write(f"Im 3D angewählt: {len(selected_ids)} Bauteil(e)")
    if validated is not None:
        st.write(f"Offene Änderungen: {len(validated)} · gültig: {int(validated[COL_VALID].sum())}")
