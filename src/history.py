"""
history.py — local NAV history store.

Purpose : IBKR's performance endpoint only reaches back about a year. This
          store merges every pull into one growing series on disk, so the
          3- and 5-year windows light up on their own as time passes.
Inputs  : Series fetched by ibkr_client.
Outputs : A merged, de-duplicated, chronologically sorted series.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

log = logging.getLogger(__name__)


class NavHistory:
    """A JSON-backed store of daily NAV and cumulative-return observations."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._rows: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.info("No history file yet; starting a fresh store at %s", self.path)
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._rows = payload.get("rows", {})
            log.info("Loaded %d historical observations.", len(self._rows))
        except (json.JSONDecodeError, OSError) as exc:
            backup = self.path.with_suffix(".corrupt.json")
            log.error("History file unreadable (%s); moved to %s and starting fresh.", exc, backup)
            try:
                self.path.rename(backup)
            except OSError:
                pass

    def merge(self, dates: Sequence[date], navs: Sequence[float], cps: Sequence[float]) -> None:
        """
        Fold a freshly fetched series into the store.

        Newly fetched values win on conflict — IBKR restates recent days as
        prices settle, and the newer figure is the corrected one.

        Cumulative returns are rebased to the store's own inception so that a
        series fetched years apart still chains correctly.
        """
        if not dates:
            return
        for d, nav, cp in zip(dates, navs, cps):
            self._rows[d.isoformat()] = {"nav": float(nav), "cps": float(cp)}
        self._rebase()

    def _rebase(self) -> None:
        """
        Rebuild one continuous cumulative-return series across merged pulls.

        Each pull's cps is relative to that pull's own start. Daily returns are
        invariant, so we recover them per contiguous run and chain them into a
        single series anchored at the earliest observation we hold.
        """
        keys = sorted(self._rows)
        if not keys:
            return
        chained, running = [], 1.0
        prev_cp = None
        for k in keys:
            cp = self._rows[k]["cps"]
            if prev_cp is None:
                daily = 0.0
            else:
                denom = 1.0 + prev_cp
                # A drop in cps signals the start of a differently-based pull;
                # treat that day as flat rather than inventing a return.
                daily = 0.0 if denom == 0 or cp < prev_cp - 0.5 else (1.0 + cp) / denom - 1.0
            running *= 1.0 + daily
            chained.append(running - 1.0)
            prev_cp = cp
        for k, c in zip(keys, chained):
            self._rows[k]["chained_cps"] = c

    def save(self) -> None:
        """Write the store back to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        payload = {"updated": datetime.now().isoformat(timespec="seconds"), "rows": self._rows}
        tmp.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        log.info("Saved %d observations to %s", len(self._rows), self.path)

    def series(self) -> tuple[list[date], list[float], list[float]]:
        """The full merged series as (dates, navs, cumulative returns)."""
        keys = sorted(self._rows)
        dates = [date.fromisoformat(k) for k in keys]
        navs = [self._rows[k]["nav"] for k in keys]
        cps = [self._rows[k].get("chained_cps", self._rows[k]["cps"]) for k in keys]
        return dates, navs, cps

    def __len__(self) -> int:
        return len(self._rows)
