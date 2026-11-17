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
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--fn:'Schibsted Grotesk',system-ui,sans-serif;
--ground:#EDF1EF;--panel:#FFFFFF;--ink:#14211C;--muted:#5E6D67;--rule:#D6DED9;
--path:#1E5B46;--fire:#A87414;--coast:#3D5B78;--warn:#B3261E;--soft:#F5F8F6;}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--fn);-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:40px 24px 80px}
.mono{font-family:var(--fn)}
h1{font-family:var(--fn);font-weight:800;font-size:clamp(32px,5.6vw,56px);letter-spacing:-.035em;line-height:.99;margin:0}
h2{font-family:var(--fn);font-weight:700;font-size:20px;letter-spacing:-.01em;margin:0}
.eyebrow{font-family:var(--fn);font-size:11px;color:var(--muted);margin-bottom:10px}
.lede{max-width:640px;margin-top:18px;font-size:15px;line-height:1.6;color:#3C464C}
section{margin-bottom:56px}
.shead{display:flex;gap:14px;align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:10px;margin-bottom:24px;flex-wrap:wrap}
.shead .n{font-family:var(--fn);font-size:12px;color:var(--muted)}
.shead .k{font-size:12px;color:var(--muted);margin-left:auto;text-align:right}
table{width:100%;border-collapse:collapse;font-family:var(--fn);font-size:13px}
th{text-align:right;padding:8px 10px;color:var(--muted);font-size:10.5px;font-weight:500;border-bottom:1px solid var(--rule)}
th.l,td.l{text-align:left}
td{text-align:right;padding:11px 10px;border-bottom:1px solid var(--rule)}
td.role{color:var(--muted);font-size:11.5px;font-family:var(--fn)}
.pos{color:var(--path)}.neg{color:var(--warn)}
.bar{display:inline-block;width:46px;height:5px;background:var(--rule);margin-right:8px;vertical-align:middle;position:relative}
.bar i{position:absolute;inset:0;background:var(--path)}
.panel{background:var(--panel);border:1px solid var(--rule);padding:22px 24px}
.dark{background:var(--ink);color:var(--panel);padding:24px 26px}
.grid{display:grid;gap:20px}
.g3{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.stat{border-left:2px solid var(--rule);padding-left:12px}
.stat .lab{font-size:10.5px;color:var(--muted);font-family:var(--fn)}
.stat .val{font-family:var(--fn);font-weight:700;font-size:26px;line-height:1.15;letter-spacing:-.02em;margin-top:3px}
.stat .sub{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.geo{display:flex;height:34px;border:1px solid var(--ink)}
.geo div{display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:600;font-family:var(--fn)}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:11.5px;color:var(--muted)}
.cols{display:grid;grid-template-columns:minmax(250px,320px) minmax(0,1fr);gap:34px;align-items:start}
@media(max-width:860px){.cols{grid-template-columns:1fr}}
.tk{font-family:var(--fn);font-weight:600;font-size:15.5px;line-height:1.38;margin:0 6px 12px;color:var(--ink);max-width:720px}
.tk b{color:var(--path)} .tk b.neg{color:var(--warn)}
.glance{border:1px solid var(--rule);background:var(--panel);padding:18px 22px;margin:0 0 40px}
.glance ul{margin:8px 0 0;padding:0;list-style:none}
.glance li{font-size:14.5px;line-height:1.5;padding:5px 0;border-top:1px solid var(--rule)}
.glance li:first-child{border-top:0}
.glance li b{font-weight:600}
.plansimple [data-detail]{display:none!important}
.cols2{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:18px;align-items:start}
@media(max-width:860px){.cols2{grid-template-columns:1fr}}
.mcv{font-family:var(--fn);font-weight:700;font-size:21px;margin:2px 0}
table.sens td,table.sens th{text-align:center;padding:7px 6px;font-size:12px}
table.sens th.l{text-align:left;white-space:nowrap}
table.sens .cur{outline:2px solid var(--ink);outline-offset:-2px;font-weight:700}
table.heat td{text-align:center;padding:5px 3px;font-size:11px;min-width:38px}
table.heat td.part{font-style:italic;opacity:.75}
details.pen{border-top:1px solid var(--rule);padding-top:14px;margin-top:6px}
details.pen summary{cursor:pointer;font-family:var(--fn);font-size:10.5px;font-weight:600}
.pengrid{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px;margin-top:10px}
.pengrid label{font-size:11.5px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
.pengrid input{font:inherit;font-size:13px;padding:5px 7px;border:1px solid var(--rule);background:var(--panel);color:var(--ink);border-radius:3px;width:100%;box-sizing:border-box}
.pengrid .h{grid-column:1/-1;font-weight:600;color:var(--ink);font-size:12px;margin-top:6px}
.phase{border-left:2px solid var(--path);padding-left:12px;margin-bottom:24px}
.phase .ph{font-family:var(--fn);font-size:10.5px;font-weight:600;margin-bottom:2px}
.phase .pd{font-size:11px;color:var(--muted);margin-bottom:12px}
.ctl{margin-bottom:18px}
.ctl .row{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.ctl label{font-size:11.5px;color:var(--muted);font-family:var(--fn)}
.ctl .v{font-family:var(--fn);font-size:14px;font-weight:600}
input[type=range]{width:100%;height:4px;accent-color:var(--path);background:var(--rule);border-radius:2px;-webkit-appearance:none}
input[type=range]:focus-visible{outline:2px solid var(--path);outline-offset:4px}
.derived{font-size:11px;color:var(--path);font-family:var(--fn);margin-top:5px}
.note{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.45}
svg{display:block;width:100%;height:auto}
.hero{border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);padding:22px 0 20px;margin:34px 0 46px}
.hero .figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:22px 26px}
.hero .fig .lab{font-family:var(--fn);font-size:10px;color:var(--muted)}
.hero .fig .num{font-family:var(--fn);font-weight:700;font-size:23px;letter-spacing:-.02em;margin-top:4px;line-height:1.1}
.hero .fig .sub{font-size:11px;color:var(--muted);margin-top:2px}
.track{position:relative;height:26px;margin-bottom:20px}
.track .rail{position:absolute;top:9px;left:0;right:0;height:8px;background:var(--rule)}
.track .fill{position:absolute;top:9px;left:0;height:8px;background:var(--path)}
.track .tick{position:absolute;top:4px;width:1px;height:18px;background:var(--ground)}
.track .tick span{position:absolute;top:20px;left:0;transform:translateX(-50%);font-family:var(--fn);
  font-size:9px;color:var(--muted);white-space:nowrap}
.track .pin{position:absolute;top:2px;width:2px;height:22px;background:var(--ink)}
.btn{font-family:var(--fn);font-size:11.5px;background:transparent;border:1px solid var(--ink);color:var(--ink);padding:7px 12px;cursor:pointer;border-radius:2px}
.btn:hover{background:var(--ink);color:var(--panel)}
.btn.ghost{border-color:var(--rule);color:#3C464C}
.btn.ghost:hover{background:var(--rule);color:var(--ink)}
.btn:focus-visible,.seg button:focus-visible,.x:focus-visible,.phname:focus-visible{outline:2px solid var(--path);outline-offset:2px}
.btnrow{margin:4px 0 20px}
.planbar{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;font-size:12.5px;color:var(--muted);margin:-8px 0 16px;line-height:1.5}
.phhead{display:flex;align-items:center;gap:4px;margin-bottom:2px}
.phname{flex:1;min-width:0;font-family:var(--fn);font-size:10.5px;font-weight:600;border:0;border-bottom:1px dashed transparent;background:transparent;color:var(--ink);padding:3px 0}
.phname:hover,.phname:focus{border-bottom-color:var(--muted);outline:none}
.x{border:0;background:transparent;color:var(--muted);font-size:17px;line-height:1;cursor:pointer;padding:2px 6px}
.x:hover{color:var(--warn)}
.seg{display:inline-flex;border:1px solid var(--rule);margin:2px 0 14px}
.seg button{font-family:var(--fn);font-size:10.5px;border:0;background:transparent;padding:5px 9px;cursor:pointer;color:var(--muted)}
.seg button.on{background:var(--ink);color:var(--panel)}
.evsec{border-top:1px solid var(--rule);padding-top:18px;margin-top:2px}
.evrow{display:grid;grid-template-columns:minmax(0,1fr) auto 92px auto;gap:8px;align-items:center;margin-top:10px}
.evrow input{font-family:var(--fn);font-size:12px;border:1px solid var(--rule);background:var(--ground);padding:5px 6px;min-width:0;color:var(--ink);border-radius:2px}
.evdate{font-family:var(--fn);font-size:11px;color:var(--muted);white-space:nowrap}
.tl{position:relative;height:104px;user-select:none;-webkit-user-select:none;touch-action:none}
.tl .lane{position:absolute;left:0;right:0;top:4px;height:48px;border:1px dashed var(--rule);box-sizing:border-box;
  background:repeating-linear-gradient(135deg,transparent 0 6px,rgba(121,131,139,.13) 6px 12px)}
.tl .blk{position:absolute;top:4px;height:48px;color:#fff;overflow:hidden;cursor:grab;padding:0 12px;box-sizing:border-box;
  display:flex;flex-direction:column;justify-content:center;box-shadow:inset -1px 0 0 rgba(246,247,244,.55)}
.tl .blk.started{cursor:default}
.tl .blk .nm{font-size:11.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none}
.tl .blk .dt{font-family:var(--fn);font-size:9.5px;opacity:.85;white-space:nowrap;overflow:hidden;pointer-events:none}
.tl .h{position:absolute;top:0;bottom:0;width:11px;cursor:ew-resize;z-index:2}
.tl .h.l{left:0}.tl .h.r{right:0}
.tl .h::after{content:'';position:absolute;top:14px;bottom:14px;left:4px;width:2px;background:rgba(255,255,255,.75)}
.tl .ev{position:absolute;top:60px;width:12px;height:12px;margin-left:-6px;background:var(--fire);transform:rotate(45deg);cursor:grab;z-index:3}
.tl .ev.neg{background:var(--warn)}
.tl .axis{position:absolute;left:0;right:0;top:78px;height:24px}
.tl .axis span{position:absolute;transform:translateX(-50%);font-family:var(--fn);font-size:9.5px;color:var(--muted);white-space:nowrap;text-align:center;line-height:1.2}
.tl [data-act]:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.tl.dragging,.tl.dragging *{cursor:grabbing!important}
.dtip{position:absolute;top:-24px;transform:translateX(-50%);background:var(--ink);color:var(--panel);font-family:var(--fn);
  font-size:11px;padding:3px 8px;white-space:nowrap;pointer-events:none;z-index:5;border-radius:2px}
.modal{position:fixed;inset:0;background:rgba(20,24,26,.55);display:flex;align-items:center;justify-content:center;z-index:50;padding:20px}
.modal .box{background:var(--panel);max-width:720px;width:100%;padding:22px 24px;max-height:90vh;display:flex;flex-direction:column;gap:12px;box-sizing:border-box}
.modal textarea{width:100%;min-height:300px;flex:1;font-family:var(--fn);font-size:11.5px;border:1px solid var(--rule);padding:10px;resize:vertical;box-sizing:border-box;background:var(--ground);color:var(--ink)}
.chartwrap{position:relative}
.tipbox{position:absolute;pointer-events:none;opacity:0;transition:opacity .09s;background:var(--ink);color:var(--panel);
  padding:8px 10px;font-family:var(--fn);font-size:11.5px;line-height:1.5;white-space:nowrap;
  border-radius:2px;z-index:5;box-shadow:0 2px 10px rgba(0,0,0,.18)}
.tipbox .tt{color:#9AA5AC;font-size:10px;display:block;margin-bottom:3px}
.tipbox .tr{display:flex;gap:10px;justify-content:space-between}
.tipbox .tr b{font-weight:600}
.axl{font-family:var(--fn);font-size:10px;fill:var(--muted)}
footer{border-top:1px solid var(--rule);padding-top:20px;font-size:11.5px;color:var(--muted);line-height:1.65;max-width:760px}
.warnbox{background:#F6E9E4;border-left:3px solid var(--warn);padding:12px 16px;font-size:12.5px;line-height:1.5;margin-bottom:24px}

/* ---- design layer: one family, sentence-case labels, soft surfaces ---- */
body{font-family:var(--fn);font-size:15px;line-height:1.5}
.wrap{max-width:1140px;padding:44px 28px 96px;overflow-x:clip}
h1{font-weight:800;letter-spacing:-.04em;line-height:.98}
h1 #h1Target{color:var(--fire)!important}
h2{font-size:24px;font-weight:700;letter-spacing:-.02em}
.eyebrow{font-size:13.5px;font-weight:600;color:var(--ink);margin-bottom:10px}
header .eyebrow{font-weight:500;color:var(--muted)}
.lede{color:#33433D;font-size:16px;max-width:620px}
section{margin-bottom:72px;scroll-margin-top:64px}
.shead{border-bottom:0;padding-bottom:0;margin-bottom:18px;gap:12px}
.shead .n{display:none}
.shead .k{font-size:13px}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:22px 24px}
.dark{border-radius:12px}
table{font-size:13.5px}
th{font-size:12px;font-weight:600;color:var(--muted);padding:8px 10px}
td{padding:11px 10px}
tbody tr:hover td{background:var(--soft)}
.stat{border-left-width:3px;padding-left:14px}
.stat .lab{font-size:12.5px;font-weight:500}
.stat .val{font-weight:700;letter-spacing:-.025em}
.stat .sub{font-size:12px}
.legend{font-size:12.5px}
.note{font-size:12px}
.axl{font-size:11px}
.tk{font-size:17px;font-weight:600;letter-spacing:-.01em;line-height:1.4;max-width:680px}
.glance{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:20px 24px;margin:0 0 56px}
.glance li{font-size:15.5px;padding:8px 0}
.secnav{position:sticky;top:0;z-index:20;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;margin:0 -28px 28px;padding:10px 28px;
  background:rgba(237,241,239,.92);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--rule)}
.secnav::-webkit-scrollbar{display:none}
.secnav a{flex:none;font-size:13.5px;font-weight:500;color:var(--muted);text-decoration:none;padding:6px 11px;border-radius:999px}
.secnav a:hover{color:var(--ink);background:var(--panel)}
.secnav a:focus-visible{outline:2px solid var(--path);outline-offset:1px}
/* the one loud element: the run to the target */
.hero{--path:#74C7A0;--coast:#9DBBD8;--fire:#E5B04F;--warn:#F2958B;border:0;background:var(--ink);color:#E9EFEC;border-radius:16px;padding:30px 30px 26px;margin:30px 0 22px}
.hero .fig .lab{font-size:12.5px;color:#9DB0A8}
.hero .fig .num{font-size:27px;color:#fff}
.hero .fig .sub{font-size:12px;color:#9DB0A8}
.hero > div[style*="font-size:10.5px"]{color:#9DB0A8!important;font-size:12px!important}
.track{height:34px}
.track .rail{top:10px;height:14px;border-radius:7px;background:#2C3B35}
.track .fill{top:10px;height:14px;border-radius:7px;background:linear-gradient(90deg,#2E7A5E,#5FB08C)}
.track .tick{background:var(--ink);top:8px;height:18px}
.track .tick span{top:26px;font-size:11px;color:#9DB0A8}
.track .pin{top:4px;height:26px;width:3px;border-radius:2px;background:var(--fire)}
.btn{font-size:13px;font-weight:600;border-radius:8px;padding:8px 14px}
.seg{border-radius:8px;overflow:hidden}
.seg button{font-size:12.5px;padding:6px 11px}
.ctl label{font-size:12.5px}
.ctl .v{font-size:15px}
.phname{font-size:13px}
.evrow input,.pengrid input{border-radius:6px}
.tipbox{border-radius:8px;font-size:12.5px}
.tipbox .tt{font-size:11.5px}
.tl .blk{border-radius:6px}
.warnbox{border-radius:8px}
.modal .box{border-radius:12px}
@media(max-width:640px){
  .wrap{padding:28px 16px 72px}
  .secnav{margin:0 -16px 22px;padding:10px 16px}
  .hero{padding:22px 18px 20px;border-radius:12px}
  .panel{padding:18px 16px}
  .tk{font-size:16px}
  h2{font-size:21px}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
html{scroll-behavior:smooth}
</style></head><body><div class="wrap">

<header style="margin-bottom:46px">
  <div class="eyebrow">Interactive Brokers snapshot from __ASOF__, in __CCY__, aiming for <span id="ebTarget">__TARGETLBL__</span></div>
  <h1>__NETLIQLBL__ today.<br><span style="color:var(--path)" id="h1Target">__TARGETLBL__</span> is the line.</h1>
  <p class="lede" id="lede">__LEDE__</p>
</header>

<nav class="secnav" aria-label="Sections">
  <a href="#holdings">Holdings</a><a href="#growthsection">Saved vs market</a><a href="#returns">Returns</a>
  <a href="#risksection">Risk and costs</a><a href="#ccysection">Currency</a><a href="#milestones">Milestones</a><a href="#plansection">Plan</a>
</nav>
<div id="staleness"></div>

<div class="hero">
  <div class="track" id="herotrack" title="progress toward the target"></div>
  <div style="font-size:10.5px;color:var(--muted);margin:22px 0 20px;font-family:var(--fn)">
    Milestones are evenly spaced, not to scale. Your position within the current step is exact.</div>
  <div class="figs" id="herofigs"></div>
</div>
<div class="glance" id="glance"><div class="eyebrow" style="margin:0">At a glance</div><ul id="glancelist"></ul></div>

<section id="holdings">
  <div class="shead"><span class="n">01</span><h2>Holdings</h2><span class="k" id="hk"></span></div>
  <div style="overflow-x:auto"><table id="postbl">
    <thead><tr><th class="l">Ticker</th><th class="l">Role</th><th>Units</th><th>Price</th><th>Value</th><th>Weight</th>
      <th class="costcol">Cost</th><th class="costcol" title="Gain against the money put into this position. Reinvested dividends raise the cost basis, so for dividend-payers this sits below the true total return.">Gain on cost</th><th>Unreal. P&amp;L</th></tr></thead>
    <tbody></tbody></table></div>
  <div class="panel" style="margin-top:28px" id="divpanel" hidden>
    <div class="eyebrow" style="margin-bottom:10px">Dividend income</div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin-bottom:16px" id="divstats"></div>
    <div class="cols2"><div id="divq"></div><div style="overflow-x:auto"><table id="divtbl"></table></div></div>
    <div class="note" style="margin-top:10px" id="divnote"></div>
  </div>
  <div class="panel" style="margin-top:28px" id="exposurepanel">
    <div class="eyebrow" style="margin-bottom:4px">True exposure &mdash; fund look-through</div>
    <p style="font-size:12.5px;color:var(--muted);margin:0 0 18px;max-width:560px;line-height:1.5">
      IBKR reports this account as United States / Broad because all the funds are US-domiciled.
      That is a custody fact, not an exposure fact. Regional splits come from <code>config.json</code>.</p>
    <p style="font-size:11.5px;color:var(--muted);margin:-8px 0 18px;max-width:560px;line-height:1.5">
      <b>Gain on cost is not total return.</b> Reinvested dividends buy more shares, which raises the
      cost basis without showing up as a gain &mdash; so for dividend-paying funds this column sits
      below the true total return by roughly the yield since purchase. The portfolio-level returns in
      sections 03 and 04 <i>do</i> include dividends; they come from the NAV series, which reflects them.</p>
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

<section id="returns">
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
  <div class="panel" style="margin-top:24px;padding:18px 14px 8px" id="benchpanel" hidden>
    <div class="eyebrow" style="margin:0 0 10px 6px" id="benchtitle"></div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:0 6px 14px" id="benchstats"></div>
    <div id="benchchart"></div>
    <div class="note" style="margin:8px 6px 4px" id="benchnote"></div>
  </div>
</section>


<section id="risksection" hidden>
  <div class="shead"><span class="n">05</span><h2>Risk and costs</h2><span class="k" id="riskk"></span></div>
  <div id="riskbody">
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin-bottom:18px" id="riskstats"></div>
  <div class="cols2">
    <div class="panel" style="padding:16px 12px 8px">
      <div class="eyebrow" style="margin:0 0 6px 8px">Underwater: how far below its last high</div>
      <div id="ddchart"></div></div>
    <div class="panel" style="padding:16px 18px 12px">
      <div class="eyebrow" style="margin:0 0 8px">Monthly returns</div>
      <div id="heatmap" style="overflow-x:auto"></div>
      <div class="note" style="margin-top:8px">Time-weighted, so deposits don&rsquo;t count as gains. Partial first and last months are marked.</div></div>
  </div>
  </div>
  <div id="feesection" hidden style="margin-top:18px">
    <div class="panel" style="padding:16px 18px 12px">
      <div class="eyebrow" style="margin:0 0 10px">What the funds charge</div>
      <div id="feepanel"></div></div>
  </div>
</section>

<section id="ccysection" hidden>
  <div class="shead"><span class="n">06</span><h2>Currency</h2><span class="k" id="ccyk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 14px;line-height:1.55">
    Your funds are priced in one currency and you will spend another. That gap is not noise: the
    reported return is the asset return multiplied by the exchange-rate move, and the two legs are
    separated below. The identity is exact &mdash; (1&nbsp;+&nbsp;assets) &times; (1&nbsp;+&nbsp;currency)
    reproduces the reported figure with no residual beyond the cross term.</p>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 20px;line-height:1.55">
    <b>These figures are time-weighted, not money-weighted.</b> Splitting a return into asset and
    currency legs only works on a series that ignores deposits, so this section cannot use the
    money-weighted figure from section 04 &mdash; the two will differ whenever the timing of your
    transfers mattered. Neither is wrong: section 04 answers &ldquo;how did my money do&rdquo;,
    this one answers &ldquo;what drove the underlying return&rdquo;.</p>

  <div class="grid g3" id="ccystats" style="margin-bottom:26px"></div>

  <div style="overflow-x:auto"><table id="ccytbl">
    <thead><tr><th class="l">Window</th><th>Time-weighted</th><th>Assets</th><th>Currency</th><th>Cross term</th><th>Currency share</th></tr></thead>
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

<section id="milestones">
  <div class="shead"><span class="n">07</span><h2>Milestones</h2><span class="k" id="msk"></span></div>
  <p style="font-size:12.5px;color:var(--muted);max-width:660px;margin:0 0 22px;line-height:1.55">
    Dates in the past are real &mdash; the day your recorded NAV first closed above the line. Dates in
    the future come from the projection in section 07 and move when you change its sliders, so treat
    them as the shape of the path, not a promise.</p>
  <div style="overflow-x:auto"><table id="mstbl">
    <thead><tr><th class="l">Milestone</th><th class="l">Status</th><th class="l">When</th><th>From today</th><th class="l">&nbsp;</th></tr></thead>
    <tbody></tbody></table></div>
</section>

<section id="plansection">
  <div class="shead"><span class="n">08</span><h2>The two finish lines</h2><span class="k">drag the timeline, change anything &mdash; it all recalculates</span></div>
  <div class="dark" style="margin-bottom:30px"><div class="grid g3" id="goalstats"></div></div>
  <div class="planbar" id="planbar"></div>
  <div class="panel" style="margin-bottom:26px;padding:18px 22px 10px">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap">
      <div class="eyebrow" style="margin-bottom:2px">Your plan</div>
      <div class="seg" id="tlzoom" role="group" aria-label="Timeline range" style="margin:0"></div></div>
    <p style="font-size:12px;color:var(--muted);margin:0 0 8px;line-height:1.5;max-width:720px">
      Drag a phase&rsquo;s edges to change when it starts and ends, or drag the middle to move it. Diamonds are
      one-off events. Hatched stretches have no phase and save nothing. Arrow keys work too (Shift for a year).</p>
    <div class="tl" id="timeline"></div>
  </div>
  <div class="cols">
    <div class="panel" id="controls"></div>
    <div>
      <div style="display:flex;justify-content:flex-end;margin-bottom:10px"><div class="seg" id="chartmode" role="group" aria-label="Chart detail" style="margin:0">
        <button type="button" data-cm="simple">Simple charts</button><button type="button" data-cm="detailed">Detailed</button></div></div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:18px" id="crossstats"></div>
      <div class="panel" style="padding:16px 12px 8px;margin-bottom:18px">
        <div class="eyebrow" style="margin:0 0 6px 8px">Each year: what you earn, save, withdraw, and what the portfolio earns</div>
        <div id="flowchart"></div>
        <div class="legend" style="padding:6px 4px">
          <span data-detail><b style="color:var(--rule)">&#9612;</b> Income</span>
          <span><b style="color:var(--coast)">&#9612;</b> Saved</span>
          <span><b style="color:var(--path)">&#9612;</b> Investment return</span>
          <span><b style="color:var(--warn);opacity:.8">&#9612;</b> Withdrawn in retirement</span>
          <span data-detail><b style="color:var(--fire)">&#9670;</b> One-off event</span>
          <span data-detail><b style="color:var(--coast)">&#9670;</b> Pension pot</span>
        </div>
        <div class="note" id="flownote" style="padding:0 6px 6px;font-size:12px;max-width:640px"></div>
      </div>
      <div class="panel" style="padding:16px 12px 8px"><div id="projchart"></div>
        <div class="legend" style="padding:6px 4px">
          <span><b style="color:var(--path)">&mdash;</b> Portfolio</span>
          <span data-detail><b style="color:var(--coast)">- -</b> Coast threshold</span>
          <span><b style="color:var(--fire)">&mdash;</b> Target</span>
          <span data-detail><b style="color:var(--path);opacity:.35">&#9608;</b> middle 80% of markets</span>
          <span data-detail><b style="color:var(--muted)">&#9612;</b> phase, event or pension</span>
        </div>
        <div id="mcnote" style="padding:10px 8px 8px;border-top:1px solid var(--rule);margin-top:6px"></div>
      </div>
      <div class="panel" style="padding:16px 18px 12px;margin-top:18px">
        <div class="eyebrow" style="margin:0 0 4px">Years to target if things go differently</div>
        <div class="note" style="margin:0 0 10px">Each cell reruns your plan with that real return and every phase&rsquo;s saving scaled.
          Darker is sooner. The outlined cell is closest to your current settings.</div>
        <div id="sensgrid" style="overflow-x:auto"></div>
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
/* ---------- one-line takeaways above charts ----------
   Each chart gets a sentence that says what it shows, so the page can be read
   from the headlines alone and the chart is there for the detail. */
function takeaway(hostId, html){
  const host=document.getElementById(hostId); if(!host) return;
  let t=document.getElementById(hostId+'_tk');
  if(!t){ t=document.createElement('p'); t.className='tk'; t.id=hostId+'_tk'; host.parentNode.insertBefore(t, host); }
  t.innerHTML=html;
}
const mag=(v,f)=>`<b class="${v<0?'neg':''}">${f(Math.abs(v))}</b>`;   /* size only: the verb carries the direction */
const sgn=(v,f)=>`<b class="${v<0?'neg':''}">${v<0?'\u2212':'+'}${f(Math.abs(v))}</b>`;
const monthName=t=>new Date(t).toLocaleDateString('en-GB',{month:'long',year:'numeric'});
const pts=v=>(v*100).toFixed(1)+' points';

/* Simple / Detailed for the busy plan charts; remembered per browser */
let chartMode='simple';
try{ const m=localStorage.getItem('ibkr-fire-chartmode'); if(m==='detailed'||m==='simple') chartMode=m; }catch(e){}

const LOCALE = (D.fmt && D.fmt.locale) || 'en-US';
const nf = new Intl.NumberFormat(LOCALE,{maximumFractionDigits:0});
const nf2 = new Intl.NumberFormat(LOCALE,{minimumFractionDigits:2,maximumFractionDigits:2});
const money = v => D.ccy + " " + nf.format(Math.round(v));
const pc = (v,d=2) => (v>=0?"":"\u2212") + Math.abs(v*100).toFixed(d) + "%";
const el = h => { const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; };

/* ---------- staleness ---------- */
(function(){
  if(D.age_days > 5 && !D.demo){
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
  const nowM = (()=>{ const [y,m]=D.plan.anchor.split('-').map(Number); return y*12+m-1; })();
  const mOf = s => { const [y,m]=s.split('-').map(Number); return y*12+m-1; };
  const curP = D.plan.phases.find(p=> nowM>=mOf(p.start) && (p.end===null || nowM<=mOf(p.end)));
  const planned = !curP ? 0 : curP.saving_mode==='fixed' ? curP.monthly_saving : curP.monthly_income*curP.savings_rate;
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
  // Single source of truth for "what it is worth now": the account summary,
  // which is also what the headline shows. The performance endpoint's NAV
  // series is a derived daily series and can sit a franc or two off it.
  const finalNav = D.summary.net_liquidation;
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
  takeaway('growthchart', `Of the ${money(finalNav)} you have, ${money(totalIn)} is money you put in`
    + ` and the market ${growth>=0?'added':'took away'} ${mag(growth,v=>money(v))}${everBelowCost?`; at the low on ${new Date(worstT).toLocaleDateString('en-GB',{day:'numeric',month:'short'})} it was worth ${money(-worst)} less than you had paid in`:''}.`);
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
        <td colspan="5" class="l" style="color:var(--muted);font-family:var(--fn);font-size:12px">${r.note}</td></tr>`));
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
  if(opts.area && opts.area.length){   /* shaded range between two curves: [[x, lo, hi], ...] */
    const top=opts.area.map(p=>`${tx(p[0]).toFixed(1)},${ty(p[2]).toFixed(1)}`);
    const bot=opts.area.slice().reverse().map(p=>`${tx(p[0]).toFixed(1)},${ty(p[1]).toFixed(1)}`);
    s+=`<polygon points="${top.concat(bot).join(' ')}" fill="var(--path)" opacity="0.10"/>`;
  }
  (opts.bands||[]).forEach(b=>{
    s+=`<rect x="${tx(b[0])}" y="${mt}" width="${Math.max(0,tx(b[1])-tx(b[0]))}" height="${H-mt-mb}" fill="${b[2]}" opacity="0.08"/>`;
  });
  /* labels drop to a lower row when they would run into the previous one */
  const rowEnds=[];
  (opts.vlines||[]).slice().sort((a,b)=>a[0]-b[0]).forEach(v=>{
    s+=`<line x1="${tx(v[0])}" y1="${mt}" x2="${tx(v[0])}" y2="${H-mb}" stroke="${v[2]||'var(--muted)'}" stroke-width="1" stroke-dasharray="2 3"/>`;
    if(v[1]){
      const x=tx(v[0])+4, w=String(v[1]).replace(/&[a-z#0-9]+;/gi,'_').length*6.2;
      let row=rowEnds.findIndex(end=>end<x-6); if(row<0){ row=rowEnds.length; }
      rowEnds[row]=x+w;
      s+=`<text class="axl" x="${x}" y="${mt+11+row*12}" fill="${v[2]||'var(--muted)'}">${v[1]}</text>`;
    }
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
  {
    const lastP=S[S.length-1].cps; let pk=-Infinity, dd=0, ddT=null;
    S.forEach(p=>{ pk=Math.max(pk,1+p.cps); const d=(1+p.cps)/pk-1; if(d<dd){dd=d; ddT=p.t;} });
    takeaway('navchart', `Your investments are ${lastP>=0?'up':'down'} ${mag(lastP,v=>(v*100).toFixed(1)+'%')} since ${new Date(t0).toLocaleDateString('en-GB',{month:'long',year:'numeric'})}, not counting deposits`
      + (dd<-0.03?`. The roughest patch was ${monthName(ddT)}, ${Math.abs(dd*100).toFixed(1)}% below the previous high.`:'.'));
  }
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
  document.getElementById('ccyk').textContent = F.pair + ' \u00b7 ECB reference rates \u00b7 time-weighted';

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

  if(main && F.rate_first && F.rate_last){
    const mv=F.rate_last/F.rate_first-1;
    takeaway('ratechart', `The ${F.asset_currency} ${mv<0?'fell':'rose'} ${Math.abs(mv*100).toFixed(1)}% against the ${F.display_currency} since ${main.label.toLowerCase().includes('since')?'you started':'the start of the window'},`
      + ` which ${main.currency<0?'cost':'added'} you ${mag(main.currency,v=>(v*100).toFixed(1)+'%')} on top of what the funds did (${pc(main.asset)}).`);
  }
  const tb=document.querySelector('#ccytbl tbody');
  F.splits.forEach(r=>{
    if(!r.available){
      tb.appendChild(el(`<tr><td class="l" style="font-weight:600">${r.label}</td>
        <td colspan="5" class="l" style="color:var(--muted);font-family:var(--fn);font-size:12px">${r.note}</td></tr>`));
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
/* Months are counted as year*12 + (month-1), so phases, events and "now" compare
   and subtract as plain integers. M0 is the month of the latest data: the
   projection always starts there, so a phase that began earlier shows as "now". */
const ym2m = s => { const [y,m]=String(s).split('-').map(Number); return y*12+(m-1); };
const m2ym = n => `${Math.floor(n/12)}-${String(n%12+1).padStart(2,'0')}`;
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const mlabel = n => `${MONTHS[((n%12)+12)%12]} ${Math.floor(n/12)}`;
const esc = s => String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kfmt = v => { const a=Math.abs(v); const s=a>=1e6?(a/1e6).toFixed(1)+'M':Math.round(a/1000)+'k'; return (v<0?'−':'')+s; };
const signedMoney = v => (v<0?'−':'+')+money(Math.abs(v));
const r6 = v => Math.round(v*1e6)/1e6;
const M0 = ym2m(D.plan.anchor);
const ageAt = n => D.age_now + (n-M0)/12;

let KEYSEQ = 0;
function normalisePlan(p){
  const num = (v,d=0) => { const x=Number(v); return Number.isFinite(x)?x:d; };
  const out = {
    target:num(p.target), real_return:num(p.real_return), withdrawal_rate:num(p.withdrawal_rate),
    coast_full_age:num(p.coast_full_age),
    volatility:num(p.volatility,0.16),
    target_mode:(p.target_mode==='spending'?'spending':'amount'),
    annual_spending:num(p.annual_spending, num(p.target)*num(p.withdrawal_rate)),
    pensions:normPensions(p.pensions||{}, num),
    phases:(p.phases||[]).map(x=>({ _k:'k'+(KEYSEQ++), id:String(x.id), label:String(x.label),
      s:ym2m(x.start), e:(x.end==null?null:ym2m(x.end)),
      monthly_income:num(x.monthly_income), saving_mode:(x.saving_mode==='fixed'?'fixed':'rate'),
      savings_rate:num(x.savings_rate), monthly_saving:num(x.monthly_saving), income_growth:num(x.income_growth)
    })).sort((a,b)=>a.s-b.s),
    events:(p.events||[]).map((x,i)=>({ _k:'k'+(KEYSEQ++), id:String(x.id||('event'+(i+1))), label:String(x.label),
      m:ym2m(x.date), amount:num(x.amount) })).sort(evOrder)
  };
  const bad = !out.target || out.phases.some(q=>!Number.isFinite(q.s) || (q.e!==null && !Number.isFinite(q.e)))
           || out.events.some(e=>!Number.isFinite(e.m));
  if(bad) throw new Error('unusable plan');
  if(out.target_mode==='spending' && out.withdrawal_rate>0) out.target=out.annual_spending/out.withdrawal_rate;
  return out;
}
function normPensions(q, num){
  const pot=(o,unlock)=>({ balance:num((o||{}).balance), yearly_contribution:num((o||{}).yearly_contribution),
    real_return:num((o||{}).real_return,0.01), unlock_age:num((o||{}).unlock_age,unlock) });
  return { enabled:!!q.enabled, pillar2:pot(q.pillar2,65), pillar3a:pot(q.pillar3a,60),
    ahv:{ yearly_amount:num((q.ahv||{}).yearly_amount), start_age:num((q.ahv||{}).start_age,65) } };
}
function canonPensions(q){
  const pot=o=>({ balance:r6(o.balance), yearly_contribution:r6(o.yearly_contribution), real_return:r6(o.real_return), unlock_age:r6(o.unlock_age) });
  return { enabled:q.enabled, pillar2:pot(q.pillar2), pillar3a:pot(q.pillar3a),
    ahv:{ yearly_amount:r6(q.ahv.yearly_amount), start_age:r6(q.ahv.start_age) } };
}

/* Canonical form: what gets stored, compared and exported. Fixed key order and
   rounding, so "is this the same plan as config.json?" is a string compare.
   Event ids are left out on purpose: they're internal, the export doesn't carry
   them, and config.json renumbers them by position - so including them made a
   pasted-in export look like a conflict with the very edits it came from. */
function evOrder(a,b){ return (a.m-b.m) || String(a.label).localeCompare(String(b.label)) || (a.amount-b.amount); }
function canon(pl){
  return {
    target:r6(pl.target), real_return:r6(pl.real_return), withdrawal_rate:r6(pl.withdrawal_rate),
    coast_full_age:r6(pl.coast_full_age), volatility:r6(pl.volatility),
    target_mode:pl.target_mode, annual_spending:r6(pl.annual_spending),
    pensions:canonPensions(pl.pensions),
    phases:pl.phases.slice().sort((a,b)=>a.s-b.s).map(p=>({ id:p.id, label:p.label, start:m2ym(p.s),
      end:(p.e===null?null:m2ym(p.e)), monthly_income:r6(p.monthly_income), saving_mode:p.saving_mode,
      savings_rate:r6(p.savings_rate), monthly_saving:r6(p.monthly_saving), income_growth:r6(p.income_growth) })),
    events:pl.events.slice().sort(evOrder).map(e=>({ label:e.label, date:m2ym(e.m), amount:r6(e.amount) }))
  };
}
const CONFIG_CANON = JSON.stringify(canon(normalisePlan(D.plan)));

/* ---- persistence: edits live in this browser until reset or exported ---- */
const STORE_KEY = 'ibkr-fire-plan:v1:' + (D.demo ? 'demo' : 'live');
const store = {
  get(){ try{ const s=localStorage.getItem(STORE_KEY); return s?JSON.parse(s):null; }catch(e){ return null; } },
  set(v){ try{ localStorage.setItem(STORE_KEY, JSON.stringify(v)); }catch(e){} },
  clear(){ try{ localStorage.removeItem(STORE_KEY); }catch(e){} }
};
let planBase = CONFIG_CANON;   /* the config.json version the browser edits were made against */
let planStatus = 'config';     /* 'config' | 'edited' | 'conflict' */
let state = null;
(function loadPlan(){
  const s = store.get();
  /* Re-canonicalise what was stored: a version saved before the plan gained
     fields must compare equal once those fields take their defaults, or every
     upgrade would look like a conflict. */
  const fromConfig = {volatility:D.plan.volatility, target_mode:D.plan.target_mode,
                      annual_spending:D.plan.annual_spending, pensions:D.plan.pensions};
  const recanon = x => { try{ const o=typeof x==='string'?JSON.parse(x):x;
    return JSON.stringify(canon(normalisePlan(Object.assign({}, fromConfig, o)))); }catch(e){ return null; } };
  if(s && s.v===1 && s.plan){
    s.plan = JSON.parse(recanon(s.plan) || 'null'); s.base = recanon(s.base) || s.base;
    if(!s.plan){ store.clear(); }
    else if(JSON.stringify(s.plan)===CONFIG_CANON){ store.clear(); }      /* edits were exported into config.json */
    else {
      try{
        state = normalisePlan(s.plan);
        planBase = s.base;
        /* config.json changed underneath the browser edits: say so instead of
           silently preferring one version over the other */
        planStatus = (s.base===CONFIG_CANON) ? 'edited' : 'conflict';
      }catch(e){ state = null; store.clear(); }
    }
  }
  if(!state) state = normalisePlan(D.plan);
})();

function savePlan(){
  const c = canon(state);
  if(JSON.stringify(c)===CONFIG_CANON){ store.clear(); planStatus='config'; planBase=CONFIG_CANON; }
  else {
    store.set({v:1, base:planBase, plan:c, saved:new Date().toISOString()});
    if(planStatus!=='conflict') planStatus='edited';
  }
  renderPlanBar();
}

/* ---- the plan model ---- */
const planEndAge = () => Math.max(state.coast_full_age+7, D.plan.plan_to_age||95);
const spanMonths = () => Math.max(12, Math.round((planEndAge()-D.age_now)*12));
const spanEnd = () => M0 + spanMonths();
const byKey = k => state.phases.find(p=>p._k===k);
const evByKey = k => state.events.find(e=>e._k===k);
const isLive = p => p.e===null || p.e>=M0;
const activePhases = () => state.phases.filter(isLive);
const phaseAt = n => state.phases.find(p=>n>=p.s && (p.e===null || n<=p.e)) || null;
/* income growth compounds from the later of the phase start and now */
const incomeAt = (p,n) => p.monthly_income*Math.pow(1+(p.income_growth||0),(n-Math.max(p.s,M0))/12);
const savingAt = (p,n) => p.saving_mode==='fixed' ? p.monthly_saving : incomeAt(p,n)*p.savings_rate;
const PHASE_COLORS = ['#1B4D3E','#4C6272','#A8632B','#5A7A6A','#6E5A7C','#9A7B4F','#3E5F52','#7A4A3A'];
const phaseColor = p => PHASE_COLORS[Math.max(0,state.phases.indexOf(p))%PHASE_COLORS.length];
function uniqueId(prefix){
  const used = new Set([...state.phases.map(p=>p.id), ...state.events.map(e=>e.id)]);
  let i=1; while(used.has(prefix+i)) i++; return prefix+i;
}

/* ---- projection engine ----
   Month by month from now: growth on last month's balance, then that month's
   saving, then any one-off event. The same order as before, so nothing moves
   for a plan without the new features. */
/* Income and saving per month don't depend on returns, so they're worked out
   once per redraw and shared by every Monte Carlo path. */
let FLOWS=null;
function monthFlows(){
  const N=spanMonths(), inc=new Float64Array(N), sav=new Float64Array(N), ev=new Float64Array(N);
  for(let t=0;t<N;t++){ const p=phaseAt(M0+t); if(p){ inc[t]=incomeAt(p,M0+t); sav[t]=savingAt(p,M0+t); } }
  state.events.forEach(e=>{ if(e.m>=M0 && e.m<M0+N) ev[e.m-M0]+=e.amount; });
  return {N, inc, sav, ev};
}

/* Options: rets   - monthly returns to use instead of the constant one (Monte Carlo)
            r      - a different real return (sensitivity grid, fee comparison)
            saveMul- scale every phase's saving (sensitivity grid)
            shock  - fall applied to the portfolio the month you retire (stress test)
            keepSaving - never retire (comparisons that must not start withdrawing)
            lite   - skip the per-month rows; keep year-start balances only */
function project(opt){
  opt=opt||{};
  const F=FLOWS||monthFlows();
  const r=opt.r!=null?opt.r:state.real_return, m=Math.pow(1+r,1/12)-1;
  const T=state.target, fullAge=state.coast_full_age, saveMul=opt.saveMul!=null?opt.saveMul:1;
  const coastAt = a => a>=fullAge ? T : T/Math.pow(1+r, fullAge-a);
  const N=F.N;
  /* After the target is reached the plan stops saving and starts living on it:
     the withdrawal is what the target was sized to pay, less any AHV pension. */
  const spendM=T*state.withdrawal_rate/12;
  const pc=state.pensions && state.pensions.enabled ? state.pensions : null;
  const pots = pc ? [['Pillar 2',pc.pillar2],['Pillar 3a',pc.pillar3a]].filter(x=>x[1].balance>0||x[1].yearly_contribution>0)
    .map(([label,x])=>({label, bal:x.balance, add:x.yearly_contribution/12, g:Math.pow(1+x.real_return,1/12)-1, unlock:x.unlock_age, paid:false})) : [];
  const ahvM = pc ? pc.ahv.yearly_amount/12 : 0, ahvAge = pc ? pc.ahv.start_age : Infinity;
  let bal=D.summary.net_liquidation, contributed=0, coastAge=null, fireAge=null, retired=false, lastsTo=null;
  const rows=opt.lite?null:[], years=[], yb=opt.lite?[]:null; let yr=null;
  for(let t=0;t<=N;t++){
    const n=M0+t, a=ageAt(n);
    if(coastAge===null && bal>=coastAt(a)) coastAge=a;
    if(fireAge===null && bal>=T){ fireAge=a; retired=!opt.keepSaving; if(opt.shock) bal*=1-opt.shock; }
    if(rows) rows.push({age:a, m:n, bal, coast:coastAt(a), contributed});
    if(t%12===0 && yb) yb.push(bal);
    if(t===N) break;
    if(!opt.lite && t%12===0){ yr={m0:n, age:a, retired, income:0, saved:0, ret:0, events:0, withdrawn:0, ahv:0, pension:0, months:0, endBal:bal}; years.push(yr); }
    const g=bal*(opt.rets?opt.rets[t]:m), ev=F.ev[t];
    const inc=retired?0:F.inc[t], c=retired?0:F.sav[t]*saveMul;
    const ahv=a>=ahvAge?ahvM:0, w=retired?Math.max(0,spendM-ahv):0;
    let pin=0;
    for(const p of pots){
      if(p.paid) continue;
      if(a>=p.unlock){ pin+=p.bal; p.paid=true; p.bal=0; }
      else p.bal = p.bal*(1+p.g) + (retired?0:p.add);
    }
    bal += g + c + ev - w + pin; contributed += c;
    if(retired && bal<=0){ if(lastsTo===null) lastsTo=a; bal=0; }
    if(yr){ yr.income+=inc; yr.saved+=c; yr.ret+=g; yr.events+=ev; yr.withdrawn+=w; yr.ahv+=retired?ahv:0; yr.pension+=pin; yr.months++; yr.endBal=bal; }
  }
  if(opt.lite) return {yb, fireAge, lastsTo, N};
  const full=years.filter(y=>y.months===12);
  /* Crossover = the first year from which the portfolio out-earns your saving
     every year after, while you are still saving. Requiring it to *stay* ahead
     stops a career break (saving nothing) from counting as the moment your
     money took over; retirement years are left out because saving stops. */
  const working=full.filter(y=>!y.retired);
  let cross=null;
  for(let i=working.length-1;i>=0;i--){ if(working[i].ret>working[i].saved) cross=working[i]; else break; }
  return {rows, years:full, cross, coastAge, fireAge, lastsTo, N, pots:pots.map(p=>({label:p.label, unlock:p.unlock}))};
}

/* ---- Monte Carlo: the same plan under random returns ----
   Monthly log-returns are normal with mean ln(1+r)/12, so the median path
   compounds at r - the deterministic line - and volatility only adds spread.
   Seeded, so the band doesn't shimmer between redraws. */
function mulberry32(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }
const MC_PATHS=500;
let MC=null, mcKey='', mcTimer=0;
function monteCarlo(){
  const N=FLOWS.N, sd=state.volatility/Math.sqrt(12), mu=Math.log(1+state.real_return)/12;
  const rnd=mulberry32(20260601), rets=new Float64Array(N);
  const nY=Math.floor(N/12)+1, cols=Array.from({length:nY},()=>new Float64Array(MC_PATHS));
  const fire=[], lasts=[];
  for(let k=0;k<MC_PATHS;k++){
    for(let t=0;t<N;t+=2){   /* Box-Muller gives two normals per draw */
      const u=1-rnd(), v=rnd(), R=Math.sqrt(-2*Math.log(u));
      rets[t]=Math.exp(mu+sd*R*Math.cos(2*Math.PI*v))-1;
      if(t+1<N) rets[t+1]=Math.exp(mu+sd*R*Math.sin(2*Math.PI*v))-1;
    }
    const o=project({rets, lite:true});
    for(let i=0;i<nY;i++) cols[i][k]=o.yb[i];
    fire.push(o.fireAge); lasts.push(o.lastsTo);
  }
  const q=(arr,p)=>{ const s=Array.from(arr).sort((a,b)=>a-b); return s[Math.min(s.length-1,Math.floor(p*(s.length-1)+0.5))]; };
  const band=cols.map((c,i)=>({age:ageAt(M0+i*12), p10:q(c,0.1), p50:q(c,0.5), p90:q(c,0.9)}));
  const reached=fire.filter(x=>x!==null).sort((a,b)=>a-b);
  const ageAtShare=s=>{ const i=Math.ceil(s*MC_PATHS)-1; return i<reached.length?reached[i]:null; };
  return { band, paths:MC_PATHS,
    reachedShare:reached.length/MC_PATHS, age50:ageAtShare(0.5), age90:ageAtShare(0.9),
    /* of the paths that retire, the share whose money lasts to the end of the plan */
    lastsShare: reached.length ? lasts.filter((x,i)=>fire[i]!==null && x===null).length/reached.length : null };
}
function scheduleMC(){
  const key=JSON.stringify(canon(state));
  if(key===mcKey) return;
  clearTimeout(mcTimer);
  /* waits for a pause, so dragging a slider stays smooth and the band settles on release */
  mcTimer=setTimeout(()=>{ FLOWS=monthFlows(); MC=monteCarlo(); mcKey=key; drawProjection(); }, 180);
}

/* ---- yearly flow chart ---- */
function niceStep(raw){
  if(!(raw>0)) return 1;
  const p=Math.pow(10,Math.floor(Math.log10(raw))), f=raw/p;
  return (f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10)*p;
}
function drawFlows(P){
  const host=document.getElementById('flowchart');
  const Y=P.years, det=chartMode==='detailed';
  if(!Y.length){ host.innerHTML=''; return; }
  const W=760, H=250, ml=54, mr=14, mt=16, mb=28;
  /* One-off events don't set the scale: a single 60k purchase would otherwise
     squash thirty years of yearly bars into a sliver. Their markers are pinned
     inside the plot and labelled with the amount instead. */
  let hi=Math.max(1, ...Y.map(y=>Math.max(det?y.income:0, y.saved, y.ret)));
  let lo=Math.min(0, ...Y.map(y=>Math.min(y.ret, y.saved, -y.withdrawn)));
  const step=niceStep((hi-lo)/4);
  hi=Math.ceil(hi*1.04/step)*step; lo=Math.floor(lo/step)*step;
  const pw=W-ml-mr, slot=pw/Y.length;
  const ty=v=> mt + (1-(v-lo)/(hi-lo))*(H-mt-mb);
  const bw=Math.max(1, slot*0.36), gapIn=slot*0.06, x0=i=> ml+i*slot+slot*0.1;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="yearly income, saving and investment return">`;
  for(let v=lo; v<=hi+1e-9; v+=step){
    s+=`<line x1="${ml}" y1="${ty(v)}" x2="${W-mr}" y2="${ty(v)}" stroke="var(--rule)" stroke-width="1"/>`;
    s+=`<text class="axl" x="${ml-8}" y="${ty(v)+3.5}" text-anchor="end">${kfmt(v)}</text>`;
  }
  const bar=(x,v,w,fill,op)=>{ const y1=ty(Math.max(v,0)), y2=ty(Math.min(v,0));
    return `<rect x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${w.toFixed(2)}" height="${Math.max(0,y2-y1).toFixed(1)}" fill="${fill}"${op?` opacity="${op}"`:''}/>`; };
  Y.forEach((y,i)=>{
    const x=x0(i);
    if(det) s+=bar(x, y.income, bw, 'var(--rule)');   /* what you earn */
    s+=bar(x, y.saved, bw, 'var(--coast)');           /* the part of it you keep */
    if(y.withdrawn) s+=bar(x, -y.withdrawn, bw, 'var(--warn)', 0.8);   /* what you live on */
    s+=bar(x+bw+gapIn, y.ret, bw, 'var(--path)');     /* what the portfolio earns */
    const lump=y.events+y.pension;
    if(lump && det){
      const cx=x+bw+gapIn/2, raw=ty(lump), cy=Math.min(Math.max(raw, mt+6), H-mb-6);
      const col=lump<0?'var(--warn)':(y.pension?'var(--coast)':'var(--fire)'), off=raw!==cy;
      s+=`<line x1="${cx}" y1="${ty(0)}" x2="${cx}" y2="${cy}" stroke="${col}" stroke-width="1.4"${off?' stroke-dasharray="3 2"':''}/>`;
      s+=`<rect x="${cx-4}" y="${cy-4}" width="8" height="8" fill="${col}" transform="rotate(45 ${cx} ${cy})"/>`;
      s+=`<text class="axl" x="${cx+7}" y="${cy+(lump<0?-4:10)}" fill="${col}">${lump<0?'':'+'}${kfmt(lump)}</text>`;
    }
  });
  if(lo<0) s+=`<line x1="${ml}" y1="${ty(0)}" x2="${W-mr}" y2="${ty(0)}" stroke="var(--muted)" stroke-width="1"/>`;
  const every=Math.max(1, Math.ceil(Y.length/9));
  Y.forEach((y,i)=>{ if(i%every===0) s+=`<text class="axl" x="${(ml+i*slot+slot/2).toFixed(1)}" y="${H-8}" text-anchor="middle">${Math.floor(y.age)}</text>`; });
  if(P.cross){
    const i=Y.indexOf(P.cross), cx=ml+i*slot;
    s+=`<line x1="${cx}" y1="${mt}" x2="${cx}" y2="${H-mb}" stroke="var(--ink)" stroke-width="1.2" stroke-dasharray="4 3"/>`;
    s+=`<text class="axl" x="${cx+5}" y="${mt+10}" fill="var(--ink)">crossover · age ${Math.floor(P.cross.age)}</text>`;
  }
  s+=`<g class="cross" style="opacity:0"><rect class="hl" y="${mt}" height="${H-mt-mb}" fill="var(--ink)" opacity="0.06"/></g>`;
  s+=`<rect class="hit" x="${ml}" y="${mt}" width="${pw}" height="${H-mt-mb}" fill="transparent"/></svg>`;
  host.classList.add('chartwrap');
  host.innerHTML=s;

  const svg=host.querySelector('svg'), hit=host.querySelector('.hit'), g=host.querySelector('.cross'), hl=host.querySelector('.hl');
  const tip=document.createElement('div'); tip.className='tipbox'; host.appendChild(tip);
  const row=(c,l,v)=>`<span class="tr"><span style="color:${c}">■</span>&nbsp;${l}<b>${v}</b></span>`;
  hit.addEventListener('mousemove',evt=>{
    const pt=svg.createSVGPoint(); pt.x=evt.clientX; pt.y=evt.clientY;
    const p=pt.matrixTransform(svg.getScreenCTM().inverse());
    const i=Math.min(Y.length-1, Math.max(0, Math.floor((p.x-ml)/slot)));
    const y=Y[i];
    hl.setAttribute('x', ml+i*slot); hl.setAttribute('width', slot); g.style.opacity=1;
    tip.innerHTML=`<span class="tt">age ${Math.floor(y.age)} · ${mlabel(y.m0)} – ${mlabel(y.m0+11)}</span>`
      + row('var(--muted)','Income',money(y.income))
      + row('var(--coast)','Saved',money(y.saved)+(y.income>0?` (${Math.round(y.saved/y.income*100)}%)`:''))
      + row('var(--path)','Investment return',money(y.ret))
      + (y.withdrawn?row('var(--warn)','Withdrawn to live on',money(y.withdrawn)):'')
      + (y.ahv?row('var(--coast)','AHV pension (not withdrawn)',money(y.ahv)):'')
      + (y.pension?row('var(--coast)','Pension pot paid in',money(y.pension)):'')
      + (y.events?row(y.events<0?'var(--warn)':'var(--fire)','One-off',signedMoney(y.events)):'')
      + row('var(--ink)','Portfolio at year end',money(y.endBal));
    tip.style.opacity=1;
    const hostW=host.clientWidth, frac=(i+0.5)/Y.length;
    tip.style.left=Math.min(Math.max(frac*hostW*(pw/W)+hostW*(ml/W)-tip.offsetWidth/2,4),Math.max(4,hostW-tip.offsetWidth-4))+'px';
    tip.style.top='6px';
  });
  hit.addEventListener('mouseleave',()=>{ g.style.opacity=0; tip.style.opacity=0; });

  const note=document.getElementById('flownote');
  if(note){
    if(!P.cross) note.innerHTML='On this plan your saving out-earns the portfolio every year shown, so savings rate &mdash; not returns &mdash; stays the main lever throughout.';
    else if(P.cross===Y[0]) note.innerHTML='The portfolio already earns more each year than you put in, and stays ahead from here.';
    else note.innerHTML=`<b>Crossover at age ${Math.floor(P.cross.age)}</b> (${mlabel(P.cross.m0)}): from that year on the portfolio earns more than you save, every year. Before it, how much you save matters most; after it, the money you already have does more of the work.`;
  }
}

/* ---- the draggable timeline ---- */
let drag = null;

/* Zoom: the timeline shows the next N years so near-term phases are wide enough
   to grab - over a 40-year span an 8-month phase is a sliver. The full horizon
   stays in the projection chart. The choice is a viewing preference, stored
   separately from the plan. */
const ZOOM_KEY='ibkr-fire-tlzoom';
let tlYears=(()=>{ try{ const v=localStorage.getItem(ZOOM_KEY); return v==='all'?'all':(+v||10); }catch(e){ return 10; } })();
const viewMonths = () => tlYears==='all' ? spanMonths() : Math.min(spanMonths(), tlYears*12);
function renderZoom(){
  const z=document.getElementById('tlzoom'); if(!z) return;
  z.innerHTML=[5,10,20,'all'].map(v=>`<button type="button" data-z="${v}" class="${String(v)===String(tlYears)?'on':''}"`
    +` aria-pressed="${String(v)===String(tlYears)}">${v==='all'?'All':'Next '+v+' yrs'}</button>`).join('');
}
document.getElementById('tlzoom').addEventListener('click',ev=>{
  const b=ev.target.closest('[data-z]'); if(!b) return;
  tlYears = b.dataset.z==='all' ? 'all' : +b.dataset.z;
  try{ localStorage.setItem(ZOOM_KEY,String(tlYears)); }catch(e){}
  renderZoom(); renderTimeline();
});

function renderTimeline(){
  const tl=document.getElementById('timeline'); if(!tl) return;
  const N=viewMonths(), end=M0+N;
  const focus=document.activeElement && tl.contains(document.activeElement)
    ? {k:document.activeElement.dataset.k, act:document.activeElement.dataset.act} : null;
  const pos=n=> ((Math.min(Math.max(n,M0),end)-M0)/N)*100;
  let h='<div class="lane" title="Months with no phase save nothing"></div>';
  let later=0;
  activePhases().forEach(p=>{
    if(p.s>=end){ later++; return; }                       /* starts beyond the view */
    const s=Math.max(p.s,M0), e=(p.e===null?end:Math.min(p.e+1,end));
    const left=pos(s), width=Math.max(0.15,pos(e)-left), started=p.s<M0, L=esc(p.label);
    const endVisible=p.e!==null && p.e<end;                 /* no handle on an edge that's off-screen */
    h+=`<div class="blk${started?' started':''}" data-k="${p._k}" data-act="move" tabindex="${started?-1:0}"`
      +` aria-label="${L}: ${started?'now':mlabel(p.s)} to ${p.e===null?'open-ended':mlabel(p.e)}. Arrow keys move it."`
      +` style="left:${left}%;width:${width}%;background:${phaseColor(p)}">`
      +(started?'':`<div class="h l" data-k="${p._k}" data-act="l" tabindex="0" role="slider" aria-label="${L} start" aria-valuetext="${mlabel(p.s)}"></div>`)
      +`<div class="nm">${L}</div><div class="dt">${started?'now':mlabel(p.s)} → ${p.e===null?'open':mlabel(p.e)}</div>`
      +(endVisible?`<div class="h r" data-k="${p._k}" data-act="r" tabindex="0" role="slider" aria-label="${L} end" aria-valuetext="${mlabel(p.e)}"></div>`:'')
      +`</div>`;
  });
  state.events.filter(e=>e.m>=M0).forEach(e=>{
    if(e.m>=end){ later++; return; }
    h+=`<div class="ev${e.amount<0?' neg':''}" data-k="${e._k}" data-act="ev" tabindex="0" role="slider"`
      +` aria-label="${esc(e.label)} ${signedMoney(e.amount)}" aria-valuetext="${mlabel(e.m)}"`
      +` title="${esc(e.label)} · ${mlabel(e.m)} · ${signedMoney(e.amount)}" style="left:${pos(e.m)+50/N}%"></div>`;
  });
  h+='<div class="axis">';
  const y0=Math.floor(M0/12)+1, y1=Math.floor((end-1)/12), stepY=Math.max(1,Math.ceil((y1-y0+1)/9));
  h+=`<span style="left:0;transform:none;text-align:left">now<br>${Math.floor(D.age_now)}</span>`;
  for(let y=y0;y<=y1;y+=stepY){ const n=y*12; if(n-M0<Math.max(4,N/14)) continue;
    h+=`<span style="left:${pos(n)}%">${y}<br>${Math.floor(ageAt(n))}</span>`; }
  if(later) h+=`<span class="later" style="right:0;left:auto;transform:none;text-align:right">+${later} more later &rarr;</span>`;
  h+='</div>';
  if(drag && drag.tip) h+=`<div class="dtip" style="left:${drag.tipX}%">${drag.tip}</div>`;
  tl.innerHTML=h;
  if(focus){ const f=tl.querySelector(`[data-k="${focus.k}"][data-act="${focus.act}"]`); if(f) f.focus({preventScroll:true}); }
}

/* Edge and move rules. Phases never overlap. Where two phases touch, their shared
   edge moves for both; where there's a gap, an edge stops at it. No phase drops
   below one month, and nothing can be moved into the past. */
function setEdge(k, side, target){
  const ph=state.phases, i=ph.findIndex(p=>p._k===k), p=ph[i], end=spanEnd();
  if(side==='l'){
    if(p.s<M0) return;
    const prev=ph[i-1], prevLive=prev && isLive(prev), touching=prevLive && prev.e===p.s-1;
    const lo=Math.max(M0, touching ? Math.max(prev.s,M0)+1 : (prevLive ? prev.e+1 : M0));
    const hi=(p.e===null ? end-1 : p.e);
    const v=Math.min(Math.max(target,lo),hi);
    p.s=v; if(touching) prev.e=v-1;
  } else {
    if(p.e===null) return;
    const next=ph[i+1], touching=next && next.s===p.e+1;
    const lo=Math.max(p.s,M0);
    const hi=touching ? (next.e===null ? end-1 : next.e)-1 : (next ? next.s-1 : end-1);
    const v=Math.min(Math.max(target,lo),hi);
    p.e=v; if(touching) next.s=v+1;
  }
}
function moveBody(k, delta){
  const ph=state.phases, i=ph.findIndex(p=>p._k===k), p=ph[i], end=spanEnd();
  if(p.s<M0) return;
  const prev=ph[i-1], next=ph[i+1];
  const prevLive=prev && isLive(prev), tPrev=prevLive && prev.e===p.s-1;
  const tNext=next && p.e!==null && next.s===p.e+1;
  const dmin=(tPrev ? Math.max(prev.s,M0)+1 : (prevLive ? prev.e+1 : M0)) - p.s;
  const dmax=(p.e===null) ? (end-1-p.s)
    : (tNext ? (next.e===null ? end-1 : next.e)-1 : (next ? next.s-1 : end-1)) - p.e;
  const d=Math.min(Math.max(delta,dmin),dmax);
  p.s+=d; if(p.e!==null) p.e+=d;
  if(tPrev) prev.e=p.s-1;
  if(tNext) next.s=p.e+1;
}
function moveEvent(k, target){ const e=evByKey(k); e.m=Math.min(Math.max(target,M0),spanEnd()-1); }

function addPhase(){
  const end=spanEnd(), live=activePhases(), last=live[live.length-1];
  let s;
  if(last && last.e===null){
    /* split the open-ended phase: the new one takes over five years in, or halfway if sooner */
    const from=Math.max(last.s,M0);
    s=from+Math.max(1, Math.min(60, Math.floor((end-from)/2)));
    if(s>=end) return null;
    last.e=s-1;
  } else {
    s=last ? last.e+1 : M0;
    if(s>=end) return null;
  }
  const b=last || {monthly_income:0, saving_mode:'rate', savings_rate:0.3, monthly_saving:0, income_growth:0};
  const np={_k:'k'+(KEYSEQ++), id:uniqueId('phase'), label:'New phase', s, e:null,
    monthly_income:b.monthly_income, saving_mode:b.saving_mode, savings_rate:b.savings_rate,
    monthly_saving:b.monthly_saving, income_growth:b.income_growth};
  state.phases.push(np); state.phases.sort((a,c)=>a.s-c.s);
  return np;
}
function removePhase(k){
  if(activePhases().length<=1) return;
  const ph=state.phases, i=ph.findIndex(p=>p._k===k), p=ph[i], prev=ph[i-1], next=ph[i+1];
  /* a neighbour absorbs the freed months rather than leaving a surprise gap */
  if(prev && isLive(prev) && prev.e===p.s-1) prev.e=p.e;
  else if(next && p.e!==null && next.s===p.e+1) next.s=p.s;
  ph.splice(i,1);
}
function addEvent(){
  const e={_k:'k'+(KEYSEQ++), id:uniqueId('event'), label:'Bonus', m:Math.min(M0+12,spanEnd()-1), amount:10000};
  state.events.push(e); state.events.sort((a,b)=>a.m-b.m); return e;
}
function removeEvent(k){ state.events=state.events.filter(e=>e._k!==k); }

function snapshotPlan(){ return {ph:state.phases.map(p=>[p._k,p.s,p.e]), ev:state.events.map(e=>[e._k,e.m])}; }
function restorePlan(s){
  s.ph.forEach(([k,a,b])=>{ const p=byKey(k); if(p){ p.s=a; p.e=b; } });
  s.ev.forEach(([k,m])=>{ const e=evByKey(k); if(e) e.m=m; });
}
function monthAt(tl, clientX){
  const r=tl.getBoundingClientRect(), N=viewMonths();
  return M0 + Math.min(N-1, Math.max(0, Math.floor((clientX-r.left)/r.width*N)));
}
function applyDrag(m){
  restorePlan(drag.orig);
  if(drag.act==='l') setEdge(drag.k,'l',m);
  else if(drag.act==='r') setEdge(drag.k,'r',m);
  else if(drag.act==='move') moveBody(drag.k, m-drag.m0);
  else if(drag.act==='ev') moveEvent(drag.k, m);
  const N=viewMonths();
  if(drag.act==='ev'){ const e=evByKey(drag.k); drag.tip=`${esc(e.label)} · ${mlabel(e.m)}`; drag.tipX=((e.m-M0+0.5)/N)*100; }
  else { const p=byKey(drag.k);
    drag.tip=`${p.s<M0?'now':mlabel(p.s)} → ${p.e===null?'open':mlabel(p.e)}`;
    const at=drag.act==='r' ? p.e+1 : Math.max(p.s,M0);
    drag.tipX=((at-M0)/N)*100; }
}
(function wireTimeline(){
  const tl=document.getElementById('timeline'); if(!tl) return;
  /* pointer capture sits on the container, which survives re-rendering its children mid-drag */
  tl.addEventListener('pointerdown',ev=>{
    const t=ev.target.closest('[data-act]'); if(!t || ev.button>0) return;
    const act=t.dataset.act, k=t.dataset.k;
    if(act==='move' && byKey(k).s<M0) return;
    ev.preventDefault();
    try{ tl.setPointerCapture(ev.pointerId); }catch(e){}
    drag={act, k, m0:monthAt(tl,ev.clientX), orig:snapshotPlan(), tip:null, tipX:0};
    tl.classList.add('dragging');
    applyDrag(drag.m0); scheduleRedraw();
  });
  tl.addEventListener('pointermove',ev=>{ if(!drag) return; applyDrag(monthAt(tl,ev.clientX)); scheduleRedraw(); });
  const finish=()=>{ if(!drag) return; drag=null; tl.classList.remove('dragging'); scheduleRedraw(); savePlan(); };
  tl.addEventListener('pointerup',finish);
  tl.addEventListener('pointercancel',finish);
  tl.addEventListener('keydown',ev=>{
    const t=ev.target.closest('[data-act]'); if(!t) return;
    const d=(ev.key==='ArrowLeft'?-1:ev.key==='ArrowRight'?1:0)*(ev.shiftKey?12:1);
    if(!d) return;
    ev.preventDefault();
    const k=t.dataset.k, act=t.dataset.act;
    if(act==='l') setEdge(k,'l',byKey(k).s+d);
    else if(act==='r') setEdge(k,'r',byKey(k).e+d);
    else if(act==='move') moveBody(k,d);
    else if(act==='ev') moveEvent(k,evByKey(k).m+d);
    scheduleRedraw(); savePlan();
  });
})();

/* ---- drawing everything that depends on the plan ---- */
function drawProjection(){
  if(state.target_mode==='spending' && state.withdrawal_rate>0) state.target=state.annual_spending/state.withdrawal_rate;
  FLOWS = monthFlows();
  const P = project();
  const T = state.target;
  const endAge = ageAt(M0+P.N);
  const mc = (MC && mcKey===JSON.stringify(canon(state))) ? MC : null;
  scheduleMC();

  const stat=(l,v,s,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${s}</div></div>`;
  const lasts = o => !o.fireAge ? '—' : o.lastsTo===null ? `past ${Math.floor(endAge)}` : 'age '+o.lastsTo.toFixed(0);
  const S = P.fireAge ? project({shock:0.3}) : null;
  document.getElementById('crossstats').innerHTML =
    stat('Coast FIRE reached', P.coastAge?('age '+P.coastAge.toFixed(1)):'not reached',
      P.coastAge?`stop saving here, still hit ${money(T)} at ${state.coast_full_age}`:'raise saving or lower the bar','var(--coast)') +
    stat('Full FIRE reached', P.fireAge?('age '+P.fireAge.toFixed(1)):'not reached',
      P.fireAge?`${money(T)} in today's money`:'not on this path','var(--fire)') +
    stat('Crossover', P.cross?('age '+Math.floor(P.cross.age)):'not reached',
      P.cross?'portfolio out-earns your saving from here on':'saving stays the bigger engine','var(--ink)') +
    stat('Money lasts to', lasts(P),
      P.fireAge?`withdrawing ${money(T*state.withdrawal_rate)}/yr from age ${P.fireAge.toFixed(0)}`
        +(state.pensions.enabled&&state.pensions.ahv.yearly_amount>0?`, less AHV from ${state.pensions.ahv.start_age}`:''):'retirement not reached','var(--path)') +
    stat('If markets fall 30% as you retire', S?lasts(S):'—',
      S?(S.lastsTo===null?'still lasts &mdash; a bad first year is the classic way plans fail':'a bad first year is the classic way plans fail'):'retirement not reached',
      S&&S.lastsTo===null?'var(--path)':'var(--warn)');

  drawUncertainty(P, mc, endAge);
  drawSensitivity(P);
  drawFees(P);

  const cur=phaseAt(M0);
  const nowSave=cur?savingAt(cur,M0):0;
  const yrsToFire = P.fireAge ? (P.fireAge - D.age_now) : null;
  const saveSub = !cur ? 'no phase covers this month'
    : cur.saving_mode==='fixed' ? `fixed amount · ${esc(cur.label)}`
    : `${(cur.savings_rate*100).toFixed(0)}% of ${money(incomeAt(cur,M0))} income`;
  document.getElementById('goalstats').innerHTML = `
    <div><div class="lab" style="color:#8A959C">Annual income at target</div>
      <div style="font-family:var(--fn);font-weight:700;font-size:27px;margin-top:3px;color:#7FBFA5">${money(T*state.withdrawal_rate)}</div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${(state.withdrawal_rate*100).toFixed(2)}% withdrawal rate</div></div>
    <div><div class="lab" style="color:#8A959C">Saving right now</div>
      <div style="font-family:var(--fn);font-weight:700;font-size:27px;margin-top:3px">${money(nowSave)}<span style="font-size:14px">/mo</span></div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${saveSub}</div></div>
    <div><div class="lab" style="color:#8A959C">Years to target</div>
      <div style="font-family:var(--fn);font-weight:700;font-size:27px;margin-top:3px;color:#E8A05E">${yrsToFire?yrsToFire.toFixed(0):'—'}</div>
      <div style="font-size:11.5px;color:#8A959C;margin-top:3px">${yrsToFire?('from today, age '+D.age_now.toFixed(0)):'unreachable on these inputs'}</div></div>`;

  drawFlows(P);

  /* The 90th percentile 60 years out is enormous; letting it set the scale
     would flatten everything that matters. The band is clipped instead. */
  const detMax = Math.max(...P.rows.map(r=>r.bal));
  const maxY = Math.max(T*1.12, detMax*1.15);
  const minY = Math.min(0, ...P.rows.map(r=>r.bal));
  const clip = v => Math.min(maxY, Math.max(minY, v));
  const ageMin=Math.floor(D.age_now), ageMax=Math.ceil(ageAt(M0+P.N));
  const stepY=niceStep((maxY-minY)/5), yt=[];
  for(let v=Math.ceil(minY/stepY)*stepY; v<=maxY+1e-6; v+=stepY) yt.push(v);
  const xt=[]; for(let a=Math.ceil(ageMin/5)*5;a<=ageMax;a+=5) xt.push(a);
  const dots=[];
  if(P.coastAge){const r=P.rows.find(x=>x.age>=P.coastAge); if(r)dots.push([r.age,r.bal,'var(--coast)']);}
  if(P.fireAge){const r=P.rows.find(x=>x.age>=P.fireAge); if(r)dots.push([r.age,r.bal,'var(--fire)']);}
  const vl = activePhases().filter(p=>p.s>M0).map(p=>[ageAt(p.s), esc(p.label), 'var(--muted)'])
    .concat(state.events.filter(e=>e.m>=M0 && e.m<M0+P.N).map(e=>[ageAt(e.m), (e.amount<0?'':'+')+kfmt(e.amount), e.amount<0?'var(--warn)':'var(--fire)']))
    .concat(P.pots.filter(p=>p.unlock<=endAge).map(p=>[p.unlock, esc(p.label), 'var(--coast)']));
  if(P.fireAge) vl.push([P.fireAge,'retire','var(--fire)']);

  const det=chartMode==='detailed';
  const series=[
    {name:'Target',data:P.rows.map(r=>[r.age,T]),color:'var(--fire)',w:2},
    {name:'Coast threshold',data:P.rows.map(r=>[r.age,r.coast]),color:'var(--coast)',w:1.6,dash:'6 4'},
    {name:'Portfolio',data:P.rows.map(r=>[r.age,r.bal]),color:'var(--path)',w:2.6}
  ];
  if(!det){ series.splice(1,1); }
  if(mc && det){
    series.push({name:'Bad markets (10th pct)',data:mc.band.map(b=>[b.age,b.p10]),color:'var(--warn)',w:1,dash:'2 3'});
    series.push({name:'Good markets (90th pct)',data:mc.band.map(b=>[b.age,b.p90>maxY?null:b.p90]),color:'var(--path)',w:1,dash:'2 3'});
  }
  chart(document.getElementById('projchart'),{
    height:340, xmin:ageMin, xmax:ageMax, ymin:minY, ymax:maxY, yticks:yt, xticks:xt,
    yfmt:v=> kfmt(v), xfmt:v=> v.toFixed(0),
    aria:'portfolio projection against the target and coast threshold',
    vlines: det ? vl : vl.filter(v=>v[1]==='retire'),
    area: mc && det ? mc.band.map(b=>[b.age, clip(b.p10), clip(b.p90)]) : null,
    tip:{fmt:v=>money(v), xfmt:v=>'age '+v.toFixed(1)},
    series:series,
    dots: det ? dots : dots.filter(d=>d[2]==='var(--fire)')
  });

  /* headlines for the plan charts, recomputed with every change */
  const yr=a=>new Date(MS_NOW.getTime()+(a-D.age_now)*365.25*864e5).getFullYear();
  takeaway('projchart', P.fireAge
    ? `On this plan you reach ${money(T)} at <b>age ${P.fireAge.toFixed(0)}</b> (${yr(P.fireAge)})`
      + (mc&&mc.age90?`, or by ${mc.age90.toFixed(0)} even if markets are poor`:'')
      + `, and the money ${P.lastsTo===null?`lasts past ${Math.floor(endAge)}`:`runs out at ${P.lastsTo.toFixed(0)}`}.`
    : `On this plan the portfolio doesn't reach ${money(T)} by ${Math.floor(endAge)}. Saving more or a lower target would change that.`);
  {
    const w=P.years.filter(y=>!y.retired);
    const save=w.reduce((s,y)=>s+y.saved,0), ret=w.reduce((s,y)=>s+y.ret,0);
    takeaway('flowchart', P.cross
      ? `Saving does the heavy lifting until <b>age ${Math.floor(P.cross.age)}</b>; from then on the portfolio earns more each year than you put in.`
      : `Your saving stays the bigger engine for the whole plan: ${money(save)} saved against ${money(ret)} of investment return.`);
  }
  drawGlance(P, mc);

  drawMilestones(P);
  drawHero(P);
  refreshHeader();
}

function drawUncertainty(P, mc, endAge){
  const host=document.getElementById('mcnote'); if(!host) return;
  if(!mc){ host.innerHTML=`<span class="note">Working out ${MC_PATHS} market paths&hellip;</span>`; return; }
  const v=(state.volatility*100).toFixed(0);
  const pct=x=>Math.round(x*100)+'%';
  host.innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px">
    <div><div class="lab">Target reached in</div><div class="mcv">${pct(mc.reachedShare)}</div>
      <div class="note" style="margin:0">of ${mc.paths} paths by age ${Math.floor(endAge)}</div></div>
    <div><div class="lab">Half of paths by</div><div class="mcv">${mc.age50?'age '+mc.age50.toFixed(0):'—'}</div>
      <div class="note" style="margin:0">the solid line assumes steady returns</div></div>
    <div><div class="lab">9 in 10 paths by</div><div class="mcv">${mc.age90?'age '+mc.age90.toFixed(0):'not by '+Math.floor(endAge)}</div>
      <div class="note" style="margin:0">a cautious date to plan around</div></div>
    <div><div class="lab">Money lasts to ${Math.floor(endAge)}</div><div class="mcv">${mc.lastsShare===null?'—':pct(mc.lastsShare)}</div>
      <div class="note" style="margin:0">of the paths that retire</div></div></div>
    <div class="note" style="margin:10px 0 0">Shaded: the middle 80% of ${mc.paths} simulated markets at ${v}% yearly volatility around
      ${(state.real_return*100).toFixed(2)}% real. Returns are random but independent month to month, which is kinder than real
      markets in long slumps.</div>`;
}

/* Years to target across return and saving assumptions: how much each lever matters. */
function drawSensitivity(P){
  const host=document.getElementById('sensgrid'); if(!host) return;
  const rs=[0.03,0.04,0.05,0.06,0.07], ms=[0.5,0.75,1,1.25,1.5];
  const curR=state.real_return;
  let h=`<table class="sens"><thead><tr><th class="l">Real return &darr; · saving &rarr;</th>${ms.map(m=>`<th${m===1?' class="cur"':''}>${m===1?'as planned':(m>1?'+':'−')+Math.round(Math.abs(m-1)*100)+'%'}</th>`).join('')}</tr></thead><tbody>`;
  const nearest=rs.reduce((a,b)=>Math.abs(b-curR)<Math.abs(a-curR)?b:a);
  rs.forEach(r=>{
    const near=r===nearest;
    h+=`<tr><th class="l${near?' cur':''}">${(r*100).toFixed(0)}%</th>`;
    ms.forEach(m=>{
      const o=project({r, saveMul:m, lite:true});
      const y=o.fireAge===null?null:o.fireAge-D.age_now;
      const shade = y===null ? 'var(--rule)' : `rgba(27,77,62,${Math.max(0.06,Math.min(0.55,0.6-y/60)).toFixed(2)})`;
      h+=`<td style="background:${shade}"${near&&m===1?' class="cur"':''}>${y===null?'—':y.toFixed(0)+' yr'}</td>`;
    });
    h+='</tr>';
  });
  host.innerHTML=h+'</tbody></table>';
  if(P.fireAge){
    const more=project({saveMul:1.25, lite:true}).fireAge, lower=project({r:state.real_return-0.01, lite:true}).fireAge;
    const d1=more!==null?P.fireAge-more:null, d2=lower!==null?lower-P.fireAge:null;
    takeaway('sensgrid', `Saving a quarter more brings the target ${d1!==null?`<b>${d1.toFixed(1)} years</b> closer`:'within reach'};`
      + ` a return one point lower pushes it ${d2!==null?`<b class="neg">${d2.toFixed(1)} years</b> later`:'out of reach'}.`);
  } else takeaway('sensgrid','The target is out of reach on the current plan; the grid shows which combinations get you there.');
}

/* ---------- at a glance: where you stand, whether you're on plan, what changed ---------- */
const SEEN_KEY='ibkr-fire-lastseen:'+(D.demo?'demo':'live');
const SEEN=(function(){
  /* keeps the previous refresh, so "since last time" survives reloading the same snapshot */
  const cur={asof:D.as_of, nav:D.summary.net_liquidation, contrib:(D.flows||[]).reduce((s,f)=>s+f.amount,0),
             divs:((D.income||{}).dividends||[]).length};
  let st=null; try{ st=JSON.parse(localStorage.getItem(SEEN_KEY)||'null'); }catch(e){}
  if(!st || !st.cur) st={prev:null, cur};
  else if(st.cur.asof!==cur.asof) st={prev:st.cur, cur};
  try{ localStorage.setItem(SEEN_KEY, JSON.stringify(st)); }catch(e){}
  return st;
})();
function drawGlance(P, mc){
  const ul=document.getElementById('glancelist'); if(!ul) return;
  const net=D.summary.net_liquidation, T=state.target, items=[];
  items.push(`You have <b>${money(net)}</b>, ${(net/T*100).toFixed(1)}% of your ${money(T)} target.`);
  const cur=phaseAt(M0);
  items.push(P.fireAge
    ? `On the current plan you reach it at <b>age ${P.fireAge.toFixed(0)}</b>`
      + (P.coastAge?`; you could stop saving from age ${P.coastAge.toFixed(0)} and still get there by ${state.coast_full_age}`:'')
      + (cur?`. You're saving ${money(savingAt(cur,M0))} a month now.`:'.')
    : `The current plan doesn't reach the target by ${Math.floor(ageAt(M0+P.N))}; section 08 shows what would.`);
  const S=D.series;
  if(S.length>1){
    const r=S[S.length-1].cps, B=(D.income||{}).benchmark;
    let line=`Your investments are ${r>=0?'up':'down'} ${pc(r)} since ${new Date(S[0].t).toLocaleDateString('en-GB',{month:'short',year:'numeric'})}, deposits aside`;
    if(B && B.cps[B.cps.length-1]!=null){ const g=(1+r)/(1+S[0].cps)-1-B.cps[B.cps.length-1];
      line+=`, ${Math.abs(g*100).toFixed(1)} points ${g>=0?'ahead of':'behind'} ${B.ticker}`; }
    items.push(line+'.');
  }
  const p=SEEN.prev;
  if(p){
    const dn=net-p.nav, dc=SEEN.cur.contrib-p.contrib, dm=dn-dc, nd=SEEN.cur.divs-p.divs;
    items.push(`Since your last refresh (${esc(p.asof)}): ${sgn(dn,v=>money(v))} in value, ${money(Math.max(0,dc))} from deposits and ${sgn(dm,v=>money(v))} from the market`
      + (nd>0?`, with ${nd} new dividend${nd>1?'s':''}.`:'.'));
  } else if(!D.demo) items.push(`Next time you refresh, this line will say what changed since today (${esc(D.as_of)}).`);
  ul.innerHTML=items.map(x=>`<li>${x}</li>`).join('');
}

/* Fee drag. The real return you enter is already after fees, so this does not
   deduct anything a second time: it shows what the same plan would reach if
   the funds were free, which is what the fees cost you. */
function drawFees(P){
  const host=document.getElementById('feepanel'); if(!host) return;
  const T=D.ters||{}, pos=D.positions||[];
  const tot=pos.reduce((s,p)=>s+p.market_value,0);
  const known=pos.filter(p=>T[p.ticker]!=null), kv=known.reduce((s,p)=>s+p.market_value,0);
  if(!tot || !known.length){ document.getElementById('feesection').hidden=true; return; }
  document.getElementById('feesection').hidden=false; document.getElementById('risksection').hidden=false;
  const ter=known.reduce((s,p)=>s+p.market_value*T[p.ticker],0)/kv;
  const yearly=ter*D.summary.net_liquidation;
  const atAge = P.fireAge || ageAt(M0+P.N);
  const balAt = (rows,a)=>{ const r=rows.find(x=>x.age>=a-1e-9); return r?r.bal:rows[rows.length-1].bal; };
  /* neither side retires here: the fee-free plan would hit the target sooner and
     start withdrawing, which would hide most of the cost */
  const free=project({r:state.real_return+ter, keepSaving:true}), paid=project({keepSaving:true});
  const cost=balAt(free.rows,atAge)-balAt(paid.rows,atAge);
  const fig=(l,v,s)=>`<div class="stat" style="border-color:var(--warn)"><div class="lab">${l}</div><div class="val">${v}</div><div class="sub">${s}</div></div>`;
  host.innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:12px">`
    + fig('Weighted expense ratio', (ter*100).toFixed(3)+'%', `across ${known.length} of ${pos.length} holdings`)
    + fig('Cost this year', money(yearly), 'on today’s portfolio')
    + fig(P.fireAge?'Cost by retirement':'Cost by age '+Math.floor(atAge), money(cost), `compounded, age ${atAge.toFixed(0)}`)
    + `</div><table><thead><tr><th class="l">Fund</th><th>Weight</th><th>Expense ratio</th><th>Per year</th></tr></thead><tbody>`
    + pos.slice().sort((a,b)=>b.market_value-a.market_value).map(p=>{ const t=T[p.ticker];
        return `<tr><td class="l">${esc(p.ticker)}</td><td>${(p.market_value/tot*100).toFixed(1)}%</td>
          <td>${t==null?'<span class="role">not in config</span>':(t*100).toFixed(2)+'%'}</td><td>${t==null?'—':money(p.market_value*t)}</td></tr>`; }).join('')
    + `</tbody></table><div class="note" style="margin-top:10px">Your real-return assumption is already after fees, so nothing is
      deducted twice. &ldquo;Cost by retirement&rdquo; compares your plan with the same plan in fee-free funds.</div>`;
}

let rafId=0;
function scheduleRedraw(){
  if(rafId) return;
  rafId=requestAnimationFrame(()=>{ rafId=0; renderTimeline(); drawProjection(); refreshDerived(); });
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

/* ---------- header text, kept in step with the plan ----------
   The server renders these from config so the page reads correctly before any
   JS runs; from then on they track `state`, otherwise editing the plan leaves
   the headline and lede quoting numbers nothing else uses. */
function refreshHeader(){
  const target = state.target;
  const net = D.summary.net_liquidation;
  const eb = document.getElementById('ebTarget');
  const h1 = document.getElementById('h1Target');
  if(eb) eb.textContent = money(target);
  if(h1) h1.textContent = money(target);

  const lede = document.getElementById('lede');
  if(!lede) return;
  const cur = phaseAt(M0);
  const next = cur ? null : activePhases().find(p=>p.s>M0);
  const opening = cur
    ? `Saving ${money(savingAt(cur,M0))} a month right now against a ${money(target)} target`
    : next
      ? `Saving starts at ${money(savingAt(next,next.s))} a month in the ${next.label.toLowerCase()} phase (${mlabel(next.s)}), against a ${money(target)} target`
      : `No saving on the current plan, against a ${money(target)} target`;
  lede.textContent = `${opening}, currently ${(net/target*100).toFixed(1)}% of the way there. `
    + 'Returns below are money-weighted. Every input in the projection is editable - '
    + 'it is only as good as what you put in it.';
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
        totalIn?`${pc(growth/totalIn)} of what you paid in — not a rate of return`:'—',
        growth>=0?'var(--path)':'var(--warn)') +
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
    onIn(v); scheduleRedraw();
  });
  inp.addEventListener('change',()=>savePlan());
  return w;
}

function refreshDerived(){
  const tn=document.querySelector('[data-tgtnote]');
  if(tn) tn.textContent=`→ target ${money(state.target)} at ${(state.withdrawal_rate*100).toFixed(2)}% withdrawal`;
  activePhases().forEach(p=>{
    const d=document.querySelector(`[data-deriv="${p._k}"]`);
    if(d) d.textContent = `→ saving ${money(savingAt(p,Math.max(p.s,M0)))}/mo`
      + (p.saving_mode==='fixed' && p.monthly_income>0 ? ` · ${Math.round(p.monthly_saving/p.monthly_income*100)}% of income` : '');
    const t=document.querySelector(`[data-dates="${p._k}"]`);
    if(t){ const len=(p.e===null?null:p.e-Math.max(p.s,M0)+1);
      t.textContent = `${p.s<M0?'now':mlabel(p.s)} → ${p.e===null?'open-ended':mlabel(p.e)}`
        + (len?` · ${len>=24?(len/12).toFixed(1)+' yr':len+' mo'}`:''); }
  });
  state.events.forEach(e=>{ const t=document.querySelector(`[data-evdate="${e._k}"]`); if(t) t.textContent=mlabel(e.m); });
}

function pensionBlock(){
  const q=state.pensions;
  const d=el(`<details class="pen"${q.enabled?' open':''}><summary>Swiss pensions (optional)</summary>
    <div class="note" style="margin:8px 0">Pillar 2 and 3a pots grow on their own and are paid into the portfolio at their unlock
      age. AHV is a yearly pension that cuts what the portfolio has to pay out. Today&rsquo;s money throughout. Your figures are on
      your pension statements.</div>
    <label style="display:flex;gap:8px;align-items:center;font-size:12.5px"><input type="checkbox" data-pen="enabled"${q.enabled?' checked':''}> Include pensions</label>
    <div class="pengrid"></div></details>`);
  const grid=d.querySelector('.pengrid');
  const field=(path,label,step)=>{ const [a,b]=path.split('.'); const v=q[a][b];
    const f=el(`<label>${label}<input type="number" step="${step}" value="${v}"${q.enabled?'':' disabled'}></label>`);
    const inp=f.querySelector('input');
    inp.addEventListener('input',()=>{ const x=parseFloat(inp.value); if(Number.isFinite(x)){ q[a][b]=x; scheduleRedraw(); } });
    inp.addEventListener('change',()=>savePlan());
    grid.appendChild(f); };
  const head=t=>grid.appendChild(el(`<div class="h">${t}</div>`));
  head('Pillar 2 (pension fund)');
  field('pillar2.balance','Balance',1000); field('pillar2.yearly_contribution','Paid in per year',500);
  field('pillar2.real_return','Real return',0.005); field('pillar2.unlock_age','Paid out at age',1);
  head('Pillar 3a');
  field('pillar3a.balance','Balance',1000); field('pillar3a.yearly_contribution','Paid in per year',500);
  field('pillar3a.real_return','Real return',0.005); field('pillar3a.unlock_age','Paid out at age',1);
  head('AHV');
  field('ahv.yearly_amount','Pension per year',500); field('ahv.start_age','From age',1);
  d.querySelector('[data-pen="enabled"]').addEventListener('change',e=>{ q.enabled=e.target.checked; rebuildPlan(); savePlan(); });
  return d;
}

function phaseBlock(p){
  const k=p._k, only=activePhases().length<=1;
  const b=el(`<div class="phase" style="border-color:${phaseColor(p)}">
    <div class="phhead"><input class="phname" type="text" maxlength="40" value="${esc(p.label)}" aria-label="Phase name">
      ${only?'':`<button class="x" type="button" title="Remove this phase" aria-label="Remove ${esc(p.label)}">×</button>`}</div>
    <div class="pd" data-dates="${k}"></div>
    <div class="derived" data-deriv="${k}"></div>
    <div class="seg" role="group" aria-label="How this phase saves">
      <button type="button" data-mode="rate" class="${p.saving_mode==='rate'?'on':''}" aria-pressed="${p.saving_mode==='rate'}">% of income</button>
      <button type="button" data-mode="fixed" class="${p.saving_mode==='fixed'?'on':''}" aria-pressed="${p.saving_mode==='fixed'}">Fixed amount</button>
    </div></div>`);
  const nm=b.querySelector('.phname');
  nm.addEventListener('input',()=>{ p.label=nm.value||'Phase'; scheduleRedraw(); });
  nm.addEventListener('change',()=>savePlan());
  const x=b.querySelector('.x');
  if(x) x.addEventListener('click',()=>{ removePhase(k); rebuildPlan(); savePlan(); });
  b.querySelectorAll('.seg button').forEach(btn=>btn.addEventListener('click',()=>{
    if(p.saving_mode===btn.dataset.mode) return;
    /* switching keeps today's saving the same, so the projection doesn't jump */
    const now=savingAt(p,Math.max(p.s,M0)), inc=incomeAt(p,Math.max(p.s,M0));
    if(btn.dataset.mode==='fixed') p.monthly_saving=Math.round(now/50)*50;
    else if(inc>0) p.savings_rate=Math.min(1,Math.round(now/inc*100)/100);
    p.saving_mode=btn.dataset.mode; rebuildPlan(); savePlan();
  }));
  const incMax=Math.max(15000, Math.ceil(p.monthly_income*2/1000)*1000);
  b.appendChild(slider('inc_'+k,'Monthly income',p.monthly_income,0,incMax,100,v=>money(v),null,v=>{p.monthly_income=v;}));
  if(p.saving_mode==='rate'){
    b.appendChild(slider('sav_'+k,'Savings rate',p.savings_rate,0,1,0.01,v=>(v*100).toFixed(0)+'%',null,v=>{p.savings_rate=v;}));
  } else {
    const fixMax=Math.max(5000, Math.ceil(Math.max(p.monthly_saving,p.monthly_income)*1.5/500)*500);
    b.appendChild(slider('fix_'+k,'Saving per month',p.monthly_saving,0,fixMax,50,v=>money(v),
      'A fixed amount, whatever the income. It does not grow with income.',v=>{p.monthly_saving=v;}));
  }
  b.appendChild(slider('gro_'+k,'Income growth',p.income_growth||0,-0.03,0.06,0.0025,
    v=>(v*100).toFixed(2)+'%/yr real','Raises above inflation within this phase. A promotion is better as a new phase.',v=>{p.income_growth=v;}));
  return b;
}

function eventRow(e){
  const r=el(`<div class="evrow">
    <input class="evname" type="text" maxlength="40" value="${esc(e.label)}" aria-label="Event name">
    <span class="evdate" data-evdate="${e._k}">${mlabel(e.m)}</span>
    <input class="evamt" type="number" step="500" value="${Math.round(e.amount)}" aria-label="Amount, negative for a purchase">
    <button class="x" type="button" aria-label="Remove ${esc(e.label)}">×</button></div>`);
  const nm=r.querySelector('.evname'), am=r.querySelector('.evamt');
  nm.addEventListener('input',()=>{ e.label=nm.value||'Event'; scheduleRedraw(); });
  nm.addEventListener('change',()=>savePlan());
  am.addEventListener('input',()=>{ const v=parseFloat(am.value); e.amount=Number.isFinite(v)?v:0; scheduleRedraw(); });
  am.addEventListener('change',()=>savePlan());
  r.querySelector('.x').addEventListener('click',()=>{ removeEvent(e._k); rebuildPlan(); savePlan(); });
  return r;
}

function buildControls(){
  const host=document.getElementById('controls');
  host.innerHTML='';
  activePhases().forEach(p=>host.appendChild(phaseBlock(p)));
  const add=el(`<div class="btnrow"><button class="btn" type="button">+ Add phase</button></div>`);
  add.querySelector('button').addEventListener('click',()=>{
    const np=addPhase(); if(!np) return;
    rebuildPlan(); savePlan();
    const blocks=host.querySelectorAll('.phname'); const i=activePhases().indexOf(np);
    if(blocks[i]){ blocks[i].focus(); blocks[i].select(); }
  });
  host.appendChild(add);

  const evs=el(`<div class="evsec"><div class="ph" style="font-family:var(--fn);font-size:10.5px;font-weight:600">One-off events</div>
    <div class="note">Lump sums on a date &mdash; a bonus or inheritance, or a big purchase as a negative amount. Drag the diamonds on the timeline to move them.</div></div>`);
  state.events.filter(e=>e.m>=M0).forEach(e=>evs.appendChild(eventRow(e)));
  const addE=el(`<div class="btnrow"><button class="btn ghost" type="button">+ Add event</button></div>`);
  addE.querySelector('button').addEventListener('click',()=>{ addEvent(); rebuildPlan(); savePlan(); });
  evs.appendChild(addE);
  host.appendChild(evs);

  const g=el(`<div style="border-top:1px solid var(--rule);padding-top:20px;margin-top:4px"></div>`);
  const tm=el(`<div class="ctl"><div class="row"><label>Set the target by</label></div><div class="seg" role="group" aria-label="How the target is set">
      <button type="button" data-tm="amount" class="${state.target_mode==='amount'?'on':''}" aria-pressed="${state.target_mode==='amount'}">Amount</button>
      <button type="button" data-tm="spending" class="${state.target_mode==='spending'?'on':''}" aria-pressed="${state.target_mode==='spending'}">Yearly spending</button></div></div>`);
  tm.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
    if(state.target_mode===b.dataset.tm) return;
    /* switching keeps the target where it is */
    if(b.dataset.tm==='spending') state.annual_spending=state.target*state.withdrawal_rate;
    state.target_mode=b.dataset.tm; rebuildPlan(); savePlan();
  }));
  g.appendChild(tm);
  if(state.target_mode==='spending'){
    g.appendChild(slider('spd','Yearly spending',state.annual_spending,10000,250000,1000,
      v=>money(v),null,v=>{state.annual_spending=v; state.target=v/state.withdrawal_rate;}));
    g.appendChild(el(`<div class="note" data-tgtnote style="margin:-6px 0 14px"></div>`));
  } else {
    g.appendChild(slider('tgt','Target',state.target,250000,5000000,50000,
      v=>money(v),'The number you are aiming at.',v=>{state.target=v;}));
  }
  g.appendChild(slider('ret','Real return',state.real_return,0.02,0.08,0.0025,
    v=>(v*100).toFixed(2)+'%','After inflation and fees. 5% is a fair global-equity base case.',v=>{state.real_return=v;}));
  g.appendChild(slider('swr','Withdrawal rate',state.withdrawal_rate,0.025,0.05,0.0005,
    v=>(v*100).toFixed(2)+'%','Sets the income the target funds. 3.25–3.75% suits a 50-year retirement.',v=>{state.withdrawal_rate=v;}));
  g.appendChild(slider('cfa','Coast target age',state.coast_full_age,50,65,1,
    v=>String(v),'The age the coast portfolio must reach the target by, unaided.',v=>{state.coast_full_age=v;}));
  g.appendChild(slider('vol','Market volatility',state.volatility,0,0.3,0.01,
    v=>(v*100).toFixed(0)+'%/yr','Only widens the shaded band. 16% is roughly a global stock index; 0 removes the band.',v=>{state.volatility=v;}));
  host.appendChild(g);
  host.appendChild(pensionBlock());
  refreshDerived();
}

/* ---------- plan bar: edited / reset / export ---------- */
function renderPlanBar(){
  const bar=document.getElementById('planbar'); if(!bar) return;
  if(planStatus==='conflict'){
    bar.innerHTML=`<div class="warnbox" style="margin:0;flex:1"><b>config.json has changed since you edited this plan in the browser.</b>
      You're seeing your browser version. Pick one:
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn" type="button" data-do="useconfig">Use config.json</button>
        <button class="btn ghost" type="button" data-do="keep">Keep my browser edits</button>
        <button class="btn ghost" type="button" data-do="export">Copy my edits as config</button></div></div>`;
  } else if(planStatus==='edited'){
    bar.innerHTML=`<span><b style="color:var(--ink)">Edited in this browser.</b> config.json still has the original &mdash; copy your edits across to make them permanent.</span>
      <span style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" data-do="export">Copy as config</button>
      <button class="btn ghost" type="button" data-do="useconfig">Reset to config</button></span>`;
  } else {
    bar.innerHTML=`<span>Showing the plan from config.json. Changes you make here are kept in this browser.</span>
      <span><button class="btn ghost" type="button" data-do="export">Copy as config</button></span>`;
  }
}
function rebuildPlan(){ buildControls(); renderTimeline(); drawProjection(); renderPlanBar(); }
document.getElementById('planbar').addEventListener('click',ev=>{
  const b=ev.target.closest('[data-do]'); if(!b) return;
  const what=b.dataset.do;
  if(what==='useconfig'){ state=normalisePlan(D.plan); store.clear(); planStatus='config'; planBase=CONFIG_CANON; rebuildPlan(); }
  else if(what==='keep'){ planBase=CONFIG_CANON; planStatus='edited'; savePlan(); }
  else if(what==='export'){ showExport(); }
});

function exportText(){
  const c=canon(state);
  const goal=Object.assign({target:c.target}, D.plan.goal_extra||{},
    {coast_full_age:c.coast_full_age, real_return:c.real_return, withdrawal_rate:c.withdrawal_rate,
     volatility:c.volatility, target_mode:c.target_mode, annual_spending:c.annual_spending});
  const phases=c.phases.map(p=>{
    const o={id:p.id, label:p.label, start:p.start, end:p.end, monthly_income:p.monthly_income,
             savings_rate:p.savings_rate, income_growth:p.income_growth};
    if(p.saving_mode==='fixed'){ o.saving_mode='fixed'; o.monthly_saving=p.monthly_saving; }
    return o;
  });
  const events=c.events.map(e=>({date:e.date, label:e.label, amount:e.amount}));
  return JSON.stringify({goal, phases, events, pensions:c.pensions}, null, 2);
}
function showExport(){
  const txt=exportText();
  const m=el(`<div class="modal" role="dialog" aria-modal="true" aria-label="Copy plan as config"><div class="box">
    <div class="eyebrow" style="margin:0">Copy as config</div>
    <p style="margin:0;font-size:12.5px;line-height:1.55;color:#3C464C">In <code>config.json</code>, replace the
      <code>"goal"</code>, <code>"phases"</code>, <code>"events"</code> and <code>"pensions"</code> entries with these. Everything else in the
      file stays as it is. Phases that have already ended are included, so nothing is lost.</p>
    <textarea readonly spellcheck="false"></textarea>
    <div style="display:flex;gap:8px;justify-content:flex-end;align-items:center"><span class="note" data-ok style="margin:0"></span>
      <button class="btn" type="button" data-copy>Copy</button><button class="btn ghost" type="button" data-close>Close</button></div>
  </div></div>`);
  const ta=m.querySelector('textarea'); ta.value=txt;
  const close=()=>{ m.remove(); document.removeEventListener('keydown',onKey); };
  const onKey=e=>{ if(e.key==='Escape') close(); };
  m.addEventListener('click',e=>{ if(e.target===m || e.target.closest('[data-close]')) close(); });
  document.addEventListener('keydown',onKey);
  m.querySelector('[data-copy]').addEventListener('click',async()=>{
    const ok=m.querySelector('[data-ok]');
    try{ await navigator.clipboard.writeText(txt); ok.textContent='Copied.'; }
    catch(e){ ta.focus(); ta.select(); try{ document.execCommand('copy'); ok.textContent='Copied.'; }
              catch(_){ ok.textContent='Select the text and copy it manually.'; } }
  });
  document.body.appendChild(m);
  ta.focus(); ta.select();
}

/* ---------- dividends (gross from IBKR; withholding is an estimate) ---------- */
(function drawDividends(){
  const I=D.income||{}, L=I.dividends||[];
  if(!L.length) return;
  document.getElementById('divpanel').hidden=false;
  const ccy=L[0].display_currency, mixed=L.some(d=>d.display_currency!==ccy);
  const amt=d=>mixed?d.amount:d.display_amount, cur=mixed?L[0].currency:ccy;
  const fm=v=>cur+' '+Math.round(v).toLocaleString((D.fmt||{}).locale||'en-US');
  const fm2=v=>cur+' '+v.toFixed(2);
  const last=new Date(D.series[D.series.length-1].t), yearAgo=new Date(last.getTime()-365*864e5);
  const total=L.reduce((s,d)=>s+amt(d),0);
  const ttm=L.filter(d=>new Date(d.date)>yearAgo).reduce((s,d)=>s+amt(d),0);
  /* yield in the funds' own currency, so the exchange rate can't distort it */
  const ttmRaw=L.filter(d=>new Date(d.date)>yearAgo).reduce((s,d)=>s+d.amount,0);
  const mv=D.positions.reduce((s,p)=>s+p.market_value,0);
  const wr=I.withholding_rate||0;
  const st=(l,v,sub,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${sub}</div></div>`;
  const first=new Date(L[0].date);
  const span=(last-first)/(365.25*864e5);
  document.getElementById('divstats').innerHTML =
    st('Received', fm(total), `${L.length} payments since ${first.toLocaleDateString('en-GB',{month:'short',year:'numeric'})}`,'var(--path)') +
    st('Last 12 months', fm(ttm), span<1?'less than a year of history':'trailing twelve months','var(--path)') +
    st('Yield', mv?(ttmRaw/mv*100).toFixed(2)+'%':'—', span<1?'so far, on today’s holdings &mdash; understated':'trailing 12 months on today’s holdings','var(--ink)') +
    st('Withholding (est.)', fm(total*wr), `${(wr*100).toFixed(0)}% of gross &mdash; not reported by IBKR here`,'var(--warn)');

  /* by quarter */
  const q=new Map(); L.forEach(d=>{ const t=new Date(d.date), k=t.getFullYear()+' Q'+(Math.floor(t.getMonth()/3)+1); q.set(k,(q.get(k)||0)+amt(d)); });
  const qs=[...q.entries()], mx=Math.max(...qs.map(x=>x[1]));
  document.getElementById('divq').innerHTML = '<div class="lab" style="margin-bottom:8px">By quarter, gross</div>' + qs.map(([k,v])=>
    `<div style="display:grid;grid-template-columns:62px 1fr 92px;gap:8px;align-items:center;font-size:12px;margin:5px 0">
      <span style="font-family:var(--fn)">${k}</span>
      <span style="height:12px;background:var(--path);opacity:.8;width:${(v/mx*100).toFixed(1)}%"></span>
      <span style="text-align:right;font-family:var(--fn)">${fm2(v)}</span></div>`).join('');

  /* by fund */
  const f=new Map(); L.forEach(d=>f.set(d.ticker,(f.get(d.ticker)||0)+amt(d)));
  { const top=[...f.entries()].sort((a,b)=>b[1]-a[1])[0];
    takeaway('divq', `Your funds have paid you ${fm(total)} in dividends, about ${fm(total*(1-wr))} after tax withheld; ${esc(top[0])} paid ${Math.round(top[1]/total*100)}% of it.`); }
  document.getElementById('divtbl').innerHTML = `<thead><tr><th class="l">Fund</th><th>Gross</th><th>Est. net</th><th>Share</th></tr></thead><tbody>`
    + [...f.entries()].sort((a,b)=>b[1]-a[1]).map(([t,v])=>`<tr><td class="l">${esc(t)}</td><td>${fm2(v)}</td><td>${fm2(v*(1-wr))}</td><td>${(v/total*100).toFixed(0)}%</td></tr>`).join('')
    + '</tbody>';
  document.getElementById('divnote').innerHTML = `IBKR reports these gross. Tax withheld at source isn't in this feed, so the net column
    assumes ${(wr*100).toFixed(0)}% (the US treaty rate with a W-8BEN on file; set <code>dividends.withholding_rate</code> in config).
    Your account statement has the exact figure, and in Switzerland it can usually be reclaimed against your tax bill.
    ${mixed?'':(ccy!==L[0].currency?`Converted from ${L[0].currency} at the ECB rate on the payment day.`:'')}`;
})();

/* ---------- benchmark: your time-weighted return against a total-return index ---------- */
(function drawBenchmark(){
  const B=(D.income||{}).benchmark;
  if(!B || !D.series.length) return;
  const S=D.series, c0=1+S[0].cps;
  const you=S.map((p,i)=>[p.t,(1+p.cps)/c0-1]);
  const vt=S.map((p,i)=>[p.t,B.cps[i]]).filter(x=>x[1]!=null);
  if(vt.length<10) return;
  document.getElementById('benchpanel').hidden=false;
  const yEnd=you[you.length-1][1], bEnd=vt[vt.length-1][1], diff=yEnd-bEnd;
  const since=new Date(S[0].t).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
  document.getElementById('benchtitle').textContent=`You against ${B.ticker}, with dividends, since ${since}`;
  const st=(l,v,sub,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${sub}</div></div>`;
  document.getElementById('benchstats').innerHTML =
    st('Your portfolio', pc(yEnd), 'time-weighted, as IBKR reports it','var(--path)') +
    st(B.ticker+' total return', pc(bEnd), `dividends reinvested${B.converted?', in '+B.currency:''}`,'var(--muted)') +
    st('Difference', (diff>=0?'+':'−')+Math.abs(diff*100).toFixed(2)+' pts', diff>=0?'ahead of the benchmark':'behind the benchmark', diff>=0?'var(--path)':'var(--warn)');
  /* where the gap opened: the calendar month in which it moved most */
  {
    const byM=new Map();
    S.forEach((p,i)=>{ if(B.cps[i]==null) return; const d=new Date(p.t), k=d.getFullYear()*12+d.getMonth();
      byM.set(k,{t:p.t, gap:(1+p.cps)/c0-1-B.cps[i]}); });
    const ms=[...byM.values()]; let big=null, prev=0;
    ms.forEach(m=>{ const ch=m.gap-prev; if(!big || Math.abs(ch)>Math.abs(big.ch)) big={t:m.t, ch}; prev=m.gap; });
    takeaway('benchchart', `You are ${mag(diff,v=>pts(v))} ${diff>=0?'ahead of':'behind'} ${B.ticker} since ${new Date(S[0].t).toLocaleDateString('en-GB',{month:'long'})}`
      + (big&&Math.abs(big.ch)>0.002?`; most of the gap ${(big.ch<0)===(diff<0)?'opened':'closed'} in ${monthName(big.t)}.`:'.'));
  }
  const all=you.concat(vt).map(x=>x[1]);
  let lo=Math.min(0,...all), hi=Math.max(0,...all);
  const step=niceStep((hi-lo)/4); lo=Math.floor(lo/step)*step; hi=Math.ceil(hi/step)*step;
  const yt=[]; for(let v=lo; v<=hi+1e-9; v+=step) yt.push(v);
  const t0=S[0].t, t1=S[S.length-1].t, xt=[]; for(let i=0;i<=4;i++) xt.push(t0+(t1-t0)*i/4);
  chart(document.getElementById('benchchart'),{ height:260, xmin:t0, xmax:t1, ymin:lo, ymax:hi, yticks:yt, xticks:xt,
    yfmt:v=>(v*100).toFixed(0)+'%', xfmt:v=>new Date(v).toLocaleDateString('en-GB',{month:'short',year:'2-digit'}),
    aria:'portfolio return against the benchmark', tip:{fmt:v=>pc(v), xfmt:v=>new Date(v).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})},
    series:[ {name:B.ticker,data:vt,color:'var(--muted)',w:1.8,dash:'5 4'}, {name:'You',data:you,color:'var(--path)',w:2.4} ] });
  document.getElementById('benchnote').innerHTML = `Both lines are time-weighted, so your deposits don't count as gains. ${B.ticker} is built from
    its daily closes with each distribution reinvested on its ex-date &mdash; price alone would understate it by its yield.
    ${B.converted?`It is converted to ${B.currency} with the same ECB rates as the currency section, so the exchange rate affects both lines alike.`:''}
    A short window says little about skill: a tilt to small-cap value can trail or lead the world index for years.`;
})();

/* ---------- risk: from the time-weighted series, so deposits never look like gains ---------- */
const RISK = (function(){
  const S=(D.series||[]).filter(p=>p.cps!=null);
  if(S.length<20) return null;
  const I=S.map(p=>1+p.cps), T=S.map(p=>p.t);
  const r=[]; for(let i=1;i<I.length;i++) r.push(I[i]/I[i-1]-1);
  const years=(T[T.length-1]-T[0])/(365.25*864e5);
  const ppy=r.length/years;                          /* observations per year, whatever the calendar */
  const mean=r.reduce((s,x)=>s+x,0)/r.length;
  const sd=Math.sqrt(r.reduce((s,x)=>s+(x-mean)*(x-mean),0)/(r.length-1));
  let peak=I[0], peakT=T[0], mdd=0, mddPeakT=T[0], mddT=T[0];
  const dd=I.map((v,i)=>{ if(v>peak){peak=v; peakT=T[i];} const d=v/peak-1;
    if(d<mdd){ mdd=d; mddT=T[i]; mddPeakT=peakT; } return d; });
  /* recovery: first point after the trough back at the old high */
  let recT=null; const iT=T.indexOf(mddT), lvl=I[T.indexOf(mddPeakT)];
  for(let i=iT+1;i<I.length;i++) if(I[i]>=lvl){ recT=T[i]; break; }
  /* month-end to month-end; the first and the current month are partial */
  const mon=new Map();
  S.forEach((p,i)=>{ const d=new Date(p.t), k=d.getFullYear()*12+d.getMonth(); mon.set(k,i); });
  const keys=[...mon.keys()].sort((a,b)=>a-b), months=[];
  keys.forEach((k,j)=>{ const end=I[mon.get(k)], start=j===0?I[0]:I[mon.get(keys[j-1])];
    months.push({k, y:Math.floor(k/12), m:k%12, r:end/start-1, part:j===0||j===keys.length-1}); });
  return { vol:sd*Math.sqrt(ppy), mdd, mddT, mddPeakT, recT, cur:dd[dd.length-1], dd:T.map((t,i)=>[t,dd[i]]), months, years };
})();
(function drawRisk(){
  if(!RISK){ document.getElementById('riskbody').hidden=true; return; }
  document.getElementById('risksection').hidden=false;
  const fd=t=>new Date(t).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
  const full=RISK.months.filter(m=>!m.part);
  const best=full.length?full.reduce((a,b)=>b.r>a.r?b:a):null, worst=full.length?full.reduce((a,b)=>b.r<a.r?b:a):null;
  const ml=m=>new Date(m.y,m.m,1).toLocaleDateString('en-GB',{month:'short',year:'numeric'});
  const st=(l,v,s,c)=>`<div class="stat" style="border-color:${c}"><div class="lab">${l}</div><div class="val" style="color:${c}">${v}</div><div class="sub">${s}</div></div>`;
  document.getElementById('riskk').textContent = `${RISK.years<1?Math.round(RISK.years*12)+' months':RISK.years.toFixed(1)+' years'} of history`;
  document.getElementById('riskstats').innerHTML =
    st('Volatility', (RISK.vol*100).toFixed(1)+'%', 'yearly, from daily moves'+(RISK.years<1?' &middot; short history':''), 'var(--ink)') +
    st('Worst fall', pc(RISK.mdd), `${fd(RISK.mddPeakT)} &rarr; ${fd(RISK.mddT)}`+(RISK.recT?` &middot; recovered ${fd(RISK.recT)}`:' &middot; not yet recovered'), 'var(--warn)') +
    st('Below last high now', RISK.cur>-0.0005?'at a high':pc(RISK.cur), 'drawdown today', RISK.cur>-0.0005?'var(--path)':'var(--warn)') +
    st('Best month', best?pc(best.r):'—', best?ml(best):'needs a full month', 'var(--path)') +
    st('Worst month', worst?pc(worst.r):'—', worst?ml(worst):'needs a full month', 'var(--warn)');

  { const wk=t=>Math.max(1,Math.round(t/(7*864e5)));
    takeaway('ddchart', `The worst fall was <b class="neg">${pc(RISK.mdd)}</b> in ${monthName(RISK.mddT)}`
      + (RISK.recT?` and it was back at its high ${wk(RISK.recT-RISK.mddT)} weeks later.`:'; it has not fully recovered yet.')); }
  { const up=full.filter(m=>m.r>0).length;
    if(full.length) takeaway('heatmap', `${up} of ${full.length} full months were positive; the best was ${best?ml(best):''} at ${best?pc(best.r):''}.`); }
  const lo=Math.min(-0.01, RISK.mdd*1.15), t0=RISK.dd[0][0], t1=RISK.dd[RISK.dd.length-1][0];
  const yt=[]; const step=niceStep(-lo/4); for(let v=0; v>=lo-1e-9; v-=step) yt.push(v);
  const xt=[]; const span=t1-t0; for(let i=0;i<=4;i++) xt.push(t0+span*i/4);
  chart(document.getElementById('ddchart'),{ height:220, xmin:t0, xmax:t1, ymin:Math.min(lo,yt[yt.length-1]), ymax:0.002,
    yticks:yt, xticks:xt, yfmt:v=>(v*100).toFixed(0)+'%',
    xfmt:v=>new Date(v).toLocaleDateString('en-GB',{month:'short',year:'2-digit'}),
    aria:'drawdown from the previous high over time',
    area:RISK.dd.map(p=>[p[0],p[1],0]),
    tip:{fmt:v=>pc(v), xfmt:v=>fd(v)},
    series:[{name:'Below high',data:RISK.dd,color:'var(--warn)',w:1.6}] });

  const ys=[...new Set(RISK.months.map(m=>m.y))];
  const mx=Math.max(0.01,...RISK.months.map(m=>Math.abs(m.r)));
  const MN=['J','F','M','A','M','J','J','A','S','O','N','D'];
  let h=`<table class="heat"><thead><tr><th class="l"></th>${MN.map(x=>`<th>${x}</th>`).join('')}<th>Year</th></tr></thead><tbody>`;
  ys.forEach(y=>{
    const row=RISK.months.filter(m=>m.y===y);
    const yr=row.reduce((p,m)=>p*(1+m.r),1)-1;
    h+=`<tr><th class="l">${y}</th>`;
    for(let k=0;k<12;k++){ const m=row.find(x=>x.m===k);
      if(!m){ h+='<td></td>'; continue; }
      const a=Math.min(0.75,0.12+Math.abs(m.r)/mx*0.6), bg=m.r>=0?`rgba(27,77,62,${a.toFixed(2)})`:`rgba(168,64,43,${a.toFixed(2)})`;
      h+=`<td class="${m.part?'part':''}" style="background:${bg};color:${a>0.45?'#fff':'inherit'}" title="${ml(m)}${m.part?' (partial)':''}: ${pc(m.r)}">${(m.r*100).toFixed(1)}</td>`; }
    h+=`<td style="font-weight:600">${(yr*100).toFixed(1)}%</td></tr>`;
  });
  document.getElementById('heatmap').innerHTML=h+'</tbody></table>';
})();

function renderChartMode(){
  document.getElementById('plansection').classList.toggle('plansimple', chartMode==='simple');
  document.querySelectorAll('#chartmode button').forEach(b=>{ const on=b.dataset.cm===chartMode;
    b.classList.toggle('on',on); b.setAttribute('aria-pressed',on); });
}
document.getElementById('chartmode').addEventListener('click',ev=>{
  const b=ev.target.closest('[data-cm]'); if(!b || b.dataset.cm===chartMode) return;
  chartMode=b.dataset.cm; try{ localStorage.setItem('ibkr-fire-chartmode',chartMode); }catch(e){}
  renderChartMode(); drawProjection();
});
renderChartMode();
buildControls();
renderZoom();
renderTimeline();
renderPlanBar();
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
