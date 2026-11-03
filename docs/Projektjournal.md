# Projektjournal IFC-Property-Editor

DT_PROGR HS26, HSLU Digital Construction · David Odermatt, Gian Scherer

Dieses Dokument wird laufend nachgeführt. Es hat zwei Teile:

- **Teil A – Quellen:** welche Referenz für welche *Funktion* des Programms
  verwendet wurde (nicht für einzelne Codezeilen).
- **Teil B – Arbeitsjournal:** was Schritt für Schritt gemacht und entschieden
  wurde, als Grundlage für Präsentationen.

Regel für die Pflege: Jede neue Quelle kommt in Teil A, jeder Arbeitsschritt in
Teil B, im selben Commit wie die Arbeit selbst. Werte, die nicht aus einer
Quelle stammen, sind als **Annahme** gekennzeichnet.

---

## Teil A – Quellen

### A1 Modulunterlagen

| Nr | Quelle | Verwendet für | Wo im Programm |
|---|---|---|---|
| A1.1 | Modulskripte DT_PROGR HS26, Semesterwochen 1, 2, 4 (Dozent Michal Rontsinsky) | Vorgaben zu Python, VS Code, venv, requirements.txt, Git/GitHub | Projektaufbau, README «Einrichten» |
| A1.2 | Leistungsnachweis DT_PROGR HS26 | Anforderungen an ZP1 (Kurzpräsentation 3 min, schriftliche Vorabgabe) und an die Abgabe | ZP1-Präsentation, Sprechertext, Phasenplan |
| A1.3 | Semesterplan DT_PROGR HS26 | Termine und Phasen | Phasenplan in der ZP1-Präsentation |

### A2 Standards (buildingSMART)

| Nr | Quelle | Verwendet für | Wo im Programm |
|---|---|---|---|
| A2.1 | IFC4-Dokumentation, Property-Set-Seiten, z. B. [Pset_WallCommon](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcsharedbldgelements/pset/pset_wallcommon.htm), [Pset_DoorCommon](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/Pset_DoorCommon.htm), [Pset_WindowCommon](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/Pset_WindowCommon.htm) | Namen und Datentypen der Standard-Properties (FireRating als IfcLabel, IsExternal/LoadBearing als IfcBoolean, ThermalTransmittance als IfcThermalTransmittanceMeasure, RiserHeight/TreadLength als Länge) | Testmodell (`tools/make_test_model.py`), Regeln (`config/rules.json`) |
| A2.2 | [IFC 4.3: Pset_WallCommon](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/Pset_WallCommon.htm) | Abgleich, dass die Sets in IFC4.3 gleich heissen | Antwort zu IFC2x3/IFC4, Regeln |
| A2.3 | [IDS – Information Delivery Specification](https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/), [Projektseite](https://technical.buildingsmart.org/projects/information-delivery-specification-ids/) | Entscheid, Prüfregeln aus IDS-Dateien zu lesen | IDS-Import (`core/ids_import.py`) |
| A2.4 | [IDS-Repository von buildingSMART](https://github.com/buildingSMART/IDS), Stand Commit 870f9c4 (25.09.2026): `Schema/ids.xsd` (Version 1.0.0), Benutzerhandbuch `property-facet.md`, `restrictions.md`, `units.md` | Aufbau einer IDS (info, specification, applicability, requirements), Property-Facet mit dataType und cardinality (required/optional/prohibited), Einschränkungen (enumeration, pattern, min/max), SI-Einheiten für Zahlen | IDS-Import, Regeltypen `pattern`, `text`, `prohibited`, `required` im Validator, Beispiel-IDS `config/beispiel_anforderungen.ids` |
| A2.5 | IDS-Benutzerhandbuch `property-facet.md` | Regel: Präfixe «Pset_» und «Qto_» sind für buildingSMART reserviert | Warnung im Formular «Neues Pset anlegen» |
| A2.6 | IDS-Beispieldateien aus dem Repository (`IDS_SimpleBIM_examples.ids`, `IDS_wooden-windows.ids`, `IDS_ucms_prefab_pipes_IFC2x3.ids`), Lizenz CC BY-ND 4.0 | Testdaten: Der Import muss echte IDS-Dateien lesen können | `tests/ids_beispiele/` (unverändert, mit Lizenzangabe) |
| A2.7 | [buildingSMART Data Dictionary (bSDD)](https://user.buildingsmart.org/knowledge-base/terminology/), [IfcOpenShell-Doku zum bSDD-Modul](https://dev.glassvision.dedyn.io/Glassvision/IfcOpenShell/src/commit/b63137e859294c47f9f44da6d3722b227fd9f376/src/ifcopenshell-python/docs/bsdd.rst) | Recherche zu Online-Katalogen für Wertelisten | **nicht verwendet**, als mögliche Erweiterung notiert |
| A2.8 | [ifctester im IfcOpenShell-Quellcode](https://dev.glassvision.dedyn.io/Glassvision/IfcOpenShell/src/commit/50c6cbcb2dfc42d06e200e5898bb6b3d6a7fe3e8/src/ifctester) | Recherche: IDS-Prüfung mit IfcOpenShell | **nicht verwendet**, der Import ist eigener Code ohne zusätzliche Abhängigkeit |

### A3 Bibliotheken und ihr Quellcode

| Nr | Quelle | Verwendet für | Wo im Programm |
|---|---|---|---|
| A3.1 | IfcOpenShell, [Quellcode auf GitHub](https://github.com/IfcOpenShell/IfcOpenShell), Branch v0.9.0 (lokal installiert: 0.9.0.post1), früher Stand 0.8 | IFC lesen (`util.element.get_psets`, `get_container`), schreiben (`api.pset.edit_pset`, `add_pset`, `unshare_pset`), Geometrie (`geom.iterator`, Einstellung `use-world-coords`, `util.shape.get_vertices/get_faces`) | `core/ifc_reader.py`, `core/ifc_writer.py`, `core/geometry.py` |
| A3.2 | IfcOpenShell `api/pset/edit_pset.py` | Erkenntnis: Bei neuen Properties ohne Vorlage bestimmt der Python-Typ den IFC-Typ (Text → IfcLabel, Zahl → IfcReal, Wahrheitswert → IfcBoolean) | Typ-Spalte im Formular «Neues Pset anlegen», `pending.typed` |
| A3.3 | IfcOpenShell `Ifc4-schema.cpp` (IFC4-Schema) | Prüfung des Testmodells auf gültige Attribute in dieser Umgebung | nur Prüfumgebung, nicht im Programm |
| A3.4 | [PyPI: ifcopenshell 0.8.3.post2](https://pypi.org/project/ifcopenshell/0.8.3.post2/) | Prüfung, ob es ein Windows-Paket für Python 3.13 gibt (ja, Python 3.9–3.13) | Einrichtungsanleitung |
| A3.5 | Streamlit, [Quellcode auf GitHub](https://github.com/streamlit/streamlit), Version 1.66.1 | `st.data_editor` hat keine Zeilenauswahl (→ Häkchen-Spalte «3D»); `components.v1.html` veraltet (→ `st.iframe`, später Komponente); Sandbox-Regeln für iframes; Nachrichtenprotokoll für Komponenten (componentReady, render, setComponentValue, setFrameHeight); Komponenten-Dateien mit `mimetypes` ausgeliefert (→ three.js per fetch/Blob laden); Regeln für Session State bei Auswahlfeldern (→ gekoppelte Auswahl Klasse/Pset) | `app.py`, `viewer/__init__.py`, `viewer/component/index.html` |
| A3.6 | three.js r169, [GitHub](https://github.com/mrdoob/three.js), MIT-Lizenz | 3D-Darstellung, Kamera-Steuerung (OrbitControls), Schnittebenen (clipping planes), Klick-Auswahl (Raycaster) | `viewer/component/` (Dateien in `vendor/`) |
| A3.7 | Pandas, pytest | Tabellen, Vergleich alt/neu, Protokoll; automatische Tests | ganzes Projekt |

### A4 Fachliche Werte

| Nr | Quelle | Verwendet für | Wo im Programm | Status |
|---|---|---|---|---|
| A4.1 | Feuerwiderstandsklassen nach VKF-Bezeichnung (EI30, EI60, EI90, REI60, R30 …) | Wertelisten für FireRating | `config/rules.json`, Testmodell, Beispiel-IDS | **Annahme:** Bezeichnungen aus dem Fachwissen, gegen die VKF-Brandschutzrichtlinien noch zu prüfen |
| A4.2 | U-Wert Fenster 0.3–3.0 W/m²K (rules.json), 0.3–1.3 W/m²K (Beispiel-IDS) | Zahlenbereich für ThermalTransmittance | `config/rules.json`, Beispiel-IDS | **Annahme:** Beispielwerte, keine Norm |
| A4.3 | Treppensteigung 0.10–0.20 m (rules.json), 0.15–0.19 m (Beispiel-IDS), Auftritt 0.22–0.35 m | Zahlenbereiche für RiserHeight, TreadLength | `config/rules.json`, Beispiel-IDS | **Annahme:** Beispielwerte, gegen SIA 500 bzw. kantonale Vorschriften noch zu prüfen |
| A4.4 | [CRB eBKP-H](https://www.crb.ch/_Resources/Persistent/3/e/6/2/3e62559d380d69676651ab7447fb4b66dc84bdbc/Anwendung_644D11.pdf) | Recherche zu Schweizer Klassifikationen | **nicht verwendet** | – |

### A5 Werkzeuge für Dokumente (nicht Teil des Programms)

| Nr | Werkzeug | Verwendet für |
|---|---|---|
| A5.1 | pptxgenjs, LibreOffice | ZP1-Präsentation erstellen und als Bild prüfen |
| A5.2 | docx (JavaScript) | Sprechertext als Word-Datei |
| A5.3 | Playwright mit Chromium, matplotlib | Vorschaubilder und Browser-Tests des 3D-Viewers |

---

## Teil B – Arbeitsjournal

Daten der Commits aus `git log`. Schritte ohne Commit sind nach Phase eingeordnet.

### Phase 0 – Themenwahl und ZP1 (Oktober 2026, bis 26.10.2026)

| Schritt | Was | Ergebnis / Entscheid |
|---|---|---|
| 0.1 | Modulunterlagen gelesen (SW1, SW2, SW4, Leistungsnachweis, Semesterplan) | Aufgabe für ZP1 geklärt (A1) |
| 0.2 | Themensuche: erst Auswertungstabelle für Ausschreibungen, dann Mengenauszug für das Leistungsverzeichnis, fünf weitere Vorschläge | Thema 5 gewählt: **IFC-Property-Editor** |
| 0.3 | Entscheid Weboberfläche statt Excel | Streamlit: bedienbar ohne BIM-Software, Tabelleneditor eingebaut |
| 0.4 | Programmaufbau in drei Schichten: Oberfläche (app.py), Kern-Logik (core/), Daten; schema.py als Vertrag zwischen den Personen | Grundlage für Arbeitsteilung Person A/B |
| 0.5 | ZP1-Präsentation: vier Stilvarianten, Stil C gewählt; Muss/Kann-Umfang, Phasen statt Daten, Risiken, Abgrenzung | Präsentation mit Teil 1 (3 min) und Teil 2 (Vorabgabe) |
| 0.6 | Beispielfolie (Skizze der Oberfläche: EI60 gültig, EI45 ungültig) als Folie 2 eingefügt | Sprechertext als Word (eine A4-Seite) |

### Phase 1–3 – Grundgerüst, Bearbeiten, Rückschreiben (23.10.2026)

| Schritt | Was | Ergebnis / Entscheid |
|---|---|---|
| 1.1 | Testmodell per Skript (IFC4): 3 Geschosse, 15 Wände, 3 Decken, 3 Türen, bewusst leere und ungültige Werte | Tests wissen genau, was herauskommen muss |
| 1.2 | Reader: Klassen, Psets, Tabelle; Ja/Nein-Anzeige | Commit 73df53d |
| 1.3 | Diff, Validator (enum, bool, float), Writer (Kopie, Datentyp bleibt, Pset entkoppeln/anlegen), Protokoll CSV | Commit 36846a6. Entscheid: Writer öffnet immer das Original neu; `bool("Nein")` ist True, deshalb echte Wahrheitswerte vor dem Schreiben |
| 1.4 | Oberfläche mit vier Reitern, README, Durchlauf-Anleitung | Commit 26a57f9; GitHub-Repo verbunden, Pull Request #1 |
| 1.5 | Prüfung ohne echtes IfcOpenShell (Paketserver gesperrt): Ersatz-Bibliotheken nach Quellcode, 29 Tests | Risiko benannt: erster echter Lauf beim Team |

### Phase 4 – Erster echter Lauf und 3D-Viewer (02.11.2026)

| Schritt | Was | Ergebnis / Entscheid |
|---|---|---|
| 4.1 | Schritt-für-Schritt-Einrichtung bei David (Windows, VS Code, venv, Skript-Sperre) | Python 3.13 geeignet (A3.4); **29 Tests mit echtem IfcOpenShell 0.9 und Pandas 3 grün**; App startet, Testmodell 15/3/2 bestätigt |
| 4.2 | Vorschaubilder 3D-Viewer (Geometrie des Testmodells, Oberfläche nachgebaut) | Freigabe durch David |
| 4.3 | 3D-Viewer neben der Tabelle, Geometrie mit IfcOpenShell, three.js lokal eingebettet; Testmodell mit Türen, 6 Fenstern, Treppe und Öffnungen; Regeln für Fenster und Treppe | Commit 257fb38, Pull Request #2. Entscheid: three.js im Projekt statt aus dem Internet |
| 4.4 | Auswahl über Häkchen-Spalte «3D», Mehrfachauswahl; Klasse/Pset auch im Reiter Bearbeiten, gekoppelt | Commit 6c82bfa. Grund: data_editor ohne Zeilenauswahl (A3.5) |
| 4.5 | Reiter «3D-Modell»: Ansichten, Geschoss- und Klassenfilter, Schnitt waagrecht/senkrecht, Pop-up mit allen Eigenschaften, bearbeitbar | Commit 2323276. Entscheid: eigene Streamlit-Komponente mit Rückkanal (A3.5) |
| 4.6 | Gemeinsame Änderungsliste für Tabelle und 3D (core/pending.py) | Klassenwechsel verwirft keine Eingaben mehr; Prüfen/Speichern über alle Klassen |
| 4.7 | Fehler behoben: Viewer in verdecktem Reiter startete mit Breite 0 | Start erst, wenn der Reiter sichtbar ist |
| 4.8 | Echte Tests bei David: 41, danach 47 Tests grün | Geometrie und Änderungsliste mit echtem IfcOpenShell bestätigt |

### Phase 5 – Kann-Umfang und Prüfung verbessern (03.11.2026)

| Schritt | Was | Ergebnis / Entscheid |
|---|---|---|
| 5.1 | Abgleich mit dem ZP1-Umfang | Muss vollständig; Kann teilweise; offen: Durchlauf mit zweitem Modell, Zusammenführen in main, Abgabe-Doku |
| 5.2 | Tabelle: Auswahlfelder aus den Wertelisten, Geschossfilter, fehlende Regel-Properties als Spalten | Commit e87a7e6 |
| 5.3 | Trennung «Bestehendes Pset bearbeiten» / «Neues Pset anlegen» (Formular mit Typen, Bauteilauswahl, Vorlage aus Regeln); Pop-up ebenfalls getrennt | Commit e87a7e6. Typen nötig wegen A3.2 |
| 5.4 | Kleiner Viewer: Auswahl per Klick, Ctrl+Klick, Wechsel auf Klasse des angeklickten Bauteils | Commit 31e75df |
| 5.5 | Analyse IFC2x3 und IFC4 | Auf beide ausgelegt, getestet nur IFC4; Risiken: Werte am Typ, mm-Einheiten, IfcStairFlight |
| 5.6 | Recherche Standards für Prüfregeln (Pset-Dokumentation, bSDD, IDS, VKF) | Entscheid für IDS (A2.3, A2.4) |
| 5.7 | IDS-Import (eigener Parser), neue Regeltypen pattern/text/prohibited und Pflichtwerte, Beispiel-IDS, Modellprüfung «Modell gegen Regeln», Test mit offiziellen IDS-Beispielen | 58 Tests, 28 App-Abläufe in der Prüfumgebung |
| 5.8 | Projektjournal (dieses Dokument) rückwirkend angelegt | Regel zur Pflege in `CLAUDE.md` |

---

## Bekannte Grenzen (Stand 03.11.2026)

- Getestet nur mit IFC4 und dem eigenen Testmodell. Zweites, echtes Modell steht aus.
- Werte, die am Bauteiltyp hängen, werden nicht angezeigt und nicht geschrieben.
- Keine Einheitenumrechnung: Regeln und IDS-Zahlen gelten in m, Modelle in mm werden falsch beurteilt.
- IDS: nur Property-Anforderungen mit festem Pset- und Property-Namen, Anwendbarkeit nur über die Klasse.
- Schnittflächen im 3D sind offen (keine Füllung).
- Fachliche Grenzwerte in A4 sind Annahmen und noch zu belegen.
