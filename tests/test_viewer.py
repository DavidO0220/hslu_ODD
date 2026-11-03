"""Tests für die 3D-Komponente: Dateien vorhanden, Protokoll und Modi in der Seite."""

import viewer

FOLDER = viewer.HERE / "component"
PAGE = (FOLDER / "index.html").read_text(encoding="utf-8")


def test_component_files_present():
    """Die Komponente lädt three.js zur Laufzeit aus ihrem eigenen Ordner."""
    for name in ("three.module.min.js", "OrbitControls.js", "LICENSE-three.txt"):
        assert (FOLDER / "vendor" / name).is_file()
    assert "vendor/three.module.min.js" in PAGE and "vendor/OrbitControls.js" in PAGE


def test_streamlit_protocol():
    for message in ("streamlit:componentReady", "streamlit:render", "streamlit:setComponentValue",
                    "streamlit:setFrameHeight", "isStreamlitMessage"):
        assert message in PAGE


def test_both_modes():
    assert 'args.mode === "select"' in PAGE and 'action: "select"' in PAGE
    assert "only-select" in PAGE and "only-edit" in PAGE
