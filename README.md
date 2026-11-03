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
app.py               Oberfläche (Streamlit), Layout «Eine Arbeitsfläche» mit vier Bereichen
viewer/              3D-Viewer (three.js)
  component/         Streamlit-Komponente mit Rückkanal, für beide Viewer
    index.html       Modus «select» neben der Tabelle, Modus «edit» in der Ansicht «3D gross»
    vendor/          three.js r169 (MIT-Lizenz), lokal, damit kein Internet nötig ist
core/                Kern-Logik, kennt Streamlit nicht
  schema.py          feste Spaltennamen: Vertrag zwischen den Modulen
  ifc_reader.py      IFC laden, Klassen, Psets und Geschosse auflisten, Tabelle bauen
  display.py         Ja/Nein-Werte für die Anzeige aufbereiten
  diff.py            Änderungen zwischen Original und Bearbeitung finden
  validator.py       Änderungen gegen config/rules.json prüfen
  pending.py         gemeinsame Liste offener Änderungen, mit Herkunft und Zeitpunkt jeder Eingabe
  ids_import.py      Prüfregeln aus einer IDS-Datei (buildingSMART) lesen
  model_check.py     alle Bauteile gegen die Regeln prüfen («Modell gegen Regeln»)
  rules_store.py     Regeln als Tabelle, Eingaben prüfen, speichern, zurücksetzen
  ifc_writer.py      gültige Änderungen in eine IFC-Kopie schreiben
  report.py          Bauteilliste als Excel-Arbeitsmappe (openpyxl)
  changelog.py       Protokoll der Änderungen als CSV
  geometry.py        Dreiecksnetze der Bauteile für den 3D-Viewer (IfcOpenShell)
config/rules.json    aktive Regeln: erlaubte Werte pro Klasse, Pset und Property (im Bereich «⚙ Regeln» bearbeitbar)
config/rules_standard.json   Standardvorlage der Regeln, wird nie verändert
config/beispiel_anforderungen.ids   Beispiel-IDS zum Testmodell
docs/Projektjournal.md   Quellen und Arbeitsjournal des Projekts
tools/               Testmodell erzeugen
tests/               automatische Tests (pytest)
data/                Testmodell
.streamlit/          Farben der Oberfläche
```

Datenfluss: `Original-IFC → Reader → Arbeitsfläche (Tabelle, Formular, 3D) → gemeinsame Änderungsliste → Validator → Writer → IFC-Kopie + Bauteilliste (Excel) + Protokoll (CSV)`

Die Änderungsliste sammelt alle Eingaben, egal aus welcher Ansicht und welcher
Klasse. Die Tabelle zeigt offene Änderungen bereits an, ein Wechsel der Klasse
verwirft nichts.

## Layout «Eine Arbeitsfläche»

Keine Seitenleiste. Oben Titel, Status (Datei, gültige Änderungen, Fehler,
angewählte Bauteile) und «⚙ Ansicht» mit den Einstellungen für die 3D-Ansichten.
Darunter vier Bereiche:

| Bereich | Inhalt |
|---|---|
| 1 Laden | IFC-Datei und Prüfregeln (rules.json, optional IDS). Rechts: Bauteile, Geschosse, Anteil erfüllt, eine Zeile pro Klasse mit Fortschrittsbalken |
| 2 Arbeitsfläche | links Filter, Mitte Tabelle, rechts 3D und Eigenschaften. Umschalten: «Werte bearbeiten» / «Neues Pset anlegen», «Tabelle + 3D» / «3D gross» |
| 3 Prüfen & Speichern | Änderungsliste mit Filter und «Entfernen», «Modell gegen Regeln» mit «zum Bauteil →», rechts Speichern und Downloads |
| ⚙ Regeln | Regeltabelle bearbeiten, rechts speichern, herunterladen, auf Standard zurücksetzen |

Streamlit führt alle Bereiche bei jedem Durchlauf aus, damit Eingaben erhalten
bleiben. Nur die 3D-Ansichten laufen nicht, solange ihr Bereich verborgen ist
(`st.tabs(..., on_change="rerun")` und `.open`), weil sie viele Daten an den
Browser schicken. Knöpfe wie «Zur Arbeitsfläche →» wechseln den Bereich über
`st.session_state["area"]`.

## Arbeitsfläche

**Filterspalte links**
- Bauteilklasse mit Anzahl Bauteile und rotem Punkt für offene Werte
  (fehlender Pflichtwert oder ungültiger Wert).
- Property-Set, Geschoss (Knöpfe, nichts gewählt = alle Geschosse).
- «nur Lücken und Fehler»: nur Bauteile mit offenem Wert oder offener Änderung
  in diesem Pset. Eine korrigierte Zeile bleibt sichtbar, bis gespeichert wird.

**Werte bearbeiten, Ansicht «Tabelle + 3D»**
- Die Tabelle zeigt Bauteile, die das gewählte Pset schon haben. Ja/Nein und
  Wertelisten aus den Regeln sind Auswahlfelder (z. B. FireRating EI30/EI60/EI90),
  Pflicht-Properties haben ein «*». Werte aus dem Modell, die nicht in der Liste
  stehen, bleiben sichtbar und werden als Fehler gemeldet.
- Properties, die laut Regeln zum Pset gehören, im Modell aber fehlen,
  erscheinen als leere Spalte und lassen sich nachtragen.
- Häkchen «3D» oder Klick im Modell wählt ein Bauteil an, Ctrl+Klick fügt hinzu.
  Liegt das angeklickte Bauteil nicht in der Tabelle, wechselt die Arbeitsfläche
  auf seine Klasse und sein Pset.
- Ist genau ein Bauteil angewählt, steht rechts unter dem Viewer das Formular
  «Eigenschaften» mit allen Properties des Psets. «Übernehmen» trägt die Werte
  in die Änderungsliste ein, mit Prüfergebnis pro Property.
- «⚙ Ansicht» oben rechts: «Beim Anwählen hinzoomen» (Kamerafahrt und
  Transparenz, ausgeschaltet bleibt die Auswahl nur orange) und
  «Transparenz übriges Modell».

**Werte bearbeiten, Ansicht «3D gross»**

Das Modell füllt die Fläche, alle Werkzeuge liegen im Viewer selbst:

- **Navigation:** drehen, verschieben, zoomen; «Ganzes Modell»; feste Ansichten
  Iso, Oben, Süd, Nord, Ost, West; Geschossfilter; Bauteilklassen ein/aus.
- **Schnitt:** waagrecht (Grundriss), senkrecht mit Ebene Nord–Süd oder
  Ost–West. Der Regler verschiebt die Ebene, «⇄ Seite» zeigt die andere Hälfte,
  «auf Geschoss …» setzt einen Grundriss 1.5 m über die Geschossunterkante und
  schaut von oben. Die Schnittflächen sind offen (man sieht in die Bauteile).
- **Pop-up:** Klick auf ein Bauteil zeigt Name, Klasse, Geschoss, GlobalId und
  zwei getrennte Bereiche: «Bestehende Property-Sets» (bearbeiten, fehlende
  Properties laut Regeln mit «fehlt» ergänzen) und «Neues Property-Set anlegen».
  Ja/Nein und Wertelisten erscheinen als Auswahl. Mengen (Qto) werden nur angezeigt.
  «Übernehmen» schickt die Eingaben an Python, das Prüfergebnis erscheint im Pop-up.
- **Farben:** orange = ausgewählt, grün = offene gültige Änderung, rot = Fehler.

**Neues Pset anlegen**
- Namen eingeben oder eine Vorlage aus den Regeln nehmen.
- Properties mit Typ eintragen: Text (IfcLabel), Zahl (IfcReal), Ja/Nein
  (IfcBoolean). Der Typ ist nötig, weil IfcOpenShell bei neuen Properties ohne
  Vorlage den IFC-Typ aus dem Wert ableitet.
- Bauteile der gewählten Klasse auswählen, die das Set noch nicht haben, mit dem
  Geschossfilter links eingrenzen. Das 3D rechts zeigt sie orange.
- «Property-Set … vormerken» trägt die Werte in die Änderungsliste ein.
- Eigene Sets nicht mit «Pset_» beginnen lassen, das Präfix ist für
  buildingSMART reserviert. Die App warnt dann.

Die Häkchen «3D» sind keine Änderung am Modell. Die Geometrie wird einmal pro
Datei berechnet und zwischengespeichert. Bei grossen Modellen (mehrere tausend
Bauteile) dauert das spürbar.

Technisch ist der Viewer eine Streamlit-Komponente (`components.declare_component`).
Sie lädt three.js als Text und bindet es als Blob ein, damit der Dateityp, mit
dem Windows `.js`-Dateien ausliefert, keine Rolle spielt.

## Prüfen & Speichern

- **Änderungen:** eine Zeile pro Eingabe mit Status ✓/✗, Bauteil, Alt, Neu,
  Meldung und «Eingabe über» (Tabelle, Eigenschaften, 3D-Modell, Neues Pset).
  Links nach Status und Klasse filtern. Häkchen «Entfernen» und
  «markierte entfernen» nimmt Eingaben aus der Liste, «Alle verwerfen …» fragt nach.
- **Modell gegen Regeln:** alle Bauteile, die die Regeln noch nicht erfüllen,
  mit dem aktuellen Stand inklusive offener Änderungen. «zum Bauteil →» öffnet
  das gewählte Bauteil in der Arbeitsfläche.
- **Speichern:** «IFC-Kopie erstellen» schreibt die gültigen Änderungen in eine
  Kopie. Danach gibt es drei Downloads: IFC-Kopie, Bauteilliste (Excel),
  Protokoll (CSV).

### Bauteilliste (Excel)

`<Datei>_bauteilliste.xlsx`, der Stand «nachher» wird aus der geschriebenen
Kopie gelesen:

| Blatt | Inhalt |
|---|---|
| Übersicht | Modell, Kopie, SHA-256 von Original und Kopie, erstellt am/von, Prüfregeln. Ergebnis vorher/nachher (Bauteile erfüllt, offene Werte, geänderte Werte, neue Psets, abgelehnte Eingaben). Eine Zeile pro Klasse mit Link auf ihr Blatt und Erfüllungsgrad als Balken. Abgelehnte Eingaben mit Grund. Visum Geprüft/Freigegeben |
| ein Blatt pro Klasse | eine Zeile pro Bauteil (Geschoss, Bauteil, GlobalId), Properties gruppiert nach Pset. Geändert grün «alt → neu», Regel nicht erfüllt rot mit Grund als Kommentar, Spalte «Stand» ✓ erfüllt / ✗ offen |
| Legende | Farben und alle verwendeten Regeln mit Quelle |
| Änderungen | jede Eingabe, gespeichert oder abgelehnt, mit Zeitpunkt, Bearbeiter, Herkunft und Meldung |

Klassenblätter haben fixierte Kopfzeilen und Filter, alle Blätter sind für A4
quer eingerichtet. Klassen ohne Regeln und ohne Änderungen bekommen kein Blatt.

## Prüfregeln aus einer IDS-Datei

Im Bereich «Laden» unter «Prüfregeln» lässt sich eine IDS-Datei hochladen
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

Im Bereich «Prüfen & Speichern» zeigt **«Modell gegen Regeln»** alle Bauteile,
die die Regeln noch nicht erfüllen (fehlende Pflichtwerte, ungültige Werte).

## Regeln anpassen

Im Bereich **«⚙ Regeln»** stehen die aktiven Regeln als Tabelle, eine Zeile pro
Property. Werte ändern, Zeilen ergänzen oder löschen, dann «Regeln speichern».
Gespeichert wird in `config/rules.json`. Die Standardvorlage
`config/rules_standard.json` verändert die App nie. «Auf Standard
zurücksetzen» (mit Sicherheitshäkchen) kopiert die Vorlage zurück. Der Bereich
zeigt auch, worin die eigenen Regeln von der Vorlage abweichen.

Die Tests prüfen immer gegen die Standardvorlage, eigene Regeln stören sie nicht.

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
