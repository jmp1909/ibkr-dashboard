"""
build_demo_site.py - regenerate the public demo page served by GitHub Pages.

Runs the dashboard against the bundled sample data, then writes it to
docs/index.html with social-preview tags added so links to it render a proper
card on LinkedIn, Slack and so on.

Usage:  python scripts/build_demo_site.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://jmp1909.github.io/ibkr-dashboard/"
REPO_URL = "https://github.com/jmp1909/ibkr-dashboard"

OG_TAGS = f"""
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:title" content="IBKR Portfolio &amp; FIRE Dashboard - live demo">
<meta property="og:description" content="Interactive demo with sample data. Money-weighted returns, contributions vs market growth, allocation drift, and financial-independence projections you can adjust with sliders.">
<meta property="og:image" content="{REPO_URL}/raw/main/docs/screenshots/overview.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="description" content="Interactive demo of an open-source Interactive Brokers portfolio and FIRE dashboard, running on sample data.">
"""

BANNER = f"""
<div style="background:#14181A;color:#F6F7F4;padding:11px 20px;font-family:'IBM Plex Mono',monospace;
            font-size:12.5px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;justify-content:center">
  <span><b>Live demo</b> &mdash; sample data, not a real account.</span>
  <a href="{REPO_URL}" style="color:#7FBFA5">Source on GitHub &rarr;</a>
</div>
"""


def main() -> int:
    py = sys.executable
    run = subprocess.run(
        [py, "src/main.py", "--demo", "--no-open"], cwd=ROOT, capture_output=True, text=True
    )
    if run.returncode != 0:
        print(run.stdout + run.stderr)
        raise SystemExit("demo build failed")

    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")

    # Social preview tags go in <head>; the banner goes at the very top of <body>.
    html = html.replace("</head>", OG_TAGS + "</head>", 1)
    html = re.sub(r"(<body[^>]*>)", r"\1" + BANNER, html, count=1)

    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
