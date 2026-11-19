"""
render.py — turn a snapshot into a self-contained HTML dashboard.

Purpose : Produce one HTML file with no external dependencies beyond a web
          font, containing the position sheet, money-weighted returns, and an
          interactive projection whose sliders recompute in the browser.
Inputs  : The snapshot dict assembled by main.py.
Outputs : A single .html file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TEMPLATE = (Path(__file__).with_name("dashboard.html")).read_text(encoding="utf-8")


def render(snapshot: dict[str, Any], out_path: Path) -> Path:
    """Write the dashboard HTML and return the path written."""
    ccy = snapshot["ccy"]
    target = snapshot["plan"]["target"]
    net = snapshot["summary"]["net_liquidation"]
    sep = (snapshot.get("fmt") or {}).get("thousands_separator", ",")

    def money(v: float) -> str:
        return f"{ccy} {v:,.0f}".replace(",", sep)

    html = TEMPLATE
    html = html.replace("__DATA__", json.dumps(snapshot, default=str))
    html = html.replace("__ASOF__", snapshot["as_of"])
    html = html.replace("__CCY__", ccy)
    html = html.replace("__TARGETLBL__", money(target))
    html = html.replace("__NETLIQLBL__", money(net))
    html = html.replace("__MEASURE__", snapshot["measure"])
    html = html.replace("__LEDE__", snapshot["lede"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    log.info("Wrote %s (%.0f KB)", out_path, out_path.stat().st_size / 1024)
    return out_path
