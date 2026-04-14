#!/usr/bin/env python3
"""
Limitless AI Trading System - Production Dashboard v2
Bloomberg-grade trading terminal. Unified view, Chart.js charts, SSE streaming.
"""

import glob
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template_string, request, stream_with_context

app = Flask(__name__)

PORT = 8888
BASE_DIR = Path("/root/limitless-ai")
load_dotenv(BASE_DIR / "TradingAgents" / ".env")
LOGS_DIR = BASE_DIR / "logs"
KB_DIR = BASE_DIR / "knowledge_base"
DEBATES_DIR = LOGS_DIR / "debates"
COST_PER_RUN = 0.043
CRON_SCHEDULE_MINUTES = 60

# ─── SPA TEMPLATE ────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Limitless AI — Trading Terminal</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{
  --bg-0:#06060c;--bg-1:#0c0c18;--bg-2:#14142a;--bg-3:#1c1c3a;
  --border:#1a1a32;--border-soft:rgba(255,255,255,.04);
  --green:#00e676;--red:#ff1744;--amber:#ffd740;--blue:#448aff;--accent:#f0b90b;
  --green-dim:rgba(0,230,118,.08);--red-dim:rgba(255,23,68,.08);
  --amber-dim:rgba(255,215,64,.08);--accent-dim:rgba(240,185,11,.08);
  --green-glow:0 0 24px rgba(0,230,118,.25);--red-glow:0 0 24px rgba(255,23,68,.25);
  --accent-glow:0 0 24px rgba(240,185,11,.3);
  --t1:#e8e8f0;--t2:#9ca3af;--t3:#6b7280;--t4:#4b5563;
  --mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
  --sans:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
  --shadow-card:0 4px 24px rgba(0,0,0,.5);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--bg-0);color:var(--t1);font-family:var(--sans);font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased}
body{min-height:100vh}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* NAV */
.nav{position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:12px;padding:10px 20px;background:rgba(6,6,12,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:14px;font-weight:700;letter-spacing:1px;color:var(--accent)}
.brand-dot{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent);animation:pulse 2s ease infinite}
.brand-sub{font-size:9px;font-weight:500;color:var(--t3);letter-spacing:1.5px;margin-left:6px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--border);border-radius:20px;font-family:var(--mono);font-size:11px;color:var(--t2);white-space:nowrap}
.dot{width:6px;height:6px;border-radius:50%;background:var(--green);flex-shrink:0}
.sdots{display:flex;gap:10px}
.sd{display:flex;align-items:center;gap:4px;font-size:10px;font-weight:600;color:var(--t3)}.sd .d{width:7px;height:7px;border-radius:50%;background:var(--t4)}
.sd.on .d{background:var(--green);box-shadow:0 0 6px var(--green)}
.sd.off .d{background:var(--red)}
.nav-r{margin-left:auto;display:flex;gap:8px;align-items:center}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* BUTTONS */
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--border);border-radius:6px;background:var(--bg-1);color:var(--t1);font-family:var(--sans);font-size:11px;font-weight:600;cursor:pointer;transition:all .15s}
.btn:hover{border-color:var(--t4);background:var(--bg-2)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-accent{background:var(--accent-dim);border-color:var(--accent);color:var(--accent)}
.btn-accent:hover{background:var(--accent);color:#0a0a0a;box-shadow:var(--accent-glow)}
.btn-green{background:var(--green-dim);border-color:var(--green);color:var(--green)}
.btn-green:hover{background:var(--green);color:#041a0c}
.btn-red{background:var(--red-dim);border-color:var(--red);color:var(--red)}
.btn-red:hover{background:var(--red);color:#1a0408}
.btn-amber{background:var(--amber-dim);border-color:var(--amber);color:var(--amber)}
.btn-sm{padding:5px 10px;font-size:10px}
.btn-lg{padding:10px 24px;font-size:12px;font-weight:700;letter-spacing:.5px}

/* LAYOUT */
.wrap{max-width:1600px;margin:0 auto;padding:16px}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(4,1fr)}.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:1fr 1fr}
.g-dec-kpi{grid-template-columns:2fr 3fr}
.g-chart-main{grid-template-columns:65fr 35fr}
.g-6-6{grid-template-columns:1fr 1fr}
@media(max-width:1100px){.g4{grid-template-columns:repeat(2,1fr)}.g-dec-kpi,.g-chart-main,.g-6-6{grid-template-columns:1fr}}
@media(max-width:640px){.g4,.g3,.g2{grid-template-columns:1fr}}
.mt{margin-top:12px}

/* CARD */
.card{background:linear-gradient(180deg,var(--bg-1) 0%,#090914 100%);border:1px solid var(--border);border-radius:10px;padding:16px;box-shadow:var(--shadow-card);position:relative;overflow:hidden}
.card-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px}
.card-t{font-size:10px;font-weight:600;letter-spacing:1.2px;color:var(--t3);text-transform:uppercase}
.card-s{font-size:10px;color:var(--t4);font-family:var(--mono)}
.kpi{font-family:var(--mono);font-size:28px;font-weight:700;letter-spacing:-.5px}
.kpi-sm{font-family:var(--mono);font-size:16px;font-weight:500}
.row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border-soft);font-size:11px;color:var(--t2)}
.row:last-child{border:none}
.row .l{color:var(--t3)}.row .v{font-family:var(--mono)}

/* DECISION HERO */
.dec-hero{display:flex;align-items:center;gap:16px;padding:20px;border-radius:10px;position:relative;overflow:hidden;animation:fadeUp .4s ease;min-height:160px}
.dec-hero::after{content:'';position:absolute;top:0;left:-100%;width:100%;height:1px;background:linear-gradient(90deg,transparent,var(--accent),transparent);animation:scanLine 4s linear infinite}
.dec-hero.BUY{background:var(--green-dim);border:1px solid var(--green);box-shadow:var(--green-glow)}
.dec-hero.SELL{background:var(--red-dim);border:1px solid var(--red);box-shadow:var(--red-glow)}
.dec-hero.HOLD{background:var(--amber-dim);border:1px solid var(--amber)}
.dec-hero.BLOCKED{background:var(--bg-2);border:1px solid var(--t4)}
.dec-text{font-family:var(--mono);font-size:48px;font-weight:800;letter-spacing:2px;line-height:1}
.dec-hero.BUY .dec-text{color:var(--green)}.dec-hero.SELL .dec-text{color:var(--red)}
.dec-hero.HOLD .dec-text{color:var(--amber)}.dec-hero.BLOCKED .dec-text{color:var(--t3)}
.dec-meta{flex:1;display:flex;flex-direction:column;gap:6px}
.dec-conf-row{display:flex;align-items:center;gap:8px}
.dec-conf-label{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:1px}
.dec-conf-val{font-family:var(--mono);font-size:20px;font-weight:700}
.conf-bar{height:4px;background:var(--bg-0);border-radius:2px;overflow:hidden;margin:4px 0}
.conf-fill{height:100%;border-radius:2px;transition:width .6s ease,background .3s}
.dec-details{display:flex;flex-wrap:wrap;gap:12px;font-size:11px;color:var(--t2)}
.dec-details b{color:var(--t1);font-family:var(--mono)}
.dec-ts{font-size:10px;color:var(--t4);font-family:var(--mono)}
@keyframes scanLine{0%{left:-100%}100%{left:200%}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes glow{0%,100%{box-shadow:0 0 4px var(--amber)}50%{box-shadow:0 0 16px var(--amber)}}

/* CHART */
.chart-container-lg{height:380px;position:relative;padding:4px 0}
.chart-container-sm{height:200px;position:relative}
#lw-chart{width:100%;height:380px;border-radius:6px;overflow:hidden}

/* PM CARDS */
.pm-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;max-height:480px;overflow-y:auto;padding:2px}
.pm-card{background:var(--bg-0);border:1px solid var(--border);border-radius:10px;padding:14px;transition:all .2s;display:flex;flex-direction:column;gap:10px}
.pm-card:hover{border-color:var(--t4);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.4)}
.pm-card.win{border-left:3px solid var(--green)}.pm-card.loss{border-left:3px solid var(--red)}.pm-card.open{border-left:3px solid var(--blue)}
.pm-card-q{font-size:12px;color:var(--t1);font-weight:500;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:34px}
.pm-card-row{display:flex;justify-content:space-between;align-items:center}
.pm-badge{padding:3px 10px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.5px}
.pm-badge.YES{background:var(--green-dim);color:var(--green);border:1px solid rgba(0,230,118,.2)}
.pm-badge.NO{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,23,68,.2)}
.pm-edge-pill{padding:2px 8px;border-radius:12px;font-family:var(--mono);font-size:10px;font-weight:600;background:var(--accent-dim);color:var(--accent);border:1px solid rgba(240,185,11,.2)}
.pm-pnl{font-family:var(--mono);font-size:22px;font-weight:700;letter-spacing:-.5px}
.pm-pnl.positive{color:var(--green)}.pm-pnl.negative{color:var(--red)}.pm-pnl.neutral{color:var(--t3)}
.pm-prob-bar{display:flex;gap:12px;font-size:10px;color:var(--t3)}
.pm-prob-bar span{font-family:var(--mono)}
.pm-prob-bar b{color:var(--t1)}
.pm-status{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.5px}
.pm-card-footer{display:flex;justify-content:space-between;align-items:center;padding-top:8px;border-top:1px solid var(--border-soft)}
.pm-tab-bar{display:flex;gap:4px;margin-bottom:10px}
.pm-tab{padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:var(--bg-0);color:var(--t3);font-family:var(--sans);font-size:11px;font-weight:600;cursor:pointer;transition:all .15s}
.pm-tab:hover{border-color:var(--t4);color:var(--t2)}
.pm-tab.active{border-color:var(--accent);color:var(--accent);background:var(--accent-dim)}

/* LAYERS */
.layer-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media(max-width:640px){.layer-grid{grid-template-columns:repeat(2,1fr)}}
.layer{padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg-0);position:relative;transition:all .3s}
.layer .n{font-family:var(--mono);font-size:10px;font-weight:600;color:var(--t1);margin-bottom:2px}
.layer .s{font-size:9px;color:var(--t3)}
.layer::after{content:'';position:absolute;top:10px;right:10px;width:7px;height:7px;border-radius:50%;background:var(--t4)}
.layer.ok::after{background:var(--green);box-shadow:0 0 6px var(--green)}
.layer.active::after{background:var(--amber);animation:glow 1s infinite}
.layer.off::after{background:var(--red)}

/* GAUGE */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:8px 0}
.gauge{width:180px;height:100px;position:relative}
.gauge svg{width:100%;height:100%;overflow:visible}
.gauge-label{font-family:var(--mono);font-size:20px;font-weight:700;margin-top:-16px}
.gauge-sub{font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:4px}
.gauge-counts{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px;width:100%;font-family:var(--mono);font-size:10px;text-align:center}
.gc{padding:6px;border-radius:4px}
.gc.bull{background:var(--green-dim);color:var(--green)}
.gc.neu{background:var(--amber-dim);color:var(--amber)}
.gc.bear{background:var(--red-dim);color:var(--red)}

/* ACTION BAR */
.action-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 0}
.action-divider{width:1px;height:24px;background:var(--border);margin:0 4px}

/* SSE AREA */
.sse-area{display:none;margin-top:12px;animation:fadeUp .3s ease}
.sse-area.open{display:block}
.sse-header{display:flex;align-items:center;gap:16px;padding:12px 16px;background:var(--bg-1);border:1px solid var(--border);border-radius:10px 10px 0 0;border-bottom:none}
.sse-title{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--accent);letter-spacing:1.5px;text-transform:uppercase}
.sse-timer{font-family:var(--mono);font-size:22px;font-weight:700;color:var(--t1)}
.sse-progress-bar{flex:1;height:4px;background:var(--bg-0);border-radius:2px;overflow:hidden}
.sse-progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--green));width:0;transition:width .3s;border-radius:2px}
.sse-body{display:grid;grid-template-columns:3fr 2fr 2fr;gap:0;border:1px solid var(--border);border-radius:0 0 10px 10px;overflow:hidden;min-height:300px}
@media(max-width:1100px){.sse-body{grid-template-columns:1fr}}
.terminal{background:#040408;padding:12px;font-family:var(--mono);font-size:11px;color:#88cc88;white-space:pre-wrap;overflow-y:auto;line-height:1.6;max-height:400px;border-right:1px solid var(--border)}
.terminal .err{color:var(--red)}.terminal .ok{color:var(--green)}.terminal .meta{color:var(--t3)}
.terminal .m-price{color:#42a5f5}.terminal .m-mirofish{color:#ab47bc}
.terminal .m-regime{color:#ffd740}.terminal .m-elo{color:#26c6da}
.terminal .m-gdelt{color:#66bb6a}.terminal .m-kb{color:#78909c}
.terminal .m-kronos{color:#ef5350}.terminal .m-whale{color:#5c6bc0}
.terminal .m-policy{color:#8d6e63}.terminal .m-pipeline{color:#f0b90b}
.terminal .m-calibration{color:#29b6f6}
.terminal .m-decision{color:#00e676;font-weight:700;font-size:13px}
.terminal .m-risk{color:#ff7043}
.terminal .m-trade{color:#f0b90b;font-weight:700}
.terminal .m-done{color:#00e676;font-weight:700}
.sse-layers-panel{padding:12px;background:var(--bg-1);border-right:1px solid var(--border)}
.sse-decision-flash{padding:16px;text-align:center;border-radius:8px;margin-top:12px;display:none}
.sse-decision-flash.show{display:block;animation:decisionPulse 2s ease infinite}
.sse-decision-flash.BUY{background:var(--green-dim);border:2px solid var(--green);box-shadow:var(--green-glow)}
.sse-decision-flash.SELL{background:var(--red-dim);border:2px solid var(--red);box-shadow:var(--red-glow)}
.sse-decision-flash.HOLD{background:var(--amber-dim);border:2px solid var(--amber)}
.sse-decision-flash.BLOCKED{background:var(--bg-2);border:2px solid var(--t4)}
.sse-decision-text{font-family:var(--mono);font-size:36px;font-weight:800}
.sse-decision-conf{font-family:var(--mono);font-size:14px;color:var(--t2);margin-top:4px}
@keyframes decisionPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.02)}}
.sse-bets-panel{padding:12px;background:var(--bg-1)}
.sse-bet-item{padding:8px;border-bottom:1px solid var(--border-soft);animation:fadeUp .3s ease;font-size:11px;color:var(--t2)}

/* CHART LEGEND */
.chip-legend{display:inline-flex;align-items:center;gap:4px;font-size:10px;color:var(--t3);margin-left:8px}
.dot-legend{width:8px;height:8px;border-radius:50%;display:inline-block}

/* PM STATS ROW */
.pm-stats-row{display:flex;justify-content:space-around;padding:10px 0;border-top:1px solid var(--border-soft);margin-top:8px}
.pm-stat{font-size:10px;color:var(--t3);text-align:center}
.pm-stat-val{display:block;font-family:var(--mono);font-size:18px;font-weight:700;color:var(--t1)}
.pm-filter-bar{display:flex;gap:4px}
.pm-filter.active{border-color:var(--accent);color:var(--accent)}

/* REASONING DRAWER */
.reasoning-drawer{background:var(--bg-1);border:1px solid var(--border);border-radius:8px;padding:16px;max-height:300px;overflow-y:auto;display:none;animation:fadeUp .3s ease}
.reasoning-drawer.open{display:block}
.reasoning-text{font-family:var(--mono);font-size:11px;color:var(--t2);white-space:pre-wrap;line-height:1.6}

/* TIMELINE */
.tl{max-height:350px;overflow-y:auto}
.tl-row{display:grid;grid-template-columns:130px 80px 60px 1fr;gap:10px;align-items:center;padding:6px 4px;border-bottom:1px solid var(--border-soft);font-size:11px;color:var(--t2)}
.tl-row:hover{background:var(--bg-2)}
.tl-row .ts{font-family:var(--mono);font-size:10px;color:var(--t3)}

/* POSITIONS */
.pos-grid{max-height:350px;overflow-y:auto}
.pos-row{display:grid;grid-template-columns:1fr auto;gap:8px;padding:8px 4px;border-bottom:1px solid var(--border-soft);font-size:11px;align-items:center}
.pos-row:hover{background:var(--bg-2)}
.pos-q{color:var(--t2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pos-meta{display:flex;gap:10px;align-items:center;font-family:var(--mono);font-size:10px}

/* BACKTEST */
.bt-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:8px;font-size:11px;color:var(--t2)}
.bt-controls input[type=number]{background:var(--bg-0);border:1px solid var(--border);border-radius:4px;color:var(--t1);padding:4px 6px;font-family:var(--mono);font-size:11px}
.bt-controls input[type=checkbox]{accent-color:var(--accent)}
.bt-progress{height:3px;background:var(--bg-0);border-radius:2px;overflow:hidden;margin-bottom:8px}
.bt-progress-fill{height:100%;background:var(--accent);width:0;transition:width .3s}

/* PRICE FLASH */
.flash{animation:priceFlash .5s ease}
@keyframes priceFlash{0%{color:var(--accent)}100%{color:var(--t1)}}

.empty{color:var(--t4);font-style:italic;padding:20px;text-align:center}
.footer{text-align:center;padding:16px;font-size:10px;color:var(--t4);border-top:1px solid var(--border);margin-top:16px}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav">
  <div class="brand"><div class="brand-dot"></div>LIMITLESS<span class="brand-sub">AI TRADING TERMINAL</span></div>
  <span class="pill" id="btc-pill"><span class="dot" style="background:var(--accent)"></span>BTC <span id="btc-price">--</span></span>
  <div class="sdots" id="status-dots">
    <span class="sd" id="sd-vps"><span class="d"></span>VPS</span>
    <span class="sd" id="sd-mf"><span class="d"></span>MF</span>
    <span class="sd" id="sd-alpaca"><span class="d"></span>ALP</span>
    <span class="sd" id="sd-or"><span class="d"></span>OR</span>
  </div>
  <div class="nav-r">
    <span class="pill"><span id="run-count">--</span> runs</span>
    <span class="pill"><span class="dot"></span><span id="last-ts">--</span></span>
  </div>
</nav>

<div class="wrap">

<!-- ROW 1: Decision + KPIs -->
<div class="grid g-dec-kpi">
  <div class="dec-hero HOLD" id="dec-hero">
    <div>
      <div class="dec-text" id="dec-text">--</div>
      <div class="dec-ts" id="dec-ts">--</div>
    </div>
    <div class="dec-meta">
      <div class="dec-conf-row">
        <span class="dec-conf-label">Confidence</span>
        <span class="dec-conf-val" id="dec-conf">--%</span>
      </div>
      <div class="conf-bar"><div class="conf-fill" id="conf-fill" style="width:0"></div></div>
      <div class="dec-details">
        <span>Regime: <b id="dec-regime">--</b></span>
        <span>Price: <b id="dec-price">--</b></span>
        <span>Asset: <b id="dec-asset">--</b></span>
      </div>
    </div>
  </div>
  <div class="grid g4 kpi-strip">
    <div class="card">
      <div class="card-h"><div class="card-t">Portfolio</div></div>
      <div class="kpi" id="kpi-portfolio">$100,000</div>
      <div class="row"><span class="l">Cash</span><span class="v" id="kpi-cash">--</span></div>
      <div class="row"><span class="l">BTC</span><span class="v" id="kpi-btc">--</span></div>
      <div class="row"><span class="l">W / L</span><span class="v" id="kpi-wl">--</span></div>
    </div>
    <div class="card">
      <div class="card-h"><div class="card-t">Pipeline</div></div>
      <div class="kpi" id="kpi-runs">--</div>
      <div class="row"><span class="l">Avg Conf</span><span class="v" id="kpi-avg-conf">--</span></div>
      <div class="row"><span class="l">Decisions</span><span class="v" id="kpi-decisions">--</span></div>
      <div class="row"><span class="l">Cost</span><span class="v" id="kpi-cost">--</span></div>
    </div>
    <div class="card">
      <div class="card-h"><div class="card-t">Backtest</div></div>
      <div class="kpi" id="kpi-bt-wr">--</div>
      <div class="row"><span class="l">W / L</span><span class="v" id="kpi-bt-wl">--</span></div>
      <div class="row"><span class="l">Expectancy</span><span class="v" id="kpi-bt-exp">--</span></div>
      <div class="row"><span class="l">SaaS Ready</span><span class="v" id="kpi-bt-ready">--</span></div>
    </div>
    <div class="card">
      <div class="card-h"><div class="card-t">Polymarket</div></div>
      <div class="kpi" id="kpi-pm-wr">--</div>
      <div class="row"><span class="l">Positions</span><span class="v" id="kpi-pm-total">--</span></div>
      <div class="row"><span class="l">Resolved</span><span class="v" id="kpi-pm-res">--</span></div>
      <div class="row"><span class="l">W / L</span><span class="v" id="kpi-pm-wl">--</span></div>
    </div>
  </div>
</div>

<!-- ROW 2: CHARTS + PM CARDS -->
<div class="grid g-chart-main mt">
  <div class="card" style="padding:12px 12px 8px">
    <div class="card-h">
      <div class="card-t">BTC Price + Decisions</div>
      <div style="display:flex;gap:2px">
        <span class="chip-legend"><span class="dot-legend" style="background:var(--green)"></span>BUY</span>
        <span class="chip-legend"><span class="dot-legend" style="background:var(--red)"></span>SELL</span>
        <span class="chip-legend"><span class="dot-legend" style="background:var(--amber)"></span>HOLD</span>
        <span class="chip-legend"><span class="dot-legend" style="background:var(--blue)"></span>Confidence</span>
      </div>
    </div>
    <div id="lw-chart"></div>
  </div>
  <div class="card">
    <div class="card-h">
      <div class="card-t">Polymarket Paper Bets</div>
      <div style="display:flex;gap:6px;align-items:center">
        <span class="card-s" id="pm-chart-count">--</span>
        <span class="pm-stat-val" id="pm-wr" style="font-size:14px">--</span>
      </div>
    </div>
    <div class="pm-tab-bar" id="pm-tab-bar">
      <button class="pm-tab active" data-f="all" onclick="filterPM('all')">All</button>
      <button class="pm-tab" data-f="open" onclick="filterPM('open')">Open <span id="pm-open-count"></span></button>
      <button class="pm-tab" data-f="win" onclick="filterPM('win')">Wins</button>
      <button class="pm-tab" data-f="loss" onclick="filterPM('loss')">Losses</button>
    </div>
    <div class="pm-cards" id="pm-cards"><div class="empty">Loading positions...</div></div>
    <div class="pm-stats-row">
      <div class="pm-stat"><span class="pm-stat-val" id="pm-resolved">--</span>Resolved</div>
      <div class="pm-stat"><span class="pm-stat-val" id="pm-open">--</span>Open</div>
      <div class="pm-stat"><span class="pm-stat-val" id="pm-best-call" style="font-size:11px;color:var(--green)">--</span>Best Call</div>
    </div>
  </div>
</div>

<!-- ROW 3: MiroFish + Layers + Confidence Trend + Decision Donut -->
<div class="grid g4 mt">
  <div class="card">
    <div class="card-h"><div class="card-t">MiroFish Sentiment</div><div class="card-s" id="mf-ts">--</div></div>
    <div class="gauge-wrap">
      <div class="gauge">
        <svg viewBox="0 0 200 110">
          <defs><linearGradient id="gg" x1="0" x2="1"><stop offset="0%" stop-color="#ff1744"/><stop offset="50%" stop-color="#ffd740"/><stop offset="100%" stop-color="#00e676"/></linearGradient></defs>
          <path d="M 15 100 A 85 85 0 0 1 185 100" fill="none" stroke="#1a1a32" stroke-width="12" stroke-linecap="round"/>
          <path d="M 15 100 A 85 85 0 0 1 185 100" fill="none" stroke="url(#gg)" stroke-width="8" stroke-linecap="round" opacity=".6"/>
          <line id="needle" x1="100" y1="100" x2="100" y2="22" stroke="var(--t1)" stroke-width="2.5" stroke-linecap="round" style="transition:transform .8s ease;transform-origin:100px 100px"/>
        </svg>
      </div>
      <div class="gauge-label" id="mf-label">--</div>
      <div class="gauge-sub" id="mf-sub">score -- · -- agents</div>
    </div>
    <div class="gauge-counts">
      <div class="gc bull"><div id="mf-bull">0</div>BULL</div>
      <div class="gc neu"><div id="mf-neu">0</div>NEU</div>
      <div class="gc bear"><div id="mf-bear">0</div>BEAR</div>
    </div>
  </div>
  <div class="card">
    <div class="card-h"><div class="card-t">12 Signal Layers</div><div class="card-s">intelligence grid</div></div>
    <div class="layer-grid" id="layer-grid"></div>
  </div>
  <div class="card">
    <div class="card-h"><div class="card-t">Confidence Trend</div><div class="card-s" id="conf-trend-count">--</div></div>
    <div class="chart-container-sm"><canvas id="chart-conf"></canvas></div>
  </div>
  <div class="card">
    <div class="card-h"><div class="card-t">Decision Distribution</div><div class="card-s" id="donut-total">--</div></div>
    <div class="chart-container-sm"><canvas id="chart-donut"></canvas></div>
  </div>
</div>

<!-- ACTION BAR -->
<div class="action-bar mt">
  <button class="btn btn-accent btn-lg" id="run-btn" onclick="runPipeline()">&#9654; RUN PIPELINE</button>
  <button class="btn btn-accent btn-sm" id="bt-btn" onclick="toggleBacktest()">&#9654; RUN BACKTEST</button>
  <div class="action-divider"></div>
  <button class="btn btn-green btn-sm" onclick="followDecision()">FOLLOW AI</button>
  <button class="btn btn-green btn-sm" onclick="overrideTrade('BUY')">BUY</button>
  <button class="btn btn-red btn-sm" onclick="overrideTrade('SELL')">SELL</button>
  <button class="btn btn-amber btn-sm" onclick="overrideTrade('HOLD')">HOLD</button>
  <div style="flex:1"></div>
  <button class="btn btn-sm" onclick="toggleReasoning()">REASONING &#9662;</button>
</div>
<div class="reasoning-drawer" id="reasoning-drawer"><pre class="reasoning-text" id="reasoning-text"></pre></div>

<!-- SSE PIPELINE EXECUTION -->
<div class="sse-area" id="sse-area">
  <div class="sse-header">
    <div class="sse-title">Pipeline Execution</div>
    <div class="sse-timer" id="sse-timer">00:00</div>
    <div class="sse-progress-bar"><div class="sse-progress-fill" id="sse-progress"></div></div>
  </div>
  <div class="sse-body">
    <div class="terminal" id="sse-log"></div>
    <div class="sse-layers-panel">
      <div class="card-t" style="margin-bottom:8px">Layer Progress</div>
      <div class="layer-grid" id="sse-layers"></div>
      <div class="sse-decision-flash" id="sse-flash">
        <div class="sse-decision-text" id="sse-flash-text">--</div>
        <div class="sse-decision-conf" id="sse-flash-conf"></div>
      </div>
    </div>
    <div class="sse-bets-panel">
      <div class="card-t" style="margin-bottom:8px">Live Activity</div>
      <div id="sse-bets"><div class="empty">Awaiting pipeline...</div></div>
    </div>
  </div>
</div>

<!-- BACKTEST PANEL -->
<div class="card mt" id="bt-panel" style="display:none">
  <div class="card-h"><div class="card-t">Backtest Engine</div><div class="card-s">historical validation</div></div>
  <div class="bt-controls">
    <label>Days: <input type="number" id="bt-days" value="30" min="1" max="365"></label>
    <label>Batch: <input type="number" id="bt-batch" value="5" min="1" max="20"></label>
    <label><input type="checkbox" id="bt-fast"> Fast</label>
    <button class="btn btn-accent btn-sm" onclick="runBacktest()">&#9654; Execute</button>
  </div>
  <div class="bt-progress"><div class="bt-progress-fill" id="bt-progress-fill"></div></div>
  <div class="terminal" id="bt-log" style="max-height:250px;display:none"></div>
</div>

<!-- ROW 6: Timeline -->
<div class="card mt">
  <div class="card-h"><div class="card-t">Pipeline Timeline</div><div class="card-s" id="tl-count">--</div></div>
  <div class="tl" id="timeline"><div class="empty">Loading...</div></div>
</div>

</div><!-- /wrap -->

<div class="footer">LIMITLESS AI · 12-layer signal stack · auto-refresh 60s · SSE streaming</div>

<script>
const $=id=>document.getElementById(id);
const fmt=(n,d=2)=>n!=null?Number(n).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d}):'--';
const decColor=d=>({BUY:'var(--green)',SELL:'var(--red)',HOLD:'var(--amber)',BLOCKED:'var(--t3)'}[d]||'var(--t3)');
const decHex=d=>({BUY:'#00e676',SELL:'#ff1744',HOLD:'#ffd740',BLOCKED:'#4b5563'}[d]||'#4b5563');

const LAYERS=[
  {id:1,name:'Price Feed',marker:'[PRICE]'},
  {id:2,name:'MiroFish',marker:'[MIROFISH]'},
  {id:3,name:'Regime',marker:'[REGIME]'},
  {id:4,name:'Elo Weights',marker:'[ELO]'},
  {id:5,name:'GDELT Geo',marker:'[GDELT]'},
  {id:6,name:'Knowledge',marker:'[KB]'},
  {id:7,name:'Kronos',marker:'[L10:Kronos]'},
  {id:8,name:'Whale Mon',marker:'[L11:Whale]'},
  {id:9,name:'Policy',marker:'[L12:Policy]'},
  {id:10,name:'TradingAgents',marker:'[PIPELINE]'},
  {id:11,name:'Calibration',marker:'[CALIBRATION]'},
  {id:12,name:'Risk Mgr',marker:'[RISK]'},
];

const MARKER_CSS={
  '[PRICE]':'m-price','[MIROFISH]':'m-mirofish','[REGIME]':'m-regime','[ELO]':'m-elo',
  '[GDELT]':'m-gdelt','[KB]':'m-kb','[L10:Kronos]':'m-kronos','[L11:Whale]':'m-whale',
  '[L12:Policy]':'m-policy','[PIPELINE]':'m-pipeline','[CALIBRATION]':'m-calibration',
  '[DECISION]':'m-decision','[RISK]':'m-risk','[TRADE]':'m-trade','[DONE]':'m-done'
};

const S={running:false,btRunning:false,charts:{},pmFilter:'all',pmData:[],sseStart:null};

// ── Layer grid renderers ──
function renderStaticLayers(dec){
  const grid=$('layer-grid');
  grid.innerHTML=LAYERS.map(l=>{
    let cls='layer',status='READY';
    if(dec&&dec.decision&&dec.decision!=='error'){cls='layer ok';status='ONLINE';}
    return `<div class="${cls}" id="sl-${l.id}"><div class="n">L${l.id} ${l.name}</div><div class="s">${status}</div></div>`;
  }).join('');
}

function renderSSELayers(){
  $('sse-layers').innerHTML=LAYERS.map(l=>
    `<div class="layer" id="sse-l-${l.id}"><div class="n">L${l.id} ${l.name}</div><div class="s">WAITING</div></div>`
  ).join('');
}

function setGauge(score,label,sub){
  const angle=(score||0)*90;
  $('needle').style.transform=`rotate(${angle}deg)`;
  $('mf-label').textContent=label||'--';
  $('mf-label').style.color=score>0.2?'var(--green)':score<-0.2?'var(--red)':'var(--amber)';
  if(sub)$('mf-sub').textContent=sub;
}

// ── Charts init ──
function initCharts(){
  const darkOpts={
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{backgroundColor:'#0c0c18',borderColor:'#1a1a32',borderWidth:1,padding:10,titleFont:{family:'JetBrains Mono',size:10},bodyFont:{family:'JetBrains Mono',size:10}}},
    scales:{x:{ticks:{color:'#6b7280',font:{family:'JetBrains Mono',size:9},maxRotation:0},grid:{color:'#111128'}},y:{ticks:{color:'#6b7280',font:{family:'JetBrains Mono',size:10}},grid:{color:'#111128'}}},
    animation:{duration:800,easing:'easeOutQuart'}
  };

  // 1. MAIN: Lightweight Charts candlestick + confidence line
  try{
    const lwContainer=$('lw-chart');
    S.charts.lwChart=LightweightCharts.createChart(lwContainer,{
      width:lwContainer.clientWidth,height:380,
      layout:{background:{type:'solid',color:'#0a0a0f'},textColor:'#6b7280',fontFamily:'JetBrains Mono',fontSize:10},
      grid:{vertLines:{color:'#111128'},horzLines:{color:'#111128'}},
      crosshair:{mode:0,vertLine:{color:'rgba(240,185,11,.3)',width:1,style:2},horzLine:{color:'rgba(240,185,11,.3)',width:1,style:2}},
      rightPriceScale:{borderColor:'#1a1a32',scaleMargins:{top:0.1,bottom:0.2}},
      timeScale:{borderColor:'#1a1a32',timeVisible:true,secondsVisible:false,rightOffset:2}
    });
    S.charts.candleSeries=S.charts.lwChart.addCandlestickSeries({
      upColor:'#00e676',downColor:'#ff1744',borderUpColor:'#00e676',borderDownColor:'#ff1744',
      wickUpColor:'#00e676',wickDownColor:'#ff1744'
    });
    S.charts.confSeries=S.charts.lwChart.addLineSeries({
      color:'#448aff',lineWidth:2,lineStyle:2,
      priceScaleId:'conf',priceFormat:{type:'custom',formatter:v=>v.toFixed(0)+'%'}
    });
    S.charts.lwChart.priceScale('conf').applyOptions({scaleMargins:{top:0.7,bottom:0.02},borderColor:'#1a1a32'});
    new ResizeObserver(()=>{if(lwContainer.clientWidth>0)S.charts.lwChart.applyOptions({width:lwContainer.clientWidth});}).observe(lwContainer);
  }catch(e){console.error('LW Charts init failed:',e);}

  // 3. CONFIDENCE TREND
  const ctxC=$('chart-conf').getContext('2d');
  const gC=ctxC.createLinearGradient(0,0,0,200);
  gC.addColorStop(0,'rgba(68,138,255,.25)');gC.addColorStop(1,'rgba(68,138,255,0)');
  S.charts.conf=new Chart(ctxC,{
    type:'line',
    data:{labels:[],datasets:[{data:[],borderColor:'#448aff',backgroundColor:gC,borderWidth:2,fill:true,tension:.3,pointRadius:4,pointBorderWidth:1,pointBorderColor:'#06060c',pointBackgroundColor:[]}]},
    options:{...darkOpts,scales:{...darkOpts.scales,y:{...darkOpts.scales.y,min:0,max:100,ticks:{...darkOpts.scales.y.ticks,callback:v=>v+'%'}}}}
  });

  // 4. DECISION DONUT
  S.charts.donut=new Chart($('chart-donut').getContext('2d'),{
    type:'doughnut',
    data:{labels:['HOLD','SELL','BUY','BLOCKED'],datasets:[{data:[0,0,0,0],backgroundColor:['rgba(255,215,64,.7)','rgba(255,23,68,.7)','rgba(0,230,118,.7)','rgba(75,85,99,.5)'],borderColor:['#ffd740','#ff1744','#00e676','#4b5563'],borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:'65%',
      plugins:{legend:{position:'bottom',labels:{color:'#6b7280',font:{family:'JetBrains Mono',size:9},padding:12,boxWidth:10}},tooltip:darkOpts.plugins.tooltip},
      animation:{animateRotate:true,duration:1000}
    }
  });
}

// ── Data loaders ──
async function loadDashboard(){
  try{
    const [decR,perfR,btR,pmR]=await Promise.all([
      fetch('/api/latest-decision'),fetch('/api/performance'),
      fetch('/api/backtest-summary'),fetch('/api/polymarket')
    ]);
    const dec=await decR.json(),perf=await perfR.json(),bt=await btR.json(),pm=await pmR.json();
    updateDecision(dec);
    updateKPIs(perf,bt,pm);
    updateMainChart(perf);
    updatePMCards(pm);
    updateConfTrend(perf);
    updateDonut(perf);
    renderStaticLayers(dec);
    updateMiroFish(dec);
    updateTimeline(perf);
    // PM cards already updated by updatePMCards
  }catch(e){console.error('Dashboard load:',e);}
}

function updateDecision(d){
  if(d.error)return;
  const hero=$('dec-hero');
  hero.className='dec-hero '+(d.decision||'HOLD');
  $('dec-text').textContent=d.decision||'--';
  $('dec-conf').textContent=(d.confidence||0)+'%';
  $('dec-conf').style.color=decColor(d.decision);
  const cf=$('conf-fill');
  cf.style.width=(d.confidence||0)+'%';
  cf.style.background=decColor(d.decision);
  $('dec-regime').textContent=d.regime||'--';
  $('dec-price').textContent='$'+fmt(d.price);
  $('dec-asset').textContent=d.asset||'BTC-USD';
  $('dec-ts').textContent=d.time_ago||'--';
  $('btc-price').textContent='$'+fmt(d.price);
  $('last-ts').textContent=new Date().toISOString().slice(0,16).replace('T',' ');
  if(d.reasoning){
    $('reasoning-text').textContent=(d.reasoning||'').substring(0,2000);
  }
  // MiroFish
  const mf=d.mirofish;
  if(mf&&mf.detail&&mf.detail.results&&mf.detail.results[0]){
    const r=mf.detail.results[0];
    setGauge(r.sentiment_score,r.sentiment_label,'score '+fmt(r.sentiment_score,3)+' · '+r.agent_count+' agents');
    $('mf-ts').textContent=r.timestamp||'--';
    const c=r.counts||{};
    $('mf-bull').textContent=c.BULLISH||0;
    $('mf-neu').textContent=c.NEUTRAL||0;
    $('mf-bear').textContent=c.BEARISH||0;
  }
}

function updateMiroFish(d){
  // Already handled in updateDecision
}

function updateKPIs(perf,bt,pm){
  const p=perf.portfolio||{};
  $('kpi-portfolio').textContent='$'+fmt(p.cash||100000);
  $('kpi-cash').textContent='$'+fmt(p.cash||100000);
  $('kpi-btc').textContent=fmt(p.btc_units||0,4)+' BTC';
  $('kpi-wl').textContent=(p.wins||0)+'W / '+(p.losses||0)+'L';
  $('kpi-runs').textContent=perf.total_runs||0;
  $('run-count').textContent=perf.total_runs||0;
  $('kpi-avg-conf').textContent=(perf.avg_confidence||0)+'%';
  const decs=perf.decisions||{};
  $('kpi-decisions').textContent=Object.entries(decs).map(([k,v])=>v+k[0]).join(' ');
  $('kpi-cost').textContent='$'+fmt((perf.total_runs||0)*0.043);
  const s=bt.summary||{};
  $('kpi-bt-wr').textContent=s.win_rate?fmt(s.win_rate*100,1)+'%':'--';
  $('kpi-bt-wl').textContent=(s.wins||0)+'W / '+(s.losses||0)+'L';
  $('kpi-bt-exp').textContent=s.expectancy_per_trade?fmt(s.expectancy_per_trade,2):'--';
  $('kpi-bt-ready').textContent=s.ready_for_saas?'YES':'NO';
  $('kpi-bt-ready').style.color=s.ready_for_saas?'var(--green)':'var(--red)';
  const pp=bt.polymarket_performance||{};
  const pmWR=pp.win_rate;
  $('kpi-pm-wr').textContent=pmWR!=null?fmt(pmWR*100,1)+'%':'--';
  $('kpi-pm-wr').style.color=pmWR>=0.5?'var(--green)':'var(--red)';
  $('kpi-pm-total').textContent=pp.total_positions||pm.length||'--';
  $('kpi-pm-res').textContent=pp.resolved||'--';
  $('kpi-pm-wl').textContent=(pp.wins||0)+'W / '+(pp.losses||0)+'L';
}

function updateMainChart(perf){
  const conf=perf.confidence||[];
  const btc=conf.filter(r=>r.price>1000);
  if(!btc.length||!S.charts.candleSeries)return;

  // Build candlestick data from pipeline runs — each run becomes a candle
  // Since we have point-in-time prices, synthesize OHLC with slight variance for visual effect
  const candles=btc.map(r=>{
    const t=Math.floor(new Date(r.x).getTime()/1000);
    const p=r.price;
    const spread=p*0.002; // 0.2% spread for visual candlestick body
    const isUp=r.decision==='BUY'||r.confidence>=60;
    return {
      time:t,
      open:isUp?p-spread:p+spread,
      high:p+spread*1.5,
      low:p-spread*1.5,
      close:isUp?p+spread:p-spread
    };
  }).sort((a,b)=>a.time-b.time);

  // Deduplicate timestamps (Lightweight Charts requires unique times)
  const seen=new Set();
  const uniqueCandles=candles.filter(c=>{if(seen.has(c.time))return false;seen.add(c.time);return true;});
  S.charts.candleSeries.setData(uniqueCandles);

  // Decision markers via setMarkers
  const markers=btc.map(r=>{
    const t=Math.floor(new Date(r.x).getTime()/1000);
    const d=r.decision;
    if(d==='BUY')return{time:t,position:'belowBar',color:'#00e676',shape:'arrowUp',text:'BUY '+r.y+'%'};
    if(d==='SELL')return{time:t,position:'aboveBar',color:'#ff1744',shape:'arrowDown',text:'SELL '+r.y+'%'};
    if(d==='HOLD')return{time:t,position:'aboveBar',color:'#ffd740',shape:'circle',text:'HOLD '+r.y+'%'};
    return{time:t,position:'aboveBar',color:'#4b5563',shape:'circle',text:(d||'?')+' '+r.y+'%'};
  }).sort((a,b)=>a.time-b.time);
  // Deduplicate marker timestamps
  const mSeen=new Set();
  const uniqueMarkers=markers.filter(m=>{if(mSeen.has(m.time))return false;mSeen.add(m.time);return true;});
  S.charts.candleSeries.setMarkers(uniqueMarkers);

  // Confidence line on right scale
  const confData=btc.map(r=>({time:Math.floor(new Date(r.x).getTime()/1000),value:r.y})).sort((a,b)=>a.time-b.time);
  const cSeen=new Set();
  const uniqueConf=confData.filter(c=>{if(cSeen.has(c.time))return false;cSeen.add(c.time);return true;});
  S.charts.confSeries.setData(uniqueConf);

  S.charts.lwChart.timeScale().fitContent();
}

function updatePMCards(pm){
  const tW=pm.filter(p=>p.win===true).length;
  const tL=pm.filter(p=>p.win===false).length;
  const tO=pm.filter(p=>p.win===undefined||p.win===null).length;
  const tR=tW+tL;
  $('pm-wr').textContent=tR>0?fmt(tW/tR*100,1)+'% WR':'--';
  $('pm-wr').style.color=tR>0&&tW/tR>=.5?'var(--green)':'var(--red)';
  $('pm-resolved').textContent=tR;
  $('pm-open').textContent=tO;
  $('pm-open-count').textContent='('+tO+')';
  $('pm-chart-count').textContent=pm.length+' positions';
  // Find best call
  const resolved=pm.filter(p=>p.win===true);
  if(resolved.length){
    const best=resolved.reduce((a,b)=>(a.edge||0)>(b.edge||0)?a:b);
    const q=(best.market_question||'').substring(0,40);
    $('pm-best-call').textContent=q+(q.length<(best.market_question||'').length?'...':'');
    $('pm-best-call').title=best.market_question||'';
  }
  S.pmData=pm;
  updatePMTable(pm);
}

function updateConfTrend(perf){
  const conf=perf.confidence||[];
  if(!conf.length)return;
  const labels=conf.map(r=>new Date(r.x).toLocaleDateString('en',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}));
  const data=conf.map(r=>r.y);
  const colors=conf.map(r=>decHex(r.decision));
  S.charts.conf.data.labels=labels;
  S.charts.conf.data.datasets[0].data=data;
  S.charts.conf.data.datasets[0].pointBackgroundColor=colors;
  S.charts.conf.update();
  $('conf-trend-count').textContent=conf.length+' runs';
}

function updateDonut(perf){
  const d=perf.decisions||{};
  S.charts.donut.data.datasets[0].data=[d.HOLD||0,d.SELL||0,d.BUY||0,d.BLOCKED||0];
  S.charts.donut.update();
  $('donut-total').textContent=(perf.total_runs||0)+' runs';
}

function updateTimeline(perf){
  const conf=perf.confidence||[];
  if(!conf.length){$('timeline').innerHTML='<div class="empty">No runs yet</div>';return;}
  $('tl-count').textContent=conf.length+' total runs';
  $('timeline').innerHTML=conf.slice().reverse().map(r=>{
    const ts=new Date(r.x).toLocaleString('en',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const dc=r.decision||'--';
    return `<div class="tl-row"><span class="ts">${ts}</span><span style="color:${decColor(dc)};font-weight:700;font-family:var(--mono)">${dc}</span><span style="font-family:var(--mono)">${r.y}%</span><span style="font-family:var(--mono);color:var(--t3)">$${fmt(r.price)}</span></div>`;
  }).join('');
}

function filterPM(f){
  S.pmFilter=f;
  document.querySelectorAll('.pm-tab').forEach(b=>b.classList.toggle('active',b.dataset.f===f));
  updatePMTable(S.pmData);
}

function updatePMTable(pm){
  let filtered=pm;
  if(S.pmFilter==='open')filtered=pm.filter(p=>p.win===undefined||p.win===null);
  else if(S.pmFilter==='win')filtered=pm.filter(p=>p.win===true);
  else if(S.pmFilter==='loss')filtered=pm.filter(p=>p.win===false);
  const el=$('pm-cards');
  if(!filtered.length){el.innerHTML='<div class="empty">No positions match filter</div>';return;}
  el.innerHTML=filtered.slice(-40).reverse().map(p=>{
    const q=p.market_question||'Unknown market';
    const edge=((p.edge||0)*100).toFixed(1);
    const side=p.side||'YES';
    const entryProb=((p.entry_prob||0)*100).toFixed(1);
    const sysProb=((p.system_prob||0)*100).toFixed(1);
    const stake=p.stake_usdc||25;
    // PnL calc: if resolved, estimate based on win/loss and stake
    let pnlVal=0,pnlClass='neutral',pnlText='--';
    if(p.pnl_usdc!=null){pnlVal=p.pnl_usdc;pnlClass=pnlVal>0?'positive':'negative';pnlText=(pnlVal>0?'+':'')+fmt(pnlVal);}
    else if(p.win===true){pnlVal=stake*(1/Math.max(p.entry_prob||0.5,0.01)-1);pnlClass='positive';pnlText='+$'+fmt(pnlVal);}
    else if(p.win===false){pnlVal=-stake;pnlClass='negative';pnlText='-$'+fmt(stake);}
    else{pnlText='$'+fmt(stake);pnlClass='neutral';}
    // Status
    let statusText='OPEN',statusColor='var(--blue)',cardClass='open';
    if(p.win===true){statusText='WIN';statusColor='var(--green)';cardClass='win';}
    else if(p.win===false){statusText='LOSS';statusColor='var(--red)';cardClass='loss';}
    // Date
    const opened=p.opened_at?new Date(p.opened_at).toLocaleDateString('en',{month:'short',day:'numeric'}):'--';
    return `<div class="pm-card ${cardClass}">
      <div class="pm-card-q" title="${esc(q)}">${esc(q)}</div>
      <div class="pm-card-row">
        <div class="pm-pnl ${pnlClass}">${pnlText}</div>
        <span class="pm-edge-pill">${edge}% edge</span>
      </div>
      <div class="pm-prob-bar">
        <span>Entry: <b>${entryProb}%</b></span>
        <span>System: <b>${sysProb}%</b></span>
        <span>Stake: <b>$${stake}</b></span>
      </div>
      <div class="pm-card-footer">
        <span class="pm-badge ${side}">${side}</span>
        <span class="pm-status" style="color:${statusColor}">${statusText}</span>
        <span style="font-size:10px;color:var(--t4)">${opened}</span>
      </div>
    </div>`;
  }).join('');
}

// ── Status ──
async function loadStatus(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    const s=d.services||{};
    $('sd-vps').className='sd '+(s.dashboard?'on':'off');
    $('sd-mf').className='sd '+(s.mirofish?'on':'off');
    $('sd-alpaca').className='sd '+(s.alpaca?'on':'off');
    $('sd-or').className='sd '+(s.anthropic?'on':'off');
  }catch(e){}
}

// ── SSE Pipeline ──
async function runPipeline(){
  if(S.running)return;
  S.running=true;
  $('run-btn').disabled=true;$('run-btn').textContent='RUNNING...';
  const area=$('sse-area');area.classList.add('open');
  const log=$('sse-log');log.innerHTML='<span class="meta">[starting pipeline...]</span>\n';
  renderSSELayers();
  $('sse-flash').className='sse-decision-flash';$('sse-flash').style.display='none';
  $('sse-bets').innerHTML='<div class="empty">Awaiting pipeline...</div>';

  S.sseStart=Date.now();
  const timer=setInterval(()=>{
    const el=Math.floor((Date.now()-S.sseStart)/1000);
    $('sse-timer').textContent=String(Math.floor(el/60)).padStart(2,'0')+':'+String(el%60).padStart(2,'0');
  },1000);

  const completed=new Set();
  try{
    const resp=await fetch('/api/run-pipeline',{method:'POST'});
    const reader=resp.body.getReader();
    const dec=new TextDecoder();
    let buf='',evt='message';
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split('\n');buf=lines.pop();
      for(const line of lines){
        if(line.startsWith('event: ')){evt=line.slice(7);continue;}
        if(!line.startsWith('data: '))continue;
        let msg=line.slice(6);
        try{const j=JSON.parse(msg);msg=j.message||msg;}catch(e){}

        // Syntax highlight
        let cls='';
        for(const[marker,c] of Object.entries(MARKER_CSS)){if(msg.includes(marker)){cls=c;break;}}
        if(evt==='error')log.innerHTML+=`<span class="err">${esc(msg)}</span>\n`;
        else if(evt==='done')log.innerHTML+=`<span class="ok">[pipeline finished]</span>\n`;
        else log.innerHTML+=cls?`<span class="${cls}">${esc(msg)}</span>\n`:esc(msg)+'\n';
        log.scrollTop=log.scrollHeight;

        // Layer progress
        LAYERS.forEach(l=>{
          if(!completed.has(l.id)&&msg.includes(l.marker)){
            completed.add(l.id);
            const el=$('sse-l-'+l.id);
            if(el){el.className='layer ok';el.querySelector('.s').textContent='DONE';}
          }
        });
        $('sse-progress').style.width=(completed.size/LAYERS.length*100)+'%';

        // Activate next layer
        for(const l of LAYERS){
          if(!completed.has(l.id)){
            const el=$('sse-l-'+l.id);
            if(el&&!el.classList.contains('active')&&!el.classList.contains('ok')){
              el.className='layer active';el.querySelector('.s').textContent='RUNNING';
            }
            break;
          }
        }

        // Decision flash
        if(msg.includes('[DECISION]')){
          const m=msg.match(/(BUY|SELL|HOLD|BLOCKED)/);
          if(m){
            const fl=$('sse-flash');
            fl.style.display='block';
            fl.className='sse-decision-flash show '+m[1];
            $('sse-flash-text').textContent=m[1];
            $('sse-flash-text').style.color=decColor(m[1]);
          }
        }

        // Live activity feed
        if(msg.includes('[TRADE]')||msg.includes('[DECISION]')||msg.includes('[RISK]')){
          const bets=$('sse-bets');
          if(bets.querySelector('.empty'))bets.innerHTML='';
          const item=document.createElement('div');
          item.className='sse-bet-item';
          item.innerHTML=`<span style="color:var(--accent)">${new Date().toLocaleTimeString()}</span> ${esc(msg.substring(0,100))}`;
          bets.prepend(item);
        }
        evt='message';
      }
    }
  }catch(e){log.innerHTML+=`<span class="err">Error: ${e}</span>\n`;}

  clearInterval(timer);
  S.running=false;
  $('run-btn').disabled=false;$('run-btn').textContent='\u25B6 RUN PIPELINE';
  setTimeout(()=>loadDashboard(),2000);
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ── Backtest ──
function toggleBacktest(){
  const p=$('bt-panel');
  p.style.display=p.style.display==='none'?'block':'none';
}

async function runBacktest(){
  if(S.btRunning)return;
  S.btRunning=true;
  const log=$('bt-log');log.style.display='block';log.innerHTML='<span class="meta">[starting backtest...]</span>\n';
  $('bt-progress-fill').style.width='0';
  const body={days:parseInt($('bt-days').value)||30,batch:parseInt($('bt-batch').value)||5,fast:$('bt-fast').checked};
  try{
    const resp=await fetch('/api/run-backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const reader=resp.body.getReader();
    const dec=new TextDecoder();
    let buf='',lines_count=0;
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split('\n');buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        let msg=line.slice(6);
        try{const j=JSON.parse(msg);msg=j.message||j.line||msg;}catch(e){}
        log.innerHTML+=esc(msg)+'\n';
        log.scrollTop=log.scrollHeight;
        lines_count++;
        $('bt-progress-fill').style.width=Math.min(lines_count*2,95)+'%';
      }
    }
    $('bt-progress-fill').style.width='100%';
    log.innerHTML+='<span class="ok">[backtest complete]</span>\n';
  }catch(e){log.innerHTML+=`<span class="err">Error: ${e}</span>\n`;}
  S.btRunning=false;
  setTimeout(()=>loadDashboard(),2000);
}

// ── Trade actions ──
async function followDecision(){
  try{await fetch('/api/confirm-trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});alert('Trade confirmed');}catch(e){alert('Error: '+e);}
}
async function overrideTrade(decision){
  try{await fetch('/api/reject-trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({override:decision})});alert('Override: '+decision);}catch(e){alert('Error: '+e);}
}
function toggleReasoning(){
  const d=$('reasoning-drawer');
  d.classList.toggle('open');
}

// ── INIT ──
initCharts();
loadDashboard();
loadStatus();
setInterval(loadDashboard,60000);
setInterval(loadStatus,60000);
setInterval(()=>{
  fetch('/api/latest-decision').then(r=>r.json()).then(d=>{
    if(d.price){const el=$('btc-price');el.textContent='$'+fmt(d.price);el.classList.add('flash');setTimeout(()=>el.classList.remove('flash'),500);}
  }).catch(()=>{});
},30000);
</script>
</body>
</html>
"""


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def load_jsonl(filepath, max_lines=100):
    results = []
    if not os.path.exists(filepath):
        return results
    try:
        with open(filepath, "r") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                try:
                    results.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return results


def load_json(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def format_time_ago(timestamp_str):
    if not timestamp_str:
        return "unknown"
    try:
        ts = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        delta = now - ts
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        remaining = mins % 60
        if hours < 24:
            return f"{hours}h {remaining}m ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return "unknown"


def format_price(price):
    try:
        return f"${float(price):,.2f}"
    except (TypeError, ValueError):
        return "--"


def get_kb_files():
    files = []
    if KB_DIR.exists():
        for f in sorted(KB_DIR.glob("*.md")):
            stat = f.stat()
            files.append({
                "name": f.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_human": f"{stat.st_size / 1024:.1f}KB" if stat.st_size > 1024 else f"{stat.st_size}B",
            })
    return files


def get_system_health():
    health = {"mirofish": False, "alpaca": False, "anthropic": False, "cron": False}
    try:
        r = requests.get("http://localhost:9876/health", timeout=2)
        health["mirofish"] = r.status_code == 200
    except Exception:
        pass
    env_file = BASE_DIR / "TradingAgents" / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                env_text = f.read()
            for line in env_text.splitlines():
                if line.startswith("ALPACA_API_KEY=") and len(line.split("=", 1)[1].strip()) > 5:
                    health["alpaca"] = True
                if line.startswith("ANTHROPIC_API_KEY=") and len(line.split("=", 1)[1].strip()) > 5:
                    health["anthropic"] = True
        except Exception:
            pass
    import shutil
    result = shutil.which("crontab")
    if result:
        try:
            import subprocess as sp
            out = sp.check_output(["crontab", "-l"], stderr=sp.DEVNULL, text=True)
            health["cron"] = "run_cron" in out
        except Exception:
            pass
    return health


def _j(filepath):
    return load_json(filepath)


def _jl(filepath, n=100):
    return load_jsonl(filepath, n)


def _jg(pattern, default=None):
    files = sorted(glob.glob(str(pattern)))
    if not files:
        return default
    return load_json(files[-1]) or default


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard")
def index():
    return render_template_string(DASHBOARD_HTML)


# ─── NEW API ENDPOINTS ───────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    live = get_system_health()
    persisted = load_json(LOGS_DIR / "health_status.json") or {}
    return jsonify({
        "services": {
            "dashboard": True,
            "mirofish": live.get("mirofish", False),
            "alpaca": live.get("alpaca", False),
            "anthropic": live.get("anthropic", False),
            "cron": live.get("cron", False),
        },
        "health_monitor": persisted,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/latest-decision")
def api_latest_decision():
    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 5000)
    if not runs:
        return jsonify({"error": "No pipeline runs yet"})
    last = runs[-1]
    mirofish_detail = None
    if last.get("mirofish_used"):
        mf_files = sorted(glob.glob(str(LOGS_DIR / "mirofish" / "mirofish_*.json")))
        if mf_files:
            mirofish_detail = load_json(mf_files[-1])
    return jsonify({
        "run_id": last.get("run_id"),
        "timestamp": last.get("timestamp"),
        "asset": last.get("asset"),
        "decision": last.get("decision"),
        "confidence": last.get("confidence"),
        "price": last.get("price_at_decision"),
        "reasoning": last.get("reasoning_summary", "")[:2000],
        "regime": last.get("regime"),
        "mirofish": {
            "used": last.get("mirofish_used", False),
            "sentiment": last.get("mirofish_sentiment"),
            "label": last.get("mirofish_label"),
            "agents": last.get("mirofish_agents"),
            "detail": mirofish_detail,
        },
        "time_ago": format_time_ago(last.get("timestamp", "")),
    })


@app.route("/api/performance")
def api_performance():
    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 5000)
    portfolio = load_json(LOGS_DIR / "portfolio.json") or {}
    journal = load_jsonl(LOGS_DIR / "trade_journal.jsonl", 5000)

    confidence_series = [{
        "x": r.get("timestamp"),
        "y": r.get("confidence", 0),
        "decision": r.get("decision"),
        "price": r.get("price_at_decision", 0),
    } for r in runs if r.get("timestamp")]

    pnl_series = []
    for entry in journal:
        p = entry.get("portfolio", {})
        if p and p.get("balance"):
            pnl_series.append({
                "x": entry.get("timestamp"),
                "y": p.get("balance", 100000),
            })

    decisions = {}
    for r in runs:
        d = r.get("decision", "UNKNOWN")
        decisions[d] = decisions.get(d, 0) + 1

    return jsonify({
        "confidence": confidence_series,
        "pnl": pnl_series,
        "decisions": decisions,
        "portfolio": portfolio,
        "total_runs": len(runs),
        "avg_confidence": round(sum(r.get("confidence", 0) for r in runs) / max(len(runs), 1), 1),
    })


@app.route("/api/backtest-summary")
def api_backtest_summary():
    summary = load_json(LOGS_DIR / "backtest_summary.json") or {}
    results = load_jsonl(LOGS_DIR / "backtest_results.jsonl", 500)
    poly_perf = load_json(LOGS_DIR / "polymarket_paper_performance.json") or {}
    return jsonify({
        "summary": summary,
        "results": results,
        "polymarket_performance": poly_perf,
    })


@app.route("/api/run-pipeline", methods=["POST"])
def api_run_pipeline():
    script = BASE_DIR / "run_paper_trade.py"

    def generate():
        if not script.exists():
            yield f"event: error\ndata: {json.dumps({'message': 'run_paper_trade.py not found'})}\n\n"
            yield "event: done\ndata: {\"exit_code\": 1}\n\n"
            return

        try:
            proc = subprocess.Popen(
                ["/root/limitless-ai/TradingAgents/venv/bin/python3", str(script), "--cron"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
                text=True,
                bufsize=1,
            )
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            yield "event: done\ndata: {\"exit_code\": 1}\n\n"
            return

        for line in proc.stdout:
            line = line.rstrip("\n\r")
            evt = "log"
            for marker, etype in [
                ("[PRICE]", "layer"), ("[MIROFISH]", "layer"), ("[REGIME]", "layer"),
                ("[ELO]", "layer"), ("[GDELT]", "layer"), ("[KB]", "layer"),
                ("[L10:Kronos]", "layer"), ("[L11:Whale]", "layer"), ("[L12:Policy]", "layer"),
                ("[PIPELINE]", "layer"), ("[CALIBRATION]", "layer"), ("[RISK]", "layer"),
                ("[DECISION]", "decision"), ("[TRADE]", "trade"), ("[DONE]", "complete"),
            ]:
                if marker in line:
                    evt = etype
                    break
            yield f"event: {evt}\ndata: {json.dumps({'message': line})}\n\n"

        proc.wait()
        yield f"event: done\ndata: {json.dumps({'exit_code': proc.returncode})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/run-backtest", methods=["POST"])
def api_run_backtest():
    data = request.get_json() or {}
    cmd = ["/root/limitless-ai/TradingAgents/venv/bin/python3",
           "/root/limitless-ai/run_backtest.py"]
    days = data.get("days")
    batch = data.get("batch")
    if days:
        cmd += ["--days", str(days)]
    if batch:
        cmd += ["--batch", str(batch)]
    if data.get("fast"):
        cmd += ["--fast"]

    def generate():
        yield f"event: start\ndata: {json.dumps({'command': ' '.join(cmd)})}\n\n"
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR), text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                yield f"event: log\ndata: {json.dumps({'message': line})}\n\n"
            proc.wait()
            yield f"event: done\ndata: {json.dumps({'exit_code': proc.returncode})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            yield "event: done\ndata: {\"exit_code\": 1}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── EXISTING API ENDPOINTS (PRESERVED) ─────────────────────────────────────

@app.route("/api/runs")
def api_runs():
    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 100)
    return jsonify(runs)

@app.route("/api/health")
def api_health():
    health = get_system_health()
    health["timestamp"] = datetime.now().isoformat()
    return jsonify(health)

@app.route("/api/cost")
def api_cost():
    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 1000)
    total_runs = len(runs)
    total_cost = total_runs * COST_PER_RUN
    return jsonify({
        "total_runs": total_runs,
        "cost_per_run": COST_PER_RUN,
        "total_estimated_cost": round(total_cost, 2),
        "currency": "USD",
    })

@app.route("/api/polymarket")
def api_polymarket():
    positions = load_json(LOGS_DIR / "polymarket_positions.json") or []
    return jsonify(positions)

@app.route("/api/backtest")
def api_backtest():
    backtest_runs = load_jsonl(LOGS_DIR / "backtest_runs.jsonl", 500)
    valid_runs = [
        r for r in backtest_runs
        if r.get("decision") not in ["ERROR", None]
        and r.get("decision_correct") is not None
    ]
    if not valid_runs:
        return jsonify({"error": "No backtest data available"})
    wins = sum(1 for r in valid_runs if r.get("decision_correct"))
    losses = len(valid_runs) - wins
    return jsonify({
        "total_evaluated": len(valid_runs),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / len(valid_runs) * 100), 1) if valid_runs else 0,
    })

@app.route("/api/layer-status")
def api_layer_status():
    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 1)
    if not runs:
        return jsonify([])
    run = runs[0]
    layers = [
        {"name": "Tavily News", "signal": "NEUTRAL", "value": str(run.get("tavily_articles", 0)) + " articles", "fired": run.get("tavily_articles", 0) > 0},
        {"name": "EDGAR Congressional", "signal": "NEUTRAL", "value": str(run.get("edgar_filings", 0)) + " filings", "fired": run.get("edgar_filings", 0) > 0},
        {"name": "Polymarket Markets", "signal": "NEUTRAL", "value": str(run.get("polymarket_markets", 0)) + " markets", "fired": run.get("polymarket_markets", 0) > 0},
        {"name": "MiroFish Sentiment", "signal": run.get("mirofish_label", "NEUTRAL"), "value": "Score: " + str(round(run.get("mirofish_sentiment", 0), 3)), "fired": run.get("mirofish_used", False)},
        {"name": "Geopolitical", "signal": "NEUTRAL", "value": "Analysis complete", "fired": True},
        {"name": "Google Trends", "signal": "NEUTRAL", "value": "Data loaded", "fired": True},
        {"name": "Whale Tracker", "signal": "NEUTRAL", "value": "Watching flows", "fired": True},
        {"name": "Options Flow", "signal": "NEUTRAL", "value": "Analyzing", "fired": True},
        {"name": "Pattern Memory", "signal": "NEUTRAL", "value": "Patterns stored", "fired": True},
    ]
    return jsonify(layers)

@app.route('/api/jarvis', methods=['POST'])
def api_jarvis():
    """JARVIS chat endpoint."""
    data = request.get_json() or {}
    user_message = data.get('message', '')
    history = data.get('history', [])

    runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 5)
    last_run = runs[0] if runs else {}

    trading_mode = load_json(LOGS_DIR / "trading_mode.json") or {'mode': 'auto'}
    backtest = load_json(LOGS_DIR / "backtest_summary.json") or {}
    health = get_system_health()

    all_runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 20)
    polymarket_count = sum(len(r.get('polymarket_markets', [])) if isinstance(r.get('polymarket_markets'), list) else 0 for r in all_runs)

    system_state = f"""LIVE SYSTEM STATE:
- BTC Price: {last_run.get('price_at_decision', 'N/A')}
- Last Decision: {last_run.get('decision', 'N/A')} at {last_run.get('confidence', 0)}% confidence
- Trading Mode: {trading_mode.get('mode', 'auto').upper()}
- Win Rate: {backtest.get('win_rate_pct', 0)}%
- Active Polymarket Positions: {polymarket_count}
- MiroFish Signal: {last_run.get('mirofish_label', 'N/A')} ({last_run.get('mirofish_agents', 0)} agents)
- Regime: {last_run.get('regime', 'UNKNOWN')}
- Health: MiroFish={health.get('mirofish')}, Alpaca={health.get('alpaca')}, Anthropic={health.get('anthropic')}"""

    env_file = BASE_DIR / "TradingAgents" / ".env"
    env = load_json(env_file) or {}
    api_key = os.getenv('ANTHROPIC_API_KEY', '')

    if not api_key:
        return jsonify({'response': "Boss, I can't connect to the AI brain. Check ANTHROPIC_API_KEY.", 'history': history})

    messages = [
        {'role': 'system', 'content': f"""You are JARVIS, the AI intelligence core of the Limitless AI autonomous
paper trading system. You have full real-time access to the system state below.
Answer questions about trading signals, portfolio status, system health, BTC analysis,
and agent decisions. Be direct, confident, and precise. Address the user as 'boss'.
Max 120 words unless asked for detail.
Live system state: {system_state}"""}
    ]

    for msg in history[-10:]:
        messages.append({'role': msg.get('role', 'user'), 'content': msg.get('content', '')})
    messages.append({'role': 'user', 'content': user_message})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Extract system message from messages list
        system_text = ""
        chat_messages = []
        for m in messages:
            if m['role'] == 'system':
                system_text = m['content']
            else:
                chat_messages.append(m)
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=300,
            system=system_text,
            messages=chat_messages,
        )
        reply = response.content[0].text
        history.append({'role': 'user', 'content': user_message})
        history.append({'role': 'assistant', 'content': reply})
        return jsonify({'response': reply, 'history': history})
    except Exception as e:
        return jsonify({'response': f"Boss, comms error: {str(e)}", 'history': history})


@app.route('/api/confirm-trade', methods=['POST'])
def api_confirm_trade():
    save_json(LOGS_DIR / "trading_mode.json", {'mode': 'manual', 'confirmed': True})
    return jsonify({'status': 'confirmed'})

@app.route('/api/reject-trade', methods=['POST'])
def api_reject_trade():
    data = request.get_json() or {}
    save_json(LOGS_DIR / "trading_mode.json", {'mode': 'manual', 'confirmed': False, 'override': data.get('override')})
    return jsonify({'status': 'rejected', 'override': data.get('override')})

@app.route('/api/update-kb', methods=['POST'])
def api_update_kb():
    try:
        subprocess.Popen(['python3', str(BASE_DIR / 'update_knowledge_base.py'), '--full'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/polymarket-verify/<market_id>')
def api_polymarket_verify(market_id):
    try:
        resp = requests.get(f'https://gamma-api.polymarket.com/markets/{market_id}', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return jsonify({'verified': True, 'real': True, 'probability': data.get('outcomePrices', ['0'])[0]})
        return jsonify({'verified': True, 'real': False, 'probability': None})
    except Exception:
        return jsonify({'verified': False, 'real': None, 'probability': None})

@app.route('/api/trading-mode')
def api_trading_mode():
    mode = load_json(LOGS_DIR / "trading_mode.json") or {'mode': 'auto'}
    return jsonify(mode)

@app.route('/api/set-mode', methods=['POST'])
def api_set_mode():
    data = request.get_json() or {}
    mode = data.get('mode', 'auto')
    save_json(LOGS_DIR / "trading_mode.json", {'mode': mode, 'confirmed': None})
    return jsonify({'mode': mode})

@app.route('/api/debate/<run_id>')
def api_debate(run_id):
    debate_file = DEBATES_DIR / f"debate_{run_id}.json"
    debate = load_json(debate_file)
    if not debate:
        runs = load_jsonl(LOGS_DIR / "pipeline_runs.jsonl", 100)
        for run in runs:
            if run.get('run_id') == run_id:
                debate = {'reasoning_summary': run.get('reasoning_summary', 'No debate available')}
                break
    return jsonify(debate or {'error': 'Debate not found'})

if __name__ == "__main__":
    print(f"Starting Limitless AI Dashboard on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
