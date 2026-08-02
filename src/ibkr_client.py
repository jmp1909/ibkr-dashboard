"""
ibkr_client.py — thin wrapper over the IBKR Client Portal Web API.

Purpose : Fetch positions, balances and the daily NAV/return series.
Inputs  : A running Client Portal Gateway on localhost (see README).
Outputs : Plain dicts and lists — no IBKR types leak past this module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import requests
import urllib3

# The gateway serves a self-signed certificate on localhost. Verification is
# disabled for that host only; this silences the resulting warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://localhost:5000/v1/api"


class GatewayError(RuntimeError):
    """Raised when the gateway is unreachable or the session is not authenticated."""


@dataclass
class Position:
    """One open position, as reported by IBKR."""
    ticker: str
    name: str
    quantity: float
    price: float
    market_value: float
    currency: str
    unrealised_pnl: float
    asset_class: str
    cost_basis: float  # 0.0 when the gateway does not report it


class IBKRClient:
    """
    Client Portal Web API wrapper.

    The gateway must already be running and logged in. Sessions expire after
    roughly 24 hours of inactivity and require re-authentication in a browser —
    this is a limitation of IBKR's design, not something the script can avoid.
    """

    def __init__(self, base_url: str = DEFAULT_BASE, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False
        self._account_id: str | None = None

    # -- plumbing ------------------------------------------------------
    def _get(self, path: str, **kw: Any) -> Any:
        return self._request("GET", path, **kw)

    def _post(self, path: str, **kw: Any) -> Any:
        return self._request("POST", path, **kw)

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kw)
        except requests.exceptions.ConnectionError as exc:
            raise GatewayError(
                "Cannot reach the Client Portal Gateway. Start it, then log in at "
                "https://localhost:5000 before running this script."
            ) from exc
        except requests.RequestException as exc:
            raise GatewayError(f"Request to {path} failed: {exc}") from exc

        if resp.status_code == 401:
            raise GatewayError("Gateway session expired. Log in again at https://localhost:5000.")
        resp.raise_for_status()
        return resp.json()

    # -- session -------------------------------------------------------
    def ensure_authenticated(self) -> None:
        """Confirm the gateway holds a live, authenticated session."""
        status = self._get("/iserver/auth/status")
        if not status.get("authenticated"):
            raise GatewayError(
                "Gateway is running but not authenticated. Log in at https://localhost:5000."
            )
        if status.get("competing"):
            log.warning("Another session is competing for this account; data may be stale.")

    @property
    def account_id(self) -> str:
        """The first account on the login. Set ACCOUNT_ID in config to override."""
        if self._account_id is None:
            accounts = self._get("/portfolio/accounts")
            if not accounts:
                raise GatewayError("No accounts returned by the gateway.")
            self._account_id = accounts[0]["accountId"]
            log.info("Using account %s", self._account_id)
        return self._account_id

    def use_account(self, account_id: str) -> None:
        """Pin a specific account id rather than taking the first."""
        self._account_id = account_id

    # -- data ----------------------------------------------------------
    def positions(self) -> list[Position]:
        """All open positions, paging until the gateway returns a short page."""
        out: list[Position] = []
        page = 0
        while True:
            rows = self._get(f"/portfolio/{self.account_id}/positions/{page}")
            if not rows:
                break
            for r in rows:
                qty = float(r.get("position") or 0)
                out.append(
                    Position(
                        ticker=r.get("contractDesc") or r.get("ticker") or "?",
                        name=r.get("name") or r.get("contractDesc") or "",
                        quantity=qty,
                        price=float(r.get("mktPrice") or 0),
                        market_value=float(r.get("mktValue") or 0),
                        currency=r.get("currency") or "USD",
                        unrealised_pnl=float(r.get("unrealizedPnl") or 0),
                        asset_class=r.get("assetClass") or "STK",
                        cost_basis=_cost_basis(r, qty),
                    )
                )
            if len(rows) < 30:
                break
            page += 1
            time.sleep(0.3)  # the gateway rate-limits aggressively
        return out

    def summary(self) -> dict[str, float]:
        """Account-level figures: net liquidation, cash, gross position value."""
        raw = self._get(f"/portfolio/{self.account_id}/summary")

        def val(key: str) -> float:
            node = raw.get(key) or {}
            try:
                return float(node.get("amount", 0.0))
            except (TypeError, ValueError):
                return 0.0

        return {
            "net_liquidation": val("netliquidation"),
            "total_cash": val("totalcashvalue"),
            "gross_position_value": val("grosspositionvalue"),
            "currency": (raw.get("netliquidation") or {}).get("currency", "CHF"),
        }

    def performance(self) -> dict[str, Any]:
        """
        Daily NAV and cumulative-return series.

        Requests the longest window the gateway offers (period=1Y). IBKR caps
        this endpoint at about one year, which is why the local history store
        exists — it stitches successive pulls together so multi-year windows
        become available over time.
        """
        body = {"acctIds": [self.account_id], "freq": "D", "period": "1Y"}
        raw = self._post("/pa/performance", json=body)

        nav_node = raw.get("nav") or {}
        cps_node = raw.get("cps") or {}
        dates = nav_node.get("dates") or cps_node.get("dates")
        nav_data = (nav_node.get("data") or [{}])[0]
        cps_data = (cps_node.get("data") or [{}])[0]
        navs = nav_data.get("navs")
        cps = cps_data.get("returns")
        if not dates or navs is None or cps is None:
            raise GatewayError("Performance response contained no series.")

        return {
            "measure": raw.get("pm", "TWR"),
            "base_currency": nav_data.get("baseCurrency", "CHF"),
            "dates": [_parse_day(d) for d in dates],
            "navs": [float(x) for x in navs],
            "cps": [float(x) for x in cps],
        }


def _cost_basis(row: dict[str, Any], quantity: float) -> float:
    """
    Total cost of a position, or 0.0 if the gateway does not report it.

    IBKR is inconsistent here: some builds return `avgCost` (total per unit
    including commission), others only `avgPrice`. Either is enough to recover
    the total, and a missing value must degrade quietly rather than break the
    run — cost basis is a nice-to-have, the return maths does not depend on it.
    """
    for key in ("avgCost", "avgPrice"):
        try:
            per_unit = float(row.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if per_unit:
            return per_unit * quantity
    return 0.0


def _parse_day(raw: str | int) -> date:
    """Parse IBKR's yyyymmdd day stamps."""
    return datetime.strptime(str(raw), "%Y%m%d").date()
