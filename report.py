"""Write market / project / QoQ charts and the unreported QPR list."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from store import REPORTS, ensure_dirs, report_stem, write_qoq_json, write_unreported_list

DEFAULT_CANVAS = Path.home() / ".cursor" / "projects" / "c-Users-pruthvir-IdeaProjects" / "canvases"


def _js(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_html(data: dict[str, Any]) -> Path:
    ensure_dirs()
    path = REPORTS / f"{report_stem(data)}.html"
    qoq = data.get("qoq") or {}
    meta = qoq.get("meta") or {}
    title = (
        f"{meta.get('district', 'K-RERA')} {meta.get('approved_year', '')} "
        "parking"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 24px; color: #1a1a1a; background: #fafafa; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    h2 {{ font-size: 16px; margin: 20px 0 8px; }}
    .sub {{ color: #555; margin-bottom: 16px; font-size: 13px; }}
    .stats {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 24px; }}
    .stat {{ background: #fff; border: 1px solid #ddd; padding: 12px 16px; min-width: 140px; }}
    .stat b {{ display: block; font-size: 20px; }}
    .stat span {{ color: #666; font-size: 12px; }}
    .toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 8px; align-items: center; }}
    button, select {{ padding: 6px 12px; font: inherit; }}
    button.active {{ background: #1d4ed8; color: #fff; border-color: #1d4ed8; }}
    .chart-wrap {{ background: #fff; border: 1px solid #ddd; padding: 16px; height: 420px; margin-bottom: 16px; }}
    .chart-wrap.tall {{ height: 720px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; margin-top: 16px; font-size: 13px; }}
    th, td {{ border: 1px solid #e5e5e5; padding: 6px 8px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    .note {{ font-size: 12px; color: #666; margin-top: 16px; }}
    .panel {{ display: none; }}
    .panel.on {{ display: block; }}
    h3.kind {{ font-size: 13px; margin: 16px 0 6px; }}
    ul.unreported {{ columns: 2; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="sub">
    Apartments = Residential/Group Housing and Mixed Development ·
    Plots / villas = Plotted Development ·
    Supply = Total No of Parkings · Demand = Parkings Booked · Inventory = Parkings Available
  </div>
  <div class="toolbar">
    <button id="btn-market" class="active" type="button">Overall market</button>
    <button id="btn-projects" type="button">Projects</button>
    <button id="btn-qoq" type="button">QoQ</button>
    <button id="btn-unreported" type="button">Unreported QPR</button>
    <select id="taluk-select" hidden></select>
  </div>
  <div class="toolbar" id="kind-bar"></div>
  <div class="toolbar" id="year-bar"></div>
  <div class="stats" id="stats"></div>
  <div id="panel-chart" class="panel on">
    <div class="chart-wrap" id="chart-box"><canvas id="chart"></canvas></div>
    <div class="chart-wrap" id="chart2-box" hidden><canvas id="chart2"></canvas></div>
  </div>
  <div id="panel-table" class="panel on"><table id="tbl"></table></div>
  <div id="panel-unreported" class="panel"><div id="unlist"></div></div>
  <p class="note" id="note"></p>
  <script>
    const DATA = {_js(data)};
    const Q = DATA.qoq;
    const KIND_ORDER = ["apartments","plots","other"];
    const fmt = n => Number(n).toLocaleString("en-IN");
    let mode = DATA.qoq.meta.default_view || "market";
    let kind = DATA.qoq.meta.default_kind || "all";
    let launchYear = "all";
    let taluk = Object.keys(Q.taluks)[0] || "";
    let chart, chart2;

    const sel = document.getElementById("taluk-select");
    Object.keys(Q.taluks).forEach(name => {{
      const o = document.createElement("option");
      o.value = name; o.textContent = name;
      sel.appendChild(o);
    }});

    const kindBar = document.getElementById("kind-bar");
    function addKindBtn(id, label) {{
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.kind = id;
      b.textContent = label;
      b.onclick = () => {{ kind = id; draw(); }};
      kindBar.appendChild(b);
    }}
    addKindBtn("all", "All types");
    KIND_ORDER.forEach(k => {{
      if (DATA.kinds[k]) addKindBtn(k, DATA.kinds[k].label);
    }});
    const YEAR_KEYS = (Q.meta.launch_years || []).map(String).filter(y => DATA.years && DATA.years[y]);
    const yearBar = document.getElementById("year-bar");
    function addYearBtn(id, label) {{
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.year = id;
      b.textContent = label;
      b.onclick = () => {{ launchYear = id; draw(); }};
      yearBar.appendChild(b);
    }}
    if (YEAR_KEYS.length > 1) {{
      addYearBtn("all", "All years");
      YEAR_KEYS.forEach(y => addYearBtn(y, y + " launches"));
    }}

    function slice() {{
      if (launchYear === "all") return kind === "all" ? DATA.market : DATA.kinds[kind];
      const yb = DATA.years[launchYear];
      if (!yb) return DATA.market;
      if (kind === "all") return yb;
      return (yb.kinds && yb.kinds[kind]) || yb;
    }}
    function kindProjects() {{
      return DATA.projects.filter(p =>
        (kind === "all" || p.kind === kind) &&
        (launchYear === "all" || String(p.launch_year) === launchYear)
      );
    }}
    function kindUnreported() {{
      return (DATA.unreported || []).filter(r =>
        (kind === "all" || r.kind === kind) &&
        (launchYear === "all" || String(r.launch_year) === launchYear)
      );
    }}
    function seriesHas(s) {{
      return s && (s.supply || []).some(v => v > 0);
    }}
    function qoqSrc() {{
      const empty = {{ overall: {{ supply:[], demand:[], inventory:[], projects:[] }}, taluks: {{}} }};
      if (launchYear === "all") {{
        if (kind === "all") return {{ overall: Q.overall, taluks: Q.taluks }};
        return Q.by_kind && Q.by_kind[kind] ? Q.by_kind[kind] : empty;
      }}
      const yb = Q.by_year && Q.by_year[launchYear];
      if (!yb) return empty;
      if (kind === "all") return yb;
      return yb.by_kind && yb.by_kind[kind] ? yb.by_kind[kind] : empty;
    }}
    function qoqBlock() {{
      const src = qoqSrc();
      const block = (!sel.hidden && taluk && src.taluks[taluk]) ? src.taluks[taluk] : src.overall;
      return {{
        labels: Q.quarters,
        supply: block.supply || [],
        demand: block.demand || [],
        inventory: block.inventory || [],
        projects: block.projects || [],
        title: ((sel.hidden || !taluk) ? "Overall" : taluk) + " QoQ — Supply, Demand, Inventory",
      }};
    }}
    function bars(el, labels, datasets, title, stacked, horizontal) {{
      return new Chart(el, {{
        type: "bar",
        data: {{ labels, datasets }},
        options: {{
          indexAxis: horizontal ? "y" : "x",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ title: {{ display: true, text: title }}, legend: {{ position: "bottom" }} }},
          scales: {{
            x: {{ stacked: !!stacked, beginAtZero: true }},
            y: {{ stacked: !!stacked, beginAtZero: true }},
          }},
        }},
      }});
    }}

    function setMode(next) {{
      mode = next;
      ["market","projects","qoq","unreported"].forEach(id => {{
        document.getElementById("btn-" + id).classList.toggle("active", id === next);
      }});
      const showUn = next === "unreported";
      document.getElementById("panel-unreported").classList.toggle("on", showUn);
      document.getElementById("panel-chart").classList.toggle("on", !showUn);
      document.getElementById("panel-table").classList.toggle("on", !showUn);
      sel.hidden = next !== "qoq";
      document.getElementById("chart-box").classList.toggle("tall", next === "projects");
      draw();
    }}

    function renderStats() {{
      const m = slice();
      const pct = m.supply ? (100 * m.demand / m.supply).toFixed(1) : "0.0";
      document.getElementById("stats").innerHTML =
        `<div class="stat"><b>${{fmt(m.supply)}}</b><span>Supply</span></div>` +
        `<div class="stat"><b>${{fmt(m.demand)}}</b><span>Demand booked</span></div>` +
        `<div class="stat"><b>${{fmt(m.inventory)}}</b><span>Inventory available</span></div>` +
        `<div class="stat"><b>${{pct}}%</b><span>Booked of supply</span></div>` +
        `<div class="stat"><b>${{fmt(m.projects_with_qpr)}} / ${{fmt(m.projects_approved)}}</b><span>Projects with QPR</span></div>` +
        `<div class="stat"><b>${{fmt(m.unreported)}}</b><span>Unreported QPR</span></div>`;
      [...kindBar.querySelectorAll("button")].forEach(b => {{
        b.classList.toggle("active", b.dataset.kind === kind);
      }});
      [...yearBar.querySelectorAll("button")].forEach(b => {{
        b.classList.toggle("active", b.dataset.year === launchYear);
      }});
    }}

    function renderTable() {{
      let html = "";
      if (mode === "market") {{
        if (YEAR_KEYS.length > 1 && launchYear === "all") {{
          html = "<thead><tr><th>Launch year</th><th>Approved</th><th>With QPR</th><th>Unreported</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
          YEAR_KEYS.forEach(y => {{
            const r = DATA.years[y];
            const pct = r.supply ? (100 * r.demand / r.supply).toFixed(1) : "0.0";
            html += `<tr><td>${{r.label}}</td><td>${{fmt(r.projects_approved)}}</td><td>${{fmt(r.projects_with_qpr)}}</td><td>${{fmt(r.unreported)}}</td><td>${{fmt(r.supply)}}</td><td>${{fmt(r.demand)}}</td><td>${{fmt(r.inventory)}}</td><td>${{pct}}%</td></tr>`;
          }});
          html += "</tbody>";
        }} else if (kind === "all") {{
          html = "<thead><tr><th>Type</th><th>K-RERA types</th><th>Approved</th><th>With QPR</th><th>Unreported</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
          KIND_ORDER.forEach(k => {{
            const r = DATA.kinds[k];
            if (!r) return;
            const pct = r.supply ? (100 * r.demand / r.supply).toFixed(1) : "0.0";
            html += `<tr><td>${{r.label}}</td><td>${{r.portal}}</td><td>${{fmt(r.projects_approved)}}</td><td>${{fmt(r.projects_with_qpr)}}</td><td>${{fmt(r.unreported)}}</td><td>${{fmt(r.supply)}}</td><td>${{fmt(r.demand)}}</td><td>${{fmt(r.inventory)}}</td><td>${{pct}}%</td></tr>`;
          }});
          html += "</tbody>";
        }} else {{
          const m = slice();
          html = "<thead><tr><th>Taluk</th><th>Approved</th><th>With QPR</th><th>Unreported</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
          Object.keys(m.taluks).forEach(n => {{
            const r = m.taluks[n];
            const pct = r.supply ? (100 * r.demand / r.supply).toFixed(1) : "0.0";
            html += `<tr><td>${{n}}</td><td>${{fmt(r.approved)}}</td><td>${{fmt(r.n)}}</td><td>${{fmt(r.unreported)}}</td><td>${{fmt(r.supply)}}</td><td>${{fmt(r.demand)}}</td><td>${{fmt(r.inventory)}}</td><td>${{pct}}%</td></tr>`;
          }});
          html += "</tbody>";
        }}
      }} else if (mode === "projects") {{
        html = "<thead><tr><th>Project</th><th>Type</th><th>Taluk</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
        kindProjects().forEach(p => {{
          const pct = p.supply ? (100 * p.demand / p.supply).toFixed(1) : "0.0";
          html += `<tr><td>${{p.name}}</td><td>${{p.kind_label}}</td><td>${{p.taluk}}</td><td>${{fmt(p.supply)}}</td><td>${{fmt(p.demand)}}</td><td>${{fmt(p.inventory)}}</td><td>${{pct}}%</td></tr>`;
        }});
        html += "</tbody>";
      }} else if (mode === "qoq") {{
        const s = qoqBlock();
        if (YEAR_KEYS.length > 1 && launchYear === "all") {{
          html = "<thead><tr><th>Quarter</th><th>Launch year</th><th>Projects</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
          s.labels.forEach((q, i) => {{
            YEAR_KEYS.forEach(y => {{
              const yb = Q.by_year && Q.by_year[y];
              const ov = yb && (kind === "all" ? yb.overall : (yb.by_kind && yb.by_kind[kind] && yb.by_kind[kind].overall));
              const sup = ov ? (ov.supply[i] || 0) : 0;
              const dem = ov ? (ov.demand[i] || 0) : 0;
              const inv = ov ? (ov.inventory[i] || 0) : 0;
              const n = ov ? (ov.projects[i] || 0) : 0;
              const pct = sup ? (100 * dem / sup).toFixed(1) : "0.0";
              html += `<tr><td>${{q}}</td><td>${{y}} launches</td><td>${{fmt(n)}}</td><td>${{fmt(sup)}}</td><td>${{fmt(dem)}}</td><td>${{fmt(inv)}}</td><td>${{pct}}%</td></tr>`;
            }});
          }});
          html += "</tbody>";
        }} else {{
          html = "<thead><tr><th>Quarter</th><th>Projects</th><th>Supply</th><th>Demand</th><th>Inventory</th><th>Booked %</th></tr></thead><tbody>";
          s.labels.forEach((q, i) => {{
            const sup = s.supply[i] || 0, dem = s.demand[i] || 0;
            const pct = sup ? (100 * dem / sup).toFixed(1) : "0.0";
            html += `<tr><td>${{q}}</td><td>${{fmt(s.projects[i] || 0)}}</td><td>${{fmt(sup)}}</td><td>${{fmt(dem)}}</td><td>${{fmt(s.inventory[i] || 0)}}</td><td>${{pct}}%</td></tr>`;
          }});
          html += "</tbody>";
        }}
      }}
      document.getElementById("tbl").innerHTML = html;
    }}

    function renderUnreported() {{
      const rows = kindUnreported();
      const groups = {{}};
      rows.forEach(r => {{
        const k = r.kind || "other";
        if (!groups[k]) groups[k] = {{ label: r.kind_label || k, names: [] }};
        groups[k].names.push(r.name);
      }});
      let html = "";
      KIND_ORDER.forEach(k => {{
        const g = groups[k];
        if (!g) return;
        html += `<h3 class="kind">${{g.label}} (${{g.names.length}})</h3><ul class="unreported">`;
        g.names.forEach(n => {{ html += `<li>${{n}}</li>`; }});
        html += "</ul>";
      }});
      document.getElementById("unlist").innerHTML = html;
    }}

    function draw() {{
      renderStats();
      renderTable();
      renderUnreported();
      document.getElementById("note").textContent =
        "Apartments = Residential/Group Housing + Mixed Development. Plots / villas = Plotted Development. Latest filing for Market and Projects. QoQ uses every filed quarter.";
      if (chart) {{ chart.destroy(); chart = null; }}
      if (chart2) {{ chart2.destroy(); chart2 = null; }}
      document.getElementById("chart-box").hidden = false;
      document.getElementById("chart2-box").hidden = true;
      if (mode === "unreported") return;

      const box = document.getElementById("chart");
      const box2 = document.getElementById("chart2");
      const parking = [
        {{ label: "Supply", key: "supply", color: "#6b7280" }},
        {{ label: "Demand (booked)", key: "demand", color: "#d97706" }},
        {{ label: "Inventory (available)", key: "inventory", color: "#2563eb" }},
      ];

      if (mode === "market") {{
        if (YEAR_KEYS.length > 1 && launchYear === "all") {{
          const labels = YEAR_KEYS.map(y => DATA.years[y].label);
          chart = bars(box, labels, [
            {{ label: "Approved", data: YEAR_KEYS.map(y => DATA.years[y].projects_approved), backgroundColor: "#6b7280" }},
            {{ label: "With parking QPR", data: YEAR_KEYS.map(y => DATA.years[y].projects_with_qpr), backgroundColor: "#2563eb" }},
            {{ label: "Unreported QPR", data: YEAR_KEYS.map(y => DATA.years[y].unreported), backgroundColor: "#d97706" }},
          ], "Project coverage by launch year", false, false);
          document.getElementById("chart2-box").hidden = false;
          chart2 = bars(box2, labels, parking.map(s => ({{
            label: s.label,
            data: YEAR_KEYS.map(y => DATA.years[y][s.key]),
            backgroundColor: s.color,
          }})), "Parking supply, demand, inventory by launch year", false, false);
          return;
        }}
        if (kind === "all") {{
          const keys = KIND_ORDER.filter(k => DATA.kinds[k]);
          const labels = keys.map(k => DATA.kinds[k].label);
          chart = bars(box, labels, [
            {{ label: "Approved", data: keys.map(k => DATA.kinds[k].projects_approved), backgroundColor: "#6b7280" }},
            {{ label: "With parking QPR", data: keys.map(k => DATA.kinds[k].projects_with_qpr), backgroundColor: "#2563eb" }},
            {{ label: "Unreported QPR", data: keys.map(k => DATA.kinds[k].unreported), backgroundColor: "#d97706" }},
          ], "Project coverage by type — approved vs parking QPR", false, false);
          document.getElementById("chart2-box").hidden = false;
          chart2 = bars(box2, labels, parking.map(s => ({{
            label: s.label,
            data: keys.map(k => DATA.kinds[k][s.key]),
            backgroundColor: s.color,
          }})), "Parking supply, demand, inventory by type", false, false);
          return;
        }}
        const m = slice();
        if (!m.supply) {{
          document.getElementById("chart-box").hidden = true;
          return;
        }}
        document.getElementById("chart-box").hidden = false;
        const names = Object.keys(m.taluks);
        chart = bars(box, names, parking.map(s => ({{
          label: s.label,
          data: names.map(n => m.taluks[n][s.key]),
          backgroundColor: s.color,
        }})), (m.label || "Type") + " by taluk — Supply, Demand, Inventory", false, false);
        return;
      }}
      document.getElementById("chart-box").hidden = false;
      if (mode === "projects") {{
        const rows = kindProjects().filter(p => p.supply > 0);
        if (!rows.length) {{ document.getElementById("chart-box").hidden = true; return; }}
        chart = bars(box,
          rows.map(p => p.name.length > 32 ? p.name.slice(0, 31) + "…" : p.name),
          [
            {{ label: "Demand (booked)", data: rows.map(p => p.demand), backgroundColor: "#d97706" }},
            {{ label: "Inventory (available)", data: rows.map(p => p.inventory), backgroundColor: "#2563eb" }},
          ],
          "Projects — Demand + Inventory = Supply", true, true);
        return;
      }}
      const s = qoqBlock();
      if (!seriesHas(s)) {{ document.getElementById("chart-box").hidden = true; return; }}
      chart = bars(box, s.labels, parking.map(x => ({{
        label: x.label, data: s[x.key], backgroundColor: x.color,
      }})), s.title, false, false);
      if (YEAR_KEYS.length > 1 && launchYear === "all") {{
        const colors = ["#2563eb", "#d97706", "#059669", "#6b7280"];
        document.getElementById("chart2-box").hidden = false;
        chart2 = bars(box2, s.labels, YEAR_KEYS.map((y, i) => {{
          const yb = Q.by_year && Q.by_year[y];
          const ov = yb && (kind === "all" ? yb.overall : (yb.by_kind && yb.by_kind[kind] && yb.by_kind[kind].overall));
          return {{
            label: y + " demand",
            data: ov ? ov.demand : [],
            backgroundColor: colors[i % colors.length],
          }};
        }}), "QoQ demand booked by launch year", false, false);
      }}
    }}

    document.getElementById("btn-market").onclick = () => setMode("market");
    document.getElementById("btn-projects").onclick = () => setMode("projects");
    document.getElementById("btn-qoq").onclick = () => setMode("qoq");
    document.getElementById("btn-unreported").onclick = () => setMode("unreported");
    sel.onchange = () => {{ taluk = sel.value; draw(); }};
    setMode(mode);
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path


def write_canvas(data: dict[str, Any], canvas_path: Path) -> Path:
    canvas_path.parent.mkdir(parents=True, exist_ok=True)
    canvas_path.write_text(_canvas_source(data), encoding="utf-8")
    return canvas_path


def _canvas_source(data: dict[str, Any]) -> str:
    payload = _js(data)
    return f'''import {{
  BarChart,
  Callout,
  Grid,
  H1,
  H2,
  PieChart,
  Pill,
  Row,
  Select,
  Stack,
  Stat,
  Table,
  Text,
  useCanvasState,
  useMemo,
}} from "cursor/canvas";

type Series = {{
  supply: number[];
  demand: number[];
  inventory: number[];
  projects: number[];
}};

type TalukRow = {{
  approved: number;
  n: number;
  unreported: number;
  supply: number;
  demand: number;
  inventory: number;
}};

type Market = {{
  projects_approved: number;
  projects_with_qpr: number;
  unreported: number;
  supply: number;
  demand: number;
  inventory: number;
  taluks: Record<string, TalukRow>;
  kind?: string;
  label?: string;
  portal?: string;
}};

type Project = {{
  id: string;
  name: string;
  promoter: string;
  reg: string;
  taluk: string;
  type: string;
  kind: string;
  kind_label: string;
  launch_year: number | null;
  approved: string;
  quarter: string;
  submitted: string | null;
  supply: number;
  demand: number;
  inventory: number;
}};

type Unreported = {{
  name: string;
  kind: string;
  kind_label: string;
  type: string;
  taluk: string;
  launch_year: number | null;
}};

type Report = {{
  qoq: {{
    meta: {{
      district?: string;
      approved_year?: number | string;
      scraped_at?: string;
      source?: string;
      qoq?: boolean;
      capture?: string;
      project_count?: number;
      quarter_count?: number;
      default_view?: string;
      default_kind?: string;
      title_year?: string;
      launch_years?: number[];
      captures?: Record<string, string>;
    }};
    quarters: string[];
    overall: Series;
    taluks: Record<string, Series>;
    by_kind: Record<string, {{ overall: Series; taluks: Record<string, Series> }}>;
    by_year: Record<
      string,
      {{
        overall: Series;
        taluks: Record<string, Series>;
        by_kind: Record<string, {{ overall: Series; taluks: Record<string, Series> }}>;
      }}
    >;
  }};
  market: Market;
  kinds: Record<string, Market>;
  years: Record<
    string,
    Market & {{ year?: string; kinds?: Record<string, Market> }}
  >;
  kind_meta: Record<string, {{ label: string; portal: string }}>;
  projects: Project[];
  unreported: Unreported[];
}};

const DATA: Report = {payload};

const TALUK_NAMES = Object.keys(DATA.qoq.taluks);
const KIND_KEYS = (["apartments", "plots", "other"] as const).filter(
  (k) => DATA.kinds[k],
);
const YEAR_KEYS = (DATA.qoq.meta.launch_years || [])
  .map(String)
  .filter((y) => DATA.years[y]);
const YEAR_TONES = ["info", "warning", "success", "neutral"] as const;

function fmt(n: number): string {{
  return n.toLocaleString("en-IN");
}}

function bookedPct(supply: number, demand: number): number {{
  return supply > 0 ? (demand / supply) * 100 : 0;
}}

function shortName(name: string, max = 32): string {{
  const n = name.trim();
  return n.length <= max ? n : `${{n.slice(0, max - 1)}}…`;
}}

function seriesHasParking(s: Series | undefined): boolean {{
  return !!s && s.supply.some((v) => v > 0);
}}

function emptySeries(): Series {{
  return {{ supply: [], demand: [], inventory: [], projects: [] }};
}}

export default function KreraParkingQoQ() {{
  const [view, setView] = useCanvasState(
    "kreraMainView",
    DATA.qoq.meta.default_view || "market",
  );
  const [kind, setKind] = useCanvasState(
    "kreraKind",
    DATA.qoq.meta.default_kind || "all",
  );
  const [launchYear, setLaunchYear] = useCanvasState("kreraLaunchYear", "all");
  const [qoqScope, setQoqScope] = useCanvasState("kreraQoqView", "overall");
  const [taluk, setTaluk] = useCanvasState(
    "kreraQoqTaluk",
    TALUK_NAMES[0] || "",
  );
  const [projTaluk, setProjTaluk] = useCanvasState("kreraProjTaluk", "all");

  const slice = useMemo(() => {{
    if (launchYear === "all") {{
      return kind === "all" ? DATA.market : DATA.kinds[kind] || DATA.market;
    }}
    const yb = DATA.years[launchYear];
    if (!yb) return DATA.market;
    if (kind === "all") return yb;
    return (yb.kinds && yb.kinds[kind]) || yb;
  }}, [launchYear, kind]);
  const kindLabel = kind === "all" ? "All types" : slice.label || kind;
  const yearLabel =
    launchYear === "all"
      ? DATA.qoq.meta.title_year || "All launch years"
      : `${{launchYear}} launches`;
  const yearMarketRows = YEAR_KEYS.map((y) => {{
    const yb = DATA.years[y];
    if (kind === "all" || !yb) return yb;
    return (yb.kinds && yb.kinds[kind]) || yb;
  }});

  const projectRows = useMemo(() => {{
    let base = DATA.projects;
    if (kind !== "all") base = base.filter((p) => p.kind === kind);
    if (launchYear !== "all") {{
      const y = Number(launchYear);
      base = base.filter((p) => p.launch_year === y);
    }}
    if (projTaluk === "all") return base;
    return base.filter((p) => p.taluk === projTaluk);
  }}, [kind, launchYear, projTaluk]);

  const chartProjects = useMemo(
    () => projectRows.filter((p) => p.supply > 0),
    [projectRows],
  );

  const top = useMemo(() => chartProjects.slice(0, 15), [chartProjects]);

  const unreportedRows = useMemo(() => {{
    let rows = DATA.unreported;
    if (kind !== "all") rows = rows.filter((r) => r.kind === kind);
    if (launchYear !== "all") {{
      const y = Number(launchYear);
      rows = rows.filter((r) => r.launch_year === y);
    }}
    return rows;
  }}, [kind, launchYear]);

  const qoqSrc = useMemo(() => {{
    if (launchYear === "all") {{
      if (kind === "all") {{
        return {{ overall: DATA.qoq.overall, taluks: DATA.qoq.taluks }};
      }}
      return DATA.qoq.by_kind[kind];
    }}
    const yb = DATA.qoq.by_year[launchYear];
    if (!yb) return undefined;
    if (kind === "all") return yb;
    return yb.by_kind[kind];
  }}, [launchYear, kind]);

  const qoqSeries = useMemo(() => {{
    if (!qoqSrc) return emptySeries();
    if (qoqScope === "taluk" && taluk && qoqSrc.taluks[taluk]) {{
      return qoqSrc.taluks[taluk];
    }}
    return qoqSrc.overall;
  }}, [qoqSrc, qoqScope, taluk]);

  const yearQoqMap = useMemo(() => {{
    const out: Record<string, Series> = {{}};
    for (const y of YEAR_KEYS) {{
      const yb = DATA.qoq.by_year[y];
      if (!yb) {{
        out[y] = emptySeries();
        continue;
      }}
      const root = kind === "all" ? yb : yb.by_kind[kind];
      if (!root) {{
        out[y] = emptySeries();
        continue;
      }}
      if (qoqScope === "taluk" && taluk && root.taluks[taluk]) {{
        out[y] = root.taluks[taluk];
      }} else {{
        out[y] = root.overall;
      }}
    }}
    return out;
  }}, [kind, qoqScope, taluk]);
  const showYearBreakout = YEAR_KEYS.length > 1 && launchYear === "all";

  const qLast = qoqSeries.supply.length - 1;
  const qSupply = qLast >= 0 ? qoqSeries.supply[qLast] : 0;
  const qDemand = qLast >= 0 ? qoqSeries.demand[qLast] : 0;
  const qInventory = qLast >= 0 ? qoqSeries.inventory[qLast] : 0;
  const talukNames = Object.keys(slice.taluks);
  const typeRows = KIND_KEYS.map((k) => DATA.kinds[k]);
  const hasParking = slice.supply > 0;
  const qoqHasParking = seriesHasParking(qoqSeries);

  return (
    <Stack gap={{24}}>
      <Stack gap={{8}}>
        <H1>
          {{DATA.qoq.meta.district}} {{DATA.qoq.meta.title_year || DATA.qoq.meta.approved_year}} parking
        </H1>
        <Text tone="secondary">
          Apartments = Residential/Group Housing and Mixed Development.
          Plots / villas = Plotted Development. Supply = Total No of Parkings.
          Demand = Parkings Booked. Inventory = Parkings Available.
        </Text>
        <Text tone="tertiary" size="small">
          Source: {{DATA.qoq.meta.source}} · scraped {{DATA.qoq.meta.scraped_at}}
        </Text>
        <Row gap={{8}} wrap>
          <Pill size="sm" active={{view === "market"}} onClick={{() => setView("market")}}>
            Overall market
          </Pill>
          <Pill size="sm" active={{view === "projects"}} onClick={{() => setView("projects")}}>
            Projects
          </Pill>
          <Pill size="sm" active={{view === "qoq"}} onClick={{() => setView("qoq")}}>
            QoQ
          </Pill>
          <Pill
            size="sm"
            active={{view === "unreported"}}
            onClick={{() => setView("unreported")}}
          >
            Unreported QPR
          </Pill>
        </Row>
        <Row gap={{8}} wrap>
          <Pill size="sm" active={{kind === "all"}} onClick={{() => setKind("all")}}>
            All types
          </Pill>
          {{DATA.kinds.apartments ? (
            <Pill
              size="sm"
              active={{kind === "apartments"}}
              onClick={{() => setKind("apartments")}}
            >
              Apartments
            </Pill>
          ) : null}}
          {{DATA.kinds.plots ? (
            <Pill
              size="sm"
              active={{kind === "plots"}}
              onClick={{() => setKind("plots")}}
            >
              Plots / villas
            </Pill>
          ) : null}}
          {{DATA.kinds.other ? (
            <Pill
              size="sm"
              active={{kind === "other"}}
              onClick={{() => setKind("other")}}
            >
              Other
            </Pill>
          ) : null}}
        </Row>
        {{YEAR_KEYS.length > 1 ? (
          <Row gap={{8}} wrap>
            <Pill
              size="sm"
              active={{launchYear === "all"}}
              onClick={{() => setLaunchYear("all")}}
            >
              All years
            </Pill>
            {{YEAR_KEYS.map((y) => (
              <Pill
                key={{y}}
                size="sm"
                active={{launchYear === y}}
                onClick={{() => setLaunchYear(y)}}
              >
                {{`${{y}} launches`}}
              </Pill>
            ))}}
          </Row>
        ) : null}}
      </Stack>

      {{view === "market" ? (
        <Stack gap={{16}}>
          <Grid columns={{4}} gap={{12}}>
            <Stat value={{fmt(slice.supply)}} label="Supply" />
            <Stat value={{fmt(slice.demand)}} label="Demand booked" tone="warning" />
            <Stat value={{fmt(slice.inventory)}} label="Inventory available" tone="info" />
            <Stat
              value={{`${{bookedPct(slice.supply, slice.demand).toFixed(1)}}%`}}
              label="Booked of supply"
              tone="success"
            />
          </Grid>
          <Callout tone="info" title={{`${{yearLabel}} · ${{kindLabel}} coverage`}}>
            {{slice.projects_with_qpr}} of {{slice.projects_approved}} approved
            projects filed parking in Quarterly Updates.
            {{slice.unreported}} have no parking QPR.
            {{kind === "all"
              ? " Parking totals are almost entirely Apartments — plotted projects rarely file a parking table."
              : slice.portal
                ? ` K-RERA type: ${{slice.portal}}.`
                : ""}}
          </Callout>
          {{showYearBreakout ? (
            <Stack gap={{16}}>
              <H2>Latest filing by launch year</H2>
              <Text tone="secondary" size="small">
                Parking spaces · {{kindLabel}} · one latest QPR per project
              </Text>
              <BarChart
                categories={{yearMarketRows.map((r) => r.label || "")}}
                series={{[
                  {{
                    name: "Supply",
                    data: yearMarketRows.map((r) => r.supply),
                    tone: "neutral",
                  }},
                  {{
                    name: "Demand (booked)",
                    data: yearMarketRows.map((r) => r.demand),
                    tone: "warning",
                  }},
                  {{
                    name: "Inventory (available)",
                    data: yearMarketRows.map((r) => r.inventory),
                    tone: "info",
                  }},
                ]}}
                height={{280}}
              />
              <H2>Coverage by launch year</H2>
              <Text tone="secondary" size="small">
                Project count · approved vs parking QPR vs unreported
              </Text>
              <BarChart
                categories={{yearMarketRows.map((r) => r.label || "")}}
                series={{[
                  {{
                    name: "Approved",
                    data: yearMarketRows.map((r) => r.projects_approved),
                    tone: "neutral",
                  }},
                  {{
                    name: "With parking QPR",
                    data: yearMarketRows.map((r) => r.projects_with_qpr),
                    tone: "info",
                  }},
                  {{
                    name: "Unreported QPR",
                    data: yearMarketRows.map((r) => r.unreported),
                    tone: "warning",
                  }},
                ]}}
                height={{280}}
              />
              <Table
                headers={{[
                  "Launch year",
                  "Approved",
                  "With QPR",
                  "Unreported",
                  "Supply",
                  "Demand",
                  "Inventory",
                  "Booked %",
                ]}}
                columnAlign={{[
                  "left",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                ]}}
                rows={{yearMarketRows.map((r) => [
                  r.label || "",
                  String(r.projects_approved),
                  String(r.projects_with_qpr),
                  String(r.unreported),
                  fmt(r.supply),
                  fmt(r.demand),
                  fmt(r.inventory),
                  `${{bookedPct(r.supply, r.demand).toFixed(1)}}%`,
                ])}}
              />
            </Stack>
          ) : null}}
          {{kind === "all" ? (
            <Stack gap={{16}}>
              <H2>Coverage by project type</H2>
              <Text tone="secondary" size="small">
                Project count · approved vs parking QPR vs unreported
              </Text>
              <BarChart
                categories={{typeRows.map((r) => r.label || "")}}
                series={{[
                  {{
                    name: "Approved",
                    data: typeRows.map((r) => r.projects_approved),
                    tone: "neutral",
                  }},
                  {{
                    name: "With parking QPR",
                    data: typeRows.map((r) => r.projects_with_qpr),
                    tone: "info",
                  }},
                  {{
                    name: "Unreported QPR",
                    data: typeRows.map((r) => r.unreported),
                    tone: "warning",
                  }},
                ]}}
                height={{280}}
              />
              <H2>Parking supply, demand, inventory by type</H2>
              <Text tone="secondary" size="small">
                Parking spaces · latest filing · plots/villas usually 0
              </Text>
              <BarChart
                categories={{typeRows.map((r) => r.label || "")}}
                series={{[
                  {{
                    name: "Supply",
                    data: typeRows.map((r) => r.supply),
                    tone: "neutral",
                  }},
                  {{
                    name: "Demand (booked)",
                    data: typeRows.map((r) => r.demand),
                    tone: "warning",
                  }},
                  {{
                    name: "Inventory (available)",
                    data: typeRows.map((r) => r.inventory),
                    tone: "info",
                  }},
                ]}}
                height={{280}}
              />
              <H2>Type detail</H2>
              <Table
                headers={{[
                  "Type",
                  "K-RERA types",
                  "Approved",
                  "With QPR",
                  "Unreported",
                  "Supply",
                  "Demand",
                  "Inventory",
                  "Booked %",
                ]}}
                columnAlign={{[
                  "left",
                  "left",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                ]}}
                rows={{typeRows.map((r) => [
                  r.label || "",
                  r.portal || "",
                  String(r.projects_approved),
                  String(r.projects_with_qpr),
                  String(r.unreported),
                  fmt(r.supply),
                  fmt(r.demand),
                  fmt(r.inventory),
                  `${{bookedPct(r.supply, r.demand).toFixed(1)}}%`,
                ])}}
              />
            </Stack>
          ) : null}}
          {{hasParking ? (
            <Grid columns={{2}} gap={{16}}>
              <Stack gap={{8}}>
                <H2>Market mix — booked vs available</H2>
                <Text tone="secondary" size="small">
                  Parking spaces · {{kindLabel}} · {{slice.projects_with_qpr}} projects with a QPR
                </Text>
                <PieChart
                  donut
                  size={{240}}
                  data={{[
                    {{ label: "Demand (booked)", value: slice.demand, tone: "warning" }},
                    {{
                      label: "Inventory (available)",
                      value: slice.inventory,
                      tone: "info",
                    }},
                  ]}}
                />
              </Stack>
              <Stack gap={{8}}>
                <H2>Supply, demand, inventory by taluk</H2>
                <Text tone="secondary" size="small">
                  Parking spaces · {{kindLabel}} · grouped bars · latest filing
                </Text>
                <BarChart
                  categories={{talukNames.map((n) => n.replace("Bengaluru ", "Blr "))}}
                  series={{[
                    {{
                      name: "Supply",
                      data: talukNames.map((n) => slice.taluks[n].supply),
                      tone: "neutral",
                    }},
                    {{
                      name: "Demand (booked)",
                      data: talukNames.map((n) => slice.taluks[n].demand),
                      tone: "warning",
                    }},
                    {{
                      name: "Inventory (available)",
                      data: talukNames.map((n) => slice.taluks[n].inventory),
                      tone: "info",
                    }},
                  ]}}
                  height={{280}}
                />
              </Stack>
            </Grid>
          ) : (
            <Callout tone="warning" title="No parking QPR for this type">
              {{slice.projects_approved}} approved {{kind === "all" ? "projects" : kindLabel.toLowerCase()}}
              and none filed Total No of Parkings in Quarterly Updates.
            </Callout>
          )}}
          <H2>Taluk detail — {{kindLabel}}</H2>
          <Table
            headers={{[
              "Taluk",
              "Approved",
              "With QPR",
              "Unreported",
              "Supply",
              "Demand",
              "Inventory",
              "Booked %",
            ]}}
            columnAlign={{[
              "left",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
            ]}}
            rows={{talukNames.map((n) => {{
              const r = slice.taluks[n];
              return [
                n,
                String(r.approved),
                String(r.n),
                String(r.unreported),
                fmt(r.supply),
                fmt(r.demand),
                fmt(r.inventory),
                `${{bookedPct(r.supply, r.demand).toFixed(1)}}%`,
              ];
            }})}}
          />
        </Stack>
      ) : null}}

      {{view === "projects" ? (
        <Stack gap={{16}}>
          <Row gap={{8}} wrap>
            <Pill size="sm" active={{projTaluk === "all"}} onClick={{() => setProjTaluk("all")}}>
              All taluks
            </Pill>
            <Pill
              size="sm"
              active={{projTaluk === "Bengaluru East"}}
              onClick={{() => setProjTaluk("Bengaluru East")}}
            >
              Bengaluru East
            </Pill>
            <Pill
              size="sm"
              active={{projTaluk === "Bengaluru South"}}
              onClick={{() => setProjTaluk("Bengaluru South")}}
            >
              Bengaluru South
            </Pill>
            <Pill
              size="sm"
              active={{projTaluk === "Anekal"}}
              onClick={{() => setProjTaluk("Anekal")}}
            >
              Anekal
            </Pill>
            <Pill
              size="sm"
              active={{projTaluk === "Bengaluru North"}}
              onClick={{() => setProjTaluk("Bengaluru North")}}
            >
              Bengaluru North
            </Pill>
            <Pill
              size="sm"
              active={{projTaluk === "Yelahanka"}}
              onClick={{() => setProjTaluk("Yelahanka")}}
            >
              Yelahanka
            </Pill>
          </Row>
          {{top.length > 0 ? (
            <Stack gap={{8}}>
              <H2>
                Largest 15 {{kind === "all" ? "projects" : kindLabel.toLowerCase()}} by
                parking supply
              </H2>
              <Text tone="secondary" size="small">
                Parking spaces · grouped bars · latest quarter on the K-RERA page
              </Text>
              <BarChart
                categories={{top.map((p) => shortName(p.name, 28))}}
                series={{[
                  {{ name: "Supply", data: top.map((p) => p.supply), tone: "neutral" }},
                  {{
                    name: "Demand (booked)",
                    data: top.map((p) => p.demand),
                    tone: "warning",
                  }},
                  {{
                    name: "Inventory (available)",
                    data: top.map((p) => p.inventory),
                    tone: "info",
                  }},
                ]}}
                height={{360}}
              />
            </Stack>
          ) : null}}
          {{chartProjects.length > 0 ? (
            <Stack gap={{8}}>
              <H2>
                All {{kind === "all" ? "projects" : kindLabel.toLowerCase()}} with a
                parking QPR
              </H2>
              <Text tone="secondary" size="small">
                Horizontal stacked bars: Demand (booked) plus Inventory (available)
                equals Supply
              </Text>
              <BarChart
                horizontal
                stacked
                height={{Math.max(420, chartProjects.length * 22)}}
                categories={{chartProjects.map((p) => shortName(p.name, 32))}}
                series={{[
                  {{
                    name: "Demand (booked)",
                    data: chartProjects.map((p) => p.demand),
                    tone: "warning",
                  }},
                  {{
                    name: "Inventory (available)",
                    data: chartProjects.map((p) => p.inventory),
                    tone: "info",
                  }},
                ]}}
              />
            </Stack>
          ) : (
            <Callout tone="warning" title="No parking QPR in this filter">
              {{kindLabel}} with the current taluk filter have no parking table
              in Quarterly Updates. Use Unreported QPR for names.
            </Callout>
          )}}
          {{projectRows.length > 0 ? (
            <Table
              stickyHeader
              striped
              headers={{
                YEAR_KEYS.length > 1
                  ? [
                      "Project",
                      "Launch",
                      "Type",
                      "Taluk",
                      "Supply",
                      "Demand",
                      "Inventory",
                      "Booked %",
                      "Quarter",
                    ]
                  : [
                      "Project",
                      "Type",
                      "Taluk",
                      "Supply",
                      "Demand",
                      "Inventory",
                      "Booked %",
                      "Quarter",
                    ]
              }}
              columnAlign={{
                YEAR_KEYS.length > 1
                  ? [
                      "left",
                      "left",
                      "left",
                      "left",
                      "right",
                      "right",
                      "right",
                      "right",
                      "left",
                    ]
                  : [
                      "left",
                      "left",
                      "left",
                      "right",
                      "right",
                      "right",
                      "right",
                      "left",
                    ]
              }}
              rows={{projectRows.map((p) =>
                YEAR_KEYS.length > 1
                  ? [
                      p.name,
                      p.launch_year != null ? String(p.launch_year) : "",
                      p.kind_label,
                      p.taluk.replace("Bengaluru ", "Blr "),
                      fmt(p.supply),
                      fmt(p.demand),
                      fmt(p.inventory),
                      `${{bookedPct(p.supply, p.demand).toFixed(1)}}%`,
                      p.quarter,
                    ]
                  : [
                      p.name,
                      p.kind_label,
                      p.taluk.replace("Bengaluru ", "Blr "),
                      fmt(p.supply),
                      fmt(p.demand),
                      fmt(p.inventory),
                      `${{bookedPct(p.supply, p.demand).toFixed(1)}}%`,
                      p.quarter,
                    ],
              )}}
              style={{{{ maxHeight: 560 }}}}
            />
          ) : null}}
        </Stack>
      ) : null}}

      {{view === "qoq" ? (
        <Stack gap={{16}}>
          <Row gap={{8}} wrap>
            <Pill
              size="sm"
              active={{qoqScope === "overall"}}
              onClick={{() => setQoqScope("overall")}}
            >
              Overall
            </Pill>
            <Pill
              size="sm"
              active={{qoqScope === "taluk"}}
              onClick={{() => setQoqScope("taluk")}}
            >
              Taluk
            </Pill>
            {{qoqScope === "taluk" ? (
              <Select
                value={{taluk}}
                onChange={{setTaluk}}
                options={{TALUK_NAMES.map((name) => ({{
                  value: name,
                  label: name,
                }}))}}
              />
            ) : null}}
          </Row>
          {{qoqHasParking ? (
            <Grid columns={{4}} gap={{12}}>
              <Stat value={{fmt(qSupply)}} label="Supply (latest quarter)" />
              <Stat value={{fmt(qDemand)}} label="Demand booked" tone="warning" />
              <Stat value={{fmt(qInventory)}} label="Inventory available" tone="info" />
              <Stat
                value={{`${{bookedPct(qSupply, qDemand).toFixed(1)}}%`}}
                label="Booked of supply"
                tone="success"
              />
            </Grid>
          ) : null}}
          {{DATA.qoq.meta.capture === "latest_only" ? (
            <Callout tone="warning" title="Imported latest filing only">
              Quarter bars here are not the same project set. Run
              `python krera.py scrape` for true QoQ.
            </Callout>
          ) : DATA.qoq.meta.capture === "mixed" ? (
            <Callout tone="warning" title="Mixed snapshots">
              Combined years mix all-filings and latest-only scrapes. 2026
              quarter bars may not follow the same project set as 2025.
            </Callout>
          ) : DATA.qoq.meta.qoq ? (
            <Callout tone="info" title="QoQ">
              Each bar group is one K-RERA quarter for {{yearLabel}} · {{kindLabel}}.
              A project that filed Q4 and Q1 is counted in both.
            </Callout>
          ) : (
            <Callout tone="info" title="Single quarter">
              Only one QPR period is in this snapshot.
            </Callout>
          )}}
          {{qoqHasParking ? (
            <Stack gap={{8}}>
              <H2>
                {{qoqScope === "taluk"
                  ? `${{taluk}} ${{kindLabel.toLowerCase()}} parking QoQ`
                  : `${{kindLabel}} parking QoQ — supply, demand, inventory`}}
              </H2>
              <Text tone="secondary" size="small">
                Parking spaces · grouped bars · K-RERA FY quarter on the x-axis
              </Text>
              <BarChart
                categories={{DATA.qoq.quarters}}
                series={{[
                  {{ name: "Supply", data: qoqSeries.supply, tone: "neutral" }},
                  {{
                    name: "Demand (booked)",
                    data: qoqSeries.demand,
                    tone: "warning",
                  }},
                  {{
                    name: "Inventory (available)",
                    data: qoqSeries.inventory,
                    tone: "info",
                  }},
                ]}}
                height={{320}}
              />
            </Stack>
          ) : (
            <Callout tone="warning" title="No QoQ parking for this type">
              {{kindLabel}} have no quarterly parking filings in this snapshot.
            </Callout>
          )}}
          {{DATA.qoq.quarters.length > 0 && qoqHasParking ? (
            <Table
              headers={{[
                "Quarter",
                "Projects with parking QPR",
                "Supply",
                "Demand",
                "Inventory",
                "Booked %",
              ]}}
              columnAlign={{["left", "right", "right", "right", "right", "right"]}}
              rows={{DATA.qoq.quarters.map((q, i) => [
                q,
                String(qoqSeries.projects[i] ?? 0),
                fmt(qoqSeries.supply[i] ?? 0),
                fmt(qoqSeries.demand[i] ?? 0),
                fmt(qoqSeries.inventory[i] ?? 0),
                `${{bookedPct(qoqSeries.supply[i] ?? 0, qoqSeries.demand[i] ?? 0).toFixed(1)}}%`,
              ])}}
            />
          ) : null}}
          {{showYearBreakout ? (
            <Stack gap={{16}}>
              <H2>QoQ breakup by launch year — supply</H2>
              <Text tone="secondary" size="small">
                Parking spaces · {{kindLabel}} · K-RERA FY quarter on the x-axis
              </Text>
              <BarChart
                categories={{DATA.qoq.quarters}}
                series={{YEAR_KEYS.map((y, i) => ({{
                  name: `${{y}} launches`,
                  data: yearQoqMap[y]?.supply || [],
                  tone: YEAR_TONES[i % YEAR_TONES.length],
                }}))}}
                height={{280}}
              />
              <H2>QoQ breakup by launch year — demand booked</H2>
              <Text tone="secondary" size="small">
                Parking spaces booked · {{kindLabel}} · K-RERA FY quarter
              </Text>
              <BarChart
                categories={{DATA.qoq.quarters}}
                series={{YEAR_KEYS.map((y, i) => ({{
                  name: `${{y}} launches`,
                  data: yearQoqMap[y]?.demand || [],
                  tone: YEAR_TONES[i % YEAR_TONES.length],
                }}))}}
                height={{280}}
              />
              <H2>QoQ breakup by launch year — inventory available</H2>
              <Text tone="secondary" size="small">
                Parking spaces available · {{kindLabel}} · K-RERA FY quarter
              </Text>
              <BarChart
                categories={{DATA.qoq.quarters}}
                series={{YEAR_KEYS.map((y, i) => ({{
                  name: `${{y}} launches`,
                  data: yearQoqMap[y]?.inventory || [],
                  tone: YEAR_TONES[i % YEAR_TONES.length],
                }}))}}
                height={{280}}
              />
              <H2>QoQ table by launch year</H2>
              <Table
                headers={{[
                  "Quarter",
                  "Launch year",
                  "Projects",
                  "Supply",
                  "Demand",
                  "Inventory",
                  "Booked %",
                ]}}
                columnAlign={{[
                  "left",
                  "left",
                  "right",
                  "right",
                  "right",
                  "right",
                  "right",
                ]}}
                rows={{DATA.qoq.quarters.flatMap((q, i) =>
                  YEAR_KEYS.map((y) => {{
                    const s = yearQoqMap[y];
                    const sup = s?.supply[i] ?? 0;
                    const dem = s?.demand[i] ?? 0;
                    return [
                      q,
                      `${{y}} launches`,
                      String(s?.projects[i] ?? 0),
                      fmt(sup),
                      fmt(dem),
                      fmt(s?.inventory[i] ?? 0),
                      `${{bookedPct(sup, dem).toFixed(1)}}%`,
                    ];
                  }}),
                )}}
              />
            </Stack>
          ) : null}}
        </Stack>
      ) : null}}

      {{view === "unreported" ? (
        <Stack gap={{8}}>
          <H2>Unreported quarterly parking — {{yearLabel}} · {{kindLabel}}</H2>
          <Text tone="secondary">
            {{unreportedRows.length}} approved projects with no parking table
            in Quarterly Updates.
          </Text>
          {{unreportedRows.length > 0 ? (
            <Table
              stickyHeader
              striped
              headers={{
                YEAR_KEYS.length > 1
                  ? ["Project", "Launch", "Type", "Taluk"]
                  : kind === "all"
                    ? ["Project", "Type", "Taluk"]
                    : ["Project", "K-RERA type", "Taluk"]
              }}
              rows={{unreportedRows.map((r) =>
                YEAR_KEYS.length > 1
                  ? [
                      r.name,
                      r.launch_year != null ? String(r.launch_year) : "",
                      r.kind_label,
                      r.taluk.replace("Bengaluru ", "Blr "),
                    ]
                  : [
                      r.name,
                      kind === "all" ? r.kind_label : r.type,
                      r.taluk.replace("Bengaluru ", "Blr "),
                    ],
              )}}
              style={{{{ maxHeight: 640 }}}}
            />
          ) : null}}
        </Stack>
      ) : null}}
    </Stack>
  );
}}
'''


def generate_reports(
    data: dict[str, Any],
    canvas_path: Path | None = None,
) -> dict[str, Path]:
    stem = report_stem(data)
    qoq_json = write_qoq_json(data)
    unreported = write_unreported_list(data.get("unreported") or [], stem=stem)
    html = write_html(data)
    out: dict[str, Path] = {
        "json": qoq_json,
        "html": html,
        "unreported": unreported,
    }
    year = (data.get("qoq") or {}).get("meta", {}).get("approved_year")
    if canvas_path is not None:
        out["canvas"] = write_canvas(data, canvas_path)
    elif DEFAULT_CANVAS.is_dir():
        name = (
            f"krera-parking-qoq-{year}.canvas.tsx"
            if year
            else "krera-parking-qoq.canvas.tsx"
        )
        out["canvas"] = write_canvas(data, DEFAULT_CANVAS / name)
    return out
