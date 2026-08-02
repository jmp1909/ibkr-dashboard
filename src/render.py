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

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portfolio &amp; FIRE &mdash; __ASOF__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--ground:#E4E6E1;--panel:#F6F7F4;--ink:#14181A;--muted:#79838B;--rule:#CBD0C9;
--path:#1B4D3E;--fire:#A8632B;--coast:#4C6272;--warn:#8C3A2E;}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:40px 24px 80px}
.mono{font-family:'IBM Plex Mono',monospace}
h1{font-family:Archivo,sans-serif;font-weight:800;font-size:clamp(32px,5.6vw,56px);letter-spacing:-.035em;line-height:.99;margin:0}
h2{font-family:Archivo,sans-serif;font-weight:700;font-size:20px;letter-spacing:-.01em;margin:0}
.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.lede{max-width:640px;margin-top:18px;font-size:15px;line-height:1.6;color:#3C464C}
section{margin-bottom:56px}
.shead{display:flex;gap:14px;align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:10px;margin-bottom:24px;flex-wrap:wrap}
.shead .n{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted)}
.shead .k{font-size:12px;color:var(--muted);margin-left:auto;text-align:right}
table{width:100%;border-collapse:collapse;font-family:'IBM Plex Mono',monospace;font-size:13px}
th{text-align:right;padding:8px 10px;color:var(--muted);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;font-weight:500;border-bottom:1px solid var(--rule)}
th.l,td.l{text-align:left}
td{text-align:right;padding:11px 10px;border-bottom:1px solid var(--rule)}
td.role{color:var(--muted);font-size:11.5px;font-family:Inter,sans-serif}
.pos{color:var(--path)}.neg{color:var(--warn)}
.bar{display:inline-block;width:46px;height:5px;background:var(--rule);margin-right:8px;vertical-align:middle;position:relative}
.bar i{position:absolute;inset:0;background:var(--path)}
.panel{background:var(--panel);border:1px solid var(--rule);padding:22px 24px}
.dark{background:var(--ink);color:var(--panel);padding:24px 26px}
.grid{display:grid;gap:20px}
.g3{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.stat{border-left:2px solid var(--rule);padding-left:12px}
.stat .lab{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.stat .val{font-family:Archivo,sans-serif;font-weight:700;font-size:26px;line-height:1.15;letter-spacing:-.02em;margin-top:3px}
.stat .sub{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.geo{display:flex;height:34px;border:1px solid var(--ink)}
.geo div{display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:600;font-family:'IBM Plex Mono',monospace}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:11.5px;color:var(--muted)}
.cols{display:grid;grid-template-columns:minmax(250px,320px) minmax(0,1fr);gap:34px;align-items:start}
@media(max-width:860px){.cols{grid-template-columns:1fr}}
.phase{border-left:2px solid var(--path);padding-left:12px;margin-bottom:24px}
.phase .ph{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;margin-bottom:2px}
.phase .pd{font-size:11px;color:var(--muted);margin-bottom:12px}
.ctl{margin-bottom:18px}
.ctl .row{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.ctl label{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.ctl .v{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600}
input[type=range]{width:100%;height:4px;accent-color:var(--path);background:var(--rule);border-radius:2px;-webkit-appearance:none}
input[type=range]:focus-visible{outline:2px solid var(--path);outline-offset:4px}
.derived{font-size:11px;color:var(--path);font-family:'IBM Plex Mono',monospace;margin-top:5px}
.note{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.45}
svg{display:block;width:100%;height:auto}
.hero{border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);padding:22px 0 20px;margin:34px 0 46px}
.hero .figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:22px 26px}
.hero .fig .lab{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.hero .fig .num{font-family:Archivo,sans-serif;font-weight:700;font-size:23px;letter-spacing:-.02em;margin-top:4px;line-height:1.1}
.hero .fig .sub{font-size:11px;color:var(--muted);margin-top:2px}
.track{position:relative;height:26px;margin-bottom:20px}
.track .rail{position:absolute;top:9px;left:0;right:0;height:8px;background:var(--rule)}
.track .fill{position:absolute;top:9px;left:0;height:8px;background:var(--path)}
.track .tick{position:absolute;top:4px;width:1px;height:18px;background:var(--ground)}
.track .tick span{position:absolute;top:20px;left:0;transform:translateX(-50%);font-family:'IBM Plex Mono',monospace;
  font-size:9px;color:var(--muted);white-space:nowrap}
.track .pin{position:absolute;top:2px;width:2px;height:22px;background:var(--ink)}
.chartwrap{position:relative}
.tipbox{position:absolute;pointer-events:none;opacity:0;transition:opacity .09s;background:var(--ink);color:var(--panel);
  padding:8px 10px;font-family:'IBM Plex Mono',monospace;font-size:11.5px;line-height:1.5;white-space:nowrap;
  border-radius:2px;z-index:5;box-shadow:0 2px 10px rgba(0,0,0,.18)}
.tipbox .tt{color:#9AA5AC;font-size:10px;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:3px}
.tipbox .tr{display:flex;gap:10px;justify-content:space-between}
.tipbox .tr b{font-weight:600}
.axl{font-family:'IBM Plex Mono',monospace;font-size:10px;fill:var(--muted)}
footer{border-top:1px solid var(--rule);padding-top:20px;font-size:11.5px;color:var(--muted);line-height:1.65;max-width:760px}
.warnbox{background:#F6E9E4;border-left:3px solid var(--warn);padding:12px 16px;font-size:12.5px;line-height:1.5;margin-bottom:24px}
</style></head><body><div class="wrap">

<header style="margin-bottom:46px">
  <div class="eyebrow">Interactive Brokers &middot; snapshot __ASOF__ &middot; base __CCY__ &middot; target __TARGETLBL__</div>
  <h1>__NETLIQLBL__ today.<br><span style="color:var(--path)">__TARGETLBL__</span> is the line.</h1>
  <p class="lede">__LEDE__</p>
</header>

<div id="staleness"></div>

<div class="hero">
  <div class="track" id="herotrack" title="progress toward the target"></div>
  <div style="font-size:10.5px;color:var(--muted);margin:22px 0 20px;font-family:'IBM Plex Mono',monospace">
    Milestones evenly spaced, not to scale &mdash; position within the current step is exact.</div>
  <div class="figs" id="herofigs"></div>
</div>

<section>
  <div class="shead"><span class="n">01</span><h2>Holdings</h2><span class="k" id="hk"></span></div>
  <div style="overflow-x:auto"><table id="postbl">
    <thead><tr><th class="l">Ticker</th><th class="l">Role</th><th>Units</th><th>Price</th><th>Value</th><th>Weight</th>
      <th class="costcol">Cost</th><th class="costcol">Total return</th><th>Unreal. P&amp;L</th></tr></thead>
    <tbody></tbody></table></div>
  <div class="panel" style="margin-top:28px" id="exposurepanel">
    <div class="eyebrow" style="margin-bottom:4px">True exposure &mdash; fund look-through</div>
    <p style="font-size:12.5px;color:var(--muted);margin:0 0 18px;max-width:560px;line-height:1.5">
      IBKR reports this account as United States / Broad because all the funds are US-domiciled.
      That is a custody fact, not an exposure fact. Regional splits come from <code>config.json</code>.</p>
    <div class="geo" id="geo"></div><div class="legend" id="geolegend"></div>
    <div class="grid g3" style="margin-top:20px;padding-top:18px;border-top:1px solid var(--rule)" id="expstats"></div>
  </div>
</section>

<section id="driftsection" hidden>
  <div class="shead"><span class="n">02</span><h2>Drift from target</h2><span class="k" id="driftk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 22px;line-height:1.55">
    Targets come from <code>config.json</code>. Rebalancing here is <b>buy-only</b>: it never suggests
    selling, it just points your next contribution at whatever has fallen furthest behind. That keeps
    you off a taxable event and, while you are still adding money monthly, is usually enough to hold
    the allocation in line on its own.</p>

  <div style="overflow-x:auto"><table id="drifttbl">
    <thead><tr><th class="l">Ticker</th><th>Target</th><th>Actual</th><th>Drift</th><th>Value</th><th>At target</th><th>Gap</th></tr></thead>
    <tbody></tbody></table></div>

  <div class="panel" style="margin-top:28px">
    <div class="eyebrow" style="margin-bottom:14px">Where the next contribution should go</div>
    <div class="ctl" style="max-width:420px">
      <div class="row"><label for="buyamt">Amount to invest</label><span class="v" id="buyamtv"></span></div>
      <input type="range" id="buyamt" min="0" max="10000" step="50">
      <div class="note">Defaults to your most recent transfer. Drag to plan a different contribution.</div>
    </div>
    <div style="overflow-x:auto;margin-top:18px"><table id="buytbl">
      <thead><tr><th class="l">Ticker</th><th>Buy</th><th>Share of contribution</th><th>Weight after</th><th class="l">&nbsp;</th></tr></thead>
      <tbody></tbody></table></div>
    <div class="note" id="buynote" style="margin-top:14px"></div>
  </div>
</section>

<section id="growthsection" hidden>
  <div class="shead"><span class="n">03</span><h2>What you saved vs what the market added</h2><span class="k" id="growthk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 20px;line-height:1.55">
    The darker band is money you transferred in. Where the value line sits above it, the gap is market
    growth; where the band sits above the value line, the account was worth <b>less than you had paid
    in</b> &mdash; an unrealised loss on paper. That is not a negative balance: the account has always
    held a positive value. Early on the band is nearly the whole chart: at this stage your savings
    rate, not your return, is doing the work. Deposits are reconstructed from the NAV and return
    series, not supplied by IBKR.</p>
  <div class="grid g3" id="growthstats" style="margin-bottom:26px"></div>
  <div class="panel" style="padding:18px 14px 6px">
    <div id="growthchart"></div>
    <div class="legend" style="padding:6px 4px">
      <span><b style="color:var(--coast)">&#9612;</b> Contributed</span>
      <span><b style="color:var(--path)">&#9612;</b> Market growth</span>
    </div>
  </div>
  <div style="overflow-x:auto;margin-top:26px"><table id="flowtbl">
    <thead><tr><th class="l">Date</th><th>Amount</th><th>Running total</th><th class="l">&nbsp;</th></tr></thead>
    <tbody></tbody></table></div>
</section>

<section>
  <div class="shead"><span class="n">04</span><h2>Money-weighted returns</h2><span class="k">what your money earned, not what the funds did</span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 18px;line-height:1.55">
    IBKR reports this account as __MEASURE__. These figures are money-weighted: external transfers are
    reconstructed from the NAV and return series, then an internal rate of return is solved over the
    result. MWR answers &ldquo;how did the money I actually had invested do&rdquo;, which is the number
    that matters when you are still contributing heavily.</p>
  <div style="overflow-x:auto"><table id="mwrtbl">
    <thead><tr><th class="l">Window</th><th>Cumulative</th><th>Annualised</th><th>Net contributed</th><th>Closing value</th><th class="l">&nbsp;</th></tr></thead>
    <tbody></tbody></table></div>
  <div class="panel" style="margin-top:24px;padding:18px 14px 6px"><div id="navchart"></div></div>
</section>


<section id="ccysection" hidden>
  <div class="shead"><span class="n">05</span><h2>Currency</h2><span class="k" id="ccyk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 20px;line-height:1.55">
    Your funds are priced in one currency and you will spend another. That gap is not noise: the
    reported return is the asset return multiplied by the exchange-rate move, and the two legs are
    separated below. The identity is exact &mdash; (1&nbsp;+&nbsp;assets) &times; (1&nbsp;+&nbsp;currency)
    reproduces the reported figure with no residual beyond the cross term.</p>

  <div class="grid g3" id="ccystats" style="margin-bottom:26px"></div>

  <div style="overflow-x:auto"><table id="ccytbl">
    <thead><tr><th class="l">Window</th><th>Reported</th><th>Assets</th><th>Currency</th><th>Cross term</th><th>Currency share</th></tr></thead>
    <tbody></tbody></table></div>

  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px;margin-top:26px">
    <div class="panel" style="padding:18px 14px 6px">
      <div class="eyebrow" style="margin-bottom:10px;padding-left:8px" id="ratelbl"></div>
      <div id="ratechart"></div>
    </div>
    <div class="panel" id="basketpanel">
      <div class="eyebrow" style="margin-bottom:4px">Where your wealth is actually denominated</div>
      <p style="font-size:12px;color:var(--muted);margin:0 0 16px;line-height:1.5">
        Look-through to the currencies inside the funds, not the currency they are priced in.</p>
      <div class="geo" id="basket"></div>
      <div class="legend" id="basketlegend"></div>
      <div id="homecurrency" style="margin-top:18px"></div>
    </div>
  </div>

  <div class="warnbox" style="margin-top:26px;margin-bottom:0">
    <b>What this does and does not measure.</b> The split above is exact for the pair shown, but that
    pair is the funds&rsquo; <i>reporting</i> currency. A global fund priced in dollars still holds euros
    and yen, so those moves are already baked into the &ldquo;assets&rdquo; leg. Isolating every
    underlying currency would need the funds&rsquo; full holdings. Read the split as
    <i>reporting-currency translation</i>, and the basket on the right as the fuller exposure picture.
  </div>
</section>

<section>
  <div class="shead"><span class="n">06</span><h2>Milestones</h2><span class="k" id="msk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 22px;line-height:1.55">
    Dates in the past are real &mdash; the day your recorded NAV first closed above the line. Dates in
    the future come from the projection in section 07 and move when you change its sliders, so treat
    them as the shape of the path, not a promise.</p>
  <div style="overflow-x:auto"><table id="mstbl">
    <thead><tr><th class="l">Milestone</th><th class="l">Status</th><th class="l">When</th><th>From today</th><th class="l">&nbsp;</th></tr></thead>
    <tbody></tbody></table></div>
</section>

<section>
  <div class="shead"><span class="n">07</span><h2>The two finish lines</h2><span class="k">drag anything &mdash; it all recalculates</span></div>
  <div class="dark" style="margin-bottom:30px"><div class="grid g3" id="goalstats"></div></div>
  <div class="cols">
    <div class="panel" id="controls"></div>
    <div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:18px" id="crossstats"></div>
      <div class="panel" style="padding:16px 12px 8px"><div id="projchart"></div>
        <div class="legend" style="padding:6px 4px">
          <span><b style="color:var(--path)">&mdash;</b> Portfolio</span>
          <span><b style="color:var(--coast)">- -</b> Coast threshold</span>
          <span><b style="color:var(--fire)">&mdash;</b> Target</span>
          <span><b style="color:var(--muted)">&#9612;</b> phase boundary</span>
        </div>
      </div>
    </div>
  </div>
</section>

<footer><p>Pulled from Interactive Brokers on __ASOF__. Money-weighted returns are derived by
reconstructing external cash flows from the NAV and time-weighted return series, then solving an
internal rate of return; they are computed here, not supplied by IBKR. Projections are deterministic
&mdash; a constant real return every month, ignoring sequence-of-returns risk, tax, pillar 3a and
second pillar. They show the shape of the problem, not a forecast. Not investment advice.</p></footer>
</div>

<script>
const D = __DATA__;
const LOCALE = (D.fmt && D.fmt.locale) || 'en-US';
const nf = new Intl.NumberFormat(LOCALE,{maximumFractionDigits:0});
const nf2 = new Intl.NumberFormat(LOCALE,{minimumFractionDigits:2,maximumFractionDigits:2});
const money = v => D.ccy + " " + nf.format(Math.round(v));
const pc = (v,d=2) => (v>=0?"":"\u2212") + Math.abs(v*100).toFixed(d) + "%";
const el = h => { const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; };

/* ---------- staleness ---------- */
(function(){
  if(D.age_days > 5){
    document.getElementById('staleness').appendChild(el(
      `<div class="warnbox"><b>Data is ${D.age_days} days old.</b> Re-run the script to refresh positions and returns.</div>`));
  }
})();

/* ---------- holdings ---------- */
(function(){
  const tb = document.querySelector('#postbl tbody');
  const tot = D.positions.reduce((s,p)=>s+p.market_value,0);
  const pnl = D.positions.reduce((s,p)=>s+p.unrealised_pnl,0);
  document.getElementById('hk').textContent =
    `${D.positions.length} positions \u00b7 ${nf.format(tot)} ${D.positions[0]?.currency||''} \u00b7 unrealised ${pnl>=0?'+':'\u2212'}${nf.format(Math.abs(pnl))}`;
  /* cost basis is optional \u2014 some gateway builds omit it. Hide both columns
     rather than printing a column of dashes. */
  const haveCost = D.positions.some(p => (p.cost_basis||0) > 0);
  if(!haveCost){
    document.querySelectorAll('.costcol').forEach(e=>e.remove());
  }
  D.positions.slice().sort((a,b)=>b.market_value-a.market_value).forEach(p=>{
    const w = tot ? p.market_value/tot : 0;
    const cost = p.cost_basis||0;
    const tr = cost ? (p.market_value-cost)/cost : null;
    const costCells = haveCost
      ? `<td>${cost?nf.format(cost):'\u2014'}</td>
         <td class="${tr===null?'':(tr>=0?'pos':'neg')}" style="font-weight:600">${tr===null?'\u2014':pc(tr)}</td>`
      : '';
    tb.appendChild(el(`<tr>
      <td class="l" style="font-weight:600;font-size:14px">${p.ticker}</td>
      <td class="l role">${p.role||''}</td>
      <td>${p.quantity.toFixed(2)}</td>
      <td>${p.price.toFixed(2)}</td>
      <td>${nf.format(p.market_value)}</td>
      <td><span class="bar"><i style="width:${(w*100).toFixed(1)}%"></i></span>${(w*100).toFixed(1)}%</td>
      ${costCells}
      <td class="${p.unrealised_pnl>=0?'pos':'neg'}">${p.unrealised_pnl>=0?'+':'\u2212'}${nf.format(Math.abs(p.unrealised_pnl))}</td></tr>`));
  });

  /* Look-through is only meaningful if the config actually describes the funds
     held. With no mapping the panel would confidently show a made-up split, so
     hide it instead. */
  const mapped = D.positions.filter(p=>D.lookthrough_keys && D.lookthrough_keys.includes(p.ticker)).length;
  if(!mapped){
    const panel=document.getElementById('exposurepanel');
    if(panel) panel.hidden = true;
    return;
  }

  const g = D.exposure, cols=[['United States',g.us,'var(--path)'],['Developed ex-US',g.dev,'var(--coast)'],['Emerging',g.em,'var(--fire)']];
  const geo=document.getElementById('geo'), leg=document.getElementById('geolegend');
  cols.forEach(([lab,v,c])=>{
    if(v<=0) return;
    geo.appendChild(el(`<div style="width:${(v*100).toFixed(2)}%;background:${c}" title="${lab} ${(v*100).toFixed(1)}%">${v>0.06?(v*100).toFixed(0)+'%':''}</div>`));
    leg.appendChild(el(`<span><b style="color:${c}">\u25a0</b> ${lab} ${(v*100).toFixed(1)}%</span>`));
  });
  const stat=(l,v,s,c)=>`<div class="stat" style="border-color:${c||'var(--rule)'}"><div class="lab">${l}</div><div class="val" style="color:${c||'var(--ink)'}">${v}</div><div class="sub">${s}</div></div>`;
  document.getElementById('expstats').innerHTML =
    stat('Factor tilt',(g.tilt*100).toFixed(0)+'%','in dedicated factor funds, rest is plain market beta','var(--path)') +
    stat('Cash',money(D.summary.total_cash),'idle cash earns nothing \u2014 keep it near zero') +
    stat('Currency','Unhedged','assets in USD and local, spending in '+D.ccy,'var(--coast)');
})();

/* ---------- drift from target + next-buy allocator ---------- */
(function(){
  const T = D.targets || {};
  const tickers = Object.keys(T);
  if(!tickers.length) return;
  document.getElementById('driftsection').hidden = false;

  const held = {};
  D.positions.forEach(p=>{ held[p.ticker] = (held[p.ticker]||0) + p.market_value; });
  const total = D.positions.reduce((s,p)=>s+p.market_value,0);

  /* union of targeted and held tickers: something held but untargeted must not vanish */
  const rows = Array.from(new Set([...tickers, ...Object.keys(held)])).map(tk=>{
    const tgt = T[tk] || 0;
    const val = held[tk] || 0;
    const act = total ? val/total : 0;
    return {tk, tgt, val, act, drift: act-tgt, atTarget: tgt*total, gap: tgt*total - val};
  }).sort((a,b)=> b.tgt-a.tgt || b.val-a.val);

  const worst = rows.reduce((m,r)=> Math.abs(r.drift)>Math.abs(m.drift)?r:m, rows[0]);
  document.getElementById('driftk').textContent =
    `largest gap ${worst.tk} ${worst.drift>=0?'+':'−'}${(Math.abs(worst.drift)*100).toFixed(1)}pp`;

  const tb=document.querySelector('#drifttbl tbody');
  rows.forEach(r=>{
    const untargeted = !(r.tk in T);
    const unheld = r.val===0;
    const dcls = Math.abs(r.drift)<0.01 ? '' : (r.drift>0?'neg':'pos'); /* over target = red, under = green (buy here) */
    tb.appendChild(el(`<tr${unheld?' style="opacity:.72"':''}>
      <td class="l" style="font-weight:600;font-size:14px">${r.tk}${unheld?' <span style="font-weight:400;font-size:10px;color:var(--muted)">not yet held</span>':''}</td>
      <td>${untargeted?'<span style="color:var(--warn)">none</span>':(r.tgt*100).toFixed(1)+'%'}</td>
      <td>${(r.act*100).toFixed(1)}%</td>
      <td class="${dcls}">${r.drift>=0?'+':'−'}${(Math.abs(r.drift)*100).toFixed(1)}pp</td>
      <td>${nf.format(r.val)}</td>
      <td style="color:var(--muted)">${untargeted?'—':nf.format(r.atTarget)}</td>
      <td class="${r.gap>0?'pos':''}">${untargeted?'—':(r.gap>=0?'+':'−')+nf.format(Math.abs(r.gap))}</td></tr>`));
  });

  /* buy-only allocator: fill the biggest shortfalls first, remainder pro-rata by target */
  function allocate(amount){
    const newTotal = total + amount;
    const gaps = rows.filter(r=> r.tk in T).map(r=>({tk:r.tk, tgt:r.tgt, val:r.val,
      need: Math.max(0, r.tgt*newTotal - r.val)}));
    const needSum = gaps.reduce((s,g)=>s+g.need,0);
    let alloc = {};
    if(needSum<=0){
      gaps.forEach(g=>{ alloc[g.tk] = amount*g.tgt; });           /* already at target: keep weights */
    } else if(needSum<=amount){
      gaps.forEach(g=>{ alloc[g.tk] = g.need; });                  /* close every gap ... */
      const left = amount-needSum;
      gaps.forEach(g=>{ alloc[g.tk] += left*g.tgt; });             /* ... then spread the rest */
    } else {
      gaps.forEach(g=>{ alloc[g.tk] = amount*g.need/needSum; });   /* partial fill, proportional to shortfall */
    }
    return {alloc, newTotal};
  }

  const amtInput=document.getElementById('buyamt');
  const lastFlow = (D.flows&&D.flows.length) ? D.flows[D.flows.length-1].amount : 0;
  const planned = D.plan.phases[0].monthly_income*D.plan.phases[0].savings_rate;
  const dflt = Math.max(50, Math.round((lastFlow||planned)/50)*50);
  amtInput.max = Math.max(10000, Math.ceil(dflt*3/1000)*1000);
  amtInput.value = dflt;

  function drawBuys(){
    const amount = parseFloat(amtInput.value);
    document.getElementById('buyamtv').textContent = money(amount);
    const {alloc, newTotal} = allocate(amount);
    const tb2=document.querySelector('#buytbl tbody');
    tb2.innerHTML='';
    const entries = Object.entries(alloc).filter(([,v])=>v>0.005).sort((a,b)=>b[1]-a[1]);
    if(!entries.length){ tb2.appendChild(el('<tr><td class="l" colspan="5" style="color:var(--muted)">Nothing to buy at this amount.</td></tr>')); }
    entries.forEach(([tk,v])=>{
      const after = ((held[tk]||0)+v)/newTotal;
      const tgt = T[tk];
      const closes = Math.abs(after-tgt) < Math.abs(((held[tk]||0)/(total||1))-tgt);
      tb2.appendChild(el(`<tr>
        <td class="l" style="font-weight:600;font-size:14px">${tk}</td>
        <td style="font-weight:600">${money(v)}</td>
        <td>${(v/amount*100).toFixed(1)}%</td>
        <td>${(after*100).toFixed(1)}% <span style="color:var(--muted);font-size:11px">vs ${(tgt*100).toFixed(1)}% target</span></td>
        <td class="l role">${closes?'closes the gap':''}</td></tr>`));
    });
    const spent = Object.values(alloc).reduce((s,v)=>s+v,0);
    const maxDriftAfter = Math.max(...Object.keys(T).map(tk=>{
      const after=((held[tk]||0)+(alloc[tk]||0))/newTotal; return Math.abs(after-T[tk]);
    }));
    document.getElementById('buynote').innerHTML =
      `Allocates ${money(spent)} of ${money(amount)}. Largest remaining drift after this buy: `+
      `<b>${(maxDriftAfter*100).toFixed(1)}pp</b>. Fractional shares assumed; round to whole shares if your order type needs it.`;
  }
  amtInput.addEventListener('input', drawBuys);
  drawBuys();
})();

/* ---------- contributions vs growth ---------- */
(function(){
  const S=D.series, F=D.flows||[];
  if(!S.length || !F.length) return;
  document.getElementById('growthsection').hidden = false;

  /* cumulative contributed at each observation date */
  let fi=0, run=0;
  const contrib = S.map(p=>{
    while(fi<F.length && F[fi].t<=p.t){ run+=F[fi].amount; fi++; }
    return run;
  });
  const totalIn = F.reduce((s,f)=>s+f.amount,0);
  const finalNav = S[S.length-1].nav;
  const growth = finalNav - totalIn;
  const growthPc = totalIn ? growth/totalIn : 0;

  document.getElementById('growthk').textContent =
    `${F.length} transfers · ${nf.format(Math.round(totalIn))} in · ${growth>=0?'+':'−'}${nf.format(Math.abs(Math.round(growth)))} growth`;

  /* worst point relative to money paid in — honest counterweight to the headline.
     This is an unrealised paper loss, never a negative balance. */
  let worst=Infinity, worstT=null, worstNav=null, worstIn=null;
  S.forEach((p,i)=>{ const g=p.nav-contrib[i]; if(g<worst){worst=g; worstT=p.t; worstNav=p.nav; worstIn=contrib[i];} });
  const everBelowCost = worst < 0;

  const stat=(l,v,s,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${s}</div></div>`;
  document.getElementById('growthstats').innerHTML =
    stat('You put in', money(totalIn), `across ${F.length} transfers`,'var(--coast)') +
    stat('The market added', (growth>=0?'':'−')+money(Math.abs(growth)),
         `${pc(growthPc)} on what you contributed`, growth>=0?'var(--path)':'var(--warn)') +
    stat(everBelowCost?'Worst paper loss':'Never below cost',
         everBelowCost?('−'+money(Math.abs(worst))):money(worst),
         everBelowCost
           ? `on ${new Date(worstT).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})} it was worth ${money(worstNav)} against ${money(worstIn)} paid in — unrealised, the balance stayed positive`
           : 'the portfolio has never been worth less than you paid in',
         everBelowCost?'var(--warn)':'var(--path)');

  /* chart: total NAV area, with contributed area layered on top */
  const t0=S[0].t, t1=S[S.length-1].t;
  const hi=Math.max(finalNav, ...S.map(p=>p.nav))*1.08;
  const stepY=hi/5, yt=[]; for(let i=0;i<=5;i++) yt.push(stepY*i);
  const xt=[]; for(let i=0;i<=4;i++) xt.push(t0+(t1-t0)*i/4);
  chart(document.getElementById('growthchart'),{
    height:260, xmin:t0, xmax:t1, ymin:0, ymax:hi, yticks:yt, xticks:xt,
    yfmt:v=> v>=1e6 ? (v/1e6).toFixed(1)+'M' : Math.round(v/1000)+'k',
    xfmt:v=>new Date(v).toLocaleDateString('en-GB',{month:'short',year:'2-digit'}),
    aria:'portfolio value split into contributions and market growth',
    tip:{fmt:v=>money(v), xfmt:v=>new Date(v).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})},
    series:[
      {name:'Total value',data:S.map(p=>[p.t,p.nav]),color:'var(--path)',w:2.2,fill:true,fillOpacity:0.20},
      {name:'Contributed',data:S.map((p,i)=>[p.t,contrib[i]]),color:'var(--coast)',w:1.8,fill:true,fillOpacity:0.42}
    ]
  });

  const tb=document.querySelector('#flowtbl tbody');
  let acc=0;
  F.forEach((f,i)=>{
    acc+=f.amount;
    const d=new Date(f.t).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
    const note = i===0 ? 'opening transfer' : '';
    tb.appendChild(el(`<tr>
      <td class="l">${d}</td>
      <td class="${f.amount>=0?'pos':'neg'}" style="font-weight:600">${f.amount>=0?'+':'−'}${nf2.format(Math.abs(f.amount))}</td>
      <td>${nf.format(acc)}</td>
      <td class="l role">${note}</td></tr>`));
  });
})();

/* ---------- MWR table ---------- */
(function(){
  const tb=document.querySelector('#mwrtbl tbody');
  D.returns.forEach(r=>{
    if(!r.available){
      tb.appendChild(el(`<tr><td class="l" style="font-weight:600">${r.label}</td>
        <td colspan="5" class="l" style="color:var(--muted);font-family:Inter,sans-serif;font-size:12px">${r.note}</td></tr>`));
      return;
    }
    const flag = r.extrapolated ? ' <span style="color:var(--muted);font-size:10px">extrapolated</span>' : '';
    const dim = r.clamped ? ' style="opacity:.45"' : '';
    const tail = r.note ? r.note : r.days + ' days';
    tb.appendChild(el(`<tr${dim}>
      <td class="l" style="font-weight:600">${r.label}</td>
      <td class="${r.cumulative>=0?'pos':'neg'}" style="font-weight:600">${pc(r.cumulative)}</td>
      <td class="${r.annualised>=0?'pos':'neg'}">${pc(r.annualised)}${flag}</td>
      <td>${nf.format(r.net_contributed)}</td>
      <td>${nf.format(r.closing_nav)}</td>
      <td class="l role">${tail}</td></tr>`));
  });
})();

/* ---------- tiny SVG chart helper ---------- */
function chart(host, opts){
  const W=760, H=opts.height||320, ml=54, mr=14, mt=10, mb=28;
  const xs=opts.xmin, xe=opts.xmax;
  let ymin=opts.ymin, ymax=opts.ymax;
  const logs = !!opts.log;
  const tx = v => ml + (v-xs)/(xe-xs)*(W-ml-mr);
  const ty = v => {
    if(logs){ const a=Math.log10(Math.max(v,ymin)), lo=Math.log10(ymin), hi=Math.log10(ymax);
      return mt + (1-(a-lo)/(hi-lo))*(H-mt-mb); }
    return mt + (1-(v-ymin)/(ymax-ymin))*(H-mt-mb);
  };
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.aria||'chart'}">`;
  (opts.yticks||[]).forEach(t=>{
    s+=`<line x1="${ml}" y1="${ty(t)}" x2="${W-mr}" y2="${ty(t)}" stroke="var(--rule)" stroke-width="1"/>`;
    s+=`<text class="axl" x="${ml-8}" y="${ty(t)+3.5}" text-anchor="end">${opts.yfmt(t)}</text>`;
  });
  (opts.xticks||[]).forEach(t=>{
    s+=`<text class="axl" x="${tx(t)}" y="${H-8}" text-anchor="middle">${opts.xfmt(t)}</text>`;
  });
  (opts.bands||[]).forEach(b=>{
    s+=`<rect x="${tx(b[0])}" y="${mt}" width="${Math.max(0,tx(b[1])-tx(b[0]))}" height="${H-mt-mb}" fill="${b[2]}" opacity="0.08"/>`;
  });
  (opts.vlines||[]).forEach(v=>{
    s+=`<line x1="${tx(v[0])}" y1="${mt}" x2="${tx(v[0])}" y2="${H-mb}" stroke="${v[2]||'var(--muted)'}" stroke-width="1" stroke-dasharray="2 3"/>`;
    if(v[1]) s+=`<text class="axl" x="${tx(v[0])+4}" y="${mt+11}" fill="${v[2]||'var(--muted)'}">${v[1]}</text>`;
  });
  (opts.series||[]).forEach(ser=>{
    const pts=ser.data.filter(p=>p[1]!=null).map(p=>`${tx(p[0]).toFixed(1)},${ty(p[1]).toFixed(1)}`).join(' ');
    if(ser.fill){
      s+=`<polygon points="${tx(xs)},${ty(ymin)} ${pts} ${tx(xe)},${ty(ymin)}" fill="${ser.color}" opacity="${ser.fillOpacity||0.13}"/>`;
    }
    s+=`<polyline points="${pts}" fill="none" stroke="${ser.color}" stroke-width="${ser.w||2}"
        ${ser.dash?`stroke-dasharray="${ser.dash}"`:''} stroke-linejoin="round"/>`;
  });
  (opts.dots||[]).forEach(d=>{
    s+=`<circle cx="${tx(d[0])}" cy="${ty(d[1])}" r="4.5" fill="${d[2]}" stroke="var(--panel)" stroke-width="2"/>`;
  });

  /* hover layer: crosshair + per-series markers, driven by the plot rect */
  const named=(opts.series||[]).filter(sr=>sr.name && sr.data && sr.data.length);
  if(named.length){
    s+=`<g class="cross" style="opacity:0">
          <line x1="0" y1="${mt}" x2="0" y2="${H-mb}" stroke="var(--ink)" stroke-width="1" stroke-dasharray="3 3"/>`;
    named.forEach(sr=>{ s+=`<circle r="4" fill="${sr.color}" stroke="var(--panel)" stroke-width="1.6" cx="-99" cy="-99"/>`; });
    s+=`</g><rect class="hit" x="${ml}" y="${mt}" width="${W-ml-mr}" height="${H-mt-mb}" fill="transparent"/>`;
  }
  s+='</svg>';

  host.classList.add('chartwrap');
  host.innerHTML=s;
  if(!named.length) return;

  const svg=host.querySelector('svg'), g=host.querySelector('.cross'), hit=host.querySelector('.hit');
  const marks=[...g.querySelectorAll('circle')];
  const tip=document.createElement('div'); tip.className='tipbox'; host.appendChild(tip);
  const vfmt = (opts.tip&&opts.tip.fmt) || opts.yfmt || (v=>String(v));
  const lfmt = (opts.tip&&opts.tip.xfmt) || opts.xfmt || (v=>String(v));

  /* screen px -> viewBox units, so it stays correct at any rendered width */
  const toViewBox = evt => {
    const pt=svg.createSVGPoint(); pt.x=evt.clientX; pt.y=evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  };

  function move(evt){
    const p=toViewBox(evt);
    const xv = xs + (p.x-ml)/(W-ml-mr)*(xe-xs);
    let rows='', anyY=[];
    named.forEach((sr,i)=>{
      let best=null, bd=Infinity;
      for(const d of sr.data){ if(d[1]==null) continue; const dist=Math.abs(d[0]-xv); if(dist<bd){bd=dist; best=d;} }
      if(!best){ marks[i].setAttribute('cx',-99); return; }
      marks[i].setAttribute('cx', tx(best[0])); marks[i].setAttribute('cy', ty(best[1]));
      anyY.push(best[0]);
      rows+=`<span class="tr"><span style="color:${sr.color}">■</span>&nbsp;${sr.name}<b>${vfmt(best[1])}</b></span>`;
    });
    if(!anyY.length) return;
    const xSnap=anyY[0];
    g.style.opacity=1;
    g.querySelector('line').setAttribute('x1',tx(xSnap));
    g.querySelector('line').setAttribute('x2',tx(xSnap));
    tip.innerHTML=`<span class="tt">${lfmt(xSnap)}</span>${rows}`;
    tip.style.opacity=1;
    const frac=(tx(xSnap)-ml)/(W-ml-mr);
    const hostW=host.clientWidth;
    tip.style.left = Math.min(Math.max(frac*hostW - tip.offsetWidth/2, 4), Math.max(4,hostW-tip.offsetWidth-4))+'px';
    tip.style.top  = '6px';
  }
  hit.addEventListener('mousemove',move);
  hit.addEventListener('mouseleave',()=>{ g.style.opacity=0; tip.style.opacity=0; });
}

/* ---------- NAV / return chart ---------- */
(function(){
  const S=D.series; if(!S.length) return;
  const t0=S[0].t, t1=S[S.length-1].t;
  const vals=S.map(p=>p.cps*100);
  let lo=Math.min(0,...vals), hi=Math.max(0,...vals);
  const pad=(hi-lo)*0.12||1; lo-=pad; hi+=pad;
  const step=Math.max(1,Math.round((hi-lo)/5));
  const yt=[]; for(let v=Math.ceil(lo/step)*step; v<=hi; v+=step) yt.push(v);
  const xt=[]; const span=t1-t0;
  for(let i=0;i<=4;i++) xt.push(t0+span*i/4);
  chart(document.getElementById('navchart'),{
    height:230, xmin:t0, xmax:t1, ymin:lo, ymax:hi, yticks:yt, xticks:xt,
    yfmt:v=>v.toFixed(0)+'%',
    xfmt:v=>new Date(v).toLocaleDateString('en-GB',{month:'short',year:'2-digit'}),
    aria:'cumulative return since inception',
    tip:{fmt:v=>v.toFixed(2)+'%', xfmt:v=>new Date(v).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})},
    series:[{name:'Cumulative',data:S.map(p=>[p.t,p.cps*100]),color:'var(--path)',w:2,fill:true}]
  });
})();


/* ---------- currency ---------- */
(function(){
  const F = D.fx; if(!F) return;
  document.getElementById('ccysection').hidden = false;
  document.getElementById('ccyk').textContent = F.pair + ' \u00b7 ECB reference rates';

  const done = F.splits.filter(s=>s.available);
  const main = done.length ? done[done.length-1] : null;

  const stat=(l,v,s,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${s}</div></div>`;
  if(main){
    const share = main.currency_share;
    document.getElementById('ccystats').innerHTML =
      stat('From the assets', pc(main.asset), `what the funds did, measured in ${F.asset_currency}`,'var(--path)') +
      stat('From the currency', pc(main.currency), `${F.pair} over the same window`,'var(--fire)') +
      stat('Currency share of return',
           share===null ? '\u2014' : (share*100).toFixed(0)+'%',
           share===null ? 'total return too near zero to attribute'
             : (Math.abs(share)>0.5 ? 'most of your return was the exchange rate, not the funds'
                                    : 'the funds did the heavier lifting'),
           Math.abs(share||0)>0.5 ? 'var(--warn)' : 'var(--coast)');
  }

  const tb=document.querySelector('#ccytbl tbody');
  F.splits.forEach(r=>{
    if(!r.available){
      tb.appendChild(el(`<tr><td class="l" style="font-weight:600">${r.label}</td>
        <td colspan="5" class="l" style="color:var(--muted);font-family:Inter,sans-serif;font-size:12px">${r.note}</td></tr>`));
      return;
    }
    const sh = r.currency_share===null ? '\u2014' : (r.currency_share*100).toFixed(0)+'%';
    tb.appendChild(el(`<tr>
      <td class="l" style="font-weight:600">${r.label}</td>
      <td class="${r.total>=0?'pos':'neg'}" style="font-weight:600">${pc(r.total)}</td>
      <td class="${r.asset>=0?'pos':'neg'}">${pc(r.asset)}</td>
      <td class="${r.currency>=0?'pos':'neg'}">${pc(r.currency)}</td>
      <td style="color:var(--muted)">${pc(r.interaction)}</td>
      <td>${sh}</td></tr>`));
  });

  /* rate chart */
  const S=F.rate_series;
  if(S.length>1){
    document.getElementById('ratelbl').textContent = `${F.pair} \u2014 ${F.rate_first.toFixed(4)} to ${F.rate_last.toFixed(4)}`;
    const t0=S[0].t, t1=S[S.length-1].t;
    const vs=S.map(p=>p.r); let lo=Math.min(...vs), hi=Math.max(...vs);
    const pad=(hi-lo)*0.15||0.01; lo-=pad; hi+=pad;
    const yt=[]; for(let i=0;i<=4;i++) yt.push(lo+(hi-lo)*i/4);
    const xt=[]; for(let i=0;i<=3;i++) xt.push(t0+(t1-t0)*i/3);
    chart(document.getElementById('ratechart'),{
      height:200, xmin:t0, xmax:t1, ymin:lo, ymax:hi, yticks:yt, xticks:xt,
      yfmt:v=>v.toFixed(3),
      xfmt:v=>new Date(v).toLocaleDateString('en-GB',{month:'short',year:'2-digit'}),
      aria:'exchange rate over the holding period',
      tip:{fmt:v=>v.toFixed(4), xfmt:v=>new Date(v).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})},
      series:[{name:F.pair,data:S.map(p=>[p.t,p.r]),color:'var(--fire)',w:2}]
    });
  }

  /* basket - only if config actually describes what is inside the funds held */
  const classified = F.basket.filter(b=>b.ccy!=='Unclassified');
  if(!classified.length){
    const bp=document.getElementById('basketpanel');
    if(bp) bp.hidden = true;
    return;
  }
  const palette=['var(--path)','var(--coast)','var(--fire)','#6B7F6E','#9A7B4F','#5A6B7C','#8C3A2E','#B0B5AE'];
  const bk=document.getElementById('basket'), bl=document.getElementById('basketlegend');
  F.basket.forEach((b,i)=>{
    const c=palette[i%palette.length];
    bk.appendChild(el(`<div style="width:${(b.weight*100).toFixed(2)}%;background:${c}" title="${b.ccy} ${(b.weight*100).toFixed(1)}%">${b.weight>0.09?(b.weight*100).toFixed(0)+'%':''}</div>`));
    bl.appendChild(el(`<span><b style="color:${c}">\u25a0</b> ${b.ccy} ${(b.weight*100).toFixed(1)}%</span>`));
  });
  const home = F.basket.find(b=>b.ccy===F.display_currency);
  const hw = home ? home.weight : 0;
  document.getElementById('homecurrency').appendChild(el(
    `<div class="stat" style="border-color:var(--warn)">
      <div class="lab">Held in ${F.display_currency}, the currency you will spend</div>
      <div class="val" style="color:var(--warn)">${(hw*100).toFixed(1)}%</div>
      <div class="sub">${((1-hw)*100).toFixed(1)}% of your wealth is denominated in currencies you do not spend. That is normal for a global portfolio and it is a real risk, not a rounding error.</div>
    </div>`));
})();

/* ---------- projection ---------- */
const state = JSON.parse(JSON.stringify(D.plan));

function project(){
  const r = state.real_return, m = Math.pow(1+r,1/12)-1;
  const T = state.target, fullAge = state.coast_full_age;
  const coastAt = a => a>=fullAge ? T : T/Math.pow(1+r, fullAge-a);
  let bal = D.summary.net_liquidation, age = D.age_now, contributed = 0;
  const rows=[]; let coastAge=null, fireAge=null;
  const phaseMarks=[];
  const endAge = Math.max(fullAge+7, 62);
  const nMonths = Math.round((endAge-age)*12);

  const ph = state.phases;
  ph.forEach(p=>{ if(p.start_month>0) phaseMarks.push([D.age_now+p.start_month/12, p.label]); });

  for(let t=0;t<=nMonths;t++){
    const a = D.age_now + t/12;
    if(coastAge===null && bal>=coastAt(a)) coastAge=a;
    if(fireAge===null && bal>=T) fireAge=a;
    if(t%6===0) rows.push({age:a, bal:bal, coast:coastAt(a), contributed:contributed});
    bal *= 1+m;
    let c = 0;
    for(let i=ph.length-1;i>=0;i--){
      const p=ph[i];
      if(t>=p.start_month && (p.end_month===null || t<=p.end_month)){
        const yrs=(t-p.start_month)/12;
        c = p.monthly_income * p.savings_rate * Math.pow(1+(p.income_growth||0), yrs);
        break;
      }
    }
    bal += c; contributed += c;
  }
  return {rows, coastAge, fireAge, phaseMarks, finalTarget:T};
}

function drawProjection(){
  const P = project();
  const T = state.target;

  const stat=(l,v,s,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${s}</div></div>`;
  document.getElementById('crossstats').innerHTML =
    stat('Coast FIRE reached', P.coastAge?('age '+P.coastAge.toFixed(1)):'not reached',
      P.coastAge?`stop saving here, still hit ${money(T)} at ${state.coast_full_age}`:'raise saving or lower the bar','var(--coast)') +
    stat('Full FIRE reached', P.fireAge?('age '+P.fireAge.toFixed(1)):'not reached',
      P.fireAge?`${money(T)} in today's money`:'not on this path','var(--fire)');

  const yrsToFire = P.fireAge ? (P.fireAge - D.age_now) : null;
  document.getElementById('goalstats').innerHTML = `
    <div><div class="lab" style="color:#8A959C">Annual income at target</div>
      <div style="font-family:Archivo;font-weight:700;font-size:27px;margin-top:3px;color:#7FBFA5">${money(T*state.withdrawal_rate)}</div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${(state.withdrawal_rate*100).toFixed(2)}% withdrawal rate</div></div>
    <div><div class="lab" style="color:#8A959C">Saving right now</div>
      <div style="font-family:Archivo;font-weight:700;font-size:27px;margin-top:3px">${money(state.phases[0].monthly_income*state.phases[0].savings_rate)}<span style="font-size:14px">/mo</span></div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${(state.phases[0].savings_rate*100).toFixed(0)}% of ${money(state.phases[0].monthly_income)} income</div></div>
    <div><div class="lab" style="color:#8A959C">Years to target</div>
      <div style="font-family:Archivo;font-weight:700;font-size:27px;margin-top:3px;color:#E8A05E">${yrsToFire?yrsToFire.toFixed(0):'\u2014'}</div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${yrsToFire?('from today, age '+D.age_now.toFixed(0)):'unreachable on these inputs'}</div></div>`;

  const maxY = Math.max(T*1.12, ...P.rows.map(r=>r.bal));
  const ageMin=Math.floor(D.age_now), ageMax=Math.ceil(Math.max(state.coast_full_age+7,62));
  const yt=[]; const stepY = maxY/5;
  for(let i=0;i<=5;i++) yt.push(stepY*i);
  const xt=[]; for(let a=Math.ceil(ageMin/5)*5;a<=ageMax;a+=5) xt.push(a);

  const dots=[];
  if(P.coastAge){const r=P.rows.find(x=>x.age>=P.coastAge); if(r)dots.push([r.age,r.bal,'var(--coast)']);}
  if(P.fireAge){const r=P.rows.find(x=>x.age>=P.fireAge); if(r)dots.push([r.age,r.bal,'var(--fire)']);}

  chart(document.getElementById('projchart'),{
    height:340, xmin:ageMin, xmax:ageMax, ymin:0, ymax:maxY, yticks:yt, xticks:xt,
    yfmt:v=> v>=1e6 ? (v/1e6).toFixed(1)+'M' : Math.round(v/1000)+'k',
    xfmt:v=> v.toFixed(0),
    aria:'portfolio projection against the target and coast threshold',
    vlines:P.phaseMarks.map(m=>[m[0],m[1],'var(--muted)']),
    tip:{fmt:v=>money(v), xfmt:v=>'age '+v.toFixed(1)},
    series:[
      {name:'Target',data:P.rows.map(r=>[r.age,T]),color:'var(--fire)',w:2},
      {name:'Coast threshold',data:P.rows.map(r=>[r.age,r.coast]),color:'var(--coast)',w:1.6,dash:'6 4'},
      {name:'Portfolio',data:P.rows.map(r=>[r.age,r.bal]),color:'var(--path)',w:2.6}
    ],
    dots:dots
  });

  drawMilestones(P);
  drawHero(P);
}

/* ---------- milestones ---------- */
const MS_NOW = D.series.length ? new Date(D.series[D.series.length-1].t) : new Date();

function milestoneLadder(target){
  /* Explicit list from config wins. Otherwise generate a 1/2.5/5 ladder that
     scales to whatever the target is, so this works for a 50k goal and a 10M
     one alike rather than assuming a particular size of ambition. */
  const custom = D.plan && D.plan.milestones;
  if(Array.isArray(custom) && custom.length){
    const out = custom.filter(v=>v>0 && v<target).sort((a,b)=>a-b);
    out.push(target);
    return out;
  }
  const out=[];
  for(let mag=Math.pow(10,Math.floor(Math.log10(Math.max(target,10)))-3); mag<=target; mag*=10){
    [1,2.5,5].forEach(m=>{ const v=mag*m; if(v>0 && v<target) out.push(v); });
  }
  const trimmed = out.sort((a,b)=>a-b).slice(-8);   /* keep the ladder readable */
  trimmed.push(target);
  return trimmed;
}

/* first date the recorded NAV closed at or above `level`, else null */
function reachedOn(level){
  for(const p of D.series){ if(p.nav>=level) return new Date(p.t); }
  return null;
}

/* age at which the projection first reaches `level`, interpolated between rows */
function projectedAge(rows, level){
  for(let i=0;i<rows.length;i++){
    if(rows[i].bal>=level){
      if(i===0) return rows[0].age;
      const a=rows[i-1], b=rows[i];
      const f=(level-a.bal)/((b.bal-a.bal)||1);
      return a.age + f*(b.age-a.age);
    }
  }
  return null;
}

/* ---------- hero band ---------- */
function drawHero(P){
  const net=D.summary.net_liquidation, target=state.target;
  const levels=milestoneLadder(target);
  const F=D.flows||[];
  const totalIn=F.reduce((s,f)=>s+f.amount,0);
  const growth=net-totalIn;
  const since=(D.returns||[]).filter(r=>r.available).pop();
  const yrs=P.fireAge ? (P.fireAge-D.age_now) : null;

  /* Milestones are spaced evenly, not by amount: on a linear money axis a
     22k balance against a 2M target is a sliver that shows nothing. Position
     within the current segment is exact. */
  let seg=levels.findIndex(v=>net<v);
  if(seg<0) seg=levels.length;
  const lo = seg===0 ? 0 : levels[seg-1];
  const hi = seg<levels.length ? levels[seg] : target;
  const within = hi>lo ? Math.min(1,Math.max(0,(net-lo)/(hi-lo))) : 1;
  const pct = ((seg + within)/levels.length)*100;

  const track=document.getElementById('herotrack');
  let h=`<div class="rail"></div><div class="fill" style="width:${Math.min(100,pct).toFixed(2)}%"></div>`;
  levels.forEach((lv,i)=>{
    const x=((i+1)/levels.length)*100;
    const lbl = lv>=1e6 ? (lv/1e6).toFixed(lv%1e6?1:0)+'M' : Math.round(lv/1000)+'k';
    h+=`<div class="tick" style="left:${x}%"><span>${lbl}</span></div>`;
  });
  h+=`<div class="pin" style="left:${Math.min(100,pct).toFixed(2)}%" title="${money(net)}"></div>`;
  track.innerHTML=h;

  const fig=(l,v,s,c)=>`<div class="fig"><div class="lab">${l}</div><div class="num"${c?` style="color:${c}"`:''}>${v}</div><div class="sub">${s}</div></div>`;
  document.getElementById('herofigs').innerHTML =
    fig('Portfolio', money(net), `${(net/target*100).toFixed(1)}% of ${money(target)}`) +
    fig('You contributed', money(totalIn), `${F.length} transfers`,'var(--coast)') +
    fig('Market growth', (growth>=0?'':'−')+money(Math.abs(growth)),
        totalIn?`${pc(growth/totalIn)} on contributions`:'—', growth>=0?'var(--path)':'var(--warn)') +
    fig('Return since start', since?pc(since.cumulative):'—',
        since?`money-weighted · ${since.days} days`:'—', since&&since.cumulative>=0?'var(--path)':'var(--warn)') +
    fig('Target reached', yrs?`${yrs.toFixed(0)} yr`:'—',
        yrs?`age ${P.fireAge.toFixed(0)} on current inputs`:'not on this path','var(--fire)');
}

function drawMilestones(P){
  const tb=document.querySelector('#mstbl tbody');
  if(!tb) return;
  tb.innerHTML='';
  const levels=milestoneLadder(state.target);
  const nav=D.summary.net_liquidation;
  let reachedCount=0;

  levels.forEach(lv=>{
    const done = nav>=lv;
    if(done) reachedCount++;
    const isTarget = Math.abs(lv-state.target)<1;
    let when='', from='', note='';

    if(done){
      const d=reachedOn(lv);
      if(d){
        when=d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
        const days=Math.round((MS_NOW-d)/86400000);
        from = days<=0 ? 'today' : `${days} d ago`;
      } else {
        when='before this history starts';
        from='—';
        note='crossed before the earliest recorded NAV';
      }
    } else {
      const age=projectedAge(P.rows, lv);
      if(age===null){ when='not on this path'; from='—'; note='raise saving or lower the bar'; }
      else{
        const yrs=age-D.age_now;
        const d=new Date(MS_NOW.getTime()+yrs*365.25*86400000);
        when=d.toLocaleDateString('en-GB',{month:'short',year:'numeric'})+` · age ${age.toFixed(1)}`;
        from = yrs<1 ? `${Math.round(yrs*12)} mo` : `${yrs.toFixed(1)} yr`;
        note='projected';
      }
    }
    tb.appendChild(el(`<tr${done?'':' style="opacity:.82"'}>
      <td class="l" style="font-weight:600${isTarget?';color:var(--fire)':''}">${money(lv)}${isTarget?' <span style="font-size:10px;font-weight:400">target</span>':''}</td>
      <td class="l" style="color:${done?'var(--path)':'var(--muted)'};font-weight:${done?'600':'400'}">${done?'reached':'ahead'}</td>
      <td class="l">${when}</td>
      <td>${from}</td>
      <td class="l role">${note}</td></tr>`));
  });

  const nextUp = levels.find(lv=>nav<lv);
  document.getElementById('msk').textContent =
    `${reachedCount} of ${levels.length} reached` + (nextUp?` · next ${money(nextUp)}`:'');
}

/* ---------- controls ---------- */
function slider(id,label,val,min,max,step,fmt,note,onIn){
  const w=el(`<div class="ctl">
    <div class="row"><label for="${id}">${label}</label><span class="v" id="${id}v">${fmt(val)}</span></div>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}">
    ${note?`<div class="note">${note}</div>`:''}</div>`);
  const inp=w.querySelector('input');
  inp.addEventListener('input',()=>{
    const v=parseFloat(inp.value);
    w.querySelector('.v').textContent=fmt(v);
    onIn(v); drawProjection(); refreshDerived();
  });
  return w;
}

function refreshDerived(){
  state.phases.forEach((p,i)=>{
    const d=document.getElementById('deriv'+i);
    if(d) d.textContent = `\u2192 saving ${money(p.monthly_income*p.savings_rate)}/mo`;
  });
}

(function(){
  const host=document.getElementById('controls');
  state.phases.forEach((p,i)=>{
    const block=el(`<div class="phase"><div class="ph">${p.label}</div><div class="pd">${p.range_label}</div>
      <div class="derived" id="deriv${i}"></div></div>`);
    block.appendChild(slider('inc'+i,'Monthly income',p.monthly_income,0,15000,100,
      v=>money(v), null, v=>{p.monthly_income=v;}));
    block.appendChild(slider('sav'+i,'Savings rate',p.savings_rate,0,1,0.01,
      v=>(v*100).toFixed(0)+'%', null, v=>{p.savings_rate=v;}));
    if(p.end_month===null){
      block.appendChild(slider('gro'+i,'Income growth',p.income_growth||0,0,0.05,0.0025,
        v=>(v*100).toFixed(2)+'%/yr real','Real career progression above inflation.',v=>{p.income_growth=v;}));
    }
    host.appendChild(block);
  });

  const g=el(`<div style="border-top:1px solid var(--rule);padding-top:20px;margin-top:4px"></div>`);
  g.appendChild(slider('tgt','Target',state.target,250000,5000000,50000,
    v=>money(v),'The number you are aiming at.',v=>{state.target=v;}));
  g.appendChild(slider('ret','Real return',state.real_return,0.02,0.08,0.0025,
    v=>(v*100).toFixed(2)+'%','After inflation and fees. 5% is a fair global-equity base case.',v=>{state.real_return=v;}));
  g.appendChild(slider('swr','Withdrawal rate',state.withdrawal_rate,0.025,0.05,0.0005,
    v=>(v*100).toFixed(2)+'%','Sets the income the target funds. 3.25\u20133.75% suits a 50-year retirement.',v=>{state.withdrawal_rate=v;}));
  g.appendChild(slider('cfa','Coast target age',state.coast_full_age,50,65,1,
    v=>String(v),'The age the coast portfolio must reach the target by, unaided.',v=>{state.coast_full_age=v;}));
  host.appendChild(g);
  refreshDerived();
})();

drawProjection();
window.addEventListener('resize',()=>{drawProjection();});
</script></body></html>
"""


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
