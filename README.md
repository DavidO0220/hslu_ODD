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
app.py               Oberfläche (Streamlit), vier Reiter: Laden, Bearbeiten, Prüfen, Speichern
core/                Kern-Logik, kennt Streamlit nicht
  schema.py          feste Spaltennamen: Vertrag zwischen den Modulen
  ifc_reader.py      IFC laden, Klassen und Psets auflisten, Tabelle bauen
  display.py         Ja/Nein-Werte für die Anzeige aufbereiten
  diff.py            Änderungen zwischen Original und Bearbeitung finden
  validator.py       Änderungen gegen config/rules.json prüfen
  ifc_writer.py      gültige Änderungen in eine IFC-Kopie schreiben
  changelog.py       Protokoll der Änderungen als CSV
config/rules.json    erlaubte Werte pro Klasse, Pset und Property
tools/               Testmodell erzeugen
tests/               automatische Tests (pytest)
data/                Testmodell
.streamlit/          Farben der Oberfläche
```

Datenfluss: `Original-IFC → Reader → Tabelle → (Bearbeitung) → Diff → Änderungsliste → Validator → Writer → IFC-Kopie + Protokoll`

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
