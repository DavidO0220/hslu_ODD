# Durchlauf mit dem Testmodell

So sieht ein vollständiger Durchlauf aus. Die Zahlen gelten für
`data/testmodell.ifc` und dienen als Kontrolle, ob alles richtig läuft.

## Das Testmodell

| Inhalt | Anzahl | Besonderheit |
|---|---|---|
| Geschosse | 3 | EG, 1. OG, 2. OG |
| Wände (IfcWall) | 15 | Pset_WallCommon; 2 ohne FireRating, 1 mit ungültigem «EI45» |
| Decken (IfcSlab) | 3 | Pset_SlabCommon |
| Türen (IfcDoor) | 3 | Pset_DoorCommon; 1 ohne FireRating |

Grundriss 10 × 8 m, vier Aussenwände (300 mm) und eine Innenwand (120 mm) pro Geschoss.

## 1 Laden

1. `streamlit run app.py`
2. Häkchen «Testmodell aus data/ verwenden» setzen.
3. Bauteilklasse `IfcWall`, Property-Set `Pset_WallCommon` wählen.

Erwartet: **15 Bauteile, 3 Properties, 2 leere Werte.** Die Tabelle zeigt die
Spalten GlobalId, Name, Geschoss, FireRating, IsExternal, LoadBearing.
IsExternal und LoadBearing erscheinen als «Ja»/«Nein».

## 2 Bearbeiten

1. Reiter «2 Bearbeiten».
2. Bei der «Innenwand 120» im 1. OG unter FireRating `EI60` eintragen.
3. Bei der «Aussenwand Nord 300» im 2. OG `EI45` eintragen.

GlobalId, Name und Geschoss lassen sich nicht ändern.

## 3 Prüfen

Erwartet: **2 Änderungen, 1 gültig, 1 Fehler.**

- grün: Innenwand 120 · FireRating: leer → EI60
- rot: Aussenwand Nord 300 · FireRating: leer → EI45 · nicht in der Werteliste (EI30, EI60, EI90)

## 4 Speichern

1. Reiter «4 Speichern», Name für das Protokoll eingeben.
2. «IFC-Kopie erstellen».
3. `testmodell_bearbeitet.ifc` und `testmodell_protokoll.csv` herunterladen.

Kontrolle: Die Kopie im Schritt «Laden» hochladen. Erwartet sind jetzt
**1 leerer Wert** und zwei Wände mit EI60. Das Protokoll enthält genau eine
Zeile, die gültige Änderung. Optional die Kopie in einem BIM-Viewer öffnen.

## Weitere Prüfungen

- **Ja/Nein ändern:** IsExternal einer Aussenwand auf «Nein» setzen, speichern, Kopie neu laden: Der Wert ist «Nein».
- **Wert löschen:** Die Zelle mit «EI45» leeren: Das Property wird entfernt.
- **Defekte Datei:** Eine beliebige andere Datei mit Endung .ifc hochladen: Es erscheint eine Fehlermeldung, die App läuft weiter.
