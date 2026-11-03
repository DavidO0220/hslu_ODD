# Hinweise für die Arbeit an diesem Projekt

Projekt: IFC-Property-Editor, DT_PROGR HS26 (HSLU), David Odermatt und Gian Scherer.
Sprache in Code-Kommentaren, Oberfläche und Doku: Deutsch (Schweiz, «ss» statt «ß»).

## Projektjournal pflegen (verbindlich)

`docs/Projektjournal.md` wird bei jeder Arbeit nachgeführt, im selben Commit:

1. **Teil A – Arbeitsjournal:** Jeder Arbeitsschritt mit Datum/Phase, was
   gemacht wurde, Ergebnis und Entscheid mit Begründung.
2. **Teil B – Quellen:** Jede verwendete Referenz (Standard, Dokumentation,
   Quellcode einer Bibliothek, Norm, Webseite) mit Link oder Fundstelle, *wofür*
   sie im Programm verwendet wurde (Funktion, nicht Codezeile) und wo.
   Nummern B1.1, B1.2 … Werte ohne Quelle als **Annahme** kennzeichnen.

Das Journal nur auf Nachfrage ausgeben, aber immer aktuell halten.

## Prüfen vor jedem Commit

```
pytest
```

Alle Tests müssen grün sein. Erwartete Zahlen für den Durchlauf stehen in `docs/Durchlauf.md`.
