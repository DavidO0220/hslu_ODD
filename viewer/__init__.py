"""3D-Viewer für die Oberfläche.

Beide Viewer sind dieselbe Streamlit-Komponente (component/index.html) mit
Rückkanal, in zwei Modi:

select3d(): kleiner Viewer neben der Tabelle in «Bearbeiten». Klick wählt ein
            Bauteil aus, Ctrl+Klick fügt hinzu oder entfernt. Die Auswahl kommt
            als Rückgabewert in Python an und setzt die Häkchen in der Tabelle.
model3d():  grosser Viewer im Reiter «3D-Modell» mit Navigation, Schnitt und
            Pop-up zum Bearbeiten. Eingaben im Pop-up kommen als Rückgabewert an.

three.js liegt in viewer/component/vendor, die Anzeige braucht kein Internet.
Rückgabewerte bleiben bestehen, bis eine neue Eingabe kommt. Die «nonce» im
Wert zeigt, ob er neu ist.
"""

from pathlib import Path

import streamlit.components.v1 as components

HERE = Path(__file__).resolve().parent
_component = components.declare_component("ifc_model3d", path=str(HERE / "component"))


def select3d(meshes: list[dict], selected: list[str], model_id: str, focus: bool = True,
             transparency: float = 0.85, height: int = 560, key: str = "viewer_select"):
    """Kleiner Viewer zum Auswählen.

    selected:     GlobalIds der ausgewählten Bauteile (orange)
    focus:        bei neuer Auswahl hinzoomen und den Rest transparent machen
    transparency: 0 bis 1, wie durchsichtig der Rest bei einer Auswahl wird

    Rückgabe: None oder {"nonce", "action": "select", "ids": [...], "clicked": GlobalId oder None}.
    """
    return _component(mode="select", meshes=meshes, selected=list(selected), model_id=model_id,
                      focus=focus, transparency=float(transparency), height=height, key=key, default=None)


def model3d(meshes: list[dict], properties: dict, rules: dict, pending: list[dict], model_id: str,
            height: int = 720, key: str = "model3d"):
    """Grosser 3D-Viewer mit Navigation, Schnitt und Pop-up zum Bearbeiten.

    meshes:     Netze aus core.geometry.load_meshes
    properties: alle Eigenschaften pro GlobalId (core.ifc_reader.element_properties)
    rules:      Regeln aus config/rules.json, für Auswahlfelder im Pop-up
    pending:    offene Änderungen mit Prüfergebnis, je {guid, pset, prop, old, new, valid, msg}
    model_id:   wechselt nur mit der Datei, dann baut der Viewer die Szene neu auf

    Rückgabe: None oder {"nonce", "guid", "changes": [{"pset", "prop", "value"}, ...]}.
    """
    return _component(mode="edit", meshes=meshes, props=properties, rules=rules, pending=pending,
                      model_id=model_id, height=height, key=key, default=None)
