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

## Kopfzeile

Oben steht der Titel, daneben der Status und rechts «⚙ Ansicht». Es gibt keine
Seitenleiste mehr. Der Status zeigt die Datei und je nach Stand «keine
Änderungen», «✓ n gültig», «✗ n Fehler» und «n angewählt».

## 1 Laden

1. `streamlit run app.py`
2. Häkchen «Testmodell aus data/ verwenden» setzen.

Erwartet rechts unter «IM MODELL · testmodell.ifc · IFC4»: **28 Bauteile,
3 Geschosse, 96 % erfüllen alle Regeln.** Die Tabelle hat fünf Zeilen in der
Reihenfolge Wände, Decken, Türen, Fenster, Treppen. Bei den Wänden steht
«offene Werte 1» und der Balken bei 93 % (14 von 15), alle anderen bei 100 %.
Im Status oben steht «keine Änderungen».

3. «Zur Arbeitsfläche →» wechselt in den Bereich 2.

## 2 Arbeitsfläche

**Filterspalte links:** Bauteilklasse «Wände · 15» mit rotem «● 1», darunter
Decken 3, Türen 3, Fenster 6, Treppen 1. Property-Set `Pset_WallCommon`,
Geschoss-Knöpfe EG, 1. OG, 2. OG (keiner gewählt = alle).

**Werte bearbeiten, Tabelle + 3D** (Standard):

1. Die Tabelle zeigt 15 Wände, sortiert EG, 1. OG, 2. OG. GlobalId, Name und
   Geschoss lassen sich nicht ändern.
2. Bei FireRating öffnet ein Klick in die Zelle eine Auswahl EI30, EI60, EI90.
   Der Fehlwert EI45 aus dem Modell steht zusätzlich in der Liste.
3. Bei der «Innenwand 120» im 1. OG `EI60` eintragen, bei der
   «Aussenwand Nord 300» im 2. OG `EI45`.
   Erwartet im Status: «✓ 1 gültig» und «✗ 1 Fehler».
4. Geschoss «EG»: Die Tabelle zeigt 5 Wände. Nochmals auf «EG» klicken: wieder alle.
5. «nur Lücken und Fehler» einschalten: Es bleiben die Wand mit EI45 und die
   beiden Wände mit den Eingaben aus Schritt 3. Wieder ausschalten.

**3D und Eigenschaften** (rechts):

1. Beim ersten Öffnen erscheint kurz «3D-Geometrie wird berechnet …», dann
   das ganze Gebäude: drei Geschosse, Fenster in der Südfassade, Treppe im
   Westraum, eine Tür pro Geschoss in der Innenwand.
2. Im Viewer auf die Innenwand im 1. OG klicken.
   Erwartet: Sie wird orange, in der Tabelle ist das Häkchen «3D» gesetzt.
   Unter dem Viewer erscheint «EIGENSCHAFTEN · Innenwand 120 · 1. OG» mit
   FireRating (Auswahl, steht auf EI60 und «✓ leer → EI60, gültig»),
   IsExternal und LoadBearing.
3. Im Formular LoadBearing auf «Ja» stellen, «Übernehmen». Die Tabelle zeigt
   sofort «Ja». In «Prüfen & Speichern» steht bei dieser Zeile «Eingabe über: Eigenschaften».
4. Ctrl+Klick auf die Innenwand im 2. OG: Beide sind orange, das Formular
   verschwindet, statt dessen steht «2 Bauteile angewählt».
5. Klick auf eine Tür: Die Arbeitsfläche wechselt auf Türen, die Tür ist angehakt.
6. «⚙ Ansicht» oben rechts → «Beim Anwählen hinzoomen» aus: Die Auswahl bleibt
   orange, der Rest wird nicht mehr transparent und die Kamera bleibt stehen.

**3D gross** (Umschalter oben rechts):

1. Das Gebäude füllt die Fläche.
2. Ansicht «Oben», dann «Iso». Geschoss «1. OG»: nur dieses Geschoss ist sichtbar, wieder «alle».
3. Schnitt «waagrecht (Grundriss)», dann «auf Geschoss … → Grundriss EG»:
   Blick von oben auf das EG, Treppe, Tür und Fenster sind zu sehen.
   Regler bewegen: Die Schnitthöhe ändert sich. Danach «kein Schnitt».
4. Auf die Treppe klicken. Pop-up: Pset_StairCommon mit FireRating, IsExternal,
   RiserHeight, TreadLength. FireRating auf `R90` stellen, «Übernehmen».
   Erwartet: Die Treppe wird grün, im Pop-up steht «✓ R30 → R90».
5. Auf ein Fenster klicken, ThermalTransmittance `9` eintragen, «Übernehmen».
   Erwartet: Das Fenster wird rot, im Pop-up steht «✗ muss zwischen 0.3 und 3.0 liegen».
6. Zurück auf «Tabelle + 3D», links «Treppen»: FireRating zeigt R90.

**Neues Pset anlegen** (Umschalter oben links):

1. Links Wände und Geschoss «EG» wählen, Name `CH_Brandschutz`.
2. Properties: `Nachweis` · Text · `VKF 2015` und `Geprueft` · Ja/Nein · `Ja`.
3. In der Bauteilliste stehen 5 Wände, das 3D rechts zeigt sie orange.
4. «Property-Set bei 5 Bauteil(en) vormerken».
   Erwartet: «10 Werte vorgemerkt», im Status 10 weitere gültige Änderungen.
5. Gegenprobe: `Dicke` · Zahl · `dick` ergibt die Meldung «passt nicht zum Typ Zahl».

## 3 Prüfen & Speichern

**Änderungen** (nur mit den Eingaben aus «Werte bearbeiten», Schritt 3):
links «Alle Änderungen · 2», «gültig · 1», «Fehler · 1».

- ✓ Innenwand 120 · 1. OG · FireRating: leer → EI60 · Eingabe über Tabelle
- ✗ Aussenwand Nord 300 · 2. OG · FireRating: leer → EI45 · nicht in der Werteliste (EI30, EI60, EI90)

Bei der fehlerhaften Zeile «Entfernen» anhaken, «1 markierte entfernen»: Die
Zeile verschwindet, im Status steht kein Fehler mehr. «Alle verwerfen …» fragt
vor dem Löschen nach.

**Modell gegen Regeln:**

- Ohne IDS: **1 Regelverstoss**, die Wand mit EI45. «Bauteil öffnen» steht
  auf dieser Wand, «zum Bauteil →» wechselt in die Arbeitsfläche, die Wand
  ist angehakt und das Formular offen.
- Bereich «Laden» → «Beispiel-IDS aus config/ verwenden».
  Erwartet: «11 Regeln aus 5 Spezifikationen», unter «Nicht übernommen» die
  Anforderung an den Türnamen. Hier: **5 Regelverstösse, davon
  4 Pflichtwert fehlt** (2 Wände und 1 Tür ohne FireRating, 1 Fenster ohne U-Wert)
  plus EI45. In der Tabelle der Arbeitsfläche heisst die Spalte «FireRating *».
- Bei einer Wand FireRating leeren: In der Änderungsliste steht
  «Pflichtwert, darf nicht leer sein (Regel: Wände: Brandschutz und Tragwerk)».

**Speichern** (Karte rechts):

1. Name für das Protokoll eingeben, «IFC-Kopie erstellen».
2. Drei Downloads: `testmodell_bearbeitet.ifc`, `testmodell_bauteilliste.xlsx`,
   `testmodell_protokoll.csv`.

Kontrolle mit den beiden Eingaben aus Schritt 3 (ohne IDS):

- Die Kopie im Bereich «Laden» hochladen: zwei Wände mit EI60, eine Wand weiter ohne FireRating.
- Bauteilliste, Blatt «Übersicht»: Blätter Übersicht, Wände, Decken, Türen,
  Fenster, Treppen, Legende, Änderungen. Ergebnis «Geänderte Werte · Bauteile:
  1 Wert · 1 Bauteil», «Abgelehnte Eingaben: 1» mit der Aussenwand Nord und EI45.
  «Wände →» springt auf das Blatt «Wände».
- Blatt «Wände»: bei der Innenwand 1. OG grün «leer → EI60». Die Innenwand im
  2. OG hat EI45 schon im Modell: rot, Grund als Kommentar, Stand «✗ offen (1)».
  Die abgelehnte Aussenwand Nord bleibt leer (ohne IDS ist FireRating kein Pflichtwert).
- Blatt «Änderungen»: 2 Zeilen, «gespeichert» und «abgelehnt».
- Das Protokoll (CSV) enthält nur die gültige Änderung.

## Regeln (Bereich «⚙ Regeln»)

1. Die Tabelle zeigt 14 Regeln, rechts steht «Entspricht der Standardvorlage».
2. Bei IfcWall · Pset_WallCommon · FireRating die Werteliste auf
   `EI30, EI60, EI90, EI120` ändern, «Regeln speichern».
   Erwartet: «Regeln gespeichert», «1 Abweichung von der Standardvorlage».
   In der Arbeitsfläche bietet FireRating jetzt EI120 an.
3. Gegenprobe: Bei einer Zeile Typ «Muster» mit Muster `([` wählen und speichern:
   Fehlermeldung «Muster ist ungültig», nichts wird gespeichert.
4. «Eigene Regeln verwerfen» anhaken, «Auf Standard zurücksetzen»: Die
   Werteliste ist wieder EI30, EI60, EI90.

## Weitere Prüfungen

- **Ja/Nein ändern:** IsExternal einer Aussenwand auf «Nein» setzen, speichern, Kopie neu laden: Der Wert ist «Nein».
- **Wert löschen:** Die Zelle mit «EI45» leeren: Das Property wird entfernt.
- **Fenster:** links Fenster: 6 Bauteile, 1 leerer U-Wert. `1,1` ist gültig, `5` liegt über dem Maximum 3.0 und wird abgelehnt.
- **Treppe:** links Treppen, die Treppe anhaken: Die Kamera zeigt sie mit der Deckenöffnung darüber.
- **Defekte Datei:** Eine beliebige andere Datei mit Endung .ifc hochladen: Es erscheint eine Fehlermeldung, die App läuft weiter.
