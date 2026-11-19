"""
main.py — build the portfolio and FIRE dashboard.

Purpose : Pull the account from IBKR, compute money-weighted returns, and
          write a self-contained interactive HTML dashboard.
Inputs  : config.json (edit this), a running Client Portal Gateway.
Outputs : dashboard.html, and an ever-growing data/nav_history.json.

Usage   : python src/main.py            pull live from IBKR
          python src/main.py --demo     build from bundled sample data
          python src/main.py --no-open  skip launching the browser
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import webbrowser
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from analytics import (  # noqa: E402
    CashFlow,
    all_currency_splits,
    all_window_returns,
    reconstruct_flows,
)
from history import NavHistory  # noqa: E402
from render import render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

log = logging.getLogger("dashboard")


# ----------------------------------------------------------------------
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read config.json, failing loudly with a useful message."""
    if not path.exists():
        raise SystemExit(
            f"Config not found at {path}.\n"
            f"Copy config.example.json to config.json and edit it - it holds your birth date, "
            f"savings phases, target and allocation, and nothing works without it."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config.json is not valid JSON: {exc}") from exc


def age_on(birth: date, when: date) -> float:
    """Age in fractional years."""
    return (when - birth).days / 365.25


def month_index(ym: str) -> int:
    """'YYYY-MM' as a single integer month count, so months can be compared and subtracted."""
    y, m = (int(x) for x in ym.split("-"))
    return y * 12 + (m - 1)


def _ym(value: Any, where: str) -> str:
    """Validate a 'YYYY-MM' string from config, failing with the offending key named."""
    ok = isinstance(value, str) and len(value) == 7 and value[4] == "-"
    if ok:
        try:
            y, m = int(value[:4]), int(value[5:])
            ok = 1900 <= y <= 2200 and 1 <= m <= 12
        except ValueError:
            ok = False
    if not ok:
        raise SystemExit(f"config.json: {where} must look like 'YYYY-MM', got {value!r}.")
    return value


# Goal keys the dashboard lets you edit; everything else in "goal" is carried
# through untouched so an export from the page can't drop it.
_EDITABLE_GOAL = (
    "target", "real_return", "withdrawal_rate", "coast_full_age",
    "volatility", "target_mode", "annual_spending",
)


def _num(v: Any, where: str, lo: float | None = None, hi: float | None = None) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"config.json: {where} must be a number, got {v!r}.") from exc
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise SystemExit(f"config.json: {where} = {x} is outside {lo}..{hi}.")
    return x


def build_scenarios(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Optional named scenarios, each stored as only what it changes from the main
    plan. The dashboard applies them on top of the plan and shows them next to
    it; the format is what its "Copy as config" produces.
    """
    out = []
    for i, sc in enumerate(cfg.get("scenarios") or []):
        if not isinstance(sc, dict) or not str(sc.get("name") or "").strip():
            raise SystemExit(f"config.json: scenarios[{i}] needs a name.")
        ov = sc.get("overrides") or {}
        if not isinstance(ov, dict):
            raise SystemExit(f"config.json: scenarios[{i}].overrides must be an object.")
        out.append({"name": str(sc["name"]).strip()[:40], "overrides": ov})
    return out


def build_pensions(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Optional Swiss pension pots. Off unless config says otherwise.

    Pillar 2 and 3a are pots that grow on their own and land in the portfolio at
    their unlock age; AHV is a yearly income from its start age that reduces what
    the portfolio has to pay out. All amounts are real, in today's money.
    """
    raw = cfg.get("pensions") or {}
    def pot(key: str, unlock: float) -> dict[str, float]:
        b = raw.get(key) or {}
        w = f"pensions.{key}"
        return {
            "balance": _num(b.get("balance", 0), w + ".balance", 0),
            "yearly_contribution": _num(b.get("yearly_contribution", 0), w + ".yearly_contribution", 0),
            "real_return": _num(b.get("real_return", 0.01), w + ".real_return", -0.05, 0.15),
            "unlock_age": _num(b.get("unlock_age", unlock), w + ".unlock_age", 40, 75),
        }
    a = raw.get("ahv") or {}
    return {
        "enabled": bool(raw.get("enabled", False)),
        "pillar2": pot("pillar2", 65),
        "pillar3a": pot("pillar3a", 60),
        "ahv": {
            "yearly_amount": _num(a.get("yearly_amount", 0), "pensions.ahv.yearly_amount", 0),
            "start_age": _num(a.get("start_age", 65), "pensions.ahv.start_age", 58, 75),
        },
    }


def build_plan(cfg: dict[str, Any], today: date) -> dict[str, Any]:
    """
    Pass the life plan to the dashboard with real calendar dates.

    Every phase is passed through, including ones that have already ended: the
    page ignores those for the projection but keeps them, so a plan exported
    from the browser never silently loses history. Dates stay as 'YYYY-MM' -
    the page works out where "now" falls from `anchor`, the month of the latest
    data, which is what keeps the projection starting at the present.
    """
    goal = cfg["goal"]
    anchor = f"{today.year:04d}-{today.month:02d}"
    now = month_index(anchor)

    phases = []
    for i, p in enumerate(cfg.get("phases", [])):
        where = f"phases[{i}]"
        start = _ym(p.get("start"), f"{where}.start")
        end = p.get("end")
        end = None if end in (None, "") else _ym(end, f"{where}.end")
        if end is not None and month_index(end) < month_index(start):
            raise SystemExit(f"config.json: {where} ends before it starts ({start} to {end}).")
        mode = p.get("saving_mode", "rate")
        if mode not in ("rate", "fixed"):
            raise SystemExit(f"config.json: {where}.saving_mode must be 'rate' or 'fixed', got {mode!r}.")
        phases.append(
            {
                "id": str(p.get("id") or f"phase{i + 1}"),
                "label": str(p.get("label") or f"Phase {i + 1}"),
                "start": start,
                "end": end,
                "monthly_income": float(p.get("monthly_income", 0.0)),
                "saving_mode": mode,
                "savings_rate": float(p.get("savings_rate", 0.0)),
                "monthly_saving": float(p.get("monthly_saving", 0.0)),
                "income_growth": float(p.get("income_growth", 0.0)),
            }
        )
    phases.sort(key=lambda p: month_index(p["start"]))

    # Each month belongs to at most one phase. Overlaps used to be resolved
    # silently (the later entry won); now they're an explicit error, because the
    # page's timeline can't represent them and a silent winner hides a typo.
    for a, b in zip(phases, phases[1:]):
        if a["end"] is None or month_index(a["end"]) >= month_index(b["start"]):
            raise SystemExit(
                f"config.json: phases '{a['label']}' and '{b['label']}' overlap. "
                "Each month can belong to only one phase - end one before the next starts."
            )
    if not any(p["end"] is None or month_index(p["end"]) >= now for p in phases):
        raise SystemExit("No current or future phases in config.json - nothing to project.")

    events = []
    for i, e in enumerate(cfg.get("events", [])):
        try:
            amount = float(e["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"config.json: events[{i}].amount must be a number.") from exc
        events.append(
            {
                "id": str(e.get("id") or f"event{i + 1}"),
                "label": str(e.get("label") or "Event"),
                "date": _ym(e.get("date"), f"events[{i}].date"),
                "amount": amount,
            }
        )
    events.sort(key=lambda e: month_index(e["date"]))

    mode = goal.get("target_mode", "amount")
    if mode not in ("amount", "spending"):
        raise SystemExit(f"config.json: goal.target_mode must be 'amount' or 'spending', got {mode!r}.")
    wr = _num(goal["withdrawal_rate"], "goal.withdrawal_rate", 0.005, 0.2)
    spending = goal.get("annual_spending")
    spending = float(goal["target"]) * wr if spending is None else _num(spending, "goal.annual_spending", 0)
    target = spending / wr if mode == "spending" else _num(goal["target"], "goal.target", 1)

    return {
        "anchor": anchor,
        "target": target,
        "target_mode": mode,
        "annual_spending": spending,
        "volatility": _num(goal.get("volatility", 0.16), "goal.volatility", 0, 0.6),
        "plan_to_age": _num(goal.get("plan_to_age", 95), "goal.plan_to_age", 60, 110),
        "pensions": build_pensions(cfg),
        "scenarios": build_scenarios(cfg),
        "real_return": float(goal["real_return"]),
        "withdrawal_rate": wr,
        "coast_full_age": float(goal["coast_full_age"]),
        # Optional. Absent means the dashboard generates a ladder scaled to the target.
        "milestones": [float(m) for m in goal.get("milestones", [])],
        "goal_extra": {k: v for k, v in goal.items() if k not in _EDITABLE_GOAL},
        "phases": phases,
        "events": events,
    }


def monthly_saving(p: dict[str, Any]) -> float:
    """What a phase puts away per month at its starting income."""
    if p.get("saving_mode") == "fixed":
        return p["monthly_saving"]
    return p["monthly_income"] * p["savings_rate"]


def current_phase(plan: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """The phase covering this month, or the next one; and whether it is still to come."""
    now = month_index(plan["anchor"])
    live = [p for p in plan["phases"] if p["end"] is None or month_index(p["end"]) >= now]
    first = live[0]
    return first, month_index(first["start"]) > now


def compute_exposure(positions: list[dict[str, Any]], lookthrough: dict[str, Any]) -> dict[str, float]:
    """Weight each fund's published regional split by its share of the portfolio."""
    total = sum(p["market_value"] for p in positions) or 1.0
    out = {"us": 0.0, "dev": 0.0, "em": 0.0, "tilt": 0.0}
    unmapped = []
    for p in positions:
        lt = lookthrough.get(p["ticker"])
        w = p["market_value"] / total
        if not lt:
            unmapped.append(p["ticker"])
            out["us"] += w  # assume domestic rather than silently dropping it
            continue
        out["us"] += w * lt.get("us", 0.0)
        out["dev"] += w * lt.get("dev", 0.0)
        out["em"] += w * lt.get("em", 0.0)
        out["tilt"] += w * lt.get("tilt", 0.0)
    if unmapped:
        log.warning("No look-through for %s - add them to config.json.", ", ".join(unmapped))
    return out


def compute_basket(positions: list[dict[str, Any]], basket_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Weight each fund's internal currency mix by its share of the portfolio.

    This answers a different question from the return decomposition: not "what
    moved my return", but "which currencies is my wealth actually denominated
    in". USD is merely the reporting currency of these funds — VT holds euros
    and yen regardless of what it is priced in.
    """
    total = sum(p["market_value"] for p in positions) or 1.0
    agg: dict[str, float] = {}
    for p in positions:
        mix = basket_cfg.get(p["ticker"])
        w = p["market_value"] / total
        if not mix:
            agg["Unclassified"] = agg.get("Unclassified", 0.0) + w
            continue
        for ccy, share in mix.items():
            agg[ccy] = agg.get(ccy, 0.0) + w * float(share)
    return [{"ccy": k, "weight": v} for k, v in sorted(agg.items(), key=lambda kv: -kv[1])]


def build_fx_section(
    cfg: dict[str, Any],
    root: Path,
    dates: list[date],
    cps: list[float],
    positions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Assemble the currency block, or None if it is disabled or unavailable.

    A failure here must never take the rest of the dashboard down — the FX
    service is a third party and the return figures do not depend on it.
    """
    fx_cfg = cfg.get("currency", {})
    if not fx_cfg.get("enabled", False):
        return None

    from fx import FXSeries, FXUnavailable

    display = cfg["account"].get("display_currency", "CHF")
    asset_ccy = fx_cfg.get("asset_currency", "USD")
    if asset_ccy == display:
        log.info("Asset and display currency match; skipping decomposition.")
        return None

    try:
        series = FXSeries(asset_ccy, display, root / fx_cfg.get("cache_path", "data/fx_history.json"))
        series.ensure_range(dates[0], dates[-1])
        rates = series.aligned(dates)
    except FXUnavailable as exc:
        log.warning("Currency decomposition unavailable: %s", exc)
        return None

    splits = all_currency_splits(dates, cps, rates)
    usable = [r for r in rates if r is not None]
    return {
        "pair": f"{asset_ccy}/{display}",
        "asset_currency": asset_ccy,
        "display_currency": display,
        "rate_first": usable[0] if usable else None,
        "rate_last": usable[-1] if usable else None,
        "rate_series": [
            {"t": int(datetime.combine(d, datetime.min.time()).timestamp() * 1000), "r": r}
            for d, r in zip(dates, rates) if r is not None
        ],
        "splits": [
            {
                "label": s.label,
                "available": s.available,
                "note": s.note,
                "total": s.total,
                "asset": s.asset,
                "currency": s.currency,
                "interaction": s.interaction,
                "currency_share": s.currency_share,
                "days": s.days,
            }
            for s in splits
        ],
        "basket": compute_basket(positions, cfg.get("currency_basket", {})),
    }


def build_lede(net: float, target: float, ccy: str, plan: dict[str, Any], sep: str = ",") -> str:
    """One honest paragraph under the headline."""
    def amount(v: float) -> str:
        # Format each number individually. A blanket replace across the whole
        # sentence also rewrites grammatical commas ("target, currently" ->
        # "target' currently"), which is how this read before.
        return f"{ccy} {v:,.0f}".replace(",", sep)

    first, upcoming = current_phase(plan)
    saving = monthly_saving(first)
    # The first remaining phase may not have started yet: don't claim someone is
    # saving that amount "right now" when it begins next year.
    if upcoming:
        opening = (
            f"Saving starts at {amount(saving)} a month in the "
            f"{first['label'].lower()} phase, against a {amount(target)} target"
        )
    else:
        opening = f"Saving {amount(saving)} a month right now against a {amount(target)} target"

    return (
        f"{opening}, currently {net / target * 100:.1f}% of the way there. Returns below are "
        "money-weighted. Every input in the projection is a slider - it is only as good as "
        "what you put in it."
    )


# ----------------------------------------------------------------------
def demo_snapshot() -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    """Bundled sample data so the dashboard can be built without the gateway."""
    from demo_data import DEMO_EXTRAS, DEMO_POSITIONS, DEMO_SERIES, DEMO_SUMMARY

    return DEMO_POSITIONS, DEMO_SUMMARY, dict(DEMO_SERIES, extras=DEMO_EXTRAS)


def live_snapshot(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    """Pull positions, summary and the performance series from the gateway."""
    from ibkr_client import IBKRClient

    acct_cfg = cfg["account"]
    client = IBKRClient(acct_cfg.get("gateway_url") or "https://localhost:5000/v1/api")
    if acct_cfg.get("account_id"):
        client.use_account(acct_cfg["account_id"])
    client.ensure_authenticated()

    positions = [
        {
            "ticker": p.ticker,
            "name": p.name,
            "quantity": p.quantity,
            "price": p.price,
            "market_value": p.market_value,
            "currency": p.currency,
            "unrealised_pnl": p.unrealised_pnl,
            "cost_basis": p.cost_basis,
        }
        for p in client.positions()
        if abs(p.quantity) > 1e-9
    ]
    summary, performance = client.summary(), client.performance()
    performance["extras"] = fetch_income(client, cfg, summary.get("currency") or "USD")
    return positions, summary, performance


def fetch_income(client: Any, cfg: dict[str, Any], base_ccy: str) -> dict[str, Any]:
    """
    Dividends and the benchmark's total-return index. Best effort: the core
    dashboard never depends on these, so a failure is logged and skipped.
    """
    import income

    extras: dict[str, Any] = {}
    ticker, choices = benchmark_choices(cfg)
    try:
        tickers = client.conids()
        raw = client.transactions(list(tickers), "USD")
        extras["dividends"] = income.parse_dividends(raw, tickers)
    except Exception as exc:  # noqa: BLE001
        log.warning("Dividend history unavailable: %s", exc)
        tickers = {}
    # Recent daily prices per fund, for the small trend lines next to each holding.
    history: dict[str, list[list[float]]] = {}
    for conid, tk in tickers.items():
        try:
            history[tk] = income.closes(client.price_history(conid, period="6m"))
            time.sleep(0.25)  # the gateway rate-limits aggressively
        except Exception as exc:  # noqa: BLE001
            log.warning("Price history for %s unavailable: %s", tk, exc)
    if history:
        extras["fund_history"] = history
    # Every candidate benchmark is fetched, so the dashboard can switch
    # between them without another refresh.
    indexes: dict[str, Any] = {}
    for tk in choices:
        try:
            conid = next((c for c, t in tickers.items() if t == tk), None) or client.search_conid(tk)
            if conid is None:
                raise ValueError(f"no contract found for {tk}")
            indexes[tk] = income.total_return_index(client.price_history(conid))
            time.sleep(0.25)
        except Exception as exc:  # noqa: BLE001
            log.warning("Benchmark %s unavailable: %s", tk, exc)
    if indexes:
        extras["benchmark_indexes"] = indexes
    if ticker in indexes:
        extras["benchmark_index"] = indexes[ticker]
        extras["benchmark_ticker"] = ticker
    return extras


def benchmark_choices(cfg: dict[str, Any]) -> tuple[str | None, list[str]]:
    """The default benchmark and every ticker the dashboard may switch to."""
    b = cfg.get("benchmark") or {}
    ticker = b.get("ticker", "VT")
    out: list[str] = []
    for tk in ([ticker] if ticker else []) + list(b.get("choices", ["VT", "ACWI", "VTI", "VXUS"])):
        tk = str(tk).strip().upper()
        if tk and tk not in out:
            out.append(tk)
    return (str(ticker).upper() if ticker else None), out[:8]


# ----------------------------------------------------------------------
def build_income_section(
    cfg: dict[str, Any], root: Path, dates: list[date], extras: dict[str, Any]
) -> dict[str, Any]:
    """
    Dividends and the benchmark, in the display currency where FX allows.

    The benchmark is converted with the same daily rates as the currency
    section, so it is compared with your return in one currency. Without rates
    (currency section off, or the same currency throughout) it stays as is.
    """
    import income

    display = cfg["account"].get("display_currency", "USD")
    fx_cfg = cfg.get("currency", {})
    asset_ccy = fx_cfg.get("asset_currency", "USD")
    rates: list[float | None] | None = None
    if fx_cfg.get("enabled") and asset_ccy != display:
        try:
            from fx import FXSeries

            fxs = FXSeries(asset_ccy, display, root / fx_cfg.get("cache_path", "data/fx_history.json"))
            fxs.ensure_range(dates[0], dates[-1])
            rates = fxs.aligned(dates)
        except Exception as exc:  # noqa: BLE001
            log.warning("No FX for income/benchmark, leaving them in %s: %s", asset_ccy, exc)

    divs = []
    rate_on = dict(zip(dates, rates)) if rates else {}
    for d in extras.get("dividends", []):
        day = date.fromisoformat(d["date"])
        r = None
        if rate_on:  # last fix on or before the payment day
            r = next((rate_on[x] for x in reversed(dates) if x <= day and rate_on.get(x)), None)
        conv = r is not None and d["currency"] == asset_ccy
        divs.append({**d, "display_amount": d["amount"] * r if conv else d["amount"],
                     "display_currency": display if conv else d["currency"]})

    def series(tk: str, idx: Any) -> dict[str, Any]:
        return {
            "ticker": tk,
            "currency": display if rates else asset_ccy,
            "converted": rates is not None,
            "cps": income.align_cumulative(dates, idx, rates),
        }

    benches = {tk: series(tk, idx) for tk, idx in (extras.get("benchmark_indexes") or {}).items() if idx}
    idx = extras.get("benchmark_index")
    tk = extras.get("benchmark_ticker", "VT")
    bench = benches.get(tk) or (series(tk, idx) if idx else None)
    if bench and tk not in benches:
        benches[tk] = bench
    return {
        "dividends": divs,
        "withholding_rate": float((cfg.get("dividends") or {}).get("withholding_rate", 0.15)),
        "benchmark": bench,
        "benchmarks": benches,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the IBKR portfolio and FIRE dashboard.")
    ap.add_argument("--demo", action="store_true", help="use bundled sample data instead of IBKR")
    ap.add_argument("--no-open", action="store_true", help="do not launch a browser")
    ap.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    cfg = load_config()
    out_cfg = cfg.get("output", {})

    try:
        positions, summary, series = demo_snapshot() if args.demo else live_snapshot(cfg)
    except Exception as exc:  # noqa: BLE001 — surface any failure clearly to a non-technical run
        log.error("Could not build a snapshot: %s", exc)
        if not args.demo:
            log.error("Try `python src/main.py --demo` to confirm the rest of the tooling works.")
        return 1

    # -- merge into the growing local history --------------------------
    # Demo runs get their own store: the sample series covers the same dates as
    # a real pull, so sharing one file would let fake NAVs overwrite real ones.
    hist_path = ROOT / out_cfg.get("history_path", "data/nav_history.json")
    if args.demo:
        hist_path = hist_path.with_name(f"demo_{hist_path.name}")
    hist = NavHistory(hist_path)
    hist.merge(series["dates"], series["navs"], series["cps"])
    hist.save()
    dates, navs, cps = hist.series()
    log.info("History spans %s to %s (%d observations).", dates[0], dates[-1], len(dates))

    # -- returns -------------------------------------------------------
    flows: list[CashFlow] = reconstruct_flows(dates, navs, cps)
    log.info("Reconstructed %d external cash flows.", len(flows))
    windows = all_window_returns(dates, navs, flows)
    fx_block = build_fx_section(cfg, ROOT, dates, cps, positions)
    income_block = build_income_section(cfg, ROOT, dates, series.get("extras") or {})

    # -- assemble ------------------------------------------------------
    today = dates[-1]
    birth = datetime.strptime(cfg["person"]["birth_date"], "%Y-%m-%d").date()
    plan = build_plan(cfg, today)
    # display_currency only *labels* the figures - it does not convert them. IBKR
    # reports NAV in the account's own base currency, so a mismatch here silently
    # prints one currency's numbers under another's name.
    reported_ccy = series.get("base_currency")
    ccy = cfg["account"].get("display_currency") or reported_ccy or "USD"
    if not args.demo and reported_ccy and ccy != reported_ccy:
        log.warning(
            "config display_currency is %s but IBKR reports this account in %s. "
            "No conversion is applied - the figures are %s shown under a %s label. "
            "Either set display_currency to %s, or change the account's base currency in IBKR.",
            ccy, reported_ccy, reported_ccy, ccy, reported_ccy,
        )

    lookthrough = cfg.get("lookthrough", {})
    for p in positions:
        p["role"] = lookthrough.get(p["ticker"], {}).get("role", "")

    snapshot = {
        "as_of": today.strftime("%d %B %Y"),
        "age_days": (date.today() - today).days,
        # Sample data is frozen, so its "age" only ever grows. Staleness is a
        # live-data concept; flagging it on the demo just nags about nothing.
        "demo": bool(args.demo),
        "ccy": ccy,
        "measure": series.get("measure", "TWR"),
        "age_now": round(age_on(birth, today), 2),
        "summary": summary,
        "positions": positions,
        "exposure": compute_exposure(positions, lookthrough),
        "series": [
            {"t": int(datetime.combine(d, datetime.min.time()).timestamp() * 1000), "cps": c, "nav": n}
            for d, c, n in zip(dates, cps, navs)
        ],
        "flows": [
            {"t": int(datetime.combine(f.on, datetime.min.time()).timestamp() * 1000), "amount": f.amount}
            for f in flows
        ],
        "targets": cfg.get("targets", {}),
        "returns": [
            {
                "label": w.label,
                "available": w.available,
                "note": w.note,
                "cumulative": w.cumulative,
                "annualised": w.annualised,
                "net_contributed": w.net_contributed,
                "closing_nav": w.closing_nav,
                "days": w.days,
                "extrapolated": w.annualised_is_extrapolated,
                "clamped": w.clamped,
            }
            for w in windows
        ],
        "fx": fx_block,
        "income": income_block,
        "fund_history": (series.get("extras") or {}).get("fund_history", {}),
        "plan": plan,
        "fmt": {
            "locale": out_cfg.get("locale", "en-US"),
            "thousands_separator": out_cfg.get("thousands_separator", ","),
        },
        "lookthrough_keys": list(lookthrough.keys()),
        # Each fund's published regional split and fees, so the Targets page can
        # show what a mix of funds holds. Fund facts, nothing personal.
        "lookthrough": {
            k: {f: v[f] for f in ("us", "dev", "em", "tilt", "ter", "role") if f in v}
            for k, v in lookthrough.items() if isinstance(v, dict)
        },
        # Expense ratios from config, keyed by ticker. Missing means unknown, not zero.
        "ters": {k: float(v["ter"]) for k, v in lookthrough.items() if isinstance(v, dict) and "ter" in v},
        "lede": build_lede(
            summary["net_liquidation"], plan["target"], ccy, plan,
            out_cfg.get("thousands_separator", ","),
        ),
    }

    out_path = ROOT / out_cfg.get("html_path", "dashboard.html")
    render(snapshot, out_path)

    for w in windows:
        if w.available:
            log.info("%-18s cumulative %+.2f%%  annualised %+.2f%%", w.label, w.cumulative * 100, w.annualised * 100)

    if fx_block:
        for s_ in fx_block["splits"]:
            if s_["available"]:
                log.info(
                    "%-18s assets %+.2f%%  currency %+.2f%%  (currency was %.0f%% of the total)",
                    s_["label"], s_["asset"] * 100, s_["currency"] * 100,
                    (s_["currency_share"] or 0) * 100,
                )

    if out_cfg.get("open_browser", True) and not args.no_open:
        webbrowser.open(out_path.as_uri())
    log.info("Done: %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
