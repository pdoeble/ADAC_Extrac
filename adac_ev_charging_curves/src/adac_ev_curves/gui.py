from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.colors import qualitative, sample_colorscale


AXIS_OPTIONS = [
    {"label": "State of charge [%]", "value": "soc_percent"},
    {"label": "Charging power [kW]", "value": "charging_power_kw"},
    {"label": "Relative charging power [%]", "value": "charging_power_relative_percent"},
    {"label": "Point index", "value": "point_index"},
    {"label": "Transformed SVG x coordinate [px]", "value": "svg_x_transformed"},
    {"label": "Transformed SVG y coordinate [px]", "value": "svg_y_transformed"},
]

AXIS_LABELS = {item["value"]: item["label"] for item in AXIS_OPTIONS}

PLOT_MODE_OPTIONS = [
    {"label": "Vehicles", "value": "vehicles"},
    {"label": "Percentiles", "value": "percentiles"},
]

DEFAULT_PERCENTILES = [("Worst", 0.0), *[(f"P{value}", float(value)) for value in range(5, 100, 5)], ("Top", 100.0)]
DEFAULT_PERCENTILES_TEXT = ", ".join(label if label in {"Worst", "Top"} else label[1:] for label, _ in DEFAULT_PERCENTILES)
DEFAULT_PERCENTILE_LEGEND_TEXT = "Worst, 25, 50, 75, Top"

PERCENTILE_DISPLAY_OPTIONS = [
    {"label": "Lines", "value": "lines"},
    {"label": "Interpolated color field", "value": "heatmap"},
]

PERCENTILE_LEGEND_MODE_OPTIONS = [
    {"label": "Legend entries", "value": "entries"},
    {"label": "Colorbar", "value": "colorbar"},
    {"label": "None", "value": "none"},
]

PERCENTILE_DASH_OPTIONS = [
    {"label": "Cycle line styles", "value": "cycle"},
    {"label": "Solid", "value": "solid"},
    {"label": "Dash", "value": "dash"},
    {"label": "Dot", "value": "dot"},
    {"label": "Dash-dot", "value": "dashdot"},
]

LEGEND_POSITION_OPTIONS = [
    {"label": "Top", "value": "top"},
    {"label": "Bottom", "value": "bottom"},
    {"label": "Right", "value": "right"},
    {"label": "Inside top right", "value": "inside_top_right"},
    {"label": "Inside bottom right", "value": "inside_bottom_right"},
]

COLOR_OPTIONS = [
    {"label": "Vehicle (discrete)", "value": "vehicle_id"},
    {"label": "Brand / manufacturer (discrete)", "value": "manufacturer"},
    {"label": "Observed max charging power (continuous)", "value": "max_observed_charging_power_kw"},
    {"label": "Observed mean charging power (continuous)", "value": "mean_observed_charging_power_kw"},
    {"label": "Total range (continuous)", "value": "range_total_one_stop_km"},
    {"label": "Full-battery range (continuous)", "value": "range_until_stop_km"},
    {"label": "Range added in 20 min (continuous)", "value": "range_added_20min_km"},
    {"label": "ADAC table rank (continuous)", "value": "rank"},
]

DISCRETE_COLOR_FIELDS = {"vehicle_id", "manufacturer"}
COLOR_LABELS = {item["value"]: item["label"] for item in COLOR_OPTIONS}

TABLE_COLUMNS = [
    {"name": "Rank", "id": "rank", "type": "numeric"},
    {"name": "Vehicle", "id": "display_name"},
    {"name": "Manufacturer", "id": "manufacturer"},
    {"name": "Total range", "id": "range_total_one_stop_km", "type": "numeric"},
    {"name": "Full-battery range", "id": "range_until_stop_km", "type": "numeric"},
    {"name": "Range added in 20 min", "id": "range_added_20min_km", "type": "numeric"},
    {"name": "Observed max kW", "id": "max_observed_charging_power_kw", "type": "numeric"},
]

NUMERIC_VEHICLE_COLUMNS = {
    "row_index",
    "rank",
    "range_until_stop_km",
    "range_added_20min_km",
    "range_total_one_stop_km",
    "battery_capacity_kwh",
    "consumption_kwh_per_100km",
    "max_charging_power_kw",
}

NUMERIC_POINT_COLUMNS = {
    "point_index",
    "soc_percent",
    "charging_power_kw",
    "svg_cx",
    "svg_cy",
    "svg_x_transformed",
    "svg_y_transformed",
}


@dataclass
class GuiDataset:
    vehicles: list[dict[str, Any]]
    points: list[dict[str, Any]]
    vehicle_records: list[dict[str, Any]]
    vehicle_ids: list[str]


@dataclass
class PlotStyle:
    font_family: str = "Times New Roman"
    title_text: str | None = None
    line_width: float = 1.4
    marker_size: float = 0.0
    opacity: float = 1.0
    plot_width: int = 336
    plot_height: int = 250
    font_size: int = 11
    title_font_size: int = 12
    axis_title_font_size: int = 12
    tick_font_size: int = 11
    legend_font_size: int = 11
    legend_position: str = "top"
    line_shape: str = "linear"
    show_title: bool = False
    cycle_line_dash: bool = True


DASH_PATTERNS = ["solid", "dash", "dot", "dashdot"]


LINE_SHAPE_OPTIONS = [
    {"label": "linear", "value": "linear"},
    {"label": "smoothed", "value": "spline"},
    {"label": "step hv", "value": "hv"},
    {"label": "step vh", "value": "vh"},
]


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    number = _to_float(value)
    if number is None:
        return default
    return max(minimum, min(maximum, float(number)))


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    number = _to_float(value)
    if number is None:
        return default
    return max(minimum, min(maximum, int(round(number))))


def make_plot_style(
    font_family: str | None = None,
    title_text: str | None = None,
    line_width: Any = None,
    marker_size: Any = None,
    opacity: Any = None,
    plot_width: Any = None,
    plot_height: Any = None,
    font_size: Any = None,
    title_font_size: Any = None,
    axis_title_font_size: Any = None,
    tick_font_size: Any = None,
    legend_font_size: Any = None,
    legend_position: str | None = None,
    line_shape: str | None = None,
    show_title: bool | None = None,
    cycle_line_dash: bool | None = None,
) -> PlotStyle:
    family = (font_family or "Times New Roman").strip() or "Times New Roman"
    title = title_text.strip() if isinstance(title_text, str) else None
    legend_positions = {item["value"] for item in LEGEND_POSITION_OPTIONS}
    return PlotStyle(
        font_family=family,
        title_text=title or None,
        line_width=_clamp_float(line_width, 1.4, 0.2, 12.0),
        marker_size=_clamp_float(marker_size, 0.0, 0.0, 20.0),
        opacity=_clamp_float(opacity, 1.0, 0.05, 1.0),
        plot_width=_clamp_int(plot_width, 336, 250, 4000),
        plot_height=_clamp_int(plot_height, 250, 180, 3000),
        font_size=_clamp_int(font_size, 11, 8, 40),
        title_font_size=_clamp_int(title_font_size, 12, 10, 60),
        axis_title_font_size=_clamp_int(axis_title_font_size, 12, 8, 44),
        tick_font_size=_clamp_int(tick_font_size, 11, 6, 36),
        legend_font_size=_clamp_int(legend_font_size, 11, 6, 36),
        legend_position=legend_position if legend_position in legend_positions else "top",
        line_shape=line_shape if line_shape in {item["value"] for item in LINE_SHAPE_OPTIONS} else "linear",
        show_title=bool(show_title),
        cycle_line_dash=True if cycle_line_dash is None else bool(cycle_line_dash),
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.+-]", "", text)
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _to_intish(value: Any) -> int | float | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(round(number)) if abs(number - round(number)) < 1e-9 else round(number, 3)


def _numeric_or_zero(value: Any) -> float:
    number = _to_float(value)
    return number if number is not None else 0.0


def _convert_numeric_fields(row: dict[str, Any], numeric_columns: set[str]) -> dict[str, Any]:
    converted = dict(row)
    for column in numeric_columns:
        if column in converted:
            converted[column] = _to_float(converted[column])
    return converted


def _round_or_none(value: Any, digits: int = 1) -> float | None:
    number = _to_float(value)
    return round(number, digits) if number is not None else None


def load_dataset(data_dir: str | Path) -> GuiDataset:
    data_path = Path(data_dir)
    vehicles = [_convert_numeric_fields(row, NUMERIC_VEHICLE_COLUMNS) for row in _read_csv(data_path / "vehicles.csv")]
    points = [_convert_numeric_fields(row, NUMERIC_POINT_COLUMNS) for row in _read_csv(data_path / "charging_curve_points.csv")]

    powers_by_vehicle: dict[str, list[float]] = defaultdict(list)
    for point in points:
        power = _to_float(point.get("charging_power_kw"))
        if power is not None:
            powers_by_vehicle[str(point.get("vehicle_id"))].append(power)

    for vehicle in vehicles:
        vehicle_id = str(vehicle.get("vehicle_id"))
        powers = powers_by_vehicle.get(vehicle_id, [])
        vehicle["manufacturer"] = vehicle.get("manufacturer") or "Unknown"
        vehicle["max_observed_charging_power_kw"] = max(powers) if powers else None
        vehicle["mean_observed_charging_power_kw"] = sum(powers) / len(powers) if powers else None

    vehicles_by_id = {str(vehicle.get("vehicle_id")): vehicle for vehicle in vehicles}
    for point in points:
        vehicle_id = str(point.get("vehicle_id"))
        max_power = vehicles_by_id.get(vehicle_id, {}).get("max_observed_charging_power_kw")
        power = _to_float(point.get("charging_power_kw"))
        point["charging_power_relative_percent"] = (
            round(power / max_power * 100, 6) if power is not None and max_power else None
        )
        vehicle = vehicles_by_id.get(vehicle_id, {})
        for column in [
            "manufacturer",
            "rank",
            "range_until_stop_km",
            "range_added_20min_km",
            "range_total_one_stop_km",
            "max_observed_charging_power_kw",
            "mean_observed_charging_power_kw",
        ]:
            point[column] = vehicle.get(column)

    sorted_vehicles = sorted(
        vehicles,
        key=lambda row: (
            _numeric_or_zero(row.get("rank")) if row.get("rank") is not None else 10_000,
            str(row.get("display_name") or ""),
        ),
    )
    vehicle_records: list[dict[str, Any]] = []
    for vehicle in sorted_vehicles:
        record = {
            "id": vehicle.get("vehicle_id"),
            "vehicle_id": vehicle.get("vehicle_id"),
            "display_name": vehicle.get("display_name"),
            "manufacturer": vehicle.get("manufacturer"),
            "rank": _to_intish(vehicle.get("rank")),
            "range_total_one_stop_km": _to_intish(vehicle.get("range_total_one_stop_km")),
            "range_until_stop_km": _to_intish(vehicle.get("range_until_stop_km")),
            "range_added_20min_km": _to_intish(vehicle.get("range_added_20min_km")),
            "max_observed_charging_power_kw": _round_or_none(vehicle.get("max_observed_charging_power_kw"), 1),
        }
        vehicle_records.append(record)

    return GuiDataset(
        vehicles=vehicles,
        points=points,
        vehicle_records=vehicle_records,
        vehicle_ids=[str(vehicle.get("vehicle_id")) for vehicle in sorted_vehicles],
    )


def _continuous_color(value: float, min_value: float, max_value: float, colorscale: str = "Viridis") -> str:
    if max_value <= min_value:
        return sample_colorscale(colorscale, 0.5)[0]
    normalized = (value - min_value) / (max_value - min_value)
    normalized = max(0.0, min(1.0, normalized))
    return sample_colorscale(colorscale, normalized)[0]


def _discrete_color_map(values: list[str]) -> dict[str, str]:
    palette = qualitative.Plotly + qualitative.Dark24 + qualitative.Light24
    unique_values = list(dict.fromkeys(values))
    return {value: palette[index % len(palette)] for index, value in enumerate(unique_values)}


def _sort_key(row: dict[str, Any], column: str) -> tuple[bool, float]:
    value = _to_float(row.get(column))
    return value is None, value if value is not None else 0.0


def _vehicle_lookup(vehicles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(vehicle.get("vehicle_id")): vehicle for vehicle in vehicles}


def _format_percentile_label(percentile: float) -> str:
    if percentile <= 0:
        return "Worst"
    if percentile >= 100:
        return "Top"
    if abs(percentile - round(percentile)) < 1e-9:
        return f"{int(round(percentile))}% Percentile"
    return f"{percentile:g}% Percentile"


def parse_percentiles(value: str | None) -> list[tuple[str, float]]:
    text = (value or "").strip()
    if not text:
        return [(_format_percentile_label(percentile), percentile) for _, percentile in DEFAULT_PERCENTILES]

    parsed: list[tuple[str, float]] = []
    seen: set[float] = set()
    tokens = [token.strip() for token in re.split(r"[,;\s]+", text) if token.strip()]
    for token in tokens:
        normalized = token.lower().replace("%", "")
        if normalized in {"worst", "min", "minimum"}:
            percentile = 0.0
        elif normalized in {"top", "max", "maximum"}:
            percentile = 100.0
        else:
            percentile = _to_float(normalized)
            if percentile is None:
                continue
            percentile = max(0.0, min(100.0, percentile))

        key = round(percentile, 9)
        if key in seen:
            continue
        seen.add(key)
        parsed.append((_format_percentile_label(percentile), percentile))

    return parsed or [(_format_percentile_label(percentile), percentile) for _, percentile in DEFAULT_PERCENTILES]


def parse_percentile_legend_selection(
    value: str | None,
    percentile_specs: list[tuple[str, float]],
) -> set[float]:
    text = (value or "").strip()
    if text.lower() == "all":
        return {round(percentile, 9) for _, percentile in percentile_specs}
    if text.lower() == "none":
        return set()
    specs = parse_percentiles(text or DEFAULT_PERCENTILE_LEGEND_TEXT)
    available = {round(percentile, 9) for _, percentile in percentile_specs}
    return {round(percentile, 9) for _, percentile in specs if round(percentile, 9) in available}


def _percentile_dash(index: int, dash_mode: str | None, style: PlotStyle) -> str:
    if dash_mode == "cycle":
        return DASH_PATTERNS[index % len(DASH_PATTERNS)] if style.cycle_line_dash else "solid"
    if dash_mode in set(DASH_PATTERNS):
        return dash_mode
    return DASH_PATTERNS[index % len(DASH_PATTERNS)] if style.cycle_line_dash else "solid"


def _legend_layout(style: PlotStyle) -> dict[str, Any]:
    base = {
        "font": {"size": style.legend_font_size},
        "bgcolor": "rgba(255,255,255,0)",
        "borderwidth": 0,
    }
    if style.legend_position == "bottom":
        return {
            **base,
            "orientation": "h",
            "yanchor": "top",
            "y": -0.28,
            "xanchor": "left",
            "x": 0,
        }
    if style.legend_position == "right":
        return {
            **base,
            "orientation": "v",
            "yanchor": "top",
            "y": 1,
            "xanchor": "left",
            "x": 1.02,
        }
    if style.legend_position == "inside_top_right":
        return {
            **base,
            "orientation": "v",
            "yanchor": "top",
            "y": 0.98,
            "xanchor": "right",
            "x": 0.98,
            "bgcolor": "rgba(255,255,255,0.75)",
        }
    if style.legend_position == "inside_bottom_right":
        return {
            **base,
            "orientation": "v",
            "yanchor": "bottom",
            "y": 0.02,
            "xanchor": "right",
            "x": 0.98,
            "bgcolor": "rgba(255,255,255,0.75)",
        }
    return {
        **base,
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.08,
        "xanchor": "left",
        "x": 0,
    }


def _layout_margins(style: PlotStyle) -> dict[str, int]:
    return {
        "l": 50,
        "r": 70 if style.legend_position == "right" else 8,
        "t": 42 if style.show_title else 8,
        "b": 70 if style.legend_position == "bottom" else 42,
    }


def _layout_title(style: PlotStyle, default_title: str) -> str | None:
    if not style.show_title:
        return None
    return style.title_text or default_title


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if percentile <= 0:
        return ordered[0]
    if percentile >= 100:
        return ordered[-1]
    position = (len(ordered) - 1) * percentile / 100
    low_index = int(math.floor(position))
    high_index = int(math.ceil(position))
    if low_index == high_index:
        return ordered[low_index]
    fraction = position - low_index
    return ordered[low_index] + (ordered[high_index] - ordered[low_index]) * fraction


def _collapse_duplicate_x(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    values_by_x: dict[float, list[float]] = defaultdict(list)
    for x_value, y_value in points:
        values_by_x[x_value].append(y_value)
    return sorted(
        (x_value, sum(y_values) / len(y_values))
        for x_value, y_values in values_by_x.items()
        if y_values
    )


def _interpolate_y(curve: list[tuple[float, float]], x_value: float) -> float | None:
    if not curve:
        return None
    if x_value < curve[0][0] or x_value > curve[-1][0]:
        return None
    for index, (current_x, current_y) in enumerate(curve):
        if abs(current_x - x_value) < 1e-9:
            return current_y
        if current_x > x_value and index > 0:
            previous_x, previous_y = curve[index - 1]
            if abs(current_x - previous_x) < 1e-9:
                return current_y
            fraction = (x_value - previous_x) / (current_x - previous_x)
            return previous_y + (current_y - previous_y) * fraction
    return None


def _percentile_support_points(curves: list[list[tuple[float, float]]]) -> list[float]:
    unique_x = sorted({x_value for curve in curves for x_value, _ in curve})
    if len(unique_x) <= 80:
        return unique_x

    min_x = min(curve[0][0] for curve in curves if curve)
    max_x = max(curve[-1][0] for curve in curves if curve)
    if max_x <= min_x:
        return [min_x]
    steps = 50
    return [min_x + (max_x - min_x) * index / steps for index in range(steps + 1)]


def build_percentile_series(
    dataset: GuiDataset,
    selected_vehicle_ids: list[str],
    x_axis: str,
    y_axis: str,
    percentile_specs: list[tuple[str, float]],
) -> dict[str, list[tuple[float, float]]]:
    selected_set = set(selected_vehicle_ids)
    grouped_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for point in dataset.points:
        vehicle_id = str(point.get("vehicle_id"))
        if vehicle_id not in selected_set:
            continue
        x_value = _to_float(point.get(x_axis))
        y_value = _to_float(point.get(y_axis))
        if x_value is None or y_value is None:
            continue
        grouped_points[vehicle_id].append((x_value, y_value))

    curves = [_collapse_duplicate_x(points) for points in grouped_points.values()]
    curves = [curve for curve in curves if len(curve) >= 2]
    if not curves:
        return {label: [] for label, _ in percentile_specs}

    support_points = _percentile_support_points(curves)
    series = {label: [] for label, _ in percentile_specs}
    for x_value in support_points:
        y_values = [
            interpolated
            for curve in curves
            if (interpolated := _interpolate_y(curve, x_value)) is not None
        ]
        if not y_values:
            continue
        for label, percentile in percentile_specs:
            percentile_y = _percentile(y_values, percentile)
            if percentile_y is not None:
                series[label].append((x_value, percentile_y))
    return series


def _inverse_percentile_for_y(percentile_y_pairs: list[tuple[float, float]], y_value: float) -> float | None:
    if not percentile_y_pairs:
        return None
    ordered = sorted(percentile_y_pairs, key=lambda item: item[1])
    if y_value <= ordered[0][1]:
        return ordered[0][0]
    if y_value >= ordered[-1][1]:
        return ordered[-1][0]
    for index in range(1, len(ordered)):
        low_percentile, low_y = ordered[index - 1]
        high_percentile, high_y = ordered[index]
        if low_y <= y_value <= high_y:
            if abs(high_y - low_y) < 1e-9:
                return max(low_percentile, high_percentile)
            fraction = (y_value - low_y) / (high_y - low_y)
            return low_percentile + (high_percentile - low_percentile) * fraction
    return None


def build_percentile_heatmap_grid(
    percentile_specs: list[tuple[str, float]],
    percentile_series: dict[str, list[tuple[float, float]]],
    y_steps: int = 120,
) -> tuple[list[float], list[float], list[list[float | None]]]:
    non_empty = [series for series in percentile_series.values() if series]
    if not non_empty:
        return [], [], []

    x_values = [x_value for x_value, _ in non_empty[0]]
    all_y_values = [y_value for series in non_empty for _, y_value in series]
    if not x_values or not all_y_values:
        return [], [], []

    y_min = min(all_y_values)
    y_max = max(all_y_values)
    y_bottom = 0.0 if y_min >= 0 else y_min
    if y_max <= y_bottom:
        y_values = [y_bottom]
    else:
        y_values = [y_bottom + (y_max - y_bottom) * index / max(y_steps - 1, 1) for index in range(y_steps)]

    y_by_label_and_x = {
        label: {round(x_value, 9): y_value for x_value, y_value in percentile_series.get(label, [])}
        for label, _ in percentile_specs
    }
    z_values: list[list[float | None]] = []
    for y_value in y_values:
        z_row: list[float | None] = []
        for x_value in x_values:
            x_key = round(x_value, 9)
            pairs = [
                (percentile, label_lookup[x_key])
                for label, percentile in percentile_specs
                if (label_lookup := y_by_label_and_x.get(label)) and x_key in label_lookup
            ]
            if not pairs:
                z_row.append(None)
                continue
            top_y = max(y_at_percentile for _, y_at_percentile in pairs)
            if y_value > top_y:
                z_row.append(None)
                continue
            z_row.append(_inverse_percentile_for_y(pairs, y_value))
        z_values.append(z_row)

    return x_values, y_values, z_values


def build_figure(
    dataset: GuiDataset,
    selected_vehicle_ids: list[str] | None,
    x_axis: str,
    y_axis: str,
    color_by: str,
    style: PlotStyle | None = None,
    plot_mode: str = "vehicles",
    percentile_text: str | None = DEFAULT_PERCENTILES_TEXT,
    percentile_legend_text: str | None = DEFAULT_PERCENTILE_LEGEND_TEXT,
    percentile_display: str = "lines",
    percentile_legend_mode: str = "entries",
    percentile_dash: str = "cycle",
) -> go.Figure:
    style = style or PlotStyle()
    selected = dataset.vehicle_ids[:10] if selected_vehicle_ids is None else selected_vehicle_ids
    selected_set = set(selected)
    points = [point for point in dataset.points if str(point.get("vehicle_id")) in selected_set]
    vehicles = [vehicle for vehicle in dataset.vehicles if str(vehicle.get("vehicle_id")) in selected_set]

    fig = go.Figure()
    if not points:
        fig.update_layout(
            title=_layout_title(style, "No vehicles selected"),
            xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
            yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
            template="plotly_white",
            width=style.plot_width,
            height=style.plot_height,
            font={"family": style.font_family, "size": style.font_size, "color": "black"},
            title_font={"size": style.title_font_size},
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=_layout_margins(style),
        )
        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.15)",
            gridwidth=0.5,
            showline=True,
            linecolor="black",
            linewidth=1,
            mirror=True,
            ticks="outside",
            ticklen=3,
            tickwidth=1,
            zeroline=False,
            nticks=6,
            title_font={"size": style.axis_title_font_size},
            tickfont={"size": style.tick_font_size},
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.15)",
            gridwidth=0.5,
            showline=True,
            linecolor="black",
            linewidth=1,
            mirror=True,
            ticks="outside",
            ticklen=3,
            tickwidth=1,
            zeroline=False,
            nticks=5,
            title_font={"size": style.axis_title_font_size},
            tickfont={"size": style.tick_font_size},
        )
        return fig

    if plot_mode == "percentiles":
        percentile_specs = parse_percentiles(percentile_text)
        legend_percentiles = parse_percentile_legend_selection(percentile_legend_text, percentile_specs)
        percentile_series = build_percentile_series(dataset, selected, x_axis, y_axis, percentile_specs)
        percentile_display = percentile_display if percentile_display in {"lines", "heatmap"} else "lines"
        percentile_legend_mode = percentile_legend_mode if percentile_legend_mode in {"entries", "colorbar", "none"} else "entries"
        palette = sample_colorscale(
            "Viridis",
            [percentile / 100 for _, percentile in percentile_specs],
        )

        if percentile_display == "heatmap":
            heatmap_x, heatmap_y, heatmap_z = build_percentile_heatmap_grid(percentile_specs, percentile_series)
            if heatmap_x and heatmap_y and heatmap_z:
                fig.add_trace(
                    go.Heatmap(
                        x=heatmap_x,
                        y=heatmap_y,
                        z=heatmap_z,
                        zmin=0,
                        zmax=100,
                        colorscale="Viridis",
                        showscale=percentile_legend_mode == "colorbar",
                        colorbar={
                            "title": {
                                "text": "Percentile [%]",
                                "font": {"size": style.legend_font_size},
                            },
                            "tickfont": {"size": style.tick_font_size},
                        },
                        hovertemplate=(
                            f"{AXIS_LABELS.get(x_axis, x_axis)}: "
                            "%{x:.2f}<br>"
                            f"{AXIS_LABELS.get(y_axis, y_axis)}: "
                            "%{y:.2f}<br>"
                            "Percentile: %{z:.1f}%"
                            "<extra></extra>"
                        ),
                    )
                )

        for trace_index, (label, percentile) in enumerate(percentile_specs):
            series = percentile_series.get(label, [])
            if not series:
                continue
            show_trace_legend = (
                percentile_legend_mode == "entries" and round(percentile, 9) in legend_percentiles
            )
            line_color = palette[trace_index]
            if percentile_display == "heatmap" and not show_trace_legend:
                if percentile < 100:
                    continue
                line_color = "black"
            fig.add_trace(
                go.Scatter(
                    x=[x_value for x_value, _ in series],
                    y=[y_value for _, y_value in series],
                    mode="lines+markers" if style.marker_size > 0 else "lines",
                    name=label,
                    showlegend=show_trace_legend,
                    opacity=style.opacity,
                    line={
                        "width": style.line_width,
                        "color": line_color,
                        "shape": style.line_shape,
                        "dash": _percentile_dash(trace_index, percentile_dash, style),
                    },
                    marker={"size": style.marker_size, "color": line_color},
                    customdata=[[label, len(selected), x_value, y_value] for x_value, y_value in series],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Selected vehicles: %{customdata[1]}<br>"
                        f"{AXIS_LABELS.get(x_axis, x_axis)}: "
                        "%{customdata[2]:.2f}<br>"
                        f"{AXIS_LABELS.get(y_axis, y_axis)}: "
                        "%{customdata[3]:.2f}"
                        "<extra></extra>"
                    ),
                )
            )

        if percentile_display == "lines" and percentile_legend_mode == "colorbar":
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker={
                        "colorscale": "Viridis",
                        "cmin": 0,
                        "cmax": 100,
                        "color": [0, 100],
                        "showscale": True,
                        "colorbar": {
                            "title": {
                                "text": "Percentile [%]",
                                "font": {"size": style.legend_font_size},
                            },
                            "tickfont": {"size": style.tick_font_size},
                        },
                    },
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        fig.update_layout(
            title=_layout_title(style, f"ADAC/Infogram charging curve percentiles - {len(selected)} vehicle(s)"),
            xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
            yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
            template="plotly_white",
            width=style.plot_width,
            height=style.plot_height,
            font={"family": style.font_family, "size": style.font_size, "color": "black"},
            title_font={"size": style.title_font_size},
            paper_bgcolor="white",
            plot_bgcolor="white",
            hovermode="closest",
            showlegend=percentile_legend_mode == "entries",
            legend=_legend_layout(style),
            margin=_layout_margins(style),
        )
        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.15)",
            gridwidth=0.5,
            showline=True,
            linecolor="black",
            linewidth=1,
            mirror=True,
            ticks="outside",
            ticklen=3,
            tickwidth=1,
            zeroline=False,
            nticks=6,
            title_font={"size": style.axis_title_font_size},
            tickfont={"size": style.tick_font_size},
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.15)",
            gridwidth=0.5,
            showline=True,
            linecolor="black",
            linewidth=1,
            mirror=True,
            ticks="outside",
            ticklen=3,
            tickwidth=1,
            zeroline=False,
            nticks=5,
            title_font={"size": style.axis_title_font_size},
            tickfont={"size": style.tick_font_size},
        )
        return fig

    discrete = color_by in DISCRETE_COLOR_FIELDS
    if discrete:
        if color_by == "vehicle_id":
            color_values = [str(vehicle.get("vehicle_id")) for vehicle in sorted(vehicles, key=lambda row: _numeric_or_zero(row.get("rank")))]
        else:
            color_values = [
                str(vehicle.get(color_by) or "Unknown")
                for vehicle in sorted(vehicles, key=lambda row: _numeric_or_zero(row.get("rank")))
            ]
        color_map = _discrete_color_map(color_values)
        continuous_min = continuous_max = None
    else:
        values = [_to_float(vehicle.get(color_by)) for vehicle in vehicles]
        numeric_values = [value for value in values if value is not None]
        continuous_min = min(numeric_values) if numeric_values else 0.0
        continuous_max = max(numeric_values) if numeric_values else 1.0
        color_map = {}

    vehicles_by_id = _vehicle_lookup(vehicles)
    grouped_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        grouped_points[str(point.get("vehicle_id"))].append(point)

    shown_legend_groups: set[str] = set()
    trace_index = 0
    for vehicle_id in selected:
        group = grouped_points.get(vehicle_id, [])
        vehicle = vehicles_by_id.get(vehicle_id)
        if not group or not vehicle:
            continue
        display_name = str(vehicle.get("display_name") or vehicle_id)
        group = sorted(group, key=lambda row: (_sort_key(row, x_axis), _sort_key(row, "point_index")))

        if discrete:
            color_value = str(vehicle_id if color_by == "vehicle_id" else vehicle.get(color_by) or "Unknown")
            line_color = color_map.get(color_value, "#333333")
            legend_name = display_name if color_by == "vehicle_id" else color_value
            legend_group = display_name if color_by == "vehicle_id" else color_value
            show_trace_legend = color_by == "vehicle_id" or legend_group not in shown_legend_groups
            shown_legend_groups.add(legend_group)
        else:
            numeric_value = _to_float(vehicle.get(color_by))
            if numeric_value is None:
                numeric_value = continuous_min or 0.0
            line_color = _continuous_color(float(numeric_value), continuous_min or 0.0, continuous_max or 1.0)
            legend_name = display_name
            legend_group = display_name
            show_trace_legend = False

        customdata = [
            [
                point.get("display_name"),
                point.get("soc_percent"),
                point.get("charging_power_kw"),
                point.get("charging_power_relative_percent"),
                point.get("manufacturer"),
                point.get("range_total_one_stop_km"),
                point.get("range_until_stop_km"),
                point.get("range_added_20min_km"),
            ]
            for point in group
        ]

        fig.add_trace(
            go.Scatter(
                x=[point.get(x_axis) for point in group],
                y=[point.get(y_axis) for point in group],
                mode="lines+markers" if style.marker_size > 0 else "lines",
                name=legend_name,
                showlegend=show_trace_legend,
                legendgroup=legend_group,
                opacity=style.opacity,
                line={
                    "width": style.line_width,
                    "color": line_color,
                    "shape": style.line_shape,
                    "dash": DASH_PATTERNS[trace_index % len(DASH_PATTERNS)]
                    if style.cycle_line_dash
                    else "solid",
                },
                marker={"size": style.marker_size, "color": line_color},
                customdata=customdata,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Manufacturer: %{customdata[4]}<br>"
                    "SOC: %{customdata[1]:.1f}%<br>"
                    "Charging power: %{customdata[2]:.1f} kW<br>"
                    "Relative power: %{customdata[3]:.1f}%<br>"
                    "Total range: %{customdata[5]} km<br>"
                    "Full-battery range: %{customdata[6]} km<br>"
                    "Range added in 20 min: %{customdata[7]} km"
                    "<extra></extra>"
                ),
            )
        )
        trace_index += 1

    if not discrete:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "colorscale": "Viridis",
                    "cmin": continuous_min,
                    "cmax": continuous_max,
                    "color": [continuous_min, continuous_max],
                    "showscale": True,
                    "colorbar": {
                        "title": {
                            "text": COLOR_LABELS.get(color_by, color_by),
                            "font": {"size": style.legend_font_size},
                        },
                        "tickfont": {"size": style.tick_font_size},
                    },
                },
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        title=_layout_title(style, f"ADAC/Infogram charging curves - {len(selected)} vehicle(s)"),
        xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
        yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
        template="plotly_white",
        width=style.plot_width,
        height=style.plot_height,
        font={"family": style.font_family, "size": style.font_size, "color": "black"},
        title_font={"size": style.title_font_size},
        paper_bgcolor="white",
        plot_bgcolor="white",
        hovermode="closest",
        showlegend=discrete,
        legend=_legend_layout(style),
        margin=_layout_margins(style),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.15)",
        gridwidth=0.5,
        showline=True,
        linecolor="black",
        linewidth=1,
        mirror=True,
        ticks="outside",
        ticklen=3,
        tickwidth=1,
        zeroline=False,
        nticks=6,
        title_font={"size": style.axis_title_font_size},
        tickfont={"size": style.tick_font_size},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.15)",
        gridwidth=0.5,
        showline=True,
        linecolor="black",
        linewidth=1,
        mirror=True,
        ticks="outside",
        ticklen=3,
        tickwidth=1,
        zeroline=False,
        nticks=5,
        title_font={"size": style.axis_title_font_size},
        tickfont={"size": style.tick_font_size},
    )
    return fig


def create_app(data_dir: str | Path = "output"):
    from dash import Dash, Input, Output, State, callback_context, dash_table, dcc, html, no_update

    dataset = load_dataset(data_dir)
    default_selected = dataset.vehicle_ids[:8]
    default_style = PlotStyle()

    app = Dash(__name__, title="ADAC EV Charging Curves")
    graph_config = {
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "svg",
            "filename": "adac_ev_charging_curves",
            "height": default_style.plot_height,
            "width": default_style.plot_width,
            "scale": 1,
        },
    }

    app.layout = html.Div(
        [
            html.Div(
                [
                    html.H1("ADAC/Infogram Charging Curves"),
                    html.Div(
                        [
                            html.Button("Select all", id="select-all", n_clicks=0),
                            html.Button("Select none", id="select-none", n_clicks=0),
                            html.Div(id="selection-summary"),
                        ],
                        className="toolbar",
                    ),
                ],
                className="header",
            ),
            dash_table.DataTable(
                id="vehicle-table",
                data=dataset.vehicle_records,
                columns=TABLE_COLUMNS,
                row_selectable="multi",
                selected_row_ids=default_selected,
                sort_action="native",
                filter_action="native",
                page_action="none",
                fixed_rows={"headers": True},
                style_table={"height": "340px", "overflowY": "auto", "overflowX": "auto"},
                style_cell={
                    "fontFamily": "Arial, sans-serif",
                    "fontSize": 13,
                    "padding": "6px 8px",
                    "whiteSpace": "normal",
                    "height": "auto",
                    "textAlign": "left",
                    "minWidth": "90px",
                },
                style_header={
                    "fontWeight": "700",
                    "backgroundColor": "#f3f4f6",
                    "borderBottom": "1px solid #cbd5e1",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    {"if": {"column_id": "display_name"}, "minWidth": "280px", "width": "360px"},
                ],
            ),
            html.Div(
                [
                    html.Label(
                        [
                            "Plot mode",
                            dcc.RadioItems(
                                PLOT_MODE_OPTIONS,
                                "vehicles",
                                id="plot-mode",
                                inline=True,
                                inputStyle={"marginRight": "4px", "marginLeft": "0"},
                                labelStyle={"marginRight": "12px", "fontWeight": "400"},
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Percentiles",
                            dcc.Input(
                                id="percentiles",
                                type="text",
                                value=DEFAULT_PERCENTILES_TEXT,
                                placeholder="Worst, 5, 10, ..., 95, Top",
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Percentile legend entries",
                            dcc.Input(
                                id="percentile-legend-entries",
                                type="text",
                                value=DEFAULT_PERCENTILE_LEGEND_TEXT,
                                placeholder="Worst, 25, 50, 75, Top; all; none",
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Percentile display",
                            dcc.Dropdown(
                                PERCENTILE_DISPLAY_OPTIONS,
                                "lines",
                                id="percentile-display",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Percentile legend",
                            dcc.Dropdown(
                                PERCENTILE_LEGEND_MODE_OPTIONS,
                                "entries",
                                id="percentile-legend-mode",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Percentile line dash",
                            dcc.Dropdown(
                                PERCENTILE_DASH_OPTIONS,
                                "cycle",
                                id="percentile-dash",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.Label(["X axis", dcc.Dropdown(AXIS_OPTIONS, "soc_percent", id="x-axis", clearable=False)]),
                    html.Label(
                        ["Y axis", dcc.Dropdown(AXIS_OPTIONS, "charging_power_kw", id="y-axis", clearable=False)]
                    ),
                    html.Label(
                        ["Line color", dcc.Dropdown(COLOR_OPTIONS, "manufacturer", id="color-by", clearable=False)]
                    ),
                    html.Label(
                        ["Line shape", dcc.Dropdown(LINE_SHAPE_OPTIONS, default_style.line_shape, id="line-shape", clearable=False)]
                    ),
                    html.Label(
                        [
                            "Legend position",
                            dcc.Dropdown(
                                LEGEND_POSITION_OPTIONS,
                                default_style.legend_position,
                                id="legend-position",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Figure title",
                            dcc.Input(
                                id="title-text",
                                type="text",
                                value="ADAC/Infogram Charging Curves",
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Font family",
                            dcc.Input(
                                id="font-family",
                                type="text",
                                value=default_style.font_family,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Line width",
                            dcc.Input(
                                id="line-width",
                                type="number",
                                min=0.2,
                                max=12,
                                step=0.2,
                                value=default_style.line_width,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Marker size",
                            dcc.Input(
                                id="marker-size",
                                type="number",
                                min=0,
                                max=20,
                                step=0.5,
                                value=default_style.marker_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Opacity",
                            dcc.Input(
                                id="line-opacity",
                                type="number",
                                min=0.05,
                                max=1,
                                step=0.05,
                                value=default_style.opacity,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Figure width / px",
                            dcc.Input(
                                id="plot-width",
                                type="number",
                                min=250,
                                max=4000,
                                step=1,
                                value=default_style.plot_width,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Figure height / px",
                            dcc.Input(
                                id="plot-height",
                                type="number",
                                min=180,
                                max=3000,
                                step=1,
                                value=default_style.plot_height,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Base font size",
                            dcc.Input(
                                id="font-size",
                                type="number",
                                min=8,
                                max=40,
                                step=1,
                                value=default_style.font_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Title font size",
                            dcc.Input(
                                id="title-font-size",
                                type="number",
                                min=10,
                                max=60,
                                step=1,
                                value=default_style.title_font_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Axis title font size",
                            dcc.Input(
                                id="axis-title-font-size",
                                type="number",
                                min=8,
                                max=44,
                                step=1,
                                value=default_style.axis_title_font_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Tick font size",
                            dcc.Input(
                                id="tick-font-size",
                                type="number",
                                min=6,
                                max=36,
                                step=1,
                                value=default_style.tick_font_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "Legend font size",
                            dcc.Input(
                                id="legend-font-size",
                                type="number",
                                min=6,
                                max=36,
                                step=1,
                                value=default_style.legend_font_size,
                            ),
                        ]
                    ),
                    html.Label(
                        [
                            "SAE options",
                            dcc.Checklist(
                                id="publication-options",
                                options=[
                                    {"label": "Show title", "value": "show_title"},
                                    {"label": "Cycle line styles", "value": "cycle_line_dash"},
                                ],
                                value=["cycle_line_dash"],
                                inputStyle={"marginRight": "4px"},
                                labelStyle={"display": "block", "fontWeight": "400"},
                            ),
                        ]
                    ),
                    html.Button("Export SVG", id="export-svg", n_clicks=0),
                    html.Div(id="export-status"),
                ],
                className="controls",
            ),
            html.Div(
                dcc.Graph(
                    id="curve-plot",
                    figure=build_figure(
                        dataset,
                        default_selected,
                        "soc_percent",
                        "charging_power_kw",
                        "manufacturer",
                        default_style,
                        "vehicles",
                        DEFAULT_PERCENTILES_TEXT,
                        DEFAULT_PERCENTILE_LEGEND_TEXT,
                    ),
                    config=graph_config,
                ),
                className="graph-wrap",
            ),
        ],
        className="page",
    )

    app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      body { margin: 0; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }
      .page { max-width: 1500px; margin: 0 auto; padding: 22px 28px 32px; }
      .header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
      h1 { margin: 0; font-size: 24px; line-height: 1.2; }
      .toolbar, .controls { display: flex; align-items: end; gap: 10px; flex-wrap: wrap; }
      button { border: 1px solid #9ca3af; background: #ffffff; color: #111827; border-radius: 6px; padding: 8px 11px; cursor: pointer; }
      button:hover { background: #f3f4f6; }
      .controls { margin: 16px 0 8px; }
      .controls label { min-width: 170px; font-size: 13px; font-weight: 700; color: #374151; }
      .controls label:first-child, .controls label:nth-child(2), .controls label:nth-child(3), .controls label:nth-child(4), .controls label:nth-child(5), .controls label:nth-child(6), .controls label:nth-child(7), .controls label:nth-child(8), .controls label:nth-child(9), .controls label:nth-child(10), .controls label:nth-child(11) { min-width: 250px; }
      .controls input { width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 4px; padding: 8px; }
      .graph-wrap { overflow-x: auto; }
      #selection-summary, #export-status { font-size: 13px; color: #4b5563; min-height: 20px; }
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th,
      .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td {
        border-color: #e5e7eb !important;
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""

    @app.callback(
        Output("vehicle-table", "selected_row_ids"),
        Input("select-all", "n_clicks"),
        Input("select-none", "n_clicks"),
        prevent_initial_call=True,
    )
    def update_selection(_: int, __: int) -> list[str]:
        trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
        if trigger == "select-all":
            return dataset.vehicle_ids
        if trigger == "select-none":
            return []
        return no_update

    @app.callback(
        Output("curve-plot", "figure"),
        Output("selection-summary", "children"),
        Input("vehicle-table", "selected_row_ids"),
        Input("plot-mode", "value"),
        Input("percentiles", "value"),
        Input("percentile-legend-entries", "value"),
        Input("percentile-display", "value"),
        Input("percentile-legend-mode", "value"),
        Input("percentile-dash", "value"),
        Input("x-axis", "value"),
        Input("y-axis", "value"),
        Input("color-by", "value"),
        Input("line-shape", "value"),
        Input("legend-position", "value"),
        Input("title-text", "value"),
        Input("font-family", "value"),
        Input("line-width", "value"),
        Input("marker-size", "value"),
        Input("line-opacity", "value"),
        Input("plot-width", "value"),
        Input("plot-height", "value"),
        Input("font-size", "value"),
        Input("title-font-size", "value"),
        Input("axis-title-font-size", "value"),
        Input("tick-font-size", "value"),
        Input("legend-font-size", "value"),
        Input("publication-options", "value"),
    )
    def update_plot(
        selected_row_ids: list[str] | None,
        plot_mode: str,
        percentiles: str,
        percentile_legend_entries: str,
        percentile_display: str,
        percentile_legend_mode: str,
        percentile_dash: str,
        x_axis: str,
        y_axis: str,
        color_by: str,
        line_shape: str,
        legend_position: str,
        title_text: str,
        font_family: str,
        line_width: float,
        marker_size: float,
        line_opacity: float,
        plot_width: int,
        plot_height: int,
        font_size: int,
        title_font_size: int,
        axis_title_font_size: int,
        tick_font_size: int,
        legend_font_size: int,
        publication_options: list[str] | None,
    ) -> tuple[go.Figure, str]:
        selected = selected_row_ids or []
        publication_options = publication_options or []
        style = make_plot_style(
            font_family=font_family,
            title_text=title_text,
            line_width=line_width,
            marker_size=marker_size,
            opacity=line_opacity,
            plot_width=plot_width,
            plot_height=plot_height,
            font_size=font_size,
            title_font_size=title_font_size,
            axis_title_font_size=axis_title_font_size,
            tick_font_size=tick_font_size,
            legend_font_size=legend_font_size,
            legend_position=legend_position,
            line_shape=line_shape,
            show_title="show_title" in publication_options,
            cycle_line_dash="cycle_line_dash" in publication_options,
        )
        figure = build_figure(
            dataset,
            selected,
            x_axis,
            y_axis,
            color_by,
            style,
            plot_mode,
            percentiles,
            percentile_legend_entries,
            percentile_display,
            percentile_legend_mode,
            percentile_dash,
        )
        mode_label = "percentile mode" if plot_mode == "percentiles" else "vehicle mode"
        return figure, f"{len(selected)} of {len(dataset.vehicle_ids)} vehicles selected; {mode_label}"

    app.clientside_callback(
        """
        function(n_clicks, width, height) {
          if (!n_clicks) {
            return "";
          }
          const graph = document.getElementById("curve-plot");
          const plot = graph ? graph.getElementsByClassName("js-plotly-plot")[0] : null;
          if (!plot || !window.Plotly) {
            return "SVG export is not ready yet";
          }
          window.Plotly.downloadImage(plot, {
            format: "svg",
            filename: "adac_ev_charging_curves",
            width: Number(width) || 1400,
            height: Number(height) || 760,
            scale: 1
          });
          return "SVG export started";
        }
        """,
        Output("export-status", "children"),
        Input("export-svg", "n_clicks"),
        State("plot-width", "value"),
        State("plot-height", "value"),
        prevent_initial_call=True,
    )

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adac-ev-curves-gui")
    parser.add_argument("--data", default="output", help="Directory containing vehicles.csv and charging_curve_points.csv.")
    parser.add_argument("--host", default="127.0.0.1", help="Dash host.")
    parser.add_argument("--port", type=int, default=8050, help="Dash port.")
    parser.add_argument("--debug", action="store_true", help="Enable Dash debug mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = create_app(args.data)
    print(json.dumps({"url": f"http://{args.host}:{args.port}", "data": str(Path(args.data).resolve())}, indent=2))
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
