from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .gui import (
    AXIS_OPTIONS,
    COLOR_OPTIONS,
    DEFAULT_PERCENTILE_LEGEND_TEXT,
    DEFAULT_PERCENTILES_TEXT,
    DEFAULT_COLOR_BY,
    LEGEND_POSITION_OPTIONS,
    LINE_SHAPE_OPTIONS,
    PERCENTILE_DASH_OPTIONS,
    PERCENTILE_DISPLAY_OPTIONS,
    PERCENTILE_LEGEND_MODE_OPTIONS,
    PLOT_MODE_OPTIONS,
    TABLE_COLUMNS,
    DEFAULT_PERCENTILE_DASH,
    DEFAULT_PERCENTILE_DISPLAY,
    DEFAULT_PERCENTILE_LEGEND_MODE,
    DEFAULT_PLOT_MODE,
    DEFAULT_PUBLICATION_OPTIONS,
    DEFAULT_TITLE_TEXT,
    DEFAULT_X_AXIS,
    DEFAULT_Y_AXIS,
    MAIN_ARTICLE_URL,
    METHODOLOGY_EXCERPT_PREFIX,
    METHODOLOGY_EXCERPT_SUFFIX,
    METHODOLOGY_SUMMARY,
    load_dataset,
)


POINT_FIELDS = [
    "vehicle_id",
    "display_name",
    "point_index",
    "soc_percent",
    "charging_power_kw",
    "charging_power_relative_percent",
    "manufacturer",
    "rank",
    "range_total_one_stop_km",
    "range_until_stop_km",
    "range_added_20min_km",
    "max_observed_charging_power_kw",
    "mean_observed_charging_power_kw",
]

VEHICLE_FIELDS = [
    "vehicle_id",
    "display_name",
    "manufacturer",
    "rank",
    "range_total_one_stop_km",
    "range_until_stop_km",
    "range_added_20min_km",
    "battery_capacity_kwh",
    "consumption_kwh_per_100km",
    "max_charging_power_kw",
    "max_observed_charging_power_kw",
    "mean_observed_charging_power_kw",
]


def _compact_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for row in rows:
        compacted.append({field: row.get(field) for field in fields if field in row})
    return compacted


def _load_source_metadata(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "source_metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_static_site(data_dir: str | Path = "output", out_dir: str | Path = "site") -> dict[str, Any]:
    data_path = Path(data_dir)
    site_path = Path(out_dir)
    assets_path = site_path / "assets"
    assets_path.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(data_path)
    payload = {
        "vehicles": _compact_rows(dataset.vehicles, VEHICLE_FIELDS),
        "vehicleRecords": dataset.vehicle_records,
        "vehicleIds": dataset.vehicle_ids,
        "points": _compact_rows(dataset.points, POINT_FIELDS),
        "sourceMetadata": _load_source_metadata(data_path),
        "ui": {
            "axisOptions": AXIS_OPTIONS,
            "colorOptions": COLOR_OPTIONS,
            "plotModeOptions": PLOT_MODE_OPTIONS,
            "lineShapeOptions": LINE_SHAPE_OPTIONS,
            "legendPositionOptions": LEGEND_POSITION_OPTIONS,
            "percentileDisplayOptions": PERCENTILE_DISPLAY_OPTIONS,
            "percentileLegendModeOptions": PERCENTILE_LEGEND_MODE_OPTIONS,
            "percentileDashOptions": PERCENTILE_DASH_OPTIONS,
            "tableColumns": TABLE_COLUMNS,
            "defaultPercentiles": DEFAULT_PERCENTILES_TEXT,
            "defaultPercentileLegendEntries": DEFAULT_PERCENTILE_LEGEND_TEXT,
            "defaultPlotMode": DEFAULT_PLOT_MODE,
            "defaultPercentileDisplay": DEFAULT_PERCENTILE_DISPLAY,
            "defaultPercentileLegendMode": DEFAULT_PERCENTILE_LEGEND_MODE,
            "defaultPercentileDash": DEFAULT_PERCENTILE_DASH,
            "defaultXAxis": DEFAULT_X_AXIS,
            "defaultYAxis": DEFAULT_Y_AXIS,
            "defaultColorBy": DEFAULT_COLOR_BY,
            "defaultLegendPosition": "inside_top_right",
            "defaultTitle": DEFAULT_TITLE_TEXT,
            "defaultPublicationOptions": DEFAULT_PUBLICATION_OPTIONS,
            "mainArticleUrl": MAIN_ARTICLE_URL,
            "methodologyExcerptPrefix": METHODOLOGY_EXCERPT_PREFIX,
            "methodologyExcerptSuffix": METHODOLOGY_EXCERPT_SUFFIX,
            "methodologySummary": METHODOLOGY_SUMMARY,
        },
    }

    (assets_path / "data.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (site_path / "index.html").write_text(_index_html(), encoding="utf-8")
    (site_path / ".nojekyll").write_text("", encoding="utf-8")
    return {
        "site": str(site_path.resolve()),
        "vehicles": len(dataset.vehicle_ids),
        "points": len(dataset.points),
    }


def _index_html() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ADAC/Infogram EV Charging Curves</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {
      color-scheme: light;
      --border: #d1d5db;
      --muted: #4b5563;
      --soft: #f3f4f6;
      --stripe: #fafafa;
      --text: #111827;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #fff; color: var(--text); font-family: Arial, sans-serif; }
    .page { max-width: 1500px; margin: 0 auto; padding: 22px 28px 34px; }
    .header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; }
    h1 { margin: 0; font-size: 24px; line-height: 1.2; }
    .toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .source-link { margin: 0 0 12px; font-size: 13px; color: #374151; }
    .source-link a, .methodology-box a { color: #1d4ed8; text-decoration: none; }
    .source-link a:hover, .methodology-box a:hover { text-decoration: underline; }
    button { border: 1px solid #9ca3af; background: #fff; color: var(--text); border-radius: 6px; padding: 8px 11px; cursor: pointer; }
    button:hover { background: var(--soft); }
    .summary, #export-status { min-height: 20px; color: var(--muted); font-size: 13px; }
    .table-wrap { height: 340px; overflow: auto; border: 1px solid #e5e7eb; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { position: sticky; top: 0; background: var(--soft); z-index: 1; font-weight: 700; }
    tbody tr:nth-child(odd) { background: var(--stripe); }
    td.vehicle { min-width: 310px; }
    .controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 12px; align-items: start; margin: 16px 0 8px; }
    .settings-panel { border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; background: #fff; }
    .settings-panel h2 { margin: 0 0 10px; font-size: 13px; line-height: 1.2; color: var(--text); }
    .settings-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(138px, 1fr)); gap: 10px; align-items: end; }
    .controls label, .export-row { min-width: 0; font-size: 13px; font-weight: 700; color: #374151; }
    .controls label.wide, .export-row.wide { grid-column: 1 / -1; }
    .controls input, .controls select, .search input {
      width: 100%; border: 1px solid var(--border); border-radius: 4px; padding: 8px; background: #fff;
    }
    .export-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .radio-row, .check-row { display: flex; flex-wrap: wrap; gap: 12px; min-height: 35px; align-items: center; font-weight: 400; }
    .radio-row label, .check-row label { min-width: 0; font-weight: 400; display: flex; gap: 4px; align-items: center; }
    .graph-wrap { overflow-x: auto; border-top: 1px solid #e5e7eb; padding-top: 10px; }
    .methodology-box { margin-top: 14px; border: 1px solid #cbd5e1; border-left: 4px solid #64748b; border-radius: 6px; background: #f8fafc; padding: 12px 14px; max-width: 920px; }
    .methodology-box h2 { margin: 0 0 8px; font-size: 15px; line-height: 1.25; }
    .methodology-box blockquote { margin: 0 0 8px; padding: 0 0 0 12px; border-left: 3px solid #94a3b8; color: var(--text); font-size: 13px; }
    .methodology-box p { margin: 0 0 8px; font-size: 13px; line-height: 1.45; color: #374151; }
    .methodology-box .methodology-source { margin-bottom: 0; font-size: 12px; color: var(--muted); }
    .small { font-size: 12px; color: var(--muted); }
    .hidden { display: none; }
  </style>
</head>
<body>
  <main class="page">
    <section class="header">
      <h1>ADAC/Infogram Charging Curves</h1>
      <div class="toolbar">
        <button id="select-all">Select all</button>
        <button id="select-none">Select none</button>
        <div id="selection-summary" class="summary"></div>
      </div>
    </section>

    <section class="source-link">
      <strong>Source:</strong>
      <a href="https://www.adac.de/rund-ums-fahrzeug/elektromobilitaet/laden/schnellladen-langstrecke-ladekurven-2026/" target="_blank" rel="noopener noreferrer">ADAC article: charging curves for long-distance fast charging</a>
    </section>

    <section class="search">
      <input id="vehicle-filter" type="search" placeholder="Filter vehicles, manufacturers, or table values">
    </section>
    <section class="table-wrap">
      <table id="vehicle-table">
        <thead></thead>
        <tbody></tbody>
      </table>
    </section>

    <section class="controls">
      <section class="settings-panel">
        <h2>Analysis</h2>
        <div class="settings-fields">
          <label class="wide">Plot mode<div id="plot-mode" class="radio-row"></div></label>
          <label>X axis<select id="x-axis"></select></label>
          <label>Y axis<select id="y-axis"></select></label>
          <label>Line color<select id="color-by"></select></label>
        </div>
      </section>
      <section class="settings-panel">
        <h2>Percentiles</h2>
        <div class="settings-fields">
          <label class="wide">Percentiles<input id="percentiles" type="text"></label>
          <label class="wide">Legend entries<input id="percentile-legend-entries" type="text"></label>
          <label>Display<select id="percentile-display"></select></label>
          <label>Legend<select id="percentile-legend-mode"></select></label>
        </div>
      </section>
      <section class="settings-panel">
        <h2>Lines & Legend</h2>
        <div class="settings-fields">
          <label>Line shape<select id="line-shape"></select></label>
          <label>Percentile dash<select id="percentile-dash"></select></label>
          <label>Legend position<select id="legend-position"></select></label>
          <label>Line width<input id="line-width" type="number" min="0.2" max="12" step="0.2" value="1.4"></label>
          <label>Marker size<input id="marker-size" type="number" min="0" max="20" step="0.5" value="0"></label>
          <label>Opacity<input id="line-opacity" type="number" min="0.05" max="1" step="0.05" value="1"></label>
        </div>
      </section>
      <section class="settings-panel">
        <h2>Figure & Export</h2>
        <div class="settings-fields">
          <label class="wide">Figure title<input id="title-text" type="text" value="100 EV Models / Charging Power"></label>
          <label class="wide">Font family<input id="font-family" type="text" value="Times New Roman"></label>
          <label>Figure width [px]<input id="plot-width" type="number" min="250" max="4000" step="1" value="500"></label>
          <label>Figure height [px]<input id="plot-height" type="number" min="180" max="3000" step="1" value="400"></label>
          <label>Base font size<input id="font-size" type="number" min="8" max="40" step="1" value="16"></label>
          <label>Title font size<input id="title-font-size" type="number" min="10" max="60" step="1" value="16"></label>
          <label>Axis title font size<input id="axis-title-font-size" type="number" min="8" max="44" step="1" value="16"></label>
          <label>Tick font size<input id="tick-font-size" type="number" min="6" max="36" step="1" value="16"></label>
          <label>Legend font size<input id="legend-font-size" type="number" min="6" max="36" step="1" value="16"></label>
          <label>SAE options<div id="publication-options" class="check-row"></div></label>
          <div class="export-row wide">
            <button id="export-svg">Export SVG</button>
            <div id="export-status"></div>
          </div>
        </div>
      </section>
    </section>

    <section class="graph-wrap">
      <div id="curve-plot"></div>
    </section>
    <section class="methodology-box">
      <h2>ADAC DC Charging Test Methodology</h2>
      <blockquote>Geladen wird im Test an einer <strong>300 kW</strong> starken Schnellladesäule von <strong>Alpitronic</strong>.</blockquote>
      <p>ADAC records charging curves to make DC charging-power fluctuations transparent. Vehicles are preconditioned overnight in a 20 °C test hall; the range basis is the mixed ADAC Ecotest cycle with urban, rural, and motorway shares. Where supported, route-planning battery preconditioning is triggered before charging. Charging power can still vary with cell state, charging management, and ambient temperature.</p>
      <p class="methodology-source">Source: <a href="https://www.adac.de/rund-ums-fahrzeug/elektromobilitaet/laden/schnellladen-langstrecke-ladekurven-2026/" target="_blank" rel="noopener noreferrer">ADAC article</a></p>
    </section>
    <p class="small">Static GitHub Pages build. Data are loaded from <code>assets/data.json</code>.</p>
  </main>

  <script>
    const DISCRETE_COLOR_FIELDS = new Set(["vehicle_id", "manufacturer"]);
    const DASH_PATTERNS = ["solid", "dash", "dot", "dashdot"];
    const PLOTLY_PALETTE = [
      "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
      "#FF97FF", "#FECB52", "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B",
      "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF"
    ];
    const VIRIDIS = [
      [0.0, [68, 1, 84]], [0.13, [71, 44, 122]], [0.25, [59, 81, 139]],
      [0.38, [44, 113, 142]], [0.50, [33, 144, 141]], [0.63, [39, 173, 129]],
      [0.75, [92, 200, 99]], [0.88, [170, 220, 50]], [1.0, [253, 231, 37]]
    ];

    let DATA = null;
    let selectedVehicleIds = new Set();
    let vehicleById = new Map();
    let pointsByVehicle = new Map();
    let currentFilter = "";

    const byId = (id) => document.getElementById(id);
    const num = (id, fallback) => {
      const value = Number(byId(id).value);
      return Number.isFinite(value) ? value : fallback;
    };
    const text = (id) => byId(id).value || "";
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const finiteNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : null;

    fetch("assets/data.json")
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load data: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        DATA = data;
        initState();
        renderControls();
        renderTable();
        bindEvents();
        updatePlot();
      })
      .catch((error) => {
        byId("selection-summary").textContent = error.message;
      });

    function initState() {
      vehicleById = new Map(DATA.vehicles.map((vehicle) => [String(vehicle.vehicle_id), vehicle]));
      pointsByVehicle = new Map();
      for (const point of DATA.points) {
        const vehicleId = String(point.vehicle_id);
        if (!pointsByVehicle.has(vehicleId)) pointsByVehicle.set(vehicleId, []);
        pointsByVehicle.get(vehicleId).push(point);
      }
      selectedVehicleIds = new Set(DATA.vehicleIds.slice(0, 8).map(String));
    }

    function fillSelect(id, options, value) {
      const element = byId(id);
      element.innerHTML = options.map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`).join("");
      element.value = value;
    }

    function fillRadio(id, options, value) {
      byId(id).innerHTML = options.map((option) => (
        `<label><input type="radio" name="${id}" value="${escapeHtml(option.value)}" ${option.value === value ? "checked" : ""}>${escapeHtml(option.label)}</label>`
      )).join("");
    }

    function renderControls() {
      fillRadio("plot-mode", DATA.ui.plotModeOptions, DATA.ui.defaultPlotMode);
      fillSelect("percentile-display", DATA.ui.percentileDisplayOptions, DATA.ui.defaultPercentileDisplay);
      fillSelect("percentile-legend-mode", DATA.ui.percentileLegendModeOptions, DATA.ui.defaultPercentileLegendMode);
      fillSelect("percentile-dash", DATA.ui.percentileDashOptions, DATA.ui.defaultPercentileDash);
      fillSelect("x-axis", DATA.ui.axisOptions, DATA.ui.defaultXAxis);
      fillSelect("y-axis", DATA.ui.axisOptions, DATA.ui.defaultYAxis);
      fillSelect("color-by", DATA.ui.colorOptions, DATA.ui.defaultColorBy);
      fillSelect("line-shape", DATA.ui.lineShapeOptions, "linear");
      fillSelect("legend-position", DATA.ui.legendPositionOptions, DATA.ui.defaultLegendPosition);
      byId("percentiles").value = DATA.ui.defaultPercentiles;
      byId("percentile-legend-entries").value = DATA.ui.defaultPercentileLegendEntries;
      byId("title-text").value = DATA.ui.defaultTitle;
      byId("publication-options").innerHTML = [
        `<label><input type="checkbox" id="show-title" ${DATA.ui.defaultPublicationOptions.includes("show_title") ? "checked" : ""}>Show title</label>`,
        `<label><input type="checkbox" id="cycle-line-dash" ${DATA.ui.defaultPublicationOptions.includes("cycle_line_dash") ? "checked" : ""}>Cycle line styles</label>`,
      ].join("");
    }

    function renderTable() {
      const table = byId("vehicle-table");
      const columns = [{name: "", id: "__selected"}, ...DATA.ui.tableColumns];
      table.querySelector("thead").innerHTML = `<tr>${columns.map((column) => `<th>${escapeHtml(column.name)}</th>`).join("")}</tr>`;
      const rows = DATA.vehicleRecords.filter(matchesFilter);
      table.querySelector("tbody").innerHTML = rows.map((vehicle) => {
        const cells = DATA.ui.tableColumns.map((column) => {
          const value = vehicle[column.id] ?? "";
          const cls = column.id === "display_name" ? " class=\"vehicle\"" : "";
          return `<td${cls}>${escapeHtml(value)}</td>`;
        }).join("");
        const checked = selectedVehicleIds.has(String(vehicle.vehicle_id)) ? "checked" : "";
        return `<tr><td><input type="checkbox" class="vehicle-check" value="${escapeHtml(vehicle.vehicle_id)}" ${checked}></td>${cells}</tr>`;
      }).join("");
      table.querySelectorAll(".vehicle-check").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
          if (checkbox.checked) selectedVehicleIds.add(String(checkbox.value));
          else selectedVehicleIds.delete(String(checkbox.value));
          updatePlot();
        });
      });
    }

    function matchesFilter(vehicle) {
      if (!currentFilter) return true;
      return Object.values(vehicle).join(" ").toLowerCase().includes(currentFilter);
    }

    function bindEvents() {
      byId("select-all").addEventListener("click", () => {
        selectedVehicleIds = new Set(DATA.vehicleIds.map(String));
        renderTable();
        updatePlot();
      });
      byId("select-none").addEventListener("click", () => {
        selectedVehicleIds = new Set();
        renderTable();
        updatePlot();
      });
      byId("vehicle-filter").addEventListener("input", (event) => {
        currentFilter = event.target.value.toLowerCase();
        renderTable();
      });
      document.querySelectorAll("input, select").forEach((element) => {
        if (element.id === "vehicle-filter" || element.classList.contains("vehicle-check")) return;
        element.addEventListener("input", updatePlot);
        element.addEventListener("change", updatePlot);
      });
      byId("export-svg").addEventListener("click", () => {
        Plotly.downloadImage("curve-plot", {
          format: "svg",
          filename: "adac_ev_charging_curves",
          width: num("plot-width", 336),
          height: num("plot-height", 250),
          scale: 1,
        });
        byId("export-status").textContent = "SVG export started";
      });
    }

    function updatePlot() {
      const selected = DATA.vehicleIds.map(String).filter((vehicleId) => selectedVehicleIds.has(vehicleId));
      const mode = document.querySelector("input[name='plot-mode']:checked")?.value || "vehicles";
      const traces = mode === "percentiles" ? buildPercentileTraces(selected) : buildVehicleTraces(selected);
      const showTitle = byId("show-title")?.checked || false;
      const titleText = text("title-text").trim();
      const layout = {
        title: plotTitle(showTitle, titleText || (mode === "percentiles" ? "ADAC/Infogram Charging Curve Percentiles" : "ADAC/Infogram Charging Curves")),
        xaxis: axisLayout("x-axis", num("axis-title-font-size", 12), num("tick-font-size", 11), 6),
        yaxis: axisLayout("y-axis", num("axis-title-font-size", 12), num("tick-font-size", 11), 5),
        width: num("plot-width", 336),
        height: num("plot-height", 250),
        font: {family: text("font-family") || "Times New Roman", size: num("font-size", 11), color: "black"},
        titlefont: {size: num("title-font-size", 12)},
        paper_bgcolor: "white",
        plot_bgcolor: "white",
        hovermode: "closest",
        showlegend: traces.some((trace) => trace.showlegend),
        legend: legendLayout(byId("legend-position").value, num("legend-font-size", 11), mode === "percentiles" ? "reversed" : "normal"),
        margin: layoutMargins(byId("legend-position").value, showTitle),
      };
      Plotly.react("curve-plot", traces, layout, {
        displaylogo: false,
        responsive: false,
        toImageButtonOptions: {
          format: "svg",
          filename: "adac_ev_charging_curves",
          width: num("plot-width", 336),
          height: num("plot-height", 250),
          scale: 1,
        },
      });
      byId("selection-summary").textContent = `${selected.length} of ${DATA.vehicleIds.length} vehicles selected; ${mode === "percentiles" ? "percentile mode" : "vehicle mode"}`;
    }

    function buildVehicleTraces(selected) {
      const xAxis = byId("x-axis").value;
      const yAxis = byId("y-axis").value;
      const colorBy = byId("color-by").value;
      const discrete = DISCRETE_COLOR_FIELDS.has(colorBy);
      const vehicles = selected.map((id) => vehicleById.get(id)).filter(Boolean);
      const traces = [];
      const seenLegendGroups = new Set();
      let colorMap = new Map();
      let colorMin = 0;
      let colorMax = 1;

      if (discrete) {
        const colorValues = vehicles.map((vehicle) => String(colorBy === "vehicle_id" ? vehicle.vehicle_id : (vehicle[colorBy] || "Unknown")));
        colorMap = discreteColorMap(colorValues);
      } else {
        const values = vehicles.map((vehicle) => finiteNumber(vehicle[colorBy])).filter((value) => value !== null);
        colorMin = values.length ? Math.min(...values) : 0;
        colorMax = values.length ? Math.max(...values) : 1;
      }

      selected.forEach((vehicleId, traceIndex) => {
        const vehicle = vehicleById.get(vehicleId);
        const group = (pointsByVehicle.get(vehicleId) || [])
          .filter((point) => finiteNumber(point[xAxis]) !== null && finiteNumber(point[yAxis]) !== null)
          .sort((a, b) => (Number(a[xAxis]) - Number(b[xAxis])) || (Number(a.point_index) - Number(b.point_index)));
        if (!vehicle || !group.length) return;

        let lineColor;
        let legendName;
        let legendGroup;
        let showLegend;
        if (discrete) {
          const colorValue = String(colorBy === "vehicle_id" ? vehicle.vehicle_id : (vehicle[colorBy] || "Unknown"));
          lineColor = colorMap.get(colorValue) || "#333";
          legendName = colorBy === "vehicle_id" ? vehicle.display_name : colorValue;
          legendGroup = colorBy === "vehicle_id" ? vehicle.display_name : colorValue;
          showLegend = colorBy === "vehicle_id" || !seenLegendGroups.has(legendGroup);
          seenLegendGroups.add(legendGroup);
        } else {
          const value = finiteNumber(vehicle[colorBy]) ?? colorMin;
          lineColor = colorFromScale((value - colorMin) / Math.max(colorMax - colorMin, 1e-9));
          legendName = vehicle.display_name;
          legendGroup = vehicle.display_name;
          showLegend = false;
        }

        traces.push({
          type: "scatter",
          x: group.map((point) => point[xAxis]),
          y: group.map((point) => point[yAxis]),
          mode: num("marker-size", 0) > 0 ? "lines+markers" : "lines",
          name: legendName,
          showlegend: showLegend,
          legendgroup: legendGroup,
          opacity: num("line-opacity", 1),
          line: lineStyle(lineColor, traceIndex),
          marker: {size: num("marker-size", 0), color: lineColor},
          customdata: group.map((point) => [
            point.display_name, point.soc_percent, point.charging_power_kw, point.charging_power_relative_percent,
            point.manufacturer, point.range_total_one_stop_km, point.range_until_stop_km, point.range_added_20min_km,
          ]),
          hovertemplate: "<b>%{customdata[0]}</b><br>Manufacturer: %{customdata[4]}<br>SOC: %{customdata[1]:.1f}%<br>Charging power: %{customdata[2]:.1f} kW<br>Relative power: %{customdata[3]:.1f}%<br>Total range: %{customdata[5]} km<br>Full-battery range: %{customdata[6]} km<br>Range added in 20 min: %{customdata[7]} km<extra></extra>",
        });
      });

      if (!discrete) traces.push(colorbarTrace(colorMin, colorMax, optionLabel(DATA.ui.colorOptions, byId("color-by").value)));
      return traces;
    }

    function buildPercentileTraces(selected) {
      const specs = parsePercentiles(text("percentiles"));
      const legendPercentiles = parsePercentileLegendSelection(text("percentile-legend-entries"), specs);
      const series = buildPercentileSeries(selected, byId("x-axis").value, byId("y-axis").value, specs);
      const display = byId("percentile-display").value;
      const legendMode = byId("percentile-legend-mode").value;
      const traces = [];

      if (display === "heatmap") {
        const grid = buildPercentileHeatmapGrid(specs, series);
        if (grid.x.length && grid.y.length) {
          traces.push({
            type: "heatmap",
            x: grid.x,
            y: grid.y,
            z: grid.z,
            zmin: 0,
            zmax: 100,
            colorscale: "Viridis",
            showscale: legendMode === "colorbar",
            colorbar: colorbarLayout("Percentile [%]"),
            hovertemplate: `${axisLabel(byId("x-axis").value)}: %{x:.2f}<br>${axisLabel(byId("y-axis").value)}: %{y:.2f}<br>Percentile: %{z:.1f}%<extra></extra>`,
          });
        }
      }

      specs.forEach((spec, index) => {
        const curve = series.get(spec.label) || [];
        if (!curve.length) return;
        const showLegend = legendMode === "entries" && legendPercentiles.has(roundKey(spec.value));
        if (display === "heatmap" && !showLegend && spec.value < 100) return;
        const color = display === "heatmap" && spec.value >= 100 ? "black" : colorFromScale(spec.value / 100);
        traces.push({
          type: "scatter",
          x: curve.map((point) => point[0]),
          y: curve.map((point) => point[1]),
          mode: num("marker-size", 0) > 0 ? "lines+markers" : "lines",
          name: spec.label,
          showlegend: showLegend,
          opacity: num("line-opacity", 1),
          line: {...lineStyle(color, index), dash: percentileDash(index)},
          marker: {size: num("marker-size", 0), color},
          customdata: curve.map((point) => [spec.label, selected.length, point[0], point[1]]),
          hovertemplate: `<b>%{customdata[0]}</b><br>Selected vehicles: %{customdata[1]}<br>${axisLabel(byId("x-axis").value)}: %{customdata[2]:.2f}<br>${axisLabel(byId("y-axis").value)}: %{customdata[3]:.2f}<extra></extra>`,
        });
      });

      if (display === "lines" && legendMode === "colorbar") traces.push(colorbarTrace(0, 100, "Percentile [%]"));
      return traces;
    }

    function buildPercentileSeries(selected, xAxis, yAxis, specs) {
      const curves = [];
      selected.forEach((vehicleId) => {
        const points = (pointsByVehicle.get(vehicleId) || [])
          .map((point) => [finiteNumber(point[xAxis]), finiteNumber(point[yAxis])])
          .filter((point) => point[0] !== null && point[1] !== null);
        const curve = collapseDuplicateX(points);
        if (curve.length >= 2) curves.push(curve);
      });
      const result = new Map(specs.map((spec) => [spec.label, []]));
      if (!curves.length) return result;

      for (const xValue of percentileSupportPoints(curves)) {
        const values = curves.map((curve) => interpolateY(curve, xValue)).filter((value) => value !== null);
        if (!values.length) continue;
        specs.forEach((spec) => {
          const yValue = percentile(values, spec.value);
          if (yValue !== null) result.get(spec.label).push([xValue, yValue]);
        });
      }
      return result;
    }

    function buildPercentileHeatmapGrid(specs, series) {
      const nonEmpty = Array.from(series.values()).filter((curve) => curve.length);
      if (!nonEmpty.length) return {x: [], y: [], z: []};
      const x = nonEmpty[0].map((point) => point[0]);
      const allY = nonEmpty.flatMap((curve) => curve.map((point) => point[1]));
      const yMin = Math.min(...allY);
      const yMax = Math.max(...allY);
      const yBottom = yMin >= 0 ? 0 : yMin;
      const steps = 120;
      const y = Array.from({length: steps}, (_, index) => yBottom + (yMax - yBottom) * index / Math.max(steps - 1, 1));
      const lookup = new Map(specs.map((spec) => [spec.label, new Map((series.get(spec.label) || []).map((point) => [roundKey(point[0]), point[1]]))]));
      const z = y.map((yValue) => x.map((xValue) => {
        const pairs = specs
          .map((spec) => [spec.value, lookup.get(spec.label).get(roundKey(xValue))])
          .filter((pair) => pair[1] !== undefined);
        if (!pairs.length) return null;
        const topY = Math.max(...pairs.map((pair) => pair[1]));
        const worstY = Math.min(...pairs.map((pair) => pair[1]));
        if (yValue > topY || yValue < worstY) return null;
        return inversePercentileForY(pairs, yValue);
      }));
      return {x, y, z};
    }

    function parsePercentiles(input) {
      const raw = (input || "").trim();
      const tokens = raw ? raw.split(/[,;\s]+/).filter(Boolean) : DATA.ui.defaultPercentiles.split(/[,;\s]+/).filter(Boolean);
      const seen = new Set();
      const specs = [];
      tokens.forEach((token) => {
        const normalized = token.toLowerCase().replace("%", "");
        let value = null;
        if (["worst", "min", "minimum"].includes(normalized)) value = 0;
        else if (["top", "max", "maximum"].includes(normalized)) value = 100;
        else {
          const parsed = Number(normalized.replace(",", "."));
          if (Number.isFinite(parsed)) value = clamp(parsed, 0, 100);
        }
        if (value === null) return;
        const key = roundKey(value);
        if (seen.has(key)) return;
        seen.add(key);
        specs.push({label: formatPercentileLabel(value), value});
      });
      return specs.length ? specs : parsePercentiles(DATA.ui.defaultPercentiles);
    }

    function parsePercentileLegendSelection(input, specs) {
      const raw = (input || "").trim().toLowerCase();
      if (raw === "all") return new Set(specs.map((spec) => roundKey(spec.value)));
      if (raw === "none") return new Set();
      const available = new Set(specs.map((spec) => roundKey(spec.value)));
      return new Set(parsePercentiles(raw || DATA.ui.defaultPercentileLegendEntries)
        .map((spec) => roundKey(spec.value))
        .filter((value) => available.has(value)));
    }

    function formatPercentileLabel(value) {
      if (value <= 0) return "Worst";
      if (value >= 100) return "Top";
      return `${Math.abs(value - Math.round(value)) < 1e-9 ? Math.round(value) : value}% Percentile`;
    }

    function percentile(values, percent) {
      if (!values.length) return null;
      const ordered = [...values].sort((a, b) => a - b);
      if (percent <= 0) return ordered[0];
      if (percent >= 100) return ordered[ordered.length - 1];
      const position = (ordered.length - 1) * percent / 100;
      const low = Math.floor(position);
      const high = Math.ceil(position);
      if (low === high) return ordered[low];
      return ordered[low] + (ordered[high] - ordered[low]) * (position - low);
    }

    function collapseDuplicateX(points) {
      const grouped = new Map();
      points.forEach((point) => {
        const key = roundKey(point[0]);
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(point[1]);
      });
      return Array.from(grouped.entries())
        .map(([x, values]) => [Number(x), values.reduce((sum, value) => sum + value, 0) / values.length])
        .sort((a, b) => a[0] - b[0]);
    }

    function interpolateY(curve, xValue) {
      if (!curve.length || xValue < curve[0][0] || xValue > curve[curve.length - 1][0]) return null;
      for (let index = 0; index < curve.length; index += 1) {
        const [currentX, currentY] = curve[index];
        if (Math.abs(currentX - xValue) < 1e-9) return currentY;
        if (currentX > xValue && index > 0) {
          const [previousX, previousY] = curve[index - 1];
          const fraction = (xValue - previousX) / Math.max(currentX - previousX, 1e-9);
          return previousY + (currentY - previousY) * fraction;
        }
      }
      return null;
    }

    function percentileSupportPoints(curves) {
      const unique = Array.from(new Set(curves.flatMap((curve) => curve.map((point) => roundKey(point[0]))))).map(Number).sort((a, b) => a - b);
      if (unique.length <= 80) return unique;
      const minX = Math.min(...curves.map((curve) => curve[0][0]));
      const maxX = Math.max(...curves.map((curve) => curve[curve.length - 1][0]));
      return Array.from({length: 51}, (_, index) => minX + (maxX - minX) * index / 50);
    }

    function inversePercentileForY(pairs, yValue) {
      const ordered = [...pairs].sort((a, b) => a[1] - b[1]);
      if (yValue <= ordered[0][1]) return ordered[0][0];
      if (yValue >= ordered[ordered.length - 1][1]) return ordered[ordered.length - 1][0];
      for (let index = 1; index < ordered.length; index += 1) {
        const [lowPercent, lowY] = ordered[index - 1];
        const [highPercent, highY] = ordered[index];
        if (lowY <= yValue && yValue <= highY) {
          if (Math.abs(highY - lowY) < 1e-9) return Math.max(lowPercent, highPercent);
          return lowPercent + (highPercent - lowPercent) * (yValue - lowY) / (highY - lowY);
        }
      }
      return null;
    }

    function lineStyle(color, index) {
      const cycleDash = byId("cycle-line-dash")?.checked ?? true;
      return {
        width: num("line-width", 1.4),
        color,
        shape: byId("line-shape").value,
        dash: cycleDash ? DASH_PATTERNS[index % DASH_PATTERNS.length] : "solid",
      };
    }

    function percentileDash(index) {
      const mode = byId("percentile-dash").value;
      if (mode === "cycle") return (byId("cycle-line-dash")?.checked ?? true) ? DASH_PATTERNS[index % DASH_PATTERNS.length] : "solid";
      return DASH_PATTERNS.includes(mode) ? mode : "solid";
    }

    function axisLayout(selectId, titleSize, tickSize, nticks) {
      return {
        title: {text: axisLabel(byId(selectId).value), font: {size: titleSize}},
        tickfont: {size: tickSize},
        showgrid: true,
        gridcolor: "rgba(0,0,0,0.15)",
        gridwidth: 0.5,
        showline: true,
        linecolor: "black",
        linewidth: 1,
        mirror: true,
        ticks: "outside",
        ticklen: 3,
        tickwidth: 1,
        zeroline: false,
        nticks,
      };
    }

    function plotTitle(showTitle, title) {
      if (!showTitle) return null;
      return {text: `<b>${escapeHtml(title)}</b>`, x: 0.5, xanchor: "center"};
    }

    function legendLayout(position, fontSize, traceorder = "normal") {
      const base = {font: {size: fontSize}, bgcolor: "rgba(255,255,255,0)", borderwidth: 0, traceorder};
      if (position === "bottom") return {...base, orientation: "h", yanchor: "top", y: -0.28, xanchor: "left", x: 0};
      if (position === "right") return {...base, orientation: "v", yanchor: "top", y: 1, xanchor: "left", x: 1.02};
      if (position === "inside_top_right") return {...base, orientation: "v", yanchor: "top", y: 0.98, xanchor: "right", x: 0.98, bgcolor: "rgba(255,255,255,0.75)"};
      if (position === "inside_bottom_left") return {...base, orientation: "v", yanchor: "bottom", y: 0.02, xanchor: "left", x: 0.02, bgcolor: "rgba(255,255,255,0.75)"};
      if (position === "inside_bottom_right") return {...base, orientation: "v", yanchor: "bottom", y: 0.02, xanchor: "right", x: 0.98, bgcolor: "rgba(255,255,255,0.75)"};
      return {...base, orientation: "h", yanchor: "bottom", y: 1.08, xanchor: "left", x: 0};
    }

    function layoutMargins(position, showTitle) {
      return {l: 50, r: position === "right" ? 70 : 8, t: showTitle ? 42 : 8, b: position === "bottom" ? 70 : 42};
    }

    function colorbarLayout(title) {
      return {title: {text: title, font: {size: num("legend-font-size", 11)}}, tickfont: {size: num("tick-font-size", 11)}};
    }

    function colorbarTrace(minValue, maxValue, title) {
      return {
        type: "scatter",
        x: [null],
        y: [null],
        mode: "markers",
        marker: {colorscale: "Viridis", cmin: minValue, cmax: maxValue, color: [minValue, maxValue], showscale: true, colorbar: colorbarLayout(title)},
        hoverinfo: "skip",
        showlegend: false,
      };
    }

    function discreteColorMap(values) {
      const unique = Array.from(new Set(values));
      return new Map(unique.map((value, index) => [value, PLOTLY_PALETTE[index % PLOTLY_PALETTE.length]]));
    }

    function colorFromScale(value) {
      const t = clamp(Number.isFinite(value) ? value : 0.5, 0, 1);
      for (let index = 1; index < VIRIDIS.length; index += 1) {
        const [stop, rgb] = VIRIDIS[index];
        const [previousStop, previousRgb] = VIRIDIS[index - 1];
        if (t <= stop) {
          const fraction = (t - previousStop) / Math.max(stop - previousStop, 1e-9);
          const mixed = rgb.map((channel, channelIndex) => Math.round(previousRgb[channelIndex] + (channel - previousRgb[channelIndex]) * fraction));
          return `rgb(${mixed[0]},${mixed[1]},${mixed[2]})`;
        }
      }
      return "rgb(253,231,37)";
    }

    function optionLabel(options, value) {
      return options.find((option) => option.value === value)?.label || value;
    }

    function axisLabel(value) {
      return optionLabel(DATA.ui.axisOptions, value);
    }

    function roundKey(value) {
      return String(Math.round(Number(value) * 1e9) / 1e9);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
  </script>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adac-ev-curves-static-site")
    parser.add_argument("--data", default="output", help="Directory containing extracted CSV files.")
    parser.add_argument("--out", default="site", help="Output directory for the static GitHub Pages site.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_static_site(args.data, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
