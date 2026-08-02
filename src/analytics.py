"""
analytics.py — return and projection maths for the IBKR FIRE dashboard.

Purpose : Reconstruct external cash flows from NAV + TWR series, compute
          money-weighted returns (XIRR), and project the portfolio forward.
Inputs  : Daily NAV series and cumulative TWR series from IBKR.
Outputs : MWR figures per window, and a monthly projection table.

No third-party dependencies — stdlib only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Sequence

log = logging.getLogger(__name__)

# Flows smaller than this are floating-point noise, not real transfers.
FLOW_NOISE_FLOOR = 0.50


# ----------------------------------------------------------------------
# Cash-flow reconstruction
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CashFlow:
    """An external transfer into (+) or out of (-) the account."""
    on: date
    amount: float


def daily_returns(cps: Sequence[float]) -> list[float]:
    """
    Convert a cumulative-return series into daily returns.

    IBKR reports `cps` as cumulative fractions from the period start, so the
    return on day t is (1 + cps_t) / (1 + cps_t-1) - 1.
    """
    out = [0.0]
    for prev, cur in zip(cps, cps[1:]):
        denom = 1.0 + prev
        if denom == 0:
            out.append(0.0)
            log.warning("Cumulative return hit -100%%; treating daily return as 0.")
        else:
            out.append((1.0 + cur) / denom - 1.0)
    return out


def reconstruct_flows(
    dates: Sequence[date],
    navs: Sequence[float],
    cps: Sequence[float],
) -> list[CashFlow]:
    """
    Derive external cash flows from NAV and time-weighted return series.

    TWR deliberately excludes the effect of deposits and withdrawals, so any
    change in NAV that the day's return does not explain must be an external
    transfer:

        flow_t = NAV_t - NAV_t-1 * (1 + r_t)

    This is how we obtain money-weighted returns from an account that IBKR
    has configured to report TWR only.
    """
    if not (len(dates) == len(navs) == len(cps)):
        raise ValueError("dates, navs and cps must be the same length")
    if not dates:
        return []

    rets = daily_returns(cps)
    flows = [CashFlow(dates[0], navs[0])] if abs(navs[0]) > FLOW_NOISE_FLOOR else []

    for i in range(1, len(dates)):
        expected = navs[i - 1] * (1.0 + rets[i])
        delta = navs[i] - expected
        if abs(delta) > FLOW_NOISE_FLOOR:
            flows.append(CashFlow(dates[i], delta))
    return flows


# ----------------------------------------------------------------------
# XIRR
# ----------------------------------------------------------------------
def _npv(rate: float, flows: Sequence[tuple[date, float]], t0: date) -> float:
    """Net present value of dated flows at an annual rate, actual/365."""
    total = 0.0
    for on, amt in flows:
        years = (on - t0).days / 365.0
        total += amt / ((1.0 + rate) ** years)
    return total


def xirr(flows: Sequence[tuple[date, float]], lo: float = -0.9999, hi: float = 10.0) -> float | None:
    """
    Annualised internal rate of return for irregularly dated flows.

    Uses bisection rather than Newton-Raphson: slower, but it cannot diverge,
    which matters because this runs unattended on whatever flows the account
    happens to contain.

    Returns None when the flows do not bracket a root (e.g. all same sign).
    """
    dated = sorted(flows, key=lambda f: f[0])
    if len(dated) < 2:
        return None
    if not (any(a > 0 for _, a in dated) and any(a < 0 for _, a in dated)):
        log.debug("XIRR skipped: flows do not change sign.")
        return None

    t0 = dated[0][0]
    f_lo, f_hi = _npv(lo, dated, t0), _npv(hi, dated, t0)
    if f_lo * f_hi > 0:
        log.debug("XIRR skipped: no sign change across the search bracket.")
        return None

    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, dated, t0)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


# ----------------------------------------------------------------------
# Money-weighted return per window
# ----------------------------------------------------------------------
@dataclass
class WindowReturn:
    """MWR over one reporting window."""
    label: str
    start: date | None = None
    end: date | None = None
    opening_nav: float = 0.0
    closing_nav: float = 0.0
    net_contributed: float = 0.0
    annualised: float | None = None
    cumulative: float | None = None
    days: int = 0
    available: bool = False
    clamped: bool = False
    note: str = ""

    @property
    def annualised_is_extrapolated(self) -> bool:
        """True when the window is under a year, so the annual figure is an extrapolation."""
        return self.available and self.days < 365


def mwr_window(
    label: str,
    dates: Sequence[date],
    navs: Sequence[float],
    flows: Sequence[CashFlow],
    start: date,
    end: date,
) -> WindowReturn:
    """
    Money-weighted return between two dates.

    The opening NAV is treated as money put in on day one and the closing NAV
    as money taken out on the last day, with real transfers in between. The
    IRR of that stream is what the account earned on the money you actually
    had in it, which is the number that answers "how did I do".
    """
    res = WindowReturn(label=label, start=start, end=end)

    in_window = [(d, n) for d, n in zip(dates, navs) if start <= d <= end]
    if len(in_window) < 2:
        res.note = "Not enough history yet."
        return res

    first_d, first_nav = in_window[0]
    last_d, last_nav = in_window[-1]
    res.days = (last_d - first_d).days
    if res.days < 25:
        res.note = "Window too short to be meaningful."
        return res

    inner = [f for f in flows if first_d < f.on <= last_d]
    res.opening_nav = first_nav
    res.closing_nav = last_nav
    res.net_contributed = sum(f.amount for f in inner)

    stream: list[tuple[date, float]] = [(first_d, -first_nav)]
    stream += [(f.on, -f.amount) for f in inner]
    stream.append((last_d, last_nav))

    rate = xirr(stream)
    if rate is None:
        res.note = "Could not solve for a rate."
        return res

    res.annualised = rate
    res.cumulative = (1.0 + rate) ** (res.days / 365.0) - 1.0
    res.available = True
    return res


def standard_windows(today: date, inception: date) -> list[tuple[str, date]]:
    """The reporting windows, newest first. Add to this list to add a row."""
    return [
        ("Year to date", date(today.year, 1, 1)),
        ("1 year", today - timedelta(days=365)),
        ("3 years", today - timedelta(days=365 * 3)),
        ("5 years", today - timedelta(days=365 * 5)),
        ("Since inception", inception),
    ]


def all_window_returns(
    dates: Sequence[date],
    navs: Sequence[float],
    flows: Sequence[CashFlow],
) -> list[WindowReturn]:
    """
    Compute MWR for every standard window, skipping those the account is too
    young for. Windows become available on their own as history accumulates.
    """
    if not dates:
        return []
    today, inception = dates[-1], dates[0]
    out = []
    for label, want_start in standard_windows(today, inception):
        start = max(want_start, inception)
        res = mwr_window(label, dates, navs, flows, start, today)
        if not res.available and not res.note:
            res.note = "Not enough history yet."
        if want_start < inception and label != "Since inception":
            # The account is younger than the window, so this row is really
            # just the since-inception figure wearing a different label.
            res.clamped = True
            months = (today - inception).days / 30.44
            res.note = f"account is only {months:.0f} months old"
        out.append(res)
    return out


# ----------------------------------------------------------------------
# Currency decomposition
# ----------------------------------------------------------------------
@dataclass
class CurrencySplit:
    """
    A CHF return separated into what the assets did and what the currency did.

    The identity is exact and multiplicative:

        (1 + total) = (1 + asset) x (1 + currency)

    so `interaction` is the cross term asset x currency, reported separately
    rather than folded into either leg.
    """
    label: str
    total: float = 0.0        # return in the reporting currency
    asset: float = 0.0        # return measured in the quote currency of the assets
    currency: float = 0.0     # move in the exchange rate
    interaction: float = 0.0  # asset x currency
    days: int = 0
    available: bool = False
    note: str = ""

    @property
    def currency_share(self) -> float | None:
        """
        Portion of the total return attributable to the currency leg.

        Undefined when the total is close to zero, since the ratio explodes;
        callers must handle None rather than print a meaningless percentage.
        """
        if not self.available or abs(self.total) < 1e-4:
            return None
        return (self.currency + self.interaction) / self.total


def _chain(returns: Iterable[float]) -> float:
    """Compound a sequence of period returns."""
    acc = 1.0
    for r in returns:
        acc *= 1.0 + r
    return acc - 1.0


def decompose_currency(
    label: str,
    dates: Sequence[date],
    cps: Sequence[float],
    fx: Sequence[float | None],
    start: date,
    end: date,
) -> CurrencySplit:
    """
    Split the reporting-currency return over a window into asset and FX legs.

    `fx` is the rate expressed as reporting-currency units per unit of the
    assets' quote currency, aligned to `dates`. A rise means the quote
    currency strengthened, which helps a holder who reports in the other one.

    The asset leg is recovered rather than observed:

        1 + r_asset = (1 + r_reported) / (1 + r_fx)

    Because both legs chain multiplicatively, the daily split aggregates to an
    exact window split with no residual beyond the stated cross term.
    """
    res = CurrencySplit(label=label)

    rows = [
        (d, c, f)
        for d, c, f in zip(dates, cps, fx)
        if start <= d <= end and f is not None
    ]
    if len(rows) < 25:
        res.note = "Not enough overlapping history."
        return res

    rep_daily = daily_returns([c for _, c, _ in rows])
    rates = [f for _, _, f in rows]
    fx_daily = [0.0]
    for prev, cur in zip(rates, rates[1:]):
        fx_daily.append(cur / prev - 1.0 if prev else 0.0)

    asset_daily = []
    for r_rep, r_fx in zip(rep_daily, fx_daily):
        denom = 1.0 + r_fx
        asset_daily.append((1.0 + r_rep) / denom - 1.0 if denom else 0.0)

    res.total = _chain(rep_daily)
    res.currency = _chain(fx_daily)
    res.asset = _chain(asset_daily)
    res.interaction = res.asset * res.currency
    res.days = (rows[-1][0] - rows[0][0]).days
    res.available = True
    return res


def all_currency_splits(
    dates: Sequence[date],
    cps: Sequence[float],
    fx: Sequence[float | None],
) -> list[CurrencySplit]:
    """Currency decomposition for each standard reporting window."""
    if not dates:
        return []
    today, inception = dates[-1], dates[0]
    out = []
    for label, want_start in standard_windows(today, inception):
        split = decompose_currency(label, dates, cps, fx, max(want_start, inception), today)
        if want_start < inception and label != "Since inception":
            continue  # would just repeat the since-inception row
        out.append(split)
    return out
