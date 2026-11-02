"""3D-Viewer für die Oberfläche, in zwei Formen.

show():    kleiner Viewer im Reiter «Bearbeiten». Nur Anzeige, die Seite
           viewer.html wird mit allen Daten als HTML eingebettet.
model3d(): grosser Viewer im Reiter «3D-Modell» (component/index.html).
           Eine Streamlit-Komponente mit Rückkanal: Eingaben im Pop-up kommen
           als Rückgabewert in Python an.

three.js liegt in viewer/component/vendor. Beide Viewer laden es von dort,
die Anzeige funktioniert deshalb ohne Internetverbindung.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HERE = Path(__file__).resolve().parent
_model3d = components.declare_component("ifc_model3d", path=str(HERE / "component"))
_PLACEHOLDER = re.compile(r"__(DATA|THREE|ORBIT)__")


@lru_cache(maxsize=1)
def _assets() -> tuple[str, str, str]:
    read = lambda p: p.read_text(encoding="utf-8")  # noqa: E731
    return (
        read(HERE / "viewer.html"),
        read(HERE / "component" / "vendor" / "three.module.min.js"),
        read(HERE / "component" / "vendor" / "OrbitControls.js"),
    )


def _embed(value) -> str:
    """JSON zum Einbetten in ein <script>.

    Jedes '<' wird als \\u003c geschrieben. So kann kein Text wie </script>
    im Inhalt den Script-Block vorzeitig beenden.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_html(meshes: list[dict], selected: list[str] | None = None, transparency: float = 0.85) -> str:
    """Vollständige HTML-Seite des Viewers.

    meshes:       Netze aus core.geometry.load_meshes
    selected:     GlobalIds der hervorgehobenen Bauteile (leer: ganzes Modell normal zeigen)
    transparency: 0 bis 1, wie durchsichtig das übrige Modell bei einer Auswahl wird
    """
    template, three, orbit = _assets()
    data = {"meshes": meshes, "selected": list(selected or []), "transparency": float(transparency)}
    parts = {"DATA": _embed(data), "THREE": _embed(three), "ORBIT": _embed(orbit)}
    # Ein Durchgang: eingesetzter Text wird nicht nochmals nach Platzhaltern durchsucht
    return _PLACEHOLDER.sub(lambda m: parts[m.group(1)], template)


def show(meshes: list[dict], selected: list[str] | None = None, transparency: float = 0.85, height: int = 560) -> None:
    """Zeigt den Viewer in der Streamlit-Seite."""
    html = build_html(meshes, selected, transparency)
    if hasattr(st, "iframe"):            # neuere Streamlit-Versionen
        st.iframe(html, height=height)
    else:                                # ältere Versionen
        import streamlit.components.v1 as components
        components.html(html, height=height)


def model3d(meshes: list[dict], properties: dict, rules: dict, pending: list[dict], model_id: str,
            height: int = 720, key: str = "model3d"):
    """Grosser 3D-Viewer mit Navigation, Schnitt und Pop-up zum Bearbeiten.

    meshes:     Netze aus core.geometry.load_meshes
    properties: alle Eigenschaften pro GlobalId (core.ifc_reader.element_properties)
    rules:      Regeln aus config/rules.json, für Auswahlfelder im Pop-up
    pending:    offene Änderungen mit Prüfergebnis, je {guid, pset, prop, old, new, valid, msg}
    model_id:   wechselt nur mit der Datei, dann baut der Viewer die Szene neu auf

    Rückgabe: None oder die letzte Eingabe aus dem Pop-up
    {"nonce": ..., "guid": ..., "changes": [{"pset", "prop", "value"}, ...]}.
    Der Wert bleibt bestehen, bis eine neue Eingabe kommt. Die nonce zeigt, ob er neu ist.
    """
    return _model3d(meshes=meshes, props=properties, rules=rules, pending=pending,
                    model_id=model_id, height=height, key=key, default=None)
