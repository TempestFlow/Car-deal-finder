import os
from statistics import mean

from jinja2 import Environment, BaseLoader

from models import CarListing

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Car Deal Finder &mdash; Results</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --navy: #0f172a;
  --navy-mid: #1e293b;
  --navy-light: #334155;
  --accent: #3b82f6;
  --accent-dark: #1d4ed8;
  --green: #16a34a;
  --green-bg: #f0fdf4;
  --green-border: #bbf7d0;
  --green-text: #15803d;
  --amber-bg: #fffbeb;
  --amber-border: #fde68a;
  --amber-text: #92400e;
  --red-bg: #fef2f2;
  --red-border: #fecaca;
  --red-text: #991b1b;
  --bg: #f1f5f9;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --muted: #64748b;
  --subtle: #94a3b8;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Helvetica, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}

/* ── Header ────────────────────────────── */
header {
  background: linear-gradient(140deg, #0a0f1e 0%, #0f2a4a 50%, #0a0f1e 100%);
  padding: 36px 40px 32px;
  position: relative;
  overflow: hidden;
}
header::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 80% 40%, rgba(59,130,246,0.18) 0%, transparent 55%),
    radial-gradient(ellipse at 20% 80%, rgba(99,102,241,0.10) 0%, transparent 50%);
  pointer-events: none;
}
.header-inner {
  position: relative;
  z-index: 1;
  max-width: 1560px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
}
.header-brand h1 {
  font-size: 2rem;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.03em;
}
.header-brand p { font-size: 0.88rem; color: #64748b; margin-top: 3px; }

.stats { display: flex; gap: 10px; flex-wrap: wrap; }
.stat {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 14px;
  padding: 14px 22px;
  min-width: 118px;
  text-align: center;
  backdrop-filter: blur(10px);
  transition: background 0.2s;
}
.stat:hover { background: rgba(255,255,255,0.10); }
.stat-label { font-size: 0.67rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }
.stat-value { font-size: 1.6rem; font-weight: 800; color: #fff; margin-top: 3px; letter-spacing: -0.02em; }
.stat-value.blue { color: #60a5fa; }
.stat-value.green { color: #4ade80; }

/* ── How scores work ────────────────────── */
.explainer { background: var(--navy-mid); border-bottom: 1px solid rgba(255,255,255,0.05); }
.explainer summary {
  padding: 10px 40px;
  color: #64748b;
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 1560px;
  margin: 0 auto;
  transition: color 0.15s;
}
.explainer summary:hover { color: #94a3b8; }
.explainer summary::-webkit-details-marker { display: none; }
.explainer summary::before { content: '\25B6'; font-size: 0.6rem; transition: transform 0.2s; }
.explainer[open] summary::before { transform: rotate(90deg); }
.explainer-body {
  padding: 20px 40px 28px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  max-width: 1560px;
  margin: 0 auto;
}
.explainer h3 { color: #cbd5e1; font-size: 0.78rem; font-weight: 700; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.07em; }
.explainer p, .explainer li { color: #64748b; font-size: 0.79rem; line-height: 1.7; }
.explainer ul { padding-left: 16px; margin-top: 6px; }
.explainer ul li { margin-bottom: 4px; }
.score-legend { display: flex; flex-direction: column; gap: 9px; }
.score-legend-item { display: flex; align-items: center; gap: 10px; font-size: 0.79rem; color: #64748b; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.metric-table { width: 100%; border-collapse: collapse; font-size: 0.77rem; margin-top: 6px; }
.metric-table th { color: #475569; text-align: left; padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-table td { color: #64748b; padding: 7px 8px; vertical-align: top; line-height: 1.5; }
.metric-table tr:not(:last-child) td { border-bottom: 1px solid rgba(255,255,255,0.03); }
.formula-block { font-family: 'Courier New', monospace; background: #0a0f1e; border: 1px solid rgba(255,255,255,0.07); padding: 12px 14px; border-radius: 8px; font-size: 0.76rem; color: #93c5fd; line-height: 1.8; margin-top: 8px; }

/* ── Controls bar ────────────────────────── */
.controls {
  background: rgba(255,255,255,0.96);
  padding: 10px 40px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  border-bottom: 1px solid var(--border);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  position: sticky;
  top: 0;
  z-index: 200;
  backdrop-filter: blur(16px);
}
.filter-group { display: flex; align-items: center; gap: 5px; }
.filter-group label { font-size: 0.72rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; white-space: nowrap; }
.controls select, .controls input[type=number] {
  padding: 6px 10px;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-size: 0.83rem;
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
  outline: none;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
  -webkit-appearance: none;
  appearance: none;
}
.controls select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2394a3b8'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 9px center;
  padding-right: 28px;
}
.controls select:focus, .controls input[type=number]:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
}
.controls input[type=number] { width: 130px; }
.ctrl-sep { width: 1px; height: 22px; background: var(--border); margin: 0 2px; }
.sort-group { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.sort-group label { font-size: 0.72rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; }
.sort-pills {
  display: flex;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 9px;
  padding: 3px;
  gap: 2px;
}
.sort-btn {
  padding: 5px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  font-size: 0.79rem;
  font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.sort-btn:hover { color: var(--accent); background: rgba(59,130,246,0.07); }
.sort-btn.active { background: var(--navy); color: #fff; font-weight: 700; box-shadow: 0 1px 3px rgba(0,0,0,0.18); }
.results-badge {
  font-size: 0.75rem;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 4px 10px;
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}

/* ── Card grid ───────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 18px;
  padding: 24px 40px;
  max-width: 1560px;
  margin: 0 auto;
}

/* ── Card ────────────────────────────────── */
.card {
  background: var(--surface);
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 14px rgba(0,0,0,0.04);
  transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.22s ease;
  display: flex;
  flex-direction: column;
}
.card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.11), 0 2px 6px rgba(0,0,0,0.06);
}

/* Image */
.card-img-wrap { position: relative; overflow: hidden; flex-shrink: 0; }
.card-img {
  width: 100%;
  height: 195px;
  object-fit: cover;
  display: block;
  transition: transform 0.35s ease;
}
.card:hover .card-img { transform: scale(1.04); }
.card-img-placeholder {
  width: 100%;
  height: 195px;
  background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.placeholder-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(148,163,184,0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}
.placeholder-icon::after {
  content: '';
  display: block;
  width: 24px;
  height: 14px;
  border: 2.5px solid #94a3b8;
  border-radius: 3px;
  position: relative;
}
.placeholder-text { font-size: 0.72rem; color: #94a3b8; font-weight: 500; }

/* Score ring */
.score-ring {
  position: absolute;
  top: 11px;
  right: 11px;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  line-height: 1;
  border: 2.5px solid;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.score-ring .rn { font-size: 1.15rem; }
.score-ring .rl { font-size: 0.52rem; font-weight: 600; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.score-ring.sr-green  { background: rgba(20,83,45,0.87);   color: #86efac; border-color: #22c55e; }
.score-ring.sr-yellow { background: rgba(120,53,15,0.87);  color: #fde68a; border-color: #f59e0b; }
.score-ring.sr-red    { background: rgba(127,29,29,0.87);  color: #fca5a5; border-color: #ef4444; }

/* Overlay badges top-left */
.overlay-badges { position: absolute; top: 11px; left: 11px; display: flex; flex-direction: column; gap: 4px; }
.ob {
  font-size: 0.67rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.ob-reliable { background: rgba(20,83,45,0.82); color: #86efac; border-color: rgba(34,197,94,0.45); }
.ob-damaged  { background: rgba(127,29,29,0.82); color: #fca5a5; border-color: rgba(239,68,68,0.45); }

/* Card body */
.card-body { padding: 15px 17px 17px; flex: 1; display: flex; flex-direction: column; }
.card-make { font-size: 0.68rem; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 3px; }
.card-title { font-size: 0.97rem; font-weight: 700; color: var(--text); line-height: 1.35; margin-bottom: 10px; }
.card-price-row { display: flex; align-items: baseline; gap: 6px; margin-bottom: 11px; }
.card-price { font-size: 1.55rem; font-weight: 800; color: var(--navy); letter-spacing: -0.025em; }
.price-na { font-size: 1.1rem; color: var(--muted); }

/* Spec chips */
.specs { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 12px; }
.spec {
  font-size: 0.74rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--muted);
  white-space: nowrap;
}
.spec.s-private  { background: var(--green-bg);  border-color: var(--green-border);  color: var(--green-text); }
.spec.s-dealer   { background: var(--amber-bg);  border-color: var(--amber-border);  color: var(--amber-text); }
.spec.s-autoplius { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
.spec.s-autogidas { background: #faf5ff; border-color: #e9d5ff; color: #6b21a8; }

/* Metric bars */
.metrics { border-top: 1px solid var(--border); padding-top: 9px; margin-bottom: 13px; display: flex; flex-direction: column; gap: 5px; }
.metric-row { display: flex; align-items: center; gap: 7px; }
.ml { width: 70px; font-size: 0.68rem; color: var(--subtle); flex-shrink: 0; font-weight: 500; }
.mw { flex: 1; height: 5px; background: #f1f5f9; border-radius: 99px; overflow: hidden; }
.mb { height: 100%; border-radius: 99px; }
.mb-price   { background: linear-gradient(90deg, #4ade80, #16a34a); }
.mb-mileage { background: linear-gradient(90deg, #60a5fa, #2563eb); }
.mb-fresh   { background: linear-gradient(90deg, #fb923c, #ea580c); }
.mb-seller  { background: linear-gradient(90deg, #c084fc, #9333ea); }
.mv { width: 22px; text-align: right; font-size: 0.68rem; color: var(--subtle); font-variant-numeric: tabular-nums; font-weight: 700; }

/* Button */
.card-footer { margin-top: auto; }
.btn-view {
  display: block;
  text-align: center;
  background: linear-gradient(135deg, #0f2a4a 0%, var(--navy) 100%);
  color: #fff;
  text-decoration: none;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 0.86rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  transition: opacity 0.15s, transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 1px 4px rgba(0,0,0,0.18);
}
.btn-view:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.22); }

/* No results */
.no-results { grid-column: 1/-1; text-align: center; padding: 80px 20px; }
.no-results h3 { font-size: 1.1rem; color: var(--muted); font-weight: 600; }
.no-results p { font-size: 0.85rem; color: var(--subtle); margin-top: 6px; }

/* Responsive */
@media (max-width: 900px) {
  .explainer-body { grid-template-columns: 1fr; }
  .header-inner { flex-direction: column; align-items: flex-start; }
  .stats { width: 100%; }
}
@media (max-width: 640px) {
  header { padding: 22px 18px 20px; }
  .grid { padding: 14px 14px; gap: 14px; }
  .controls { padding: 8px 14px; }
  .explainer summary { padding: 9px 18px; }
  .explainer-body { padding: 16px 18px 22px; }
  .sort-group { margin-left: 0; width: 100%; }
  .header-brand h1 { font-size: 1.55rem; }
}
</style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="header-brand">
      <h1>Car Deal Finder</h1>
      <p>Lithuania &mdash; autoplius.lt &amp; autogidas.lt</p>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Listings</div>
        <div class="stat-value">{{ total }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Avg Price</div>
        <div class="stat-value">&euro;{{ avg_price | int }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Best Score</div>
        <div class="stat-value green">{{ best_score }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Makes</div>
        <div class="stat-value blue">{{ makes | length }}</div>
      </div>
    </div>
  </div>
</header>

<details class="explainer">
  <summary>How deal scores are calculated</summary>
  <div class="explainer-body">
    <div>
      <h3>Score Factors (0&ndash;100)</h3>
      <table class="metric-table">
        <tr><th>Factor</th><th>Weight</th><th>Description</th></tr>
        <tr>
          <td><span style="color:#4ade80">&#9632;</span> Price</td>
          <td>40%</td>
          <td>How far below median market price for same make/model/year. 50% below = 100 pts.</td>
        </tr>
        <tr>
          <td><span style="color:#60a5fa">&#9632;</span> Mileage</td>
          <td>30%</td>
          <td>Expected 15,000 km/year. Near-zero mileage = 100. Double expected = 0. Suspiciously low mileage on old cars capped at 90.</td>
        </tr>
        <tr>
          <td><span style="color:#fb923c">&#9632;</span> Freshness</td>
          <td>15%</td>
          <td>Decays 1 pt/day from 100. Hits 0 at 100 days. +15 bonus if a price drop was detected.</td>
        </tr>
        <tr>
          <td><span style="color:#c084fc">&#9632;</span> Seller</td>
          <td>15%</td>
          <td>Private = 100 (no dealer markup). Dealer = 40.</td>
        </tr>
      </table>
    </div>
    <div>
      <h3>Score Tiers</h3>
      <div class="score-legend">
        <div class="score-legend-item"><span class="dot" style="background:#22c55e"></span><span><strong style="color:#cbd5e1">&ge; 70 &mdash; Great deal.</strong> Noticeably below market, fresh listing, and/or low mileage.</span></div>
        <div class="score-legend-item"><span class="dot" style="background:#f59e0b"></span><span><strong style="color:#cbd5e1">40&ndash;69 &mdash; Fair deal.</strong> Around market average. Worth a look.</span></div>
        <div class="score-legend-item"><span class="dot" style="background:#ef4444"></span><span><strong style="color:#cbd5e1">&lt; 40 &mdash; Below average.</strong> Overpriced, high mileage, or stale listing.</span></div>
      </div>
      <h3 style="margin-top:18px">Formula &amp; Adjustments</h3>
      <div class="formula-block">score = price&times;0.40 + mileage&times;0.30<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ freshness&times;0.15 + seller&times;0.15<br><br><span style="color:#4ade80">+ 5&ndash;10</span> reliability bonus (Toyota, Honda, Lexus&hellip;)<br><span style="color:#f87171">&minus; 30&nbsp;&nbsp;&nbsp;</span> damage penalty (accident / body damage)</div>
    </div>
  </div>
</details>

<div class="controls">
  <div class="filter-group">
    <label for="filter-make">Make</label>
    <select id="filter-make" onchange="applyFilters()">
      <option value="">All makes</option>
      {% for mk in makes %}
      <option value="{{ mk | lower }}">{{ mk }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="filter-group">
    <label for="filter-seller">Seller</label>
    <select id="filter-seller" onchange="applyFilters()">
      <option value="">All</option>
      <option value="private">Private</option>
      <option value="dealer">Dealer</option>
    </select>
  </div>
  <div class="filter-group">
    <label for="filter-fuel">Fuel</label>
    <select id="filter-fuel" onchange="applyFilters()">
      <option value="">All</option>
      {% for ft in fuel_types %}
      <option value="{{ ft }}">{{ ft }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="filter-group">
    <label for="filter-source">Source</label>
    <select id="filter-source" onchange="applyFilters()">
      <option value="">All</option>
      <option value="autoplius">autoplius</option>
      <option value="autogidas">autogidas</option>
    </select>
  </div>
  <div class="ctrl-sep"></div>
  <div class="filter-group">
    <label for="filter-price">Max &euro;</label>
    <input type="number" id="filter-price" placeholder="e.g. 8000" oninput="applyFilters()">
  </div>
  <span class="results-badge" id="results-count">{{ total }} results</span>
  <div class="sort-group">
    <label>Sort</label>
    <div class="sort-pills">
      <button class="sort-btn active" onclick="sortBy('score',this)">Score</button>
      <button class="sort-btn" onclick="sortBy('price',this)">Price</button>
      <button class="sort-btn" onclick="sortBy('mileage',this)">Mileage</button>
      <button class="sort-btn" onclick="sortBy('year',this)">Year</button>
    </div>
  </div>
</div>

<div class="grid" id="card-grid">
  {% for car in listings %}
  <div class="card"
    data-source="{{ car.source }}"
    data-seller="{{ car.seller_type }}"
    data-fuel="{{ car.fuel_type }}"
    data-price="{{ car.price }}"
    data-mileage="{{ car.mileage }}"
    data-year="{{ car.year }}"
    data-score="{{ car.deal_score }}"
    data-make="{{ car.make | lower }}">

    <div class="card-img-wrap">
      {% if car.images %}
      <img class="card-img" src="{{ car.images[0] }}" alt="{{ car.title }}" loading="lazy"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
      <div class="card-img-placeholder" style="display:none">
        <div class="placeholder-icon"></div>
        <span class="placeholder-text">No image</span>
      </div>
      {% else %}
      <div class="card-img-placeholder">
        <div class="placeholder-icon"></div>
        <span class="placeholder-text">No image</span>
      </div>
      {% endif %}

      <div class="score-ring {% if car.deal_score >= 70 %}sr-green{% elif car.deal_score >= 40 %}sr-yellow{% else %}sr-red{% endif %}">
        <span class="rn">{{ car.deal_score | round(1) }}</span>
        <span class="rl">score</span>
      </div>

      <div class="overlay-badges">
        {% if car.reliability_bonus > 0 %}
        <span class="ob ob-reliable" title="+{{ car.reliability_bonus | int }} reliability bonus">Reliable</span>
        {% endif %}
        {% if car.damage %}
        <span class="ob ob-damaged" title="{{ car.damage_info }}">Damaged</span>
        {% endif %}
      </div>
    </div>

    <div class="card-body">
      <div class="card-make">{{ car.make }}</div>
      <div class="card-title">{{ car.title }}</div>

      <div class="card-price-row">
        {% if car.price %}
        <span class="card-price">&euro;{{ '{:,.0f}'.format(car.price) }}</span>
        {% else %}
        <span class="price-na">Price N/A</span>
        {% endif %}
      </div>

      <div class="specs">
        {% if car.year %}<span class="spec">{{ car.year }}</span>{% endif %}
        {% if car.fuel_type %}<span class="spec">{{ car.fuel_type }}</span>{% endif %}
        {% if car.mileage %}<span class="spec">{{ '{:,}'.format(car.mileage) }} km</span>{% endif %}
        <span class="spec s-{{ car.seller_type }}">{{ car.seller_type | capitalize }}</span>
        <span class="spec s-{{ car.source }}">{{ car.source }}</span>
      </div>

      <div class="metrics">
        <div class="metric-row">
          <span class="ml" title="Price vs. market median for similar cars">Price 40%</span>
          <div class="mw"><div class="mb mb-price" style="width:{{ car.price_sub_score }}%"></div></div>
          <span class="mv">{{ car.price_sub_score | int }}</span>
        </div>
        <div class="metric-row">
          <span class="ml" title="Mileage vs. expected for car age (15k km/yr)">Mileage 30%</span>
          <div class="mw"><div class="mb mb-mileage" style="width:{{ car.mileage_sub_score }}%"></div></div>
          <span class="mv">{{ car.mileage_sub_score | int }}</span>
        </div>
        <div class="metric-row">
          <span class="ml" title="Days since listed. +15 if price dropped.">Freshness 15%</span>
          <div class="mw"><div class="mb mb-fresh" style="width:{{ car.freshness_sub_score }}%"></div></div>
          <span class="mv">{{ car.freshness_sub_score | int }}</span>
        </div>
        <div class="metric-row">
          <span class="ml" title="Private=100, Dealer=40">Seller 15%</span>
          <div class="mw"><div class="mb mb-seller" style="width:{{ car.seller_sub_score }}%"></div></div>
          <span class="mv">{{ car.seller_sub_score | int }}</span>
        </div>
      </div>

      <div class="card-footer">
        <a class="btn-view" href="{{ car.url }}" target="_blank" rel="noopener">View Listing &rarr;</a>
      </div>
    </div>
  </div>
  {% endfor %}

  <div class="no-results" id="no-results" style="display:none">
    <h3>No listings match your filters</h3>
    <p>Try relaxing the Make, Fuel, or Max Price filter.</p>
  </div>
</div>

<script>
var currentSort = 'score';
var sortDir = -1;

function sortBy(field, btn) {
  if (currentSort === field) { sortDir *= -1; }
  else { currentSort = field; sortDir = (field === 'price' || field === 'mileage') ? 1 : -1; }
  document.querySelectorAll('.sort-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  applyFilters();
}

function applyFilters() {
  var make     = document.getElementById('filter-make').value.toLowerCase();
  var seller   = document.getElementById('filter-seller').value.toLowerCase();
  var fuel     = document.getElementById('filter-fuel').value.toLowerCase();
  var source   = document.getElementById('filter-source').value.toLowerCase();
  var maxPrice = parseFloat(document.getElementById('filter-price').value) || Infinity;

  var grid  = document.getElementById('card-grid');
  var cards = Array.from(grid.querySelectorAll('.card'));

  var visible = cards.filter(function(c) {
    if (make   && c.dataset.make   !== make)                      return false;
    if (seller && c.dataset.seller !== seller)                    return false;
    if (fuel   && c.dataset.fuel.toLowerCase() !== fuel)         return false;
    if (source && c.dataset.source !== source)                    return false;
    if (parseFloat(c.dataset.price) > maxPrice)                   return false;
    return true;
  });

  cards.forEach(function(c) { c.style.display = 'none'; });

  visible.sort(function(a, b) {
    var av = parseFloat(a.dataset[currentSort]) || 0;
    var bv = parseFloat(b.dataset[currentSort]) || 0;
    return (av - bv) * sortDir;
  });

  visible.forEach(function(c) { c.style.display = ''; grid.appendChild(c); });

  var nr = document.getElementById('no-results');
  nr.style.display = visible.length === 0 ? '' : 'none';

  var rc = document.getElementById('results-count');
  if (rc) rc.textContent = visible.length + ' result' + (visible.length !== 1 ? 's' : '');
}
</script>
</body>
</html>
"""


def render_html(listings: list, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    total = len(listings)
    prices = [l.price for l in listings if l.price > 0]
    avg_price = mean(prices) if prices else 0
    best_score = max((l.deal_score for l in listings), default=0)
    fuel_types = sorted({l.fuel_type for l in listings if l.fuel_type})
    makes = sorted({l.make for l in listings if l.make})

    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(TEMPLATE)
    html = tmpl.render(
        listings=listings,
        total=total,
        avg_price=avg_price,
        best_score=round(best_score, 1),
        fuel_types=fuel_types,
        makes=makes,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Output written to: {output_path}")
