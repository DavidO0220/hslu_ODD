"""Feste Schnittstellen zwischen den Modulen.

Diese Datei ist der «Vertrag» zwischen Person A (Kern-Logik) und Person B
(Oberfläche). Spaltennamen werden nur hier geändert, nie direkt im Code.
"""

# --- Tabelle: Reader -> Oberfläche -> Diff ---------------------------------
# Eine Zeile pro Bauteil. Nach diesen festen Spalten folgt eine Spalte pro
# Property des gewählten Property-Sets.
COL_GLOBAL_ID = "GlobalId"
COL_NAME = "Name"
COL_STOREY = "Geschoss"
FIXED_COLUMNS = [COL_GLOBAL_ID, COL_NAME, COL_STOREY]

# Diese Spalten darf der Nutzer in der Oberfläche nicht bearbeiten.
LOCKED_COLUMNS = FIXED_COLUMNS

# --- Änderungsliste: Diff -> Validator -> Writer -> Protokoll --------------
# Eine Zeile pro geänderter Zelle.
COL_PSET = "Pset"
COL_PROPERTY = "Property"
COL_OLD = "Alt"
COL_NEW = "Neu"
CHANGE_COLUMNS = [COL_GLOBAL_ID, COL_NAME, COL_PSET, COL_PROPERTY, COL_OLD, COL_NEW]

# Gemeinsame Änderungsliste (core/pending.py): zusätzlich die Bauteilklasse,
# weil Änderungen aus mehreren Klassen zusammenkommen (Tabelle und 3D-Viewer)
COL_CLASS = "Klasse"

# Vom Validator ergänzt
COL_VALID = "Gueltig"
COL_MESSAGE = "Meldung"
VALIDATED_COLUMNS = CHANGE_COLUMNS + [COL_VALID, COL_MESSAGE]

# --- Protokoll ---------------------------------------------------------------
COL_TIMESTAMP = "Zeitpunkt"
COL_USER = "Benutzer"
LOG_COLUMNS = [COL_TIMESTAMP, COL_USER] + CHANGE_COLUMNS
