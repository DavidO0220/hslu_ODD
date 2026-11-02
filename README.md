# IFC-Property-Editor

Webanwendung zum Ergänzen, Prüfen und Zurückschreiben von Properties in
IFC-Modellen. Fachpersonen ohne BIM-Software ergänzen Werte im Browser, das
Programm prüft sie gegen Regeln und schreibt gültige Werte in eine Kopie des
IFC-Modells.

Semesterprojekt DT_PROGR HS26, HSLU Digital Construction · David Odermatt, Gian Scherer

## Einrichten (Windows, PowerShell im Terminal von VS Code)

Voraussetzung: Python 3.11, 3.12 oder 3.13 (64 Bit). Prüfen mit `python --version`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Falls `Activate.ps1` wegen der Ausführungsrichtlinie abbricht, einmalig:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. In VS Code danach unten
rechts den Interpreter `.venv` wählen.

## Testen

```powershell
pytest
```

Erwartet: alle Tests grün. Das Testmodell `data/testmodell.ifc` liegt bei.
Neu erzeugen lässt es sich mit `python tools\make_test_model.py`.

## Starten

```powershell
streamlit run app.py
```

Der Browser öffnet `http://localhost:8501`. Ablauf mit dem Testmodell:
siehe [docs/Durchlauf.md](docs/Durchlauf.md).

## Aufbau

```
app.py               Oberfläche (Streamlit), fünf Reiter: Laden, Bearbeiten, 3D-Modell, Prüfen, Speichern
viewer/              3D-Viewer (three.js)
  viewer.html        kleiner Viewer neben der Tabelle in «Bearbeiten» (nur Anzeige)
  component/         grosser Viewer im Reiter «3D-Modell»: Streamlit-Komponente mit Rückkanal
    index.html       Navigation, Schnitt, Pop-up mit Eigenschaften
    vendor/          three.js r169 (MIT-Lizenz), lokal, damit kein Internet nötig ist
core/                Kern-Logik, kennt Streamlit nicht
  schema.py          feste Spaltennamen: Vertrag zwischen den Modulen
  ifc_reader.py      IFC laden, Klassen und Psets auflisten, Tabelle bauen
  display.py         Ja/Nein-Werte für die Anzeige aufbereiten
  diff.py            Änderungen zwischen Original und Bearbeitung finden
  validator.py       Änderungen gegen config/rules.json prüfen
  pending.py         gemeinsame Liste offener Änderungen aus Tabelle und 3D-Modell
  ifc_writer.py      gültige Änderungen in eine IFC-Kopie schreiben
  changelog.py       Protokoll der Änderungen als CSV
  geometry.py        Dreiecksnetze der Bauteile für den 3D-Viewer (IfcOpenShell)
config/rules.json    erlaubte Werte pro Klasse, Pset und Property
tools/               Testmodell erzeugen
tests/               automatische Tests (pytest)
data/                Testmodell
.streamlit/          Farben der Oberfläche
```

Datenfluss: `Original-IFC → Reader → Tabelle / 3D-Modell → (Bearbeitung) → gemeinsame Änderungsliste → Validator → Writer → IFC-Kopie + Protokoll`

Die Änderungsliste sammelt alle Eingaben, egal aus welchem Reiter und welcher
Klasse. Die Tabelle zeigt offene Änderungen bereits an, ein Wechsel der Klasse
verwirft nichts.

## 3D-Viewer

Im Reiter «Bearbeiten» steht rechts neben der Tabelle das Modell in 3D.

- Linke Maustaste dreht, rechte Maustaste verschiebt, das Mausrad zoomt.
  Ein Klick ohne Ziehen zeigt Name, Klasse und Geschoss des Bauteils.
- Bauteilklasse und Property-Set lassen sich auch im Reiter «Bearbeiten» wählen.
  Die Felder sind mit denen in «Laden» gekoppelt.
- Die Tabelle hat vorne die Häkchen-Spalte «3D». Ein Häkchen wählt das Bauteil
  im Viewer an, mehrere Häkchen sind möglich. Die Kamera fährt zur Auswahl,
  die Bauteile werden orange, der Rest transparent. Unter dem Viewer stehen
  ihre aktuellen Werte, auch noch nicht gespeicherte. Die Häkchen sind keine
  Änderung am Modell und erscheinen nicht im Schritt «Prüfen».
- In der Seitenleiste: «3D-Ansicht anzeigen» blendet den Viewer aus,
  «Bauteil beim Anwählen zeigen» schaltet Auswahl und Kamerafahrt ab,
  «Transparenz übriges Modell» regelt, wie durchsichtig der Rest wird.

Die Auswahl läuft über eine Häkchen-Spalte, weil die bearbeitbare Tabelle von
Streamlit keine angeklickte Zeile zurückmeldet. Ein Klick im 3D-Modell setzt
kein Häkchen, er benennt das Bauteil nur.

Die Geometrie wird beim ersten Öffnen des Reiters einmal berechnet und dann
zwischengespeichert. Bei grossen Modellen (mehrere tausend Bauteile) dauert
das spürbar, und der Viewer überträgt entsprechend viele Daten an den Browser.

## Reiter «3D-Modell»

Das Modell füllt den Reiter, alle Werkzeuge liegen im Viewer selbst:

- **Navigation:** drehen, verschieben, zoomen; «Ganzes Modell»; feste Ansichten
  Iso, Oben, Süd, Nord, Ost, West; Geschossfilter; Bauteilklassen ein/aus.
- **Schnitt:** waagrecht (Grundriss), senkrecht mit Ebene Nord–Süd oder
  Ost–West. Der Regler verschiebt die Ebene, «⇄ Seite» zeigt die andere Hälfte,
  «auf Geschoss …» setzt einen Grundriss 1.5 m über die Geschossunterkante und
  schaut von oben. Die Schnittflächen sind offen (man sieht in die Bauteile).
- **Pop-up:** Klick auf ein Bauteil zeigt Name, Klasse, Geschoss, GlobalId und
  alle Property-Sets. Alle Werte sind bearbeitbar. Ja/Nein und Wertelisten aus
  den Regeln erscheinen als Auswahl. Properties, die laut Regeln fehlen, stehen
  mit «fehlt» da und lassen sich ergänzen. Mengen (Qto) werden nur angezeigt.
  «Übernehmen» schickt die Eingaben an Python, das Prüfergebnis erscheint im
  Pop-up. «◎ Hinzoomen» fährt zum Bauteil und macht den Rest transparent.
- **Farben:** orange = ausgewählt, grün = offene gültige Änderung, rot = Fehler.

Technisch ist der Viewer eine Streamlit-Komponente (`components.declare_component`).
Sie lädt three.js als Text und bindet es als Blob ein, damit der Dateityp, mit
dem Windows `.js`-Dateien ausliefert, keine Rolle spielt.

## Regeln anpassen

`config/rules.json` legt pro Bauteilklasse, Property-Set und Property fest,
welche Werte erlaubt sind:

| Typ | Bedeutung | Beispiel |
|---|---|---|
| `enum` | Wert muss in der Liste stehen | `{"type": "enum", "values": ["EI30", "EI60", "EI90"]}` |
| `bool` | Ja oder Nein | `{"type": "bool"}` |
| `float` | Zahl, optional mit Grenzen | `{"type": "float", "min": 0.05, "max": 3.0}` |

Properties ohne Regel werden ohne Prüfung übernommen.

## Sicherheitsregeln beim Schreiben

- Das Original wird nie verändert, es entsteht immer eine Kopie.
- Nur gültige Änderungen werden geschrieben.
- Der Datentyp eines bestehenden Properties bleibt erhalten.
- Ja/Nein-Werte werden vor dem Schreiben in echte Wahrheitswerte umgewandelt.
- Hängt ein Property-Set an mehreren Bauteilen, erhält das geänderte Bauteil eine eigene Kopie.
- Fehlt das Property-Set an einem Bauteil, wird es angelegt.
- Die erzeugte Datei wird zur Kontrolle wieder geöffnet.

## Grenzen

- Nur einfache Properties (IfcPropertySingleValue), keine Mengen (Qto), keine Aufzählungs-Properties.
- Werte, die nur am Bauteiltyp hängen, werden nicht angezeigt.
- Betrieb lokal im Browser, kein Mehrbenutzerbetrieb.
- Der 3D-Viewer zeigt Bauteile (IfcElement), keine Räume (IfcSpace) und keine Öffnungen.
