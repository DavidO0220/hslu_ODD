"""3D-Viewer für die Oberfläche.

Die Seite viewer.html zeichnet die Netze aus core/geometry.py mit three.js.
three.js liegt in viewer/vendor und wird in die Seite eingebettet, die
Anzeige funktioniert deshalb auch ohne Internetverbindung.

Der Viewer zeigt nur an. Welches Bauteil gewählt ist, entscheidet app.py.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
_PLACEHOLDER = re.compile(r"__(DATA|THREE|ORBIT)__")


@lru_cache(maxsize=1)
def _assets() -> tuple[str, str, str]:
    read = lambda p: p.read_text(encoding="utf-8")  # noqa: E731
    return (
        read(HERE / "viewer.html"),
        read(HERE / "vendor" / "three.module.min.js"),
        read(HERE / "vendor" / "OrbitControls.js"),
    )


def _embed(value) -> str:
    """JSON zum Einbetten in ein <script>.

    Jedes '<' wird als \\u003c geschrieben. So kann kein Text wie </script>
    im Inhalt den Script-Block vorzeitig beenden.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_html(meshes: list[dict], selected: str | None = None, transparency: float = 0.85) -> str:
    """Vollständige HTML-Seite des Viewers.

    meshes:       Netze aus core.geometry.load_meshes
    selected:     GlobalId des hervorgehobenen Bauteils oder None
    transparency: 0 bis 1, wie durchsichtig das übrige Modell bei einer Auswahl wird
    """
    template, three, orbit = _assets()
    data = {"meshes": meshes, "selected": selected, "transparency": float(transparency)}
    parts = {"DATA": _embed(data), "THREE": _embed(three), "ORBIT": _embed(orbit)}
    # Ein Durchgang: eingesetzter Text wird nicht nochmals nach Platzhaltern durchsucht
    return _PLACEHOLDER.sub(lambda m: parts[m.group(1)], template)


def show(meshes: list[dict], selected: str | None = None, transparency: float = 0.85, height: int = 560) -> None:
    """Zeigt den Viewer in der Streamlit-Seite."""
    html = build_html(meshes, selected, transparency)
    if hasattr(st, "iframe"):            # neuere Streamlit-Versionen
        st.iframe(html, height=height)
    else:                                # ältere Versionen
        import streamlit.components.v1 as components
        components.html(html, height=height)
