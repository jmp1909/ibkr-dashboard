"""
fx.py — daily exchange-rate series with a local cache.

Purpose : Supply the FX series needed to split a CHF return into what the
          assets did and what the currency did.
Source  : frankfurter.app, which serves European Central Bank reference
          rates. Free, no API key, no registration.
Inputs  : A base and quote currency, and a date range.
Outputs : A date -> rate mapping, forward-filled onto the days you ask for.

Rates are quoted as "units of quote currency per one unit of base".
With base=USD and quote=CHF, a rising number means the dollar is
strengthening against the franc.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

log = logging.getLogger(__name__)

API_ROOT = "https://api.frankfurter.app"
REQUEST_TIMEOUT = 25


class FXUnavailable(RuntimeError):
    """Raised when no rates can be obtained from the network or the cache."""


class FXSeries:
    """
    A cached daily FX series.

    ECB publishes on business days only, so rates are forward-filled onto
    weekends and holidays: the rate stays at its last fix until the next one,
    which is what actually happens to a portfolio marked over a weekend.
    """

    def __init__(self, base: str, quote: str, cache_path: Path) -> None:
        self.base = base.upper()
        self.quote = quote.upper()
        self.cache_path = cache_path
        self._rates: dict[str, float] = {}
        self._fetched_on: str | None = None
        self._load_cache()

    # -- cache ---------------------------------------------------------
    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("pair") == f"{self.base}{self.quote}":
                self._rates = payload.get("rates", {})
                self._fetched_on = payload.get("fetched_on")
                log.info("Loaded %d cached %s/%s rates.", len(self._rates), self.base, self.quote)
            else:
                log.info("Cached FX pair differs from requested; ignoring cache.")
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("FX cache unreadable (%s); refetching.", exc)

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "pair": f"{self.base}{self.quote}",
                    "fetched_on": self._fetched_on,
                    "rates": self._rates,
                },
                indent=1,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.cache_path)

    # -- network -------------------------------------------------------
    def _fetch(self, start: date, end: date) -> dict[str, float]:
        url = f"{API_ROOT}/{start.isoformat()}..{end.isoformat()}?from={self.base}&to={self.quote}"
        log.info("Fetching %s/%s rates %s to %s", self.base, self.quote, start, end)
        req = urllib.request.Request(url, headers={"User-Agent": "fire-dashboard/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise FXUnavailable(f"Could not fetch rates: {exc}") from exc

        out: dict[str, float] = {}
        for day, node in (payload.get("rates") or {}).items():
            rate = node.get(self.quote)
            if rate:
                out[day] = float(rate)
        if not out:
            raise FXUnavailable("Rate service returned an empty series.")
        return out

    def ensure_range(self, start: date, end: date) -> None:
        """
        Make sure the cache covers the requested span, fetching only the gap.

        The tail is always refetched over a short overlap because the most
        recent day may not have been published when the cache was last written.
        """
        have = set(self._rates)
        newest = max(have) if have else None

        if newest is None:
            fetch_from = start
        elif date.fromisoformat(newest) >= end:
            log.debug("FX cache already covers the requested range.")
            return
        elif self._is_probably_current(date.fromisoformat(newest), end):
            # The last fix trails the requested end only because the ECB has
            # not published yet — over a weekend or holiday it never will for
            # those dates. Refetching on every run would be pointless traffic.
            log.debug("FX cache is current to the latest published fix.")
            return
        else:
            fetch_from = date.fromisoformat(newest) - timedelta(days=5)

        fetch_from = min(fetch_from, start)
        try:
            fresh = self._fetch(fetch_from, end)
        except FXUnavailable as exc:
            if self._rates:
                log.warning("%s - falling back to %d cached rates.", exc, len(self._rates))
                return
            raise
        self._rates.update(fresh)
        self._fetched_on = date.today().isoformat()
        self._save_cache()

    def _is_probably_current(self, newest: date, end: date) -> bool:
        """
        True when the cache is as fresh as the ECB is likely to be.

        Rates are published on business days only, so a cache whose last entry
        is a few days behind the requested end is not stale — it is simply
        waiting for the next fix. Only trust this if we already fetched today.
        """
        if self._fetched_on != date.today().isoformat():
            return False
        return (end - newest).days <= 4

    # -- access --------------------------------------------------------
    def aligned(self, days: Sequence[date]) -> list[float | None]:
        """
        Return one rate per requested day, forward-filled from the last fix.

        Days before the first available rate come back as None; callers should
        drop the corresponding observations rather than guess.
        """
        if not self._rates:
            raise FXUnavailable("No rates available.")
        keys = sorted(self._rates)
        out: list[float | None] = []
        idx = 0
        current: float | None = None
        for d in days:
            iso = d.isoformat()
            while idx < len(keys) and keys[idx] <= iso:
                current = self._rates[keys[idx]]
                idx += 1
            out.append(current)
        missing = sum(1 for v in out if v is None)
        if missing:
            log.warning("%d day(s) precede the first available rate and were left blank.", missing)
        return out

    def __len__(self) -> int:
        return len(self._rates)
