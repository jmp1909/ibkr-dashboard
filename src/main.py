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


def months_between(anchor: date, ym: str) -> int:
    """Whole months from the anchor date to the first of the given YYYY-MM."""
    y, m = (int(x) for x in ym.split("-"))
    return (y - anchor.year) * 12 + (m - anchor.month)


def build_plan(cfg: dict[str, Any], today: date) -> dict[str, Any]:
    """
    Convert the config's calendar phases into month offsets from today.

    Phases that ended in the past are dropped; a phase already under way is
    clipped to start now, so the projection always begins from the present.
    """
    goal = cfg["goal"]
    phases = []
    for p in cfg["phases"]:
        start = max(0, months_between(today, p["start"]))
        end = None if p.get("end") in (None, "") else months_between(today, p["end"])
        if end is not None and end < 0:
            continue  # wholly in the past
        phases.append(
            {
                "id": p["id"],
                "label": p["label"],
                "range_label": f"{p['start']} \u2192 {p.get('end') or 'open-ended'}",
                "start_month": start,
                "end_month": end,
                "monthly_income": float(p["monthly_income"]),
                "savings_rate": float(p["savings_rate"]),
                "income_growth": float(p.get("income_growth", 0.0)),
            }
        )
    if not phases:
        raise SystemExit("No future phases in config.json - nothing to project.")

    return {
        "target": float(goal["target"]),
        "real_return": float(goal["real_return"]),
        "withdrawal_rate": float(goal["withdrawal_rate"]),
        "coast_full_age": float(goal["coast_full_age"]),
        "phases": phases,
    }


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


def build_lede(net: float, target: float, ccy: str, plan: dict[str, Any]) -> str:
    """One honest paragraph under the headline."""
    saving = plan["phases"][0]["monthly_income"] * plan["phases"][0]["savings_rate"]
    return (
        f"Saving {ccy} {saving:,.0f} a month right now against a {ccy} {target:,.0f} target, "
        f"currently {net / target * 100:.1f}% of the way there. Returns below are money-weighted. "
        "Every input in section 03 is a slider — the projection is only as good as what you put in it."
    ).replace(",", "'")


# ----------------------------------------------------------------------
def demo_snapshot() -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    """Bundled sample data so the dashboard can be built without the gateway."""
    from demo_data import DEMO_POSITIONS, DEMO_SERIES, DEMO_SUMMARY

    return DEMO_POSITIONS, DEMO_SUMMARY, DEMO_SERIES


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
    return positions, client.summary(), client.performance()


# ----------------------------------------------------------------------
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

    # -- assemble ------------------------------------------------------
    today = dates[-1]
    birth = datetime.strptime(cfg["person"]["birth_date"], "%Y-%m-%d").date()
    plan = build_plan(cfg, today)
    ccy = cfg["account"].get("display_currency", series.get("base_currency", "CHF"))

    lookthrough = cfg.get("lookthrough", {})
    for p in positions:
        p["role"] = lookthrough.get(p["ticker"], {}).get("role", "")

    snapshot = {
        "as_of": today.strftime("%d %B %Y"),
        "age_days": (date.today() - today).days,
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
        "plan": plan,
        "lede": build_lede(summary["net_liquidation"], plan["target"], ccy, plan),
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
