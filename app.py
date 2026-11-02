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
Die bearbeitbare Tabelle meldet keine angeklickte Zeile zurück, deshalb wird
das Bauteil über ein Auswahlfeld angewählt.
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


def show_3d_panel(file_bytes: bytes, current: pd.DataFrame, ifc_class: str) -> str | None:
    """Viewer mit Auswahlfeld. Gibt die GlobalId des gewählten Bauteils zurück."""
    try:
        meshes = get_meshes(file_bytes)
    except Exception as exc:
        st.warning(f"Die 3D-Geometrie konnte nicht berechnet werden: {exc}")
        return None
    if not meshes:
        st.info("Das Modell enthält keine darstellbare Geometrie.")
        return None

    selected = None
    if focus_on_select:
        labels = {row[COL_GLOBAL_ID]: f"{row[COL_NAME] or 'ohne Name'} · {row[COL_STOREY] or 'ohne Geschoss'}"
                  for _, row in current.iterrows()}
        selected = st.selectbox(
            f"Bauteil anwählen ({ifc_class})",
            [None, *labels],
            format_func=lambda gid: "— keines, ganzes Modell zeigen —" if gid is None else labels[gid],
            key="select::" + "::".join(map(str, st.session_state["context"])),
        )

    with_geometry = {m["id"] for m in meshes}
    if selected is not None and selected not in with_geometry:
        st.caption("Dieses Bauteil hat keine Geometrie und kann im 3D nicht gezeigt werden.")
    viewer.show(meshes, selected if selected in with_geometry else None, transparency / 100)

    if selected is not None:
        row = current.loc[current[COL_GLOBAL_ID] == selected].iloc[0]
        props = [c for c in current.columns if c not in LOCKED_COLUMNS]
        with st.container(border=True):
            st.markdown(f"**{row[COL_NAME] or 'ohne Name'}** · {row[COL_STOREY] or 'ohne Geschoss'} · {ifc_class}")
            st.markdown("  \n".join(f"{p}: **{_text(row[p])}**" for p in props))
    return selected


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

    if model is not None:
        classes = ifc_reader.list_classes(model)
        if not classes:
            st.warning("Im Modell wurden keine Bauteile gefunden.")
        else:
            col1, col2 = st.columns(2)
            ifc_class = col1.selectbox("Bauteilklasse", classes)
            psets = ifc_reader.list_psets(model, ifc_class)
            if not psets:
                st.warning(f"Die Bauteile der Klasse {ifc_class} haben keine Property-Sets.")
            else:
                pset = col2.selectbox("Property-Set", psets)
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
selected_id = None
with tab_edit:
    if table is None:
        st.info("Zuerst im Schritt «Laden» eine Datei, eine Klasse und ein Property-Set wählen.")
    else:
        st.write(f"**{ifc_class} · {pset}** — Werte direkt in der Tabelle ändern. "
                 "GlobalId, Name und Geschoss sind gesperrt. Zelle leeren entfernt den Wert.")
        left, right = st.columns([1.15, 1], gap="medium") if show_3d else (st.container(), None)
        with left:
            # Ja/Nein-Properties als Auswahlfeld, alle anderen als freie Texteingabe
            config = {col: st.column_config.SelectboxColumn(col, options=[YES, NO]) for col in bool_columns(raw_table)}
            edited = st.data_editor(
                table,
                disabled=LOCKED_COLUMNS,
                hide_index=True,
                column_config=config,
                num_rows="fixed",
                key=f"editor::{'::'.join(map(str, st.session_state['context']))}",
            )
        if right is not None:
            with right:
                selected_id = show_3d_panel(ifc_bytes, edited, ifc_class)

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
    if selected_id is not None and edited is not None:
        sel = edited.loc[edited[COL_GLOBAL_ID] == selected_id].iloc[0]
        st.write(f"Angewählt: {sel[COL_NAME] or 'ohne Name'} ({sel[COL_STOREY] or '—'})")
    if validated is not None:
        st.write(f"Änderungen: {len(validated)} · gültig: {int(validated[COL_VALID].sum())}")
