from datetime import datetime

import pandas as pd

from core.changelog import build_log, to_csv_bytes
from core.schema import LOG_COLUMNS, VALIDATED_COLUMNS


def test_only_valid_and_readable():
    changes = pd.DataFrame([
        ["g1", "Wand A", "Pset_WallCommon", "IsExternal", "Nein", True, True, ""],
        ["g2", "Wand B", "Pset_WallCommon", "FireRating", None, "EI45", False, "nicht in der Werteliste"],
    ], columns=VALIDATED_COLUMNS)
    log = build_log(changes, "David", now=datetime(2026, 10, 26, 18, 15))
    assert list(log.columns) == LOG_COLUMNS
    assert len(log) == 1
    assert log.iloc[0]["Neu"] == "Ja"
    assert log.iloc[0]["Zeitpunkt"] == "2026-10-26 18:15"
    csv = to_csv_bytes(log).decode("utf-8-sig")
    assert csv.splitlines()[0].startswith("Zeitpunkt;Benutzer;GlobalId")
