"""
Module  : income.py
Purpose : Dividend income and a total-return benchmark, from raw gateway data.

Kept free of network calls so it can be tested against saved responses.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence


def parse_dividends(raw: dict[str, Any], tickers: dict[int, str]) -> list[dict[str, Any]]:
    """
    Dividend payments from a /pa/transactions response.

    The amounts are gross: on real data they match per-share payout x shares
    held to the cent, so withholding tax is not in them and is not reported by
    this endpoint at all.
    """
    out = []
    for t in (raw or {}).get("transactions", []):
        if "dividend" not in str(t.get("type", "")).lower():
            continue
        out.append({
            "date": datetime.strptime(str(t["rawDate"]), "%Y%m%d").date().isoformat(),
            "ticker": tickers.get(t.get("conid"), str(t.get("desc") or "?")),
            "amount": float(t.get("amt") or 0.0) * float(t.get("fxRate") or 1.0),
            "currency": t.get("cur") or "",
        })
    out.sort(key=lambda d: d["date"])
    return out


def payouts_from_history(raw: dict[str, Any]) -> list[tuple[date, float]]:
    """
    Per-share distributions from a /iserver/marketdata/history response.

    They arrive as chart annotations, "x/D <amount>/<minutes after startTime>",
    which land on the ex-dividend date.
    """
    start = datetime.strptime(raw["startTime"], "%Y%m%d-%H:%M:%S")
    out = []
    for part in str(raw.get("chartAnnotations") or "").split(";"):
        part = part.strip()
        if not part.startswith("x/D "):
            continue
        amount, minutes = part[4:].split("/")
        out.append(((start + timedelta(minutes=int(minutes))).date(), float(amount)))
    return sorted(out)


def closes(raw: dict[str, Any], keep: int = 140) -> list[list[float]]:
    """Daily closes from a history response as [epoch ms, close], newest last."""
    bars = sorted(raw.get("data") or [], key=lambda b: b["t"])
    return [[int(b["t"]), float(b["c"])] for b in bars][-keep:]


def total_return_index(raw: dict[str, Any]) -> list[tuple[date, float]]:
    """
    Daily total-return index (dividends reinvested at the ex-date close).

    Price alone understates a fund like VT by its whole yield, about 2% a year,
    so a price-only line would flatter anything compared with it.
    """
    bars = sorted(raw.get("data") or [], key=lambda b: b["t"])
    pays = dict(payouts_from_history(raw))
    out: list[tuple[date, float]] = []
    idx, prev = 1.0, None
    for b in bars:
        d = datetime.fromtimestamp(b["t"] / 1000, timezone.utc).date()
        close = float(b["c"])
        if prev is not None:
            idx *= (close + pays.get(d, 0.0)) / prev
        out.append((d, idx))
        prev = close
    return out


def align_cumulative(
    days: Sequence[date],
    index: list[tuple[date, float]],
    rates: Sequence[float | None] | None = None,
) -> list[float | None]:
    """
    Cumulative return on each portfolio day, rebased to the first one.

    The index is carried forward over days it has no bar for. With `rates`
    (asset currency -> display currency, one per day) the benchmark is
    converted the same way the portfolio is, so both are in one currency.
    """
    if not index or not days:
        return [None] * len(days)
    keys = [d for d, _ in index]
    vals = []
    for i, d in enumerate(days):
        j = bisect_right(keys, d) - 1
        v = index[j][1] if j >= 0 else None
        if v is not None and rates is not None:
            r = rates[i]
            v = v * r if r else None
        vals.append(v)
    base = next((v for v in vals if v), None)
    if base is None:
        return [None] * len(days)
    return [None if v is None else v / base - 1.0 for v in vals]
