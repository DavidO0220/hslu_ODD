"""Erzeugt ein kleines IFC4-Testmodell für den IFC-Property-Editor.

Das Modell ist bewusst klein und kontrolliert, damit die Tests genau wissen,
was herauskommen muss:

- 3 Geschosse: EG, 1. OG, 2. OG
- 15 Wände (IfcWall) mit Pset_WallCommon, davon
    - 2 Wände ohne FireRating (leer)
    - 1 Wand mit dem ungültigen Wert "EI45"
- 3 Decken (IfcSlab) mit Pset_SlabCommon
- 3 Türen (IfcDoor) mit Pset_DoorCommon, davon 1 ohne FireRating
- 6 Fenster (IfcWindow) mit Pset_WindowCommon, davon 1 ohne ThermalTransmittance
- 1 Treppe (IfcStair) vom EG ins 1. OG mit Pset_StairCommon

Alle Bauteile haben eine einfache Geometrie aus Quadern, damit der 3D-Viewer
etwas anzeigen kann. Türen und Fenster sitzen in Öffnungen (IfcOpeningElement),
die aus den Wänden ausgeschnitten werden. Die Treppe führt durch eine Öffnung
in der Decke über dem EG.

Das Skript verwendet nur die Grundfunktionen von IfcOpenShell
(ifcopenshell.file, create_entity, guid.new). Diese sind über alle Versionen
stabil, im Gegensatz zu einigen Funktionen in ifcopenshell.api.

Aufruf aus dem Projektordner:
    python tools/make_test_model.py
"""

from pathlib import Path

import ifcopenshell
import ifcopenshell.guid

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "testmodell.ifc"

STOREYS = [("EG", 0.0), ("1. OG", 3.0), ("2. OG", 6.0)]
SLAB_THICKNESS = 0.25
WALL_HEIGHT = 2.75

# Grundriss 10 m x 8 m: (Name, Startpunkt, Richtung, Länge, Dicke, aussen?)
WALL_LAYOUT = [
    ("Aussenwand Süd 300", (0.0, 0.0), (1.0, 0.0), 10.0, 0.30, True),
    ("Aussenwand Ost 300", (10.0, 0.0), (0.0, 1.0), 8.0, 0.30, True),
    ("Aussenwand Nord 300", (10.0, 8.0), (-1.0, 0.0), 10.0, 0.30, True),
    ("Aussenwand West 300", (0.0, 8.0), (0.0, -1.0), 8.0, 0.30, True),
    ("Innenwand 120", (5.0, 0.0), (0.0, 1.0), 8.0, 0.12, False),
]

# FireRating pro (Geschoss-Index, Wandname). None = Property fehlt (leer).
FIRE_RATING_EXCEPTIONS = {
    (0, "Innenwand 120"): "EI60",
    (1, "Innenwand 120"): None,
    (2, "Innenwand 120"): "EI45",        # absichtlich ungültig
    (2, "Aussenwand Nord 300"): None,
}
DEFAULT_OUTER_FIRE_RATING = "EI90"

SLAB_NAMES = ["Bodenplatte", "Decke über EG", "Decke über 1. OG"]

# Tür in der Innenwand (x = 5 m), 0.9 m breit, ab y = 2 m
DOOR_FIRE_RATINGS = ["EI30", None, "EI30"]
DOOR_START_Y, DOOR_WIDTH, DOOR_HEIGHT = 2.0, 0.9, 2.1

# Fenster in der Südwand (y = 0): (Name, Start x). Brüstung 0.9 m, 1.2 x 1.4 m
WINDOWS = [("Fenster Süd 1", 2.0), ("Fenster Süd 2", 6.5)]
WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_SILL = 1.2, 1.4, 0.9
WINDOW_U_VALUE = 0.9                                  # W/m2K
WINDOW_U_MISSING = {(2, "Fenster Süd 2")}             # ohne U-Wert (leer)

# Gerade Treppe im Westraum vom EG ins 1. OG: 17 Steigungen, 16 Auftritte
STAIR_X, STAIR_Y, STAIR_WIDTH = 0.5, 1.5, 1.1
STAIR_RISERS, STAIR_TREAD = 17, 0.27


class ModelBuilder:
    """Kleine Hilfsklasse, damit der Aufbau unten lesbar bleibt."""

    def __init__(self) -> None:
        self.f = ifcopenshell.file(schema="IFC4")

    def root(self, ifc_class: str, **attrs):
        """Erzeugt ein Wurzelobjekt (Bauteil, Beziehung, Pset) mit neuer GlobalId."""
        return self.f.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    # --- Geometrie-Hilfen -------------------------------------------------
    def point3(self, x, y, z):
        return self.f.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y), float(z)))

    def point2(self, x, y):
        return self.f.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y)))

    def direction(self, *xyz):
        return self.f.create_entity("IfcDirection", DirectionRatios=tuple(float(v) for v in xyz))

    def axis3(self, x=0.0, y=0.0, z=0.0, dx=1.0, dy=0.0):
        return self.f.create_entity(
            "IfcAxis2Placement3D",
            Location=self.point3(x, y, z),
            Axis=self.direction(0, 0, 1),
            RefDirection=self.direction(dx, dy, 0),
        )

    def placement(self, relative_to, x=0.0, y=0.0, z=0.0, dx=1.0, dy=0.0):
        return self.f.create_entity(
            "IfcLocalPlacement", PlacementRelTo=relative_to, RelativePlacement=self.axis3(x, y, z, dx, dy)
        )

    def solid(self, x_dim, y_dim, depth, center_x, center_y):
        """Quader als extrudiertes Rechteck (Grundfläche bei z = 0)."""
        profile = self.f.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            Position=self.f.create_entity("IfcAxis2Placement2D", Location=self.point2(center_x, center_y)),
            XDim=float(x_dim),
            YDim=float(y_dim),
        )
        solid = self.f.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile,
            Position=self.axis3(),
            ExtrudedDirection=self.direction(0, 0, 1),
            Depth=float(depth),
        )
        return solid

    def shape(self, context, solids):
        """Körperdarstellung aus einem oder mehreren Quadern."""
        rep = self.f.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=list(solids),
        )
        return self.f.create_entity("IfcProductDefinitionShape", Representations=[rep])

    def box(self, context, x_dim, y_dim, depth, center_x, center_y):
        """Ein einzelner Quader als Körperdarstellung."""
        return self.shape(context, [self.solid(x_dim, y_dim, depth, center_x, center_y)])

    def opening(self, host, placement, representation, name):
        """Öffnung, die aus dem Bauteil host ausgeschnitten wird."""
        opening = self.root("IfcOpeningElement", Name=name, ObjectPlacement=placement,
                            Representation=representation, PredefinedType="OPENING")
        self.root("IfcRelVoidsElement", RelatingBuildingElement=host, RelatedOpeningElement=opening)
        return opening

    def fill(self, opening, element):
        """Tür oder Fenster sitzt in der Öffnung."""
        self.root("IfcRelFillsElement", RelatingOpeningElement=opening, RelatedBuildingElement=element)

    # --- Beziehungen und Properties ---------------------------------------
    def aggregate(self, parent, children):
        self.root("IfcRelAggregates", RelatingObject=parent, RelatedObjects=list(children))

    def contain(self, storey, elements):
        self.root("IfcRelContainedInSpatialStructure", RelatingStructure=storey, RelatedElements=list(elements))

    def pset(self, element, name, values: dict):
        """Hängt ein Property-Set an. Werte mit None werden weggelassen (= leer)."""
        props = []
        for prop_name, value in values.items():
            if value is None:
                continue
            if isinstance(value, tuple):          # (IFC-Typ, Wert), z. B. ("IfcPositiveLengthMeasure", 0.27)
                nominal = self.f.create_entity(value[0], value[1])
            elif isinstance(value, bool):
                nominal = self.f.create_entity("IfcBoolean", value)
            elif isinstance(value, float):
                nominal = self.f.create_entity("IfcReal", value)
            else:
                nominal = self.f.create_entity("IfcLabel", str(value))
            props.append(self.f.create_entity("IfcPropertySingleValue", Name=prop_name, NominalValue=nominal))
        pset = self.root("IfcPropertySet", Name=name, HasProperties=props)
        self.root("IfcRelDefinesByProperties", RelatedObjects=[element], RelatingPropertyDefinition=pset)


def build(path: Path = DEFAULT_PATH) -> Path:
    b = ModelBuilder()
    f = b.f

    # Einheiten: Meter, Quadratmeter, Kubikmeter
    units = f.create_entity(
        "IfcUnitAssignment",
        Units=[
            f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
            f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
        ],
    )

    # Darstellungskontext
    model_ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=b.axis3(),
    )
    body_ctx = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=model_ctx,
        TargetView="MODEL_VIEW",
    )

    # Räumliche Struktur
    project = b.root("IfcProject", Name="Testprojekt IFC-Property-Editor", UnitsInContext=units, RepresentationContexts=[model_ctx])
    site_pl = b.placement(None)
    site = b.root("IfcSite", Name="Grundstück", ObjectPlacement=site_pl, CompositionType="ELEMENT")
    building_pl = b.placement(site_pl)
    building = b.root("IfcBuilding", Name="Testgebäude", ObjectPlacement=building_pl, CompositionType="ELEMENT")
    b.aggregate(project, [site])
    b.aggregate(site, [building])

    storeys = []
    for name, elevation in STOREYS:
        pl = b.placement(building_pl, z=elevation)
        storeys.append((b.root("IfcBuildingStorey", Name=name, ObjectPlacement=pl, Elevation=elevation, CompositionType="ELEMENT"), pl))
    b.aggregate(building, [s for s, _ in storeys])

    for i, (storey, storey_pl) in enumerate(storeys):
        contained = []

        # Decke bzw. Bodenplatte
        slab = b.root(
            "IfcSlab",
            Name=SLAB_NAMES[i],
            ObjectPlacement=b.placement(storey_pl),
            Representation=b.box(body_ctx, 10.0, 8.0, SLAB_THICKNESS, 5.0, 4.0),
            PredefinedType="FLOOR" if i else "BASESLAB",
        )
        b.pset(slab, "Pset_SlabCommon", {"LoadBearing": True, "IsExternal": i == 0, "FireRating": "REI60"})
        contained.append(slab)

        # Wände
        walls = {}
        for name, (x, y), (dx, dy), length, thickness, outer in WALL_LAYOUT:
            wall = b.root(
                "IfcWall",
                Name=name,
                ObjectPlacement=b.placement(storey_pl, x, y, SLAB_THICKNESS, dx, dy),
                Representation=b.box(body_ctx, length, thickness, WALL_HEIGHT, length / 2, 0.0),
                PredefinedType="STANDARD",
            )
            fire = FIRE_RATING_EXCEPTIONS.get((i, name), DEFAULT_OUTER_FIRE_RATING if outer else "EI30")
            b.pset(wall, "Pset_WallCommon", {"IsExternal": outer, "LoadBearing": outer, "FireRating": fire})
            contained.append(wall)
            walls[name] = wall

        # Tür in der Innenwand, mit Öffnung
        door_pl = b.placement(storey_pl, 5.0, DOOR_START_Y, SLAB_THICKNESS, 0.0, 1.0)
        door = b.root(
            "IfcDoor",
            Name="Tür Treppenhaus",
            ObjectPlacement=door_pl,
            Representation=b.box(body_ctx, DOOR_WIDTH, 0.05, DOOR_HEIGHT, DOOR_WIDTH / 2, 0.0),
            OverallHeight=DOOR_HEIGHT,
            OverallWidth=DOOR_WIDTH,
            PredefinedType="DOOR",
        )
        door_opening = b.opening(
            walls["Innenwand 120"],
            b.placement(storey_pl, 5.0, DOOR_START_Y, SLAB_THICKNESS, 0.0, 1.0),
            b.box(body_ctx, DOOR_WIDTH, 0.4, DOOR_HEIGHT, DOOR_WIDTH / 2, 0.0),
            "Öffnung Tür",
        )
        b.fill(door_opening, door)
        b.pset(door, "Pset_DoorCommon", {"IsExternal": False, "FireRating": DOOR_FIRE_RATINGS[i]})
        contained.append(door)

        # Fenster in der Südwand, mit Öffnungen
        for win_name, start_x in WINDOWS:
            z = SLAB_THICKNESS + WINDOW_SILL
            window = b.root(
                "IfcWindow",
                Name=win_name,
                ObjectPlacement=b.placement(storey_pl, start_x, 0.0, z),
                Representation=b.box(body_ctx, WINDOW_WIDTH, 0.08, WINDOW_HEIGHT, WINDOW_WIDTH / 2, 0.0),
                OverallHeight=WINDOW_HEIGHT,
                OverallWidth=WINDOW_WIDTH,
                PredefinedType="WINDOW",
            )
            win_opening = b.opening(
                walls["Aussenwand Süd 300"],
                b.placement(storey_pl, start_x, 0.0, z),
                b.box(body_ctx, WINDOW_WIDTH, 0.5, WINDOW_HEIGHT, WINDOW_WIDTH / 2, 0.0),
                "Öffnung Fenster",
            )
            b.fill(win_opening, window)
            u_value = None if (i, win_name) in WINDOW_U_MISSING else ("IfcThermalTransmittanceMeasure", WINDOW_U_VALUE)
            b.pset(window, "Pset_WindowCommon", {"IsExternal": True, "ThermalTransmittance": u_value})
            contained.append(window)

        # Treppe vom EG ins 1. OG und Öffnung in der Decke darüber
        if i == 0:
            riser = round(STOREYS[1][1] / STAIR_RISERS, 4)
            steps = [
                b.solid(STAIR_WIDTH, STAIR_TREAD, (k + 1) * riser, STAIR_WIDTH / 2, (k + 0.5) * STAIR_TREAD)
                for k in range(STAIR_RISERS - 1)
            ]
            stair = b.root(
                "IfcStair",
                Name="Treppe EG bis 1. OG",
                ObjectPlacement=b.placement(storey_pl, STAIR_X, STAIR_Y, SLAB_THICKNESS),
                Representation=b.shape(body_ctx, steps),
                PredefinedType="STRAIGHT_RUN_STAIR",
            )
            b.pset(stair, "Pset_StairCommon", {
                "IsExternal": False,
                "FireRating": "R30",
                "RiserHeight": ("IfcPositiveLengthMeasure", riser),
                "TreadLength": ("IfcPositiveLengthMeasure", STAIR_TREAD),
            })
            contained.append(stair)
        if i == 1:
            run = (STAIR_RISERS - 1) * STAIR_TREAD
            hole_start = STAIR_Y + 3 * STAIR_TREAD - 0.2
            hole_len = STAIR_Y + run - hole_start
            b.opening(
                slab,
                b.placement(storey_pl, STAIR_X - 0.1, hole_start, -0.05),
                b.box(body_ctx, STAIR_WIDTH + 0.2, hole_len, SLAB_THICKNESS + 0.1, (STAIR_WIDTH + 0.2) / 2, hole_len / 2),
                "Öffnung Treppe",
            )

        b.contain(storey, contained)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(path))
    return path


if __name__ == "__main__":
    out = build()
    model = ifcopenshell.open(str(out))
    print(f"Testmodell geschrieben: {out}")
    for cls in ("IfcBuildingStorey", "IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcStair", "IfcOpeningElement"):
        print(f"  {cls}: {len(model.by_type(cls))}")
