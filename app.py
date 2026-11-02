"""IFC-Property-Editor: Weboberfläche.

Start:  streamlit run app.py

Die Oberfläche enthält keine IFC-Logik. Sie ruft nur Funktionen aus core/ auf.

Zwei Eigenheiten von Streamlit bestimmen den Aufbau:
- Bei jedem Klick läuft dieses Skript von oben neu durch. Das Modell wird
  deshalb mit st.cache_resource nur einmal geladen.
- Die vier Schritte sind Reiter (st.tabs). Streamlit führt alle Reiter bei
  jedem Durchlauf aus, so bleiben Eingaben erhalten, wenn man zwischen den
  Schritten wechselt.

Im Schritt «Bearbeiten» steht neben der Tabelle der 3D-Viewer (viewer/).
Die bearbeitbare Tabelle meldet keine angeklickte Zeile zurück. Bauteile
werden deshalb über die Häkchen-Spalte «3D» in der Tabelle angewählt.

Bauteilklasse und Property-Set lassen sich in «Laden» und «Bearbeiten»
wählen. Beide Auswahlfelder sind gekoppelt (siehe pick).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

import viewer
from core import changelog, diff, geometry, ifc_reader, ifc_writer
from core.display import NO, YES, bool_columns, to_display
from core.schema import (COL_GLOBAL_ID, COL_MESSAGE, COL_NAME, COL_NEW, COL_OLD, COL_PROPERTY, COL_STOREY,
                         COL_VALID, LOCKED_COLUMNS)
from core.validator import load_rules, validate

TEST_MODEL = Path(__file__).resolve().parent / "data" / "testmodell.ifc"
COL_SHOW = "3D"   # Häkchen-Spalte: Bauteil im Viewer zeigen. Nur Oberfläche, wird nie geschrieben.
MAX_CARDS = 5     # so viele angewählte Bauteile werden unter dem Viewer mit Werten gezeigt

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


def _text(value) -> str:
    return "leer" if value is None or (isinstance(value, float) and value != value) else str(value)


def show_3d_panel(file_bytes: bytes, current: pd.DataFrame, selected: list[str], ifc_class: str) -> None:
    """Viewer und darunter die Werte der angewählten Bauteile."""
    try:
        meshes = get_meshes(file_bytes)
    except Exception as exc:
        st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
        return
    if not meshes:
        st.info("Das Modell enthält keine darstellbare Geometrie.")
        return

    with_geometry = {m["id"] for m in meshes}
    shown = [gid for gid in selected if gid in with_geometry] if focus_on_select else []
    if focus_on_select and len(shown) < len(selected):
        st.caption(f"{len(selected) - len(shown)} angewähltes Bauteil ohne Geometrie kann im 3D nicht gezeigt werden.")
    viewer.show(meshes, shown, transparency / 100)

    if not focus_on_select:
        st.caption("Anwählen ist ausgeschaltet (Seitenleiste). Der Viewer zeigt das ganze Modell.")
        return
    if not selected:
        st.caption(f"Häkchen in der Spalte «{COL_SHOW}» setzen, um Bauteile im Modell zu zeigen.")
        return
    props = [c for c in current.columns if c not in LOCKED_COLUMNS]
    rows = current[current[COL_GLOBAL_ID].isin(selected)]
    for _, row in rows.head(MAX_CARDS).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row[COL_NAME] or 'ohne Name'}** · {row[COL_STOREY] or 'ohne Geschoss'} · {ifc_class}  \n"
                        + " · ".join(f"{p}: **{_text(row[p])}**" for p in props))
    if len(rows) > MAX_CARDS:
        st.caption(f"… und {len(rows) - MAX_CARDS} weitere angewählte Bauteile.")


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


def reset_downstream() -> None:
    """Datei, Klasse oder Pset gewechselt: alte Bearbeitungen und Ergebnisse verwerfen."""
    for key in ("result_ifc", "result_log"):
        st.session_state.pop(key, None)


# Einstellungen für den 3D-Viewer, gelten für die ganze Sitzung
with st.sidebar:
    st.subheader("3D-Ansicht")
    show_3d = st.toggle("3D-Ansicht anzeigen", value=True)
    focus_on_select = st.toggle(
        "Bauteil beim Anwählen zeigen", value=True, disabled=not show_3d,
        help="Die Kamera fährt zum gewählten Bauteil, der Rest des Modells wird transparent.",
    )
    transparency = st.slider("Transparenz übriges Modell (%)", 0, 95, 85, step=5,
                             disabled=not (show_3d and focus_on_select))
    st.divider()

st.title("IFC-Property-Editor")
st.caption("Properties von IFC-Modellen im Browser ergänzen, prüfen und zurückschreiben")
tab_load, tab_edit, tab_check, tab_save = st.tabs(["1  Laden", "2  Bearbeiten", "3  Prüfen", "4  Speichern"])

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
    if classes:
        pick_class_and_pset("edit")   # dieselbe Auswahl wie in «Laden»
    if table is None:
        st.info("Zuerst im Schritt «Laden» eine Datei, eine Klasse und ein Property-Set wählen.")
    else:
        st.write(f"**{ifc_class} · {pset}** — Werte direkt in der Tabelle ändern. "
                 "GlobalId, Name und Geschoss sind gesperrt. Zelle leeren entfernt den Wert.")
        left, right = st.columns([1.15, 1], gap="medium") if show_3d else (st.container(), None)
        with left:
            # Häkchen-Spalte vorne, Ja/Nein-Properties als Auswahlfeld, alle anderen als freie Texteingabe
            config = {col: st.column_config.SelectboxColumn(col, options=[YES, NO]) for col in bool_columns(raw_table)}
            config[COL_SHOW] = st.column_config.CheckboxColumn(COL_SHOW, help="Bauteil im 3D-Viewer zeigen", width="small")
            with_show = table.copy()
            with_show.insert(0, COL_SHOW, False)
            edited_full = st.data_editor(
                with_show,
                disabled=LOCKED_COLUMNS,
                hide_index=True,
                column_config=config,
                num_rows="fixed",
                key=f"editor::{'::'.join(map(str, st.session_state['context']))}",
            )
            selected_ids = list(edited_full.loc[edited_full[COL_SHOW] == True, COL_GLOBAL_ID])  # noqa: E712
            edited = edited_full.drop(columns=[COL_SHOW])   # die Häkchen sind keine Änderung am Modell
        if right is not None:
            with right:
                show_3d_panel(ifc_bytes, edited, selected_ids, ifc_class)

# =============================== 3 Prüfen ====================================
validated = None
with tab_check:
    if edited is None:
        st.info("Zuerst im Schritt «Bearbeiten» Werte ändern.")
    else:
        changes = diff.find_changes(table, edited, pset)
        if changes.empty:
            st.info("Noch keine Änderungen.")
        else:
            validated = validate(changes, ifc_class, get_rules())
            # Ergebnis aus Schritt 4 verwerfen, sobald sich die Änderungen ändern
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
                if row[COL_VALID]:
                    st.success(text + (f"  ·  {row[COL_MESSAGE]}" if row[COL_MESSAGE] else ""))
                else:
                    st.error(f"{text}  ·  {row[COL_MESSAGE]}")
            if n_ok < len(validated):
                st.caption("Fehlerhafte Änderungen werden nicht gespeichert. Im Schritt «Bearbeiten» korrigieren.")

# =============================== 4 Speichern =================================
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
        st.write(f"Änderungen: {len(validated)} · gültig: {int(validated[COL_VALID].sum())}")
