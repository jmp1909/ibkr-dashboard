"""
Module  : fund_data.py
Purpose : What each fund holds by region, whether it tilts to small/value, and
          what it costs, fetched instead of typed into config.json.

Sources, both free and keyless:
  * Yahoo Finance, through the open-source yfinance package: every US-listed
    ETF's expense ratio and Morningstar category ("Small Value", "Foreign
    Large Value", "Diversified Emerging Mkts", ...). A single-region fund's
    category says which region it holds.
  * Vanguard's public fund-data service (the one its website uses): the
    country-by-country split of Vanguard funds, which a category like
    "Global Large-Stock Blend" can't give.

Neither is an official, guaranteed API, so results are cached and a failed
fetch keeps the last good data. Anything set under "lookthrough" in
config.json wins over what is fetched.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import requests

log = logging.getLogger(__name__)

VANGUARD = "https://investor.vanguard.com/vmf/api/{ticker}/{what}"
UA = {"User-Agent": "Mozilla/5.0 (portfolio dashboard)"}

# FTSE's emerging list, since Vanguard's global funds follow FTSE indexes
# (FTSE counts Korea and Poland as developed, unlike MSCI).
EMERGING = {
    "argentina", "brazil", "chile", "china", "colombia", "czech republic", "egypt", "greece",
    "hungary", "iceland", "india", "indonesia", "kuwait", "malaysia", "mexico", "pakistan",
    "peru", "philippines", "qatar", "romania", "russia", "saudi arabia", "south africa",
    "taiwan", "thailand", "turkey", "turkiye", "united arab emirates", "uae", "vietnam",
    "bangladesh", "nigeria", "kenya", "morocco",
}
_US_STYLE = re.compile(r"^(large|mid-cap|mid|small)\s*(value|blend|growth)$", re.I)
_EM_CATS = {"china region", "india equity", "latin america stock"}
_DEV_CATS = {"japan stock", "europe stock", "diversified pacific/asia", "miscellaneous region"}


def split_from_category(category: str | None) -> dict[str, float] | None:
    """Regional split implied by a Morningstar category, or None if it doesn't say."""
    c = (category or "").strip().lower()
    if not c:
        return None
    if "emerging" in c or c in _EM_CATS:
        return {"us": 0.0, "dev": 0.0, "em": 1.0}
    if c.startswith("foreign") or c in _DEV_CATS:
        return {"us": 0.0, "dev": 1.0, "em": 0.0}
    if _US_STYLE.match(c):
        return {"us": 1.0, "dev": 0.0, "em": 0.0}
    return None  # global, sector or other funds: the category alone can't tell


def tilt_from_category(category: str | None, name: str | None = None) -> int | None:
    """1 for small-cap or value funds, judged by category and fund name."""
    c = f"{category or ''} {name or ''}".lower()
    if not c.strip():
        return None
    return 1 if ("value" in c or "small" in c) else 0


def split_from_countries(items: list[dict[str, Any]]) -> dict[str, float] | None:
    """Group Vanguard's country list into US / other developed / emerging."""
    out = {"us": 0.0, "dev": 0.0, "em": 0.0}
    total = 0.0
    for it in items:
        try:
            pct = float(it.get("currYrPct"))
        except (TypeError, ValueError):
            continue
        name = str(it.get("name", "")).strip().lower()
        key = "us" if name in ("united states", "usa", "us") else "em" if name in EMERGING else "dev"
        out[key] += pct
        total += pct
    if total < 50:  # too little to trust
        return None
    return {k: round(v / total, 4) for k, v in out.items()}


def from_yahoo(ticker: str) -> dict[str, Any]:
    import yfinance as yf  # optional dependency, imported only when used

    f = yf.Ticker(ticker).funds_data
    overview = f.fund_overview or {}
    out: dict[str, Any] = {"category": overview.get("categoryName"), "family": overview.get("family")}
    try:
        out["name"] = yf.Ticker(ticker).info.get("longName")
    except Exception:  # noqa: BLE001
        pass
    ops = f.fund_operations
    try:
        ter = float(ops.loc["Annual Report Expense Ratio"].iloc[0])
        if ter == ter and 0 < ter < 0.05:  # not NaN, and a plausible ratio
            out["ter"] = round(ter, 5)
    except Exception:  # noqa: BLE001
        pass
    return out


def from_vanguard(ticker: str, session: requests.Session) -> dict[str, Any]:
    out: dict[str, Any] = {}
    r = session.get(VANGUARD.format(ticker=ticker, what="diversification"), headers=UA, timeout=15)
    if r.ok and r.headers.get("content-type", "").startswith("application/json"):
        split = split_from_countries(((r.json().get("country") or {}).get("item")) or [])
        if split:
            out["split"] = split
    r = session.get(VANGUARD.format(ticker=ticker, what="expense"), headers=UA, timeout=15)
    if r.ok and r.headers.get("content-type", "").startswith("application/json"):
        try:
            out["ter"] = round(float(r.json()["expenseRatio"]) / 100, 5)  # given in percent
        except (KeyError, TypeError, ValueError):
            pass
    return out


def fetch_one(ticker: str, session: requests.Session) -> dict[str, Any] | None:
    """Everything we can learn about one fund, or None if nothing came back."""
    y: dict[str, Any] = {}
    try:
        y = from_yahoo(ticker)
    except ImportError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("Yahoo fund data for %s unavailable: %s", ticker, exc)
    v: dict[str, Any] = {}
    if "vanguard" in str(y.get("family") or "").lower() or not y:
        try:
            v = from_vanguard(ticker, session)
        except Exception as exc:  # noqa: BLE001
            log.warning("Vanguard fund data for %s unavailable: %s", ticker, exc)
    if not y and not v:
        return None
    cat = y.get("category")
    split, src = v.get("split"), "Vanguard"
    if not split:
        split = split_from_category(cat)
        # "Foreign" categories may still hold some emerging markets.
        src = "fund category, approximate" if cat and cat.lower().startswith("foreign") else "fund category"
    rec: dict[str, Any] = {"category": cat, "family": y.get("family"), "name": y.get("name")}
    if split:
        rec.update(split)
        rec["split_source"] = src
    t = tilt_from_category(cat, y.get("name"))
    if t is not None:
        rec["tilt"] = t
    ter = v.get("ter") if v.get("ter") is not None else y.get("ter")
    if ter is not None:
        rec["ter"] = ter
        rec["ter_source"] = "Vanguard" if v.get("ter") is not None else "Yahoo"
    if cat:
        rec["role"] = cat
    return rec


def load(tickers: Iterable[str], cache_path: Path, max_age_days: int = 7) -> dict[str, dict[str, Any]]:
    """
    Fund data for `tickers`, from the cache when it is fresh enough.

    Never raises: a fund that can't be fetched keeps whatever the cache had,
    and the dashboard falls back to config.json for anything still missing.
    """
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    now = datetime.now()
    stale = []
    for tk in dict.fromkeys(t.strip().upper() for t in tickers if t and t.strip()):
        rec = cache.get(tk)
        try:
            fresh = rec and now - datetime.fromisoformat(rec["fetched"]) < timedelta(days=max_age_days)
        except (KeyError, TypeError, ValueError):
            fresh = False
        if not fresh:
            stale.append(tk)
    if stale:
        session = requests.Session()
        for tk in stale:
            try:
                rec = fetch_one(tk, session)
            except ImportError:
                log.warning("Fund data needs the yfinance package: pip install -r requirements.txt")
                break
            if rec:
                old = cache.get(tk) or {}
                # A failed Vanguard call must not swap a real split for an estimate.
                if old.get("split_source") == "Vanguard" and rec.get("split_source") != "Vanguard":
                    rec.update({k: old[k] for k in ("us", "dev", "em", "split_source") if k in old})
                rec["fetched"] = now.isoformat(timespec="seconds")
                cache[tk] = rec
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not save fund data cache: %s", exc)
    return cache


def merge(fetched: dict[str, dict[str, Any]], overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    One look-through entry per fund: fetched data, with config.json on top.

    A config entry with its own us/dev/em replaces the fetched split as a
    whole (a partial split would no longer add up); other keys override one
    by one. `source` records where the split came from, for the page.
    """
    out: dict[str, dict[str, Any]] = {}
    for tk, rec in fetched.items():
        e = {k: rec[k] for k in ("us", "dev", "em", "tilt", "ter", "role") if k in rec}
        if "us" in e:
            e["source"] = rec.get("split_source", "fetched")
        if "ter" in e:
            e["ter_source"] = rec.get("ter_source", "fetched")
        out[tk] = e
    for tk, ov in (overrides or {}).items():
        if not isinstance(ov, dict):
            continue
        e = out.setdefault(tk, {})
        if any(k in ov for k in ("us", "dev", "em")):
            for k in ("us", "dev", "em"):
                e[k] = float(ov.get(k, 0.0))
            e["source"] = "config.json"
        for k in ("tilt", "role"):
            if k in ov:
                e[k] = ov[k]
        if "ter" in ov:
            e["ter"] = float(ov["ter"])
            e["ter_source"] = "config.json"
    return out
