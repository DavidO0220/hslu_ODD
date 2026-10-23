"""Protokoll: Änderungen mit Zeitpunkt und Benutzer festhalten (Phase 3)."""

from datetime import datetime

import pandas as pd

from core.display import NO, YES
from core.schema import COL_NEW, COL_OLD, COL_TIMESTAMP, COL_USER, COL_VALID, LOG_COLUMNS


def _readable(value):
    if isinstance(value, bool):
        return YES if value else NO
    return "" if value is None else value


def build_log(changes: pd.DataFrame, user: str, now: datetime | None = None) -> pd.DataFrame:
    """Protokoll der gültigen Änderungen mit Zeitpunkt und Benutzer."""
    done = changes[changes[COL_VALID]] if COL_VALID in changes.columns else changes
    log = done.copy()
    log[COL_TIMESTAMP] = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    log[COL_USER] = user.strip() or "unbekannt"
    for col in (COL_OLD, COL_NEW):
        log[col] = [_readable(v) for v in log[col]]
    return log[LOG_COLUMNS].reset_index(drop=True)


def to_csv_bytes(log: pd.DataFrame) -> bytes:
    """CSV mit Semikolon und BOM, damit Excel in der Schweiz Umlaute korrekt zeigt."""
    return log.to_csv(index=False, sep=";").encode("utf-8-sig")
