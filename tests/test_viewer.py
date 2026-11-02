"""Tests für die Viewer-Seite: Daten und Bibliotheken müssen korrekt eingebettet sein."""

import json
import re

import viewer

MESH = {"id": "0123456789abcdefABCDEF", "cls": "IfcWall", "name": "Wand </script> <b>", "storey": "EG",
        "v": [0, 0, 0, 1, 0, 0, 0, 1, 0], "f": [0, 1, 2]}


def _data(html):
    raw = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1)
    return json.loads(raw)


def test_placeholders_replaced():
    html = viewer.build_html([MESH])
    # three.js enthält selbst den Text window.__THREE__, deshalb die Platzhalter mit ihrer Umgebung prüfen
    assert 'application/json">__DATA__' not in html
    assert "__THREE_SRC__ = __THREE__;" not in html and "__ORBIT_SRC__ = __ORBIT__;" not in html
    assert "class OrbitControls" in html and 'const t=\\"169\\"' in html


def test_data_roundtrip_and_selection():
    data = _data(viewer.build_html([MESH], selected=[MESH["id"]], transparency=0.7))
    assert data["selected"] == [MESH["id"]] and data["transparency"] == 0.7
    assert _data(viewer.build_html([MESH]))["selected"] == []
    assert data["meshes"][0]["name"] == "Wand </script> <b>"   # Sonderzeichen kommen unverändert an


def test_no_script_break_from_content():
    html = viewer.build_html([MESH])
    # Genau so viele </script> wie die Vorlage selbst enthält: Inhalte dürfen keinen Block beenden
    assert html.count("</script>") == 3


def test_component_files_present():
    """Die 3D-Komponente lädt three.js zur Laufzeit aus ihrem eigenen Ordner."""
    folder = viewer.HERE / "component"
    page = (folder / "index.html").read_text(encoding="utf-8")
    assert "streamlit:componentReady" in page and "streamlit:setComponentValue" in page
    for name in ("three.module.min.js", "OrbitControls.js"):
        assert (folder / "vendor" / name).is_file()
        assert f"vendor/{name}" in page
