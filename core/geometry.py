"""Geometrie: Dreiecksnetze der Bauteile für den 3D-Viewer.

IfcOpenShell berechnet aus der IFC-Geometrie (Extrusionen, Öffnungen usw.)
Dreiecke. Pro Bauteil entsteht ein Netz mit Eckpunkten in Metern und
Weltkoordinaten. Die GlobalId verbindet das Netz mit der Zeile in der Tabelle.

Der Viewer selbst (Oberfläche) liegt in viewer/, nicht hier.
"""

import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape as shape_util

from core.ifc_reader import storey_name

DECIMALS = 4  # 0.1 mm genügt für die Anzeige und hält die Datenmenge klein


def _settings():
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)  # Eckpunkte direkt in Weltkoordinaten
    return settings


def _elements(model):
    """Alle Bauteile mit Geometrie. Öffnungen werden nicht gezeigt, sie werden ausgeschnitten."""
    return [
        e for e in model.by_type("IfcElement")
        if not e.is_a("IfcFeatureElement") and getattr(e, "Representation", None) is not None
    ]


def _mesh(element, geometry) -> dict | None:
    verts = shape_util.get_vertices(geometry)
    faces = shape_util.get_faces(geometry)
    if len(verts) == 0 or len(faces) == 0:
        return None
    return {
        "id": element.GlobalId,
        "cls": element.is_a(),
        "name": element.Name or "",
        "storey": storey_name(element),
        "v": [round(float(x), DECIMALS) for x in verts.reshape(-1)],
        "f": [int(i) for i in faces.reshape(-1)],
    }


def _shapes(model, elements, settings):
    """Liefert (Bauteil, Geometrie). Zuerst schnell mit dem Iterator, sonst einzeln."""
    try:
        it = ifcopenshell.geom.iterator(settings, model, max(1, os.cpu_count() or 1), include=elements)
        result = [(model.by_id(shape.id), shape.geometry) for shape in it]
        if result:
            return result
    except Exception:
        pass
    # Rückfallebene: jedes Bauteil einzeln. Fehlerhafte Bauteile werden übersprungen.
    result = []
    for element in elements:
        try:
            result.append((element, ifcopenshell.geom.create_shape(settings, element).geometry))
        except Exception:
            continue
    return result


def load_meshes(model) -> list[dict]:
    """Netze aller Bauteile: [{'id', 'cls', 'name', 'storey', 'v', 'f'}, ...].

    'v' sind die Eckpunkte als flache Liste x, y, z, x, y, z, ... in Metern,
    'f' die Dreiecke als flache Liste von Eckpunkt-Indizes.
    Bauteile ohne berechenbare Geometrie fehlen in der Liste.
    """
    elements = _elements(model)
    if not elements:
        return []
    meshes = []
    for element, geometry in _shapes(model, elements, _settings()):
        mesh = _mesh(element, geometry)
        if mesh is not None:
            meshes.append(mesh)
    return meshes


def bounds(mesh: dict) -> tuple[list[float], list[float]]:
    """Kleinster und grösster Eckpunkt eines Netzes: ([xmin, ymin, zmin], [xmax, ymax, zmax])."""
    v = mesh["v"]
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]
