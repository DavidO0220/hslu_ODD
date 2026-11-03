# Durchlauf mit dem Testmodell

So sieht ein vollständiger Durchlauf aus. Die Zahlen gelten für
`data/testmodell.ifc` und dienen als Kontrolle, ob alles richtig läuft.

## Das Testmodell

| Inhalt | Anzahl | Besonderheit |
|---|---|---|
| Geschosse | 3 | EG, 1. OG, 2. OG |
| Wände (IfcWall) | 15 | Pset_WallCommon; 2 ohne FireRating, 1 mit ungültigem «EI45» |
| Decken (IfcSlab) | 3 | Pset_SlabCommon |
| Türen (IfcDoor) | 3 | Pset_DoorCommon; 1 ohne FireRating; in der Innenwand |
| Fenster (IfcWindow) | 6 | Pset_WindowCommon; 1 ohne ThermalTransmittance (U-Wert); in der Südwand |
| Treppe (IfcStair) | 1 | Pset_StairCommon; vom EG ins 1. OG, durch eine Deckenöffnung |

Grundriss 10 × 8 m, vier Aussenwände (300 mm) und eine Innenwand (120 mm) pro
Geschoss. Türen und Fenster sitzen in Öffnungen, die aus den Wänden
ausgeschnitten sind (IfcOpeningElement, im Programm nicht als Klasse gelistet).

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

**3D-Ansicht** (rechts neben der Tabelle):

1. Beim ersten Öffnen erscheint kurz «3D-Geometrie wird berechnet …», dann
   das ganze Gebäude: drei Geschosse, Fenster in der Südfassade, Treppe im
   Westraum, eine Tür pro Geschoss in der Innenwand.
2. Mit der Maus drehen, verschieben, zoomen. «⟲ Ganzes Modell» setzt die Kamera zurück.
3. In der Tabelle bei «Innenwand 120 · 1. OG» das Häkchen in der Spalte «3D» setzen.
   Erwartet: Die Kamera fährt zur Wand, sie wird orange, der Rest wird
   transparent. Darunter: FireRating **leer**, IsExternal Nein, LoadBearing Nein.
4. Zusätzlich «Innenwand 120 · 2. OG» anhaken: Beide Wände sind orange, oben
   rechts steht «2 Bauteile angewählt».
5. Bei der Innenwand im 1. OG `EI60` eintragen: Die Karte unter dem Viewer zeigt sofort EI60.
6. Oben im Reiter «Bearbeiten» die Bauteilklasse auf `IfcWindow` stellen:
   Tabelle und Viewer wechseln auf die Fenster, im Reiter «Laden» steht
   ebenfalls `IfcWindow`. Danach wieder `IfcWall` wählen: Die Eingabe EI60
   ist noch da.
7. In der Seitenleiste «Bauteil beim Anwählen zeigen» ausschalten: Das Modell
   ist wieder ganz sichtbar, die Häkchen werden ignoriert.

**Dropdowns und Geschossfilter** (Modus «Bestehendes Pset bearbeiten»):

- Bei FireRating öffnet ein Klick in die Zelle eine Auswahl EI30, EI60, EI90.
  Der Fehlwert EI45 aus dem Modell steht zusätzlich in der Liste.
- Geschoss «EG»: Die Tabelle zeigt 5 Wände. Danach wieder «alle Geschosse».

**Neues Pset anlegen** (Modus oben umschalten):

1. Bauteilklasse `IfcWall`, Name `CH_Brandschutz`.
2. Properties: `Nachweis` · Text · `VKF 2015` und `Geprueft` · Ja/Nein · `Ja`.
3. Geschoss «EG»: In der Bauteilliste stehen 5 Wände.
4. «Property-Set bei 5 Bauteil(en) vormerken».
   Erwartet: «10 Werte vorgemerkt». In «Prüfen» stehen 10 gültige Änderungen
   mit `IfcWall · CH_Brandschutz`.
5. Gegenprobe: `Dicke` · Zahl · `dick` ergibt die Meldung «passt nicht zum Typ Zahl».

## 3 3D-Modell

1. Reiter «3 3D-Modell». Das Gebäude füllt den Reiter.
2. Ansicht «Oben», dann «Iso». Geschoss «1. OG»: nur dieses Geschoss ist sichtbar, wieder «alle».
3. Schnitt «waagrecht (Grundriss)», dann «auf Geschoss … → Grundriss EG»:
   Blick von oben auf das EG, Treppe, Tür und Fenster sind zu sehen.
   Regler bewegen: Die Schnitthöhe ändert sich. Danach «kein Schnitt».
4. Auf die Treppe klicken. Pop-up: Pset_StairCommon mit FireRating, IsExternal,
   RiserHeight, TreadLength. FireRating auf `R90` stellen, «Übernehmen».
   Erwartet: Die Treppe wird grün, im Pop-up steht «✓ R30 → R90».
5. Auf ein Fenster klicken, ThermalTransmittance `9` eintragen, «Übernehmen».
   Erwartet: Das Fenster wird rot, im Pop-up steht «✗ muss zwischen 0.3 und 3.0 liegen».
   Wert auf `1,1` ändern und übernehmen: Das Fenster wird grün.
6. Unter dem Viewer steht die Anzahl offener Änderungen.

## 4 Prüfen

Erwartet (nur mit den Eingaben aus Schritt 2): **2 Änderungen, 1 gültig, 1 Fehler.**
Mit den Eingaben aus dem 3D-Modell kommen sie dazu, jede Zeile zeigt Klasse und Pset.

- grün: Innenwand 120 · FireRating: leer → EI60
- rot: Aussenwand Nord 300 · FireRating: leer → EI45 · nicht in der Werteliste (EI30, EI60, EI90)

## 5 Speichern

1. Reiter «5 Speichern», Name für das Protokoll eingeben.
2. «IFC-Kopie erstellen».
3. `testmodell_bearbeitet.ifc` und `testmodell_protokoll.csv` herunterladen.

Kontrolle: Die Kopie im Schritt «Laden» hochladen. Erwartet sind jetzt
**1 leerer Wert** und zwei Wände mit EI60. Das Protokoll enthält genau eine
Zeile, die gültige Änderung. Optional die Kopie in einem BIM-Viewer öffnen.

## Weitere Prüfungen

- **Ja/Nein ändern:** IsExternal einer Aussenwand auf «Nein» setzen, speichern, Kopie neu laden: Der Wert ist «Nein».
- **Wert löschen:** Die Zelle mit «EI45» leeren: Das Property wird entfernt.
- **Fenster:** Klasse `IfcWindow`, Pset `Pset_WindowCommon`: 6 Bauteile, 1 leerer Wert. U-Wert `1,1` ist gültig, `5` liegt über dem Maximum 3.0 und wird abgelehnt.
- **Treppe:** Klasse `IfcStair` wählen und die Treppe anhaken: Die Kamera zeigt sie mit der Deckenöffnung darüber.
- **Defekte Datei:** Eine beliebige andere Datei mit Endung .ifc hochladen: Es erscheint eine Fehlermeldung, die App läuft weiter.
