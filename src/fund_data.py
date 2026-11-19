"""
Module  : fund_data.py
Purpose : What each fund holds by region, whether it tilts to small/value, and
          what it costs, fetched instead of typed into config.json.

Sources, all free and keyless:
  * Yahoo Finance, through the open-source yfinance package: every US-listed
    ETF's expense ratio, Morningstar category ("Small Value", "Foreign Large
    Value", "Diversified Emerging Mkts", ...) and name. A single-region
    fund's category says which region it holds.
  * Vanguard's public fund data (what its website uses): the country split of
    Vanguard funds.
  * iShares' published holdings files: every holding with its country, for
    iShares funds.

Country lists are cached as fetched and grouped into US / other developed /
emerging when the page is built, so switching between MSCI's and FTSE's
definition of "emerging" needs no new download. None of these is an official,
guaranteed API: results are cached, a failed fetch keeps the last good data,
and anything set under "lookthrough" in config.json wins.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import requests

log = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (portfolio dashboard)"}
VANGUARD_API = "https://investor.vanguard.com/vmf/api/{key}/{what}"
VANGUARD_PAGES = (
    "https://investor.vanguard.com/investment-products/etfs/profile/{t}",
    "https://investor.vanguard.com/investment-products/mutual-funds/profile/{t}",
)
ISHARES_LIST = ("https://www.ishares.com/us/product-screener/product-screener-v3.1.jsn?dcrPath=/templatedata/"
                "config/product-screener-v3/data/en/us-ishares/ishares-product-screener-backend-config"
                "&siteEntryPassthrough=true")
ISHARES_HOLDINGS = "https://www.ishares.com{page}/latest-holdings.csv"

# MSCI's emerging markets, plus frontier markets (counted as emerging here).
# FTSE's list is the same without Korea and Poland, which FTSE calls developed.
EMERGING_MSCI = {
    "brazil", "chile", "china", "colombia", "czech republic", "egypt", "greece", "hungary",
    "india", "indonesia", "korea", "kuwait", "malaysia", "mexico", "peru", "philippines",
    "poland", "qatar", "saudi arabia", "south africa", "taiwan", "thailand", "turkey",
    "united arab emirates", "argentina", "pakistan", "iceland", "romania", "vietnam",
    "bangladesh", "nigeria", "kenya", "morocco", "russia",
}
EMERGING = {"msci": EMERGING_MSCI, "ftse": EMERGING_MSCI - {"korea", "poland"}}
_ALIASES = {"korea (south)": "korea", "south korea": "korea", "republic of korea": "korea",
            "turkiye": "turkey", "uae": "united arab emirates", "czechia": "czech republic",
            "usa": "united states", "us": "united states", "u.s.": "united states"}

_US_STYLE = re.compile(r"^(large|mid-cap|mid|small)\s*(value|blend|growth)$", re.I)
_EM_CATS = {"china region", "india equity", "latin america stock"}
_DEV_CATS = {"japan stock", "europe stock", "diversified pacific/asia", "miscellaneous region"}


def country_key(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name or "")).strip().lower()
    return _ALIASES.get(n, n)


def split_from_countries(countries: dict[str, float], scheme: str = "msci") -> dict[str, float] | None:
    """Group a {country: weight} list into US / other developed / emerging."""
    em = EMERGING.get(scheme, EMERGING_MSCI)
    out = {"us": 0.0, "dev": 0.0, "em": 0.0}
    for name, w in countries.items():
        k = country_key(name)
        if not k or k in ("-", "other", "cash"):
            continue
        out["us" if k == "united states" else "em" if k in em else "dev"] += float(w)
    total = sum(out.values())
    if total <= 0:
        return None
    return {k: round(v / total, 4) for k, v in out.items()}


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


# ---------------------------------------------------------------- sources
def from_yahoo(ticker: str) -> dict[str, Any]:
    import yfinance as yf  # optional dependency, imported only when used

    t = yf.Ticker(ticker)
    f = t.funds_data
    overview = f.fund_overview or {}
    out: dict[str, Any] = {"category": overview.get("categoryName"), "family": overview.get("family")}
    try:
        out["name"] = t.info.get("longName")
    except Exception:  # noqa: BLE001
        pass
    try:
        ter = float(f.fund_operations.loc["Annual Report Expense Ratio"].iloc[0])
        if ter == ter and 0 < ter < 0.05:  # not NaN, and a plausible ratio
            out["ter"] = round(ter, 5)
    except Exception:  # noqa: BLE001
        pass
    return out


def _vanguard_json(session: requests.Session, key: str, what: str) -> dict[str, Any] | None:
    r = session.get(VANGUARD_API.format(key=key, what=what), headers=UA, timeout=15)
    if not r.ok or not r.headers.get("content-type", "").startswith("application/json"):
        return None
    d = r.json()
    # Vanguard's own back end sometimes fails for a ticker and says so in a
    # 200 response; the same fund usually still answers by its fund number.
    return None if not isinstance(d, dict) or "response" in d else d


def _vanguard_fund_id(session: requests.Session, ticker: str) -> str | None:
    for url in VANGUARD_PAGES:
        try:
            r = session.get(url.format(t=ticker.lower()), headers=UA, timeout=20)
        except requests.RequestException:
            continue
        m = r.ok and re.search(r'fundId(?:&#34;|")\s*:\s*(?:&#34;|")(\d+)', r.text)
        if m:
            return m.group(1)
    return None


def from_vanguard(ticker: str, session: requests.Session) -> dict[str, Any]:
    out: dict[str, Any] = {}
    key = ticker
    div = _vanguard_json(session, key, "diversification")
    if div is None:
        fid = _vanguard_fund_id(session, ticker)
        if fid:
            key = fid
            div = _vanguard_json(session, key, "diversification")
    items = ((div or {}).get("country") or {}).get("item") or []
    countries: dict[str, float] = {}
    for it in items:
        try:
            countries[str(it.get("name", "")).strip()] = float(it.get("currYrPct"))
        except (TypeError, ValueError):
            continue
    if sum(countries.values()) >= 50:  # too little to trust otherwise
        out["countries"] = countries
    exp = _vanguard_json(session, key, "expense")
    try:
        out["ter"] = round(float(exp["expenseRatio"]) / 100, 5)  # given in percent
    except (TypeError, KeyError, ValueError):
        pass
    return out


class IShares:
    """iShares' product list is one large download, so it's fetched once per run."""

    def __init__(self, session: requests.Session) -> None:
        self.session = session
        self._pages: dict[str, str] | None = None

    def page(self, ticker: str) -> str | None:
        if self._pages is None:
            self._pages = {}
            r = self.session.get(ISHARES_LIST, headers=UA, timeout=60)
            r.raise_for_status()
            for p in r.json().values():
                if isinstance(p, dict) and p.get("localExchangeTicker") and p.get("productPageUrl"):
                    self._pages[str(p["localExchangeTicker"]).upper()] = p["productPageUrl"]
        return self._pages.get(ticker.upper())

    def countries(self, ticker: str) -> dict[str, float] | None:
        page = self.page(ticker)
        if not page:
            return None
        r = self.session.get(ISHARES_HOLDINGS.format(page=page), headers=UA, timeout=60)
        r.raise_for_status()
        text = r.text
        start = text.find("Ticker,")
        if start < 0:
            return None
        out: dict[str, float] = {}
        for row in csv.DictReader(io.StringIO(text[start:])):
            if (row.get("Asset Class") or "").strip() != "Equity":
                continue
            try:
                w = float((row.get("Weight (%)") or "").replace(",", ""))
            except ValueError:
                continue
            loc = (row.get("Location") or "").strip()
            out[loc] = out.get(loc, 0.0) + w
        return out if sum(out.values()) >= 50 else None


def fetch_one(ticker: str, session: requests.Session, ishares: IShares) -> dict[str, Any] | None:
    """Everything we can learn about one fund, or None if nothing came back."""
    y: dict[str, Any] = {}
    try:
        y = from_yahoo(ticker)
    except ImportError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("Yahoo fund data for %s unavailable: %s", ticker, exc)
    family = str(y.get("family") or "").lower()
    cat = y.get("category")
    rec: dict[str, Any] = {"category": cat, "family": y.get("family"), "name": y.get("name")}

    v: dict[str, Any] = {}
    if "vanguard" in family or not y:
        try:
            v = from_vanguard(ticker, session)
        except Exception as exc:  # noqa: BLE001
            log.warning("Vanguard fund data for %s unavailable: %s", ticker, exc)
    if v.get("countries"):
        rec["countries"], rec["split_source"] = v["countries"], "Vanguard"
    elif "ishares" in family or "blackrock" in family:
        try:
            c = ishares.countries(ticker)
            if c:
                rec["countries"], rec["split_source"] = c, "iShares holdings"
        except Exception as exc:  # noqa: BLE001
            log.warning("iShares holdings for %s unavailable: %s", ticker, exc)
    if "countries" not in rec:
        split = split_from_category(cat)
        if split:
            rec.update(split)
            # Morningstar's "Foreign" categories may still hold some emerging markets.
            rec["split_source"] = ("fund category, approximate"
                                   if cat and cat.lower().startswith("foreign") and "value" not in cat.lower()
                                   else "fund category")
    if not y and not v and "countries" not in rec:
        return None
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


def _rank(rec: dict[str, Any]) -> int:
    return 2 if rec.get("countries") else 1 if "us" in rec else 0


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
        ishares = IShares(session)
        for tk in stale:
            try:
                rec = fetch_one(tk, session, ishares)
            except ImportError:
                log.warning("Fund data needs the yfinance package: pip install -r requirements.txt")
                break
            if not rec:
                continue
            old = cache.get(tk) or {}
            # A source that failed this time must not swap a real split for a guess.
            if _rank(old) > _rank(rec):
                for k in ("countries", "us", "dev", "em", "split_source"):
                    rec.pop(k, None)
                    if k in old:
                        rec[k] = old[k]
            rec["fetched"] = now.isoformat(timespec="seconds")
            cache[tk] = rec
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not save fund data cache: %s", exc)
    return cache


def merge(fetched: dict[str, dict[str, Any]], overrides: dict[str, Any],
          scheme: str = "msci") -> dict[str, dict[str, Any]]:
    """
    One look-through entry per fund: fetched data, with config.json on top.

    A config entry with its own us/dev/em replaces the fetched split as a
    whole (a partial split would no longer add up); other keys override one
    by one. `source` records where the split came from, for the page.
    """
    out: dict[str, dict[str, Any]] = {}
    for tk, rec in fetched.items():
        e = {k: rec[k] for k in ("us", "dev", "em", "tilt", "ter", "role") if k in rec}
        if rec.get("countries"):
            split = split_from_countries(rec["countries"], scheme)
            if split:
                e.update(split)
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
