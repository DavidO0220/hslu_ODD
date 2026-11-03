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
  component/         Streamlit-Komponente mit Rückkanal, für beide Viewer
    index.html       Modus «select» neben der Tabelle, Modus «edit» im Reiter «3D-Modell»
    vendor/          three.js r169 (MIT-Lizenz), lokal, damit kein Internet nötig ist
core/                Kern-Logik, kennt Streamlit nicht
  schema.py          feste Spaltennamen: Vertrag zwischen den Modulen
  ifc_reader.py      IFC laden, Klassen und Psets auflisten, Tabelle bauen
  display.py         Ja/Nein-Werte für die Anzeige aufbereiten
  diff.py            Änderungen zwischen Original und Bearbeitung finden
  validator.py       Änderungen gegen config/rules.json prüfen
  pending.py         gemeinsame Liste offener Änderungen aus Tabelle und 3D-Modell
  ids_import.py      Prüfregeln aus einer IDS-Datei (buildingSMART) lesen
  model_check.py     alle Bauteile gegen die Regeln prüfen («Modell gegen Regeln»)
  ifc_writer.py      gültige Änderungen in eine IFC-Kopie schreiben
  changelog.py       Protokoll der Änderungen als CSV
  geometry.py        Dreiecksnetze der Bauteile für den 3D-Viewer (IfcOpenShell)
config/rules.json    erlaubte Werte pro Klasse, Pset und Property
config/beispiel_anforderungen.ids   Beispiel-IDS zum Testmodell
docs/Projektjournal.md   Quellen und Arbeitsjournal des Projekts
tools/               Testmodell erzeugen
tests/               automatische Tests (pytest)
data/                Testmodell
.streamlit/          Farben der Oberfläche
```

Datenfluss: `Original-IFC → Reader → Tabelle / 3D-Modell → (Bearbeitung) → gemeinsame Änderungsliste → Validator → Writer → IFC-Kopie + Protokoll`

Die Änderungsliste sammelt alle Eingaben, egal aus welchem Reiter und welcher
Klasse. Die Tabelle zeigt offene Änderungen bereits an, ein Wechsel der Klasse
verwirft nichts.

## Reiter «Bearbeiten»: zwei Modi

Oben wählst du, was du tun willst:

**Bestehendes Pset bearbeiten**
- Bauteilklasse, Property-Set und Geschoss wählen. Die Tabelle zeigt nur
  Bauteile, die dieses Pset schon haben.
- Ja/Nein und Wertelisten aus `config/rules.json` sind Auswahlfelder
  (z. B. FireRating EI30/EI60/EI90). Werte aus dem Modell, die nicht in der
  Liste stehen, bleiben sichtbar und werden in «Prüfen» als Fehler gemeldet.
- Properties, die laut Regeln zum Pset gehören, im Modell aber fehlen,
  erscheinen als leere Spalte und lassen sich nachtragen.

**Neues Pset anlegen**
- Bauteilklasse wählen, Namen eingeben oder eine Vorlage aus den Regeln nehmen.
- Properties mit Typ eintragen: Text (IfcLabel), Zahl (IfcReal), Ja/Nein
  (IfcBoolean). Der Typ ist nötig, weil IfcOpenShell bei neuen Properties ohne
  Vorlage den IFC-Typ aus dem Wert ableitet.
- Bauteile auswählen, die das Set bekommen (nur solche, die es noch nicht haben),
  optional nach Geschoss. Der Wert gilt für alle gewählten Bauteile.
- «Property-Set … vormerken» trägt die Werte in die Änderungsliste ein.
  Geprüft und gespeichert wird wie immer in «Prüfen» und «Speichern».
- Eigene Sets nicht mit «Pset_» beginnen lassen, das Präfix ist für
  buildingSMART reserviert. Die App warnt dann.

## 3D-Viewer neben der Tabelle

Im Modus «Bestehendes Pset bearbeiten» steht rechts neben der Tabelle das Modell in 3D.

- Drehen (linke Maustaste), verschieben (rechte), zoomen (Mausrad), feste
  Ansichten, Geschossfilter und Klassen wie im Reiter «3D-Modell».
- **Auswählen per Klick:** Klick auf ein Bauteil wählt es aus und setzt das
  Häkchen in der Spalte «3D». Ctrl+Klick fügt hinzu oder entfernt.
  «Auswahl aufheben» leert die Auswahl.
- **Auswählen über die Liste:** Häkchen in der Spalte «3D» wirken gleich, die
  Kamera fährt zur Auswahl.
- Liegt das angeklickte Bauteil nicht in der Tabelle (andere Klasse, anderes
  Pset oder Geschossfilter), wechselt die Tabelle auf seine Klasse und sein Pset.
- Unter dem Viewer stehen die aktuellen Werte der ausgewählten Bauteile.
- Seitenleiste: «3D-Ansicht anzeigen» blendet den Viewer aus, «Beim Anwählen
  hinzoomen» schaltet Kamerafahrt und Transparenz ab (die Auswahl bleibt orange),
  «Transparenz übriges Modell» regelt, wie durchsichtig der Rest wird.

Die Häkchen sind keine Änderung am Modell und erscheinen nicht in «Prüfen».
Die Geometrie wird einmal pro Datei berechnet und zwischengespeichert. Bei
grossen Modellen (mehrere tausend Bauteile) dauert das spürbar.

## Reiter «3D-Modell»

Das Modell füllt den Reiter, alle Werkzeuge liegen im Viewer selbst:

- **Navigation:** drehen, verschieben, zoomen; «Ganzes Modell»; feste Ansichten
  Iso, Oben, Süd, Nord, Ost, West; Geschossfilter; Bauteilklassen ein/aus.
- **Schnitt:** waagrecht (Grundriss), senkrecht mit Ebene Nord–Süd oder
  Ost–West. Der Regler verschiebt die Ebene, «⇄ Seite» zeigt die andere Hälfte,
  «auf Geschoss …» setzt einen Grundriss 1.5 m über die Geschossunterkante und
  schaut von oben. Die Schnittflächen sind offen (man sieht in die Bauteile).
- **Pop-up:** Klick auf ein Bauteil zeigt Name, Klasse, Geschoss, GlobalId und
  zwei getrennte Bereiche: «Bestehende Property-Sets» (bearbeiten, fehlende
  Properties laut Regeln mit «fehlt» ergänzen) und «Neues Property-Set anlegen»
  (Sets aus den Regeln, die das Bauteil noch nicht hat, und bereits vorgemerkte
  neue Sets). Ja/Nein und Wertelisten erscheinen als Auswahl. Mengen (Qto) werden
  nur angezeigt.
  «Übernehmen» schickt die Eingaben an Python, das Prüfergebnis erscheint im
  Pop-up. «◎ Hinzoomen» fährt zum Bauteil und macht den Rest transparent.
- **Farben:** orange = ausgewählt, grün = offene gültige Änderung, rot = Fehler.

Technisch ist der Viewer eine Streamlit-Komponente (`components.declare_component`).
Sie lädt three.js als Text und bindet es als Blob ein, damit der Dateityp, mit
dem Windows `.js`-Dateien ausliefert, keine Rolle spielt.

## Prüfregeln aus einer IDS-Datei

In der Seitenleiste unter «Prüfregeln» lässt sich eine IDS-Datei hochladen
(Information Delivery Specification, Standard von buildingSMART). Zum
Ausprobieren liegt `config/beispiel_anforderungen.ids` bei.

- Die IDS ergänzt `config/rules.json` und hat bei gleicher Property Vorrang.
  Mit «Nur Regeln aus der IDS» gilt nur die IDS.
- Übernommen werden Anforderungen an Properties: Werteliste, fester Wert,
  Muster, Zahlenbereich, Datentyp, Pflicht/optional/verboten. Die Klasse kommt
  aus der Anwendbarkeit (Facet «entity»).
- Was nicht passt (Attribute, Klassifikation, Material, partOf, Muster in
  Pset-Namen …), steht unter «Nicht übernommen». Die App prüft es nicht.
- Pflichtwerte gelten auch beim Bearbeiten: Einen Pflichtwert leeren ist ein Fehler.
- Grenze: Zahlen in einer IDS sind in SI-Einheiten (Länge in m). Die App
  rechnet Modelle in mm nicht um.

Im Reiter «Prüfen» zeigt **«Modell gegen Regeln»** alle Bauteile, die die
Regeln noch nicht erfüllen (fehlende Pflichtwerte, ungültige Werte), mit dem
aktuellen Stand inklusive offener Änderungen.

## Regeln anpassen

`config/rules.json` legt pro Bauteilklasse, Property-Set und Property fest,
welche Werte erlaubt sind:

| Typ | Bedeutung | Beispiel |
|---|---|---|
| `enum` | Wert muss in der Liste stehen | `{"type": "enum", "values": ["EI30", "EI60", "EI90"]}` |
| `bool` | Ja oder Nein | `{"type": "bool"}` |
| `float` | Zahl, optional mit Grenzen | `{"type": "float", "min": 0.05, "max": 3.0}` |
| `pattern` | Text nach Muster (Regex) | `{"type": "pattern", "pattern": "VKF.*"}` |
| `text` | beliebiger Text | `{"type": "text"}` |
| `prohibited` | Property darf nicht vorkommen | `{"type": "prohibited"}` |

Jede Regel kann zusätzlich `"required": true` (Pflichtwert) haben.

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
